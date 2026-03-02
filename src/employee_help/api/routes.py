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
    AgencyRecommendationInfo,
    AgencyRoutingRequest,
    AgencyRoutingResponse,
    AskRequest,
    DeadlineInfo,
    DeadlineRequest,
    DeadlineResponse,
    DocumentationFieldInfo,
    EvidenceItemInfo,
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
    IdentifiedIssueInfo,
    IncidentDocRequest,
    IncidentDocResponse,
    IntakeAnswerOptionInfo,
    IntakeQuestionsResponse,
    IntakeQuestionInfo,
    IntakeRequest,
    IntakeResponse,
    IntakeSummaryRequest,
    SourceInfo,
    ToolRecommendationInfo,
    UnpaidWagesRequest,
    UnpaidWagesResponse,
    WageBreakdownInfo,
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


@router.post("/agency-routing", response_model=AgencyRoutingResponse)
async def agency_routing_endpoint(request: AgencyRoutingRequest):
    """Get agency routing recommendations for an employment issue."""
    from employee_help.tools.routing import (
        DISCLAIMER,
        ISSUE_TYPE_LABELS,
        get_agency_routing,
    )

    results = get_agency_routing(
        request.issue_type,
        is_government_employee=request.is_government_employee,
    )

    return AgencyRoutingResponse(
        issue_type=request.issue_type.value,
        issue_type_label=ISSUE_TYPE_LABELS[request.issue_type],
        is_government_employee=request.is_government_employee,
        recommendations=[
            AgencyRecommendationInfo(
                agency_name=r.agency.name,
                agency_acronym=r.agency.acronym,
                agency_description=r.agency.description,
                agency_handles=r.agency.handles,
                portal_url=r.agency.portal_url,
                phone=r.agency.phone,
                filing_methods=list(r.agency.filing_methods),
                process_overview=r.agency.process_overview,
                typical_timeline=r.agency.typical_timeline,
                priority=r.priority.value,
                reason=r.reason,
                what_to_file=r.what_to_file,
                notes=r.notes,
                related_claim_type=r.related_claim_type,
            )
            for r in results
        ],
        disclaimer=DISCLAIMER,
    )


@router.post("/unpaid-wages", response_model=UnpaidWagesResponse)
async def unpaid_wages_endpoint(request: UnpaidWagesRequest):
    """Calculate unpaid wages and related damages."""
    from decimal import Decimal

    from employee_help.tools.unpaid_wages import (
        DISCLAIMER,
        calculate_unpaid_wages,
    )

    result = calculate_unpaid_wages(
        hourly_rate=Decimal(str(request.hourly_rate)),
        unpaid_hours=Decimal(str(request.unpaid_hours)),
        employment_status=request.employment_status,
        termination_date=request.termination_date,
        final_wages_paid_date=request.final_wages_paid_date,
        missed_meal_breaks=request.missed_meal_breaks,
        missed_rest_breaks=request.missed_rest_breaks,
        unpaid_since=request.unpaid_since,
    )

    return UnpaidWagesResponse(
        items=[
            WageBreakdownInfo(
                category=item.category,
                label=item.label,
                amount=item.amount,
                legal_citation=item.legal_citation,
                description=item.description,
                notes=item.notes,
            )
            for item in result.items
        ],
        total=result.total,
        hourly_rate=result.hourly_rate,
        unpaid_hours=result.unpaid_hours,
        disclaimer=DISCLAIMER,
    )


@router.post("/incident-guide", response_model=IncidentDocResponse)
async def incident_guide_endpoint(request: IncidentDocRequest):
    """Get incident documentation guidance for a workplace incident type."""
    from employee_help.tools.incident_docs import (
        DISCLAIMER,
        get_incident_guide,
    )

    guide = get_incident_guide(request.incident_type)

    def _field_info(f):
        return DocumentationFieldInfo(
            name=f.name,
            label=f.label,
            field_type=f.field_type.value,
            placeholder=f.placeholder,
            required=f.required,
            help_text=f.help_text,
            options=list(f.options),
        )

    return IncidentDocResponse(
        incident_type=guide.incident_type.value,
        incident_type_label=guide.label,
        description=guide.description,
        common_fields=[_field_info(f) for f in guide.common_fields],
        specific_fields=[_field_info(f) for f in guide.specific_fields],
        prompts=list(guide.prompts),
        evidence_checklist=[
            EvidenceItemInfo(
                description=e.description,
                importance=e.importance.value,
                tip=e.tip,
            )
            for e in guide.evidence_checklist
        ],
        related_claim_types=list(guide.related_claim_types),
        legal_tips=list(guide.legal_tips),
        disclaimer=DISCLAIMER,
    )


