"""API endpoints for LITIGAGENT case file management."""

from __future__ import annotations

import asyncio
import json
import mimetypes
import time
import uuid
from pathlib import Path

import structlog
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from employee_help.api.casefile_schemas import (
    CaseChatRequest,
    CaseChatSourceInfo,
    CaseFileDetailResponse,
    CaseFileResponse,
    CaseListResponse,
    CaseResponse,
    ChatHistoryResponse,
    ChatSessionListResponse,
    ChatSessionResponse,
    ChatTurnResponse,
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
    schedule_reembed,
    unregister_sse_client,
)
from employee_help.storage.models import (
    Case,
    CaseChatSession,
    CaseChatTurn,
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


def _audit(action: str, request, **kwargs) -> None:
    """Best-effort audit log. Never raises."""
    try:
        from employee_help.api.deps import get_audit_logger

        audit = get_audit_logger()
        if audit is not None:
            audit.log_from_request(action, request, **kwargs)
    except Exception:
        # Rollback any failed transaction to release the WAL write lock
        try:
            from employee_help.api.deps import get_audit_logger as _get_al

            al = _get_al()
            if al is not None:
                al._conn.rollback()
        except Exception:
            pass
        logger.warning("audit_log_failed", action=action, exc_info=True)


def _get_embedding_deps():
    """Get embedding service + case vector store (may be None)."""
    from employee_help.api.deps import get_case_vector_store, get_embedding_service

    return get_embedding_service(), get_case_vector_store()


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


def _require_user(request: Request):
    """Extract authenticated user from request or raise 401."""
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(401, "Authentication required")
    return user


def _require_case(case_id: str, *, user_id: str | None = None) -> Case:
    """Fetch a case owned by user_id, or raise 404 (never 403 — don't leak existence)."""
    storage = _get_case_storage()
    case = storage.get_case(case_id, user_id=user_id)
    if case is None:
        raise HTTPException(404, f"Case not found: {case_id}")
    return case


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# ── Case CRUD ─────────────────────────────────────────────────────


@casefile_router.post("", response_model=CaseResponse, status_code=201)
async def create_case(body: CreateCaseRequest, request: Request):
    """Create a new case."""
    user = _require_user(request)
    storage = _get_case_storage()
    case = Case(
        name=body.name,
        user_id=user.sub,
        organization_id=user.org,
        description=body.description,
    )
    case = storage.create_case(case)
    logger.info("case_created", case_id=case.id)
    _audit("case.create", request, resource_type="case", resource_id=case.id)
    return _case_response(case)


@casefile_router.get("", response_model=CaseListResponse)
async def list_cases(request: Request, status: str | None = None):
    """List all cases, optionally filtered by status."""
    from employee_help.storage.models import CaseStatus

    user = _require_user(request)
    storage = _get_case_storage()
    filter_status = None
    if status:
        try:
            filter_status = CaseStatus(status)
        except ValueError:
            raise HTTPException(400, f"Invalid status: {status}")
    cases = storage.list_cases(user_id=user.sub, status=filter_status)
    results = []
    for c in cases:
        file_count = len(storage.list_case_files(c.id))
        results.append(_case_response(c, file_count=file_count))
    return CaseListResponse(cases=results)


@casefile_router.get("/{case_id}", response_model=CaseResponse)
async def get_case(case_id: str, request: Request):
    """Get case details."""
    user = _require_user(request)
    storage = _get_case_storage()
    case = _require_case(case_id, user_id=user.sub)
    file_count = len(storage.list_case_files(case_id))
    return _case_response(case, file_count=file_count)


@casefile_router.patch("/{case_id}", response_model=CaseResponse)
async def update_case(case_id: str, body: UpdateCaseRequest, request: Request):
    """Update case name and/or description."""
    user = _require_user(request)
    storage = _get_case_storage()
    _require_case(case_id, user_id=user.sub)

    kwargs: dict = {}
    if body.name is not None:
        kwargs["name"] = body.name
    if body.description is not None:
        kwargs["description"] = body.description

    updated = storage.update_case(case_id, user_id=user.sub, **kwargs)
    if updated is None:
        raise HTTPException(404, f"Case not found: {case_id}")

    file_count = len(storage.list_case_files(case_id))
    logger.info("case_updated", case_id=case_id)
    return _case_response(updated, file_count=file_count)


@casefile_router.delete("/{case_id}", status_code=204)
async def archive_case(case_id: str, request: Request):
    """Archive a case (soft delete)."""
    user = _require_user(request)
    storage = _get_case_storage()
    _require_case(case_id, user_id=user.sub)
    success = storage.archive_case(case_id, user_id=user.sub)
    if not success:
        raise HTTPException(404, f"Case not found: {case_id}")
    logger.info("case_archived", case_id=case_id)
    _audit("case.archive", request, resource_type="case", resource_id=case_id)


# ── File management ──────────────────────────────────────────────


@casefile_router.post(
    "/{case_id}/files", response_model=FileUploadResponse, status_code=201
)
async def upload_files(case_id: str, request: Request, files: list[UploadFile] = File(...)):
    """Upload one or more files to a case. Processing happens in the background."""
    user = _require_user(request)
    storage = _get_case_storage()
    _require_case(case_id, user_id=user.sub)

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

        # Launch background processing (with embedding if available)
        embedder, cvs = _get_embedding_deps()
        asyncio.create_task(
            process_file(storage, cf.id, case_id, embedder, cvs)
        )

        logger.info(
            "file_uploaded",
            case_id=case_id,
            file_id=cf.id,
            size=len(file_bytes),
        )
        _audit(
            "file.upload", request,
            resource_type="file", resource_id=cf.id,
            metadata={"case_id": case_id, "filename": filename},
        )

    return FileUploadResponse(files=results)


@casefile_router.get("/{case_id}/files", response_model=list[CaseFileResponse])
async def list_files(case_id: str, request: Request):
    """List all files in a case."""
    user = _require_user(request)
    storage = _get_case_storage()
    _require_case(case_id, user_id=user.sub)
    files = storage.list_case_files(case_id)
    return [_file_response(f) for f in files]


@casefile_router.get(
    "/{case_id}/files/{file_id}", response_model=CaseFileDetailResponse
)
async def get_file(case_id: str, file_id: str, request: Request):
    """Get file details including extracted/edited text."""
    user = _require_user(request)
    storage = _get_case_storage()
    _require_case(case_id, user_id=user.sub)
    cf = storage.get_case_file(file_id)
    if cf is None or cf.case_id != case_id:
        raise HTTPException(404, f"File not found: {file_id}")
    return _file_detail_response(cf)


@casefile_router.patch(
    "/{case_id}/files/{file_id}", response_model=CaseFileDetailResponse
)
async def update_file_text(case_id: str, file_id: str, body: UpdateFileTextRequest, request: Request):
    """Update the edited text for a file."""
    user = _require_user(request)
    storage = _get_case_storage()
    _require_case(case_id, user_id=user.sub)

    cf = storage.get_case_file(file_id)
    if cf is None or cf.case_id != case_id:
        raise HTTPException(404, f"File not found: {file_id}")

    h = content_hash(body.edited_text) if body.edited_text else None
    updated = storage.update_case_file_text(
        file_id, edited_text=body.edited_text, content_hash=h
    )
    if updated is None:
        raise HTTPException(404, f"File not found: {file_id}")

    # Schedule debounced re-embedding if text changed (L3.3)
    embedder, cvs = _get_embedding_deps()
    if updated.text_dirty and embedder is not None and cvs is not None:
        schedule_reembed(file_id, case_id, storage, embedder, cvs)

    logger.info("file_text_updated", case_id=case_id, file_id=file_id)
    return _file_detail_response(updated)


@casefile_router.delete("/{case_id}/files/{file_id}", status_code=204)
async def delete_file(case_id: str, file_id: str, request: Request):
    """Remove a file from a case."""
    user = _require_user(request)
    storage = _get_case_storage()
    _require_case(case_id, user_id=user.sub)

    cf = storage.get_case_file(file_id)
    if cf is None or cf.case_id != case_id:
        raise HTTPException(404, f"File not found: {file_id}")

    # Delete from disk
    storage_path = Path(cf.storage_path)
    if storage_path.exists():
        storage_path.unlink()

    # Delete embeddings from LanceDB
    _, cvs = _get_embedding_deps()
    if cvs is not None:
        cvs.delete_file_embeddings(file_id)

    # Delete chunks first, then file
    storage.delete_case_chunks_for_file(file_id)
    storage.delete_case_file(file_id)
    logger.info("file_deleted", case_id=case_id, file_id=file_id)
    _audit(
        "file.delete", request,
        resource_type="file", resource_id=file_id,
        metadata={"case_id": case_id},
    )


@casefile_router.post(
    "/{case_id}/files/{file_id}/reprocess",
    response_model=CaseFileResponse,
)
async def reprocess_file(case_id: str, file_id: str, request: Request):
    """Re-extract text from a file."""
    user = _require_user(request)
    storage = _get_case_storage()
    _require_case(case_id, user_id=user.sub)

    cf = storage.get_case_file(file_id)
    if cf is None or cf.case_id != case_id:
        raise HTTPException(404, f"File not found: {file_id}")

    # Reset status to QUEUED
    storage.update_case_file_status(file_id, ProcessingStatus.QUEUED)

    # Relaunch background processing (with embedding if available)
    embedder, cvs = _get_embedding_deps()
    asyncio.create_task(
        process_file(storage, file_id, case_id, embedder, cvs)
    )

    # Refetch for response
    cf = storage.get_case_file(file_id)
    logger.info("file_reprocessing", case_id=case_id, file_id=file_id)
    _audit(
        "file.reprocess", request,
        resource_type="file", resource_id=file_id,
        metadata={"case_id": case_id},
    )
    return _file_response(cf)


@casefile_router.get("/{case_id}/files/{file_id}/download")
async def download_file(case_id: str, file_id: str, request: Request):
    """Download the original uploaded file."""
    user = _require_user(request)
    storage = _get_case_storage()
    _require_case(case_id, user_id=user.sub)

    cf = storage.get_case_file(file_id)
    if cf is None or cf.case_id != case_id:
        raise HTTPException(404, f"File not found: {file_id}")

    storage_path = Path(cf.storage_path)
    if not storage_path.exists():
        raise HTTPException(404, "Original file no longer available on disk")

    _audit(
        "file.download", request,
        resource_type="file", resource_id=file_id,
        metadata={"case_id": case_id},
    )
    return FileResponse(
        path=str(storage_path),
        filename=cf.original_filename,
        media_type=cf.mime_type,
    )


# ── SSE status stream ────────────────────────────────────────────


@casefile_router.get("/{case_id}/status-stream")
async def status_stream(case_id: str, request: Request):
    """SSE endpoint for real-time file processing status updates."""
    user = _require_user(request)
    _require_case(case_id, user_id=user.sub)

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
async def create_note(case_id: str, body: CreateNoteRequest, request: Request):
    """Create a note on a case (optionally linked to a file)."""
    user = _require_user(request)
    storage = _get_case_storage()
    _require_case(case_id, user_id=user.sub)

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
    _audit(
        "note.create", request,
        resource_type="note", resource_id=note.id,
        metadata={"case_id": case_id},
    )
    return _note_response(note)


@casefile_router.get("/{case_id}/notes", response_model=NoteListResponse)
async def list_notes(case_id: str, request: Request, file_id: str | None = None):
    """List notes for a case, optionally filtered by file_id."""
    user = _require_user(request)
    storage = _get_case_storage()
    _require_case(case_id, user_id=user.sub)
    notes = storage.list_notes(case_id, file_id=file_id)
    return NoteListResponse(notes=[_note_response(n) for n in notes])


@casefile_router.patch(
    "/{case_id}/notes/{note_id}", response_model=NoteResponse
)
async def update_note(case_id: str, note_id: str, body: UpdateNoteRequest, request: Request):
    """Update a note's content."""
    user = _require_user(request)
    storage = _get_case_storage()
    _require_case(case_id, user_id=user.sub)

    note = storage.get_note(note_id)
    if note is None or note.case_id != case_id:
        raise HTTPException(404, f"Note not found: {note_id}")

    updated = storage.update_note(note_id, body.content)
    if updated is None:
        raise HTTPException(404, f"Note not found: {note_id}")

    logger.info("note_updated", case_id=case_id, note_id=note_id)
    _audit(
        "note.update", request,
        resource_type="note", resource_id=note_id,
        metadata={"case_id": case_id},
    )
    return _note_response(updated)


@casefile_router.delete("/{case_id}/notes/{note_id}", status_code=204)
async def delete_note(case_id: str, note_id: str, request: Request):
    """Delete a note."""
    user = _require_user(request)
    storage = _get_case_storage()
    _require_case(case_id, user_id=user.sub)

    note = storage.get_note(note_id)
    if note is None or note.case_id != case_id:
        raise HTTPException(404, f"Note not found: {note_id}")

    storage.delete_note(note_id)
    logger.info("note_deleted", case_id=case_id, note_id=note_id)
    _audit(
        "note.delete", request,
        resource_type="note", resource_id=note_id,
        metadata={"case_id": case_id},
    )


# ── Case Chat ─────────────────────────────────────────────────────

MAX_CHAT_TURNS = 10


def _get_case_chat_service():
    """Get the CaseChatService singleton from deps."""
    from employee_help.api.deps import get_case_chat_service

    svc = get_case_chat_service()
    if svc is None:
        raise HTTPException(503, "Case chat service not available")
    return svc


def _validate_chat_history(
    history: list, turn_number: int
) -> str | None:
    """Validate conversation history. Returns error message or None."""
    expected_len = (turn_number - 1) * 2
    if len(history) != expected_len:
        return (
            f"History length {len(history)} doesn't match "
            f"turn {turn_number} (expected {expected_len})"
        )
    for i, turn in enumerate(history):
        expected_role = "user" if i % 2 == 0 else "assistant"
        if turn.role != expected_role:
            return (
                f"History turn {i} has role '{turn.role}', "
                f"expected '{expected_role}'"
            )
    return None


@casefile_router.post("/{case_id}/chat")
async def case_chat(case_id: str, body: CaseChatRequest, request: Request):
    """Stream a case chat answer via server-sent events.

    SSE event types:
      - sources: case file and KB retrieval results
      - token: text chunk from LLM stream
      - done: final metadata (model, tokens, cost, duration, session_id)
      - error: error message
    """
    user = _require_user(request)
    storage = _get_case_storage()
    _require_case(case_id, user_id=user.sub)
    chat_service = _get_case_chat_service()

    start_time = time.monotonic()
    query_id = str(uuid.uuid4())

    # Determine turn number from history
    turn_number = len(body.conversation_history) // 2 + 1

    # Turn limit enforcement
    if turn_number > MAX_CHAT_TURNS:
        def limit_sse():
            yield _sse_event("error", {
                "message": "TURN_LIMIT_EXCEEDED",
                "max_turns": MAX_CHAT_TURNS,
            })
        return StreamingResponse(
            limit_sse(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # Validate conversation history
    if body.conversation_history:
        validation_error = _validate_chat_history(
            body.conversation_history, turn_number
        )
        if validation_error:
            raise HTTPException(422, validation_error)

    # Resolve or create session
    session_id = body.session_id
    if session_id:
        session = storage.get_chat_session(session_id)
        if session is None or session.case_id != case_id:
            raise HTTPException(404, f"Chat session not found: {session_id}")
    else:
        session = CaseChatSession(case_id=case_id)
        session = storage.create_chat_session(session)
        session_id = session.id

    def generate_sse():
        try:
            # Choose single-turn or multi-turn path
            if turn_number > 1 and body.conversation_history:
                history = [
                    {"role": t.role, "content": t.content}
                    for t in body.conversation_history
                ]
                text_stream, case_results, kb_results, stream_metadata = (
                    chat_service.generate_stream_multiturn(
                        query=body.query,
                        case_id=case_id,
                        conversation_history=history,
                        turn_number=turn_number,
                        max_turns=MAX_CHAT_TURNS,
                    )
                )
            else:
                text_stream, case_results, kb_results, stream_metadata = (
                    chat_service.generate_stream(
                        query=body.query,
                        case_id=case_id,
                    )
                )

            # Emit sources
            case_sources = [
                CaseChatSourceInfo(
                    source_type="case_file",
                    title=r.original_filename,
                    relevance_score=r.relevance_score,
                    file_id=r.file_id,
                    chunk_id=r.chunk_id,
                    heading_path=r.heading_path,
                ).model_dump()
                for r in case_results
            ]
            kb_sources = [
                CaseChatSourceInfo(
                    source_type="knowledge_base",
                    title=r.heading_path or r.citation or "",
                    relevance_score=r.relevance_score,
                    chunk_id=r.chunk_id,
                    content_category=r.content_category,
                    heading_path=r.heading_path,
                ).model_dump()
                for r in kb_results
            ]
            yield _sse_event("sources", {
                "case_sources": case_sources,
                "kb_sources": kb_sources,
            })

            # Stream LLM tokens
            full_text_parts: list[str] = []
            for chunk in text_stream:
                full_text_parts.append(chunk)
                yield _sse_event("token", {"text": chunk})

            # Collect metadata
            duration_ms = int((time.monotonic() - start_time) * 1000)
            meta = stream_metadata[0] if stream_metadata else {}
            model = meta.get("model", "")
            input_tokens = meta.get("input_tokens", 0)
            output_tokens = meta.get("output_tokens", 0)

            cost = 0.0
            if model:
                from employee_help.generation.models import TokenUsage

                usage = TokenUsage(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    model=model,
                )
                cost = usage.cost_estimate

            # Persist turns to DB (best-effort)
            try:
                full_text = "".join(full_text_parts)

                # Save user turn
                user_turn = CaseChatTurn(
                    session_id=session_id,
                    turn_number=turn_number,
                    role="user",
                    content=body.query,
                )
                storage.create_chat_turn(user_turn)

                # Save assistant turn with sources
                sources_json = json.dumps({
                    "case_sources": [
                        {"file_id": r.file_id, "filename": r.original_filename}
                        for r in case_results
                    ],
                    "kb_sources": [
                        {"chunk_id": r.chunk_id, "heading": r.heading_path}
                        for r in kb_results
                    ],
                })
                assistant_turn = CaseChatTurn(
                    session_id=session_id,
                    turn_number=turn_number,
                    role="assistant",
                    content=full_text,
                    sources=sources_json,
                )
                storage.create_chat_turn(assistant_turn)

                # Update session timestamp
                storage.update_chat_session_timestamp(session_id)
            except Exception:
                logger.warning("chat_turn_persist_failed", exc_info=True)

            is_final_turn = turn_number >= MAX_CHAT_TURNS

            yield _sse_event("done", {
                "query_id": query_id,
                "session_id": session_id,
                "turn_number": turn_number,
                "max_turns": MAX_CHAT_TURNS,
                "is_final_turn": is_final_turn,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_estimate": round(cost, 6),
                "duration_ms": duration_ms,
            })

            logger.info(
                "case_chat_complete",
                case_id=case_id,
                session_id=session_id,
                turn_number=turn_number,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                duration_ms=duration_ms,
            )
            _audit(
                "case.chat", request,
                resource_type="case", resource_id=case_id,
                metadata={
                    "session_id": session_id,
                    "turn_number": turn_number,
                    "query_id": query_id,
                },
            )

        except Exception as e:
            logger.error("case_chat_error", error=str(e), exc_info=True)
            yield _sse_event("error", {"message": str(e)})

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@casefile_router.get(
    "/{case_id}/chat/sessions", response_model=ChatSessionListResponse
)
async def list_chat_sessions(case_id: str, request: Request):
    """List chat sessions for a case."""
    user = _require_user(request)
    storage = _get_case_storage()
    _require_case(case_id, user_id=user.sub)

    sessions = storage.list_chat_sessions(case_id)
    results = []
    for s in sessions:
        turn_count = storage.get_chat_session_turn_count(s.id)
        # Each pair of user+assistant = 1 logical turn
        results.append(ChatSessionResponse(
            id=s.id,
            case_id=s.case_id,
            created_at=s.created_at.isoformat(),
            updated_at=s.updated_at.isoformat(),
            turn_count=turn_count,
        ))
    return ChatSessionListResponse(sessions=results)


@casefile_router.get(
    "/{case_id}/chat/{session_id}", response_model=ChatHistoryResponse
)
async def get_chat_history(case_id: str, session_id: str, request: Request):
    """Get the full chat history for a session."""
    user = _require_user(request)
    storage = _get_case_storage()
    _require_case(case_id, user_id=user.sub)

    session = storage.get_chat_session(session_id)
    if session is None or session.case_id != case_id:
        raise HTTPException(404, f"Chat session not found: {session_id}")

    turns = storage.list_chat_turns(session_id)
    turn_responses = []
    for t in turns:
        sources = None
        if t.sources:
            try:
                sources = json.loads(t.sources)
            except (json.JSONDecodeError, TypeError):
                pass
        turn_responses.append(ChatTurnResponse(
            id=t.id,
            session_id=t.session_id,
            turn_number=t.turn_number,
            role=t.role,
            content=t.content,
            sources=sources,
            created_at=t.created_at.isoformat(),
        ))

    return ChatHistoryResponse(
        session_id=session_id,
        case_id=case_id,
        turns=turn_responses,
    )


@casefile_router.delete("/{case_id}/chat/{session_id}", status_code=204)
async def delete_chat_session(case_id: str, session_id: str, request: Request):
    """Delete a chat session and its turns."""
    user = _require_user(request)
    storage = _get_case_storage()
    _require_case(case_id, user_id=user.sub)

    session = storage.get_chat_session(session_id)
    if session is None or session.case_id != case_id:
        raise HTTPException(404, f"Chat session not found: {session_id}")

    storage.delete_chat_session(session_id)
