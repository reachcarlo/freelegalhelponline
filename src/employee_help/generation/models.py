"""Data models for answer generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from employee_help.retrieval.service import RetrievalResult

# Pricing per million tokens (USD) as of 2026
MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.0},
    "claude-haiku-4-5": {"input": 0.80, "output": 4.0},
    "claude-opus-4-6": {"input": 5.0, "output": 25.0},
}


@dataclass
class TokenUsage:
    """Token usage tracking for a single LLM call."""

    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def cost_estimate(self) -> float:
        """Estimate cost in USD based on model-specific pricing."""
        pricing = MODEL_PRICING.get(self.model)
        if pricing:
            return (
                self.input_tokens * pricing["input"]
                + self.output_tokens * pricing["output"]
            ) / 1_000_000
        # Fallback to Sonnet pricing as upper bound
        return (self.input_tokens * 3.0 + self.output_tokens * 15.0) / 1_000_000


@dataclass
class AnswerCitation:
    """A citation mapping a claim in the answer to a source chunk."""

    claim_text: str
    chunk_id: int
    source_url: str
    citation: str | None
    content_category: str
    document_index: int | None = None  # Index in the Citations API document list


@dataclass
class Answer:
    """Complete answer from the RAG pipeline."""

    text: str
    mode: str
    query: str
    citations: list[AnswerCitation] = field(default_factory=list)
    retrieval_results: list[RetrievalResult] = field(default_factory=list)
    model_used: str = ""
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    duration_ms: int = 0
    warnings: list[str] = field(default_factory=list)
