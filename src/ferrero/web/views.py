"""Read models for the web frontend: overview KPIs and charts, the case list, document sync status.

Every query runs on the principal's filtered snapshot of the case tracker, so the pages show exactly
what the assistant can see, and the definitions match the dashboards' measures (and the golden set).
"""
from __future__ import annotations

import os
import sqlite3
from typing import Any

from ..casemodel import CaseModel
from ..security import CASE_GROUPS, Principal
from ..sync.index import DocumentIndex

STAGES = ["Intake", "Investigation", "Notice sent", "Filed", "Hearing", "Judgment", "Appeal"]
OUTCOMES = ["Won", "Partially won", "Settled", "Takedown achieved", "Lost", "Withdrawn"]
FAVOURABLE = ("Won", "Partially won", "Settled", "Takedown achieved")


def _rows(conn: sqlite3.Connection, sql: str, params: list[Any] | tuple = ()) -> list[dict[str, Any]]:
    cur = conn.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _ratio(num: float | None, den: float | None) -> float | None:
    return round(num / den, 4) if num is not None and den else None


def overview(model: CaseModel, principal: Principal, country: str | None = None, mark: str | None = None) -> dict[str, Any]:
    conn = model.connect(principal)
    try:
        where, params = ["1 = 1"], []
        if country:
            where.append("country = ?")
            params.append(country)
        if mark:
            where.append("mark_id = ?")
            params.append(mark)
        w = " AND ".join(where)
        fav = ", ".join(f"'{o}'" for o in FAVOURABLE)
        k = _rows(conn, f"""
            SELECT COUNT(*) AS cases,
                   COALESCE(SUM(status = 'Open'), 0) AS open_cases,
                   COALESCE(SUM(opened_date >= date(reporting_date(), '-30 days')), 0) AS new_cases_30d,
                   COALESCE(SUM(status = 'Open' AND next_hearing_date BETWEEN reporting_date() AND date(reporting_date(), '+30 days')), 0) AS hearings_30d,
                   COALESCE(SUM(status = 'Open' AND next_action_due < reporting_date()), 0) AS overdue_actions,
                   AVG(CASE WHEN status = 'Open' THEN julianday(reporting_date()) - julianday(opened_date) END) AS avg_days_open,
                   COALESCE(SUM(status = 'Closed' AND closed_date BETWEEN strftime('%Y', reporting_date()) || '-01-01' AND reporting_date()), 0) AS closed_ytd,
                   COALESCE(SUM(claim_amount_aed), 0) AS claimed,
                   COALESCE(SUM(awarded_amount_aed), 0) AS awarded,
                   COALESCE(SUM(settlement_amount_aed), 0) AS settled,
                   COALESCE(SUM(recovered_amount_aed), 0) AS recovered,
                   COALESCE(SUM(outcome IN ({fav})), 0) AS favourable,
                   COALESCE(SUM(outcome IN ({fav}, 'Lost')), 0) AS decided
            FROM fact_case WHERE {w}""", params)[0]
        k["legal_spend"] = _rows(conn, f"SELECT COALESCE(SUM(i.amount_aed), 0) AS s FROM fact_invoice i "
                                       f"JOIN fact_case c ON c.case_id = i.case_id WHERE {w}", params)[0]["s"]
        k["recovery_rate"] = _ratio(k["recovered"], (k["awarded"] or 0) + (k["settled"] or 0))
        k["win_rate"] = _ratio(k["favourable"], k["decided"])
        k["spend_to_recovery"] = _ratio(k["legal_spend"], k["recovered"])
        k["avg_days_open"] = round(k["avg_days_open"]) if k["avg_days_open"] is not None else None

        stage_counts = {r["stage"]: r["n"] for r in _rows(
            conn, f"SELECT stage, COUNT(*) AS n FROM fact_case WHERE status = 'Open' AND {w} GROUP BY stage", params)}
        outcome_counts = {r["outcome"]: r["n"] for r in _rows(
            conn, f"SELECT outcome, COUNT(*) AS n FROM fact_case WHERE status = 'Closed' AND {w} GROUP BY outcome", params)}
        return {
            "as_of": model.demo_today.isoformat(),
            "kpis": k,
            "open_by_stage": [{"label": s, "value": stage_counts.get(s, 0)} for s in STAGES],
            "open_by_country": [{"label": r["country"], "value": r["n"]} for r in _rows(
                conn, f"SELECT country, COUNT(*) AS n FROM fact_case WHERE status = 'Open' AND {w} "
                      f"GROUP BY country ORDER BY n DESC, country", params)],
            "amounts_by_year": _rows(conn, f"""
                SELECT strftime('%Y', opened_date) AS year, SUM(claim_amount_aed) AS claimed,
                       SUM(awarded_amount_aed + settlement_amount_aed) AS awarded_or_settled, SUM(recovered_amount_aed) AS recovered
                FROM fact_case WHERE {w} GROUP BY year ORDER BY year""", params),
            "outcomes": [{"label": o, "value": outcome_counts.get(o, 0)} for o in OUTCOMES],
            "upcoming": _rows(conn, f"""
                SELECT case_id, title, country, court_name, stage, next_hearing_date, next_action, next_action_due,
                       lead_counsel, (next_action_due < reporting_date()) AS overdue
                FROM fact_case
                WHERE status = 'Open' AND {w}
                  AND (next_hearing_date <= date(reporting_date(), '+30 days') OR next_action_due <= date(reporting_date(), '+30 days'))
                ORDER BY overdue DESC, COALESCE(next_action_due, next_hearing_date) LIMIT 12""", params),
            "top_infringers": _rows(conn, f"""
                SELECT infringer_id, infringer_name AS name, infringer_type AS type, country, COUNT(*) AS cases,
                       SUM(status = 'Open') AS open, SUM(recovered_amount_aed) AS recovered
                FROM fact_case WHERE {w} GROUP BY infringer_id ORDER BY cases DESC, recovered DESC LIMIT 8""", params),
            "opened_by_month": _rows(conn, f"""
                WITH RECURSIVE months(m, n) AS (
                    SELECT date(reporting_date(), 'start of month', '-11 months'), 0
                    UNION ALL SELECT date(m, '+1 month'), n + 1 FROM months WHERE n < 11)
                SELECT strftime('%Y-%m', m) AS month,
                       (SELECT COUNT(*) FROM fact_case WHERE strftime('%Y-%m', opened_date) = strftime('%Y-%m', m) AND {w}) AS value
                FROM months ORDER BY m""", params),
            "filters": {
                "countries": [r["country"] for r in _rows(conn, "SELECT DISTINCT country FROM fact_case ORDER BY country")],
                "marks": _rows(conn, "SELECT DISTINCT mark_id AS id, mark_name AS name FROM fact_case ORDER BY mark_name"),
            },
        }
    finally:
        conn.close()


