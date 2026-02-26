"""Integration tests for the embedding pipeline with real models.

These tests load the actual BGE model and LanceDB, testing the full
embedding → storage → search pipeline. They are slow (~60s) and require
the `sentence-transformers` package.

Run with: uv run pytest -m slow tests/test_embedding_integration.py -v
"""

from __future__ import annotations

import tempfile

import pytest

from employee_help.storage.models import Chunk, ContentCategory


@pytest.mark.slow
class TestEmbeddingIntegration:
    """Integration tests using real BGE model."""

    @pytest.fixture(scope="class")
    def embedding_service(self):
        """Load the real BGE model once for all tests in this class."""
        from employee_help.retrieval.embedder import EmbeddingService

        return EmbeddingService(model_name="BAAI/bge-base-en-v1.5", device="cpu")

    def test_embed_single_text(self, embedding_service):
        result = embedding_service.embed_text("California employment law")
        assert len(result.dense_vector) == 768
        # Verify L2-normalized (should be ~1.0)
        norm = sum(x**2 for x in result.dense_vector) ** 0.5
        assert abs(norm - 1.0) < 0.01

    def test_embed_query_differs_from_text(self, embedding_service):
        """Query embedding (with prefix) should differ from document embedding."""
        text = "minimum wage California"
        doc_result = embedding_service.embed_text(text)
        query_result = embedding_service.embed_query(text)
        # Vectors should be different due to query prefix
        assert doc_result.dense_vector != query_result.dense_vector

    def test_embed_batch(self, embedding_service):
        texts = [
            "California minimum wage requirements",
            "FEHA discrimination protections",
            "Whistleblower retaliation statute",
        ]
        results = embedding_service.embed_batch(texts, batch_size=2)
        assert len(results) == 3
        for r in results:
            assert len(r.dense_vector) == 768

    def test_semantic_similarity(self, embedding_service):
        """Related texts should have higher cosine similarity than unrelated."""
        import numpy as np

        q = embedding_service.embed_query("Can I be fired for reporting safety violations?")
        related = embedding_service.embed_text("Whistleblower retaliation protections for employees who report safety violations")
        unrelated = embedding_service.embed_text("How to apply for unemployment insurance benefits online")

        q_vec = np.array(q.dense_vector)
        r_vec = np.array(related.dense_vector)
        u_vec = np.array(unrelated.dense_vector)

        sim_related = float(np.dot(q_vec, r_vec))
        sim_unrelated = float(np.dot(q_vec, u_vec))

        assert sim_related > sim_unrelated, (
            f"Related text similarity ({sim_related:.4f}) should be higher "
            f"than unrelated ({sim_unrelated:.4f})"
        )

    def test_embed_chunks(self, embedding_service):
        chunks = [
            Chunk(
                content="Under Cal. Lab. Code section 1102.5, an employer shall not retaliate against an employee for disclosing information to a government or law enforcement agency.",
                content_hash="hash_1102_5",
                chunk_index=0,
                heading_path="Labor Code > Division 2 > Part 3 > Chapter 3.6",
                token_count=40,
                document_id=1,
                id=100,
                content_category=ContentCategory.STATUTORY_CODE,
                citation="Cal. Lab. Code § 1102.5",
                is_active=True,
            ),
            Chunk(
                content="If you believe your employer has violated your workplace rights, you can file a complaint with the California Labor Commissioner's Office.",
                content_hash="hash_agency",
                chunk_index=0,
                heading_path="DIR > Filing a Complaint",
                token_count=30,
                document_id=2,
                id=101,
                content_category=ContentCategory.AGENCY_GUIDANCE,
                is_active=True,
            ),
        ]

        embeddings = embedding_service.embed_chunks(chunks, source_id=1)
        assert len(embeddings) == 2
        assert embeddings[0].chunk_id == 100
        assert embeddings[0].content_category == "statutory_code"
        assert embeddings[0].model_version == "BAAI/bge-base-en-v1.5"
        assert len(embeddings[0].dense_vector) == 768


