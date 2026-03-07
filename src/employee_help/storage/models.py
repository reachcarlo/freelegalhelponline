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


class UpsertStatus(str, Enum):
    """Result of a document upsert operation."""

    NEW = "new"
    UPDATED = "updated"
    UNCHANGED = "unchanged"


class SourceType(str, Enum):
    AGENCY = "agency"
    STATUTORY_CODE = "statutory_code"


class CaseStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class FileType(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    CSV = "csv"
    EML = "eml"
    MSG = "msg"
    TXT = "txt"
    IMAGE = "image"
    PPTX = "pptx"


class ProcessingStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"


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
    FEDERAL_GUIDANCE = "federal_guidance"
    LEGAL_AID_RESOURCE = "legal_aid_resource"


@dataclass
class Source:
    name: str
    slug: str
    source_type: SourceType
    base_url: str
    enabled: bool = True
    created_at: datetime = field(default_factory=_utcnow)
    last_refreshed_at: datetime | None = None
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


# --- LITIGAGENT Case File Models ---


@dataclass
class Case:
    name: str
    id: str = field(default_factory=lambda: "")
    description: str | None = None
    status: CaseStatus = CaseStatus.ACTIVE
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        if not self.id:
            import uuid

            self.id = str(uuid.uuid4())


@dataclass
class CaseFile:
    case_id: str
    original_filename: str
    file_type: FileType
    mime_type: str
    file_size_bytes: int
    storage_path: str
    upload_order: int
    id: str = field(default_factory=lambda: "")
    processing_status: ProcessingStatus = ProcessingStatus.QUEUED
    error_message: str | None = None
    extracted_text: str | None = None
    edited_text: str | None = None
    text_dirty: bool = False
    ocr_confidence: float | None = None
    page_count: int | None = None
    metadata: dict[str, Any] | None = None
    content_hash: str | None = None
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        if not self.id:
            import uuid

            self.id = str(uuid.uuid4())


@dataclass
class CaseNote:
    case_id: str
    content: str
    id: str = field(default_factory=lambda: "")
    file_id: str | None = None
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        if not self.id:
            import uuid

            self.id = str(uuid.uuid4())


@dataclass
class CaseChunk:
    file_id: str
    case_id: str
    chunk_index: int
    content: str
    heading_path: str
    token_count: int
    content_hash: str
    id: str = field(default_factory=lambda: "")
    is_active: bool = True
    created_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        if not self.id:
            import uuid

            self.id = str(uuid.uuid4())
