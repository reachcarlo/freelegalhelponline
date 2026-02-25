"""SQLite storage for the Employee Help knowledge base."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from employee_help.storage.models import (
    Chunk,
    ContentType,
    CrawlRun,
    CrawlStatus,
    Document,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS crawl_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    summary TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    crawl_run_id INTEGER NOT NULL REFERENCES crawl_runs(id),
    source_url TEXT NOT NULL,
    title TEXT NOT NULL,
    content_type TEXT NOT NULL,
    raw_content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    last_modified TEXT,
    language TEXT NOT NULL DEFAULT 'en'
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    heading_path TEXT NOT NULL DEFAULT '',
    token_count INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    embedding BLOB,
    metadata TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_documents_content_hash ON documents(content_hash);
CREATE INDEX IF NOT EXISTS idx_documents_source_url ON documents(source_url);
CREATE INDEX IF NOT EXISTS idx_chunks_content_hash ON chunks(content_hash);
CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);
"""


class Storage:
    """SQLite-backed storage for crawl runs, documents, and chunks."""

    def __init__(self, db_path: str | Path = "data/employee_help.db") -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Storage:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ── Crawl Runs ──────────────────────────────────────────────

    def create_run(self) -> CrawlRun:
        run = CrawlRun()
        cur = self._conn.execute(
            "INSERT INTO crawl_runs (started_at, status, summary) VALUES (?, ?, ?)",
            (run.started_at.isoformat(), run.status.value, json.dumps(run.summary)),
        )
        self._conn.commit()
        run.id = cur.lastrowid
        return run

    def complete_run(self, run_id: int, status: CrawlStatus, summary: dict) -> None:
        self._conn.execute(
            "UPDATE crawl_runs SET completed_at = ?, status = ?, summary = ? WHERE id = ?",
            (datetime.now(tz=UTC).isoformat(), status.value, json.dumps(summary), run_id),
        )
        self._conn.commit()

    def get_run_summary(self, run_id: int) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM crawl_runs WHERE id = ?", (run_id,)
        ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
            "status": row["status"],
            "summary": json.loads(row["summary"]),
        }

    def get_latest_run(self) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM crawl_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
            "status": row["status"],
            "summary": json.loads(row["summary"]),
        }

    # ── Documents ───────────────────────────────────────────────

    def get_document_by_url(self, source_url: str) -> Document | None:
        row = self._conn.execute(
            "SELECT * FROM documents WHERE source_url = ? ORDER BY id DESC LIMIT 1",
            (source_url,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_document(row)

    def upsert_document(self, doc: Document) -> tuple[Document, bool]:
        """Insert or update a document. Returns (document, is_new_or_changed).

        If a document with the same source_url exists and has the same
        content_hash, it is unchanged — returns (existing, False).
        Otherwise inserts a new row and returns (new_doc, True).
        """
        existing = self.get_document_by_url(doc.source_url)
        if existing and existing.content_hash == doc.content_hash:
            return existing, False

        # Delete old document and its chunks if URL exists with different content
        if existing and existing.id is not None:
            self._conn.execute("DELETE FROM chunks WHERE document_id = ?", (existing.id,))
            self._conn.execute("DELETE FROM documents WHERE id = ?", (existing.id,))

        cur = self._conn.execute(
            """INSERT INTO documents
               (crawl_run_id, source_url, title, content_type, raw_content,
                content_hash, retrieved_at, last_modified, language)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                doc.crawl_run_id,
                doc.source_url,
                doc.title,
                doc.content_type.value,
                doc.raw_content,
                doc.content_hash,
                doc.retrieved_at.isoformat(),
                doc.last_modified,
                doc.language,
            ),
        )
        self._conn.commit()
        doc.id = cur.lastrowid
        return doc, True

    def get_all_documents(self) -> list[Document]:
        rows = self._conn.execute("SELECT * FROM documents ORDER BY id").fetchall()
        return [self._row_to_document(row) for row in rows]

    def get_document_count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) as cnt FROM documents").fetchone()
        return row["cnt"]

    # ── Chunks ──────────────────────────────────────────────────

    def insert_chunks(self, chunks: list[Chunk]) -> None:
        self._conn.executemany(
            """INSERT INTO chunks
               (document_id, chunk_index, content, heading_path,
                token_count, content_hash, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    c.document_id,
                    c.chunk_index,
                    c.content,
                    c.heading_path,
                    c.token_count,
                    c.content_hash,
                    json.dumps(c.metadata),
                )
                for c in chunks
            ],
        )
        self._conn.commit()

    def get_chunks_for_document(self, document_id: int) -> list[Chunk]:
        rows = self._conn.execute(
            "SELECT * FROM chunks WHERE document_id = ? ORDER BY chunk_index",
            (document_id,),
        ).fetchall()
        return [self._row_to_chunk(row) for row in rows]

    def get_chunk_count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) as cnt FROM chunks").fetchone()
        return row["cnt"]

    def get_all_chunks(self) -> list[Chunk]:
        rows = self._conn.execute(
            "SELECT * FROM chunks ORDER BY document_id, chunk_index"
        ).fetchall()
        return [self._row_to_chunk(row) for row in rows]

    # ── Private helpers ─────────────────────────────────────────

    @staticmethod
    def _row_to_document(row: sqlite3.Row) -> Document:
        return Document(
            id=row["id"],
            crawl_run_id=row["crawl_run_id"],
            source_url=row["source_url"],
            title=row["title"],
            content_type=ContentType(row["content_type"]),
            raw_content=row["raw_content"],
            content_hash=row["content_hash"],
            retrieved_at=datetime.fromisoformat(row["retrieved_at"]),
            last_modified=row["last_modified"],
            language=row["language"],
        )

    @staticmethod
    def _row_to_chunk(row: sqlite3.Row) -> Chunk:
        return Chunk(
            id=row["id"],
            document_id=row["document_id"],
            chunk_index=row["chunk_index"],
            content=row["content"],
            heading_path=row["heading_path"],
            token_count=row["token_count"],
            content_hash=row["content_hash"],
            metadata=json.loads(row["metadata"]),
        )
