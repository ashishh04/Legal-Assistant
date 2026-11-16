"""The case model: the pack's tables (the data behind the Power BI dashboards), filtered per user.

Each principal gets an in-memory SQLite database that contains only the rows their role may
see, so any SQL the assistant writes is row-level secure by construction. The database is
built once per access scope, cached as a serialised snapshot, and opened read-only per query
(an authorizer allows SELECT and reads only; one statement per call; time and row limits).
"""
from __future__ import annotations

import csv
import re
import sqlite3
import threading
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable

from .security import Principal, role_for_group

TABLES = (
    "dim_mark", "dim_court", "dim_infringer", "dim_user",
    "fact_case", "fact_case_event", "fact_document", "fact_mailbox", "fact_intake_form", "fact_appstore", "fact_invoice",
)
HIDDEN_COLUMNS = {"dim_user": {"email"}}  # not needed to answer questions; keep personal data out of the prompt
CASE_CHILD_TABLES = {"fact_case_event", "fact_invoice", "fact_document"}
COUNTRY_TABLES = {"fact_mailbox", "fact_intake_form", "fact_appstore"}

_INT = re.compile(r"-?\d+\Z")
_REAL = re.compile(r"-?\d+(\.\d+)?([eE][-+]?\d+)?\Z")
_ALLOWED_ACTIONS = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
    getattr(sqlite3, "SQLITE_RECURSIVE", 33),
}


class QueryError(ValueError):
    """A query the case model refused or could not run; the message is safe to show the model."""


@dataclass
class Table:
    name: str
    columns: list[str]
    types: list[str]
    rows: list[tuple]

    def dicts(self) -> list[dict[str, Any]]:
        return [dict(zip(self.columns, row)) for row in self.rows]


def _converter(values: list[str]) -> tuple[str, Callable[[str], Any]]:
    if values and all(v in ("True", "False") for v in values):
        return "INTEGER", lambda v: None if v == "" else int(v == "True")
    if values and all(_INT.match(v) for v in values):
        return "INTEGER", lambda v: None if v == "" else int(v)
    if values and all(_REAL.match(v) for v in values):
        return "REAL", lambda v: None if v == "" else float(v)
    return "TEXT", lambda v: None if v == "" else v


def load_table(path: Path, hidden: set[str] | frozenset[str] = frozenset()) -> Table:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        raw = [row for row in reader if row]
    keep = [i for i, c in enumerate(header) if c not in hidden]
    types, convs = [], []
    for i in keep:
        t, conv = _converter([r[i] for r in raw if i < len(r) and r[i] != ""])
        types.append(t)
        convs.append(conv)
    rows = [tuple(conv(r[i] if i < len(r) else "") for i, conv in zip(keep, convs)) for r in raw]
    return Table(path.stem, [header[i] for i in keep], types, rows)


def _read_only_authorizer(action: int, *_: Any) -> int:
    return sqlite3.SQLITE_OK if action in _ALLOWED_ACTIONS else sqlite3.SQLITE_DENY