def case_list(model: CaseModel, principal: Principal) -> list[dict[str, Any]]:
    conn = model.connect(principal)
    try:
        return _rows(conn, """
            SELECT case_id, title, mark_id, mark_name, infringer_name, infringer_type, case_type, country, court_name,
                   status, stage, outcome, priority, risk_rating, opened_date, closed_date, next_hearing_date, next_action,
                   next_action_due, lead_counsel_id, lead_counsel, currency, claim_amount_aed, awarded_amount_aed,
                   settlement_amount_aed, recovered_amount_aed, days_open,
                   (status = 'Open' AND next_action_due < reporting_date()) AS overdue,
                   business_priority, consultation_required, consultation_status, commercial_relationship
            FROM fact_case ORDER BY opened_date DESC""")
    finally:
        conn.close()


def documents(index: DocumentIndex, principal: Principal) -> dict[str, Any]:
    """The document sync's status, as far as this principal may see it."""
    if not principal.sees_documents:
        return {"documents": [], "counts": {}, "visible": False}
    sees_everything = principal.role.case_groups == frozenset(CASE_GROUPS)
    rows = [r for r in index.catalogue()
            if (r["access_group"] and principal.sees_group(r["access_group"])) or (not r["access_group"] and sees_everything)]
    keep = ("doc_id", "case_id", "file_name", "doc_type", "language", "access_group", "sensitivity", "library_path",
            "extraction", "ocr_confidence", "pages", "index_status", "skip_reason", "passages", "indexed_at")
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["index_status"]] = counts.get(r["index_status"], 0) + 1
    return {"documents": [{k: r[k] for k in keep} for r in rows], "counts": counts, "visible": True}


def superset_dashboards() -> list[dict[str, str]]:
    """FERRERO_SUPERSET_DASHBOARDS="Title|https://…;Title|https://…" -> embeddable dashboards for the Dashboards page."""
    out = []
    for item in os.environ.get("FERRERO_SUPERSET_DASHBOARDS", "").split(";"):
        title, sep, url = item.partition("|")
        if sep and url.strip().startswith(("http://", "https://")):
            out.append({"title": title.strip(), "url": url.strip()})
    return out
