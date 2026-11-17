"""Deadline reminders: which notifications are due on a given day, and for whom. Pure functions; the service stores them.

Three kinds of deadline are watched:
- follow-ups that users set on a case (e.g. a store given 30 days to remove infringing products): the owner is reminded
  before the deadline, told when it is reached so they can follow up and decide (close, extend or escalate), and the
  deadline is escalated if it is still open some days later;
- the case tracker's next action and its due date, reminded and escalated the same way, to the case owner;
- hearings, the week before and on the day.

Each reminder is one stage of one deadline (key = deadline + stage + date), so it is sent once however often the check
runs; moving a deadline gives it new keys. Only the latest stage reached is sent: a deadline first seen already overdue
produces one "overdue" notice, not three.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Callable, Iterable

TEXTS = {
    ("follow_up", "upcoming"): ("Follow-up due soon", "{case} · {what}: due {due}."),
    ("follow_up", "due"): ("Deadline reached: follow up and decide",
                           "{case} · {what}: the deadline ({due}) has been reached. Check whether it was complied with, "
                           "then close the case, extend the deadline or escalate."),
    ("follow_up", "overdue"): ("Overdue: decision still needed",
                               "{case} · {what}: due {due} and still open. Record the follow-up decision."),
    ("next_action", "upcoming"): ("Next action due soon", "{case} · {what}: due {due}."),
    ("next_action", "due"): ("Next action due", "{case} · {what}: due {due}."),
    ("next_action", "overdue"): ("Next action overdue", "{case} · {what}: was due {due}. Update the case or its next step."),
    ("hearing", "upcoming"): ("Hearing coming up", "{case} · {what}: hearing on {due}."),
    ("hearing", "today"): ("Hearing today", "{case} · {what}: hearing today, {due}."),
}


def fmt_day(day: date | str) -> str:
    d = date.fromisoformat(day) if isinstance(day, str) else day
    return f"{d.day} {d:%b %Y}"


@dataclass(frozen=True)
class Reminder:
    key: str
    recipients: tuple[str, ...]
    case_id: str
    kind: str          # follow_up | next_action | hearing
    stage: str         # upcoming | due | overdue | today
    title: str
    body: str
    due_date: str
    link: str
    ref_id: str | None = None


def stage_of(due: date, today: date, lead_days: int, escalate_days: int) -> str | None:
    if today >= due + timedelta(days=escalate_days):
        return "overdue"
    if today >= due:
        return "due"
    if lead_days > 0 and today >= due - timedelta(days=lead_days):
        return "upcoming"
    return None


def _unique(ids: Iterable[str | None]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(i for i in ids if i))


def _reminder(key: str, recipients: Iterable[str | None], case: dict[str, Any], kind: str, stage: str, what: str,
              due: date, link: str, ref_id: str | None = None) -> Reminder:
    title, body = TEXTS[(kind, stage)]
    return Reminder(key, _unique(recipients), case["case_id"], kind, stage, title,
                    body.format(case=case["case_id"], what=what, due=fmt_day(due)), due.isoformat(), link, ref_id)


def follow_up_reminders(follow_ups: Iterable[dict[str, Any]], cases: dict[str, dict[str, Any]], today: date,
                        escalate_days: int, escalate_to: Callable[[dict[str, Any]], list[str]]) -> list[Reminder]:
    """Open follow-ups: rows with id, case_id, title, owner_id, created_by, due_date, remind_days, status."""
    out = []
    for fu in follow_ups:
        case = cases.get(fu["case_id"])
        if fu["status"] != "Open" or case is None:
            continue
        due = date.fromisoformat(fu["due_date"])
        stage = stage_of(due, today, fu["remind_days"], escalate_days)
        if stage is None:
            continue
        recipients = [fu["owner_id"]]
        if stage != "upcoming":
            recipients.append(fu["created_by"])  # whoever set the deadline wants to know it was reached
        if stage == "overdue":
            recipients += escalate_to(case)
        out.append(_reminder(f"fu:{fu['id']}:{stage}:{due}", recipients, case, "follow_up", stage, fu["title"], due,
                             f"/cases/{case['case_id']}?tab=follow-ups", fu["id"]))
    return out


def tracker_reminders(cases: Iterable[dict[str, Any]], today: date, lead_days: int, escalate_days: int,
                      escalate_to: Callable[[dict[str, Any]], list[str]]) -> list[Reminder]:
    """Open cases' next action due dates and next hearings, for the case owner (lead counsel)."""
    out = []
    for case in cases:
        if case["status"] != "Open":
            continue
        owner = case.get("lead_counsel_id")
        if case.get("next_action_due"):
            due = date.fromisoformat(case["next_action_due"])
            stage = stage_of(due, today, lead_days, escalate_days)
            if stage:
                recipients = [owner, *(escalate_to(case) if stage == "overdue" else [])]
                out.append(_reminder(f"na:{case['case_id']}:{stage}:{due}", recipients, case, "next_action", stage,
                                     case.get("next_action") or "Next action", due, f"/cases/{case['case_id']}"))
        if case.get("next_hearing_date"):
            day = date.fromisoformat(case["next_hearing_date"])
            stage = "today" if day == today else "upcoming" if lead_days and today < day <= today + timedelta(days=lead_days) else None
            if stage:
                out.append(_reminder(f"hr:{case['case_id']}:{stage}:{day}", [owner], case, "hearing", stage,
                                     case.get("court_name") or "Court", day, f"/cases/{case['case_id']}"))
    return out
