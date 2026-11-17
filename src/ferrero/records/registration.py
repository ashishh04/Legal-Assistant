"""Registering a new case in the app: the choices the form offers, the checks, and the case as first recorded.

The choices come from the case tracker itself (case types, sources, countries, courts, reference exchange rates), so a
registered case looks like every other case to the pages, the KPIs, the reminders and the assistant. It starts at the
Intake stage with an owner; assigning, following up and closing then work as on any case.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Callable

from ..casemodel import CaseModel
from ..security import Principal, group_for_country
from . import fields as cf
from .errors import RecordError
from .evidence import parse_day

LANGUAGES = ("EN", "AR", "EN/AR")
SENSITIVITIES = ("Confidential", "Restricted", "Internal")
FIRST_STAGE = "Intake"
DEFAULT_NEXT_ACTION = "Review the report and decide the next step"
DEFAULT_NEXT_ACTION_DAYS = 7
_INFRINGER_ID = re.compile(r"INF-(\d+)\Z")


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


def _choice(value: Any, label: str, choices: tuple[str, ...] | list[str], *, required: bool = True) -> str | None:
    if value in (None, ""):
        if required:
            raise RecordError(f"Choose the {label.lower()}.")
        return None
    if value not in choices:
        raise RecordError(f"{label} must be one of: {', '.join(choices)}.")
    return value


@dataclass(frozen=True)
class Choices:
    """What a new case may be: the values the tracker already uses."""
    case_types: tuple[str, ...]
    sources: tuple[str, ...]
    countries: tuple[str, ...]
    currency: dict[str, str]          # country -> currency
    aed_rate: dict[str, float]        # currency -> AED per unit (the tracker's reference rates)
    courts: dict[str, dict[str, Any]]
    infringer_types: tuple[str, ...]

    @classmethod
    def from_model(cls, model: CaseModel) -> "Choices":
        cases = model.base_cases()
        rates: dict[str, float] = {"AED": 1.0}
        for c in cases:
            for local, aed in (("claim_amount_local", "claim_amount_aed"), ("awarded_amount_local", "awarded_amount_aed")):
                if c[local] and c[aed] and c["currency"] not in rates:
                    rates[c["currency"]] = round(c[aed] / c[local], 4)
        return cls(
            case_types=tuple(sorted({c["case_type"] for c in cases})),
            sources=tuple(sorted({c["source_channel"] for c in cases})),
            countries=tuple(sorted({c["country"] for c in cases})),
            currency={c["country"]: c["currency"] for c in cases},
            aed_rate=rates,
            courts={r["court_id"]: r for r in model.tables["dim_court"].dicts()},
            infringer_types=tuple(sorted({r["infringer_type"] for r in model.infringers()})),
        )


def options_for(principal: Principal, model: CaseModel, choices: Choices) -> dict[str, Any]:
    """The registration form's choices, limited to the countries this user's role covers."""
    countries = [c for c in choices.countries if principal.sees_country(c)]
    return {
        "marks": [{k: m[k] for k in ("mark_id", "mark_name", "mark_name_ar", "product_category")} for m in model.marks()],
        "case_types": list(choices.case_types),
        "sources": list(choices.sources),
        "countries": [{"country": c, "currency": choices.currency.get(c, "AED"), "access_group": group_for_country(c)}
                      for c in countries],
        "courts": sorted(({"court_id": r["court_id"], "country": r["country"], "court_name": r["court_name_en"]}
                          for r in choices.courts.values() if r["country"] in countries),
                         key=lambda r: (r["country"], r["court_name"])),
        "infringers": sorted(({"infringer_id": i["infringer_id"], "name": i["infringer_name_en"],
                               "name_ar": i["infringer_name_ar"], "type": i["infringer_type"], "country": i["country"]}
                              for i in model.infringers() if i["country"] in countries), key=lambda i: i["name"].casefold()),
        "infringer_types": list(choices.infringer_types),
        "levels": list(cf.LEVELS),
        "relationships": list(cf.RELATIONSHIPS),
        "languages": list(LANGUAGES),
        "sensitivities": list(SENSITIVITIES),
        "default_next_action": DEFAULT_NEXT_ACTION,
        "default_next_action_days": DEFAULT_NEXT_ACTION_DAYS,
    }


@dataclass
class Draft:
    """A checked registration, before it has its case number."""
    fields: dict[str, Any]
    infringer: dict[str, Any] | None        # an existing infringer
    new_infringer: dict[str, Any] | None    # or one to record with the case
    details: str | None

    def row(self, case_id: str, infringer: dict[str, Any], owner_name: str, today: date) -> dict[str, Any]:
        f = self.fields
        opened = date.fromisoformat(f["opened_date"])
        return {
            **f, "case_id": case_id, "title": f"{f['mark_name']} v. {infringer['infringer_name_en']}",
            "infringer_id": infringer["infringer_id"], "infringer_name": infringer["infringer_name_en"],
            "infringer_type": infringer["infringer_type"], "status": "Open", "stage": FIRST_STAGE, "outcome": cf.PENDING,
            "closed_date": None, "awarded_amount_local": 0, "awarded_amount_aed": 0, "settlement_amount_local": 0,
            "settlement_amount_aed": 0, "recovered_amount_local": 0, "recovered_amount_aed": 0, "next_hearing_date": None,
            "last_action_date": f["opened_date"], "sharepoint_library": f"/sites/Legal/Cases/{f['country']}/{case_id}",
            "days_open": (today - opened).days, "legal_spend_aed": 0, "lead_counsel": owner_name,
            "consultation_contact": None, "consultation_notes": None,
        }


def validate(data: dict[str, Any], principal: Principal, model: CaseModel, choices: Choices, today: date,
             can_own: Callable[[str, str], bool]) -> Draft:
    if not isinstance(data, dict):
        raise RecordError("Fill in the case details.")
    mark = model.mark(data.get("mark_id") or "")
    if mark is None:
        raise RecordError("Choose the mark that is infringed.")
    country = _choice(data.get("country"), "Country", choices.countries)
    if not principal.sees_country(country):
        raise RecordError(f"Your role doesn't cover {country}: ask Legal Operations to register this case.", 403,
                          "country_not_covered")
    group = group_for_country(country)
    case_type = _choice(data.get("case_type"), "Case type", choices.case_types)
    source = _choice(data.get("source_channel"), "Source", choices.sources)
    court = None
    if data.get("court_id"):
        court = choices.courts.get(data["court_id"])
        if court is None or court["country"] != country:
            raise RecordError(f"Choose a court in {country}, or leave the court empty.")
    opened_text = parse_day(data.get("opened_date"), "The date it was reported") or today.isoformat()
    if opened_text > today.isoformat():
        raise RecordError("The date it was reported can't be in the future.")
    if opened_text < "2000-01-01":
        raise RecordError("Check the date it was reported.")
    priority = _choice(data.get("priority") or "Medium", "Legal priority", cf.LEVELS)
    risk = _choice(data.get("risk_rating"), "Risk rating", cf.LEVELS, required=False)
    owner = _text(data.get("lead_counsel_id"), "The case owner", 10) or principal.user_id
    if not cf.USER_ID.fullmatch(owner) or not can_own(owner, group):
        raise RecordError(f"The case owner must be a member of the legal team who covers {country}.")
    next_action = _text(data.get("next_action"), "The next action", 200)
    due = parse_day(data.get("next_action_due"), "The next action's due date")
    if due and not next_action:
        raise RecordError("Say what the next action is, or leave its due date empty.")
    if due and due < opened_text:
        raise RecordError("The next action can't be due before the case was reported.")
    claim = data.get("claim_amount_local")
    if claim in (None, ""):
        claim = 0
    try:
        claim = float(claim)
    except (TypeError, ValueError):
        raise RecordError("The amount claimed must be a number.") from None
    if isinstance(data.get("claim_amount_local"), bool) or not 0 <= claim <= 1e12:
        raise RecordError("The amount claimed must be zero or more.")
    claim = int(claim) if claim.is_integer() else round(claim, 2)
    currency = choices.currency.get(country, "AED")
    business_priority = _choice(data.get("business_priority"), "Business priority", cf.LEVELS, required=False)
    consult = data.get("consultation_required")
    if consult not in (None, True, False):
        raise RecordError("Business consultation before enforcement must be Yes or No.")
    relationship = _choice(data.get("commercial_relationship"), "Commercial relationship", cf.RELATIONSHIPS, required=False)

    infringer, new_infringer = None, None
    if data.get("infringer_id"):
        infringer = next((i for i in model.infringers() if i["infringer_id"] == data["infringer_id"]), None)
        if infringer is None:
            raise RecordError("Choose the infringer from the list, or enter a new one.")
    else:
        name = _text(data.get("infringer_name"), "The infringer's name", 200, required=True)
        known = next((i for i in model.infringers()
                      if i["infringer_name_en"].casefold() == name.casefold() and i["country"] == country), None)
        if known:
            infringer = known  # the same name in the same country is the infringer already on record
        else:
            new_infringer = {
                "infringer_name_en": name, "infringer_name_ar": _text(data.get("infringer_name_ar"), "The Arabic name", 200),
                "infringer_type": _choice(data.get("infringer_type"), "Infringer type", choices.infringer_types),
                "country": country, "city": _text(data.get("infringer_city"), "The city", 100),
                "case_count": 1, "repeat_offender": 0, "first_seen": opened_text,
            }

    fields = {
        "mark_id": mark["mark_id"], "mark_name": mark["mark_name"], "case_type": case_type, "country": country,
        "court_id": court["court_id"] if court else None, "court_name": court["court_name_en"] if court else None,
        "source_channel": source, "opened_date": opened_text, "priority": priority, "risk_rating": risk,
        "lead_counsel_id": owner, "external_firm": _text(data.get("external_firm"), "The external firm", 200),
        "currency": currency, "claim_amount_local": claim, "claim_amount_aed": round(claim * choices.aed_rate.get(currency, 1.0)),
        "next_action": next_action, "next_action_due": due,
        "language": _choice(data.get("language") or "EN", "File language", LANGUAGES),
        "sensitivity": _choice(data.get("sensitivity") or "Confidential", "Sensitivity", SENSITIVITIES),
        "access_group": group, "business_priority": business_priority,
        "consultation_required": None if consult is None else int(consult),
        "commercial_relationship": relationship, "consultation_status": "Not started" if consult else None,
    }
    return Draft(fields, infringer, new_infringer, _text(data.get("details"), "The details", 2000, multiline=True))


def next_case_id(taken: set[str], opened: str) -> str:
    year = opened[:4]
    numbers = [int(c[-3:]) for c in taken if c.startswith(f"TM-{year}-") and c[-3:].isdigit()]
    number = max(numbers, default=400) + 1
    if number > 999:
        raise RecordError(f"There are no case numbers left for {year}.", 409)
    return f"TM-{year}-{number:03d}"


def next_infringer_id(taken: set[str]) -> str:
    numbers = [int(m.group(1)) for t in taken if (m := _INFRINGER_ID.match(t))]
    return f"INF-{max(numbers, default=0) + 1:03d}"


def facts(row: dict[str, Any]) -> list[dict[str, Any]]:
    """The case as registered, for its first audit entry (each value as 'before: none, after: value')."""
    items = [("title", "Title"), ("mark_name", "Mark"), ("infringer_name", "Infringer"), ("case_type", "Case type"),
             ("country", "Country"), ("court_name", "Court"), ("source_channel", "Source"), ("opened_date", "Reported on"),
             ("stage", "Stage"), ("priority", "Legal priority"), ("risk_rating", "Risk rating"),
             ("lead_counsel_id", "Case owner"), ("external_firm", "External firm"), ("next_action", "Next action"),
             ("next_action_due", "Next action due"), ("claim_amount_local", f"Amount claimed ({row['currency']})"),
             ("business_priority", "Business priority"),
             ("consultation_required", "Business consultation before enforcement"),
             ("commercial_relationship", "Commercial relationship"), ("language", "File language"),
             ("sensitivity", "Sensitivity")]
    out = []
    for field, label in items:
        value = row.get(field)
        if field == "consultation_required" and value is not None:
            value = bool(value)
        if value not in (None, "", 0) or field == "consultation_required" and value is False:
            out.append({"field": field, "label": label, "old": None, "new": value})
    return out


def default_due(today: date) -> str:
    return (today + timedelta(days=DEFAULT_NEXT_ACTION_DAYS)).isoformat()
