"""Tests for case law content category and chunking strategy (4C.1 + 4C.2)."""

from __future__ import annotations

import pytest

from employee_help.processing.chunker import (
    ChunkResult,
    chunk_case_law,
    content_hash,
    estimate_tokens,
)
from employee_help.retrieval.service import CONSUMER_CATEGORIES, RetrievalResult
from employee_help.storage.models import ContentCategory


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CASE_CITATION = "Tameny v. Atlantic Richfield Co. (1980) 27 Cal.3d 167"
HEADING_PATH = "Case Law > Employment > Wrongful Termination"

SHORT_OPINION = (
    "The plaintiff was terminated after refusing to participate in an illegal "
    "price-fixing scheme. The court held that an employer may not discharge an "
    "employee for refusing to violate a statute. This establishes the tort of "
    "wrongful termination in violation of public policy under California law."
)

def _make_long_opinion(paragraphs: int = 20, words_per_para: int = 200) -> str:
    """Generate a multi-paragraph opinion text exceeding default max_tokens."""
    paras = []
    for i in range(paragraphs):
        words = " ".join(f"word{i}_{j}" for j in range(words_per_para))
        paras.append(f"Paragraph {i + 1}. {words}")
    return "\n\n".join(paras)


def _make_single_long_paragraph(word_count: int = 3000) -> str:
    """Generate a single paragraph with no double-newline breaks."""
    sentences = []
    for i in range(word_count // 10):
        sentences.append(f"Sentence number {i} contains several words that form a complete thought.")
    return " ".join(sentences)


# ---------------------------------------------------------------------------
# ContentCategory enum tests (4C.1)
# ---------------------------------------------------------------------------

class TestContentCategoryEnum:
    def test_case_law_exists(self):
        assert ContentCategory.CASE_LAW == "case_law"
        assert ContentCategory.CASE_LAW.value == "case_law"

    def test_case_law_excluded_from_consumer_categories(self):
        assert "case_law" not in CONSUMER_CATEGORIES

    def test_all_consumer_categories_still_present(self):
        expected = {"agency_guidance", "fact_sheet", "faq", "opinion_letter", "enforcement_manual", "federal_guidance", "legal_aid_resource"}
        assert CONSUMER_CATEGORIES == expected


# ---------------------------------------------------------------------------
# Short opinion tests
# ---------------------------------------------------------------------------

class TestShortOpinion:
    def test_single_chunk(self):
        chunks = chunk_case_law(SHORT_OPINION, CASE_CITATION, HEADING_PATH)
        assert len(chunks) == 1

    def test_content_preserved(self):
        chunks = chunk_case_law(SHORT_OPINION, CASE_CITATION, HEADING_PATH)
        assert chunks[0].content == SHORT_OPINION

    def test_heading_path(self):
        chunks = chunk_case_law(SHORT_OPINION, CASE_CITATION, HEADING_PATH)
        assert chunks[0].heading_path == HEADING_PATH

    def test_chunk_index_zero(self):
        chunks = chunk_case_law(SHORT_OPINION, CASE_CITATION, HEADING_PATH)
        assert chunks[0].chunk_index == 0

    def test_token_count_accurate(self):
        chunks = chunk_case_law(SHORT_OPINION, CASE_CITATION, HEADING_PATH)
        assert chunks[0].token_count == estimate_tokens(SHORT_OPINION)

    def test_content_hash_correct(self):
        chunks = chunk_case_law(SHORT_OPINION, CASE_CITATION, HEADING_PATH)
        assert chunks[0].content_hash == content_hash(SHORT_OPINION)


# ---------------------------------------------------------------------------
# Long opinion tests
# ---------------------------------------------------------------------------

class TestLongOpinion:
    def test_multiple_chunks(self):
        text = _make_long_opinion()
        chunks = chunk_case_law(text, CASE_CITATION, HEADING_PATH)
        assert len(chunks) > 1

    def test_first_chunk_no_citation_header(self):
        text = _make_long_opinion()
        chunks = chunk_case_law(text, CASE_CITATION, HEADING_PATH)
        assert not chunks[0].content.startswith(f"[{CASE_CITATION}]")

    def test_continuation_chunks_have_citation_header(self):
        text = _make_long_opinion()
        chunks = chunk_case_law(text, CASE_CITATION, HEADING_PATH)
        for chunk in chunks[1:]:
            assert chunk.content.startswith(f"[{CASE_CITATION}]\n\n"), (
                f"Chunk {chunk.chunk_index} missing citation header"
            )

    def test_heading_path_on_all_chunks(self):
        text = _make_long_opinion()
        chunks = chunk_case_law(text, CASE_CITATION, HEADING_PATH)
        for chunk in chunks:
            assert chunk.heading_path == HEADING_PATH

    def test_chunk_indices_sequential(self):
        text = _make_long_opinion()
        chunks = chunk_case_law(text, CASE_CITATION, HEADING_PATH)
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_content_hash_uniqueness(self):
        text = _make_long_opinion()
        chunks = chunk_case_law(text, CASE_CITATION, HEADING_PATH)
        hashes = [c.content_hash for c in chunks]
        assert len(hashes) == len(set(hashes)), "Duplicate content hashes found"

    def test_token_counts_within_limit(self):
        max_tokens = 1500
        text = _make_long_opinion()
        chunks = chunk_case_law(text, CASE_CITATION, HEADING_PATH, max_tokens=max_tokens)
        for chunk in chunks:
            # Allow some tolerance for the citation header + boundary effects
            assert chunk.token_count <= max_tokens * 1.2, (
                f"Chunk {chunk.chunk_index} has {chunk.token_count} tokens "
                f"(limit {max_tokens})"
            )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_text(self):
        assert chunk_case_law("", CASE_CITATION, HEADING_PATH) == []

    def test_whitespace_only(self):
        assert chunk_case_law("   \n\n  ", CASE_CITATION, HEADING_PATH) == []

    def test_custom_max_tokens(self):
        text = _make_long_opinion(paragraphs=10, words_per_para=100)
        chunks_default = chunk_case_law(text, CASE_CITATION, HEADING_PATH)
        chunks_small = chunk_case_law(text, CASE_CITATION, HEADING_PATH, max_tokens=500)
        assert len(chunks_small) >= len(chunks_default)

    def test_very_long_single_paragraph(self):
        text = _make_single_long_paragraph(word_count=3000)
        chunks = chunk_case_law(text, CASE_CITATION, HEADING_PATH, max_tokens=500)
        assert len(chunks) > 1

    def test_returns_chunk_result_type(self):
        chunks = chunk_case_law(SHORT_OPINION, CASE_CITATION, HEADING_PATH)
        for chunk in chunks:
            assert isinstance(chunk, ChunkResult)


# ---------------------------------------------------------------------------
# Attorney mode scoring boost
# ---------------------------------------------------------------------------

class TestAttorneyModeScoring:
    def test_case_law_boost_applied(self):
        """Verify case_law gets 1.25x boost in attorney mode scoring."""
        from unittest.mock import MagicMock

        from employee_help.retrieval.service import RetrievalService

        service = RetrievalService(
            vector_store=MagicMock(),
            embedding_service=MagicMock(),
        )

        candidate = RetrievalResult(
            chunk_id=1,
            document_id=1,
            source_id=1,
            content="test",
            heading_path="test",
            content_category="case_law",
            citation=None,
            relevance_score=1.0,
        )

        processed = MagicMock()
        processed.has_citation = False
        processed.cited_section = None

        service._apply_mode_scoring([candidate], "attorney", processed)
        assert candidate.relevance_score == pytest.approx(1.25)

    def test_case_law_no_boost_consumer_mode(self):
        """Verify case_law gets no boost in consumer mode."""
        from unittest.mock import MagicMock

        from employee_help.retrieval.service import RetrievalService

        service = RetrievalService(
            vector_store=MagicMock(),
            embedding_service=MagicMock(),
        )

        candidate = RetrievalResult(
            chunk_id=1,
            document_id=1,
            source_id=1,
            content="test",
            heading_path="test",
            content_category="case_law",
            citation=None,
            relevance_score=1.0,
        )

        processed = MagicMock()
        processed.has_citation = False

        service._apply_mode_scoring([candidate], "consumer", processed)
        assert candidate.relevance_score == pytest.approx(1.0)
