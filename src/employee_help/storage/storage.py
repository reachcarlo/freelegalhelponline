"""SQLite storage for the Employee Help knowledge base."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from employee_help.storage.models import (
    Chunk,
    CitationLink,
    ContentCategory,
    ContentType,
    CrawlRun,
    CrawlStatus,
    Document,
    Source,
    SourceType,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    source_type TEXT NOT NULL DEFAULT 'agency',
    base_url TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS crawl_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER REFERENCES sources(id),
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    summary TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    crawl_run_id INTEGER NOT NULL REFERENCES crawl_runs(id),
    source_id INTEGER REFERENCES sources(id),
    source_url TEXT NOT NULL,
    title TEXT NOT NULL,
    content_type TEXT NOT NULL,
    raw_content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    last_modified TEXT,
    language TEXT NOT NULL DEFAULT 'en',
    content_category TEXT NOT NULL DEFAULT 'agency_guidance'
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
    metadata TEXT NOT NULL DEFAULT '{}',
    content_category TEXT NOT NULL DEFAULT 'agency_guidance',
    citation TEXT,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS citation_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_chunk_id INTEGER NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    cited_text TEXT NOT NULL,
    citation_type TEXT NOT NULL,
    reporter TEXT,
    volume TEXT,
    page TEXT,
    section TEXT,
    is_california INTEGER NOT NULL DEFAULT 0,
    target_chunk_id INTEGER REFERENCES chunks(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_citation_links_source ON citation_links(source_chunk_id);
CREATE INDEX IF NOT EXISTS idx_citation_links_target ON citation_links(target_chunk_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_citation_links_dedup
    ON citation_links(source_chunk_id, cited_text);

CREATE INDEX IF NOT EXISTS idx_documents_content_hash ON documents(content_hash);
CREATE INDEX IF NOT EXISTS idx_documents_source_url ON documents(source_url);
CREATE INDEX IF NOT EXISTS idx_documents_source_id ON documents(source_id);
CREATE INDEX IF NOT EXISTS idx_chunks_content_hash ON chunks(content_hash);
CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_content_category ON chunks(content_category);
CREATE INDEX IF NOT EXISTS idx_sources_slug ON sources(slug);
"""

# Migrations for upgrading from Phase 1 schema to Phase 1.5 schema.
# Each migration is idempotent — safe to run multiple times.
_MIGRATIONS = [
    # Add sources table
    """
    CREATE TABLE IF NOT EXISTS sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        slug TEXT NOT NULL UNIQUE,
        source_type TEXT NOT NULL DEFAULT 'agency',
        base_url TEXT NOT NULL,
        enabled INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    );
    """,
    # source_id on crawl_runs (nullable for backward compat)
    "ALTER TABLE crawl_runs ADD COLUMN source_id INTEGER REFERENCES sources(id);",
    # source_id on documents
    "ALTER TABLE documents ADD COLUMN source_id INTEGER REFERENCES sources(id);",
    # content_category on documents
    "ALTER TABLE documents ADD COLUMN content_category TEXT NOT NULL DEFAULT 'agency_guidance';",
    # content_category on chunks
    "ALTER TABLE chunks ADD COLUMN content_category TEXT NOT NULL DEFAULT 'agency_guidance';",
    # citation on chunks
    "ALTER TABLE chunks ADD COLUMN citation TEXT;",
    # is_active on chunks
    "ALTER TABLE chunks ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1;",
]


