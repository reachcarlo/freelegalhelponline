"""Search utilities for querying stored chunks.

Provides full-text search and keyword-based retrieval from the database.
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from employee_help.storage.models import Chunk
from employee_help.storage.storage import Storage

logger = structlog.get_logger()


@dataclass
class SearchResult:
    """Result from a chunk search."""

    chunk_id: int
    document_url: str
    heading_path: str
    content: str
    token_count: int
    relevance_score: float


class ChunkSearch:
    """Search stored chunks by keyword."""

    def __init__(self, db_path: str = "data/employee_help.db") -> None:
        """Initialize search with database.

        Args:
            db_path: Path to the SQLite database.
        """
        self.storage = Storage(db_path)
        self.logger = structlog.get_logger(__name__)

    def search(self, query: str, top_k: int = 5, min_score: float = 0.1) -> list[SearchResult]:
        """Search for chunks matching the query.

        Uses simple keyword matching with relevance scoring based on:
        - Number of query terms found in chunk
        - Position in heading (more relevant if in heading)
        - Token count (prefer more substantial chunks)

        Args:
            query: Search query (keywords separated by spaces).
            top_k: Maximum number of results to return.
            min_score: Minimum relevance score threshold.

        Returns:
            List of SearchResult objects ranked by relevance.
        """
        query_terms = [term.lower() for term in query.split()]
        results = []

        # Get all chunks and score them
        all_chunks = self.storage.get_all_chunks()
        all_docs = self.storage.get_all_documents()

        for chunk in all_chunks:
            # Calculate relevance score
            score = self._score_chunk(chunk, query_terms)

            if score >= min_score:
                # Find the document for this chunk
                doc_url = ""
                for doc in all_docs:
                    if doc.id == chunk.document_id:
                        doc_url = doc.source_url
                        break

                result = SearchResult(
                    chunk_id=chunk.id or 0,
                    document_url=doc_url,
                    heading_path=chunk.heading_path,
                    content=chunk.content,
                    token_count=chunk.token_count,
                    relevance_score=score,
                )
                results.append(result)

        # Sort by relevance and return top_k
        results.sort(key=lambda r: r.relevance_score, reverse=True)
        return results[:top_k]

    def _score_chunk(self, chunk: Chunk, query_terms: list[str]) -> float:
        """Score a chunk's relevance to the query.

        Args:
            chunk: Chunk to score.
            query_terms: List of query terms to match.

        Returns:
            Relevance score from 0 to 1.
        """
        if not query_terms:
            return 0.0

        # Combine heading and content for matching
        text = (chunk.heading_path + " " + chunk.content).lower()

        # Count matches
        matches = 0
        for term in query_terms:
            if term in text:
                matches += 1

        # Base score: proportion of query terms found
        base_score = matches / len(query_terms)

        # Boost score if matches are in heading (higher relevance)
        heading_text = chunk.heading_path.lower()
        heading_matches = sum(1 for term in query_terms if term in heading_text)
        heading_boost = (heading_matches / len(query_terms)) * 0.3

        # Boost score for substantial chunks (not too small)
        size_boost = 0.0
        if chunk.token_count >= 300:
            size_boost = 0.1

        final_score = base_score + heading_boost + size_boost
        return min(1.0, final_score)

    def close(self) -> None:
        """Close database connection."""
        self.storage.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, *exc):
        """Context manager exit."""
        self.close()
