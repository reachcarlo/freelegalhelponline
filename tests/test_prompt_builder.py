"""Tests for the prompt builder."""

from __future__ import annotations

from pathlib import Path

import pytest

from employee_help.generation.prompts import PromptBuilder
from employee_help.retrieval.service import RetrievalResult


def _make_result(chunk_id: int, content: str = "Test content", **kwargs) -> RetrievalResult:
    defaults = {
        "chunk_id": chunk_id,
        "document_id": chunk_id * 10,
        "source_id": 1,
        "content": content,
        "heading_path": f"Test > Chunk {chunk_id}",
        "content_category": "statutory_code",
        "citation": f"Cal. Lab. Code § {chunk_id}",
        "relevance_score": 0.9,
        "source_url": f"https://example.com/{chunk_id}",
    }
    defaults.update(kwargs)
    return RetrievalResult(**defaults)


class TestPromptBuilder:
    """Tests for PromptBuilder with real templates."""

    @pytest.fixture
    def builder(self):
        return PromptBuilder(
            prompts_dir="config/prompts",
            max_context_tokens=6000,
        )

    def test_build_consumer_prompt(self, builder):
        results = [_make_result(1), _make_result(2)]
        bundle = builder.build_prompt(
            query="What is minimum wage?",
            mode="consumer",
            retrieval_results=results,
        )

        assert "legal information assistant" in bundle.system_prompt.lower()
        assert "What is minimum wage?" == bundle.user_message
        assert bundle.total_tokens_estimate > 0

    def test_build_attorney_prompt(self, builder):
        results = [_make_result(1)]
        bundle = builder.build_prompt(
            query="Elements of FEHA retaliation",
            mode="attorney",
            retrieval_results=results,
        )

        assert "legal research assistant" in bundle.system_prompt.lower()
        assert "retaliation" in bundle.user_message

    def test_context_in_document_blocks(self, builder):
        """Context now goes into Citations API document blocks, not user_message."""
        results = [
            _make_result(1, content="Section 1102.5 content here"),
            _make_result(2, content="Section 12940 content here"),
        ]
        bundle = builder.build_prompt("test", "attorney", results)

        # Context should be in document_blocks, not user_message
        assert len(bundle.document_blocks) == 2
        doc_texts = [
            b["source"]["content"][0]["text"] for b in bundle.document_blocks
        ]
        assert any("1102.5" in t for t in doc_texts)
        assert any("12940" in t for t in doc_texts)

    def test_document_blocks_format(self, builder):
        results = [_make_result(1, content="Test content")]
        bundle = builder.build_prompt("test", "consumer", results)

        block = bundle.document_blocks[0]
        assert block["type"] == "document"
        assert block["citations"]["enabled"] is True
        assert "source" in block
        assert block["source"]["type"] == "content"

    def test_document_block_title_uses_citation(self, builder):
        results = [_make_result(1, citation="Cal. Lab. Code § 1102.5")]
        bundle = builder.build_prompt("test", "consumer", results)

        assert bundle.document_blocks[0]["title"] == "Cal. Lab. Code § 1102.5"

    def test_document_block_title_fallback(self, builder):
        results = [_make_result(1, citation=None)]
        bundle = builder.build_prompt("test", "consumer", results)

        assert bundle.document_blocks[0]["title"] == "Test > Chunk 1"

    def test_document_block_includes_metadata(self, builder):
        results = [
            _make_result(
                1,
                content="Content here",
                source_url="https://dir.ca.gov/page",
                content_category="agency_guidance",
            )
        ]
        bundle = builder.build_prompt("test", "consumer", results)

        doc_text = bundle.document_blocks[0]["source"]["content"][0]["text"]
        assert "agency_guidance" in doc_text
        assert "https://dir.ca.gov/page" in doc_text

    def test_user_message_is_query_only(self, builder):
        results = [_make_result(1)]
        bundle = builder.build_prompt("What is minimum wage?", "consumer", results)

        # User message should only contain the query
        assert bundle.user_message == "What is minimum wage?"

    def test_token_budget_enforcement(self):
        builder = PromptBuilder(
            prompts_dir="config/prompts",
            max_context_tokens=100,  # Very small budget
        )
        results = [
            _make_result(i, content="x" * 500)
            for i in range(10)
        ]

        bundle = builder.build_prompt("test", "consumer", results)
        # Should have fewer chunks than input due to budget
        assert len(bundle.context_chunks) < len(results)

    def test_at_least_one_result_included(self):
        builder = PromptBuilder(
            prompts_dir="config/prompts",
            max_context_tokens=1,  # Impossibly small budget
        )
        results = [_make_result(1, content="x" * 500)]

        bundle = builder.build_prompt("test", "consumer", results)
        assert len(bundle.context_chunks) >= 1

    def test_empty_results(self, builder):
        bundle = builder.build_prompt("test", "consumer", [])
        assert bundle.context_chunks == []
        assert bundle.document_blocks == []
        assert bundle.total_tokens_estimate > 0  # System prompt still has tokens

    def test_consumer_disclaimer_in_template(self, builder):
        bundle = builder.build_prompt("test", "consumer", [])
        assert "not legal advice" in bundle.system_prompt.lower()

    def test_attorney_disclaimer_in_template(self, builder):
        bundle = builder.build_prompt("test", "attorney", [])
        assert "independently verified" in bundle.system_prompt.lower()

    def test_jinja_env_cached(self, builder):
        results = [_make_result(1)]
        builder.build_prompt("q1", "consumer", results)
        env1 = builder._jinja_env

        builder.build_prompt("q2", "consumer", results)
        env2 = builder._jinja_env

        assert env1 is env2


class TestPromptBuilderMissingTemplates:
    """Tests for error handling when templates are missing."""

    def test_missing_template_raises(self):
        builder = PromptBuilder(prompts_dir="/nonexistent/path")
        with pytest.raises(FileNotFoundError):
            builder.build_prompt("test", "consumer", [])

    def test_missing_mode_template(self, tmp_path):
        builder = PromptBuilder(prompts_dir=str(tmp_path))
        with pytest.raises(FileNotFoundError):
            builder.build_prompt("test", "consumer", [])
