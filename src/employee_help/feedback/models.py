"""Data models for query analytics and user feedback."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class QueryLogEntry:
    """A single logged query with cost and performance metadata."""

    query_id: str
    query_hash: str
    mode: str  # 'consumer' | 'attorney'
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_estimate: float = 0.0
    duration_ms: int = 0
    source_count: int = 0
    error: str | None = None
    session_id: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(tz=UTC).isoformat())


@dataclass
class FeedbackEntry:
    """Thumbs up/down feedback on a specific query."""

    query_id: str
    rating: int  # +1 (thumbs up) or -1 (thumbs down)
    created_at: str = field(default_factory=lambda: datetime.now(tz=UTC).isoformat())


@dataclass
class CitationAuditEntry:
    """A single citation verification result logged for audit."""

    query_id: str
    citation_text: str
    citation_type: str  # 'case' | 'statute'
    verification_status: str  # e.g. 'verified', 'not_found', 'wrong_jurisdiction'
    confidence: str  # 'verified' | 'unverified' | 'suspicious'
    detail: str | None = None
    model_used: str = ""
    session_id: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(tz=UTC).isoformat())
