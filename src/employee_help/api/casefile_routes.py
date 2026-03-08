"""API endpoints for LITIGAGENT case file management."""

from __future__ import annotations

import asyncio
import json
import mimetypes
from pathlib import Path

import structlog
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from employee_help.api.casefile_schemas import (
    CaseFileDetailResponse,
    CaseFileResponse,
    CaseListResponse,
    CaseResponse,
    CreateCaseRequest,
    CreateNoteRequest,
    FileUploadResponse,
    NoteListResponse,
    NoteResponse,
    UpdateCaseRequest,
    UpdateFileTextRequest,
    UpdateNoteRequest,
)
from employee_help.casefile.processing import (
    MAX_FILE_SIZE,
    broadcast_status,
    content_hash,
    get_file_type,
    get_registry,
    get_supported_extensions,
    process_file,
    register_sse_client,
    save_upload,
    unregister_sse_client,
)
from employee_help.storage.models import (
    Case,
    CaseFile,
    CaseNote,
    ProcessingStatus,
)

logger = structlog.get_logger(__name__)

casefile_router = APIRouter(prefix="/api/cases", tags=["cases"])


def _get_case_storage():
    """Get the CaseStorage singleton from deps."""
    from employee_help.api.deps import get_case_storage

    return get_case_storage()


# ── Helpers ───────────────────────────────────────────────────────


def _case_response(case: Case, file_count: int = 0) -> CaseResponse:
    return CaseResponse(
        id=case.id,
        name=case.name,
        description=case.description,
        status=case.status.value,
        file_count=file_count,
        created_at=case.created_at.isoformat(),
        updated_at=case.updated_at.isoformat(),
    )


def _file_response(cf: CaseFile) -> CaseFileResponse:
    return CaseFileResponse(
        id=cf.id,
        case_id=cf.case_id,
        original_filename=cf.original_filename,
        file_type=cf.file_type.value,
        mime_type=cf.mime_type,
        file_size_bytes=cf.file_size_bytes,
        upload_order=cf.upload_order,
        processing_status=cf.processing_status.value,
        error_message=cf.error_message,
        ocr_confidence=cf.ocr_confidence,
        page_count=cf.page_count,
        metadata=cf.metadata,
        text_dirty=cf.text_dirty,
        created_at=cf.created_at.isoformat(),
        updated_at=cf.updated_at.isoformat(),
    )


def _file_detail_response(cf: CaseFile) -> CaseFileDetailResponse:
    return CaseFileDetailResponse(
        id=cf.id,
        case_id=cf.case_id,
        original_filename=cf.original_filename,
        file_type=cf.file_type.value,
        mime_type=cf.mime_type,
        file_size_bytes=cf.file_size_bytes,
        upload_order=cf.upload_order,
        processing_status=cf.processing_status.value,
        error_message=cf.error_message,
        ocr_confidence=cf.ocr_confidence,
        page_count=cf.page_count,
        metadata=cf.metadata,
        text_dirty=cf.text_dirty,
        extracted_text=cf.extracted_text,
        edited_text=cf.edited_text,
        created_at=cf.created_at.isoformat(),
        updated_at=cf.updated_at.isoformat(),
    )


def _note_response(note: CaseNote) -> NoteResponse:
    return NoteResponse(
        id=note.id,
        case_id=note.case_id,
        file_id=note.file_id,
        content=note.content,
        created_at=note.created_at.isoformat(),
        updated_at=note.updated_at.isoformat(),
    )


def _require_case(case_id: str) -> Case:
    """Fetch a case or raise 404."""
    storage = _get_case_storage()
    case = storage.get_case(case_id)
    if case is None:
        raise HTTPException(404, f"Case not found: {case_id}")
    return case


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# ── Case CRUD ─────────────────────────────────────────────────────


@casefile_router.post("", response_model=CaseResponse, status_code=201)
async def create_case(body: CreateCaseRequest):
    """Create a new case."""
    storage = _get_case_storage()
    case = Case(name=body.name, description=body.description)
    case = storage.create_case(case)
    logger.info("case_created", case_id=case.id, name=case.name)
    return _case_response(case)


@casefile_router.get("", response_model=CaseListResponse)
async def list_cases(status: str | None = None):
    """List all cases, optionally filtered by status."""
    from employee_help.storage.models import CaseStatus

    storage = _get_case_storage()
    filter_status = None
    if status:
        try:
            filter_status = CaseStatus(status)
        except ValueError:
            raise HTTPException(400, f"Invalid status: {status}")
    cases = storage.list_cases(status=filter_status)
    results = []
    for c in cases:
        file_count = len(storage.list_case_files(c.id))
        results.append(_case_response(c, file_count=file_count))
    return CaseListResponse(cases=results)


@casefile_router.get("/{case_id}", response_model=CaseResponse)
async def get_case(case_id: str):
    """Get case details."""
    storage = _get_case_storage()
    case = _require_case(case_id)
    file_count = len(storage.list_case_files(case_id))
    return _case_response(case, file_count=file_count)


