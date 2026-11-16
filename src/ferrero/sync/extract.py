"""Turn a case document into ordered sections of citable blocks (paragraphs, list items, table rows)."""
from __future__ import annotations

import hashlib
import io
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import PurePath
from typing import TYPE_CHECKING

import docx
from docx.table import Table
from docx.text.paragraph import Paragraph

from ..textproc import has_presentation_forms

if TYPE_CHECKING:
    from ..ocr.reader import OcrReader

log = logging.getLogger(__name__)
HEADER_SECTION = "Header"
SUPPORTED_SUFFIXES = (".docx", ".pdf", ".txt", ".md")
MIN_TEXT_CHARS_PER_PAGE = 40  # below this a PDF is treated as scanned (image-only)
# Reasons for scans, in the catalogue's vocabulary (fact_document.skip_reason) where it has one.
AWAITING_OCR = "Scanned PDF – waiting for text recognition"
LOW_OCR_CONFIDENCE = "OCR confidence below threshold"
REVIEW_PAGES = "Low-confidence pages flagged for review"


class ExtractionError(Exception):
    """The file cannot be indexed (now); ``reason`` uses the catalogue's skip-reason vocabulary.

    ``status`` is "Skipped", or "Pending" when the file will be retried (a scan waiting for text recognition).
    """

    def __init__(self, reason: str, *, status: str = "Skipped", extraction: str | None = None,
                 ocr_confidence: float | None = None):
        super().__init__(reason)
        self.reason = reason
        self.status = status
        self.extraction = extraction
        self.ocr_confidence = ocr_confidence


@dataclass
class Section:
    heading: str
    blocks: list[str] = field(default_factory=list)


@dataclass
class Extracted:
    sections: list[Section]
    pages: int | None = None
    flag: str | None = None  # set when indexed but needs review (e.g. low OCR confidence)
    extraction: str = "text"  # "text" (the file's own text) or "ocr" (recognised from page images)
    ocr_confidence: float | None = None

    @property
    def text(self) -> str:
        return "\n".join([s.heading for s in self.sections] + [b for s in self.sections for b in s.blocks])


def extract(file_name: str, data: bytes, ocr: OcrReader | None = None) -> Extracted:
    """``ocr`` supplies recognised text for scans; without it a scan is reported as waiting for recognition."""
    suffix = PurePath(file_name).suffix.lower()
    if suffix == ".docx":
        return _docx(data)
    if suffix == ".pdf":
        return _pdf(data, file_name, ocr)
    if suffix in (".txt", ".md"):
        return _text(data.decode("utf-8", errors="replace"))
    raise ExtractionError(f"Unsupported file type ({suffix or 'no extension'})")


# ---------- DOCX ----------
def _docx(data: bytes) -> Extracted:
    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as e:  # corrupt or not really a DOCX
        raise ExtractionError(f"Unreadable DOCX ({type(e).__name__})") from None
    sections = [Section(HEADER_SECTION)]
    list_no = 0
    for element in document.element.body.iterchildren():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag == "p":
            p = Paragraph(element, document)
            text = _clean(p.text)
            if not text:
                continue
            style = (p.style.name if p.style is not None else "") or ""
            if style.startswith("Heading"):
                sections.append(Section(text))
                list_no = 0
                continue
            if p._p.pPr is not None and p._p.pPr.numPr is not None:  # numbered / bulleted item
                list_no += 1
                text = f"{list_no}. {text}"
            sections[-1].blocks.append(text)
        elif tag == "tbl":
            sections[-1].blocks.extend(_table_rows(Table(element, document)))
    sections = [s for s in sections if s.blocks]
    if not sections:
        raise ExtractionError("No text found")
    return Extracted(sections)


def _table_rows(table: Table) -> list[str]:
    rows: list[list[str]] = []
    for row in table.rows:
        cells: list[str] = []
        for cell in row.cells:  # python-docx repeats merged cells; keep each once
            text = _clean(cell.text)
            if not cells or cells[-1] != text:
                cells.append(text)
        if any(cells):
            rows.append(cells)
    if not rows:
        return []
    header = rows[0] if len(rows) > 1 and _is_header_row(table) else None
    out = []
    for cells in rows[1:] if header else rows:
        if header and len(header) == len(cells) and len(cells) > 2:
            out.append("; ".join(f"{h}: {v}" for h, v in zip(header, cells)))
        elif len(cells) == 2:
            out.append(f"{cells[0]}: {cells[1]}")
        else:
            out.append(" | ".join(cells))
    return out


