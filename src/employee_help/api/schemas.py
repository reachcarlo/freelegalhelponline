"""Pydantic request/response models for the API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from employee_help.api.sanitize import detect_prompt_injection, sanitize_text


class ConversationTurn(BaseModel):
    """A single turn in the conversation history."""

    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=20000)

    @field_validator("content", mode="before")
    @classmethod
    def sanitize_content(cls, v: str) -> str:
        if isinstance(v, str):
            return sanitize_text(v)
        return v


class AskRequest(BaseModel):
    """Request body for POST /api/ask."""

    query: str = Field(..., min_length=1, max_length=2000)
    mode: Literal["consumer", "attorney"] = "consumer"
    session_id: str | None = Field(default=None, max_length=100, pattern=r"^[a-zA-Z0-9\-_]+$")
    conversation_history: list[ConversationTurn] = Field(default_factory=list, max_length=20)
    turn_number: int = Field(default=1, ge=1, le=10)

    @field_validator("query", mode="before")
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        if isinstance(v, str):
            return sanitize_text(v)
        return v

    @field_validator("query")
    @classmethod
    def check_prompt_injection(cls, v: str) -> str:
        match = detect_prompt_injection(v)
        if match:
            raise ValueError(
                "Your query was flagged by our safety filter. "
                "Please rephrase your question about California employment law."
            )
        return v


class SourceInfo(BaseModel):
    """A single source/chunk used in the answer."""

    chunk_id: int
    content_category: str
    citation: str | None = None
    source_url: str = ""
    heading_path: str = ""
    relevance_score: float = 0.0


class AskMetadata(BaseModel):
    """Metadata returned after answer generation completes."""

    query_id: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_estimate: float = 0.0
    duration_ms: int = 0
    warnings: list[str] = []
    session_id: str | None = None
    turn_number: int = 1
    max_turns: int = 3
    is_final_turn: bool = False


class FeedbackRequest(BaseModel):
    """Request body for POST /api/feedback."""

    query_id: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9\-]+$")
    rating: Literal[1, -1]


class FeedbackResponse(BaseModel):
    """Response body for POST /api/feedback."""

    status: str = "ok"


class HealthResponse(BaseModel):
    """Response body for GET /api/health."""

    status: str = "ok"
    embedding_model_loaded: bool = False
    vector_store_connected: bool = False
