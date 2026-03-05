"""API endpoints for the discovery objection drafter."""

from __future__ import annotations

from typing import Any, Literal

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from employee_help.api.sanitize import sanitize_text
from employee_help.discovery.objections.models import (
    DISCLAIMER,
    DEFAULT_TEMPLATE,
    ObjectionTemplate,
    ResponseDiscoveryType,
    Verbosity,
)

logger = structlog.get_logger(__name__)

objection_router = APIRouter(prefix="/api/objections", tags=["objections"])

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ObjectionGroundInfo(BaseModel):
    """A single objection ground (for UI display)."""

    ground_id: str
    label: str
    category: str
    description: str
    applies_to: list[str]
    statutory_citations: list[dict[str, str]]
    case_citations: list[dict[str, Any]]
    last_verified: str


class GroundsResponse(BaseModel):
    """Response for GET /api/objections/grounds."""

    grounds: list[ObjectionGroundInfo]
    total: int


class ParseRequest(BaseModel):
    """Request body for POST /api/objections/parse."""

    text: str = Field(..., min_length=1, max_length=100000)
    discovery_type: str | None = Field(
        default=None,
        description="Override auto-detection: interrogatories, rfps, or rfas",
    )

    @field_validator("text", mode="before")
    @classmethod
    def sanitize_text_field(cls, v: str) -> str:
        if isinstance(v, str):
            return sanitize_text(v)
        return v


class ParsedRequestInfo(BaseModel):
    """A single parsed request (for the editable card list)."""

    id: str
    request_number: int | str
    request_text: str
    discovery_type: str
    is_selected: bool = True


class SkippedSectionInfo(BaseModel):
    """A skipped non-request section."""

    section_type: str
    content: str
    defined_terms: list[str] = []


class ExtractedMetadataInfo(BaseModel):
    """Metadata extracted from the document."""

    propounding_party: str = ""
    responding_party: str = ""
    set_number: int | None = None
    case_name: str = ""


class ParseResponse(BaseModel):
    """Response for POST /api/objections/parse."""

    requests: list[ParsedRequestInfo]
    skipped_sections: list[SkippedSectionInfo]
    metadata: ExtractedMetadataInfo
    detected_type: str | None
    is_response_shell: bool = False
    warnings: list[str] = []


class ObjectionRequestInput(BaseModel):
    """A single request to generate objections for."""

    request_number: int = Field(..., ge=1)
    request_text: str = Field(..., min_length=1, max_length=5000)
    discovery_type: str = "interrogatories"

    @field_validator("request_text", mode="before")
    @classmethod
    def sanitize_request(cls, v: str) -> str:
        if isinstance(v, str):
            return sanitize_text(v)
        return v


class GenerateRequest(BaseModel):
    """Request body for POST /api/objections/generate."""

    requests: list[ObjectionRequestInput] = Field(..., min_length=1, max_length=50)
    verbosity: Literal["short", "medium", "long"] = "medium"
    party_role: Literal["plaintiff", "defendant"] = "defendant"
    template: str | None = None
    separator: str = "; "
    include_request_text: bool = False
    include_waiver_language: bool = False
    ground_ids: list[str] | None = None
    model: str | None = None


class GeneratedObjectionInfo(BaseModel):
    """A single generated objection."""

    ground_id: str
    label: str
    category: str
    explanation: str
    strength: str
    statutory_citations: list[dict[str, str]]
    case_citations: list[dict[str, Any]]
    citation_warnings: list[str] = []


class RequestAnalysisInfo(BaseModel):
    """Analysis result for a single request."""

    request_number: int | str
    request_text: str
    discovery_type: str
    objections: list[GeneratedObjectionInfo]
    no_objections_rationale: str | None = None
    formatted_output: str = ""


class GenerateResponse(BaseModel):
    """Response for POST /api/objections/generate."""

    results: list[RequestAnalysisInfo]
    formatted_text: str
    model_used: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_estimate: float = 0.0
    duration_ms: int = 0
    warnings: list[str] = []
    disclaimer: str = DISCLAIMER


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@objection_router.get("/grounds", response_model=GroundsResponse)
async def list_grounds(discovery_type: str | None = None):
    """List all objection grounds, optionally filtered by discovery type."""
    kb = _get_knowledge_base()

    dtype = None
    if discovery_type:
        try:
            dtype = ResponseDiscoveryType(discovery_type)
        except ValueError:
            raise HTTPException(400, f"Invalid discovery_type: {discovery_type}")

    grounds = kb.get_grounds(discovery_type=dtype)

    items = [
        ObjectionGroundInfo(
            ground_id=g.ground_id,
            label=g.label,
            category=g.category.value,
            description=g.description,
            applies_to=[t.value for t in g.applies_to],
            statutory_citations=[
                {"code": s.code, "section": s.section, "description": s.description}
                for s in g.statutory_citations
            ],
            case_citations=[
                {
                    "name": c.name,
                    "year": c.year,
                    "citation": c.citation,
                    "reporter_key": c.reporter_key,
                    "holding": c.holding,
                }
                for c in g.case_citations
            ],
            last_verified=g.last_verified,
        )
        for g in grounds
    ]

    return GroundsResponse(grounds=items, total=len(items))


