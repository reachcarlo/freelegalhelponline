"""Tests for the answer generation pipeline.

Tests cover the LLM client, prompt builder, and answer service with
mocked Anthropic API calls.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from employee_help.generation.llm import LLMClient, LLMResponse, StreamChunk
from employee_help.generation.models import (
    MODEL_PRICING,
    Answer,
    AnswerCitation,
    TokenUsage,
)
from employee_help.generation.prompts import PromptBuilder
from employee_help.generation.service import AnswerService
from employee_help.retrieval.service import RetrievalResult, RetrievalService


# ============================================================
# Helpers
# ============================================================


def _make_result(
    chunk_id: int,
    content: str = "Test content",
    category: str = "statutory_code",
    citation: str | None = None,
    source_url: str = "",
    score: float = 0.8,
) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        document_id=chunk_id * 10,
        source_id=1,
        content=content,
        heading_path=f"Path > Chunk {chunk_id}",
        content_category=category,
        citation=citation,
        relevance_score=score,
        source_url=source_url,
        content_hash=f"hash_{chunk_id}",
    )


def _make_mock_response(
    text: str = "Test answer",
    citations: list | None = None,
    input_tokens: int = 100,
    output_tokens: int = 50,
):
    """Create a mock Anthropic API response."""
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = text
    text_block.citations = citations or []

    response = MagicMock()
    response.content = [text_block]
    response.usage = MagicMock()
    response.usage.input_tokens = input_tokens
    response.usage.output_tokens = output_tokens
    return response


# ============================================================
# TokenUsage Tests
# ============================================================


class TestTokenUsage:
    """Tests for token usage and cost estimation."""

    def test_total_tokens(self):
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        assert usage.total_tokens == 150

    def test_cost_estimate_sonnet(self):
        usage = TokenUsage(
            input_tokens=1000, output_tokens=500, model="claude-sonnet-4-6"
        )
        # Sonnet: $3/M input + $15/M output
        expected = (1000 * 3.0 + 500 * 15.0) / 1_000_000
        assert abs(usage.cost_estimate - expected) < 1e-10

    def test_cost_estimate_haiku(self):
        usage = TokenUsage(
            input_tokens=1000, output_tokens=500, model="claude-haiku-4-5-20251001"
        )
        # Haiku: $0.80/M input + $4/M output
        expected = (1000 * 0.80 + 500 * 4.0) / 1_000_000
        assert abs(usage.cost_estimate - expected) < 1e-10

    def test_cost_estimate_unknown_model_uses_sonnet(self):
        usage = TokenUsage(
            input_tokens=1000, output_tokens=500, model="unknown-model"
        )
        expected = (1000 * 3.0 + 500 * 15.0) / 1_000_000
        assert abs(usage.cost_estimate - expected) < 1e-10

    def test_cost_estimate_no_model_uses_sonnet(self):
        usage = TokenUsage(input_tokens=1000, output_tokens=500)
        expected = (1000 * 3.0 + 500 * 15.0) / 1_000_000
        assert abs(usage.cost_estimate - expected) < 1e-10


# ============================================================
# LLMClient Tests
# ============================================================


class TestLLMClient:
    """Tests for LLMClient with mocked Anthropic client."""

    @pytest.fixture
    def mock_anthropic(self):
        """Mock the anthropic module."""
        with patch.dict("sys.modules", {"anthropic": MagicMock()}):
            import anthropic

            mock_client = MagicMock()
            anthropic.Anthropic.return_value = mock_client
            yield mock_client

    @pytest.fixture
    def client(self):
        """Create an LLMClient with a mocked client."""
        llm = LLMClient(api_key="test-key")
        mock_client = MagicMock()
        llm._client = mock_client
        return llm, mock_client

    def test_requires_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                LLMClient()

    def test_api_key_from_env(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            client = LLMClient()
            assert client.api_key == "test-key"

    def test_model_for_mode_consumer(self):
        llm = LLMClient(api_key="test-key")
        assert "haiku" in llm.model_for_mode("consumer")

    def test_model_for_mode_attorney(self):
        llm = LLMClient(api_key="test-key")
        assert "sonnet" in llm.model_for_mode("attorney")

    def test_model_for_mode_custom(self):
        llm = LLMClient(
            api_key="test-key",
            consumer_model="custom-consumer",
            attorney_model="custom-attorney",
        )
        assert llm.model_for_mode("consumer") == "custom-consumer"
        assert llm.model_for_mode("attorney") == "custom-attorney"

    def test_model_for_mode_default_override(self):
        llm = LLMClient(api_key="test-key", default_model="override-model")
        assert llm.model_for_mode("consumer") == "override-model"
        assert llm.model_for_mode("attorney") == "override-model"

    def test_generate_returns_response(self, client):
        llm, mock_client = client
        mock_client.messages.create.return_value = _make_mock_response(
            text="Test answer text"
        )

        result = llm.generate("system", "question")
        assert isinstance(result, LLMResponse)
        assert result.text == "Test answer text"
        assert result.input_tokens == 100
        assert result.output_tokens == 50

    def test_generate_with_document_blocks(self, client):
        llm, mock_client = client
        mock_client.messages.create.return_value = _make_mock_response()

        doc_blocks = [
            {
                "type": "document",
                "source": {
                    "type": "content",
                    "content": [{"type": "text", "text": "doc content"}],
                },
                "title": "Source 1",
                "citations": {"enabled": True},
            }
        ]

        llm.generate("system", "question", document_blocks=doc_blocks)

        # Verify user content includes document blocks
        call_kwargs = mock_client.messages.create.call_args
        messages = call_kwargs.kwargs["messages"]
        user_content = messages[0]["content"]
        assert isinstance(user_content, list)
        assert user_content[0]["type"] == "document"
        assert user_content[1]["type"] == "text"

    def test_generate_without_document_blocks(self, client):
        llm, mock_client = client
        mock_client.messages.create.return_value = _make_mock_response()

        llm.generate("system", "question")

        # Verify user content is plain text
        call_kwargs = mock_client.messages.create.call_args
        messages = call_kwargs.kwargs["messages"]
        user_content = messages[0]["content"]
        assert isinstance(user_content, str)
        assert user_content == "question"

    def test_generate_extracts_citations(self, client):
        llm, mock_client = client

        cit = MagicMock()
        cit.type = "char_location"
        cit.cited_text = "relevant text"
        cit.document_index = 0
        cit.start_char_index = 10
        cit.end_char_index = 30

        mock_client.messages.create.return_value = _make_mock_response(
            citations=[cit]
        )

        result = llm.generate("system", "question")
        assert len(result.citations) == 1
        assert result.citations[0]["cited_text"] == "relevant text"
        assert result.citations[0]["document_index"] == 0

    def test_generate_sets_temperature_zero(self, client):
        llm, mock_client = client
        mock_client.messages.create.return_value = _make_mock_response()

        llm.generate("system", "question")

        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs.kwargs["temperature"] == 0.0

    def test_generate_token_usage_includes_model(self, client):
        llm, mock_client = client
        mock_client.messages.create.return_value = _make_mock_response()

        result = llm.generate("system", "question", mode="attorney")
        assert result.token_usage.model == result.model

    def test_generate_stream_yields_text(self, client):
        llm, mock_client = client

        # Mock streaming context manager
        stream_ctx = MagicMock()
        stream_ctx.__enter__ = MagicMock(return_value=stream_ctx)
        stream_ctx.__exit__ = MagicMock(return_value=False)
        stream_ctx.text_stream = ["Hello", " world"]

        final_msg = _make_mock_response(text="Hello world")
        final_msg.content[0].citations = []
        stream_ctx.get_final_message.return_value = final_msg

        mock_client.messages.stream.return_value = stream_ctx

        chunks = list(llm.generate_stream("system", "question"))
        text_chunks = [c for c in chunks if c.text]
        assert len(text_chunks) == 2
        assert text_chunks[0].text == "Hello"
        assert text_chunks[1].text == " world"

    def test_generate_stream_final_chunk(self, client):
        llm, mock_client = client

        stream_ctx = MagicMock()
        stream_ctx.__enter__ = MagicMock(return_value=stream_ctx)
        stream_ctx.__exit__ = MagicMock(return_value=False)
        stream_ctx.text_stream = ["text"]

        final_msg = _make_mock_response(
            text="text", input_tokens=200, output_tokens=100
        )
        final_msg.content[0].citations = []
        stream_ctx.get_final_message.return_value = final_msg

        mock_client.messages.stream.return_value = stream_ctx

        chunks = list(llm.generate_stream("system", "question"))
        final = [c for c in chunks if c.is_final]
        assert len(final) == 1
        assert final[0].input_tokens == 200
        assert final[0].output_tokens == 100


# ============================================================
# PromptBuilder Tests
# ============================================================


class TestPromptBuilder:
    """Tests for the prompt builder."""

    @pytest.fixture
    def builder(self, tmp_path):
        """Create a PromptBuilder with test templates."""
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()

        (prompts_dir / "consumer_system.j2").write_text(
            "You are a helpful assistant."
        )
        (prompts_dir / "attorney_system.j2").write_text(
            "You are a legal research assistant."
        )

        return PromptBuilder(
            prompts_dir=str(prompts_dir),
            max_context_tokens=1000,
        )

    def test_build_prompt_consumer(self, builder):
        results = [_make_result(1, content="Chunk content")]
        bundle = builder.build_prompt("test question", "consumer", results)

        assert bundle.system_prompt == "You are a helpful assistant."
        assert bundle.user_message == "test question"
        assert len(bundle.document_blocks) == 1
        assert len(bundle.context_chunks) == 1

    def test_build_prompt_attorney(self, builder):
        results = [_make_result(1, content="Statutory text")]
        bundle = builder.build_prompt("legal question", "attorney", results)

        assert bundle.system_prompt == "You are a legal research assistant."

    def test_document_blocks_format(self, builder):
        results = [
            _make_result(
                1,
                content="Section text",
                citation="Cal. Lab. Code § 1102.5",
                source_url="https://example.com",
            )
        ]
        bundle = builder.build_prompt("test", "consumer", results)

        block = bundle.document_blocks[0]
        assert block["type"] == "document"
        assert block["citations"]["enabled"] is True
        assert block["title"] == "Cal. Lab. Code § 1102.5"
        assert "Section text" in block["source"]["content"][0]["text"]

    def test_document_blocks_include_metadata(self, builder):
        results = [
            _make_result(
                1,
                content="Content here",
                category="agency_guidance",
                source_url="https://dir.ca.gov/page",
            )
        ]
        bundle = builder.build_prompt("test", "consumer", results)

        doc_text = bundle.document_blocks[0]["source"]["content"][0]["text"]
        assert "agency_guidance" in doc_text
        assert "https://dir.ca.gov/page" in doc_text

    def test_fit_to_budget_respects_limit(self, builder):
        # Create results with very long content
        results = [
            _make_result(i, content="x" * 2000) for i in range(10)
        ]
        bundle = builder.build_prompt("test", "consumer", results)

        # Should include fewer than 10 chunks due to budget
        assert len(bundle.context_chunks) < 10
        assert len(bundle.context_chunks) > 0

    def test_fit_to_budget_includes_at_least_one(self, builder):
        # Single result that exceeds budget
        results = [_make_result(1, content="x" * 10000)]
        bundle = builder.build_prompt("test", "consumer", results)

        assert len(bundle.context_chunks) == 1

    def test_empty_results(self, builder):
        bundle = builder.build_prompt("test", "consumer", [])
        assert len(bundle.document_blocks) == 0
        assert len(bundle.context_chunks) == 0

    def test_template_not_found(self, builder):
        with pytest.raises(FileNotFoundError):
            builder.build_prompt("test", "nonexistent", [])

    def test_template_caching(self, builder):
        results = [_make_result(1)]
        builder.build_prompt("q1", "consumer", results)
        builder.build_prompt("q2", "consumer", results)

        # Template should be cached
        assert "consumer_system.j2" in builder._templates

    def test_total_tokens_estimate(self, builder):
        results = [_make_result(1, content="Short content")]
        bundle = builder.build_prompt("test", "consumer", results)

        assert bundle.total_tokens_estimate > 0

    def test_document_block_title_fallback(self, builder):
        results = [_make_result(1, content="Content", citation=None)]
        bundle = builder.build_prompt("test", "consumer", results)

        # Should fall back to heading_path when no citation
        assert bundle.document_blocks[0]["title"] == "Path > Chunk 1"


# ============================================================
# AnswerService Tests
# ============================================================


class TestAnswerService:
    """Tests for the answer generation service."""

    @pytest.fixture
    def mock_retrieval(self):
        svc = MagicMock(spec=RetrievalService)
        svc.retrieve.return_value = [
            _make_result(
                1,
                content="Cal. Lab. Code § 1102.5 protects whistleblowers.",
                citation="Cal. Lab. Code § 1102.5",
                category="statutory_code",
            ),
            _make_result(
                2,
                content="Filing a complaint with the Labor Commissioner.",
                category="agency_guidance",
                source_url="https://dir.ca.gov/complaint",
            ),
        ]
        return svc

    @pytest.fixture
    def mock_llm(self):
        llm = MagicMock(spec=LLMClient)
        llm.generate.return_value = LLMResponse(
            text="Under Cal. Lab. Code § 1102.5, whistleblowers are protected.",
            citations=[],
            model="claude-sonnet-4-6",
            input_tokens=500,
            output_tokens=200,
            duration_ms=1000,
        )
        llm.model_for_mode.return_value = "claude-sonnet-4-6"
        return llm

    @pytest.fixture
    def mock_prompt_builder(self, tmp_path):
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "consumer_system.j2").write_text("Consumer prompt")
        (prompts_dir / "attorney_system.j2").write_text("Attorney prompt")
        return PromptBuilder(prompts_dir=str(prompts_dir))

    @pytest.fixture
    def service(self, mock_retrieval, mock_llm, mock_prompt_builder):
        return AnswerService(
            retrieval_service=mock_retrieval,
            llm_client=mock_llm,
            prompt_builder=mock_prompt_builder,
        )

    def test_generate_returns_answer(self, service):
        answer = service.generate("test question", mode="attorney")
        assert isinstance(answer, Answer)
        assert len(answer.text) > 0
        assert answer.mode == "attorney"
        assert answer.query == "test question"

    def test_generate_includes_model(self, service):
        answer = service.generate("test", mode="attorney")
        assert answer.model_used == "claude-sonnet-4-6"

    def test_generate_includes_token_usage(self, service):
        answer = service.generate("test", mode="attorney")
        assert answer.token_usage.input_tokens == 500
        assert answer.token_usage.output_tokens == 200
        assert answer.token_usage.model == "claude-sonnet-4-6"

    def test_generate_includes_duration(self, service):
        answer = service.generate("test", mode="attorney")
        assert answer.duration_ms >= 0

    def test_generate_includes_retrieval_results(self, service):
        answer = service.generate("test", mode="attorney")
        assert len(answer.retrieval_results) == 2

    def test_generate_no_results(self, service, mock_retrieval):
        mock_retrieval.retrieve.return_value = []
        answer = service.generate("unknown topic", mode="consumer")
        assert "wasn't able to find" in answer.text
        assert answer.warnings

    def test_generate_no_results_attorney(self, service, mock_retrieval):
        mock_retrieval.retrieve.return_value = []
        answer = service.generate("unknown topic", mode="attorney")
        assert "No relevant statutory provisions" in answer.text

    def test_generate_passes_document_blocks(self, service, mock_llm):
        service.generate("test", mode="attorney")

        # Verify document_blocks were passed to LLM
        call_kwargs = mock_llm.generate.call_args
        assert "document_blocks" in call_kwargs.kwargs
        doc_blocks = call_kwargs.kwargs["document_blocks"]
        assert len(doc_blocks) == 2
        assert doc_blocks[0]["type"] == "document"

    def test_attorney_citation_validation(self, service, mock_llm):
        mock_llm.generate.return_value = LLMResponse(
            text="Under Cal. Lab. Code § 9999.9, employers must...",
            model="claude-sonnet-4-6",
            input_tokens=500,
            output_tokens=200,
        )

        answer = service.generate("test", mode="attorney")
        # The fabricated citation should be flagged
        assert any("9999.9" in w for w in answer.warnings)
        assert "[citation not verified]" in answer.text

    def test_consumer_mode_skips_citation_validation(self, service, mock_llm):
        mock_llm.generate.return_value = LLMResponse(
            text="According to the DIR, minimum wage is $16.",
            model="claude-haiku-4-5-20251001",
            input_tokens=300,
            output_tokens=100,
        )

        answer = service.generate("test", mode="consumer")
        assert not answer.warnings

    def test_valid_citation_not_flagged(self, service, mock_llm):
        mock_llm.generate.return_value = LLMResponse(
            text="Under Cal. Lab. Code § 1102.5, whistleblowers are protected.",
            model="claude-sonnet-4-6",
            input_tokens=500,
            output_tokens=200,
        )

        answer = service.generate("test", mode="attorney")
        assert not any("1102.5" in w for w in answer.warnings)
        assert "[citation not verified]" not in answer.text

    def test_api_citations_extracted(self, service, mock_llm):
        mock_llm.generate.return_value = LLMResponse(
            text="Whistleblowers are protected.",
            citations=[
                {
                    "type": "char_location",
                    "cited_text": "protects whistleblowers",
                    "document_index": 0,
                    "start_char_index": 0,
                    "end_char_index": 22,
                }
            ],
            model="claude-sonnet-4-6",
            input_tokens=500,
            output_tokens=200,
        )

        answer = service.generate("test", mode="attorney")
        assert len(answer.citations) > 0
        assert answer.citations[0].chunk_id == 1

    def test_generate_stream_returns_tuple(self, service, mock_llm):
        def mock_stream(**kwargs):
            yield StreamChunk(text="Hello")
            yield StreamChunk(
                text="",
                is_final=True,
                input_tokens=100,
                output_tokens=50,
                model="claude-sonnet-4-6",
            )

        mock_llm.generate_stream.return_value = mock_stream()

        stream, results, metadata = service.generate_stream("test", mode="attorney")
        text = "".join(stream)

        assert text == "Hello"
        assert len(results) == 2
        assert len(metadata) == 1
        assert metadata[0]["input_tokens"] == 100

    def test_generate_stream_empty_results(self, service, mock_retrieval):
        mock_retrieval.retrieve.return_value = []

        stream, results, metadata = service.generate_stream("unknown", mode="consumer")
        text = "".join(stream)

        assert "wasn't able to find" in text
        assert results == []

    def test_citation_matches_same_code(self, service):
        assert service._citation_matches(
            "Cal. Lab. Code § 1102.5",
            "Cal. Lab. Code § 1102.5",
        )

    def test_citation_matches_different_format(self, service):
        assert service._citation_matches(
            "Cal. Lab. Code § 1102.5",
            "Lab. Code sec. 1102.5",
        )

    def test_citation_no_match_different_section(self, service):
        assert not service._citation_matches(
            "Cal. Lab. Code § 1102.5",
            "Cal. Lab. Code § 98.6",
        )

    def test_citation_no_match_different_code(self, service):
        assert not service._citation_matches(
            "Cal. Lab. Code § 1102.5",
            "Cal. Gov. Code § 1102.5",
        )

    def test_permissive_citation_validation(self, mock_retrieval, mock_llm, tmp_path):
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "attorney_system.j2").write_text("Attorney prompt")

        mock_llm.generate.return_value = LLMResponse(
            text="Under Cal. Lab. Code § 9999.9, test.",
            model="claude-sonnet-4-6",
            input_tokens=500,
            output_tokens=200,
        )

        svc = AnswerService(
            retrieval_service=mock_retrieval,
            llm_client=mock_llm,
            prompt_builder=PromptBuilder(prompts_dir=str(prompts_dir)),
            citation_validation="permissive",
        )

        answer = svc.generate("test", mode="attorney")
        assert "[unverified]" in answer.text
        assert "[citation not verified]" not in answer.text
