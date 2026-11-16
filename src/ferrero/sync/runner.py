"""Run the document sync: list a source's changes, extract each file, tie it to a case, index it, record its status.

A file becomes searchable only when it can be tied to a case in the case tracker, because the case
decides who may read it (its access group):

1. the document catalogue (``fact_document``) lists the file name, or
2. the file name carries a case number (and the text does not name a different case), or
3. the text carries exactly one case number.

Files tied to a case through 2 or 3 must also *corroborate* it: the text has to mention the case's
mark or infringer (English or Arabic). A document that merely reuses a case number - another
matter's judgment, a misfiled scan - is recorded as skipped with the reason and never indexed.
"""
from __future__ import annotations

import csv
import hashlib
import logging
import re
from dataclasses import dataclass, field, replace
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from ..casemodel import CaseModel
from ..textproc import case_ids_in, contains, fold, is_arabic
from .chunker import passages
from .extract import ExtractionError, extract
from .index import DocumentIndex, DocumentRecord
from .sources import Source, SourceFile

if TYPE_CHECKING:
    from ..ocr.reader import OcrReader

log = logging.getLogger(__name__)

_TYPE_BY_NAME = {
    "judgment": "Judgment", "judgement": "Judgment", "حكم": "Judgment",
    "cease_and_desist": "Cease-and-desist letter", "statement_of_claim": "Statement of claim",
    "settlement_agreement": "Settlement agreement", "investigation_report": "Investigation report",
    "inspection_report": "Investigation report", "customs_seizure_notice": "Customs seizure notice",
    "licence_agreement": "Licence agreement", "license_agreement": "Licence agreement",
    "takedown_notice": "Takedown notice", "trademark_office_decision": "Trademark office decision",
    "evidence_test_purchase": "Evidence – test purchase", "power_of_attorney": "Power of attorney",
    "expert_report": "Expert report",
}
# Checked against the first lines of a document, in this order (most specific first; Judgment last).
_TYPE_BY_CONTENT = (
    ("Statement of claim", ("statement of claim", "صحيفه دعوي")),
    ("Settlement agreement", ("settlement agreement", "اتفاقيه تسويه")),
    ("Licence agreement", ("licence and distribution agreement", "licence agreement", "اتفاقيه ترخيص")),
    ("Cease-and-desist letter", ("cease-and-desist", "cease and desist", "انذار قانوني")),
    ("Investigation report", ("investigation report", "تقرير تحقيق")),
    ("Customs seizure notice", ("seizure notice", "حجز جمركي")),
    ("Takedown notice", ("takedown", "trademark infringement notice", "اخطار ازاله")),
    ("Trademark office decision", ("opposition", "اعتراضات العلامات")),
    ("Judgment", ("judgment", "حكم")),
)
STATUS_COLUMNS = ("doc_id", "case_id", "file_name", "doc_type", "language", "access_group", "sensitivity", "library_path",
                  "pages", "scanned", "ocr_confidence", "index_status", "skip_reason", "passages", "source", "indexed_at")


class Unresolved(Exception):
    pass


def _type_from_name(file_name: str) -> str | None:
    stem = PurePosixPath(file_name).stem
    stem = re.sub(r"(?i)TM-\d{4}-\d{3}|_(EN|AR)$|\(.*?\)", " ", stem)
    stem = stem.split(" - ")[0]
    key = re.sub(r"[\s\-_]+", "_", stem).strip("_").lower()
    return _TYPE_BY_NAME.get(key)


def _type_from_content(text: str) -> str | None:
    head = fold(text[:400])
    for doc_type, keywords in _TYPE_BY_CONTENT:
        if any(re.search(rf"(?<!\w){re.escape(k)}(?!\w)", head) for k in keywords):
            return doc_type
    return None


def _language(file_name: str) -> str | None:
    suffix = PurePosixPath(file_name).stem[-3:].upper()
    return suffix[1:] if suffix in ("_EN", "_AR") else None


def _doc_id(source: str, key: str) -> str:
    return "SP-" + hashlib.sha1(f"{source}:{key}".encode()).hexdigest()[:10].upper()


