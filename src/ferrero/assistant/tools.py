"""The assistant's tools: definitions (fixed for every request, so the prompt cache holds) and their execution.

Every tool runs for one principal. Documents come back as ``search_result`` blocks so Claude cites the
exact paragraphs it used; case data comes back as JSON. Access is enforced here and in the data layer,
never by the prompt: a case or document the user may not see is reported exactly like one that does
not exist.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from ..casemodel import CaseModel, QueryError
from ..security import Principal
from ..sync.index import DocumentIndex, Hit

DOC_TYPES = (
    "Judgment", "Statement of claim", "Cease-and-desist letter", "Settlement agreement", "Licence agreement",
    "Investigation report", "Customs seizure notice", "Takedown notice", "Trademark office decision",
    "Evidence – test purchase", "Power of attorney", "Expert report",
)
CASE_ID = re.compile(r"TM-\d{4}-\d{3}\Z", re.IGNORECASE)
MAX_READ_CHARS = 60_000

CASE_DATA_GUIDE = """\
Tables (SQLite). Dates are ISO text 'YYYY-MM-DD', timestamps 'YYYY-MM-DD HH:MM:SS'; booleans are 0/1; amounts are integers.
- fact_case (one row per case): case_id ('TM-YYYY-NNN'), title, case_type, country, court_id, court_name, source_channel, \
opened_date, closed_date, status ('Open'|'Closed'), stage (Intake, Investigation, Notice sent, Filed, Hearing, Judgment, Appeal, \
Settled, Closed), outcome (Won, Partially won, Settled, Takedown achieved, Lost, Withdrawn, Pending), priority, risk_rating, \
mark_id, mark_name, infringer_id, infringer_name, infringer_type, lead_counsel_id, lead_counsel, external_firm, currency (local), \
claim_amount_local, claim_amount_aed, awarded_amount_local, awarded_amount_aed, settlement_amount_local, settlement_amount_aed, \
recovered_amount_local, recovered_amount_aed, next_hearing_date, next_action, next_action_due, last_action_date, days_open, \
legal_spend_aed, language, sensitivity, access_group, sharepoint_library
- fact_case_event: event_id, case_id, event_date, event_type, description, owner_user_id, external_fees_aed
- fact_invoice (external counsel): invoice_id, case_id, firm, invoice_date, category, amount_aed, status
- fact_document (document catalogue, metadata only): doc_id, case_id, doc_type, title (file name), language, doc_date, pages, \
scanned, sensitivity, library_path
- fact_mailbox (infringement mailbox): email_id, received_at, reporter_type, sender_domain, subject, country, mark_id, channel, \
triage_status, triaged_at, sla_hours, sla_breached, linked_case_id, assigned_to
- fact_intake_form: form_id, submitted_at, submitter_team, mark_id, country, infringement_type, evidence_files, estimated_units, \
status, converted_case_id
- fact_appstore: app_id, store, app_name, developer, mark_id, country, detected_date, status, takedown_requested_date, \
removed_date, est_downloads, linked_case_id
- dim_mark: mark_id, mark_name, mark_name_ar, product_category, nice_classes, uae_registration_no, registered_in
- dim_infringer: infringer_id, infringer_name_en, infringer_name_ar, infringer_type, country, city, case_count, repeat_offender, first_seen
- dim_court: court_id, country, city, court_name_en, court_name_ar, court_type, currency
- dim_user: user_id, full_name, job_title, team, country, entra_group
reporting_date() returns today's date for reporting: use it instead of date('now').
Definitions used by the dashboards: win rate = cases with outcome in (Won, Partially won, Settled, Takedown achieved) divided by \
cases with those outcomes or Lost; recovery rate = recovered / (awarded + settled); a hearing "in the next 30 days" is an open case \
with next_hearing_date between reporting_date() and date(reporting_date(), '+30 days'); an action is overdue when an open case has \
next_action_due < reporting_date()."""

TOOLS: list[dict[str, Any]] = [
    {
        "name": "search_case_documents",
        "description": (
            "Search the text of the case documents in the SharePoint case libraries: judgments, statements of claim, "
            "cease-and-desist letters, settlement and licence agreements, investigation reports, customs seizure notices, "
            "takedown notices and trademark-office decisions. Returns the best-matching passages with their file and section; "
            "passages you use are cited in your answer. Use it for anything a document says: amounts claimed or awarded, terms, "
            "deadlines, findings, parties, reasons. Documents are in English or Arabic and the question may be in the other "
            "language: write `query` as keywords in the language the document is likely to be in, and when unsure search once in "
            "English and once in Arabic. Set `case_id` whenever the question names a case. Only documents the signed-in user "
            "may open are searched."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keywords to look for, e.g. 'damages awarded compensation' or 'التعويض المحكوم به'."},
                "case_id": {"type": "string", "description": "Restrict to one case, format TM-YYYY-NNN."},
                "doc_type": {"type": "string", "enum": list(DOC_TYPES), "description": "Restrict to one document type."},
                "language": {"type": "string", "enum": ["EN", "AR"], "description": "Restrict to documents in this language."},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 10, "description": "Passages to return (default 6)."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "read_case_document",
        "description": (
            "Read a whole case document, section by section (citable). Use it after a search when you need full context, for "
            "example to compare two judgments or to check every clause of an agreement. Identify the document by its file name "
            "as shown in search results or by get_case."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"file_name": {"type": "string", "description": "File name, e.g. TM-2024-428_Judgment_EN.docx."}},
            "required": ["file_name"],
        },
    },
    {
        "name": "get_case",
        "description": (
            "Get one case from the case tracker: status, stage, outcome, court, mark, infringer, lead counsel, external firm, "
            "amounts claimed, awarded, settled and recovered (local currency and AED), next hearing, next action and its due date, "
            "the event timeline, invoice totals, and the documents on file (with whether their text is searchable). Use it for "
            "where a case stands and what happens next."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"case_id": {"type": "string", "description": "Case number, format TM-YYYY-NNN."}},
            "required": ["case_id"],
        },
    },
    {
        "name": "query_case_data",
        "description": (
            "Run one read-only SQLite SELECT over the case-tracker data - the same model behind the Power BI dashboards - for "
            "counts, totals, rankings and lists across cases, intake reports, app-store detections and invoices. Only rows the "
            "signed-in user may see exist. At most 200 rows are returned, so aggregate in SQL instead of fetching raw rows.\n\n"
            + CASE_DATA_GUIDE
        ),
        "input_schema": {
            "type": "object",
            "properties": {"sql": {"type": "string", "description": "A single SELECT statement."}},
            "required": ["sql"],
        },
    },
]
DOCUMENT_TOOLS = frozenset({"search_case_documents", "read_case_document"})
CASE_DATA_TOOLS = frozenset({"get_case", "query_case_data"})
NO_DOCUMENT_ACCESS = "The signed-in user's role has no access to case documents."


@dataclass(frozen=True)
class SourceRef:
    """A passage Claude was given, keyed by the ``source`` string its citations carry."""
    source: str
    title: str
    file_name: str
    doc_id: str
    case_id: str
    doc_type: str | None
    language: str | None
    section: str
    library_path: str
    sensitivity: str | None
    scanned: bool = False  # the passage's text was recognised from a scanned copy

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ToolOutcome:
    content: str | list[dict[str, Any]]
    is_error: bool = False
    sources: list[SourceRef] = field(default_factory=list)
    summary: str = ""

    def as_tool_result(self, tool_use_id: str) -> dict[str, Any]:
        block: dict[str, Any] = {"type": "tool_result", "tool_use_id": tool_use_id, "content": self.content}
        if self.is_error:
            block["is_error"] = True
        return block


def _title(h: Hit) -> str:
    scan = ", text recognised from a scanned copy" if h.extraction == "ocr" else ""
    return f"{h.file_name} · {h.section} ({h.doc_type or 'document'}, {h.language or '?'}, case {h.case_id}{scan})"


def _search_result(h: Hit) -> dict[str, Any]:
    return {
        "type": "search_result",
        "source": h.source,
        "title": _title(h),
        "content": [{"type": "text", "text": b} for b in h.blocks],
        "citations": {"enabled": True},  # all-or-nothing per request: every search_result we send enables citations
    }


def _ref(h: Hit) -> SourceRef:
    return SourceRef(h.source, _title(h), h.file_name, h.doc_id, h.case_id, h.doc_type, h.language, h.section,
                     h.library_path, h.sensitivity, scanned=h.extraction == "ocr")


def case_detail(model: CaseModel, index: DocumentIndex, principal: Principal, case_id: str) -> dict[str, Any] | None:
    """One case as the principal may see it, with each catalogued document marked searchable or not.

    Shared by the get_case tool and the web case page, so both always say the same thing.
    """
    summary = model.case_summary(principal, case_id)
    if summary is None or not isinstance(summary["documents_on_file"], list):
        return summary
    synced = index.case_files(case_id)
    by_id = {d["doc_id"]: d for d in synced}
    by_name = {d["file_name"]: d for d in synced}
    matched: set[str] = set()
    for doc in summary["documents_on_file"]:
        status = by_id.get(doc["doc_id"]) or by_name.get(doc["title"])
        doc["text_searchable"] = bool(status and status["index_status"].startswith("Indexed"))
        if status:
            matched.add(status["doc_id"])
            doc["file_name"] = status["file_name"]  # the synced file may be named differently
            doc["synced_doc_id"] = status["doc_id"]
            doc.update(_sync_notes(status, doc["text_searchable"]))
    for status in synced:  # synced files the catalogue does not list (e.g. added in SharePoint)
        if status["doc_id"] not in matched:
            searchable = status["index_status"].startswith("Indexed")
            summary["documents_on_file"].append({
                "file_name": status["file_name"], "doc_type": status["doc_type"], "language": status["language"],
                "synced_doc_id": status["doc_id"], "text_searchable": searchable, **_sync_notes(status, searchable),
            })
    return summary


def _sync_notes(status: dict[str, Any], searchable: bool) -> dict[str, Any]:
    notes: dict[str, Any] = {}
    if status.get("extraction") == "ocr":
        notes["scanned_copy"] = True  # its text, if any, was recognised from the page images
        if status.get("ocr_confidence") is not None:
            notes["ocr_confidence"] = round(status["ocr_confidence"], 2)
    if status["skip_reason"]:
        notes["sync_note" if not searchable else "review_note"] = status["skip_reason"]
    return notes


def _text(value: Any, name: str, required: bool = False) -> str | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise ValueError(f"`{name}` is required.")
        return None
    if not isinstance(value, str):
        raise ValueError(f"`{name}` must be a string.")
    return value.strip()


def _case_id(value: Any, required: bool = False) -> str | None:
    value = _text(value, "case_id", required)
    if value is not None and not CASE_ID.match(value):
        raise ValueError("`case_id` must look like TM-2024-428.")
    return value.upper() if value else None


class ToolBox:
    def __init__(self, principal: Principal, model: CaseModel, index: DocumentIndex, max_rows: int = 200):
        self.principal, self.model, self.index, self.max_rows = principal, model, index, max_rows

    def run(self, name: str, tool_input: Any) -> ToolOutcome:
        handlers = {
            "search_case_documents": self._search, "read_case_document": self._read,
            "get_case": self._get_case, "query_case_data": self._query,
        }
        handler = handlers.get(name)
        if handler is None:
            return ToolOutcome(f"Unknown tool: {name}", is_error=True, summary=f"Unknown tool {name}")
        if not isinstance(tool_input, dict):
            return ToolOutcome("Tool input must be an object.", is_error=True, summary="Invalid input")
        try:
            return handler(tool_input)
        except (ValueError, QueryError) as e:
            return ToolOutcome(str(e), is_error=True, summary=str(e))

    # ---------- documents ----------
    def _search(self, args: dict[str, Any]) -> ToolOutcome:
        query = _text(args.get("query"), "query", required=True)
        case_id = _case_id(args.get("case_id"))
        doc_type = _text(args.get("doc_type"), "doc_type")
        if doc_type is not None and doc_type not in DOC_TYPES:
            raise ValueError(f"`doc_type` must be one of: {', '.join(DOC_TYPES)}.")
        language = (_text(args.get("language"), "language") or "").upper() or None
        if language not in (None, "EN", "AR"):
            raise ValueError("`language` must be EN or AR.")
        limit = args.get("max_results", 6)
        limit = max(1, min(10, limit)) if isinstance(limit, int) and not isinstance(limit, bool) else 6
        scope = f" in {case_id}" if case_id else ""
        if not self.principal.sees_documents:
            return ToolOutcome(NO_DOCUMENT_ACCESS, summary="No document access for this role")
        hits = self.index.search(self.principal, query, case_id=case_id, doc_type=doc_type, language=language, limit=limit)
        if not hits:
            return ToolOutcome(f"No matching passages{scope} in the documents available to the signed-in user.",
                               summary=f"Searched documents{scope}: no matches")
        return ToolOutcome([_search_result(h) for h in hits], sources=[_ref(h) for h in hits],
                           summary=f"Searched documents{scope}: {len(hits)} passages")

    def _read(self, args: dict[str, Any]) -> ToolOutcome:
        file_name = _text(args.get("file_name"), "file_name", required=True)
        if not self.principal.sees_documents:
            return ToolOutcome(NO_DOCUMENT_ACCESS, summary="No document access for this role")
        found = self.index.document(self.principal, file_name)
        if found is None:
            return ToolOutcome(f"No searchable document named {file_name} is available to the signed-in user.",
                               summary=f"Read {file_name}: not available")
        meta, hits = found
        kept, total = [], 0
        for h in hits:
            size = sum(len(b) for b in h.blocks)
            if kept and total + size > MAX_READ_CHARS:
                break
            kept.append(h)
            total += size
        blocks = [_search_result(h) for h in kept]
        if len(kept) < len(hits):
            blocks[-1]["content"].append({"type": "text", "text": f"[Document truncated: {len(hits) - len(kept)} more sections; "
                                                                     "search within it for specific points.]"})
        return ToolOutcome(blocks, sources=[_ref(h) for h in kept], summary=f"Read {meta['file_name']} ({len(kept)} sections)")

    # ---------- case data ----------
    def _get_case(self, args: dict[str, Any]) -> ToolOutcome:
        case_id = _case_id(args.get("case_id"), required=True)
        summary = case_detail(self.model, self.index, self.principal, case_id)
        if summary is None:
            return ToolOutcome(f"No case {case_id} is available to the signed-in user.", summary=f"Case {case_id}: not available")
        return ToolOutcome(json.dumps(summary, ensure_ascii=False, default=str), summary=f"Looked up case {case_id}")

    def _query(self, args: dict[str, Any]) -> ToolOutcome:
        sql = _text(args.get("sql"), "sql", required=True)
        result = self.model.query(self.principal, sql, max_rows=self.max_rows)
        return ToolOutcome(json.dumps(result, ensure_ascii=False, default=str),
                           summary=f"Queried case data ({result['row_count']} rows{', truncated' if result['truncated'] else ''})")
