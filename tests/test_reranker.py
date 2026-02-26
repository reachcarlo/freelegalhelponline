"""Tests for the reranker."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from employee_help.retrieval.reranker import Reranker
from employee_help.retrieval.service import RetrievalResult


def _make_result(chunk_id: int, content: str, score: float = 0.5) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        document_id=1,
        source_id=1,
        content=content,
        heading_path="Test",
        content_category="statutory_code",
        citation=None,
        relevance_score=score,
    )


class TestReranker:
    """Tests for Reranker with mocked model."""

    @pytest.fixture
    def mock_model(self):
        import numpy as np

        model = MagicMock()
        model.predict.return_value = np.array([0.9, 0.3, 0.7, 0.1, 0.5])
        return model

    @pytest.fixture
    def reranker(self, mock_model):
        rr = Reranker(model_name="test-model", device="cpu")
        rr._model = mock_model
        return rr

    def test_rerank_returns_top_k(self, reranker):
        candidates = [
            _make_result(i, f"content {i}") for i in range(5)
        ]
        results = reranker.rerank("test query", candidates, top_k=3)
        assert len(results) == 3

    def test_rerank_orders_by_score(self, reranker):
        candidates = [
            _make_result(i, f"content {i}") for i in range(5)
        ]
        results = reranker.rerank("test query", candidates, top_k=5)
        scores = [r.relevance_score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_rerank_normalizes_scores(self, reranker):
        candidates = [
            _make_result(i, f"content {i}") for i in range(5)
        ]
        results = reranker.rerank("test query", candidates, top_k=5)
        for r in results:
            assert 0.0 <= r.relevance_score <= 1.0

    def test_rerank_sets_reranker_score(self, reranker):
        candidates = [
            _make_result(i, f"content {i}") for i in range(5)
        ]
        results = reranker.rerank("test query", candidates, top_k=5)
        for r in results:
            assert r.reranker_score is not None

    def test_rerank_empty_candidates(self, reranker):
        results = reranker.rerank("test", [], top_k=5)
        assert results == []

    def test_rerank_single_candidate(self, reranker):
        candidates = [_make_result(1, "content")]
        results = reranker.rerank("test", candidates, top_k=5)
        assert len(results) == 1

    def test_model_called_with_pairs(self, reranker, mock_model):
        candidates = [
            _make_result(1, "content A"),
            _make_result(2, "content B"),
        ]

        import numpy as np
        mock_model.predict.return_value = np.array([0.8, 0.3])

        reranker.rerank("test query", candidates, top_k=2)

        mock_model.predict.assert_called_once()
        pairs = mock_model.predict.call_args[0][0]
        assert len(pairs) == 2
        assert pairs[0] == ("test query", "content A")
        assert pairs[1] == ("test query", "content B")

    def test_equal_scores_preserve_order(self, reranker, mock_model):
        """When all cross-encoder scores are equal, original order is preserved."""
        import numpy as np

        mock_model.predict.return_value = np.array([0.5, 0.5, 0.5])
        candidates = [
            _make_result(1, "first", score=0.9),
            _make_result(2, "second", score=0.8),
            _make_result(3, "third", score=0.7),
        ]
        results = reranker.rerank("test", candidates, top_k=3)
        # With equal scores, the tie-breaking offset should maintain order
        ids = [r.chunk_id for r in results]
        assert ids == [1, 2, 3]

    def test_blended_score(self, reranker, mock_model):
        """Relevance score should blend reranker and original scores."""
        import numpy as np

        mock_model.predict.return_value = np.array([0.9, 0.1])
        candidates = [
            _make_result(1, "content A", score=0.5),
            _make_result(2, "content B", score=0.5),
        ]
        results = reranker.rerank("test", candidates, top_k=2)
        # The top result should have higher blended score
        assert results[0].relevance_score > results[1].relevance_score
        # Score should be a blend, not purely reranker
        assert results[0].relevance_score < 1.0