@casefile_router.patch("/{case_id}", response_model=CaseResponse)
async def update_case(case_id: str, body: UpdateCaseRequest):
    """Update case name and/or description."""
    storage = _get_case_storage()
    _require_case(case_id)

    kwargs: dict = {}
    if body.name is not None:
        kwargs["name"] = body.name
    if body.description is not None:
        kwargs["description"] = body.description

    updated = storage.update_case(case_id, **kwargs)
    if updated is None:
        raise HTTPException(404, f"Case not found: {case_id}")

    file_count = len(storage.list_case_files(case_id))
    logger.info("case_updated", case_id=case_id)
    return _case_response(updated, file_count=file_count)


@casefile_router.delete("/{case_id}", status_code=204)
async def archive_case(case_id: str):
    """Archive a case (soft delete)."""
    storage = _get_case_storage()
    success = storage.archive_case(case_id)
    if not success:
        raise HTTPException(404, f"Case not found: {case_id}")
    logger.info("case_archived", case_id=case_id)


# ── File management ──────────────────────────────────────────────


@casefile_router.post(
    "/{case_id}/files", response_model=FileUploadResponse, status_code=201
)
async def upload_files(case_id: str, files: list[UploadFile] = File(...)):
    """Upload one or more files to a case. Processing happens in the background."""
    storage = _get_case_storage()
    _require_case(case_id)

    if not files:
        raise HTTPException(400, "No files provided")

    supported = get_supported_extensions()
    results: list[CaseFileResponse] = []

    for upload in files:
        filename = upload.filename or "upload"
        ext = Path(filename).suffix.lower().lstrip(".")

        # Validate extension
        if ext not in supported:
            raise HTTPException(
                400,
                f"Unsupported file type: .{ext}. "
                f"Supported: {', '.join(sorted(supported))}",
            )

        # Read and validate size
        file_bytes = await upload.read()
        if len(file_bytes) > MAX_FILE_SIZE:
            raise HTTPException(
                400,
                f"File too large: {filename} ({len(file_bytes)} bytes). "
                f"Maximum: {MAX_FILE_SIZE} bytes.",
            )

        # Resolve FileType
        file_type = get_file_type(ext)
        if file_type is None:
            raise HTTPException(400, f"Unknown file type for extension: .{ext}")

        # Determine MIME type
        mime_type = upload.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"

        # Get upload order
        upload_order = storage.get_next_upload_order(case_id)

        # Create CaseFile
        cf = CaseFile(
            case_id=case_id,
            original_filename=filename,
            file_type=file_type,
            mime_type=mime_type,
            file_size_bytes=len(file_bytes),
            storage_path="",  # Set after save
            upload_order=upload_order,
        )

        # Save to disk
        storage_path = save_upload(case_id, cf.id, filename, file_bytes)
        cf.storage_path = str(storage_path)

        # Insert DB row
        cf = storage.create_case_file(cf)
        results.append(_file_response(cf))

        # Launch background processing
        asyncio.create_task(process_file(storage, cf.id, case_id))

        logger.info(
            "file_uploaded",
            case_id=case_id,
            file_id=cf.id,
            filename=filename,
            size=len(file_bytes),
        )

    return FileUploadResponse(files=results)


@casefile_router.get("/{case_id}/files", response_model=list[CaseFileResponse])
async def list_files(case_id: str):
    """List all files in a case."""
    storage = _get_case_storage()
    _require_case(case_id)
    files = storage.list_case_files(case_id)
    return [_file_response(f) for f in files]


@casefile_router.get(
    "/{case_id}/files/{file_id}", response_model=CaseFileDetailResponse
)
async def get_file(case_id: str, file_id: str):
    """Get file details including extracted/edited text."""
    storage = _get_case_storage()
    _require_case(case_id)
    cf = storage.get_case_file(file_id)
    if cf is None or cf.case_id != case_id:
        raise HTTPException(404, f"File not found: {file_id}")
    return _file_detail_response(cf)


@casefile_router.patch(
    "/{case_id}/files/{file_id}", response_model=CaseFileDetailResponse
)
async def update_file_text(case_id: str, file_id: str, body: UpdateFileTextRequest):
    """Update the edited text for a file."""
    storage = _get_case_storage()
    _require_case(case_id)

    cf = storage.get_case_file(file_id)
    if cf is None or cf.case_id != case_id:
        raise HTTPException(404, f"File not found: {file_id}")

    h = content_hash(body.edited_text) if body.edited_text else None
    updated = storage.update_case_file_text(
        file_id, edited_text=body.edited_text, content_hash=h
    )
    if updated is None:
        raise HTTPException(404, f"File not found: {file_id}")

    logger.info("file_text_updated", case_id=case_id, file_id=file_id)
    return _file_detail_response(updated)


