"""SQLite store for the case records (data/records/records.sqlite), with the append-only, hash-chained audit trail.

Unlike the document index, this is not derived data: it is what users entered, so it is never rebuilt or migrated
silently. The audit trail cannot be edited through SQLite (triggers refuse UPDATE and DELETE), and each entry's hash
covers its content and the previous entry's hash, so a changed, removed or reordered entry shows up in
``verify_chain`` even if someone edits the file directly.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .errors import RecordError

SCHEMA_VERSION = "1"
GENESIS = "0" * 64
SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

-- Current value of every case field a user has changed (JSON); the pack's CSV holds the rest.
CREATE TABLE IF NOT EXISTS case_fields (
    case_id     TEXT NOT NULL,
    field       TEXT NOT NULL,
    value       TEXT,
    updated_at  TEXT NOT NULL,
    updated_by  TEXT NOT NULL,
    PRIMARY KEY (case_id, field)
);

-- Evidence and supporting documents. Files live beside the database, named by their SHA-256; rows are never deleted.
CREATE TABLE IF NOT EXISTS evidence (
    seq               INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id           TEXT NOT NULL,
    category          TEXT NOT NULL,
    title             TEXT NOT NULL,
    notes             TEXT,
    captured_on       TEXT,              -- when the photo was taken or the document is dated
    location          TEXT,              -- where it was found: store, address, marketplace or web address
    file_name         TEXT NOT NULL,     -- as uploaded; shown, never used as a path
    content_type      TEXT NOT NULL,
    size_bytes        INTEGER NOT NULL,
    sha256            TEXT NOT NULL,
    uploaded_by       TEXT NOT NULL,
    uploaded_at       TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'Active',   -- Active | Withdrawn
    withdrawn_by      TEXT,
    withdrawn_at      TEXT,
    withdrawn_reason  TEXT
);
CREATE INDEX IF NOT EXISTS ix_evidence_case ON evidence(case_id, seq);
CREATE TRIGGER IF NOT EXISTS evidence_is_kept BEFORE DELETE ON evidence
BEGIN SELECT RAISE(ABORT, 'evidence is never deleted; withdraw it instead'); END;

-- Follow-ups: a deadline on a case (e.g. a store given 30 days to remove products), its owner and the decision.
CREATE TABLE IF NOT EXISTS follow_ups (
    seq            INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id        TEXT NOT NULL,
    kind           TEXT NOT NULL,
    title          TEXT NOT NULL,
    details        TEXT,
    owner_id       TEXT NOT NULL,
    start_date     TEXT NOT NULL,
    period_days    INTEGER,
    due_date       TEXT NOT NULL,
    remind_days    INTEGER NOT NULL,
    status         TEXT NOT NULL DEFAULT 'Open',        -- Open | Done | Cancelled
    decision       TEXT,
    decision_note  TEXT,
    resolved_by    TEXT,
    resolved_at    TEXT,
    created_by     TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_follow_ups_case ON follow_ups(case_id, status);

-- In-app notifications (and the e-mail copy). One row per recipient; dedupe_key stops a reminder being sent twice.
CREATE TABLE IF NOT EXISTS notifications (
    seq             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT NOT NULL,
    case_id         TEXT NOT NULL,
    kind            TEXT NOT NULL,       -- follow_up | next_action | hearing | assigned
    stage           TEXT NOT NULL,       -- upcoming | due | overdue | today | assigned
    title           TEXT NOT NULL,
    body            TEXT NOT NULL,
    link            TEXT NOT NULL,
    ref_id          TEXT,
    due_date        TEXT,
    dedupe_key      TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    read_at         TEXT,
    emailed_at      TEXT,
    email_attempts  INTEGER NOT NULL DEFAULT 0,
    UNIQUE (user_id, dedupe_key)
);
CREATE INDEX IF NOT EXISTS ix_notifications_user ON notifications(user_id, seq);

-- Cases registered in this app (the pack's tracker holds the rest), as first recorded (JSON). Later changes go to
-- case_fields like any other case's. A registered case is never deleted: it is closed, or withdrawn as an outcome.
CREATE TABLE IF NOT EXISTS registered_cases (
    seq            INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id        TEXT NOT NULL UNIQUE,
    data           TEXT NOT NULL,
    registered_by  TEXT NOT NULL,
    registered_at  TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS registered_cases_are_kept BEFORE DELETE ON registered_cases
BEGIN SELECT RAISE(ABORT, 'registered cases are never deleted; close them instead'); END;

-- Infringers first recorded when a case was registered (the pack's dim_infringer holds the rest).
CREATE TABLE IF NOT EXISTS registered_infringers (
    seq            INTEGER PRIMARY KEY AUTOINCREMENT,
    infringer_id   TEXT NOT NULL UNIQUE,
    data           TEXT NOT NULL,
    registered_by  TEXT NOT NULL,
    registered_at  TEXT NOT NULL
);

-- Visual trademark comparisons: the registered mark against the sign on the infringing product. A new assessment
-- supersedes the last one; none is deleted.
CREATE TABLE IF NOT EXISTS mark_comparisons (
    seq              INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id          TEXT NOT NULL,
    mark_id          TEXT NOT NULL,
    evidence_id      TEXT,                -- the photo of the infringing product compared, if any
    infringing_sign  TEXT NOT NULL,       -- the name or sign as it appears on the product
    visual           TEXT NOT NULL,
    phonetic         TEXT NOT NULL,
    conceptual       TEXT NOT NULL,
    goods            TEXT NOT NULL,
    overall          TEXT NOT NULL,       -- likelihood of confusion
    notes            TEXT,
    word_similarity  REAL,
    sounds_alike     INTEGER,
    assessed_by      TEXT NOT NULL,
    assessed_at      TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'Current'   -- Current | Superseded
);
CREATE INDEX IF NOT EXISTS ix_comparisons_case ON mark_comparisons(case_id, seq);
CREATE TRIGGER IF NOT EXISTS mark_comparisons_are_kept BEFORE DELETE ON mark_comparisons
BEGIN SELECT RAISE(ABORT, 'comparisons are never deleted; record a new one instead'); END;

-- The audit trail: one entry per material change, global sequence, each entry hash-chained to the one before.
CREATE TABLE IF NOT EXISTS audit_log (
    seq          INTEGER PRIMARY KEY,
    at           TEXT NOT NULL,          -- UTC, ISO 8601
    case_id      TEXT NOT NULL,
    actor_id     TEXT NOT NULL,
    actor_name   TEXT NOT NULL,
    actor_role   TEXT NOT NULL,
    action       TEXT NOT NULL,
    summary      TEXT NOT NULL,
    changes      TEXT NOT NULL,          -- JSON list of {field, label, old, new}
    reason       TEXT,
    ref_type     TEXT,                   -- evidence | follow_up | comparison, when the entry is about one
    ref_id       TEXT,
    prev_hash    TEXT NOT NULL,
    entry_hash   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_audit_case ON audit_log(case_id, seq);
CREATE TRIGGER IF NOT EXISTS audit_log_no_update BEFORE UPDATE ON audit_log
BEGIN SELECT RAISE(ABORT, 'the audit trail is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_log_no_delete BEFORE DELETE ON audit_log
BEGIN SELECT RAISE(ABORT, 'the audit trail is append-only'); END;
"""
# What an entry's hash covers: everything except the hash itself.
HASHED = ("seq", "at", "case_id", "actor_id", "actor_name", "actor_role", "action", "summary", "changes", "reason",
          "ref_type", "ref_id", "prev_hash")