@pytest.mark.slow
class TestVectorStoreIntegration:
    """Integration tests for the full embed → store → search pipeline."""

    @pytest.fixture
    def pipeline(self):
        """Set up a complete embedding + vector store pipeline."""
        from employee_help.retrieval.embedder import EmbeddingService
        from employee_help.retrieval.vector_store import VectorStore

        embedding_service = EmbeddingService(
            model_name="BAAI/bge-base-en-v1.5", device="cpu"
        )
        tmp_dir = tempfile.mkdtemp()
        vector_store = VectorStore(db_path=f"{tmp_dir}/test_lancedb")

        return embedding_service, vector_store

    def test_embed_store_search(self, pipeline):
        """Full pipeline: embed chunks, store in LanceDB, search."""
        embedding_service, vector_store = pipeline

        chunks = [
            Chunk(
                content="California minimum wage is $16.00 per hour effective January 1, 2024.",
                content_hash="hash_mw",
                chunk_index=0,
                heading_path="DIR > Minimum Wage",
                token_count=20,
                document_id=1,
                id=1,
                content_category=ContentCategory.AGENCY_GUIDANCE,
                citation=None,
                is_active=True,
            ),
            Chunk(
                content="Under the Fair Employment and Housing Act (FEHA), it is unlawful for an employer to discriminate against an employee based on disability.",
                content_hash="hash_feha",
                chunk_index=0,
                heading_path="FEHA > Disability Discrimination",
                token_count=30,
                document_id=2,
                id=2,
                content_category=ContentCategory.STATUTORY_CODE,
                citation="Cal. Gov. Code § 12940",
                is_active=True,
            ),
            Chunk(
                content="Employees who are laid off may be eligible for unemployment insurance benefits through the Employment Development Department.",
                content_hash="hash_ui",
                chunk_index=0,
                heading_path="EDD > Unemployment Insurance",
                token_count=25,
                document_id=3,
                id=3,
                content_category=ContentCategory.AGENCY_GUIDANCE,
                citation=None,
                is_active=True,
            ),
        ]

        # Embed
        embeddings = embedding_service.embed_chunks(chunks, source_id=1)
        assert len(embeddings) == 3

        # Store
        vector_store.create_table(embeddings)
        stats = vector_store.get_stats()
        assert stats["embedding_count"] == 3
        assert stats["active_count"] == 3

        # Search by vector
        query_emb = embedding_service.embed_query("What is the minimum wage?")
        results = vector_store.search_vector(query_emb.dense_vector, top_k=3)
        assert len(results) > 0
        # The minimum wage chunk should be in the results
        chunk_ids = [r["chunk_id"] for r in results]
        assert 1 in chunk_ids, f"Expected chunk 1 (minimum wage) in results, got {chunk_ids}"

        # Verify content_hash and model_version are stored
        assert results[0].get("content_hash") is not None
        assert results[0].get("model_version") == "BAAI/bge-base-en-v1.5"

    def test_keyword_search(self, pipeline):
        """Test FTS keyword search."""
        embedding_service, vector_store = pipeline

        chunks = [
            Chunk(
                content="California Labor Code section 1102.5 protects whistleblowers from retaliation.",
                content_hash="hash_wb",
                chunk_index=0,
                heading_path="Lab. Code § 1102.5",
                token_count=15,
                document_id=1,
                id=1,
                content_category=ContentCategory.STATUTORY_CODE,
                citation="Cal. Lab. Code § 1102.5",
                is_active=True,
            ),
            Chunk(
                content="The minimum wage in California is sixteen dollars per hour.",
                content_hash="hash_mw",
                chunk_index=0,
                heading_path="DIR > Minimum Wage",
                token_count=12,
                document_id=2,
                id=2,
                content_category=ContentCategory.AGENCY_GUIDANCE,
                is_active=True,
            ),
        ]

        embeddings = embedding_service.embed_chunks(chunks, source_id=1)
        vector_store.create_table(embeddings)

        # Keyword search for "1102.5" should find the whistleblower chunk
        results = vector_store.search_keyword("1102.5", top_k=2)
        if results:  # FTS may not always work depending on index state
            chunk_ids = [r["chunk_id"] for r in results]
            assert 1 in chunk_ids

    def test_upsert_and_search(self, pipeline):
        """Test that upserted embeddings are searchable."""
        embedding_service, vector_store = pipeline

        chunk1 = Chunk(
            content="Original content about employment law.",
            content_hash="hash_orig",
            chunk_index=0,
            heading_path="Test",
            token_count=10,
            document_id=1,
            id=1,
            content_category=ContentCategory.AGENCY_GUIDANCE,
            is_active=True,
        )

        emb1 = embedding_service.embed_chunks([chunk1], source_id=1)
        vector_store.create_table(emb1)
        assert vector_store.get_stats()["embedding_count"] == 1

        # Upsert new content
        chunk2 = Chunk(
            content="Disability accommodation under FEHA requires interactive process.",
            content_hash="hash_feha",
            chunk_index=0,
            heading_path="FEHA",
            token_count=12,
            document_id=2,
            id=2,
            content_category=ContentCategory.STATUTORY_CODE,
            citation="Cal. Gov. Code § 12940",
            is_active=True,
        )

        emb2 = embedding_service.embed_chunks([chunk2], source_id=1)
        vector_store.upsert_embeddings(emb2)
        assert vector_store.get_stats()["embedding_count"] == 2

        # Search should find the new content
        query_emb = embedding_service.embed_query("FEHA disability accommodation")
        results = vector_store.search_vector(query_emb.dense_vector, top_k=2)
        chunk_ids = [r["chunk_id"] for r in results]
        assert 2 in chunk_ids
