"""The document index: catalogue of synced files plus a full-text index of their passages.

SQLite FTS5 with BM25 ranking keeps the demo self-contained. Every passage carries the
access group of its case, and every search filters on the caller's groups inside the SQL,
so a user can never retrieve text from a case they cannot open. The production equivalent
is an Azure AI Search index with the same fields and a security filter on access_group.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from ..security import Principal
from ..textproc import index_text, query_terms
from .chunker import Passage

SCHEMA_VERSION = 3  # bump when SCHEMA changes; the index is derived data and is rebuilt on mismatch
SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    doc_id        TEXT PRIMARY KEY,
    source        TEXT NOT NULL,
    source_key    TEXT NOT NULL,
    file_name     TEXT NOT NULL,
    case_id       TEXT NOT NULL,
    doc_type      TEXT,
    language      TEXT,
    access_group  TEXT NOT NULL,
    sensitivity   TEXT,
    library_path  TEXT NOT NULL,
    version       TEXT,
    modified_at   TEXT,
    content_sha   TEXT,
    extraction    TEXT,               -- 'text' (the file's own text) or 'ocr' (a scan: text recognised from page images)
    ocr_confidence REAL,              -- mean recognition confidence, 0-1, for scans
    pages         INTEGER,
    index_status  TEXT NOT NULL,
    skip_reason   TEXT,
    passages      INTEGER NOT NULL DEFAULT 0,
    indexed_at    TEXT NOT NULL,
    UNIQUE (source, source_key)
);
CREATE TABLE IF NOT EXISTS passages (
    passage_id    INTEGER PRIMARY KEY,
    doc_id        TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    seq           INTEGER NOT NULL,
    section       TEXT NOT NULL,
    blocks_json   TEXT NOT NULL,
    case_id       TEXT NOT NULL,
    access_group  TEXT NOT NULL,
    language      TEXT,
    doc_type      TEXT
);
CREATE INDEX IF NOT EXISTS ix_passages_doc ON passages(doc_id, seq);
CREATE INDEX IF NOT EXISTS ix_passages_case ON passages(case_id);
CREATE INDEX IF NOT EXISTS ix_documents_file ON documents(file_name);
CREATE INDEX IF NOT EXISTS ix_documents_sha ON documents(content_sha);
CREATE VIRTUAL TABLE IF NOT EXISTS passages_fts USING fts5(body, tokenize = 'porter unicode61 remove_diacritics 2');
CREATE TABLE IF NOT EXISTS sync_state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


@dataclass(frozen=True)
class DocumentRecord:
    doc_id: str
    source: str
    source_key: str
    file_name: str
    case_id: str
    doc_type: str | None
    language: str | None
    access_group: str
    sensitivity: str | None
    library_path: str
    version: str | None
    modified_at: str | None
    content_sha: str | None = None
    extraction: str | None = None
    ocr_confidence: float | None = None
    pages: int | None = None


@dataclass(frozen=True)
class Hit:
    passage_id: int
    doc_id: str
    seq: int
    section: str
    blocks: tuple[str, ...]
    file_name: str
    case_id: str
    doc_type: str | None
    language: str | None
    library_path: str
    sensitivity: str | None
    extraction: str | None = None
    score: float = 0.0

    @property
    def source(self) -> str:
        """Stable, unique identifier for this passage (what Claude's citations point back to)."""
        return f"{self.library_path}#p{self.seq}"


_HIT_COLUMNS = ("p.passage_id, p.doc_id, p.seq, p.section, p.blocks_json, d.file_name, d.case_id, d.doc_type, "
                "d.language, d.library_path, d.sensitivity, d.extraction")
_HIT_WIDTH = 12


def _hit(row: tuple, score: float = 0.0) -> Hit:
    return Hit(row[0], row[1], row[2], row[3], tuple(json.loads(row[4])), *row[5:_HIT_WIDTH], score=score)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class DocumentIndex:
    def __init__(self, path: Path, readonly: bool = False):
        self.path = Path(path)
        self.readonly = readonly
        if not readonly:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with closing(self._connect()) as conn:
                if conn.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
                    for table in ("passages_fts", "passages", "documents", "sync_state"):
                        conn.execute(f"DROP TABLE IF EXISTS {table}")
                conn.executescript(SCHEMA)
                conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def _connect(self) -> sqlite3.Connection:
        if self.readonly:
            conn = sqlite3.connect(f"{self.path.resolve().as_uri()}?mode=ro", uri=True, check_same_thread=False)
        else:
            conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @property
    def exists(self) -> bool:
        return self.path.is_file()

    # ---------- writing (sync) ----------
    def upsert(self, record: DocumentRecord, passages: Iterable[Passage], status: str, skip_reason: str | None = None) -> int:
        passages = list(passages)
        with closing(self._connect()) as conn, conn:
            # Replace whatever was there before: same file (source key) or same catalogue document (doc_id).
            for (old_id,) in conn.execute(
                "SELECT doc_id FROM documents WHERE (source = ? AND source_key = ?) OR doc_id = ?",
                (record.source, record.source_key, record.doc_id),
            ).fetchall():
                self._delete_doc(conn, old_id)
                conn.execute("DELETE FROM documents WHERE doc_id = ?", (old_id,))
            conn.execute(
                "INSERT INTO documents (doc_id, source, source_key, file_name, case_id, doc_type, language, access_group,"
                " sensitivity, library_path, version, modified_at, content_sha, extraction, ocr_confidence, pages,"
                " index_status, skip_reason, passages, indexed_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (record.doc_id, record.source, record.source_key, record.file_name, record.case_id, record.doc_type,
                 record.language, record.access_group, record.sensitivity, record.library_path, record.version,
                 record.modified_at, record.content_sha, record.extraction, record.ocr_confidence, record.pages,
                 status, skip_reason, len(passages), _now()),
            )
            for p in passages:
                cur = conn.execute(
                    "INSERT INTO passages (doc_id, seq, section, blocks_json, case_id, access_group, language, doc_type)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (record.doc_id, p.seq, p.section, json.dumps(p.blocks, ensure_ascii=False), record.case_id,
                     record.access_group, record.language, record.doc_type),
                )
                body = index_text(f"{p.section}\n{p.text}\n{record.file_name}")
                conn.execute("INSERT INTO passages_fts (rowid, body) VALUES (?, ?)", (cur.lastrowid, body))
        return len(passages)

    def delete(self, source: str, source_key: str) -> bool:
        with closing(self._connect()) as conn, conn:
            row = conn.execute("SELECT doc_id FROM documents WHERE source = ? AND source_key = ?", (source, source_key)).fetchone()
            if row is None:
                return False
            self._delete_doc(conn, row[0])
            conn.execute("DELETE FROM documents WHERE doc_id = ?", (row[0],))
            return True

    @staticmethod
    def _delete_doc(conn: sqlite3.Connection, doc_id: str) -> None:
        ids = [r[0] for r in conn.execute("SELECT passage_id FROM passages WHERE doc_id = ?", (doc_id,))]
        conn.executemany("DELETE FROM passages_fts WHERE rowid = ?", [(i,) for i in ids])
        conn.execute("DELETE FROM passages WHERE doc_id = ?", (doc_id,))

    def duplicate_of(self, content_sha: str, source: str, source_key: str) -> str | None:
        """File name of an already-indexed document with identical content (other than this file itself)."""
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT file_name FROM documents WHERE content_sha = ? AND index_status LIKE 'Indexed%'"
                " AND NOT (source = ? AND source_key = ?) LIMIT 1", (content_sha, source, source_key)).fetchone()
            return row[0] if row else None

    def versions(self, source: str) -> dict[str, tuple[str | None, str]]:
        """source_key -> (version, index_status) for everything previously synced from ``source``."""
        with closing(self._connect()) as conn:
            return {k: (v, s) for k, v, s in conn.execute(
                "SELECT source_key, version, index_status FROM documents WHERE source = ?", (source,))}

    def get_state(self, key: str) -> str | None:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT value FROM sync_state WHERE key = ?", (key,)).fetchone()
            return row[0] if row else None

    def set_state(self, key: str, value: str | None) -> None:
        with closing(self._connect()) as conn, conn:
            if value is None:
                conn.execute("DELETE FROM sync_state WHERE key = ?", (key,))
            else:
                conn.execute("INSERT INTO sync_state (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                             (key, value))

    # ---------- reading (assistant) ----------
    def search(self, principal: Principal, query: str, *, case_id: str | None = None, doc_type: str | None = None,
               language: str | None = None, limit: int = 6) -> list[Hit]:
        if not principal.sees_documents or not principal.role.case_groups or not self.exists:
            return []
        groups = sorted(principal.role.case_groups)
        where = [f"p.access_group IN ({', '.join('?' * len(groups))})"]
        params: list[Any] = list(groups)
        for column, value in (("p.case_id", case_id), ("p.doc_type", doc_type), ("p.language", language)):
            if value:
                where.append(f"{column} = ?")
                params.append(value)
        terms = query_terms(query)
        with closing(self._connect()) as conn:
            if terms:
                match = " OR ".join(f'"{t}"' for t in terms)
                rows = conn.execute(
                    f"SELECT {_HIT_COLUMNS}, bm25(passages_fts) AS score FROM passages_fts"
                    " JOIN passages p ON p.passage_id = passages_fts.rowid JOIN documents d ON d.doc_id = p.doc_id"
                    f" WHERE passages_fts MATCH ? AND {' AND '.join(where)} ORDER BY score LIMIT ?",
                    [match, *params, limit],
                ).fetchall()
                if rows:
                    return [_hit(r[:_HIT_WIDTH], r[_HIT_WIDTH]) for r in rows]
            if not (case_id or doc_type):
                return []
            # No keyword hit, but the caller scoped the search: return the scoped passages in reading order.
            rows = conn.execute(
                f"SELECT {_HIT_COLUMNS} FROM passages p JOIN documents d ON d.doc_id = p.doc_id"
                f" WHERE {' AND '.join(where)} ORDER BY d.file_name, p.seq LIMIT ?",
                [*params, limit],
            ).fetchall()
            return [_hit(r) for r in rows]

    def document(self, principal: Principal, file_name: str) -> tuple[dict[str, Any], list[Hit]] | None:
        """A whole indexed document, if the principal may open it."""
        if not principal.sees_documents or not self.exists:
            return None
        meta = self.document_meta(principal, file_name)
        if meta is None or not meta["index_status"].startswith("Indexed"):
            return None
        with closing(self._connect()) as conn:
            rows = conn.execute(
                f"SELECT {_HIT_COLUMNS} FROM passages p JOIN documents d ON d.doc_id = p.doc_id WHERE p.doc_id = ? ORDER BY p.seq",
                (meta["doc_id"],)).fetchall()
        return meta, [_hit(r) for r in rows]

    _META_COLUMNS = ("doc_id", "file_name", "case_id", "doc_type", "language", "access_group", "sensitivity",
                     "library_path", "index_status", "skip_reason", "extraction", "ocr_confidence", "pages", "content_sha")

    def document_meta(self, principal: Principal, file_name_or_doc_id: str) -> dict[str, Any] | None:
        """A synced file's catalogue row (any status), if the principal may open its case's documents."""
        if not principal.sees_documents or not self.exists:
            return None
        with closing(self._connect()) as conn:
            doc = conn.execute(
                f"SELECT {', '.join(self._META_COLUMNS)} FROM documents WHERE doc_id = ? OR file_name = ?"
                " ORDER BY doc_id = ? DESC LIMIT 1", (file_name_or_doc_id, file_name_or_doc_id, file_name_or_doc_id)).fetchone()
        if doc is None or not doc[5] or not principal.sees_group(doc[5]):
            return None
        return dict(zip(self._META_COLUMNS, doc))

    def case_files(self, case_id: str) -> list[dict[str, Any]]:
        """Every synced file tied to this case, searchable or not (skipped files explain why)."""
        if not self.exists or not case_id:
            return []
        with closing(self._connect()) as conn:
            cur = conn.execute(
                "SELECT doc_id, file_name, doc_type, language, index_status, skip_reason, extraction, ocr_confidence"
                " FROM documents WHERE case_id = ? ORDER BY file_name", (case_id,))
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur]

    def catalogue(self) -> list[dict[str, Any]]:
        if not self.exists:
            return []
        with closing(self._connect()) as conn:
            cur = conn.execute("SELECT * FROM documents ORDER BY case_id, file_name")
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur]

    def stats(self) -> dict[str, Any]:
        if not self.exists:
            return {"documents": 0, "indexed": 0, "passages": 0}
        with closing(self._connect()) as conn:
            docs, indexed = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(index_status LIKE 'Indexed%'), 0) FROM documents").fetchone()
            passages = conn.execute("SELECT COUNT(*) FROM passages").fetchone()[0]
        return {"documents": docs, "indexed": indexed, "passages": passages}
