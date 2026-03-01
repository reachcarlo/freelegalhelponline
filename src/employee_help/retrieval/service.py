"""Retrieval service for dual-mode (consumer/attorney) search.

Orchestrates query preprocessing, hybrid search, reranking, and mode-specific
filtering to return the most relevant chunks for a given query.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import structlog

from employee_help.retrieval.embedder import EmbeddingService
from employee_help.retrieval.query import QueryPreprocessor
from employee_help.retrieval.reranker import Reranker
from employee_help.retrieval.vector_store import VectorStore

logger = structlog.get_logger()

# Content categories for consumer mode filtering
CONSUMER_CATEGORIES = {"agency_guidance", "fact_sheet", "faq"}


@dataclass
class RetrievalResult:
    """A single retrieval result with metadata."""

    chunk_id: int
    document_id: int
    source_id: int
    content: str
    heading_path: str
    content_category: str
    citation: str | None
    relevance_score: float
    source_url: str = ""
    content_hash: str = ""
    reranker_score: float | None = None
    vector_score: float | None = None
    keyword_score: float | None = None


class RetrievalService:
    """Dual-mode retrieval service combining hybrid search with reranking.

    Supports consumer mode (agency content only) and attorney mode
    (all content with statutory boosting).
    """

    def __init__(
        self,
        vector_store: VectorStore,
        embedding_service: EmbeddingService,
        reranker: Reranker | None = None,
        query_preprocessor: QueryPreprocessor | None = None,
        *,
        top_k_search: int = 50,
        top_k_rerank: int = 10,
        top_k_final: int = 5,
        citation_boost: float = 1.5,
        statutory_boost: float = 1.2,
        diversity_max_per_doc: int = 3,
        reranker_enabled: bool = True,
    ) -> None:
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.reranker = reranker
        self.query_preprocessor = query_preprocessor or QueryPreprocessor()
        self.top_k_search = top_k_search
        self.top_k_rerank = top_k_rerank
        self.top_k_final = top_k_final
        self.citation_boost = citation_boost
        self.statutory_boost = statutory_boost
        self.diversity_max_per_doc = diversity_max_per_doc
        self.reranker_enabled = reranker_enabled and reranker is not None
        self.logger = structlog.get_logger(__name__)

    def retrieve(
        self,
        query: str,
        mode: str = "consumer",
        top_k: int | None = None,
    ) -> list[RetrievalResult]:
        """Retrieve relevant chunks for a query in the given mode.

        Pipeline: preprocess -> hybrid search -> rerank -> mode filter ->
                  diversity enforcement -> top-k selection.

        Args:
            query: User's natural language question.
            mode: "consumer" or "attorney".
            top_k: Override for number of final results.

        Returns:
            Ranked list of RetrievalResult objects.
        """
        final_k = top_k or self.top_k_final

        # 1. Preprocess query
        processed = self.query_preprocessor.preprocess(query)

        # 2. Generate query embedding (with BGE retrieval instruction prefix)
        query_embedding = self.embedding_service.embed_query(
            processed.normalized_query
        )

        # 3. Build metadata filter
        filter_expr = self._build_filter(mode)

        # 4. Hybrid search
        raw_results = self.vector_store.search_hybrid(
            query_text=processed.normalized_query,
            query_vector=query_embedding.dense_vector,
            top_k=self.top_k_search,
            filter_expr=filter_expr,
        )

        if not raw_results:
            self.logger.info("no_results_found", query=query, mode=mode)
            return []

        # 5. Convert to RetrievalResult
        candidates = self._to_retrieval_results(raw_results)

        # 6. Rerank (with graceful fallback on failure)
        if self.reranker_enabled and self.reranker:
            try:
                candidates = self.reranker.rerank(
                    query=processed.normalized_query,
                    candidates=candidates,
                    top_k=self.top_k_rerank,
                )
            except Exception as e:
                self.logger.warning(
                    "reranker_failed_using_hybrid_scores",
                    error=str(e),
                )
                candidates = candidates[: self.top_k_rerank]

        # 7. Apply mode-specific scoring
        self._apply_mode_scoring(candidates, mode, processed)

        # 8. Deduplicate overlapping content
        candidates = self._deduplicate(candidates)

        # 9. Enforce source diversity
        candidates = self._enforce_diversity(candidates)

        # 10. Final sort and selection
        candidates.sort(key=lambda r: r.relevance_score, reverse=True)
        results = candidates[:final_k]

        self.logger.info(
            "retrieval_complete",
            query=query[:80],
            mode=mode,
            candidates_initial=len(raw_results),
            results_final=len(results),
        )

        return results

    def _build_filter(self, mode: str, language: str = "en") -> str | None:
        """Build LanceDB filter expression based on mode and language."""
        filters = ["is_active = true"]

        if language and "language" in self.vector_store.columns:
            filters.append(f"language = '{language}'")

        if mode == "consumer":
            categories = ", ".join(f"'{c}'" for c in CONSUMER_CATEGORIES)
            filters.append(f"content_category IN ({categories})")

        return " AND ".join(filters) if filters else None

    def _to_retrieval_results(
        self, raw_results: list[dict]
    ) -> list[RetrievalResult]:
        """Convert raw LanceDB results to RetrievalResult objects."""
        results = []
        for row in raw_results:
            score = row.get("_relevance_score") or row.get("_distance")
            if score is None:
                score = 0.0
            # LanceDB _distance is cosine distance; convert to similarity
            if "_distance" in row and "_relevance_score" not in row:
                score = max(0.0, 1.0 - float(score))
            else:
                score = float(score)

            results.append(
                RetrievalResult(
                    chunk_id=row.get("chunk_id", 0),
                    document_id=row.get("document_id", 0),
                    source_id=row.get("source_id", 0),
                    content=row.get("content", ""),
                    heading_path=row.get("heading_path", ""),
                    content_category=row.get("content_category", ""),
                    citation=row.get("citation") or None,
                    relevance_score=score,
                    source_url=row.get("source_url", ""),
                    content_hash=row.get("content_hash", ""),
                )
            )
        return results

    def _apply_mode_scoring(
        self,
        candidates: list[RetrievalResult],
        mode: str,
        processed,
    ) -> None:
        """Apply mode-specific score adjustments."""
        if mode != "attorney":
            return

        for candidate in candidates:
            # Statutory content boost in attorney mode
            if candidate.content_category == "statutory_code":
                candidate.relevance_score *= self.statutory_boost

            # CACI jury instruction boost in attorney mode
            if candidate.content_category == "jury_instruction":
                candidate.relevance_score *= 1.3

            # Case law boost in attorney mode
            if candidate.content_category == "case_law":
                candidate.relevance_score *= 1.25

            # Citation match boost — strong boost for exact section match
            if (
                processed.has_citation
                and processed.cited_section
                and candidate.citation
                and processed.cited_section in candidate.citation
            ):
                candidate.relevance_score *= self.citation_boost

                # Extra boost for exact section number match (not just substring)
                # e.g., "1102.5" should boost "§ 1102.5." more than "§ 11025."
                section = processed.cited_section
                if f"§ {section}." in candidate.citation or f"§ {section}" == candidate.citation.rstrip(".").split("§")[-1].strip():
                    candidate.relevance_score *= 2.0  # Strong exact-match bonus

    def _deduplicate(
        self, candidates: list[RetrievalResult]
    ) -> list[RetrievalResult]:
        """Remove duplicate results using content_hash or content prefix."""
        seen: set[str] = set()
        deduped: list[RetrievalResult] = []

        for candidate in candidates:
            # Prefer content_hash for exact dedup; fall back to prefix
            key = candidate.content_hash or candidate.content[:200]
            if key not in seen:
                seen.add(key)
                deduped.append(candidate)

        return deduped

    def _enforce_diversity(
        self, candidates: list[RetrievalResult]
    ) -> list[RetrievalResult]:
        """Limit results from the same document for source diversity."""
        doc_counts: dict[int, int] = {}
        diverse: list[RetrievalResult] = []

        for candidate in candidates:
            doc_id = candidate.document_id
            current_count = doc_counts.get(doc_id, 0)
            if current_count < self.diversity_max_per_doc:
                diverse.append(candidate)
                doc_counts[doc_id] = current_count + 1

        return diverse
