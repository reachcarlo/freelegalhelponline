"""Tests for the retrieval service."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from employee_help.retrieval.embedder import EmbeddingResult, EmbeddingService
from employee_help.retrieval.query import QueryPreprocessor
from employee_help.retrieval.reranker import Reranker
from employee_help.retrieval.service import CONSUMER_CATEGORIES, RetrievalResult, RetrievalService
from employee_help.retrieval.vector_store import VectorStore


def _make_raw_result(chunk_id: int, category: str = "statutory_code", **kwargs):
    """Helper to create a raw LanceDB result dict."""
    defaults = {
        "chunk_id": chunk_id,
        "document_id": chunk_id * 10,
        "source_id": 1,
        "content": f"Content for chunk {chunk_id}",
        "heading_path": f"Path > Chunk {chunk_id}",
        "content_category": category,
        "citation": f"§ {chunk_id}" if category == "statutory_code" else None,
        "source_url": f"https://example.com/{chunk_id}",
        "content_hash": f"hash_{chunk_id}",
        "_relevance_score": 0.9 - chunk_id * 0.1,
        "is_active": True,
    }
    defaults.update(kwargs)
    return defaults


@pytest.fixture
def mock_embedding_service():
    svc = MagicMock(spec=EmbeddingService)
    svc.embed_query.return_value = EmbeddingResult(
        dense_vector=[0.1] * 768,
    )
    return svc


@pytest.fixture
def mock_vector_store():
    store = MagicMock(spec=VectorStore)
    store.search_hybrid.return_value = [
        _make_raw_result(1, "statutory_code"),
        _make_raw_result(2, "agency_guidance"),
        _make_raw_result(3, "fact_sheet"),
        _make_raw_result(4, "statutory_code"),
        _make_raw_result(5, "faq"),
    ]
    return store


@pytest.fixture
def mock_reranker():
    rr = MagicMock(spec=Reranker)
    # Reranker returns candidates in same order but with reranker scores
    def fake_rerank(query, candidates, top_k):
        for i, c in enumerate(candidates):
            c.reranker_score = 1.0 - i * 0.1
            c.relevance_score = c.reranker_score
        return candidates[:top_k]
    rr.rerank.side_effect = fake_rerank
    return rr


@pytest.fixture
def service(mock_vector_store, mock_embedding_service, mock_reranker):
    return RetrievalService(
        vector_store=mock_vector_store,
        embedding_service=mock_embedding_service,
        reranker=mock_reranker,
        top_k_search=50,
        top_k_rerank=10,
        top_k_final=5,
    )


class TestRetrievalService:
    """Tests for the main RetrievalService."""

    def test_retrieve_returns_results(self, service):
        results = service.retrieve("test query", mode="consumer")
        assert len(results) > 0

    def test_retrieve_uses_embed_query(self, service, mock_embedding_service):
        """Should use embed_query (with BGE prefix), not embed_text."""
        service.retrieve("test query", mode="consumer")
        mock_embedding_service.embed_query.assert_called_once()
        mock_embedding_service.embed_text.assert_not_called()

    def test_retrieve_consumer_mode(self, service, mock_vector_store):
        service.retrieve("test query", mode="consumer")
        # Check that filter was applied
        call_kwargs = mock_vector_store.search_hybrid.call_args
        filter_expr = call_kwargs.kwargs.get("filter_expr") or call_kwargs[1].get("filter_expr")
        assert "content_category" in filter_expr
        assert "agency_guidance" in filter_expr

    def test_retrieve_attorney_mode_no_category_filter(self, service, mock_vector_store):
        service.retrieve("test query", mode="attorney")
        call_kwargs = mock_vector_store.search_hybrid.call_args
        filter_expr = call_kwargs.kwargs.get("filter_expr") or call_kwargs[1].get("filter_expr")
        # Attorney mode should only filter by is_active, not content_category
        assert "content_category" not in filter_expr

    def test_retrieve_respects_top_k(self, service):
        results = service.retrieve("test query", mode="consumer", top_k=2)
        assert len(results) <= 2

    def test_retrieve_empty_results(self, service, mock_vector_store):
        mock_vector_store.search_hybrid.return_value = []
        results = service.retrieve("obscure query", mode="consumer")
        assert results == []

    def test_retrieve_results_have_content_hash(self, service):
        results = service.retrieve("test query", mode="attorney")
        for r in results:
            assert hasattr(r, "content_hash")

    def test_attorney_mode_statutory_boost(self, service, mock_vector_store):
        """Attorney mode should boost statutory_code chunks."""
        mock_vector_store.search_hybrid.return_value = [
            _make_raw_result(1, "agency_guidance", _relevance_score=0.8),
            _make_raw_result(2, "statutory_code", _relevance_score=0.8),
        ]

        results = service.retrieve("test query", mode="attorney")

        statutory_results = [r for r in results if r.content_category == "statutory_code"]
        agency_results = [r for r in results if r.content_category == "agency_guidance"]

        assert len(statutory_results) > 0, "Expected statutory results"
        assert len(agency_results) > 0, "Expected agency results"
        assert statutory_results[0].relevance_score >= agency_results[0].relevance_score

    def test_citation_boost(self, service, mock_vector_store):
        """Citation queries should boost matching chunks."""
        mock_vector_store.search_hybrid.return_value = [
            _make_raw_result(1, "statutory_code", citation="Cal. Lab. Code § 1102.5"),
            _make_raw_result(2, "statutory_code", citation="Cal. Lab. Code § 98.6"),
        ]

        results = service.retrieve(
            "Lab. Code section 1102.5", mode="attorney"
        )

        assert len(results) >= 2, "Expected at least 2 results"
        matching = [r for r in results if r.citation and "1102.5" in r.citation]
        non_matching = [r for r in results if r.citation and "1102.5" not in r.citation]
        assert len(matching) > 0, "Expected matching citation result"
        assert len(non_matching) > 0, "Expected non-matching citation result"
        assert matching[0].relevance_score >= non_matching[0].relevance_score

    def test_reranker_failure_falls_back(self, service, mock_reranker, mock_vector_store):
        """Reranker failure should fall back to hybrid search scores."""
        mock_reranker.rerank.side_effect = RuntimeError("model failed")
        results = service.retrieve("test query", mode="consumer")
        # Should still return results (from hybrid search, unreranked)
        assert len(results) > 0


class TestDeduplication:
    """Tests for result deduplication."""

    def test_duplicate_content_removed(self, service, mock_vector_store):
        mock_vector_store.search_hybrid.return_value = [
            _make_raw_result(1, content="Same content here", content_hash="same_hash"),
            _make_raw_result(2, content="Same content here", content_hash="same_hash"),
            _make_raw_result(3, content="Different content", content_hash="diff_hash"),
        ]

        results = service.retrieve("test", mode="attorney")
        contents = [r.content for r in results]
        assert len(set(contents)) == len(contents)

    def test_dedup_uses_content_hash(self, service, mock_vector_store):
        """Dedup should prefer content_hash over content prefix."""
        mock_vector_store.search_hybrid.return_value = [
            _make_raw_result(1, content="Different text A", content_hash="shared_hash"),
            _make_raw_result(2, content="Different text B", content_hash="shared_hash"),
            _make_raw_result(3, content="Other text", content_hash="unique_hash"),
        ]

        results = service.retrieve("test", mode="attorney")
        # Should deduplicate by hash even though content differs
        assert len(results) == 2


class TestSourceDiversity:
    """Tests for source diversity enforcement."""

    def test_max_per_document(self, service, mock_vector_store):
        # All from same document
        mock_vector_store.search_hybrid.return_value = [
            _make_raw_result(i, document_id=1) for i in range(10)
        ]

        results = service.retrieve("test", mode="attorney")
        assert len(results) <= service.diversity_max_per_doc


class TestFilterBuilding:
    """Tests for filter expression building."""

    def test_consumer_filter(self, service):
        filter_expr = service._build_filter("consumer")
        assert "is_active = true" in filter_expr
        assert "content_category" in filter_expr

    def test_attorney_filter(self, service):
        filter_expr = service._build_filter("attorney")
        assert "is_active = true" in filter_expr
        assert "content_category" not in filter_expr

    def test_consumer_filter_excludes_jury_instruction(self, service):
        """Consumer mode should exclude jury_instruction content."""
        filter_expr = service._build_filter("consumer")
        assert "jury_instruction" not in filter_expr
        # jury_instruction is not in CONSUMER_CATEGORIES
        assert "jury_instruction" not in CONSUMER_CATEGORIES


class TestJuryInstructionBoost:
    """Tests for CACI jury instruction scoring in attorney mode."""

    def test_attorney_mode_jury_instruction_boost(self, service, mock_vector_store):
        """Attorney mode should boost jury_instruction chunks by 1.3x."""
        mock_vector_store.search_hybrid.return_value = [
            _make_raw_result(1, "agency_guidance", _relevance_score=0.8),
            _make_raw_result(
                2, "jury_instruction",
                _relevance_score=0.8,
                citation="CACI No. 2430",
            ),
        ]
        results = service.retrieve("wrongful discharge elements", mode="attorney")

        jury_results = [r for r in results if r.content_category == "jury_instruction"]
        agency_results = [r for r in results if r.content_category == "agency_guidance"]

        assert len(jury_results) > 0, "Expected jury_instruction results"
        assert len(agency_results) > 0, "Expected agency results"
        assert jury_results[0].relevance_score > agency_results[0].relevance_score

    def test_consumer_mode_no_jury_instructions(self, service, mock_vector_store):
        """Consumer mode filter should not include jury_instruction."""
        filter_expr = service._build_filter("consumer")
        # The filter uses CONSUMER_CATEGORIES which doesn't include jury_instruction
        assert "jury_instruction" not in filter_expr


class TestCaseLawRetrieval:
    """Tests for case law retrieval in attorney and consumer modes (4C.5)."""

    def test_attorney_query_returns_case_law(self, service, mock_vector_store):
        """Attorney mode should include case_law results alongside statutes."""
        mock_vector_store.search_hybrid.return_value = [
            _make_raw_result(1, "statutory_code", _relevance_score=0.8),
            _make_raw_result(
                2, "case_law",
                _relevance_score=0.8,
                citation="Yanowitz v. L'Oreal USA, Inc. (2005) 36 Cal.4th 1028",
                content="FEHA retaliation elements require adverse employment action.",
            ),
            _make_raw_result(3, "agency_guidance", _relevance_score=0.7),
        ]
        results = service.retrieve("FEHA retaliation elements", mode="attorney")

        case_law_results = [r for r in results if r.content_category == "case_law"]
        assert len(case_law_results) > 0, "Attorney mode should return case law results"

    def test_consumer_query_excludes_case_law(self, service, mock_vector_store):
        """Consumer mode filter should exclude case_law content."""
        filter_expr = service._build_filter("consumer")
        assert "case_law" not in filter_expr
        assert "case_law" not in CONSUMER_CATEGORIES

    def test_attorney_mode_case_law_boost(self, service, mock_vector_store):
        """Attorney mode should boost case_law chunks by 1.25x."""
        mock_vector_store.search_hybrid.return_value = [
            _make_raw_result(1, "agency_guidance", _relevance_score=0.8),
            _make_raw_result(
                2, "case_law",
                _relevance_score=0.8,
                citation="Tameny v. Atlantic Richfield Co. (1980) 27 Cal.3d 167",
            ),
        ]
        results = service.retrieve("wrongful termination public policy", mode="attorney")

        case_results = [r for r in results if r.content_category == "case_law"]
        agency_results = [r for r in results if r.content_category == "agency_guidance"]

        assert len(case_results) > 0, "Expected case_law results"
        assert len(agency_results) > 0, "Expected agency results"
        # case_law gets 1.25x boost vs agency_guidance (no boost)
        assert case_results[0].relevance_score > agency_results[0].relevance_score

    def test_case_citation_query_finds_case(self, service, mock_vector_store):
        """Citation query for a specific case should find it via citation boost."""
        mock_vector_store.search_hybrid.return_value = [
            _make_raw_result(
                1, "case_law",
                _relevance_score=0.7,
                citation="Yanowitz v. L'Oreal USA, Inc. (2005) 36 Cal.4th 1028",
                content="The Yanowitz court established the framework for FEHA retaliation claims.",
            ),
            _make_raw_result(
                2, "case_law",
                _relevance_score=0.7,
                citation="Tameny v. Atlantic Richfield Co. (1980) 27 Cal.3d 167",
                content="Wrongful termination in violation of public policy.",
            ),
        ]
        results = service.retrieve("Yanowitz case FEHA", mode="attorney")
        assert len(results) > 0
        # Both should be case_law
        for r in results:
            assert r.content_category == "case_law"

    def test_case_law_mixed_with_statutory(self, service, mock_vector_store):
        """Attorney mode retrieval should return a mix of case law and statutes."""
        mock_vector_store.search_hybrid.return_value = [
            _make_raw_result(
                1, "statutory_code",
                _relevance_score=0.9,
                citation="Cal. Gov. Code § 12940",
            ),
            _make_raw_result(
                2, "case_law",
                _relevance_score=0.85,
                citation="Yanowitz v. L'Oreal USA, Inc. (2005) 36 Cal.4th 1028",
            ),
            _make_raw_result(
                3, "jury_instruction",
                _relevance_score=0.8,
                citation="CACI No. 2505",
            ),
            _make_raw_result(4, "agency_guidance", _relevance_score=0.75),
        ]
        results = service.retrieve("FEHA employment discrimination", mode="attorney")

        categories = {r.content_category for r in results}
        assert "statutory_code" in categories
        assert "case_law" in categories

    def test_case_law_deduplication(self, service, mock_vector_store):
        """Case law chunks from the same opinion should be deduplicated by content_hash."""
        mock_vector_store.search_hybrid.return_value = [
            _make_raw_result(
                1, "case_law",
                _relevance_score=0.9,
                content="Opinion text chunk 1",
                content_hash="case_hash_shared",
            ),
            _make_raw_result(
                2, "case_law",
                _relevance_score=0.85,
                content="Opinion text chunk 1 (duplicate)",
                content_hash="case_hash_shared",
            ),
            _make_raw_result(
                3, "case_law",
                _relevance_score=0.8,
                content="Different opinion chunk",
                content_hash="case_hash_unique",
            ),
        ]
        results = service.retrieve("test", mode="attorney")
        hashes = [r.content_hash for r in results]
        assert len(hashes) == len(set(hashes)), "Duplicate case law chunks should be deduplicated"

    def test_attorney_filter_includes_all_categories(self, service):
        """Attorney mode filter should not restrict by content category."""
        filter_expr = service._build_filter("attorney")
        assert "content_category" not in filter_expr
        # This means case_law, statutory_code, jury_instruction all pass through

    def test_case_law_boost_value(self):
        """Verify case_law gets exactly 1.25x boost in attorney mode."""
        svc = RetrievalService(
            vector_store=MagicMock(),
            embedding_service=MagicMock(),
        )
        candidate = RetrievalResult(
            chunk_id=1, document_id=1, source_id=1,
            content="test", heading_path="test",
            content_category="case_law",
            citation=None, relevance_score=1.0,
        )
        processed = MagicMock()
        processed.has_citation = False
        processed.cited_section = None

        svc._apply_mode_scoring([candidate], "attorney", processed)
        assert candidate.relevance_score == pytest.approx(1.25)

    def test_case_law_no_boost_in_consumer_mode(self):
        """Case law should not receive any boost in consumer mode."""
        svc = RetrievalService(
            vector_store=MagicMock(),
            embedding_service=MagicMock(),
        )
        candidate = RetrievalResult(
            chunk_id=1, document_id=1, source_id=1,
            content="test", heading_path="test",
            content_category="case_law",
            citation=None, relevance_score=1.0,
        )
        processed = MagicMock()
        processed.has_citation = False

        svc._apply_mode_scoring([candidate], "consumer", processed)
        assert candidate.relevance_score == pytest.approx(1.0)
