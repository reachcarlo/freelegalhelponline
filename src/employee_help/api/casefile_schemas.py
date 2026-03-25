"""Pydantic request/response models for LITIGAGENT case file API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from employee_help.api.sanitize import sanitize_text


# ── Case schemas ──────────────────────────────────────────────────


class CreateCaseRequest(BaseModel):
    """Request body for POST /api/cases."""

    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name", mode="before")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        if isinstance(v, str):
            return sanitize_text(v)
        return v


class UpdateCaseRequest(BaseModel):
    """Request body for PATCH /api/cases/{case_id}."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def sanitize_name(cls, v: str | None) -> str | None:
        if isinstance(v, str):
            return sanitize_text(v)
        return v


class CaseResponse(BaseModel):
    """A single case."""

    id: str
    name: str
    description: str | None
    status: str
    file_count: int = 0
    created_at: str
    updated_at: str


class CaseListResponse(BaseModel):
    """Response body for GET /api/cases."""

    cases: list[CaseResponse]


# ── File schemas ──────────────────────────────────────────────────


class CaseFileResponse(BaseModel):
    """A single file (without text body)."""

    id: str
    case_id: str
    original_filename: str
    file_type: str
    mime_type: str
    file_size_bytes: int
    upload_order: int
    processing_status: str
    error_message: str | None = None
    ocr_confidence: float | None = None
    page_count: int | None = None
    metadata: dict | None = None
    text_dirty: bool = False
    created_at: str
    updated_at: str


class CaseFileDetailResponse(CaseFileResponse):
    """File details including extracted/edited text."""

    extracted_text: str | None = None
    edited_text: str | None = None


class FileUploadResponse(BaseModel):
    """Response body for POST /api/cases/{case_id}/files."""

    files: list[CaseFileResponse]


class UpdateFileTextRequest(BaseModel):
    """Request body for PATCH /api/cases/{case_id}/files/{file_id}."""

    edited_text: str = Field(..., max_length=1_000_000)


# ── Note schemas ──────────────────────────────────────────────────


class CreateNoteRequest(BaseModel):
    """Request body for POST /api/cases/{case_id}/notes."""

    content: str = Field(..., min_length=1, max_length=10000)
    file_id: str | None = None

    @field_validator("content", mode="before")
    @classmethod
    def sanitize_content(cls, v: str) -> str:
        if isinstance(v, str):
            return sanitize_text(v)
        return v


class NoteResponse(BaseModel):
    """A single note."""

    id: str
    case_id: str
    file_id: str | None
    content: str
    created_at: str
    updated_at: str


class NoteListResponse(BaseModel):
    """Response body for GET /api/cases/{case_id}/notes."""

    notes: list[NoteResponse]


class UpdateNoteRequest(BaseModel):
    """Request body for PATCH /api/cases/{case_id}/notes/{note_id}."""

    content: str = Field(..., min_length=1, max_length=10000)

    @field_validator("content", mode="before")
    @classmethod
    def sanitize_content(cls, v: str) -> str:
        if isinstance(v, str):
            return sanitize_text(v)
        return v


# ── Chat schemas ──────────────────────────────────────────────────


class CaseChatTurnItem(BaseModel):
    """A single turn in the case chat conversation history."""

    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=20000)

    @field_validator("content", mode="before")
    @classmethod
    def sanitize_content(cls, v: str) -> str:
        if isinstance(v, str):
            return sanitize_text(v)
        return v


class CaseChatRequest(BaseModel):
    """Request body for POST /api/cases/{case_id}/chat."""

    query: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = None
    conversation_history: list[CaseChatTurnItem] = Field(default_factory=list)

    @field_validator("query", mode="before")
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        if isinstance(v, str):
            return sanitize_text(v)
        return v


class CaseChatSourceInfo(BaseModel):
    """A source reference in chat responses."""

    source_type: str  # "case_file" | "knowledge_base"
    title: str
    relevance_score: float
    file_id: str | None = None
    chunk_id: str | None = None
    content_category: str | None = None
    heading_path: str | None = None


class ChatTurnResponse(BaseModel):
    """A single turn in chat history."""

    id: str
    session_id: str
    turn_number: int
    role: str
    content: str
    sources: dict | list | None = None
    created_at: str


class ChatSessionResponse(BaseModel):
    """A chat session summary."""

    id: str
    case_id: str
    created_at: str
    updated_at: str
    turn_count: int = 0


class ChatSessionListResponse(BaseModel):
    """Response body for GET /api/cases/{case_id}/chat/sessions."""

    sessions: list[ChatSessionResponse]


