"""API endpoints for the Employee Help RAG pipeline."""

from __future__ import annotations

import hashlib
import json
import time
import uuid

import structlog
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from employee_help.api.deps import (
    get_answer_service,
    get_conversation_config,
    get_feedback_store,
    get_retrieval_service,
)
from employee_help.api.schemas import (
    AskRequest,
    DeadlineInfo,
    DeadlineRequest,
    DeadlineResponse,
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
    SourceInfo,
)
from employee_help.generation.models import TokenUsage

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    try:
        retrieval = get_retrieval_service()
        return HealthResponse(
            status="ok",
            embedding_model_loaded=retrieval.embedding_service is not None,
            vector_store_connected=retrieval.vector_store is not None,
        )
    except RuntimeError:
        return HealthResponse(status="starting")


def _sse_event(event: str, data: dict) -> str:
    """Format a server-sent event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _validate_conversation_history(
    history: list, turn_number: int
) -> str | None:
    """Validate conversation history. Returns error message or None."""
    expected_len = (turn_number - 1) * 2
    if len(history) != expected_len:
        return f"History length {len(history)} doesn't match turn {turn_number} (expected {expected_len})"

    for i, turn in enumerate(history):
        expected_role = "user" if i % 2 == 0 else "assistant"
        if turn.role != expected_role:
            return f"History turn {i} has role '{turn.role}', expected '{expected_role}'"

    return None


@router.post("/ask")
async def ask_question(request: AskRequest):
    """Stream a RAG answer via server-sent events.

    SSE event types:
      - sources: retrieval results (sent before LLM generation starts)
      - token: text chunk from LLM stream
      - done: final metadata (model, tokens, cost, duration, query_id)
      - error: error message
    """
    start_time = time.monotonic()
    query_id = str(uuid.uuid4())

    try:
        answer_service = get_answer_service()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    # Determine if this is a multi-turn request
    is_multiturn = request.session_id is not None and request.turn_number > 0
    conv_config = get_conversation_config() if is_multiturn else None
    max_turns = 3
    session_id = request.session_id

    if is_multiturn and conv_config:
        max_turns_map = conv_config["max_turns"]
        max_turns = max_turns_map.get(request.mode, 3)

        # Turn limit enforcement
        if request.turn_number > max_turns:
            def limit_sse():
                yield _sse_event("error", {
                    "message": "TURN_LIMIT_EXCEEDED",
                    "max_turns": max_turns,
                })
            return StreamingResponse(
                limit_sse(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

        # Validate conversation history
        if request.conversation_history:
            validation_error = _validate_conversation_history(
                request.conversation_history, request.turn_number
            )
            if validation_error:
                raise HTTPException(status_code=422, detail=validation_error)

    is_final_turn = is_multiturn and request.turn_number >= max_turns

    def generate_sse():
        source_count = 0
        try:
            if is_multiturn and conv_config and request.turn_number > 1:
                # Multi-turn path
                history = [
                    {"role": t.role, "content": t.content}
                    for t in request.conversation_history
                ]
                stream, retrieval_results, stream_metadata = (
                    answer_service.generate_stream_multiturn(
                        query=request.query,
                        mode=request.mode,
                        conversation_history=history,
                        turn_number=request.turn_number,
                        max_turns=max_turns,
                        history_token_budget=conv_config["history_token_budget"],
                        short_followup_threshold=conv_config["short_followup_threshold"],
                    )
                )
            else:
                # Single-turn path (backward compatible)
                stream, retrieval_results, stream_metadata = (
                    answer_service.generate_stream(
                        query=request.query,
                        mode=request.mode,
                    )
                )

            source_count = len(retrieval_results)

            # Emit sources immediately
            sources = [
                SourceInfo(
                    chunk_id=r.chunk_id,
                    content_category=r.content_category,
                    citation=r.citation,
                    source_url=r.source_url,
                    heading_path=r.heading_path,
                    relevance_score=r.relevance_score,
                ).model_dump()
                for r in retrieval_results
            ]
            yield _sse_event("sources", {"sources": sources})

            # Stream LLM tokens (accumulate text for post-stream verification)
            full_text_parts: list[str] = []
            for chunk in stream:
                full_text_parts.append(chunk)
                yield _sse_event("token", {"text": chunk})

            # Emit final metadata
            duration_ms = int((time.monotonic() - start_time) * 1000)
            meta = stream_metadata[0] if stream_metadata else {}
            model = meta.get("model", "")
            input_tokens = meta.get("input_tokens", 0)
            output_tokens = meta.get("output_tokens", 0)

            cost = 0.0
            if model:
                usage = TokenUsage(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    model=model,
                )
                cost = usage.cost_estimate

            # Run citation verification for attorney mode
            citation_verifications: list[dict] = []
            if request.mode == "attorney":
                full_text = "".join(full_text_parts)
                try:
                    scored = answer_service.verify_answer_citations(full_text)
                    citation_verifications = [
                        {
                            "citation_text": s.citation_text,
                            "citation_type": s.citation_type,
                            "confidence": s.confidence.value,
                            "verification_status": s.verification_status,
                            "detail": s.detail,
                        }
                        for s in scored
                    ]
                except Exception:
                    logger.warning("citation_verification_failed", exc_info=True)

            done_data: dict = {
                "query_id": query_id,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_estimate": round(cost, 6),
                "duration_ms": duration_ms,
                "warnings": [],
                "citation_verifications": citation_verifications,
            }

            # Include conversation metadata when in multi-turn mode
            if is_multiturn:
                done_data["session_id"] = session_id
                done_data["turn_number"] = request.turn_number
                done_data["max_turns"] = max_turns
                done_data["is_final_turn"] = is_final_turn

            yield _sse_event("done", done_data)

            # Best-effort query logging
            _log_query(
                query_id=query_id,
                query=request.query,
                mode=request.mode,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost,
                duration_ms=duration_ms,
                source_count=source_count,
                session_id=session_id,
            )

            # Best-effort citation audit logging
            if citation_verifications:
                _log_citation_audit(
                    query_id=query_id,
                    verifications=citation_verifications,
                    model=model,
                    session_id=session_id,
                )

            # Best-effort session tracking
            if is_multiturn and session_id:
                _log_session(session_id, request.mode, request.turn_number)

        except Exception as e:
            logger.error("ask_stream_error", error=str(e), exc_info=True)
            yield _sse_event("error", {"message": str(e)})

            # Log errored query
            duration_ms = int((time.monotonic() - start_time) * 1000)
            _log_query(
                query_id=query_id,
                query=request.query,
                mode=request.mode,
                duration_ms=duration_ms,
                source_count=source_count,
                error=str(e),
                session_id=session_id,
            )

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _log_query(
    *,
    query_id: str,
    query: str,
    mode: str,
    model: str = "",
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost: float = 0.0,
    duration_ms: int = 0,
    source_count: int = 0,
    error: str | None = None,
    session_id: str | None = None,
) -> None:
    """Best-effort log a query to the feedback store."""
    try:
        store = get_feedback_store()
        if store is None:
            return
        from employee_help.feedback.models import QueryLogEntry

        query_hash = hashlib.sha256(query.strip().lower().encode()).hexdigest()
        store.log_query(
            QueryLogEntry(
                query_id=query_id,
                query_hash=query_hash,
                mode=mode,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_estimate=cost,
                duration_ms=duration_ms,
                source_count=source_count,
                error=error,
                session_id=session_id,
            )
        )
    except Exception:
        logger.warning("query_log_failed", query_id=query_id, exc_info=True)


def _log_session(session_id: str, mode: str, turn_number: int) -> None:
    """Best-effort log/update a conversation session."""
    try:
        store = get_feedback_store()
        if store is None:
            return
        store.create_or_update_session(session_id, mode, turn_number)
    except Exception:
        logger.warning("session_log_failed", session_id=session_id, exc_info=True)


def _log_citation_audit(
    *,
    query_id: str,
    verifications: list[dict],
    model: str = "",
    session_id: str | None = None,
) -> None:
    """Best-effort log citation verifications to the audit table."""
    try:
        store = get_feedback_store()
        if store is None:
            return
        from employee_help.feedback.models import CitationAuditEntry

        entries = [
            CitationAuditEntry(
                query_id=query_id,
                citation_text=v["citation_text"],
                citation_type=v["citation_type"],
                verification_status=v["verification_status"],
                confidence=v["confidence"],
                detail=v.get("detail"),
                model_used=model,
                session_id=session_id,
            )
            for v in verifications
        ]
        store.log_citation_audit(entries)
    except Exception:
        logger.warning("citation_audit_log_failed", query_id=query_id, exc_info=True)


@router.post("/deadlines", response_model=DeadlineResponse)
async def calculate_deadlines_endpoint(request: DeadlineRequest):
    """Calculate statute of limitations deadlines for a claim type."""
    from employee_help.tools.deadlines import (
        CLAIM_TYPE_LABELS,
        DISCLAIMER,
        calculate_deadlines,
    )

    results = calculate_deadlines(request.claim_type, request.incident_date)

    return DeadlineResponse(
        claim_type=request.claim_type.value,
        claim_type_label=CLAIM_TYPE_LABELS[request.claim_type],
        incident_date=request.incident_date.isoformat(),
        deadlines=[
            DeadlineInfo(
                name=r.name,
                description=r.description,
                deadline_date=r.deadline_date.isoformat(),
                days_remaining=r.days_remaining,
                urgency=r.urgency.value,
                filing_entity=r.filing_entity,
                portal_url=r.portal_url,
                legal_citation=r.legal_citation,
                notes=r.notes,
            )
            for r in results
        ],
        disclaimer=DISCLAIMER,
    )


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(request: FeedbackRequest):
    """Submit thumbs up/down feedback for a query."""
    store = get_feedback_store()
    if store is None:
        raise HTTPException(status_code=503, detail="Feedback store not available")

    from employee_help.feedback.models import FeedbackEntry

    try:
        store.add_feedback(FeedbackEntry(query_id=request.query_id, rating=request.rating))
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Unknown query_id: {request.query_id}")

    return FeedbackResponse(status="ok")
