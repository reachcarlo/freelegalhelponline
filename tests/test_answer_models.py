"""Tests for answer generation data models."""

from __future__ import annotations

from employee_help.generation.models import Answer, AnswerCitation, TokenUsage


class TestTokenUsage:
    def test_total_tokens(self):
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        assert usage.total_tokens == 150

    def test_cost_estimate_positive(self):
        usage = TokenUsage(input_tokens=1000, output_tokens=500)
        assert usage.cost_estimate > 0

    def test_cost_estimate_zero(self):
        usage = TokenUsage(input_tokens=0, output_tokens=0)
        assert usage.cost_estimate == 0.0


class TestAnswerCitation:
    def test_creation(self):
        cit = AnswerCitation(
            claim_text="Whistleblower protections apply",
            chunk_id=42,
            source_url="https://example.com",
            citation="Cal. Lab. Code § 1102.5",
            content_category="statutory_code",
        )
        assert cit.chunk_id == 42
        assert cit.citation == "Cal. Lab. Code § 1102.5"

    def test_nullable_citation(self):
        cit = AnswerCitation(
            claim_text="Agency says...",
            chunk_id=1,
            source_url="https://dir.ca.gov",
            citation=None,
            content_category="agency_guidance",
        )
        assert cit.citation is None


class TestAnswer:
    def test_creation(self):
        answer = Answer(
            text="Test answer",
            mode="consumer",
            query="Test query",
        )
        assert answer.text == "Test answer"
        assert answer.mode == "consumer"
        assert answer.citations == []
        assert answer.warnings == []

    def test_with_citations(self):
        answer = Answer(
            text="Test answer",
            mode="attorney",
            query="Test query",
            citations=[
                AnswerCitation(
                    claim_text="claim",
                    chunk_id=1,
                    source_url="url",
                    citation="§ 1",
                    content_category="statutory_code",
                ),
            ],
        )
        assert len(answer.citations) == 1

    def test_default_token_usage(self):
        answer = Answer(text="test", mode="consumer", query="q")
        assert answer.token_usage.total_tokens == 0