class ChatHistoryResponse(BaseModel):
    """Response body for GET /api/cases/{case_id}/chat/{session_id}."""

    session_id: str
    case_id: str
    turns: list[ChatTurnResponse]


# ── CaseContext schemas (V2.1c) ──────────────────────────────────


class PartyViewResponse(BaseModel):
    """A party in the case."""

    name: str
    role: str
    party_type: str
    count: int | None = None


class CourtViewResponse(BaseModel):
    """Court information."""

    court: str
    county: str | None = None
    department: str | None = None
    judge: str | None = None


class AttorneyViewResponse(BaseModel):
    """An attorney in the case."""

    name: str
    side: str
    bar_number: str | None = None
    firm: str | None = None
    email: str | None = None


class EmploymentPeriodViewResponse(BaseModel):
    """An employment period."""

    employer: str
    position: str | None = None
    department: str | None = None
    compensation_rate: float | None = None
    compensation_type: str | None = None
    pay_period: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    change_reason: str | None = None


class ClaimViewResponse(BaseModel):
    """A legal claim."""

    claim_type: str
    status: str = "active"
    protected_class: str | None = None
    supporting_facts: str | None = None
    reason: str | None = None


class DateViewResponse(BaseModel):
    """A key date."""

    label: str
    date: str
    date_type: str | None = None


class FinancialViewResponse(BaseModel):
    """A financial entry."""

    label: str
    amount: float
    date: str | None = None


class CaseContextResponse(BaseModel):
    """Response body for GET /api/cases/{case_id}/context."""

    case_id: str
    case_name: str
    parties: list[PartyViewResponse] = Field(default_factory=list)
    court: CourtViewResponse | None = None
    attorneys: list[AttorneyViewResponse] = Field(default_factory=list)
    employment_history: list[EmploymentPeriodViewResponse] = Field(default_factory=list)
    claims: list[ClaimViewResponse] = Field(default_factory=list)
    key_dates: list[DateViewResponse] = Field(default_factory=list)
    financials: list[FinancialViewResponse] = Field(default_factory=list)
    fact_count: int = 0
    confirmed_count: int = 0
    extraction_sources: dict[str, list[str]] = Field(default_factory=dict)
    plaintiff_names: list[str] = Field(default_factory=list)
    defendant_names: list[str] = Field(default_factory=list)
    all_person_names: list[str] = Field(default_factory=list)
    all_entity_names: list[str] = Field(default_factory=list)


# ── CaseFact schemas (V2.1c.2) ──────────────────────────────────


class CaseFactResponse(BaseModel):
    """A single case fact."""

    id: str
    case_id: str
    category: str
    fact_type: str
    value: dict
    source_file_id: str | None = None
    extraction_method: str
    confidence: float
    confirmed: bool = False
    superseded_by: str | None = None
    effective_date: str | None = None
    created_at: str


class CreateFactRequest(BaseModel):
    """Request body for POST /api/cases/{case_id}/facts (manual fact)."""

    category: str
    fact_type: str = Field(..., min_length=1, max_length=200)
    value: dict
    source_file_id: str | None = None
    effective_date: str | None = None


class SupersedeFactRequest(BaseModel):
    """Request body for POST /api/cases/{case_id}/facts/{fact_id}/supersede."""

    category: str
    fact_type: str = Field(..., min_length=1, max_length=200)
    value: dict
    effective_date: str | None = None


class CaseFactListResponse(BaseModel):
    """Response body for GET /api/cases/{case_id}/facts."""

    facts: list[CaseFactResponse]
    total: int


# ── Tier 2 extraction schemas (V2.2c.3) ─────────────────────────


class ExtractRequest(BaseModel):
    """Request body for POST /api/cases/{case_id}/extract."""

    file_id: str | None = Field(
        default=None,
        description="Specific file to extract from. If omitted, extracts from all key documents.",
    )


class ExtractResponse(BaseModel):
    """Response body for POST /api/cases/{case_id}/extract."""

    facts_created: int
    files_processed: int
    factual_summary: str | None = None
    facts: list[CaseFactResponse] = Field(default_factory=list)


# ── Artifact schemas (V2.4.6) ────────────────────────────────────


class ArtifactResponse(BaseModel):
    """A single case artifact."""

    id: str
    case_id: str
    artifact_type: str
    tool_source: str
    summary: str | None = None
    file_path: str | None = None
    metadata: dict | None = None
    created_at: str
    created_by: str | None = None


class ArtifactListResponse(BaseModel):
    """Response body for GET /api/cases/{case_id}/artifacts."""

    artifacts: list[ArtifactResponse]
