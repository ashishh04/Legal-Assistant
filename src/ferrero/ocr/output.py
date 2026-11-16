"""Unlimited-OCR-2's page output -> sections of citable blocks, like the other document types.

The model writes each layout block as a header followed by the block's text::

    <PAGE><BLOCK>title<LEVEL1>[295, 72, 705, 93]<FORK>SPECIAL POWER OF ATTORNEY
    <BLOCK>text[102, 153, 893, 219]<FORK>Dolce Group International S.A., … duly authorised by resolution of the board,
    <MERGE>
    <BLOCK>text[101, 223, 893, 306]<FORK>hereby appoints Tariq Haddadin and Dana Khoury of Levant Legal Group …
    <BLOCK>footer[170, 955, 802, 970]<FORK>Power of attorney · TM-2025-415 · … Page 1 of 1

The header names the block type (title with its heading level, text, table, image, header, footer, …) and its box
on the page (0-1000). ``<MERGE>`` says the next block continues the same paragraph (across a column or page break).
Titles become section headings, tables one block per row; page furniture (running headers, footers, page numbers)
and images are dropped. DeepSeek-OCR's ``<|ref|>…<|det|>`` form is read the same way, and output without layout
markup falls back to the heuristics used for PDF text layers.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass

from ..sync.extract import HEADER_SECTION, Section, _clean, _is_heading, _strip_page_furniture, pdf_sections

_BLOCK_HEADER = re.compile(
    r"<BLOCK>\s*(?P<blk>[A-Za-z_][\w-]*)\s*(?:<LEVEL(?P<level>\d+)>)?\s*(?:\[[^\]]*\]\s*)*<FORK>"   # Unlimited-OCR-2
    r"|<\|ref\|>(?P<ref>.*?)<\|/ref\|>\s*<\|det\|>.*?<\|/det\|>"                                 # DeepSeek-OCR
    r"|<\|det\|>\s*(?P<det>[A-Za-z_][\w-]*)\s*(?:\[[^\]]*\]\s*)*<\|/det\|>",
    re.S)
_MERGE = re.compile(r"\s*<MERGE>\s*$")
_MARKERS = re.compile(r"<PAGE>|<CHILD>|<MERGE>|<LEVEL\d+>|<\|/?[a-z_]{1,24}\|>|<｜[^｜]{1,40}｜>")
_TABLE = re.compile(r"<table\b.*?</table>|<tr>.*</tr>", re.S | re.I)
_ROW = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.S | re.I)
_CELL = re.compile(r"<t([hd])\b[^>]*>(.*?)</t[hd]>", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")
_MD_HEADING = re.compile(r"^#{1,6}\s+")
_MD_EMPHASIS = re.compile(r"(\*\*|__)(.+?)\1")

HEADING_LABELS = {"title", "doc_title", "sub_title", "subtitle", "section_title", "section_header", "paragraph_title",
                  "heading", "header_title"}
DROP_LABELS = {"header", "page_header", "footer", "page_footer", "page_number", "number", "image", "figure", "chart",
               "seal", "stamp", "signature_image"}


@dataclass
class Block:
    label: str
    text: str
    level: int | None = None
    continues: bool = False  # the previous block's paragraph goes on here (<MERGE>)


def has_layout(raw: str) -> bool:
    return bool(_BLOCK_HEADER.search(raw))


def page_blocks(raw: str) -> list[Block]:
    """The layout blocks of one page, in reading order."""
    pieces: list[Block] = []
    label, level, pos = "text", None, 0
    for m in _BLOCK_HEADER.finditer(raw):
        pieces.append(Block(label, raw[pos:m.start()], level))
        label = (m.group("blk") or m.group("ref") or m.group("det") or "text").strip().lower()
        level = int(m.group("level")) if m.group("level") else None
        pos = m.end()
    pieces.append(Block(label, raw[pos:], level))
    blocks: list[Block] = []
    merge_next = False
    for b in pieces:
        merge_here = merge_next
        merge_next = bool(_MERGE.search(b.text))
        text = _MARKERS.sub(" ", _MERGE.sub("", b.text)).strip() if b.label != "table" else _MERGE.sub("", b.text).strip()
        if text:
            blocks.append(Block(b.label, text, b.level, continues=merge_here))
        elif merge_here:
            merge_next = True  # an empty block between two halves of a paragraph keeps the merge
    return blocks


def table_rows(text: str) -> list[str]:
    """HTML table rows -> one block per row: 'header: value; …' when there is a header row, like DOCX tables."""
    rows = []
    for row in _ROW.findall(text):
        cells = [(kind.lower(), _clean(html.unescape(_TAG.sub(" ", cell)))) for kind, cell in _CELL.findall(row)]
        if any(c for _, c in cells):
            rows.append(cells)
    if not rows:
        return [_inline(text)] if _inline(text) else []
    first = [c for _, c in rows[0]]
    header = first if len(rows) > 1 and (all(k == "h" for k, _ in rows[0]) or _looks_like_header(first, rows[1:])) else None
    out = []
    for cells in rows[1:] if header else rows:
        values = [c for _, c in cells]
        if header and len(header) == len(values) and len(values) > 2:
            out.append("; ".join(f"{h}: {v}" for h, v in zip(header, values)))
        elif len(values) == 2:
            out.append(f"{values[0]}: {values[1]}")
        else:
            out.append(" | ".join(values))
    return out


def _looks_like_header(first: list[str], rest: list[list[tuple[str, str]]]) -> bool:
    """A first row of short labels without digits over rows that carry figures reads as a header row."""
    if len(first) < 3 or any(re.search(r"\d", c) or len(c) > 40 for c in first):
        return False
    return any(re.search(r"\d", c) for row in rest for _, c in row)


def _inline(text: str) -> str:
    text = _MD_EMPHASIS.sub(r"\2", _TAG.sub(" ", text))
    return _clean(html.unescape(text))


def _paragraphs(text: str) -> list[str]:
    """A text block's lines -> paragraphs (blank lines and list items start new ones)."""
    paras, current = [], []
    for line in text.splitlines():
        line = _MD_HEADING.sub("", line.strip())
        if not line:
            if current:
                paras.append(" ".join(current))
                current = []
            continue
        if re.match(r"^(?:[-*•]\s+|\(?\d{1,2}[.)]\s+|[a-z]\)\s+)", line) and current:
            paras.append(" ".join(current))
            current = []
        current.append(line)
    if current:
        paras.append(" ".join(current))
    return [p for p in (_inline(p) for p in paras) if p]


