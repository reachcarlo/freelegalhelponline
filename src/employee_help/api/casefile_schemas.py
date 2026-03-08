"""Pydantic request/response models for LITIGAGENT case file API."""

from __future__ import annotations

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