ID_PREFIX = {"evidence": ("EVD", 5), "follow_up": ("FU", 5), "audit": ("AUD", 6), "comparison": ("CMP", 5)}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def format_id(kind: str, seq: int) -> str:
    prefix, width = ID_PREFIX[kind]
    return f"{prefix}-{seq:0{width}d}"


def parse_id(kind: str, text: str) -> int:
    prefix, _ = ID_PREFIX[kind]
    m = re.fullmatch(rf"{prefix}-(\d{{1,9}})", (text or "").strip().upper())
    if not m:
        raise RecordError(f"There is no {kind.replace('_', '-')} {text}.", 404)
    return int(m.group(1))


def entry_hash(entry: dict[str, Any]) -> str:
    payload = json.dumps({k: entry[k] for k in HASHED}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class RecordStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = self.connect()
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(SCHEMA)
            found = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
            if found is None:
                conn.execute("INSERT INTO meta (key, value) VALUES ('schema_version', ?)", (SCHEMA_VERSION,))
            elif found["value"] != SCHEMA_VERSION:
                raise RuntimeError(f"{path} has schema {found['value']}, this version expects {SCHEMA_VERSION}; "
                                   "it holds users' records, so it is not rebuilt automatically")
        finally:
            conn.close()

    def connect(self) -> sqlite3.Connection:
        # Autocommit mode: transactions are opened explicitly (BEGIN IMMEDIATE), so writers queue for the lock up front.
        conn = sqlite3.connect(self.path, timeout=15, isolation_level=None, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 15000")
        return conn

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """One write transaction, holding SQLite's write lock from the start: audit entries get gap-free numbers."""
        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            conn.execute("COMMIT")
        finally:
            conn.close()

    # ---------- audit trail ----------
    @staticmethod
    def append_audit(conn: sqlite3.Connection, *, case_id: str, actor_id: str, actor_name: str, actor_role: str,
                     action: str, summary: str, changes: list[dict[str, Any]], reason: str | None = None,
                     ref_type: str | None = None, ref_id: str | None = None) -> dict[str, Any]:
        if not conn.in_transaction:
            raise RuntimeError("audit entries are written inside a transaction")
        head = conn.execute("SELECT seq, entry_hash FROM audit_log ORDER BY seq DESC LIMIT 1").fetchone()
        entry: dict[str, Any] = {
            "seq": head["seq"] + 1 if head else 1, "at": utc_now(), "case_id": case_id, "actor_id": actor_id,
            "actor_name": actor_name, "actor_role": actor_role, "action": action, "summary": summary,
            "changes": json.dumps(changes, ensure_ascii=False, sort_keys=True, default=str), "reason": reason,
            "ref_type": ref_type, "ref_id": ref_id, "prev_hash": head["entry_hash"] if head else GENESIS,
        }
        entry["entry_hash"] = entry_hash(entry)
        cols = (*HASHED, "entry_hash")
        conn.execute(f"INSERT INTO audit_log ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                     [entry[c] for c in cols])
        # the head is kept apart too, so entries removed from the end of the chain are noticed as well
        conn.execute("INSERT INTO meta (key, value) VALUES ('audit_head', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                     (f"{entry['seq']}:{entry['entry_hash']}",))
        return entry

    def verify_chain(self) -> dict[str, Any]:
        """Recompute every audit entry's hash and its link to the entry before it."""
        def broken(seq: int, problem: str) -> dict[str, Any]:
            return {"ok": False, "entries": checked, "first_bad": format_id("audit", seq), "problem": problem}

        checked, prev, expected = 0, GENESIS, 1
        with self.read() as conn:
            conn.execute("BEGIN")  # one read snapshot for the entries and the head, even while others write
            for row in conn.execute("SELECT * FROM audit_log ORDER BY seq"):
                e = dict(row)
                if e["seq"] != expected:
                    return broken(expected, "an entry is missing")
                if e["prev_hash"] != prev:
                    return broken(e["seq"], "it does not follow on from the entry before it")
                if entry_hash(e) != e["entry_hash"]:
                    return broken(e["seq"], "its content changed after it was written")
                prev, expected, checked = e["entry_hash"], expected + 1, checked + 1
            head = conn.execute("SELECT value FROM meta WHERE key = 'audit_head'").fetchone()
            conn.execute("COMMIT")
        if head is not None and head["value"] != f"{checked}:{prev}":
            return broken(checked + 1, "entries are missing from the end of the trail")
        return {"ok": True, "entries": checked, "head": prev}