def resolve(f: SourceFile, model: CaseModel, source: str, text: str = "") -> tuple[DocumentRecord, list[str], bool]:
    """Tie a file to its case. Returns (record, review notes, authoritative mapping); raises ``Unresolved``.

    A manifest row or a catalogue entry is authoritative; otherwise the case comes from the name or the text.
    """
    hint = f.hints or {}
    entry = model.catalogue_entry(f.name)
    if hint.get("doc_id") and entry is None:  # manifests refer to catalogue rows by doc_id
        entry = model.catalogue_by_id(hint["doc_id"])
    if hint.get("case_id"):
        case_id = hint["case_id"].upper()
    elif entry is not None:
        case_id = entry["case_id"]
    else:
        name_ids = case_ids_in(f.name) or case_ids_in(f.library_path)
        text_ids = case_ids_in(text)
        if name_ids:
            case_id = name_ids[0]
            if text_ids and case_id not in text_ids:
                raise Unresolved(f"File name refers to {case_id} but the text refers to {', '.join(text_ids)}")
        elif len(text_ids) == 1:
            case_id = text_ids[0]
        elif text_ids:
            raise Unresolved(f"The text refers to several cases ({', '.join(text_ids)})")
        else:
            raise Unresolved("No case number in the file name or text")
    case = model.case(case_id)
    if case is None:
        raise Unresolved(f"Case {case_id} is not in the case tracker")

    notes: list[str] = []
    authoritative = bool(hint.get("case_id")) or entry is not None
    if authoritative:
        meta = entry or {}
        doc_id = hint.get("doc_id") or meta.get("doc_id") or _doc_id(source, f.key)
        doc_type = hint.get("doc_type") or meta.get("doc_type") or _type_from_content(text) or _type_from_name(f.name)
        language = (hint.get("language") or meta.get("language") or _language(f.name) or "").upper() or None
    else:
        doc_id, language = _doc_id(source, f.key), _language(f.name)
        by_name, by_content = _type_from_name(f.name), _type_from_content(text)
        doc_type = by_content or by_name
        if by_name and by_content and by_name != by_content:
            notes.append(f"File name says {by_name.lower()}, but the document is a {by_content.lower()}")
    record = DocumentRecord(
        doc_id=doc_id, source=source, source_key=f.key, file_name=f.name, case_id=case_id, doc_type=doc_type,
        language=language, access_group=case["access_group"],
        sensitivity=(entry or {}).get("sensitivity") or case["sensitivity"],
        library_path=f.library_path, version=f.version, modified_at=f.modified_at,
    )
    return record, notes, authoritative


def corroborates(text: str, names: list[str]) -> bool:
    folded = fold(text)
    return any(contains(folded, n) for n in names)


@dataclass
class SyncResult:
    source: str
    indexed: list[str] = field(default_factory=list)
    flagged: list[tuple[str, str]] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    pending: list[tuple[str, str]] = field(default_factory=list)  # could not be read: retried next run
    awaiting_ocr: list[str] = field(default_factory=list)          # scans waiting for text recognition: retried too
    recognised: int = 0                                            # scans indexed from recognised text
    unchanged: int = 0
    deleted: int = 0

    def summary(self) -> str:
        lines = [f"Source: {self.source}",
                 f"  indexed {len(self.indexed)}, indexed with review flags {len(self.flagged)}, skipped {len(self.skipped)}, "
                 f"pending {len(self.pending)}, waiting for text recognition {len(self.awaiting_ocr)}, "
                 f"unchanged {self.unchanged}, removed {self.deleted}"]
        if self.recognised:
            lines.append(f"  {self.recognised} scanned documents indexed from recognised text")
        for label, items in (("flagged", self.flagged), ("skipped", self.skipped), ("pending", self.pending)):
            lines += [f"  {label:8s} {name}: {reason}" for name, reason in items]
        if self.awaiting_ocr:
            lines.append(f"  {len(self.awaiting_ocr)} scans are waiting for text recognition: run  python -m ferrero.ocr")
        return "\n".join(lines)


