"""Tests for the content chunker."""

import pytest

from employee_help.processing.chunker import (
    ChunkResult,
    chunk_document,
    content_hash,
    estimate_tokens,
)


class TestEstimateTokens:
    def test_empty_string(self) -> None:
        assert estimate_tokens("") == 1  # Minimum 1

    def test_short_text(self) -> None:
        # "hello world" = 11 chars -> ~2-3 tokens
        tokens = estimate_tokens("hello world")
        assert 1 <= tokens <= 5

    def test_longer_text(self) -> None:
        text = "California law protects individuals from illegal discrimination by employers."
        tokens = estimate_tokens(text)
        assert 10 < tokens < 30


class TestContentHash:
    def test_deterministic(self) -> None:
        text = "Same content"
        assert content_hash(text) == content_hash(text)

    def test_different_content_different_hash(self) -> None:
        assert content_hash("text A") != content_hash("text B")

    def test_returns_hex_string(self) -> None:
        h = content_hash("test")
        assert len(h) == 64  # SHA-256 hex digest


class TestChunkDocument:
    def test_empty_document(self) -> None:
        assert chunk_document("") == []
        assert chunk_document("   ") == []

    def test_small_document_single_chunk(self) -> None:
        text = "## Title\n\nShort paragraph about employment law."
        chunks = chunk_document(text, min_tokens=10, max_tokens=500)
        assert len(chunks) >= 1
        assert chunks[0].chunk_index == 0
        assert "employment law" in chunks[0].content

    def test_heading_path_propagation(self) -> None:
        # Each section must exceed min_tokens, and total must exceed max_tokens
        # so sections don't all merge into one chunk
        text = (
            "# Employment\n\n"
            "## Protected Categories\n\n"
            + "California law protects individuals from discrimination based on race, color, and ancestry. " * 20
            + "\n\n## Remedies\n\n"
            + "Back pay and front pay are available remedies under the Fair Employment and Housing Act. " * 20
        )
        chunks = chunk_document(text, min_tokens=50, max_tokens=500, document_title="CRD Guide")
        assert len(chunks) >= 2, f"Expected >= 2 chunks, got {len(chunks)}"
        paths = [c.heading_path for c in chunks]
        assert any("Protected Categories" in p for p in paths)
        assert any("Remedies" in p for p in paths)

    def test_document_title_in_heading_path(self) -> None:
        text = "## Section\n\nContent here."
        chunks = chunk_document(text, min_tokens=10, max_tokens=500, document_title="Employment Guide")
        assert chunks[0].heading_path.startswith("Employment Guide")

    def test_respects_max_token_limit(self) -> None:
        # Create a long document that should be split
        paragraphs = [f"Paragraph {i}. " + "word " * 100 for i in range(10)]
        text = "## Long Section\n\n" + "\n\n".join(paragraphs)
        chunks = chunk_document(text, min_tokens=50, max_tokens=300)
        for chunk in chunks:
            assert chunk.token_count <= 350  # Allow small overshoot from overlap

    def test_chunk_indices_sequential(self) -> None:
        text = (
            "## Section A\n\nContent A is here.\n\n"
            "## Section B\n\nContent B is here.\n\n"
            "## Section C\n\nContent C is here."
        )
        chunks = chunk_document(text, min_tokens=5, max_tokens=500)
        indices = [c.chunk_index for c in chunks]
        assert indices == list(range(len(chunks)))

    def test_each_chunk_has_hash(self) -> None:
        text = "## Title\n\nParagraph one.\n\n## Other\n\nParagraph two."
        chunks = chunk_document(text, min_tokens=5, max_tokens=500)
        for chunk in chunks:
            assert len(chunk.content_hash) == 64

    def test_hash_determinism(self) -> None:
        text = "## Title\n\nConsistent content here."
        chunks1 = chunk_document(text, min_tokens=5, max_tokens=500)
        chunks2 = chunk_document(text, min_tokens=5, max_tokens=500)
        assert chunks1[0].content_hash == chunks2[0].content_hash

    def test_small_sections_merged(self) -> None:
        text = "## A\n\nTiny.\n\n## B\n\nAlso tiny."
        chunks = chunk_document(text, min_tokens=100, max_tokens=500)
        # Both sections are too small individually; should be merged
        assert len(chunks) <= 2

    def test_overlap_between_large_chunks(self) -> None:
        """When a section is split, adjacent chunks should share some content."""
        # Create a very long section with short paragraphs so overlap can grab them
        paragraphs = [f"Point {i}: this is a short statement." for i in range(40)]
        text = "## Large Section\n\n" + "\n\n".join(paragraphs)
        chunks = chunk_document(text, min_tokens=50, max_tokens=300, overlap_tokens=150)

        # Must produce multiple chunks
        assert len(chunks) >= 2, f"Expected >= 2 chunks, got {len(chunks)}"

        # Verify overlap: the last paragraph of chunk N should appear in chunk N+1
        for i in range(len(chunks) - 1):
            last_para = chunks[i].content.split("\n\n")[-1]
            assert last_para in chunks[i + 1].content, (
                f"Expected overlap between chunk {i} and {i+1}"
            )

    def test_multiple_heading_levels(self) -> None:
        text = (
            "# Top Level\n\n"
            + "Introduction to the topic with enough text to avoid merging. " * 15
            + "\n\n## Sub Level\n\n"
            + "Sub level content with enough substance to stand alone. " * 15
            + "\n\n### Sub Sub Level\n\n"
            + "Deep content about a very specific topic in employment law. " * 15
        )
        chunks = chunk_document(text, min_tokens=50, max_tokens=2000, document_title="Doc")
        paths = [c.heading_path for c in chunks]
        assert any("Sub Level" in p for p in paths)