def _is_header_row(table: Table) -> bool:
    runs = [r for cell in table.rows[0].cells for p in cell.paragraphs for r in p.runs if r.text.strip()]
    return bool(runs) and all(r.bold for r in runs)


# ---------- PDF ----------
def _pdf(data: bytes, file_name: str = "", ocr: OcrReader | None = None) -> Extracted:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:  # an owner-password-only PDF opens with an empty user password
                opened = bool(reader.decrypt(""))
            except Exception:  # e.g. AES-256 without the optional crypto dependency: treat as locked
                opened = False
            if not opened:
                raise ExtractionError("Password-protected PDF")
        pages = [(_clean_multiline(page.extract_text() or "")) for page in reader.pages]
    except ExtractionError:
        raise
    except Exception as e:
        if b"/Encrypt" in data:  # pypdf can fail while opening an encrypted file (e.g. AES-256 without the crypto extra)
            raise ExtractionError("Password-protected PDF") from None
        raise ExtractionError(f"Unreadable PDF ({type(e).__name__})") from None  # malformed or truncated
    if sum(len(p) for p in pages) < MIN_TEXT_CHARS_PER_PAGE * max(1, len(pages)):
        return _scan(data, file_name, ocr)  # image-only: the text has to be recognised from the page images
    flag = None
    if any(has_presentation_forms(p) for p in pages):
        # Shaped Arabic glyphs: NFKC restores the letters, but runs of digits and Latin text inside
        # right-to-left lines can come out in visual order, so dates and amounts need checking.
        pages = [unicodedata.normalize("NFKC", p) for p in pages]
        flag = "Arabic PDF text layer uses presentation forms – check dates and amounts against the original"
    sections = pdf_sections(pages)
    if not sections:
        raise ExtractionError("No text found")
    return Extracted(sections, pages=len(pages), flag=flag)


def _pages_phrase(numbers: list[int]) -> str:
    if len(numbers) == 1:
        return f"page {numbers[0]}"
    return "pages " + ", ".join(map(str, numbers[:-1])) + f" and {numbers[-1]}"


def _scan(data: bytes, file_name: str, ocr: OcrReader | None) -> Extracted:
    """A scanned PDF, from its recognised text (Unlimited-OCR-2, see ferrero.ocr)."""
    from ..ocr.output import ocr_sections
    from ..ocr.scans import ScanError

    try:
        result = ocr.read(data, hashlib.sha256(data).hexdigest(), file_name) if ocr is not None else None
    except ScanError as e:
        raise ExtractionError(f"Scanned PDF – {e}", extraction="ocr") from None
    except Exception as e:  # the recognition engine failed (server down, out of memory…): keep the file queued
        log.warning("Text recognition failed for %s: %s", file_name, e)
        raise ExtractionError(f"{AWAITING_OCR} (last attempt failed)", status="Pending", extraction="ocr") from None
    if result is None:
        raise ExtractionError(AWAITING_OCR, status="Pending", extraction="ocr")

    confidence = result.confidence
    if confidence is not None and confidence < ocr.min_confidence:
        raise ExtractionError(LOW_OCR_CONFIDENCE, extraction="ocr", ocr_confidence=confidence)
    sections = ocr_sections([p.text for p in result.pages])
    if not sections:
        raise ExtractionError("No text found", extraction="ocr", ocr_confidence=confidence)
    review = [p.number for p in result.pages
              if p.finish != "stop" or (p.score is not None and p.score < ocr.review_confidence)]
    flag = f"{REVIEW_PAGES} ({_pages_phrase(review)})" if review else None
    return Extracted(sections, pages=len(result.pages), flag=flag, extraction="ocr", ocr_confidence=confidence)


