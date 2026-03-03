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


class SourceType(str, Enum):
    AGENCY = "agency"
    STATUTORY_CODE = "statutory_code"


class ContentCategory(str, Enum):
    AGENCY_GUIDANCE = "agency_guidance"
    FACT_SHEET = "fact_sheet"
    STATUTORY_CODE = "statutory_code"
    REGULATION = "regulation"
    POSTER = "poster"
    FAQ = "faq"
    JURY_INSTRUCTION = "jury_instruction"
    CASE_LAW = "case_law"
    OPINION_LETTER = "opinion_letter"
    ENFORCEMENT_MANUAL = "enforcement_manual"


@dataclass
class Source:
    name: str
    slug: str
    source_type: SourceType
    base_url: str
    enabled: bool = True
    created_at: datetime = field(default_factory=_utcnow)
    id: int | None = None


@dataclass
class CrawlRun:
    id: int | None = None
    source_id: int | None = None
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
    source_id: int | None = None
    content_category: ContentCategory = ContentCategory.AGENCY_GUIDANCE


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
    content_category: ContentCategory = ContentCategory.AGENCY_GUIDANCE
    citation: str | None = None
    is_active: bool = True


@dataclass
class CitationLink:
    """Bidirectional link between a citing chunk and a cited reference.

    Enables lookups in both directions:
    - Forward: given a case chunk, which statutes/cases does it cite?
    - Reverse: given a statute chunk, which cases cite it?
    """

    source_chunk_id: int
    cited_text: str
    citation_type: str  # "case" | "statute" | "short_case" | "id" | "supra"
    reporter: str | None = None
    volume: str | None = None
    page: str | None = None
    section: str | None = None
    is_california: bool = False
    target_chunk_id: int | None = None
    created_at: datetime = field(default_factory=_utcnow)
    id: int | None = None
