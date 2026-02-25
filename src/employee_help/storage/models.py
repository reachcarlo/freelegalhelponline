"""Data models for the Employee Help knowledge base."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


class ContentType(str, Enum):
    HTML = "html"
    PDF = "pdf"


class CrawlStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class CrawlRun:
    id: int | None = None
    started_at: datetime = field(default_factory=_utcnow)
    completed_at: datetime | None = None
    status: CrawlStatus = CrawlStatus.RUNNING
    summary: dict[str, Any] = field(default_factory=dict)


@dataclass
class Document:
    source_url: str
    title: str
    content_type: ContentType
    raw_content: str
    content_hash: str
    retrieved_at: datetime = field(default_factory=_utcnow)
    last_modified: str | None = None
    language: str = "en"
    id: int | None = None
    crawl_run_id: int | None = None


@dataclass
class Chunk:
    content: str
    content_hash: str
    chunk_index: int
    heading_path: str
    token_count: int
    document_id: int | None = None
    embedding: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    id: int | None = None
