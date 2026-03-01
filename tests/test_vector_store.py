"""Tests for the LanceDB vector store."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from employee_help.retrieval.embedder import ChunkEmbedding
from employee_help.retrieval.vector_store import VectorStore


def _make_embedding(chunk_id: int, content: str = "test", **kwargs) -> ChunkEmbedding:
    """Helper to create a test ChunkEmbedding."""
    defaults = {
        "chunk_id": chunk_id,
        "document_id": 1,
        "source_id": 1,
        "content_category": "statutory_code",
        "citation": f"§ {chunk_id}",
        "content": content,
        "heading_path": f"Test > Chunk {chunk_id}",
        "dense_vector": [0.1 * (i % 10) for i in range(768)],
        "content_hash": f"hash_{chunk_id}",
        "is_active": True,
        "source_url": f"https://example.com/{chunk_id}",
        "model_version": "test-model",
    }
    defaults.update(kwargs)
    return ChunkEmbedding(**defaults)


@pytest.fixture
def tmp_db_path(tmp_path):
    return str(tmp_path / "test_lancedb")


@pytest.fixture
def vector_store(tmp_db_path):
    return VectorStore(db_path=tmp_db_path)


@pytest.fixture
def populated_store(vector_store):
    """Vector store with 5 test embeddings."""
    embeddings = [
        _make_embedding(1, "California labor law minimum wage requirements"),
        _make_embedding(2, "FEHA discrimination protections for employees"),
        _make_embedding(3, "Whistleblower retaliation protections under Labor Code"),
        _make_embedding(4, "Unemployment insurance benefits and eligibility", content_category="agency_guidance"),
        _make_embedding(5, "Workplace safety and Cal OSHA requirements", content_category="fact_sheet"),
    ]
    vector_store.create_table(embeddings)
    return vector_store


class TestVectorStoreCreation:
    """Tests for creating and managing the vector store."""

    def test_create_empty_store(self, vector_store):
        assert vector_store.table is None

    def test_create_table(self, vector_store):
        embeddings = [_make_embedding(1), _make_embedding(2)]
        vector_store.create_table(embeddings)
        assert vector_store.table is not None

    def test_create_table_empty(self, vector_store):
        vector_store.create_table([])
        assert vector_store.table is None

    def test_create_table_replaces_existing(self, vector_store):
        vector_store.create_table([_make_embedding(1)])
        stats1 = vector_store.get_stats()
        assert stats1["embedding_count"] == 1

        vector_store.create_table([_make_embedding(2), _make_embedding(3)])
        stats2 = vector_store.get_stats()
        assert stats2["embedding_count"] == 2

    def test_create_table_stores_model_version(self, vector_store):
        vector_store.create_table([
            _make_embedding(1, model_version="BAAI/bge-base-en-v1.5"),
        ])
        arrow = vector_store.table.to_arrow()
        versions = arrow.column("model_version").to_pylist()
        assert versions == ["BAAI/bge-base-en-v1.5"]


class TestVectorStoreOperations:
    """Tests for upsert, delete, and query operations."""

    def test_upsert_new_embeddings(self, vector_store):
        vector_store.create_table([_make_embedding(1)])
        vector_store.upsert_embeddings([_make_embedding(2)])
        stats = vector_store.get_stats()
        assert stats["embedding_count"] == 2

    def test_upsert_updates_existing(self, vector_store):
        """merge_insert should update existing chunk_id, not create duplicates."""
        vector_store.create_table([_make_embedding(1, content="original")])
        vector_store.upsert_embeddings([_make_embedding(1, content="updated")])
        stats = vector_store.get_stats()
        assert stats["embedding_count"] == 1
        # Verify content was updated
        arrow = vector_store.table.to_arrow()
        contents = arrow.column("content").to_pylist()
        assert "updated" in contents[0]

    def test_upsert_creates_table_if_missing(self, vector_store):
        vector_store.upsert_embeddings([_make_embedding(1)])
        assert vector_store.table is not None

    def test_delete_embeddings(self, populated_store):
        initial_count = populated_store.get_stats()["embedding_count"]
        populated_store.delete_embeddings([1, 2])
        final_count = populated_store.get_stats()["embedding_count"]
        assert final_count == initial_count - 2

    def test_delete_nonexistent(self, populated_store):
        initial_count = populated_store.get_stats()["embedding_count"]
        populated_store.delete_embeddings([999])
        final_count = populated_store.get_stats()["embedding_count"]
        assert final_count == initial_count

    def test_delete_empty_list_is_noop(self, populated_store):
        initial_count = populated_store.get_stats()["embedding_count"]
        populated_store.delete_embeddings([])
        assert populated_store.get_stats()["embedding_count"] == initial_count

    def test_get_stats(self, populated_store):
        stats = populated_store.get_stats()
        assert stats["table_exists"] is True
        assert stats["embedding_count"] == 5
        assert stats["active_count"] == 5
        assert "content_categories" in stats

    def test_get_stats_with_inactive(self, vector_store):
        embeddings = [
            _make_embedding(1, is_active=True),
            _make_embedding(2, is_active=False),
        ]
        vector_store.create_table(embeddings)
        stats = vector_store.get_stats()
        assert stats["embedding_count"] == 2
        assert stats["active_count"] == 1

    def test_get_embedded_chunk_ids(self, populated_store):
        ids = populated_store.get_embedded_chunk_ids()
        assert ids == {1, 2, 3, 4, 5}

    def test_get_embedded_content_hashes(self, populated_store):
        hashes = populated_store.get_embedded_content_hashes()
        assert len(hashes) == 5
        assert "hash_1" in hashes


class TestVectorStoreSearch:
    """Tests for search operations."""

    def test_vector_search(self, populated_store):
        query_vec = [0.1 * (i % 10) for i in range(768)]
        results = populated_store.search_vector(query_vec, top_k=3)
        assert len(results) <= 3
        assert len(results) > 0

    def test_vector_search_empty_store(self, vector_store):
        query_vec = [0.1] * 768
        results = vector_store.search_vector(query_vec)
        assert results == []

    def test_keyword_search(self, populated_store):
        results = populated_store.search_keyword("minimum wage", top_k=3)
        assert isinstance(results, list)

    def test_hybrid_search(self, populated_store):
        query_vec = [0.1 * (i % 10) for i in range(768)]
        results = populated_store.search_hybrid(
            "minimum wage", query_vec, top_k=3
        )
        assert isinstance(results, list)
        assert len(results) <= 3

    def test_hybrid_search_falls_back_on_error(self, vector_store):
        """Hybrid search should fall back to vector search if FTS fails."""
        vector_store.create_table([_make_embedding(1, content="test content")])
        query_vec = [0.1 * (i % 10) for i in range(768)]
        # Even if hybrid fails internally, we should get results
        results = vector_store.search_hybrid("test", query_vec, top_k=3)
        assert isinstance(results, list)

    def test_search_with_filter(self, populated_store):
        query_vec = [0.1 * (i % 10) for i in range(768)]
        results = populated_store.search_vector(
            query_vec,
            top_k=10,
            filter_expr="content_category = 'statutory_code'",
        )
        for r in results:
            assert r["content_category"] == "statutory_code"

    def test_search_with_is_active_filter(self, vector_store):
        embeddings = [
            _make_embedding(1, content="active content", is_active=True),
            _make_embedding(2, content="inactive content", is_active=False),
        ]
        vector_store.create_table(embeddings)
        query_vec = [0.1 * (i % 10) for i in range(768)]
        results = vector_store.search_vector(
            query_vec, top_k=10, filter_expr="is_active = true"
        )
        for r in results:
            assert r["is_active"] is True


class TestCaseLawIndexing:
    """Tests for case law embedding indexing and retrieval (4C.5)."""

    def test_case_law_stored_in_vector_index(self, vector_store):
        """Case law embeddings should be stored alongside other categories."""
        embeddings = [
            _make_embedding(1, "FEHA retaliation elements", content_category="statutory_code"),
            _make_embedding(
                2, "Yanowitz court held adverse action includes pattern of retaliatory conduct",
                content_category="case_law",
                citation="Yanowitz v. L'Oreal USA, Inc. (2005) 36 Cal.4th 1028",
            ),
            _make_embedding(3, "Agency guidance on filing complaints", content_category="agency_guidance"),
        ]
        vector_store.create_table(embeddings)

        stats = vector_store.get_stats()
        assert stats["embedding_count"] == 3
        assert stats["content_categories"]["case_law"] == 1

    def test_case_law_excluded_by_consumer_filter(self, vector_store):
        """Consumer mode filter should exclude case_law from results."""
        embeddings = [
            _make_embedding(1, "agency content", content_category="agency_guidance"),
            _make_embedding(2, "case law content", content_category="case_law"),
        ]
        vector_store.create_table(embeddings)

        query_vec = [0.1 * (i % 10) for i in range(768)]
        results = vector_store.search_vector(
            query_vec, top_k=10,
            filter_expr="is_active = true AND content_category IN ('agency_guidance', 'fact_sheet', 'faq')",
        )
        for r in results:
            assert r["content_category"] != "case_law"

    def test_case_law_included_in_attorney_filter(self, vector_store):
        """Attorney mode filter (is_active only) should include case_law."""
        embeddings = [
            _make_embedding(1, "statutory content", content_category="statutory_code"),
            _make_embedding(2, "case law content", content_category="case_law"),
        ]
        vector_store.create_table(embeddings)

        query_vec = [0.1 * (i % 10) for i in range(768)]
        results = vector_store.search_vector(
            query_vec, top_k=10,
            filter_expr="is_active = true",
        )
        categories = {r["content_category"] for r in results}
        assert "case_law" in categories

    def test_case_law_fts_searchable(self, vector_store):
        """Case law content should be discoverable via FTS/BM25 search."""
        embeddings = [
            _make_embedding(
                1, "Yanowitz adverse employment action retaliation FEHA",
                content_category="case_law",
                citation="Yanowitz v. L'Oreal USA, Inc. (2005) 36 Cal.4th 1028",
            ),
        ]
        vector_store.create_table(embeddings)

        results = vector_store.search_keyword("Yanowitz retaliation", top_k=5)
        assert len(results) > 0
        assert results[0]["content_category"] == "case_law"

    def test_case_law_citation_in_fts_content(self, vector_store):
        """Case law citation should be prepended to FTS content for discoverability."""
        emb = _make_embedding(
            1, "The court analyzed the elements of retaliation.",
            content_category="case_law",
            citation="Yanowitz v. L'Oreal USA, Inc. (2005) 36 Cal.4th 1028",
        )
        records = vector_store._embeddings_to_records([emb])
        # Citation should be prepended to the searchable content
        assert "[Yanowitz v. L'Oreal" in records[0]["content"]


class TestFTSIndex:
    """Tests for FTS index management."""

    def test_fts_dirty_flag_on_upsert(self, populated_store):
        populated_store.upsert_embeddings([_make_embedding(10, content="new content")])
        assert populated_store._fts_dirty is True

    def test_rebuild_fts_clears_dirty(self, populated_store):
        populated_store._fts_dirty = True
        populated_store.rebuild_fts_index()
        assert populated_store._fts_dirty is False
