"""Reranker using cross-encoder model for re-scoring retrieval candidates.

Applies a more accurate but slower model to re-order the top candidates
from initial retrieval, ensuring the final results are truly the most relevant.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from employee_help.retrieval.service import RetrievalResult

logger = structlog.get_logger()


class Reranker:
    """Cross-encoder reranker for improving retrieval precision."""

    def __init__(
        self,
        model_name: str = "mixedbread-ai/mxbai-rerank-base-v2",
        device: str = "cpu",
    ) -> None:
        self.model_name = model_name
        self.device = device
        self._model = None
        self.logger = structlog.get_logger(__name__, model=model_name)

    def _load_model(self) -> None:
        """Lazy-load the reranker model."""
        if self._model is not None:
            return

        self.logger.info("loading_reranker_model")
        try:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(
                self.model_name,
                device=self.device,
            )
            self.logger.info("reranker_model_loaded")
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for reranking. "
                "Install with: uv pip install -e '.[rag]'"
            )

    @property
    def model(self):
        self._load_model()
        return self._model

    def rerank(
        self,
        query: str,
        candidates: list[RetrievalResult],
        top_k: int = 10,
    ) -> list[RetrievalResult]:
        """Re-score candidates using the cross-encoder model.

        Args:
            query: The original search query.
            candidates: List of RetrievalResult from initial retrieval.
            top_k: Number of top results to return after reranking.

        Returns:
            Reranked list of RetrievalResult, sorted by cross-encoder score.
        """
        if not candidates:
            return []

        if len(candidates) <= 1:
            return candidates[:top_k]

        model = self.model

        # Build query-document pairs for cross-encoder
        pairs = [(query, c.content) for c in candidates]

        # Score all pairs
        scores = model.predict(pairs)

        # Normalize scores to 0-1 range via min-max scaling
        min_score = float(min(scores))
        max_score = float(max(scores))
        score_range = max_score - min_score

        for i, candidate in enumerate(candidates):
            raw_score = float(scores[i])
            if score_range > 0:
                candidate.reranker_score = (raw_score - min_score) / score_range
            else:
                # All scores equal: preserve hybrid search ordering via
                # a small descending offset so stable sort keeps original rank.
                candidate.reranker_score = 1.0 - (i / max(len(candidates), 1))
            # Blend reranker score with original hybrid score to avoid
            # completely discarding retrieval signal.
            original = candidate.relevance_score or 0.0
            candidate.relevance_score = (
                0.7 * candidate.reranker_score + 0.3 * original
            )

        # Sort by reranker score and return top_k
        candidates.sort(key=lambda c: c.relevance_score, reverse=True)

        self.logger.debug(
            "reranking_complete",
            candidates_in=len(candidates),
            candidates_out=min(top_k, len(candidates)),
        )

        return candidates[:top_k]