@router.get("/intake-questions", response_model=IntakeQuestionsResponse)
async def intake_questions_endpoint():
    """Return the guided intake questionnaire."""
    from employee_help.tools.intake import get_questions

    questions = get_questions()

    return IntakeQuestionsResponse(
        questions=[
            IntakeQuestionInfo(
                question_id=q.question_id,
                question_text=q.question_text,
                help_text=q.help_text,
                options=[
                    IntakeAnswerOptionInfo(
                        key=opt.key.value,
                        label=opt.label,
                        help_text=opt.help_text,
                    )
                    for opt in q.options
                ],
                allow_multiple=q.allow_multiple,
                show_if=[k.value for k in q.show_if] if q.show_if else None,
            )
            for q in questions
        ]
    )


@router.post("/intake", response_model=IntakeResponse)
async def intake_endpoint(request: IntakeRequest):
    """Evaluate intake answers and return identified issues with tool recommendations."""
    from employee_help.tools.intake import DISCLAIMER, evaluate_intake

    result = evaluate_intake(request.answers)

    return IntakeResponse(
        identified_issues=[
            IdentifiedIssueInfo(
                issue_type=issue.issue_type.value,
                issue_label=issue.issue_label,
                confidence=issue.confidence,
                description=issue.description,
                related_claim_types=list(issue.related_claim_types),
                tools=[
                    ToolRecommendationInfo(
                        tool_name=t.tool_name,
                        tool_label=t.tool_label,
                        tool_path=t.tool_path,
                        description=t.description,
                        prefill_params=dict(t.prefill_params),
                    )
                    for t in issue.tools
                ],
                has_deadline_urgency=issue.has_deadline_urgency,
            )
            for issue in result.identified_issues
        ],
        is_government_employee=result.is_government_employee,
        employment_status=result.employment_status,
        summary=result.summary,
        disclaimer=DISCLAIMER,
    )


@router.post("/intake-summary")
async def intake_summary(request: IntakeSummaryRequest):
    """Stream a personalised rights summary based on intake answers.

    Evaluates the intake answers, converts the result into a natural-language
    query, and streams the consumer-mode RAG response via SSE.
    """
    from employee_help.tools.intake import build_intake_query, evaluate_intake

    start_time = time.monotonic()
    query_id = str(uuid.uuid4())

    try:
        answer_service = get_answer_service()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    # Evaluate intake and build query
    try:
        intake_result = evaluate_intake(request.answers)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    if not intake_result.identified_issues:
        def no_issues_sse():
            yield _sse_event("done", {
                "query_id": query_id,
                "model": "",
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_estimate": 0.0,
                "duration_ms": 0,
                "warnings": ["No issues identified from intake answers."],
            })
        return StreamingResponse(
            no_issues_sse(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    query = build_intake_query(intake_result)

    def generate_sse():
        source_count = 0
        try:
            stream, retrieval_results, stream_metadata = (
                answer_service.generate_stream(query=query, mode="consumer")
            )

            source_count = len(retrieval_results)

            # Emit sources
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

            # Stream LLM tokens
            for chunk in stream:
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

            yield _sse_event("done", {
                "query_id": query_id,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_estimate": round(cost, 6),
                "duration_ms": duration_ms,
                "warnings": [],
            })

            _log_query(
                query_id=query_id,
                query=query,
                mode="consumer",
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost,
                duration_ms=duration_ms,
                source_count=source_count,
            )

        except Exception as e:
            logger.error("intake_summary_stream_error", error=str(e), exc_info=True)
            yield _sse_event("error", {"message": str(e)})

            duration_ms = int((time.monotonic() - start_time) * 1000)
            _log_query(
                query_id=query_id,
                query=query,
                mode="consumer",
                duration_ms=duration_ms,
                source_count=source_count,
                error=str(e),
            )

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
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