def run_sync(source: Source, index: DocumentIndex, model: CaseModel, *, full: bool = False,
             verify_content: bool = True, status_csv: Path | None = None, ocr: OcrReader | None = None) -> SyncResult:
    """``ocr`` gives scans their recognised text (from the OCR cache, or an engine); without it scans wait."""
    result = SyncResult(source.name)
    state_key = f"cursor:{source.name}"
    cursor = None if full else index.get_state(state_key)
    changes = source.changes(cursor)
    known = index.versions(source.name)
    seen: set[str] = set()

    def placeholder(f: SourceFile, sha: str | None) -> DocumentRecord:
        return DocumentRecord(doc_id=_doc_id(source.name, f.key), source=source.name, source_key=f.key, file_name=f.name,
                              case_id="", doc_type=_type_from_name(f.name), language=_language(f.name), access_group="",
                              sensitivity=None, library_path=f.library_path, version=f.version, modified_at=f.modified_at,
                              content_sha=sha)

    def skip(record: DocumentRecord, reason: str) -> None:
        index.upsert(record, [], "Skipped", reason)
        result.skipped.append((record.file_name, reason))

    def wait(record: DocumentRecord, reason: str) -> None:
        index.upsert(record, [], "Pending", reason)
        result.awaiting_ocr.append(record.file_name)

    # Catalogued files first, so that when two files are identical the catalogued one is indexed and the
    # other recorded as its duplicate (stable sort: listing order is kept within each group).
    for f in sorted(changes.files, key=lambda f: not (f.hints.get("case_id") or model.catalogue_entry(f.name))):
        seen.add(f.key)
        previous = known.get(f.key)
        if not full and previous and previous[0] == f.version and previous[1] != "Pending":
            result.unchanged += 1
            continue
        try:
            data = f.read()
        except Exception as e:  # download failure: keep it queued and retry next run
            log.exception("Could not read %s", f.name)
            reason = f"Queued for reindex ({type(e).__name__})"
            index.upsert(replace(placeholder(f, None), version=None), [], "Pending", reason)
            result.pending.append((f.name, reason))
            continue
        sha = hashlib.sha256(data).hexdigest()
        extracted, error = None, None
        try:
            extracted = extract(f.name, data, ocr=ocr)
        except ExtractionError as e:
            error = e
        text = extracted.text if extracted else ""
        how = dict(extraction=extracted.extraction, ocr_confidence=extracted.ocr_confidence, pages=extracted.pages) \
            if extracted else dict(extraction=error.extraction, ocr_confidence=error.ocr_confidence)

        try:
            record, notes, catalogued = resolve(f, model, source.name, text)
        except Unresolved as e:
            if error is not None and error.status == "Pending":  # its recognised text may tie it to a case
                wait(replace(placeholder(f, sha), **how), error.reason)
            else:
                skip(replace(placeholder(f, sha), **how), f"{error.reason}; {e}" if error else str(e))
            continue
        record = replace(record, content_sha=sha, **how)
        if error is not None:
            (wait if error.status == "Pending" else skip)(record, error.reason)
            continue

        names = model.case_names(record.case_id)
        if not corroborates(text, names):
            mismatch = (f"Content does not match {record.case_id} in the case tracker "
                        f"(no mention of {' or '.join(names[::2]) or 'its mark or parties'})")
            if verify_content and not catalogued:
                skip(record, mismatch)
                continue
            notes.append(mismatch)
        duplicate = index.duplicate_of(sha, source.name, f.key)
        if duplicate:
            skip(record, f"Duplicate of {duplicate}")
            continue

        found = passages(extracted.sections)
        if record.language is None:
            record = replace(record, language="AR" if is_arabic(text) else "EN")
        flags = "; ".join(x for x in [extracted.flag, *notes] if x) or None
        index.upsert(record, found, "Indexed (flagged)" if flags else "Indexed", flags)
        result.recognised += extracted.extraction == "ocr"
        if flags:
            result.flagged.append((f.name, flags))
        else:
            result.indexed.append(f.name)

    removed = list(changes.deleted)
    if changes.complete:
        removed += [key for key in known if key not in seen]
    for key in removed:
        result.deleted += index.delete(source.name, key)

    # Only advance an incremental cursor when everything in this batch was processed (scans waiting for text
    # recognition included: the next run must list them again).
    if not result.pending and not result.awaiting_ocr:
        index.set_state(state_key, changes.cursor)
    if status_csv is not None:
        write_status(index, status_csv)
    return result


def write_status(index: DocumentIndex, path: Path) -> None:
    """Per-document sync status in the shape of fact_document (load it back into the lakehouse)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=STATUS_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in index.catalogue():
            writer.writerow({**row, "scanned": row.get("extraction") == "ocr"})
