"""Vector store backed by LanceDB for hybrid search.

Stores chunk embeddings and supports vector, keyword (BM25), and hybrid search
with metadata filtering. Uses merge_insert for atomic upserts and scalar
indexes on frequently filtered columns.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog

from employee_help.retrieval.embedder import ChunkEmbedding

logger = structlog.get_logger()


class VectorStore:
    """LanceDB-backed vector store for chunk embeddings.

    At ~23K chunks with 768-dim vectors, flat-scan vector search returns in
    under 10ms so no ANN index is needed. An FTS index on the ``content``
    column supports BM25 keyword search, and hybrid search combines both
    via Reciprocal Rank Fusion.
    """

    TABLE_NAME = "chunk_embeddings"

    def __init__(self, db_path: str = "data/lancedb") -> None:
        self.db_path = db_path
        self._db = None
        self._table = None
        self._fts_dirty = False
        self.logger = structlog.get_logger(__name__, db_path=db_path)

    def _open_db(self):
        """Lazy-open the LanceDB database."""
        if self._db is not None:
            return self._db

        try:
            import lancedb
        except ImportError:
            raise ImportError(
                "lancedb is required for vector search. "
                "Install with: uv pip install -e '.[rag]'"
            )

        Path(self.db_path).mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(self.db_path)
        return self._db

    @property
    def db(self):
        return self._open_db()

    def _get_table(self):
        """Get the embeddings table, or None if it doesn't exist."""
        if self._table is not None:
            return self._table

        if self.TABLE_NAME in self.db.table_names():
            self._table = self.db.open_table(self.TABLE_NAME)
            return self._table
        return None

    @property
    def table(self):
        return self._get_table()

    @property
    def columns(self) -> set[str]:
        """Return the set of column names in the embeddings table."""
        if self.table is None:
            return set()
        try:
            return set(self.table.schema.names)
        except Exception:
            return set()

    # ── Table creation ──────────────────────────────────────────────

    def create_table(self, embeddings: list[ChunkEmbedding]) -> None:
        """Create the embeddings table from a list of chunk embeddings.

        Drops and recreates the table if it already exists.
        """
        if not embeddings:
            self.logger.warning("create_table_empty_embeddings")
            return

        data = self._embeddings_to_records(embeddings)

        if self.TABLE_NAME in self.db.table_names():
            self.db.drop_table(self.TABLE_NAME)
            self._table = None

        self._table = self.db.create_table(self.TABLE_NAME, data=data)
        self._create_scalar_indexes()
        self._create_fts_index()

        self.logger.info("table_created", rows=len(data))

    def _create_scalar_indexes(self) -> None:
        """Create scalar indexes on frequently filtered columns."""
        if self.table is None:
            return

        for col in ("chunk_id", "content_category", "source_id", "language"):
            try:
                self.table.create_scalar_index(col, replace=True)
            except Exception as e:
                self.logger.debug("scalar_index_skipped", column=col, error=str(e))

    def _create_fts_index(self) -> None:
        """Create full-text search index on the content column."""
        if self.table is None:
            return

        try:
            self.table.create_fts_index("content", replace=True)
            self._fts_dirty = False
            self.logger.info("fts_index_created")
        except Exception as e:
            self.logger.warning("fts_index_creation_failed", error=str(e))

    def rebuild_fts_index(self) -> None:
        """Explicitly rebuild the FTS index (e.g. after batch upserts)."""
        self._create_fts_index()

    # ── Mutations ───────────────────────────────────────────────────

    def upsert_embeddings(self, embeddings: list[ChunkEmbedding]) -> None:
        """Add or update embeddings using atomic merge_insert.

        Creates the table if it doesn't exist. Uses LanceDB's merge_insert
        for atomic upsert keyed on chunk_id.

        Note: call ``rebuild_fts_index()`` after a series of upserts to
        refresh the full-text search index.
        """
        if not embeddings:
            return

        if self.table is None:
            self.create_table(embeddings)
            return

        data = self._embeddings_to_records(embeddings)

        try:
            (
                self.table
                .merge_insert("chunk_id")
                .when_matched_update_all()
                .when_not_matched_insert_all()
                .execute(data)
            )
            self._fts_dirty = True
            self.logger.info("embeddings_upserted", count=len(data))
        except Exception as e:
            self.logger.error("merge_insert_failed", error=str(e))
            raise

    def delete_embeddings(self, chunk_ids: list[int]) -> None:
        """Remove embeddings for the given chunk IDs."""
        if not chunk_ids or self.table is None:
            return

        id_list = ", ".join(str(int(cid)) for cid in chunk_ids)
        self.table.delete(f"chunk_id IN ({id_list})")
        self._fts_dirty = True
        self.logger.info("embeddings_deleted", count=len(chunk_ids))

    # ── Search ──────────────────────────────────────────────────────

    def search_vector(
        self,
        query_vector: list[float],
        top_k: int = 50,
        filter_expr: str | None = None,
    ) -> list[dict[str, Any]]:
        """Pure vector similarity search (cosine, flat scan)."""
        if self.table is None:
            return []

        query = self.table.search(query_vector).limit(top_k)
        if filter_expr:
            query = query.where(filter_expr, prefilter=True)

        return query.to_list()

    def search_keyword(
        self,
        query_text: str,
        top_k: int = 50,
        filter_expr: str | None = None,
    ) -> list[dict[str, Any]]:
        """Pure BM25 keyword search via full-text search index."""
        if self.table is None:
            return []

        try:
            query = self.table.search(query_text, query_type="fts").limit(top_k)
            if filter_expr:
                query = query.where(filter_expr, prefilter=True)
            return query.to_list()
        except Exception as e:
            self.logger.warning("keyword_search_failed", error=str(e))
            return []

    def search_hybrid(
        self,
        query_text: str,
        query_vector: list[float],
        top_k: int = 50,
        filter_expr: str | None = None,
    ) -> list[dict[str, Any]]:
        """Hybrid search combining vector similarity and BM25 via RRF fusion."""
        if self.table is None:
            return []

        try:
            from lancedb.rerankers import RRFReranker

            query = (
                self.table.search(query_type="hybrid")
                .vector(query_vector)
                .text(query_text)
                .rerank(RRFReranker())
                .limit(top_k)
            )
            if filter_expr:
                query = query.where(filter_expr, prefilter=True)
            return query.to_list()
        except Exception as e:
            self.logger.warning("hybrid_search_fallback_to_vector", error=str(e))
            return self.search_vector(query_vector, top_k, filter_expr)

    # ── Stats & queries ─────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Return embedding count, active count, and category breakdown.

        Uses column-level selection to avoid loading vectors into memory.
        """
        stats: dict[str, Any] = {
            "db_path": self.db_path,
            "table_exists": self.table is not None,
            "embedding_count": 0,
            "active_count": 0,
        }

        if self.table is None:
            return stats

        try:
            # Select only the metadata columns we need (not the vector column)
            arrow_table = self.table.to_arrow().select(
                ["is_active", "content_category"]
            )
            stats["embedding_count"] = arrow_table.num_rows

            is_active_col = arrow_table.column("is_active").to_pylist()
            stats["active_count"] = sum(1 for v in is_active_col if v)

            cat_col = arrow_table.column("content_category").to_pylist()
            categories: dict[str, int] = {}
            for cat in cat_col:
                categories[cat] = categories.get(cat, 0) + 1
            stats["content_categories"] = categories
        except Exception as e:
            self.logger.warning("stats_error", error=str(e))

        return stats

    def get_embedded_chunk_ids(self) -> set[int]:
        """Return the set of chunk IDs that have embeddings."""
        if self.table is None:
            return set()

        try:
            col = self.table.to_arrow().select(["chunk_id"]).column("chunk_id")
            return set(col.to_pylist())
        except Exception:
            return set()

    def get_embedded_content_hashes(self) -> set[str]:
        """Return the set of content hashes that have embeddings."""
        if self.table is None:
            return set()

        try:
            col = self.table.to_arrow().select(["content_hash"]).column("content_hash")
            return set(col.to_pylist())
        except Exception:
            return set()

    # ── Internals ───────────────────────────────────────────────────

    def _embeddings_to_records(
        self, embeddings: list[ChunkEmbedding]
    ) -> list[dict[str, Any]]:
        """Convert ChunkEmbedding objects to dicts for LanceDB insertion.

        The ``content`` field is prepended with the citation and heading path
        so that BM25 full-text search can match citation queries like
        "section 1102.5" even when the statute body doesn't mention its own
        section number.
        """
        records = []
        for emb in embeddings:
            # Prepend citation + heading to content for FTS discoverability
            searchable_content = emb.content
            prefix_parts = []
            if emb.citation:
                prefix_parts.append(f"[{emb.citation}]")
            if emb.heading_path:
                prefix_parts.append(emb.heading_path)
            if prefix_parts:
                searchable_content = " ".join(prefix_parts) + "\n" + emb.content

            records.append(
                {
                    "chunk_id": emb.chunk_id,
                    "document_id": emb.document_id,
                    "source_id": emb.source_id,
                    "content_category": emb.content_category,
                    "citation": emb.citation or "",
                    "content": searchable_content,
                    "heading_path": emb.heading_path,
                    "vector": emb.dense_vector,
                    "content_hash": emb.content_hash,
                    "is_active": emb.is_active,
                    "source_url": emb.source_url,
                    "model_version": emb.model_version,
                    "language": emb.language,
                }
            )
        return records