class CaseModel:
    def __init__(self, csv_dir: Path, demo_today: date, catalogue: Path | None = None):
        self.demo_today = demo_today
        self.tables: dict[str, Table] = {
            name: load_table(csv_dir / f"{name}.csv", HIDDEN_COLUMNS.get(name, frozenset())) for name in TABLES
        }
        if catalogue is not None and catalogue.is_file():
            # The document corpus's own catalogue (<corpus>_meta/fact_document.csv): the same rows, with the real
            # file names and the dates the files carry, which follow the case timeline.
            self.tables["fact_document"] = load_table(catalogue, HIDDEN_COLUMNS.get("fact_document", frozenset()))
        self._cases = {r["case_id"]: r for r in self.tables["fact_case"].dicts()}
        self._marks = {r["mark_id"]: r for r in self.tables["dim_mark"].dicts()}
        self._infringers = {r["infringer_id"]: r for r in self.tables["dim_infringer"].dicts()}
        self._users = {r["user_id"]: r for r in self.tables["dim_user"].dicts()}
        self._docs_by_file = {r["title"]: r for r in self.tables["fact_document"].dicts()}
        self._docs_by_id = {r["doc_id"]: r for r in self.tables["fact_document"].dicts()}
        self._by_case: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
        for name in CASE_CHILD_TABLES:
            for r in self.tables[name].dicts():
                self._by_case[r["case_id"]][name].append(r)
        self._snapshots: dict[tuple, bytes] = {}
        self._lock = threading.Lock()

    # ---------- directory ----------
    def users(self) -> list[dict[str, Any]]:
        out = []
        for u in self._users.values():
            role = role_for_group(u["entra_group"])
            out.append({**u, "access": role.description, "documents": role.documents})
        return out

    def principal(self, user_id: str) -> Principal | None:
        u = self._users.get(user_id)
        if u is None:
            return None
        return Principal(u["user_id"], u["full_name"], u["job_title"], u["entra_group"], role_for_group(u["entra_group"]))

    # ---------- unfiltered lookups (for the sync, which assigns access metadata) ----------
    def case(self, case_id: str) -> dict[str, Any] | None:
        return self._cases.get(case_id)

    def catalogue_entry(self, file_name: str) -> dict[str, Any] | None:
        return self._docs_by_file.get(file_name)

    def catalogue_by_id(self, doc_id: str) -> dict[str, Any] | None:
        return self._docs_by_id.get(doc_id)

    def case_names(self, case_id: str) -> list[str]:
        """Names a genuine document of this case would mention: its mark and the infringer, in English and Arabic."""
        c = self._cases.get(case_id)
        if c is None:
            return []
        mark = self._marks.get(c["mark_id"], {})
        infringer = self._infringers.get(c["infringer_id"], {})
        names = [mark.get("mark_name"), mark.get("mark_name_ar"), infringer.get("infringer_name_en"),
                 infringer.get("infringer_name_ar")]
        return [n for n in names if n]

    # ---------- filtered access ----------
    def visible_case(self, principal: Principal, case_id: str) -> dict[str, Any] | None:
        r = self._cases.get(case_id)
        return r if r is not None and principal.sees_group(r["access_group"]) else None

    def case_summary(self, principal: Principal, case_id: str) -> dict[str, Any] | None:
        r = self.visible_case(principal, case_id)
        if r is None:
            return None
        children = self._by_case.get(case_id, {})
        invoices = children.get("fact_invoice", [])
        by_cat = Counter()
        for inv in invoices:
            by_cat[inv["category"]] += inv["amount_aed"] or 0
        keep = ("case_id", "title", "case_type", "country", "court_name", "court_id", "status", "stage", "outcome",
                "opened_date", "closed_date", "priority", "risk_rating", "mark_name", "infringer_name", "infringer_type",
                "lead_counsel", "external_firm", "source_channel", "currency", "claim_amount_local", "claim_amount_aed",
                "awarded_amount_local", "awarded_amount_aed", "settlement_amount_local", "settlement_amount_aed",
                "recovered_amount_local", "recovered_amount_aed", "next_hearing_date", "next_action", "next_action_due",
                "last_action_date", "days_open", "language", "sensitivity")
        summary: dict[str, Any] = {k: r.get(k) for k in keep}
        summary["timeline"] = [
            {k: e[k] for k in ("event_date", "event_type", "external_fees_aed")}
            for e in sorted(children.get("fact_case_event", []), key=lambda e: (e["event_date"], e["event_id"]))
        ]
        summary["invoices"] = {"count": len(invoices), "total_aed": sum(by_cat.values()), "by_category_aed": dict(by_cat)}
        if principal.sees_documents:
            summary["documents_on_file"] = [
                {k: d[k] for k in ("doc_id", "doc_type", "language", "doc_date", "title")}
                for d in sorted(children.get("fact_document", []), key=lambda d: (d["doc_date"] or "", d["doc_id"]))
            ]
        else:
            summary["documents_on_file"] = "not available for this user's role"
        return summary

    def connect(self, principal: Principal) -> sqlite3.Connection:
        data = self._snapshot(principal)
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        conn.deserialize(data)
        today = self.demo_today.isoformat()
        for name in ("reporting_date", "demo_today"):  # demo_today kept as an alias for older queries
            conn.create_function(name, 0, lambda: today, deterministic=True)
        conn.set_authorizer(_read_only_authorizer)
        return conn

    def query(self, principal: Principal, sql: str, max_rows: int = 200, time_limit: float = 3.0) -> dict[str, Any]:
        sql = sql.strip().rstrip(";").strip()
        if not sql:
            raise QueryError("Empty query.")
        conn = self.connect(principal)
        deadline = time.monotonic() + time_limit
        conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
        try:
            cur = conn.execute(sql)
            if cur.description is None:
                raise QueryError("Only SELECT queries are allowed.")
            columns = [d[0] for d in cur.description]
            rows = cur.fetchmany(max_rows + 1)
        except (sqlite3.Error, sqlite3.Warning) as e:
            msg = str(e)
            if "interrupted" in msg:
                msg = "The query took too long. Aggregate in SQL or add filters."
            elif "not authorized" in msg:
                msg = "Only read-only SELECT queries are allowed."
            raise QueryError(msg) from None
        finally:
            conn.close()
        return {
            "columns": columns,
            "rows": [list(r) for r in rows[:max_rows]],
            "row_count": min(len(rows), max_rows),
            "truncated": len(rows) > max_rows,
        }

    # ---------- snapshots ----------
    def _snapshot(self, principal: Principal) -> bytes:
        key = principal.scope_key
        with self._lock:
            data = self._snapshots.get(key)
            if data is None:
                data = self._snapshots[key] = self._build_snapshot(principal)
            return data

    def _build_snapshot(self, principal: Principal) -> bytes:
        visible = {cid for cid, r in self._cases.items() if principal.sees_group(r["access_group"])}
        conn = sqlite3.connect(":memory:")
        try:
            for name, table in self.tables.items():
                if name == "fact_document" and not principal.sees_documents:
                    continue  # object-level security: the table does not exist for this role
                rows = self._visible_rows(name, table, principal, visible)
                cols = ", ".join(f'"{c}" {t}' for c, t in zip(table.columns, table.types))
                conn.execute(f'CREATE TABLE "{name}" ({cols})')
                conn.executemany(f'INSERT INTO "{name}" VALUES ({", ".join("?" * len(table.columns))})', rows)
            conn.commit()
            return conn.serialize()
        finally:
            conn.close()

    def _visible_rows(self, name: str, table: Table, principal: Principal, visible: set[str]) -> list[tuple]:
        cols = table.columns
        if name == "fact_case":
            i = cols.index("access_group")
            return [r for r in table.rows if principal.sees_group(r[i])]
        if name in CASE_CHILD_TABLES:
            i = cols.index("case_id")
            return [r for r in table.rows if r[i] in visible]
        if name in COUNTRY_TABLES:
            i = cols.index("country")
            return [r for r in table.rows if principal.sees_country(r[i])]
        if name == "dim_infringer":
            return self._infringer_rows(table, visible)
        return list(table.rows)

    def _infringer_rows(self, table: Table, visible: set[str]) -> list[tuple]:
        """Infringers with at least one visible case; counts recomputed over the visible cases only."""
        counts: Counter[str] = Counter()
        first: dict[str, str] = {}
        for cid in visible:
            c = self._cases[cid]
            counts[c["infringer_id"]] += 1
            first[c["infringer_id"]] = min(first.get(c["infringer_id"], c["opened_date"]), c["opened_date"])
        idx = {c: table.columns.index(c) for c in ("infringer_id", "case_count", "repeat_offender", "first_seen")}
        out = []
        for row in table.rows:
            inf = row[idx["infringer_id"]]
            if inf not in counts:
                continue
            row = list(row)
            row[idx["case_count"]] = counts[inf]
            row[idx["repeat_offender"]] = int(counts[inf] >= 2)
            row[idx["first_seen"]] = first[inf]
            out.append(tuple(row))
        return out