@objection_router.post("/parse", response_model=ParseResponse)
async def parse_requests(body: ParseRequest):
    """Parse pasted text into individual discovery requests."""
    from employee_help.discovery.objections.parser import RequestParser

    parser = RequestParser()

    dtype = None
    if body.discovery_type:
        try:
            dtype = ResponseDiscoveryType(body.discovery_type)
        except ValueError:
            raise HTTPException(400, f"Invalid discovery_type: {body.discovery_type}")

    result = parser.parse_text(body.text, discovery_type=dtype)

    return ParseResponse(
        requests=[
            ParsedRequestInfo(
                id=r.id,
                request_number=r.request_number,
                request_text=r.request_text,
                discovery_type=r.discovery_type.value,
                is_selected=r.is_selected,
            )
            for r in result.requests
        ],
        skipped_sections=[
            SkippedSectionInfo(
                section_type=s.section_type,
                content=s.content,
                defined_terms=list(s.defined_terms),
            )
            for s in result.skipped_sections
        ],
        metadata=ExtractedMetadataInfo(
            propounding_party=result.metadata.propounding_party,
            responding_party=result.metadata.responding_party,
            set_number=result.metadata.set_number,
            case_name=result.metadata.case_name,
        ),
        detected_type=result.detected_type.value if result.detected_type else None,
        is_response_shell=result.is_response_shell,
        warnings=result.warnings,
    )


@objection_router.post("/generate", response_model=GenerateResponse)
async def generate_objections(body: GenerateRequest):
    """Generate objections for parsed discovery requests."""
    from employee_help.discovery.objections.models import (
        ObjectionRequest,
        PartyRole,
    )

    analyzer = _get_analyzer()
    formatter = _get_formatter()

    # Convert inputs
    requests = [
        ObjectionRequest(
            request_number=r.request_number,
            request_text=r.request_text,
            discovery_type=ResponseDiscoveryType(r.discovery_type),
        )
        for r in body.requests
    ]

    verbosity = Verbosity(body.verbosity)
    party_role = PartyRole(body.party_role)

    # Run analysis
    batch_result = analyzer.analyze_batch(
        requests,
        verbosity=verbosity,
        party_role=party_role,
        model=body.model,
        ground_ids=body.ground_ids,
    )

    # Format results
    template = DEFAULT_TEMPLATE
    if body.template:
        template = ObjectionTemplate(
            name="Custom", template=body.template, separator=body.separator
        )

    for result in batch_result.results:
        result.formatted_output = formatter.format_request(
            result,
            template=template,
            include_request_text=body.include_request_text,
            include_waiver_language=body.include_waiver_language,
        )

    formatted_text = formatter.format_batch(
        batch_result.results,
        template=template,
        include_request_text=body.include_request_text,
        include_waiver_language=body.include_waiver_language,
    )

    # Build response
    result_items = [
        RequestAnalysisInfo(
            request_number=r.request.request_number,
            request_text=r.request.request_text,
            discovery_type=r.request.discovery_type.value,
            objections=[
                GeneratedObjectionInfo(
                    ground_id=o.ground.ground_id,
                    label=o.ground.label,
                    category=o.ground.category.value,
                    explanation=o.explanation,
                    strength=o.strength.value,
                    statutory_citations=[
                        {"code": s.code, "section": s.section, "description": s.description}
                        for s in o.statutory_citations
                    ],
                    case_citations=[
                        {
                            "name": c.name,
                            "year": c.year,
                            "citation": c.citation,
                            "reporter_key": c.reporter_key,
                        }
                        for c in o.case_citations
                    ],
                    citation_warnings=o.citation_warnings,
                )
                for o in r.objections
            ],
            no_objections_rationale=r.no_objections_rationale,
            formatted_output=r.formatted_output,
        )
        for r in batch_result.results
    ]

    logger.info(
        "objections_generated",
        request_count=len(requests),
        total_objections=sum(len(r.objections) for r in result_items),
        model=batch_result.model_used,
        cost=f"${batch_result.cost_estimate:.4f}",
        duration_ms=batch_result.duration_ms,
    )

    return GenerateResponse(
        results=result_items,
        formatted_text=formatted_text,
        model_used=batch_result.model_used,
        input_tokens=batch_result.input_tokens,
        output_tokens=batch_result.output_tokens,
        cost_estimate=batch_result.cost_estimate,
        duration_ms=batch_result.duration_ms,
        warnings=batch_result.warnings,
    )


# ---------------------------------------------------------------------------
# Service singletons (lazy-initialized, matching deps.py pattern)
# ---------------------------------------------------------------------------

_knowledge_base = None
_analyzer = None
_formatter = None


def _get_knowledge_base():
    """Get or create the knowledge base singleton."""
    global _knowledge_base
    if _knowledge_base is None:
        from employee_help.discovery.objections.knowledge_base import ObjectionKnowledgeBase

        _knowledge_base = ObjectionKnowledgeBase()
    return _knowledge_base


def _get_analyzer():
    """Get or create the analyzer singleton."""
    global _analyzer
    if _analyzer is None:
        from employee_help.discovery.objections.analyzer import ObjectionAnalyzer
        from employee_help.discovery.objections.validator import CitationValidator
        from employee_help.generation.llm import LLMClient

        kb = _get_knowledge_base()
        llm_client = LLMClient(timeout=120.0)
        validator = CitationValidator(kb.get_reporter_keys())
        _analyzer = ObjectionAnalyzer(llm_client, kb, validator)
    return _analyzer


def _get_formatter():
    """Get or create the formatter singleton."""
    global _formatter
    if _formatter is None:
        from employee_help.discovery.objections.formatter import ObjectionFormatter

        _formatter = ObjectionFormatter()
    return _formatter