def ocr_sections(pages: list[str]) -> list[Section]:
    """All pages of a recognised scan -> sections, headed by the document's own titles."""
    if not any(has_layout(p) for p in pages):
        return pdf_sections([_MARKERS.sub(" ", p) for p in pages])
    per_page = [page_blocks(p) for p in pages]
    # Letterheads and running footers repeated on every page are furniture even when labelled as text.
    kept = _strip_page_furniture([[b.text for b in blocks] for blocks in per_page])
    blocks = [b for page, keep in zip(per_page, kept) for b in page if b.text in keep and b.label not in DROP_LABELS]

    sections = [Section(HEADER_SECTION)]
    for i, b in enumerate(blocks):
        if b.label == "table" or _TABLE.search(b.text):
            sections[-1].blocks.extend(table_rows(b.text))
            continue
        paras = _paragraphs(b.text)
        if not paras:
            continue
        if b.continues and sections[-1].blocks:  # the same paragraph, split by a column or page break
            sections[-1].blocks[-1] = f"{sections[-1].blocks[-1]} {paras[0]}"
            paras = paras[1:]
            sections[-1].blocks.extend(paras)
            continue
        nxt = next((n.text for n in blocks[i + 1:]), "")
        single = len(paras) == 1 and len(paras[0]) <= 80
        if single and _is_section_title(b, paras[0], _inline(nxt)):
            sections.append(Section(paras[0].rstrip(":")))
            continue
        sections[-1].blocks.extend(paras)
    return [s for s in sections if s.blocks]


def _is_section_title(block: Block, text: str, nxt: str) -> bool:
    if block.label in HEADING_LABELS:
        # A document title always heads a section; a smaller title only when body text follows it (not the
        # name and position lines of a signature block, which the model also marks as titles).
        return block.level in (None, 1) or len(nxt) >= 40
    return block.label == "text" and _is_heading(text, nxt)
