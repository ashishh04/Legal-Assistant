"""SQLite store for sign-in (data/records/auth.sqlite): users' own passwords, live sessions and the sign-in log.

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
"""


class AuthStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=15, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            with conn:  # commit on success, roll back on error
                yield conn
        finally:
            conn.close()