class Storage:
    """SQLite-backed storage for crawl runs, documents, and chunks."""

    def __init__(self, db_path: str | Path = "data/employee_help.db") -> None:
        self._db_path = Path(db_path)
        if str(self._db_path) != ":memory:":
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self) -> None:
        # First run migrations to handle upgrading from Phase 1 schema
        self.migrate()
        # Then create any missing tables/indexes (safe for fresh and migrated DBs)
        self._conn.executescript(_SCHEMA)

    def migrate(self) -> None:
        """Run schema migrations for upgrading from Phase 1 to Phase 1.5.

        Each migration is idempotent — safe to run on an already-migrated DB.
        """
        for migration in _MIGRATIONS:
            try:
                self._conn.execute(migration)
                self._conn.commit()
            except sqlite3.OperationalError as e:
                msg = str(e)
                # "duplicate column name" means migration already applied
                # "no such table" means fresh DB — tables will be created by _SCHEMA
                # "already exists" means table/index was already created
                if "duplicate column" in msg or "already exists" in msg or "no such table" in msg:
                    continue
                raise

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Storage:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ── Sources ──────────────────────────────────────────────────

    def create_source(self, source: Source) -> Source:
        cur = self._conn.execute(
            """INSERT INTO sources (name, slug, source_type, base_url, enabled, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                source.name,
                source.slug,
                source.source_type.value,
                source.base_url,
                1 if source.enabled else 0,
                source.created_at.isoformat(),
            ),
        )
        self._conn.commit()
        source.id = cur.lastrowid
        return source

    def get_source(self, slug: str) -> Source | None:
        row = self._conn.execute(
            "SELECT * FROM sources WHERE slug = ?", (slug,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_source(row)

    def get_source_by_id(self, source_id: int) -> Source | None:
        row = self._conn.execute(
            "SELECT * FROM sources WHERE id = ?", (source_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_source(row)

    def get_all_sources(self, enabled_only: bool = False) -> list[Source]:
        if enabled_only:
            rows = self._conn.execute(
                "SELECT * FROM sources WHERE enabled = 1 ORDER BY id"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM sources ORDER BY id"
            ).fetchall()
        return [self._row_to_source(row) for row in rows]

    def update_source(self, source: Source) -> None:
        self._conn.execute(
            """UPDATE sources SET name = ?, slug = ?, source_type = ?,
               base_url = ?, enabled = ? WHERE id = ?""",
            (
                source.name,
                source.slug,
                source.source_type.value,
                source.base_url,
                1 if source.enabled else 0,
                source.id,
            ),
        )
        self._conn.commit()

    # ── Crawl Runs ──────────────────────────────────────────────

    def create_run(self, source_id: int | None = None) -> CrawlRun:
        run = CrawlRun(source_id=source_id)
        cur = self._conn.execute(
            "INSERT INTO crawl_runs (source_id, started_at, status, summary) VALUES (?, ?, ?, ?)",
            (source_id, run.started_at.isoformat(), run.status.value, json.dumps(run.summary)),
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
            "source_id": row["source_id"],
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
            "status": row["status"],
            "summary": json.loads(row["summary"]),
        }

    def get_latest_run(self, source_id: int | None = None) -> dict | None:
        if source_id is not None:
            row = self._conn.execute(
                "SELECT * FROM crawl_runs WHERE source_id = ? ORDER BY id DESC LIMIT 1",
                (source_id,),
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT * FROM crawl_runs ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "source_id": row["source_id"],
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
               (crawl_run_id, source_id, source_url, title, content_type, raw_content,
                content_hash, retrieved_at, last_modified, language, content_category)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                doc.crawl_run_id,
                doc.source_id,
                doc.source_url,
                doc.title,
                doc.content_type.value,
                doc.raw_content,
                doc.content_hash,
                doc.retrieved_at.isoformat(),
                doc.last_modified,
                doc.language,
                doc.content_category.value,
            ),
        )
        self._conn.commit()
        doc.id = cur.lastrowid
        return doc, True

    def get_all_documents(self, source_id: int | None = None) -> list[Document]:
        if source_id is not None:
            rows = self._conn.execute(
                "SELECT * FROM documents WHERE source_id = ? ORDER BY id",
                (source_id,),
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT * FROM documents ORDER BY id").fetchall()
        return [self._row_to_document(row) for row in rows]

    def get_document_count(self, source_id: int | None = None) -> int:
        if source_id is not None:
            row = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM documents WHERE source_id = ?",
                (source_id,),
            ).fetchone()
        else:
            row = self._conn.execute("SELECT COUNT(*) as cnt FROM documents").fetchone()
        return row["cnt"]

    # ── Chunks ──────────────────────────────────────────────────

    def insert_chunks(self, chunks: list[Chunk]) -> None:
        # Deduplicate by (document_id, content_hash) — keeps the first
        # occurrence when a page has repeated content blocks.
        seen: set[tuple[int | None, str]] = set()
        unique: list[Chunk] = []
        for c in chunks:
            key = (c.document_id, c.content_hash)
            if key not in seen:
                seen.add(key)
                unique.append(c)

        self._conn.executemany(
            """INSERT INTO chunks
               (document_id, chunk_index, content, heading_path,
                token_count, content_hash, metadata, content_category, citation, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    c.document_id,
                    c.chunk_index,
                    c.content,
                    c.heading_path,
                    c.token_count,
                    c.content_hash,
                    json.dumps(c.metadata),
                    c.content_category.value,
                    c.citation,
                    1 if c.is_active else 0,
                )
                for c in unique
            ],
        )
        self._conn.commit()

    def get_chunks_for_document(self, document_id: int) -> list[Chunk]:
        rows = self._conn.execute(
            "SELECT * FROM chunks WHERE document_id = ? ORDER BY chunk_index",
            (document_id,),
        ).fetchall()
        return [self._row_to_chunk(row) for row in rows]

    def get_chunk_count(self, source_id: int | None = None) -> int:
        if source_id is not None:
            row = self._conn.execute(
                """SELECT COUNT(*) as cnt FROM chunks c
                   JOIN documents d ON c.document_id = d.id
                   WHERE d.source_id = ?""",
                (source_id,),
            ).fetchone()
        else:
            row = self._conn.execute("SELECT COUNT(*) as cnt FROM chunks").fetchone()
        return row["cnt"]

    def deactivate_chunks_for_document(self, document_id: int) -> int:
        """Mark all active chunks for a document as inactive (soft-delete).

        Used when a statutory section is repealed — chunks are deactivated
        rather than deleted so existing references don't break.

        Returns:
            Number of chunks deactivated.
        """
        cur = self._conn.execute(
            "UPDATE chunks SET is_active = 0 WHERE document_id = ? AND is_active = 1",
            (document_id,),
        )
        self._conn.commit()
        return cur.rowcount

    def deactivate_missing_sections(
        self, source_id: int, current_section_urls: set[str]
    ) -> int:
        """Deactivate chunks for sections no longer present in the source.

        Compares the set of section URLs from the latest extraction against
        stored documents for this source.  Any stored document whose URL is
        NOT in current_section_urls has its chunks marked inactive.

        Args:
            source_id: The source to check.
            current_section_urls: URLs of sections found in the latest extraction.

        Returns:
            Total number of chunks deactivated.
        """
        docs = self.get_all_documents(source_id=source_id)
        total_deactivated = 0
        for doc in docs:
            if doc.source_url not in current_section_urls and doc.id is not None:
                count = self.deactivate_chunks_for_document(doc.id)
                total_deactivated += count
        return total_deactivated

    def get_all_chunks(self, source_id: int | None = None) -> list[Chunk]:
        if source_id is not None:
            rows = self._conn.execute(
                """SELECT c.* FROM chunks c
                   JOIN documents d ON c.document_id = d.id
                   WHERE d.source_id = ?
                   ORDER BY c.document_id, c.chunk_index""",
                (source_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM chunks ORDER BY document_id, chunk_index"
            ).fetchall()
        return [self._row_to_chunk(row) for row in rows]

    # ── Citation Links ─────────────────────────────────────────

    def insert_citation_links(self, links: list[CitationLink]) -> int:
        """Bulk-insert citation links, skipping duplicates.

        Deduplicates on (source_chunk_id, cited_text) so re-processing
        the same opinion is idempotent.

        Returns:
            Number of links inserted.
        """
        inserted = 0
        for link in links:
            try:
                self._conn.execute(
                    """INSERT INTO citation_links
                       (source_chunk_id, cited_text, citation_type, reporter,
                        volume, page, section, is_california, target_chunk_id, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        link.source_chunk_id,
                        link.cited_text,
                        link.citation_type,
                        link.reporter,
                        link.volume,
                        link.page,
                        link.section,
                        1 if link.is_california else 0,
                        link.target_chunk_id,
                        link.created_at.isoformat(),
                    ),
                )
                inserted += 1
            except sqlite3.IntegrityError:
                # Duplicate (source_chunk_id, cited_text) — skip
                continue
        self._conn.commit()
        return inserted

    def get_citations_for_chunk(self, chunk_id: int) -> list[CitationLink]:
        """Get all citations made by a chunk (forward lookup).

        Args:
            chunk_id: The citing chunk's ID.

        Returns:
            List of CitationLink objects for citations in this chunk.
        """
        rows = self._conn.execute(
            "SELECT * FROM citation_links WHERE source_chunk_id = ? ORDER BY id",
            (chunk_id,),
        ).fetchall()
        return [self._row_to_citation_link(row) for row in rows]

    def get_citing_chunks(self, chunk_id: int) -> list[CitationLink]:
        """Get all citation links that point to a chunk (reverse lookup).

        Args:
            chunk_id: The cited chunk's ID (target_chunk_id).

        Returns:
            List of CitationLink objects where this chunk is the target.
        """
        rows = self._conn.execute(
            "SELECT * FROM citation_links WHERE target_chunk_id = ? ORDER BY id",
            (chunk_id,),
        ).fetchall()
        return [self._row_to_citation_link(row) for row in rows]

    def get_citation_link_count(self) -> int:
        """Return total number of citation links."""
        row = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM citation_links"
        ).fetchone()
        return row["cnt"]

    def delete_citation_links_for_chunk(self, chunk_id: int) -> int:
        """Delete all citation links originating from a chunk.

        Used to re-process a chunk's citations cleanly.

        Returns:
            Number of links deleted.
        """
        cur = self._conn.execute(
            "DELETE FROM citation_links WHERE source_chunk_id = ?",
            (chunk_id,),
        )
        self._conn.commit()
        return cur.rowcount

    def resolve_citation_targets(self) -> int:
        """Resolve unlinked citation_links to target chunks by matching citations.

        For statute citations, matches the section number against chunks
        with a matching citation field. For case citations, matches the
        reporter + volume + page against chunk citation text.

        Returns:
            Number of links resolved.
        """
        resolved = 0

        # Resolve statute citations: match section against chunk citation field
        cur = self._conn.execute(
            """UPDATE citation_links SET target_chunk_id = (
                   SELECT c.id FROM chunks c
                   WHERE c.citation IS NOT NULL
                     AND c.is_active = 1
                     AND citation_links.section IS NOT NULL
                     AND c.citation LIKE '%§ ' || citation_links.section || '%'
                   ORDER BY c.id LIMIT 1
               )
               WHERE target_chunk_id IS NULL
                 AND citation_type = 'statute'
                 AND section IS NOT NULL"""
        )
        resolved += cur.rowcount

        # Resolve case citations: match volume + reporter + page
        cur = self._conn.execute(
            """UPDATE citation_links SET target_chunk_id = (
                   SELECT c.id FROM chunks c
                   WHERE c.citation IS NOT NULL
                     AND c.is_active = 1
                     AND c.content_category = 'case_law'
                     AND citation_links.volume IS NOT NULL
                     AND citation_links.reporter IS NOT NULL
                     AND citation_links.page IS NOT NULL
                     AND c.citation LIKE '%' || citation_links.volume
                         || ' ' || citation_links.reporter
                         || ' ' || citation_links.page || '%'
                   ORDER BY c.id LIMIT 1
               )
               WHERE target_chunk_id IS NULL
                 AND citation_type = 'case'
                 AND volume IS NOT NULL
                 AND reporter IS NOT NULL
                 AND page IS NOT NULL"""
        )
        resolved += cur.rowcount

        self._conn.commit()
        return resolved

    # ── Cross-Source Duplicate Detection ────────────────────────

    def find_cross_source_duplicates(self) -> list[dict]:
        """Find chunks with identical content_hash across different sources.

        Returns a list of dicts, each describing a set of duplicate chunks:
        {
            "content_hash": str,
            "occurrences": [
                {"chunk_id": int, "source_id": int, "source_slug": str,
                 "citation": str | None, "content_category": str}
            ]
        }
        """
        rows = self._conn.execute(
            """SELECT c.id as chunk_id, c.content_hash, c.citation,
                      c.content_category, d.source_id, s.slug as source_slug
               FROM chunks c
               JOIN documents d ON c.document_id = d.id
               LEFT JOIN sources s ON d.source_id = s.id
               WHERE c.content_hash IN (
                   SELECT c2.content_hash
                   FROM chunks c2
                   JOIN documents d2 ON c2.document_id = d2.id
                   GROUP BY c2.content_hash
                   HAVING COUNT(DISTINCT d2.source_id) > 1
               )
               ORDER BY c.content_hash, d.source_id"""
        ).fetchall()

        # Group by content_hash
        duplicates: dict[str, list[dict]] = {}
        for row in rows:
            h = row["content_hash"]
            if h not in duplicates:
                duplicates[h] = []
            duplicates[h].append({
                "chunk_id": row["chunk_id"],
                "source_id": row["source_id"],
                "source_slug": row["source_slug"],
                "citation": row["citation"],
                "content_category": row["content_category"],
            })

        return [
            {"content_hash": h, "occurrences": occs}
            for h, occs in duplicates.items()
        ]

    # ── Private helpers ─────────────────────────────────────────

    @staticmethod
    def _row_to_source(row: sqlite3.Row) -> Source:
        return Source(
            id=row["id"],
            name=row["name"],
            slug=row["slug"],
            source_type=SourceType(row["source_type"]),
            base_url=row["base_url"],
            enabled=bool(row["enabled"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    @staticmethod
    def _row_to_document(row: sqlite3.Row) -> Document:
        return Document(
            id=row["id"],
            crawl_run_id=row["crawl_run_id"],
            source_id=row["source_id"],
            source_url=row["source_url"],
            title=row["title"],
            content_type=ContentType(row["content_type"]),
            raw_content=row["raw_content"],
            content_hash=row["content_hash"],
            retrieved_at=datetime.fromisoformat(row["retrieved_at"]),
            last_modified=row["last_modified"],
            language=row["language"],
            content_category=ContentCategory(row["content_category"]),
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
            content_category=ContentCategory(row["content_category"]),
            citation=row["citation"],
            is_active=bool(row["is_active"]),
        )

    @staticmethod
    def _row_to_citation_link(row: sqlite3.Row) -> CitationLink:
        return CitationLink(
            id=row["id"],
            source_chunk_id=row["source_chunk_id"],
            cited_text=row["cited_text"],
            citation_type=row["citation_type"],
            reporter=row["reporter"],
            volume=row["volume"],
            page=row["page"],
            section=row["section"],
            is_california=bool(row["is_california"]),
            target_chunk_id=row["target_chunk_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