# ---------- PDF structure recovery ----------
# A PDF text layer has lines, not paragraphs or headings. These heuristics rebuild both, so PDF citations point
# at a paragraph under its real section heading ("Operative part"), as they do for Word documents.
_LIST_ITEM = re.compile(r"^\(?\d{1,2}[.)]\s+")
_FOOTER = re.compile(r"·.*\bPage\s+\d+\s*$|^Page\s+\d+(\s+of\s+\d+)?$", re.IGNORECASE)
_SENTENCE_END = (".", ":", ";", "!", "?", "؟", "؛")
_ABBREVIATION_END = re.compile(r"\b(Co|No|Ltd|Inc|S\.A|St|Mr|Ms|Dr|Art|Nos)\.$")
_INNER_PUNCTUATION = re.compile(r"[;,،؛]")


def _strip_page_furniture(pages: list[list[str]]) -> list[list[str]]:
    """Drop running headers/footers: lines repeated on every page (digits ignored) and '… · Page N' lines."""
    norm = lambda s: re.sub(r"\d+", "#", s.strip())  # noqa: E731
    repeated: set[str] = set()
    non_empty = [{norm(line) for line in p if line.strip()} for p in pages]
    if len(pages) > 1 and all(non_empty):
        repeated = set.intersection(*non_empty)
    return [[line for line in p if norm(line) not in repeated and not _FOOTER.search(line.strip())] for p in pages]


def _is_heading(line: str, nxt: str) -> bool:
    text = _LIST_ITEM.sub("", line)  # "2. Settlement payment" -> "Settlement payment"
    if len(line) > 60 or len(line.split()) > 6 or line.endswith(_SENTENCE_END):
        return False
    if _INNER_PUNCTUATION.search(text) or re.search(r"\d", text):  # headings carry no clauses, dates or amounts
        return False
    # A heading introduces body text: a full line, a numbered item, or a lead-in such as "the Court rules:".
    if not (len(nxt) >= 50 or _LIST_ITEM.match(nxt) or nxt.endswith(":") or nxt.startswith(":")):
        return False
    first = text[:1]
    return not (first.isascii() and first.isalpha() and first.islower())  # lower-case Latin start: a wrapped line


def pdf_sections(pages: list[str]) -> list[Section]:
    lines = [line.strip() for page in _strip_page_furniture([p.splitlines() for p in pages]) for line in page]
    sections = [Section(HEADER_SECTION)]
    para: list[str] = []

    def flush() -> None:
        if para:
            sections[-1].blocks.append(_clean(" ".join(para)))
            para.clear()

    for i, line in enumerate(lines):
        if not line:
            flush()
            continue
        nxt = next((n for n in lines[i + 1:] if n), "")
        if _is_heading(line, nxt):
            flush()
            sections.append(Section(_clean(line)))
            continue
        if _LIST_ITEM.match(line):
            flush()
        para.append(line)
        starts_new = bool(_LIST_ITEM.match(nxt)) or (nxt[:1].isupper() or nxt[:1].isdigit() or not nxt[:1].isascii())
        if line.endswith(_SENTENCE_END) and not _ABBREVIATION_END.search(line) and starts_new:
            flush()
    flush()
    return [s for s in sections if s.blocks]


# ---------- plain text / markdown ----------
def _text(text: str) -> Extracted:
    sections = [Section(HEADER_SECTION)]
    for para in _paragraphs(text):
        m = re.match(r"#{1,6}\s+(.*)", para)
        if m:
            sections.append(Section(_clean(m.group(1))))
        else:
            sections[-1].blocks.append(para)
    sections = [s for s in sections if s.blocks]
    if not sections:
        raise ExtractionError("No text found")
    return Extracted(sections)


# ---------- helpers ----------
def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace(" ", " ")).strip()


def _clean_multiline(text: str) -> str:
    return "\n".join(_clean(line) for line in text.splitlines()).strip()


def _paragraphs(text: str) -> list[str]:
    paras, current = [], []
    for line in text.splitlines():
        if line.strip():
            current.append(line.strip())
        elif current:
            paras.append(_clean(" ".join(current)))
            current = []
    if current:
        paras.append(_clean(" ".join(current)))
    return [p for p in paras if p]
