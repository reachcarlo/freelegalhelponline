"""Tests for the answer generation service."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from employee_help.generation.llm import LLMClient, LLMResponse
from employee_help.generation.models import Answer, AnswerCitation, TokenUsage
from employee_help.generation.prompts import PromptBuilder, PromptBundle
from employee_help.generation.service import AnswerService
from employee_help.retrieval.service import RetrievalResult, RetrievalService


def _make_result(chunk_id: int, **kwargs) -> RetrievalResult:
    defaults = {
        "chunk_id": chunk_id,
        "document_id": chunk_id * 10,
        "source_id": 1,
        "content": f"Content for chunk {chunk_id}",
        "heading_path": f"Test > Chunk {chunk_id}",
        "content_category": "statutory_code",
        "citation": f"Cal. Lab. Code § {chunk_id}",
        "relevance_score": 0.9,
        "source_url": f"https://example.com/{chunk_id}",
    }
    defaults.update(kwargs)
    return RetrievalResult(**defaults)


@pytest.fixture
def mock_retrieval():
    svc = MagicMock(spec=RetrievalService)
    svc.retrieve.return_value = [
        _make_result(1, citation="Cal. Lab. Code § 1102.5"),
        _make_result(2, citation="Cal. Gov. Code § 12940"),
    ]
    return svc


@pytest.fixture
def mock_llm():
    client = MagicMock(spec=LLMClient)
    client.generate.return_value = LLMResponse(
        text="Under Cal. Lab. Code § 1102.5, whistleblower protections apply.",
        model="claude-haiku-4-5-20251001",
        input_tokens=200,
        output_tokens=50,
        duration_ms=500,
    )
    return client


@pytest.fixture
def mock_prompt_builder():
    builder = MagicMock(spec=PromptBuilder)
    builder.build_prompt.return_value = PromptBundle(
        system_prompt="You are helpful.",
        user_message="What is FEHA?",
        context_chunks=[
            _make_result(1, citation="Cal. Lab. Code § 1102.5"),
            _make_result(2, citation="Cal. Gov. Code § 12940"),
        ],
        total_tokens_estimate=500,
    )
    return builder


@pytest.fixture
def answer_service(mock_retrieval, mock_llm, mock_prompt_builder):
    return AnswerService(
        retrieval_service=mock_retrieval,
        llm_client=mock_llm,
        prompt_builder=mock_prompt_builder,
        citation_validation="strict",
    )


class TestAnswerService:
    """Tests for AnswerService."""

    def test_generate_returns_answer(self, answer_service):
        answer = answer_service.generate("What is FEHA?", mode="consumer")
        assert isinstance(answer, Answer)
        assert answer.text
        assert answer.mode == "consumer"
        assert answer.query == "What is FEHA?"

    def test_generate_includes_retrieval_results(self, answer_service):
        answer = answer_service.generate("test", mode="consumer")
        assert len(answer.retrieval_results) > 0

    def test_generate_tracks_model(self, answer_service):
        answer = answer_service.generate("test", mode="consumer")
        assert answer.model_used == "claude-haiku-4-5-20251001"

    def test_generate_tracks_tokens(self, answer_service):
        answer = answer_service.generate("test", mode="consumer")
        assert answer.token_usage.input_tokens > 0
        assert answer.token_usage.output_tokens > 0

    def test_generate_tracks_duration(self, answer_service):
        answer = answer_service.generate("test", mode="consumer")
        assert answer.duration_ms >= 0  # May be 0 with mocked LLM

    def test_no_results_returns_fallback(self, answer_service, mock_retrieval):
        mock_retrieval.retrieve.return_value = []
        answer = answer_service.generate("obscure query", mode="consumer")
        assert "wasn't able to find" in answer.text.lower() or "no relevant" in answer.text.lower()
        assert len(answer.warnings) > 0


class TestCitationValidation:
    """Tests for citation validation in attorney mode."""

    def test_valid_citation_passes(self, answer_service, mock_llm):
        mock_llm.generate.return_value = LLMResponse(
            text="Under Cal. Lab. Code § 1102.5, protections apply.",
            model="test",
            input_tokens=100,
            output_tokens=50,
        )

        answer = answer_service.generate("test", mode="attorney")
        # Citation § 1102.5 exists in context, should not be flagged
        assert "unverified" not in answer.text.lower()

    def test_hallucinated_citation_flagged_strict(self, answer_service, mock_llm):
        mock_llm.generate.return_value = LLMResponse(
            text="Under Cal. Lab. Code § 9999.99, something applies.",
            model="test",
            input_tokens=100,
            output_tokens=50,
        )

        answer = answer_service.generate("test", mode="attorney")
        assert "not verified" in answer.text.lower() or "unverified" in answer.text.lower()
        assert len(answer.warnings) > 0

    def test_consumer_mode_skips_citation_validation(
        self, answer_service, mock_llm
    ):
        mock_llm.generate.return_value = LLMResponse(
            text="Cal. Lab. Code § 9999.99 is referenced.",
            model="test",
            input_tokens=100,
            output_tokens=50,
        )

        answer = answer_service.generate("test", mode="consumer")
        # Consumer mode should not validate statute citations
        assert "unverified" not in answer.text.lower()

    def test_permissive_validation_mode(self, mock_retrieval, mock_llm, mock_prompt_builder):
        service = AnswerService(
            retrieval_service=mock_retrieval,
            llm_client=mock_llm,
            prompt_builder=mock_prompt_builder,
            citation_validation="permissive",
        )
        mock_llm.generate.return_value = LLMResponse(
            text="See Cal. Lab. Code § 9999.99 for details.",
            model="test",
            input_tokens=100,
            output_tokens=50,
        )

        answer = service.generate("test", mode="attorney")
        assert "[unverified]" in answer.text


class TestNoResultsMessage:
    """Tests for the no-results fallback messages."""

    def test_consumer_no_results(self, answer_service, mock_retrieval):
        mock_retrieval.retrieve.return_value = []
        answer = answer_service.generate("test", mode="consumer")
        assert "dir.ca.gov" in answer.text.lower() or "attorney" in answer.text.lower()

    def test_attorney_no_results(self, answer_service, mock_retrieval):
        mock_retrieval.retrieve.return_value = []
        answer = answer_service.generate("test", mode="attorney")
        assert "knowledge base" in answer.text.lower()
