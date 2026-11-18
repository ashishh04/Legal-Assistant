"""SQLite store for sign-in (data/records/auth.sqlite): passwords, live sessions, the sign-in log, and the users the
platform administrator manages (people added, accounts disabled, and a log of what the administrator did).

Session tokens are never stored, only their SHA-256, so a copy of this file can't be used to take over a session.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS credentials (
    user_id        TEXT PRIMARY KEY,
    password_hash  TEXT NOT NULL,
    set_at         TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash     TEXT PRIMARY KEY,
    user_id        TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    last_seen_at   TEXT NOT NULL,
    expires_at     TEXT NOT NULL,
    persistent     INTEGER NOT NULL,    -- 1: "keep me signed in" (longer idle time, cookie survives the browser)
    ip             TEXT,
    user_agent     TEXT
);
CREATE INDEX IF NOT EXISTS ix_sessions_user ON sessions(user_id);
CREATE TABLE IF NOT EXISTS sign_ins (
    seq            INTEGER PRIMARY KEY AUTOINCREMENT,
    at             TEXT NOT NULL,
    user_id        TEXT,                -- the account, when the name given matched one
    login          TEXT NOT NULL,       -- what was typed (e-mail address or user id)
    ip             TEXT,
    ok             INTEGER NOT NULL,
    reason         TEXT
);
CREATE INDEX IF NOT EXISTS ix_sign_ins_user ON sign_ins(user_id, seq);

-- People the administrator added (the pack's dim_user holds the rest).
CREATE TABLE IF NOT EXISTS directory_users (
    user_id        TEXT PRIMARY KEY,
    full_name      TEXT NOT NULL,
    job_title      TEXT NOT NULL,
    team           TEXT NOT NULL,
    country        TEXT NOT NULL,
    entra_group    TEXT NOT NULL,
    email          TEXT NOT NULL UNIQUE COLLATE NOCASE,
    created_by     TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);
-- Accounts the administrator disabled: they can't sign in, own cases or receive reminders.
CREATE TABLE IF NOT EXISTS disabled_users (
    user_id        TEXT PRIMARY KEY,
    disabled_by    TEXT NOT NULL,
    disabled_at    TEXT NOT NULL
);
-- What the administrator did: users added and changed, passwords set, switches into another user's view.
CREATE TABLE IF NOT EXISTS admin_log (
    seq            INTEGER PRIMARY KEY AUTOINCREMENT,
    at             TEXT NOT NULL,
    admin_id       TEXT NOT NULL,
    action         TEXT NOT NULL,
    user_id        TEXT,
    detail         TEXT
);
"""
# Columns added after the first release, created on existing files.
ADDED_COLUMNS = {
    "credentials": [("temporary", "INTEGER NOT NULL DEFAULT 0")],  # 1: set by the administrator, to be changed
    "sessions": [("acting_as", "TEXT")],                           # the user the administrator switched into
}


class AuthStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(SCHEMA)
            for table, columns in ADDED_COLUMNS.items():
                have = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
                for name, decl in columns:
                    if name not in have:
                        conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=15, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            with conn:  # commit on success, roll back on error
                yield conn
        finally:
            conn.close()
