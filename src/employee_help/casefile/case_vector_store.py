"""LanceDB vector store for case file embeddings.

Manages the ``case_embeddings`` table — separate from the knowledge base
``chunk_embeddings`` table. All searches are scoped to a single case via
``case_id`` filter for tenant isolation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class CaseChunkEmbedding:
    """Embedding with case-file metadata for LanceDB storage."""

    chunk_id: str  # UUID from CaseChunk.id
    file_id: str  # UUID from CaseFile.id
    case_id: str  # UUID from Case.id
    content: str  # Chunk text
    heading_path: str  # "filename.pdf > Page 3"
    dense_vector: list[float]  # 768-dim bge-base-en-v1.5
    content_hash: str  # SHA-256
    is_active: bool
    file_type: str  # "pdf", "docx", etc.
    original_filename: str  # For display in search results


class CaseVectorStore:
    """LanceDB-backed vector store for case file chunk embeddings.

    Uses a separate ``case_embeddings`` table in the same LanceDB directory
    as the knowledge base. All search methods require a ``case_id`` filter
    to ensure case isolation.
    """

    TABLE_NAME = "case_embeddings"

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
                "lancedb is required for case file search. "
                "Install with: uv pip install -e '.[rag]'"
            )

        Path(self.db_path).mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(self.db_path)
        return self._db

    @property
    def db(self):
        return self._open_db()

    def _get_table(self):
        """Get the case embeddings table, or None if it doesn't exist."""
        if self._table is not None:
            return self._table

        if self.TABLE_NAME in self.db.table_names():
            self._table = self.db.open_table(self.TABLE_NAME)
            return self._table
        return None

    @property
    def table(self):
        return self._get_table()

    # ── Mutations ───────────────────────────────────────────────────

    def upsert_embeddings(self, embeddings: list[CaseChunkEmbedding]) -> None:
        """Add or update case chunk embeddings.

        Creates the table on first call. Uses merge_insert keyed on chunk_id.
        Call ``rebuild_fts_index()`` after a batch of upserts.
        """
        if not embeddings:
            return

        data = self._to_records(embeddings)

        if self.table is None:
            self._table = self.db.create_table(self.TABLE_NAME, data=data)
            self._create_scalar_indexes()
            self._create_fts_index()
            self.logger.info("case_embeddings_table_created", rows=len(data))
            return

        try:
            (
                self.table
                .merge_insert("chunk_id")
                .when_matched_update_all()
                .when_not_matched_insert_all()
                .execute(data)
            )
            self._fts_dirty = True
            self.logger.info("case_embeddings_upserted", count=len(data))
        except Exception as e:
            self.logger.error("case_embeddings_upsert_failed", error=str(e))
            raise

    def delete_file_embeddings(self, file_id: str) -> None:
        """Remove all embeddings for a specific file."""
        if self.table is None:
            return

        self.table.delete(f"file_id = '{file_id}'")
        self._fts_dirty = True
        self.logger.info("case_file_embeddings_deleted", file_id=file_id)

    def delete_case_embeddings(self, case_id: str) -> None:
        """Remove all embeddings for a case."""
        if self.table is None:
            return

        self.table.delete(f"case_id = '{case_id}'")
        self._fts_dirty = True
        self.logger.info("case_embeddings_deleted", case_id=case_id)

    # ── Search ──────────────────────────────────────────────────────

    def search_hybrid(
        self,
        case_id: str,
        query_text: str,
        query_vector: list[float],
        top_k: int = 20,
    ) -> list[dict[str, Any]]:
        """Hybrid vector + BM25 search scoped to a single case."""
        if self.table is None:
            return []

        filter_expr = f"case_id = '{case_id}' AND is_active = true"

        try:
            from lancedb.rerankers import RRFReranker

            query = (
                self.table.search(query_type="hybrid")
                .vector(query_vector)
                .text(query_text)
                .rerank(RRFReranker())
                .limit(top_k)
                .where(filter_expr, prefilter=True)
            )
            return query.to_list()
        except Exception as e:
            self.logger.warning("case_hybrid_search_fallback", error=str(e))
            return self.search_vector(case_id, query_vector, top_k)

    def search_vector(
        self,
        case_id: str,
        query_vector: list[float],
        top_k: int = 20,
    ) -> list[dict[str, Any]]:
        """Pure vector search scoped to a single case."""
        if self.table is None:
            return []

        filter_expr = f"case_id = '{case_id}' AND is_active = true"
        query = self.table.search(query_vector).limit(top_k)
        query = query.where(filter_expr, prefilter=True)
        return query.to_list()

    # ── Stats ───────────────────────────────────────────────────────

    def get_chunk_count(self, case_id: str) -> int:
        """Count active embeddings for a case."""
        if self.table is None:
            return 0

        try:
            arrow_table = self.table.to_arrow().select(["case_id", "is_active"])
            case_ids = arrow_table.column("case_id").to_pylist()
            actives = arrow_table.column("is_active").to_pylist()
            return sum(
                1 for cid, act in zip(case_ids, actives)
                if cid == case_id and act
            )
        except Exception:
            return 0

    # ── Index management ────────────────────────────────────────────

    def rebuild_fts_index(self) -> None:
        """Rebuild FTS index after upserts."""
        self._create_fts_index()

    def _create_scalar_indexes(self) -> None:
        """Create scalar indexes on filter columns."""
        if self.table is None:
            return

        for col in ("chunk_id", "case_id", "file_id"):
            try:
                self.table.create_scalar_index(col, replace=True)
            except Exception as e:
                self.logger.debug(
                    "case_scalar_index_skipped", column=col, error=str(e)
                )

    def _create_fts_index(self) -> None:
        """Create full-text search index on content."""
        if self.table is None:
            return

        try:
            self.table.create_fts_index("content", replace=True)
            self._fts_dirty = False
            self.logger.info("case_fts_index_created")
        except Exception as e:
            self.logger.warning("case_fts_index_failed", error=str(e))

    # ── Internals ───────────────────────────────────────────────────

    def _to_records(
        self, embeddings: list[CaseChunkEmbedding]
    ) -> list[dict[str, Any]]:
        """Convert CaseChunkEmbedding objects to LanceDB records."""
        records = []
        for emb in embeddings:
            # Prepend heading_path to content for FTS discoverability
            searchable_content = emb.content
            if emb.heading_path:
                searchable_content = emb.heading_path + "\n" + emb.content

            records.append({
                "chunk_id": emb.chunk_id,
                "file_id": emb.file_id,
                "case_id": emb.case_id,
                "content": searchable_content,
                "heading_path": emb.heading_path,
                "vector": emb.dense_vector,
                "content_hash": emb.content_hash,
                "is_active": emb.is_active,
                "file_type": emb.file_type,
                "original_filename": emb.original_filename,
            })
        return records