@casefile_router.delete("/{case_id}/files/{file_id}", status_code=204)
async def delete_file(case_id: str, file_id: str):
    """Remove a file from a case."""
    storage = _get_case_storage()
    _require_case(case_id)

    cf = storage.get_case_file(file_id)
    if cf is None or cf.case_id != case_id:
        raise HTTPException(404, f"File not found: {file_id}")

    # Delete from disk
    storage_path = Path(cf.storage_path)
    if storage_path.exists():
        storage_path.unlink()

    # Delete chunks first, then file
    storage.delete_case_chunks_for_file(file_id)
    storage.delete_case_file(file_id)
    logger.info("file_deleted", case_id=case_id, file_id=file_id)


@casefile_router.post(
    "/{case_id}/files/{file_id}/reprocess",
    response_model=CaseFileResponse,
)
async def reprocess_file(case_id: str, file_id: str):
    """Re-extract text from a file."""
    storage = _get_case_storage()
    _require_case(case_id)

    cf = storage.get_case_file(file_id)
    if cf is None or cf.case_id != case_id:
        raise HTTPException(404, f"File not found: {file_id}")

    # Reset status to QUEUED
    storage.update_case_file_status(file_id, ProcessingStatus.QUEUED)

    # Relaunch background processing
    asyncio.create_task(process_file(storage, file_id, case_id))

    # Refetch for response
    cf = storage.get_case_file(file_id)
    logger.info("file_reprocessing", case_id=case_id, file_id=file_id)
    return _file_response(cf)


@casefile_router.get("/{case_id}/files/{file_id}/download")
async def download_file(case_id: str, file_id: str):
    """Download the original uploaded file."""
    storage = _get_case_storage()
    _require_case(case_id)

    cf = storage.get_case_file(file_id)
    if cf is None or cf.case_id != case_id:
        raise HTTPException(404, f"File not found: {file_id}")

    storage_path = Path(cf.storage_path)
    if not storage_path.exists():
        raise HTTPException(404, "Original file no longer available on disk")

    return FileResponse(
        path=str(storage_path),
        filename=cf.original_filename,
        media_type=cf.mime_type,
    )


# ── SSE status stream ────────────────────────────────────────────


@casefile_router.get("/{case_id}/status-stream")
async def status_stream(case_id: str):
    """SSE endpoint for real-time file processing status updates."""
    _require_case(case_id)

    queue = register_sse_client(case_id)

    async def event_generator():
        try:
            # Send initial heartbeat
            yield _sse_event("connected", {"case_id": case_id})

            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield _sse_event("file_status", event)
                except asyncio.TimeoutError:
                    # Send keepalive comment
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            unregister_sse_client(case_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Notes CRUD ────────────────────────────────────────────────────


@casefile_router.post(
    "/{case_id}/notes", response_model=NoteResponse, status_code=201
)
async def create_note(case_id: str, body: CreateNoteRequest):
    """Create a note on a case (optionally linked to a file)."""
    storage = _get_case_storage()
    _require_case(case_id)

    # Validate file_id if provided
    if body.file_id:
        cf = storage.get_case_file(body.file_id)
        if cf is None or cf.case_id != case_id:
            raise HTTPException(404, f"File not found: {body.file_id}")

    note = CaseNote(
        case_id=case_id,
        content=body.content,
        file_id=body.file_id,
    )
    note = storage.create_note(note)
    logger.info("note_created", case_id=case_id, note_id=note.id)
    return _note_response(note)


@casefile_router.get("/{case_id}/notes", response_model=NoteListResponse)
async def list_notes(case_id: str, file_id: str | None = None):
    """List notes for a case, optionally filtered by file_id."""
    storage = _get_case_storage()
    _require_case(case_id)
    notes = storage.list_notes(case_id, file_id=file_id)
    return NoteListResponse(notes=[_note_response(n) for n in notes])


@casefile_router.patch(
    "/{case_id}/notes/{note_id}", response_model=NoteResponse
)
async def update_note(case_id: str, note_id: str, body: UpdateNoteRequest):
    """Update a note's content."""
    storage = _get_case_storage()
    _require_case(case_id)

    note = storage.get_note(note_id)
    if note is None or note.case_id != case_id:
        raise HTTPException(404, f"Note not found: {note_id}")

    updated = storage.update_note(note_id, body.content)
    if updated is None:
        raise HTTPException(404, f"Note not found: {note_id}")

    logger.info("note_updated", case_id=case_id, note_id=note_id)
    return _note_response(updated)


@casefile_router.delete("/{case_id}/notes/{note_id}", status_code=204)
async def delete_note(case_id: str, note_id: str):
    """Delete a note."""
    storage = _get_case_storage()
    _require_case(case_id)

    note = storage.get_note(note_id)
    if note is None or note.case_id != case_id:
        raise HTTPException(404, f"Note not found: {note_id}")

    storage.delete_note(note_id)
    logger.info("note_deleted", case_id=case_id, note_id=note_id)
