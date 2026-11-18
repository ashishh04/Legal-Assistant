"""The case fields users may change, the values each takes, and the rules that keep a case consistent.

``plan_update`` turns a request ("close the case as Settled", "set business priority to High") into the full set of
field changes it implies, or refuses it with a message saying what to fix. It does not write anything.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

from .errors import RecordError
from .evidence import parse_day

STAGES_OPEN = ("Intake", "Investigation", "Notice sent", "Filed", "Hearing", "Judgment", "Appeal")
STAGES_CLOSED = ("Closed", "Settled")
OUTCOMES = ("Won", "Partially won", "Settled", "Takedown achieved", "Lost", "Withdrawn")
PENDING = "Pending"
LEVELS = ("High", "Medium", "Low")
RELATIONSHIPS = ("None known", "Customer", "Distributor or reseller", "Commercial partner", "Supplier")
CONSULTATION_STATUSES = ("Not started", "In progress", "Cleared to proceed", "Hold enforcement")
CLEARED = "Cleared to proceed"
# Moving a case into one of these stages from an earlier one starts enforcement: a notice, a filing, a court step.
ENFORCEMENT_STAGES = frozenset({"Notice sent", "Filed", "Hearing", "Judgment", "Appeal"})
USER_ID = re.compile(r"U-\d{2,3}")
ISO_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")


@dataclass(frozen=True)
class FieldSpec:
    name: str
    label: str
    kind: str                       # choice | text | date | bool | user
    choices: tuple[str, ...] = ()
    max_len: int = 200
    required: bool = False          # can't be emptied
    business: bool = False          # part of the commercial-sensitivity assessment


FIELDS: dict[str, FieldSpec] = {f.name: f for f in (
    FieldSpec("status", "Status", "choice", ("Open", "Closed"), required=True),
    FieldSpec("stage", "Stage", "choice", STAGES_OPEN + STAGES_CLOSED, required=True),
    FieldSpec("outcome", "Outcome", "choice", OUTCOMES + (PENDING,), required=True),
    FieldSpec("closed_date", "Closed on", "date"),
    FieldSpec("priority", "Legal priority", "choice", LEVELS, required=True),
    FieldSpec("risk_rating", "Risk rating", "choice", LEVELS),
    FieldSpec("lead_counsel_id", "Case owner", "user", required=True),
    FieldSpec("external_firm", "External firm", "text"),
    FieldSpec("next_action", "Next action", "text"),
    FieldSpec("next_action_due", "Next action due", "date"),
    FieldSpec("next_hearing_date", "Next hearing", "date"),
    FieldSpec("business_priority", "Business priority", "choice", LEVELS, business=True),
    FieldSpec("consultation_required", "Business consultation before enforcement", "bool", business=True),
    FieldSpec("commercial_relationship", "Commercial relationship", "choice", RELATIONSHIPS, business=True),
    FieldSpec("consultation_status", "Business consultation status", "choice", CONSULTATION_STATUSES, business=True),
    FieldSpec("consultation_contact", "Business contact", "text", business=True),
    FieldSpec("consultation_notes", "Business considerations", "text", max_len=2000, business=True),
)}
MANAGED = {"last_action_date": "Last activity"}  # set by the rules below, never directly
LABELS = {**{n: f.label for n, f in FIELDS.items()}, **MANAGED}
TRACKED = (*FIELDS, *MANAGED)


def clean_value(spec: FieldSpec, raw: Any) -> Any:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        if spec.required:
            raise RecordError(f"{spec.label} can't be empty.")
        return None
    if spec.kind == "bool":
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str) and raw.strip().lower() in ("yes", "no", "true", "false"):
            return raw.strip().lower() in ("yes", "true")
        raise RecordError(f"{spec.label} must be Yes or No.")
    if not isinstance(raw, str):
        raise RecordError(f"{spec.label} must be text.")
    value = raw.strip() if spec.max_len > 200 else " ".join(raw.split())
    if spec.kind == "choice":
        if value not in spec.choices:
            raise RecordError(f"{spec.label} must be one of: {', '.join(spec.choices)}.")
    elif spec.kind == "date":
        value = parse_day(value, spec.label)
    elif spec.kind == "user":
        if not USER_ID.fullmatch(value):
            raise RecordError(f"{spec.label} must be a user id such as U-04.")
    elif len(value) > spec.max_len:
        raise RecordError(f"{spec.label} is limited to {spec.max_len} characters.")
    return value


def _current(name: str, value: Any) -> Any:
    if name in FIELDS and FIELDS[name].kind == "bool" and value is not None:
        return bool(value)
    return value


@dataclass
class Plan:
    new: dict[str, Any]
    diffs: list[dict[str, Any]]   # {field, label, old, new}, in field order
    closing: bool = False
    reopening: bool = False
    starts_enforcement: bool = False

    @property
    def business_only(self) -> bool:
        return bool(self.diffs) and all(FIELDS.get(d["field"], FIELDS["status"]).business for d in self.diffs)


def plan_update(case: dict[str, Any], raw_changes: dict[str, Any], *, today: date,
                can_own: Callable[[str], bool]) -> Plan:
    if not isinstance(raw_changes, dict) or not raw_changes:
        raise RecordError("Nothing to change.")
    unknown = sorted(k for k in raw_changes if k not in FIELDS)
    if unknown:
        raise RecordError(f"These case details can't be changed here: {', '.join(unknown)}.")
    changes = {k: clean_value(FIELDS[k], v) for k, v in raw_changes.items()}
    cur = {k: _current(k, case.get(k)) for k in TRACKED}
    new = {**cur, **changes}
    today_s, opened = today.isoformat(), case.get("opened_date")

    if changes.get("lead_counsel_id") not in (None, cur["lead_counsel_id"]) and not can_own(changes["lead_counsel_id"]):
        raise RecordError("The case owner must be a member of the legal team who can see this case.")

    closing = new["status"] == "Closed" and cur["status"] != "Closed"
    reopening = new["status"] == "Open" and cur["status"] == "Closed"
    if new["status"] == "Closed":
        if new["outcome"] in (None, PENDING):
            raise RecordError("Choose the outcome to close the case.")
        if closing:
            new["closed_date"] = changes.get("closed_date") or today_s
            if new["stage"] not in STAGES_CLOSED or "stage" not in changes:
                new["stage"] = "Settled" if new["outcome"] == "Settled" else "Closed"
            new.update(next_action=None, next_action_due=None, next_hearing_date=None, last_action_date=new["closed_date"])
        elif new["stage"] not in STAGES_CLOSED:
            raise RecordError("A closed case's stage is Closed or Settled. Reopen the case to move it to another stage.")
        if not new["closed_date"]:
            raise RecordError("A closed case needs the date it was closed.")
        if new["closed_date"] > today_s:
            raise RecordError("The closing date can't be in the future.")
    elif reopening:
        if "stage" not in changes or new["stage"] not in STAGES_OPEN:
            raise RecordError("Choose the stage the reopened case is at.")
        new.update(outcome=PENDING, closed_date=None)
    else:
        if new["stage"] not in STAGES_OPEN:
            raise RecordError("To close the case, set its status to Closed and choose the outcome.")
        if new["outcome"] != PENDING:
            raise RecordError("An open case's outcome stays Pending until the case is closed.")
        if new["closed_date"]:
            raise RecordError("Only a closed case has a closing date.")
    if new["closed_date"] and opened and new["closed_date"] < opened:
        raise RecordError(f"The closing date can't be before the case was opened ({opened}).")

    # A consultation status only exists when consultation is required; it starts at "Not started".
    if new["consultation_required"] is not True:
        if changes.get("consultation_status") is not None:
            raise RecordError("Mark business consultation as required before recording its status.")
        new["consultation_status"] = None
    elif new["consultation_status"] is None:
        new["consultation_status"] = "Not started"

    diffs = [{"field": f, "label": LABELS[f], "old": cur[f], "new": new[f]} for f in TRACKED if new[f] != cur[f]]
    starts = new["stage"] in ENFORCEMENT_STAGES and cur["stage"] not in ENFORCEMENT_STAGES
    return Plan(new, diffs, closing=closing, reopening=reopening, starts_enforcement=starts)


def enforcement_blocked(plan: Plan) -> bool:
    """Starting enforcement while business consultation is required and not cleared."""
    return plan.starts_enforcement and plan.new["consultation_required"] is True and plan.new["consultation_status"] != CLEARED


def show(value: Any, name_of: Callable[[str], str] = str) -> str:
    if value is None or value == "":
        return "–"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, str) and USER_ID.fullmatch(value):
        return name_of(value)
    if isinstance(value, str) and ISO_DAY.fullmatch(value):
        day = date.fromisoformat(value)
        return f"{day.day} {day:%b %Y}"
    text = str(value)
    return text if len(text) <= 60 else text[:57].rstrip() + "…"


def describe(diffs: list[dict[str, Any]], name_of: Callable[[str], str] = str, limit: int = 4) -> str:
    """'Stage: Investigation → Notice sent; Business priority: – → High' (long texts shortened)."""
    parts = []
    for d in diffs[:limit]:
        if isinstance(d["new"], str) and len(d["new"]) > 60 or isinstance(d["old"], str) and len(d["old"] or "") > 60:
            parts.append(f"{d['label']} updated")
        else:
            parts.append(f"{d['label']}: {show(d['old'], name_of)} → {show(d['new'], name_of)}")
    more = len(diffs) - limit
    return "; ".join(parts) + (f"; and {more} more" if more > 0 else "")
