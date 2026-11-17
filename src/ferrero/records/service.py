"""Case records: the writable side of the case tracker.

Users register new cases, update cases (status, next steps, owner, and the commercial-sensitivity assessment), add
evidence and supporting documents (photos of infringing products, letters, correspondence, invoices, screenshots, counsel
documents), set follow-ups with deadlines, and record visual trademark comparisons. Every change is checked against the user's role and written together with its audit entry
(who, when, what changed from what to what, and why) in one transaction. After each change the case model's overlay is
refreshed, so the case pages, the KPIs and the assistant all see it at once.

Business dates (deadlines, "today", closing dates) follow the reporting date (FERRERO_DEMO_TODAY), like the rest of
the app. Audit and upload timestamps are the real time, in UTC.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import sqlite3
import threading
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, BinaryIO, Callable

from ..casemodel import CaseModel, Table
from ..config import Settings
from ..security import ESCALATION_GROUPS, Principal
from . import evidence as ev
from . import fields as cf
from . import registration as reg
from . import similarity as sim
from .errors import RecordError
from .mailer import Mailer, compose
from .reminders import follow_up_reminders, fmt_day, tracker_reminders
from .store import RecordStore, format_id, parse_id, utc_now

log = logging.getLogger(__name__)

# Follow-up kinds, with the title and the number of days the form suggests for each.
FOLLOW_UP_KINDS: dict[str, tuple[str, int]] = {
    "Compliance deadline": ("Infringer to remove the infringing products", 30),
    "Response deadline": ("Reply due to the cease-and-desist letter", 14),
    "Court or authority deadline": ("", 30),
    "Business consultation": ("Agree the enforcement approach with the business", 7),
    "Internal follow-up": ("", 7),
}
DECISIONS = {
    "close_case": "Complied – case closed",
    "keep_open": "Done – case stays open",
    "escalate": "Not complied – escalated",
    "cancel": "No longer needed",
    "case_closed": "Closed with the case",
}
RESOLVE_DECISIONS = ("close_case", "keep_open", "escalate", "cancel")
ESCALATION_CHANGES = ("stage", "next_action", "next_action_due")
FOLLOW_UP_EDITABLE = {"title": "Title", "details": "Details", "owner_id": "Owner", "due_date": "Due date",
                      "remind_days": "Reminder (days before)"}

FOLLOW_UP_COLUMNS = (("follow_up_id", "TEXT"), ("case_id", "TEXT"), ("kind", "TEXT"), ("title", "TEXT"),
                     ("details", "TEXT"), ("owner_user_id", "TEXT"), ("owner_name", "TEXT"), ("start_date", "TEXT"),
                     ("period_days", "INTEGER"), ("due_date", "TEXT"), ("remind_days_before", "INTEGER"),
                     ("status", "TEXT"), ("decision", "TEXT"), ("decision_note", "TEXT"), ("resolved_by", "TEXT"),
                     ("resolved_at", "TEXT"), ("created_by", "TEXT"), ("created_at", "TEXT"))
EVIDENCE_COLUMNS = (("evidence_id", "TEXT"), ("case_id", "TEXT"), ("category", "TEXT"), ("title", "TEXT"),
                    ("notes", "TEXT"), ("captured_on", "TEXT"), ("location", "TEXT"), ("file_name", "TEXT"),
                    ("file_type", "TEXT"), ("size_bytes", "INTEGER"), ("sha256", "TEXT"), ("uploaded_by", "TEXT"),
                    ("uploaded_at", "TEXT"), ("status", "TEXT"), ("withdrawn_reason", "TEXT"))
COMPARISON_COLUMNS = (("comparison_id", "TEXT"), ("case_id", "TEXT"), ("mark_id", "TEXT"), ("evidence_id", "TEXT"),
                      ("infringing_sign", "TEXT"), ("visual", "TEXT"), ("phonetic", "TEXT"), ("conceptual", "TEXT"),
                      ("goods", "TEXT"), ("overall", "TEXT"), ("notes", "TEXT"), ("word_similarity", "REAL"),
                      ("sounds_alike", "INTEGER"), ("assessed_by", "TEXT"), ("assessed_at", "TEXT"), ("status", "TEXT"))
# A visual trademark comparison: how alike the registered mark and the sign on the product look, sound and mean, how
# close the goods are, and the resulting likelihood of confusion.
SIMILARITY = ("High", "Medium", "Low", "None")
GOODS = ("Identical", "Similar", "Different")
COMPARISON_FIELDS = {"infringing_sign": "Sign on the product", "evidence_id": "Photo compared",
                     "visual": "Visual similarity", "phonetic": "Phonetic similarity", "conceptual": "Conceptual similarity",
                     "goods": "Goods", "overall": "Likelihood of confusion", "notes": "Notes"}
AUDIT_COLUMNS = (("entry_id", "TEXT"), ("case_id", "TEXT"), ("changed_at", "TEXT"), ("changed_by", "TEXT"),
                 ("role", "TEXT"), ("action", "TEXT"), ("summary", "TEXT"), ("reason", "TEXT"), ("ref_type", "TEXT"))


def _table(name: str, columns: tuple[tuple[str, str], ...], rows: list[dict[str, Any]]) -> Table:
    names = [c for c, _ in columns]
    return Table(name, names, [t for _, t in columns], [tuple(r.get(c) for c in names) for r in rows])


def _emails(path: Path) -> dict[str, str]:
    """User id -> e-mail address, read straight from dim_user (the case model leaves addresses out on purpose)."""
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {r["user_id"]: r["email"] for r in csv.DictReader(f) if r.get("email")}


def _text(value: Any, label: str, limit: int, *, required: bool = False, multiline: bool = False) -> str | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise RecordError(f"{label} is required.")
        return None
    if not isinstance(value, str):
        raise RecordError(f"{label} must be text.")
    value = value.strip() if multiline else " ".join(value.split())
    if len(value) > limit:
        raise RecordError(f"{label} is limited to {limit} characters.")
    return value


def _int(value: Any, label: str, low: int, high: int) -> int | None:
    if value is None or value == "":
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise RecordError(f"{label} must be a whole number.") from None
    if isinstance(value, bool) or not low <= number <= high:
        raise RecordError(f"{label} must be between {low} and {high}.")
    return number


class CaseRecords:
    def __init__(self, settings: Settings, model: CaseModel, *, today: Callable[[], date] | None = None,
                 mailer: Mailer | Any | None = None):
        self.settings, self.model = settings, model
        self.today = today or (lambda: settings.demo_today)
        self.store = RecordStore(settings.records_dir / "records.sqlite")
        self.blobs = ev.BlobStore(settings.records_dir / "evidence")
        self.mailer = mailer
        self._emails = _emails(settings.csv_dir / "dim_user.csv")
        self._refresh_lock = threading.Lock()
        self._reminder_lock = threading.Lock()
        self.choices = reg.Choices.from_model(model)  # from the pack, before anything is laid over it
        self.refresh()

    # ---------- helpers ----------
    def _name(self, user_id: str | None) -> str:
        u = self.model.user(user_id) if user_id else None
        return u["full_name"] if u else (user_id or "")

    def _visible(self, principal: Principal, case_id: str) -> dict[str, Any]:
        case = self.model.visible_case(principal, (case_id or "").strip().upper())
        if case is None:
            raise RecordError(f"Case {(case_id or '').upper()} is not available to this user.", 404)
        return case

    @staticmethod
    def _need_edit(principal: Principal) -> None:
        if not principal.can_edit:
            raise RecordError("Your role can see cases but not change them.", 403, "read_only")

    @staticmethod
    def _need_documents(principal: Principal) -> None:
        if not principal.sees_documents:
            raise RecordError("Evidence and documents are not available for your role.", 403, "no_documents")

    def can_own(self, user_id: str, case: dict[str, Any]) -> bool:
        """Owners of a case or follow-up: users who can change cases and can see this one."""
        p = self.model.principal(user_id)
        return bool(p and p.can_edit and p.sees_group(case["access_group"]))

    def _escalate_to(self, case: dict[str, Any]) -> list[str]:
        return [u["user_id"] for u in self.model.users()
                if u["entra_group"] in ESCALATION_GROUPS and case["access_group"] in u["case_groups"]]

    def _audit(self, conn: sqlite3.Connection, principal: Principal, case_id: str, action: str, summary: str,
               changes: list[dict[str, Any]] | None = None, reason: str | None = None,
               ref_type: str | None = None, ref_id: str | None = None) -> None:
        self.store.append_audit(conn, case_id=case_id, actor_id=principal.user_id, actor_name=principal.full_name,
                                actor_role=principal.entra_group, action=action, summary=summary,
                                changes=changes or [], reason=reason or None, ref_type=ref_type, ref_id=ref_id)

    # ---------- the overlay on the case model ----------
    def refresh(self) -> None:
        """Re-read the records and lay them over the pack's tables (cheap: hundreds of rows)."""
        with self._refresh_lock:
            with self.store.read() as conn:
                conn.execute("BEGIN")
                fields: dict[str, dict[str, Any]] = defaultdict(dict)
                for r in conn.execute("SELECT case_id, field, value FROM case_fields"):
                    fields[r["case_id"]][r["field"]] = json.loads(r["value"])
                follow_ups = [self._follow_up_row(r) for r in conn.execute("SELECT * FROM follow_ups ORDER BY seq")]
                evidence = [self._evidence_row(r) for r in conn.execute("SELECT * FROM evidence ORDER BY seq")]
                audit = [{"entry_id": format_id("audit", r["seq"]), "case_id": r["case_id"], "changed_at": r["at"],
                          "changed_by": r["actor_name"], "role": r["actor_role"], "action": r["action"],
                          "summary": r["summary"], "reason": r["reason"], "ref_type": r["ref_type"]}
                         for r in conn.execute("SELECT * FROM audit_log ORDER BY seq")]
                comparisons = [self._comparison_row(r) for r in conn.execute("SELECT * FROM mark_comparisons ORDER BY seq")]
                new_cases = [json.loads(r["data"]) for r in conn.execute("SELECT data FROM registered_cases ORDER BY seq")]
                new_infringers = [json.loads(r["data"]) for r in conn.execute("SELECT data FROM registered_infringers ORDER BY seq")]
                conn.execute("COMMIT")
            self.model.apply_overlay(dict(fields), {
                "case_follow_up": _table("case_follow_up", FOLLOW_UP_COLUMNS, follow_ups),
                "case_evidence": _table("case_evidence", EVIDENCE_COLUMNS, evidence),
                "case_audit": _table("case_audit", AUDIT_COLUMNS, audit),
                "case_mark_comparison": _table("case_mark_comparison", COMPARISON_COLUMNS, comparisons),
            }, new_cases=new_cases, new_infringers=new_infringers)

    def _comparison_row(self, r: sqlite3.Row) -> dict[str, Any]:
        return {"comparison_id": format_id("comparison", r["seq"]), "case_id": r["case_id"], "mark_id": r["mark_id"],
                "evidence_id": r["evidence_id"], "infringing_sign": r["infringing_sign"], "visual": r["visual"],
                "phonetic": r["phonetic"], "conceptual": r["conceptual"], "goods": r["goods"], "overall": r["overall"],
                "notes": r["notes"], "word_similarity": r["word_similarity"], "sounds_alike": r["sounds_alike"],
                "assessed_by": self._name(r["assessed_by"]), "assessed_at": r["assessed_at"], "status": r["status"]}

    def _follow_up_row(self, r: sqlite3.Row) -> dict[str, Any]:
        return {"follow_up_id": format_id("follow_up", r["seq"]), "case_id": r["case_id"], "kind": r["kind"],
                "title": r["title"], "details": r["details"], "owner_user_id": r["owner_id"],
                "owner_name": self._name(r["owner_id"]), "start_date": r["start_date"], "period_days": r["period_days"],
                "due_date": r["due_date"], "remind_days_before": r["remind_days"], "status": r["status"],
                "decision": DECISIONS.get(r["decision"]) if r["decision"] else None, "decision_note": r["decision_note"],
                "resolved_by": self._name(r["resolved_by"]) if r["resolved_by"] else None,
                "resolved_at": r["resolved_at"], "created_by": self._name(r["created_by"]), "created_at": r["created_at"]}

    def _evidence_row(self, r: sqlite3.Row) -> dict[str, Any]:
        return {"evidence_id": format_id("evidence", r["seq"]), "case_id": r["case_id"], "category": r["category"],
                "title": r["title"], "notes": r["notes"], "captured_on": r["captured_on"], "location": r["location"],
                "file_name": r["file_name"], "file_type": ev.kind_of(r["content_type"]).label,
                "size_bytes": r["size_bytes"], "sha256": r["sha256"], "uploaded_by": self._name(r["uploaded_by"]),
                "uploaded_at": r["uploaded_at"], "status": r["status"], "withdrawn_reason": r["withdrawn_reason"]}

    # ---------- case fields ----------
    def _plan(self, case: dict[str, Any], changes: dict[str, Any], override_reason: str | None) -> cf.Plan:
        plan = cf.plan_update(case, changes, today=self.today(), can_own=lambda uid: self.can_own(uid, case))
        if cf.enforcement_blocked(plan) and not (override_reason or "").strip():
            raise RecordError(
                f"{case['case_id']} needs business consultation before enforcement, and it has not been cleared "
                f"(consultation: {plan.new['consultation_status']}). Record the business sign-off first, or give the "
                "reason for going ahead without it.", 409, "consultation_required")
        return plan

    def update_case(self, principal: Principal, case_id: str, changes: dict[str, Any], reason: str | None = None,
                    override_reason: str | None = None) -> list[dict[str, Any]]:
        """Change case fields; returns the changes made (empty when nothing changed)."""
        self._need_edit(principal)
        case = self._visible(principal, case_id)
        reason = _text(reason, "The reason", 2000, multiline=True)
        override_reason = _text(override_reason, "The reason for going ahead", 2000, multiline=True)
        plan = self._plan(case, changes, override_reason)
        if not plan.diffs:
            return []
        with self.store.transaction() as conn:
            self._write_case(conn, principal, case, plan, reason, override_reason)
        self.refresh()
        self.run_reminders()  # a deadline moved to today or earlier is due now
        return plan.diffs

    def _write_case(self, conn: sqlite3.Connection, principal: Principal, case: dict[str, Any], plan: cf.Plan,
                    reason: str | None, override_reason: str | None = None) -> None:
        cid, now = case["case_id"], utc_now()
        if override_reason and cf.enforcement_blocked(plan):
            self._audit(conn, principal, cid, "business.override",
                        f"Enforcement started without business clearance (consultation: {plan.new['consultation_status']})",
                        [{"field": "stage", "label": "Stage", "old": case.get("stage"), "new": plan.new["stage"]}],
                        override_reason)
        for d in plan.diffs:
            conn.execute(
                "INSERT INTO case_fields (case_id, field, value, updated_at, updated_by) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(case_id, field) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at, "
                "updated_by = excluded.updated_by", (cid, d["field"], json.dumps(d["new"]), now, principal.user_id))
        action = ("case.closed" if plan.closing else "case.reopened" if plan.reopening
                  else "business.updated" if plan.business_only else "case.updated")
        self._audit(conn, principal, cid, action, cf.describe(plan.diffs, self._name), plan.diffs, reason)
        changed = {d["field"] for d in plan.diffs}
        if "lead_counsel_id" in changed and plan.new["lead_counsel_id"] != principal.user_id and not plan.closing:
            self._notify_case_owner(conn, principal, cid, case["title"], plan.new["lead_counsel_id"],
                                    "made you the owner of", plan.new.get("next_action_due"))
        for field, kind in (("next_action_due", "next_action"), ("next_hearing_date", "hearing")):
            if field in changed and not plan.closing:  # reminders about the old date are no longer news
                conn.execute("UPDATE notifications SET read_at = ? WHERE case_id = ? AND kind = ? AND read_at IS NULL "
                             "AND COALESCE(due_date, '') <> COALESCE(?, '')", (now, cid, kind, plan.new[field]))
        if plan.closing:  # nothing left to follow up on a closed case; its reminders are no longer news
            conn.execute("UPDATE notifications SET read_at = ? WHERE case_id = ? AND read_at IS NULL", (now, cid))
            for row in conn.execute("SELECT seq, title FROM follow_ups WHERE case_id = ? AND status = 'Open'", (cid,)).fetchall():
                fid = format_id("follow_up", row["seq"])
                conn.execute("UPDATE follow_ups SET status = 'Done', decision = 'case_closed', resolved_by = ?, "
                             "resolved_at = ?, updated_at = ? WHERE seq = ?", (principal.user_id, now, now, row["seq"]))
                self._audit(conn, principal, cid, "follow_up.resolved", f"Follow-up {fid} closed with the case: {row['title']}",
                            [{"field": "status", "label": "Status", "old": "Open", "new": "Done"}], None, "follow_up", fid)

    # ---------- evidence ----------
    def _evidence_out(self, r: sqlite3.Row) -> dict[str, Any]:
        kind = ev.kind_of(r["content_type"])
        return {"evidence_id": format_id("evidence", r["seq"]), "case_id": r["case_id"], "category": r["category"],
                "title": r["title"], "notes": r["notes"], "captured_on": r["captured_on"], "location": r["location"],
                "file_name": r["file_name"], "content_type": r["content_type"], "file_label": kind.label,
                "image": kind.image, "size_bytes": r["size_bytes"], "sha256": r["sha256"],
                "uploaded_by_id": r["uploaded_by"], "uploaded_by": self._name(r["uploaded_by"]), "uploaded_at": r["uploaded_at"],
                "status": r["status"], "withdrawn_by": self._name(r["withdrawn_by"]) if r["withdrawn_by"] else None,
                "withdrawn_at": r["withdrawn_at"], "withdrawn_reason": r["withdrawn_reason"]}

    def _evidence(self, principal: Principal, evidence_id: str) -> tuple[sqlite3.Row, dict[str, Any]]:
        self._need_documents(principal)
        seq = parse_id("evidence", evidence_id)
        with self.store.read() as conn:
            row = conn.execute("SELECT * FROM evidence WHERE seq = ?", (seq,)).fetchone()
        if row is None or self.model.visible_case(principal, row["case_id"]) is None:
            raise RecordError(f"Evidence {evidence_id.upper()} is not available to this user.", 404)
        return row, self.model.visible_case(principal, row["case_id"])

    def list_evidence(self, principal: Principal, case_id: str) -> list[dict[str, Any]]:
        self._need_documents(principal)
        case = self._visible(principal, case_id)
        with self.store.read() as conn:
            rows = conn.execute("SELECT * FROM evidence WHERE case_id = ? ORDER BY seq DESC", (case["case_id"],)).fetchall()
        return [self._evidence_out(r) for r in rows]

    def check_can_add_evidence(self, principal: Principal, case_id: str) -> dict[str, Any]:
        """Refuse an upload before its body is read."""
        self._need_edit(principal)
        self._need_documents(principal)
        return self._visible(principal, case_id)

    def add_evidence(self, principal: Principal, case_id: str, stream: BinaryIO, file_name: str,
                     details: dict[str, Any]) -> dict[str, Any]:
        """Store one file against a case: type and size checked, fingerprinted, never overwritten."""
        case = self.check_can_add_evidence(principal, case_id)
        name = ev.clean_file_name(file_name)
        meta = ev.clean_meta(details, self.today())
        meta["title"] = meta["title"] or Path(name).stem[:200]
        stored = self.blobs.ingest(stream, name, self.settings.evidence_max_mb)
        cid = case["case_id"]
        with self.store.transaction() as conn:
            dup = conn.execute("SELECT seq FROM evidence WHERE case_id = ? AND sha256 = ? AND status = 'Active'",
                               (cid, stored.sha256)).fetchone()
            if dup:
                raise RecordError(f"This file is already on file for {cid} as {format_id('evidence', dup['seq'])}.",
                                  409, "duplicate")
            seq = conn.execute(
                "INSERT INTO evidence (case_id, category, title, notes, captured_on, location, file_name, content_type, "
                "size_bytes, sha256, uploaded_by, uploaded_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (cid, meta["category"], meta["title"], meta["notes"], meta["captured_on"], meta["location"], name,
                 stored.kind.content_type, stored.size, stored.sha256, principal.user_id, utc_now())).lastrowid
            eid = format_id("evidence", seq)
            facts = [("category", "Category", meta["category"]), ("title", "Title", meta["title"]),
                     ("file_name", "File", name), ("size_bytes", "Size", stored.size),
                     ("sha256", "SHA-256 fingerprint", stored.sha256), ("captured_on", "Captured or dated", meta["captured_on"]),
                     ("location", "Where found", meta["location"]), ("notes", "Notes", meta["notes"])]
            self._audit(conn, principal, cid, "evidence.added", f"Added {meta['category'].lower()} {eid}: {meta['title']}",
                        [{"field": f, "label": label, "old": None, "new": v} for f, label, v in facts if v is not None],
                        None, "evidence", eid)
            row = conn.execute("SELECT * FROM evidence WHERE seq = ?", (seq,)).fetchone()
        self.refresh()
        return self._evidence_out(row)

    def update_evidence(self, principal: Principal, evidence_id: str, changes: dict[str, Any],
                        reason: str | None = None) -> dict[str, Any]:
        self._need_edit(principal)
        row, case = self._evidence(principal, evidence_id)
        if row["status"] != "Active":
            raise RecordError("Withdrawn evidence can't be changed.", 409)
        if not isinstance(changes, dict) or not changes:
            raise RecordError("Nothing to change.")
        meta = ev.clean_meta(changes, self.today(), partial=True)
        diffs = [{"field": k, "label": ev.EDITABLE[k], "old": row[k], "new": v} for k, v in meta.items() if row[k] != v]
        if diffs:
            eid = format_id("evidence", row["seq"])
            with self.store.transaction() as conn:
                sets = ", ".join(d["field"] + " = ?" for d in diffs)  # names from ev.EDITABLE only
                conn.execute(f"UPDATE evidence SET {sets} WHERE seq = ?", [d["new"] for d in diffs] + [row["seq"]])
                self._audit(conn, principal, case["case_id"], "evidence.updated",
                            f"Evidence {eid} details changed: {cf.describe(diffs)}", diffs,
                            _text(reason, "The reason", 2000, multiline=True), "evidence", eid)
            self.refresh()
        return self.get_evidence(principal, evidence_id)

    def withdraw_evidence(self, principal: Principal, evidence_id: str, reason: str | None) -> dict[str, Any]:
        """Take an item out of the case's evidence. The file and its record are kept, with who withdrew it and why."""
        self._need_edit(principal)
        row, case = self._evidence(principal, evidence_id)
        reason = _text(reason, "The reason for withdrawing it", 2000, required=True, multiline=True)
        if row["status"] != "Active":
            raise RecordError("This evidence has already been withdrawn.", 409)
        eid, now = format_id("evidence", row["seq"]), utc_now()
        with self.store.transaction() as conn:
            conn.execute("UPDATE evidence SET status = 'Withdrawn', withdrawn_by = ?, withdrawn_at = ?, withdrawn_reason = ? "
                         "WHERE seq = ?", (principal.user_id, now, reason, row["seq"]))
            self._audit(conn, principal, case["case_id"], "evidence.withdrawn", f"Withdrew evidence {eid}: {row['title']}",
                        [{"field": "status", "label": "Status", "old": "Active", "new": "Withdrawn"}], reason, "evidence", eid)
        self.refresh()
        return self.get_evidence(principal, evidence_id)

    def get_evidence(self, principal: Principal, evidence_id: str) -> dict[str, Any]:
        row, _ = self._evidence(principal, evidence_id)
        return self._evidence_out(row)

    def evidence_file(self, principal: Principal, evidence_id: str) -> tuple[Path, ev.FileKind, str]:
        row, _ = self._evidence(principal, evidence_id)
        path = self.blobs.path(row["sha256"])
        if not path.is_file():
            raise RecordError("The file for this evidence is missing from the store.", 410)
        return path, ev.kind_of(row["content_type"]), row["file_name"]

    def verify_evidence(self, principal: Principal, evidence_id: str) -> dict[str, Any]:
        row, _ = self._evidence(principal, evidence_id)
        return {"evidence_id": format_id("evidence", row["seq"]), "sha256": row["sha256"],
                "ok": self.blobs.verify(row["sha256"]), "checked_at": utc_now()}

    # ---------- follow-ups ----------
    def _follow_up_out(self, r: sqlite3.Row, case: dict[str, Any] | None = None) -> dict[str, Any]:
        today = self.today()
        due = date.fromisoformat(r["due_date"])
        out = {"follow_up_id": format_id("follow_up", r["seq"]), "case_id": r["case_id"], "kind": r["kind"],
               "title": r["title"], "details": r["details"], "owner_id": r["owner_id"], "owner_name": self._name(r["owner_id"]),
               "start_date": r["start_date"], "period_days": r["period_days"], "due_date": r["due_date"],
               "remind_days": r["remind_days"], "status": r["status"], "decision": r["decision"],
               "decision_label": DECISIONS.get(r["decision"]) if r["decision"] else None, "decision_note": r["decision_note"],
               "resolved_by": self._name(r["resolved_by"]) if r["resolved_by"] else None, "resolved_at": r["resolved_at"],
               "created_by_id": r["created_by"], "created_by": self._name(r["created_by"]), "created_at": r["created_at"],
               "days_left": (due - today).days}
        if case is not None:
            out["case_title"] = case["title"]
        return out

    def _follow_up(self, principal: Principal, follow_up_id: str) -> tuple[sqlite3.Row, dict[str, Any]]:
        seq = parse_id("follow_up", follow_up_id)
        with self.store.read() as conn:
            row = conn.execute("SELECT * FROM follow_ups WHERE seq = ?", (seq,)).fetchone()
        case = self.model.visible_case(principal, row["case_id"]) if row else None
        if row is None or case is None:
            raise RecordError(f"Follow-up {follow_up_id.upper()} is not available to this user.", 404)
        return row, case

    def list_follow_ups(self, principal: Principal, case_id: str) -> list[dict[str, Any]]:
        case = self._visible(principal, case_id)
        with self.store.read() as conn:
            rows = conn.execute("SELECT * FROM follow_ups WHERE case_id = ? ORDER BY status <> 'Open', due_date, seq",
                                (case["case_id"],)).fetchall()
        return [self._follow_up_out(r) for r in rows]

    def get_follow_up(self, principal: Principal, follow_up_id: str) -> dict[str, Any]:
        row, case = self._follow_up(principal, follow_up_id)
        return self._follow_up_out(row, case)

    def create_follow_up(self, principal: Principal, case_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """A deadline on the case, for example 'store given 30 days to remove the products': start + days, or a date."""
        self._need_edit(principal)
        case = self._visible(principal, case_id)
        today = self.today()
        kind = data.get("kind")
        if kind not in FOLLOW_UP_KINDS:
            raise RecordError(f"Choose the kind of follow-up: {', '.join(FOLLOW_UP_KINDS)}.")
        title = _text(data.get("title"), "The title", 200, required=True)
        details = _text(data.get("details"), "Details", 2000, multiline=True)
        owner = _text(data.get("owner_id"), "The owner", 10) or case["lead_counsel_id"]
        if not self.can_own(owner, case):
            raise RecordError("The owner must be a member of the legal team who can see this case.")
        start = date.fromisoformat(ev.parse_day(data.get("start_date"), "The start date") or today.isoformat())
        period = _int(data.get("period_days"), "The number of days allowed", 1, 3650)
        due_text = ev.parse_day(data.get("due_date"), "The due date")
        if due_text is None and period is None:
            raise RecordError("Give the number of days allowed or the due date.")
        due = date.fromisoformat(due_text) if due_text else start + timedelta(days=period or 0)
        if due < start:
            raise RecordError("The due date can't be before the start date.")
        period = (due - start).days
        remind = _int(data.get("remind_days"), "The reminder", 0, 90)
        remind = self.settings.reminder_lead_days if remind is None else remind
        now = utc_now()
        with self.store.transaction() as conn:
            seq = conn.execute(
                "INSERT INTO follow_ups (case_id, kind, title, details, owner_id, start_date, period_days, due_date, "
                "remind_days, created_by, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (case["case_id"], kind, title, details, owner, start.isoformat(), period, due.isoformat(), remind,
                 principal.user_id, now, now)).lastrowid
            fid = format_id("follow_up", seq)
            facts = [("kind", "Kind", kind), ("title", "Title", title), ("owner_id", "Owner", owner),
                     ("start_date", "Starts", start.isoformat()), ("period_days", "Days allowed", period),
                     ("due_date", "Due date", due.isoformat()), ("remind_days", "Reminder (days before)", remind),
                     ("details", "Details", details)]
            self._audit(conn, principal, case["case_id"], "follow_up.created",
                        f"Follow-up {fid} set: {title} – due {fmt_day(due)} ({period} days)",
                        [{"field": f, "label": label, "old": None, "new": v} for f, label, v in facts if v is not None],
                        None, "follow_up", fid)
            if owner != principal.user_id:
                self._notify_assigned(conn, principal, case, fid, title, owner, due)
            row = conn.execute("SELECT * FROM follow_ups WHERE seq = ?", (seq,)).fetchone()
        self.refresh()
        self.run_reminders()  # a deadline already reached is reported now, not at the next check
        return self._follow_up_out(row, case)

    def update_follow_up(self, principal: Principal, follow_up_id: str, changes: dict[str, Any],
                         reason: str | None = None) -> dict[str, Any]:
        """Edit an open follow-up: reassign it, or extend or bring forward its deadline (with the reason)."""
        self._need_edit(principal)
        row, case = self._follow_up(principal, follow_up_id)
        if row["status"] != "Open":
            raise RecordError("This follow-up is already resolved.", 409)
        if not isinstance(changes, dict) or not changes:
            raise RecordError("Nothing to change.")
        unknown = sorted(set(changes) - set(FOLLOW_UP_EDITABLE))
        if unknown:
            raise RecordError(f"These follow-up details can't be changed: {', '.join(unknown)}.")
        new: dict[str, Any] = {}
        if "title" in changes:
            new["title"] = _text(changes["title"], "The title", 200, required=True)
        if "details" in changes:
            new["details"] = _text(changes["details"], "Details", 2000, multiline=True)
        if "owner_id" in changes:
            new["owner_id"] = _text(changes["owner_id"], "The owner", 10, required=True)
            if not self.can_own(new["owner_id"], case):
                raise RecordError("The owner must be a member of the legal team who can see this case.")
        if "due_date" in changes:
            new["due_date"] = ev.parse_day(changes["due_date"], "The due date")
            if new["due_date"] is None:
                raise RecordError("The due date can't be empty.")
            if new["due_date"] < row["start_date"]:
                raise RecordError("The due date can't be before the start date.")
        if "remind_days" in changes:
            new["remind_days"] = _int(changes["remind_days"], "The reminder", 0, 90) or 0
        diffs = [{"field": k, "label": FOLLOW_UP_EDITABLE[k], "old": row[k], "new": v} for k, v in new.items() if row[k] != v]
        if not diffs:
            return self._follow_up_out(row, case)
        reason = _text(reason, "The reason", 2000, multiline=True)
        moved = next((d for d in diffs if d["field"] == "due_date"), None)
        if moved and not reason:
            raise RecordError("Say why the deadline changes.")
        fid, now = format_id("follow_up", row["seq"]), utc_now()
        sets = {d["field"]: d["new"] for d in diffs}
        if moved:
            sets["period_days"] = (date.fromisoformat(moved["new"]) - date.fromisoformat(row["start_date"])).days
        action = "follow_up.extended" if moved and moved["new"] > moved["old"] else "follow_up.updated"
        assignments = ", ".join(k + " = ?" for k in sets)  # names from FOLLOW_UP_EDITABLE (and period_days) only
        with self.store.transaction() as conn:
            conn.execute(f"UPDATE follow_ups SET {assignments}, updated_at = ? WHERE seq = ?", [*sets.values(), now, row["seq"]])
            if moved:  # reminders about the old deadline are no longer news
                conn.execute("UPDATE notifications SET read_at = ? WHERE ref_id = ? AND kind = 'follow_up' AND read_at IS NULL "
                             "AND due_date <> ?", (now, fid, moved["new"]))
            summary = (f"Follow-up {fid} deadline moved: {fmt_day(moved['old'])} → {fmt_day(moved['new'])}" if moved
                       else f"Follow-up {fid} changed: {cf.describe(diffs, self._name)}")
            self._audit(conn, principal, case["case_id"], action, summary, diffs, reason, "follow_up", fid)
            owner = sets.get("owner_id")
            if owner and owner != principal.user_id:
                self._notify_assigned(conn, principal, case, fid, sets.get("title", row["title"]), owner,
                                      date.fromisoformat(sets.get("due_date", row["due_date"])))
        self.refresh()
        self.run_reminders()
        return self.get_follow_up(principal, follow_up_id)

    def resolve_follow_up(self, principal: Principal, follow_up_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Record the follow-up decision once the deadline is reached: close the case, keep it open, escalate or cancel."""
        self._need_edit(principal)
        row, case = self._follow_up(principal, follow_up_id)
        decision = data.get("decision")
        if decision not in RESOLVE_DECISIONS:
            raise RecordError("Choose the decision: close the case, keep it open, escalate or cancel.")
        if row["status"] != "Open":
            raise RecordError("This follow-up is already resolved.", 409)
        note = _text(data.get("note"), "The note", 2000, multiline=True)
        if decision in ("cancel", "escalate") and not note:
            raise RecordError("Add a note saying why." if decision == "cancel" else "Add a note on what was found.")
        plan = None
        if decision == "close_case":
            if case["status"] == "Closed":
                raise RecordError("The case is already closed: record the follow-up as done instead.")
            plan = self._plan(case, {"status": "Closed", "outcome": data.get("outcome"),
                                     "closed_date": data.get("closed_date")}, None)
        elif decision == "escalate":
            raw = data.get("case_changes") or {}
            if not isinstance(raw, dict):
                raise RecordError("The case changes must be a set of fields.")
            wanted = {k: v for k, v in raw.items() if k in ESCALATION_CHANGES and v not in (None, "")}
            if wanted:
                plan = self._plan(case, wanted, data.get("override_reason"))
        fid, now = format_id("follow_up", row["seq"]), utc_now()
        status = "Cancelled" if decision == "cancel" else "Done"
        with self.store.transaction() as conn:
            changed = conn.execute(
                "UPDATE follow_ups SET status = ?, decision = ?, decision_note = ?, resolved_by = ?, resolved_at = ?, "
                "updated_at = ? WHERE seq = ? AND status = 'Open'",
                (status, decision, note, principal.user_id, now, now, row["seq"])).rowcount
            if not changed:
                raise RecordError("This follow-up is already resolved.", 409)
            # the reminders asked for this decision: settled for everyone they went to
            conn.execute("UPDATE notifications SET read_at = ? WHERE ref_id = ? AND read_at IS NULL", (now, fid))
            self._audit(conn, principal, case["case_id"], "follow_up.resolved",
                        f"Follow-up {fid} resolved – {DECISIONS[decision]}: {row['title']}",
                        [{"field": "status", "label": "Status", "old": "Open", "new": status},
                         {"field": "decision", "label": "Decision", "old": None, "new": DECISIONS[decision]}],
                        note, "follow_up", fid)
            if plan and plan.diffs:
                self._write_case(conn, principal, case, plan, note or f"Follow-up {fid}: {DECISIONS[decision]}",
                                 _text(data.get("override_reason"), "The reason for going ahead", 2000, multiline=True))
        self.refresh()
        self.run_reminders()
        return self.get_follow_up(principal, follow_up_id)

    def _notify_case_owner(self, conn: sqlite3.Connection, principal: Principal, case_id: str, title: str, owner: str,
                           verb: str, due: str | None) -> None:
        now = utc_now()
        conn.execute(
            "INSERT OR IGNORE INTO notifications (user_id, case_id, kind, stage, title, body, link, ref_id, due_date, "
            "dedupe_key, created_at) VALUES (?, ?, 'assigned', 'assigned', ?, ?, ?, ?, ?, ?, ?)",
            (owner, case_id, "Case assigned to you", f"{principal.full_name} {verb} {case_id}: {title}.",
             f"/cases/{case_id}", case_id, due, f"case-as:{case_id}:{owner}:{now}", now))

    def _notify_assigned(self, conn: sqlite3.Connection, principal: Principal, case: dict[str, Any], fid: str,
                         title: str, owner: str, due: date) -> None:
        conn.execute(
            "INSERT OR IGNORE INTO notifications (user_id, case_id, kind, stage, title, body, link, ref_id, due_date, "
            "dedupe_key, created_at) VALUES (?, ?, 'assigned', 'assigned', ?, ?, ?, ?, ?, ?, ?)",
            (owner, case["case_id"], "Follow-up assigned to you",
             f"{principal.full_name} assigned you “{title}” on {case['case_id']}: due {fmt_day(due)}.",
             f"/cases/{case['case_id']}?tab=follow-ups", fid, due.isoformat(), f"as:{fid}:{owner}:{utc_now()}", utc_now()))

    def worklist(self, principal: Principal) -> dict[str, Any]:
        """Every open deadline the user can see: follow-ups, next actions and hearings, soonest first."""
        today = self.today()
        cases = {c["case_id"]: c for c in self.model.visible_cases(principal)}
        items: list[dict[str, Any]] = []
        with self.store.read() as conn:
            rows = conn.execute("SELECT * FROM follow_ups ORDER BY due_date, seq").fetchall()
        resolved = []
        for r in rows:
            case = cases.get(r["case_id"])
            if case is None:
                continue
            fu = self._follow_up_out(r, case)
            if r["status"] == "Open":
                items.append({**fu, "type": "follow_up", "id": fu["follow_up_id"], "mine": r["owner_id"] == principal.user_id,
                              "link": f"/cases/{r['case_id']}?tab=follow-ups"})
            else:
                resolved.append({**fu, "type": "follow_up", "id": fu["follow_up_id"],
                                 "mine": r["owner_id"] == principal.user_id, "link": f"/cases/{r['case_id']}?tab=follow-ups"})
        for c in cases.values():
            if c["status"] != "Open":
                continue
            base = {"case_id": c["case_id"], "case_title": c["title"], "owner_id": c["lead_counsel_id"],
                    "owner_name": c["lead_counsel"], "mine": c["lead_counsel_id"] == principal.user_id,
                    "status": "Open", "link": f"/cases/{c['case_id']}"}
            if c.get("next_action_due"):
                items.append({**base, "type": "next_action", "id": f"{c['case_id']}:next-action", "kind": "Next action",
                              "title": c.get("next_action") or "Next action", "due_date": c["next_action_due"],
                              "days_left": (date.fromisoformat(c["next_action_due"]) - today).days})
            if c.get("next_hearing_date") and c["next_hearing_date"] >= today.isoformat():
                items.append({**base, "type": "hearing", "id": f"{c['case_id']}:hearing", "kind": "Hearing",
                              "title": f"Hearing · {c['court_name']}", "due_date": c["next_hearing_date"],
                              "days_left": (date.fromisoformat(c["next_hearing_date"]) - today).days})
        items.sort(key=lambda i: (i["due_date"], i["case_id"], i["type"]))
        resolved.sort(key=lambda i: i["resolved_at"] or "", reverse=True)
        return {"as_of": today.isoformat(), "lead_days": self.settings.reminder_lead_days,
                "escalate_days": self.settings.escalate_days, "items": items, "resolved": resolved[:20]}

    # ---------- notifications ----------
    def notifications(self, principal: Principal, limit: int = 30) -> dict[str, Any]:
        with self.store.read() as conn:
            rows = conn.execute("SELECT * FROM notifications WHERE user_id = ? ORDER BY seq DESC", (principal.user_id,)).fetchall()
        mine = [r for r in rows if self.model.visible_case(principal, r["case_id"]) is not None]
        today = self.today()
        items = [{"id": r["seq"], "case_id": r["case_id"], "kind": r["kind"], "stage": r["stage"], "title": r["title"],
                  "body": r["body"], "link": r["link"], "ref_id": r["ref_id"], "due_date": r["due_date"],
                  "days_left": (date.fromisoformat(r["due_date"]) - today).days if r["due_date"] else None,
                  "created_at": r["created_at"], "read": r["read_at"] is not None} for r in mine[:limit]]
        return {"unread": sum(1 for r in mine if r["read_at"] is None), "items": items, "email": self.mailer is not None}

    def mark_read(self, principal: Principal, ids: list[int] | None = None) -> int:
        with self.store.transaction() as conn:
            sql, params = "UPDATE notifications SET read_at = ? WHERE user_id = ? AND read_at IS NULL", [utc_now(), principal.user_id]
            if ids is not None:
                if not ids:
                    return 0
                sql += f" AND seq IN ({', '.join('?' * len(ids))})"
                params += [int(i) for i in ids]
            return conn.execute(sql, params).rowcount

    def run_reminders(self, today: date | None = None) -> int:
        """Create the notifications due today (each at most once); returns how many were created."""
        today = today or self.today()
        with self._reminder_lock:
            cases = {c["case_id"]: c for c in self.model.cases()}
            with self.store.read() as conn:
                follow_ups = [{**dict(r), "id": format_id("follow_up", r["seq"])}
                              for r in conn.execute("SELECT * FROM follow_ups WHERE status = 'Open'")]
            due = (follow_up_reminders(follow_ups, cases, today, self.settings.escalate_days, self._escalate_to)
                   + tracker_reminders(cases.values(), today, self.settings.reminder_lead_days,
                                       self.settings.escalate_days, self._escalate_to))
            created, now = 0, utc_now()
            with self.store.transaction() as conn:
                for rem in due:
                    access = cases[rem.case_id]["access_group"]
                    for uid in rem.recipients:
                        p = self.model.principal(uid)
                        if p is None or not p.sees_group(access):
                            continue  # never tell someone about a case they can't open
                        created += conn.execute(
                            "INSERT OR IGNORE INTO notifications (user_id, case_id, kind, stage, title, body, link, ref_id, "
                            "due_date, dedupe_key, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (uid, rem.case_id, rem.kind, rem.stage, rem.title, rem.body, rem.link, rem.ref_id,
                             rem.due_date, rem.key, now)).rowcount
        if created:
            log.info("Reminders: %d new notifications for %s", created, today.isoformat())
        return created

    def deliver_email(self) -> int:
        """E-mail unread notifications from the last week that have not been sent yet; one message per recipient."""
        if self.mailer is None:
            return 0
        since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(timespec="seconds")
        with self.store.read() as conn:
            rows = conn.execute("SELECT * FROM notifications WHERE emailed_at IS NULL AND read_at IS NULL "
                                "AND email_attempts < 3 AND created_at >= ? ORDER BY seq", (since,)).fetchall()
        by_user: dict[str, list[sqlite3.Row]] = defaultdict(list)
        for r in rows:
            by_user[r["user_id"]].append(r)
        settings, sent = getattr(self.mailer, "settings", None), 0
        redirect = getattr(settings, "redirect_to", None)
        for uid, items in by_user.items():
            to = redirect or self._emails.get(uid)
            if not to:
                continue
            subject, body = compose(self._name(uid), [dict(r) for r in items], getattr(settings, "public_url", None))
            seqs = [r["seq"] for r in items]
            marks = ", ".join("?" * len(seqs))
            try:
                self.mailer.send(to, subject, body)
            except Exception as e:  # a mail server problem never breaks reminders; retried at the next check
                log.warning("Reminder e-mail to %s failed: %s", uid, e)
                with self.store.transaction() as conn:
                    conn.execute(f"UPDATE notifications SET email_attempts = email_attempts + 1 WHERE seq IN ({marks})", seqs)
                continue
            with self.store.transaction() as conn:
                conn.execute(f"UPDATE notifications SET emailed_at = ? WHERE seq IN ({marks})", [utc_now(), *seqs])
            sent += len(items)
        return sent

    # ---------- registering a case ----------
    def register_options(self, principal: Principal) -> dict[str, Any]:
        self._need_edit(principal)
        return reg.options_for(principal, self.model, self.choices)

    def register_case(self, principal: Principal, data: dict[str, Any]) -> dict[str, Any]:
        """Record a new case (from an intake report, a mailbox complaint, a vendor alert ...); returns its number."""
        self._need_edit(principal)
        draft = reg.validate(data, principal, self.model, self.choices, self.today(),
                             lambda uid, group: self.can_own(uid, {"access_group": group}))
        now = utc_now()
        with self.store.transaction() as conn:  # holds the write lock: two registrations can't take the same number
            taken = {c["case_id"] for c in self.model.cases()}
            taken |= {r["case_id"] for r in conn.execute("SELECT case_id FROM registered_cases")}
            case_id = reg.next_case_id(taken, draft.fields["opened_date"])
            infringer = draft.infringer
            if draft.new_infringer is not None:
                known = {i["infringer_id"] for i in self.model.infringers()}
                known |= {r["infringer_id"] for r in conn.execute("SELECT infringer_id FROM registered_infringers")}
                infringer = {**draft.new_infringer, "infringer_id": reg.next_infringer_id(known)}
                conn.execute("INSERT INTO registered_infringers (infringer_id, data, registered_by, registered_at) "
                             "VALUES (?, ?, ?, ?)", (infringer["infringer_id"], json.dumps(infringer, ensure_ascii=False),
                                                     principal.user_id, now))
            owner = draft.fields["lead_counsel_id"]
            row = draft.row(case_id, infringer, self._name(owner), self.today())
            conn.execute("INSERT INTO registered_cases (case_id, data, registered_by, registered_at) VALUES (?, ?, ?, ?)",
                         (case_id, json.dumps(row, ensure_ascii=False), principal.user_id, now))
            self._audit(conn, principal, case_id, "case.registered", f"Case registered: {row['title']}",
                        reg.facts(row), draft.details)
            if owner != principal.user_id:
                self._notify_case_owner(conn, principal, case_id, row["title"], owner, "registered and assigned you",
                                        row["next_action_due"])
        self.refresh()
        self.run_reminders()  # a first action due today is reported now
        return {"case_id": case_id}

    # ---------- visual trademark comparison ----------
    def mark_info(self, mark: dict[str, Any], specimen: bool = False) -> dict[str, Any]:
        return {"mark_id": mark["mark_id"], "mark_name": mark["mark_name"], "mark_name_ar": mark["mark_name_ar"],
                "product_category": mark["product_category"], "nice_classes": str(mark["nice_classes"]),
                "registration_no": mark["uae_registration_no"],
                "registered_in": [c.strip() for c in str(mark["registered_in"] or "").split(",") if c.strip()],
                "specimen": specimen}

    def similarity(self, mark_id: str, sign: str) -> dict[str, Any]:
        mark = self.model.mark(mark_id)
        if mark is None:
            raise RecordError(f"There is no mark {mark_id}.", 404)
        return sim.compare(mark["mark_name"], mark["mark_name_ar"], sign or "")

    def _comparison_out(self, r: sqlite3.Row) -> dict[str, Any]:
        out = self._comparison_row(r)
        out["sounds_alike"] = bool(r["sounds_alike"]) if r["sounds_alike"] is not None else None
        out["assessed_by_id"] = r["assessed_by"]
        return out

    def comparison(self, principal: Principal, case_id: str,
                   specimen: Callable[[str], bool] = lambda _: False) -> dict[str, Any]:
        """The registered mark, the latest assessment against the infringing sign, the earlier ones, and the photos."""
        case = self._visible(principal, case_id)
        mark = self.model.mark(case["mark_id"])
        with self.store.read() as conn:
            rows = conn.execute("SELECT * FROM mark_comparisons WHERE case_id = ? ORDER BY seq DESC",
                                (case["case_id"],)).fetchall()
            photos = None
            if principal.sees_documents:
                photos = [self._evidence_out(e) for e in conn.execute(
                    "SELECT * FROM evidence WHERE case_id = ? AND status = 'Active' AND content_type LIKE 'image/%' "
                    "ORDER BY seq DESC", (case["case_id"],))]
        current = next((r for r in rows if r["status"] == "Current"), None)
        return {"case_id": case["case_id"], "mark": self.mark_info(mark, specimen(mark["mark_id"])) if mark else None,
                "current": self._comparison_out(current) if current else None,
                "history": [self._comparison_out(r) for r in rows],
                "indicators": self.similarity(mark["mark_id"], current["infringing_sign"]) if current and mark else None,
                "photos": photos, "can_record": principal.can_edit}

    def record_comparison(self, principal: Principal, case_id: str, data: dict[str, Any],
                          specimen: Callable[[str], bool] = lambda _: False) -> dict[str, Any]:
        """A new assessment of the registered mark against the sign on the product; it supersedes the last one."""
        self._need_edit(principal)
        case = self._visible(principal, case_id)
        mark = self.model.mark(case["mark_id"])
        if mark is None:
            raise RecordError("This case has no registered mark to compare with.", 409)
        new: dict[str, Any] = {
            "infringing_sign": _text(data.get("infringing_sign"), "The sign on the product", 120, required=True)}
        for field, choices in (("visual", SIMILARITY), ("phonetic", SIMILARITY), ("conceptual", SIMILARITY),
                               ("goods", GOODS), ("overall", cf.LEVELS)):
            value = data.get(field)
            if value not in choices:
                raise RecordError(f"Choose the {COMPARISON_FIELDS[field].lower()}: {', '.join(choices)}.")
            new[field] = value
        new["notes"] = _text(data.get("notes"), "The notes", 2000, multiline=True)
        new["evidence_id"] = None
        if data.get("evidence_id"):
            self._need_documents(principal)
            seq = parse_id("evidence", data["evidence_id"])
            with self.store.read() as conn:
                photo = conn.execute("SELECT * FROM evidence WHERE seq = ?", (seq,)).fetchone()
            if (photo is None or photo["case_id"] != case["case_id"] or photo["status"] != "Active"
                    or not str(photo["content_type"]).startswith("image/")):
                raise RecordError("Choose a photo that is on file for this case.")
            new["evidence_id"] = format_id("evidence", seq)
        found = sim.compare(mark["mark_name"], mark["mark_name_ar"], new["infringing_sign"])
        cid, now = case["case_id"], utc_now()
        with self.store.transaction() as conn:
            prev = conn.execute("SELECT * FROM mark_comparisons WHERE case_id = ? AND status = 'Current' "
                                "ORDER BY seq DESC LIMIT 1", (cid,)).fetchone()
            diffs = [{"field": f, "label": label, "old": prev[f] if prev else None, "new": new[f]}
                     for f, label in COMPARISON_FIELDS.items() if (prev[f] if prev else None) != new[f]]
            if prev is not None and not diffs:
                return self.comparison(principal, cid, specimen)
            conn.execute("UPDATE mark_comparisons SET status = 'Superseded' WHERE case_id = ? AND status = 'Current'", (cid,))
            seq = conn.execute(
                "INSERT INTO mark_comparisons (case_id, mark_id, evidence_id, infringing_sign, visual, phonetic, conceptual, "
                "goods, overall, notes, word_similarity, sounds_alike, assessed_by, assessed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (cid, mark["mark_id"], new["evidence_id"], new["infringing_sign"], new["visual"], new["phonetic"],
                 new["conceptual"], new["goods"], new["overall"], new["notes"], found["word_similarity"],
                 int(found["sounds_alike"]), principal.user_id, now)).lastrowid
            ref = format_id("comparison", seq)
            self._audit(conn, principal, cid, "comparison.recorded",
                        f"Trademark comparison {ref}: {mark['mark_name']} v. “{new['infringing_sign']}” – likelihood of "
                        f"confusion {new['overall'].lower()}", diffs, None, "comparison", ref)
        self.refresh()
        return self.comparison(principal, cid, specimen)

    # ---------- audit trail ----------
    def _audit_rows(self, principal: Principal, case_id: str) -> list[sqlite3.Row]:
        case = self._visible(principal, case_id)
        with self.store.read() as conn:
            rows = conn.execute("SELECT * FROM audit_log WHERE case_id = ? ORDER BY seq DESC", (case["case_id"],)).fetchall()
        return [r for r in rows if principal.sees_documents or r["ref_type"] != "evidence"]

    def audit(self, principal: Principal, case_id: str) -> dict[str, Any]:
        entries = [{"entry_id": format_id("audit", r["seq"]), "at": r["at"], "actor_id": r["actor_id"],
                    "actor_name": r["actor_name"], "actor_role": r["actor_role"], "action": r["action"],
                    "summary": r["summary"], "changes": json.loads(r["changes"]), "reason": r["reason"],
                    "ref_type": r["ref_type"], "ref_id": r["ref_id"], "entry_hash": r["entry_hash"]}
                   for r in self._audit_rows(principal, case_id)]
        return {"entries": entries, "integrity": self.store.verify_chain()}

    def audit_csv(self, principal: Principal, case_id: str) -> str:
        """The case's audit trail as CSV, one row per changed field (for a case file or a court bundle)."""
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(["Entry", "When (UTC)", "Who", "Role", "Action", "Summary", "Field", "Before", "After", "Reason",
                    "Entry hash"])
        for r in reversed(self._audit_rows(principal, case_id)):
            changes = json.loads(r["changes"]) or [None]
            for c in changes:
                w.writerow([format_id("audit", r["seq"]), r["at"], r["actor_name"], r["actor_role"], r["action"],
                            r["summary"], c["label"] if c else "", cf.show(c["old"], self._name) if c else "",
                            cf.show(c["new"], self._name) if c else "", r["reason"] or "", r["entry_hash"]])
        return out.getvalue()

    def counts(self, principal: Principal, case_id: str) -> dict[str, int | None]:
        with self.store.read() as conn:
            evidence = conn.execute("SELECT COUNT(*) FROM evidence WHERE case_id = ? AND status = 'Active'",
                                    (case_id,)).fetchone()[0]
            follow_ups = conn.execute("SELECT COUNT(*) FROM follow_ups WHERE case_id = ? AND status = 'Open'",
                                      (case_id,)).fetchone()[0]
            audit = conn.execute("SELECT COUNT(*) FROM audit_log WHERE case_id = ?"
                                 + ("" if principal.sees_documents else " AND COALESCE(ref_type, '') <> 'evidence'"),
                                 (case_id,)).fetchone()[0]
        return {"evidence": evidence if principal.sees_documents else None, "follow_ups_open": follow_ups, "audit": audit}

    def verify(self) -> dict[str, Any]:
        """The whole store: the audit chain, and every evidence file against its fingerprint."""
        with self.store.read() as conn:
            rows = conn.execute("SELECT seq, sha256 FROM evidence ORDER BY seq").fetchall()
        bad = [format_id("evidence", r["seq"]) for r in rows if not self.blobs.verify(r["sha256"])]
        return {"audit": self.store.verify_chain(), "evidence_checked": len(rows), "evidence_problems": bad}


def case_options(settings: Settings) -> dict[str, Any]:
    """Choices the case forms offer (sent once with /api/meta)."""
    return {
        "stages_open": cf.STAGES_OPEN, "stages_closed": cf.STAGES_CLOSED, "outcomes": cf.OUTCOMES, "levels": cf.LEVELS,
        "relationships": cf.RELATIONSHIPS, "consultation_statuses": cf.CONSULTATION_STATUSES,
        "enforcement_stages": sorted(cf.ENFORCEMENT_STAGES), "labels": cf.LABELS,
        "evidence_categories": ev.CATEGORIES, "photo_categories": ev.PHOTO_CATEGORIES, "accept": ev.ACCEPT,
        "accepted_types": ev.ALLOWED, "evidence_max_mb": settings.evidence_max_mb,
        "follow_up_kinds": [{"kind": k, "title": t, "days": d} for k, (t, d) in FOLLOW_UP_KINDS.items()],
        "decisions": [{"value": k, "label": DECISIONS[k]} for k in RESOLVE_DECISIONS],
        "comparison": {"similarity": SIMILARITY, "goods": GOODS, "overall": cf.LEVELS, "labels": COMPARISON_FIELDS},
        "reminder_lead_days": settings.reminder_lead_days, "escalate_days": settings.escalate_days,
    }
