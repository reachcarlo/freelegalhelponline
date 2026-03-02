"""Pydantic request/response models for the API."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from employee_help.api.sanitize import detect_prompt_injection, sanitize_text
from employee_help.tools.deadlines import ClaimType
from employee_help.tools.incident_docs import IncidentType
from employee_help.tools.routing import IssueType
from employee_help.tools.unpaid_wages import EmploymentStatus


class ConversationTurn(BaseModel):
    """A single turn in the conversation history."""

    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=20000)

    @field_validator("content", mode="before")
    @classmethod
    def sanitize_content(cls, v: str) -> str:
        if isinstance(v, str):
            return sanitize_text(v)
        return v


class AskRequest(BaseModel):
    """Request body for POST /api/ask."""

    query: str = Field(..., min_length=1, max_length=2000)
    mode: Literal["consumer", "attorney"] = "consumer"
    session_id: str | None = Field(default=None, max_length=100, pattern=r"^[a-zA-Z0-9\-_]+$")
    conversation_history: list[ConversationTurn] = Field(default_factory=list, max_length=20)
    turn_number: int = Field(default=1, ge=1, le=10)

    @field_validator("query", mode="before")
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        if isinstance(v, str):
            return sanitize_text(v)
        return v

    @field_validator("query")
    @classmethod
    def check_prompt_injection(cls, v: str) -> str:
        match = detect_prompt_injection(v)
        if match:
            raise ValueError(
                "Your query was flagged by our safety filter. "
                "Please rephrase your question about California employment law."
            )
        return v


class SourceInfo(BaseModel):
    """A single source/chunk used in the answer."""

    chunk_id: int
    content_category: str
    citation: str | None = None
    source_url: str = ""
    heading_path: str = ""
    relevance_score: float = 0.0


class AskMetadata(BaseModel):
    """Metadata returned after answer generation completes."""

    query_id: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_estimate: float = 0.0
    duration_ms: int = 0
    warnings: list[str] = []
    session_id: str | None = None
    turn_number: int = 1
    max_turns: int = 3
    is_final_turn: bool = False


class FeedbackRequest(BaseModel):
    """Request body for POST /api/feedback."""

    query_id: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9\-]+$")
    rating: Literal[1, -1]


class FeedbackResponse(BaseModel):
    """Response body for POST /api/feedback."""

    status: str = "ok"


class HealthResponse(BaseModel):
    """Response body for GET /api/health."""

    status: str = "ok"
    embedding_model_loaded: bool = False
    vector_store_connected: bool = False


# ── Deadline calculator schemas ──────────────────────────────────────


class DeadlineRequest(BaseModel):
    """Request body for POST /api/deadlines."""

    claim_type: ClaimType
    incident_date: date

    @field_validator("incident_date")
    @classmethod
    def validate_incident_date(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("Incident date cannot be in the future.")
        if v.year < 1970:
            raise ValueError("Incident date must be after 1970.")
        return v


class DeadlineInfo(BaseModel):
    """A single computed deadline."""

    name: str
    description: str
    deadline_date: str  # ISO format
    days_remaining: int
    urgency: str
    filing_entity: str
    portal_url: str
    legal_citation: str
    notes: str


class DeadlineResponse(BaseModel):
    """Response body for POST /api/deadlines."""

    claim_type: str
    claim_type_label: str
    incident_date: str  # ISO format
    deadlines: list[DeadlineInfo]
    disclaimer: str


# ── Agency routing schemas ───────────────────────────────────────────


class AgencyRoutingRequest(BaseModel):
    """Request body for POST /api/agency-routing."""

    issue_type: IssueType
    is_government_employee: bool = False


class AgencyRecommendationInfo(BaseModel):
    """A single agency recommendation."""

    agency_name: str
    agency_acronym: str
    agency_description: str
    agency_handles: str
    portal_url: str
    phone: str
    filing_methods: list[str]
    process_overview: str
    typical_timeline: str
    priority: str
    reason: str
    what_to_file: str
    notes: str
    related_claim_type: str | None = None


class AgencyRoutingResponse(BaseModel):
    """Response body for POST /api/agency-routing."""

    issue_type: str
    issue_type_label: str
    is_government_employee: bool
    recommendations: list[AgencyRecommendationInfo]
    disclaimer: str


# ── Unpaid wages calculator schemas ────────────────────────────────


# ── Incident documentation schemas ──────────────────────────────────


class IncidentDocRequest(BaseModel):
    """Request body for POST /api/incident-guide."""

    incident_type: IncidentType


class DocumentationFieldInfo(BaseModel):
    """A single form field description."""

    name: str
    label: str
    field_type: str
    placeholder: str
    required: bool
    help_text: str
    options: list[str]


class EvidenceItemInfo(BaseModel):
    """A single evidence checklist item."""

    description: str
    importance: str
    tip: str


class IncidentDocResponse(BaseModel):
    """Response body for POST /api/incident-guide."""

    incident_type: str
    incident_type_label: str
    description: str
    common_fields: list[DocumentationFieldInfo]
    specific_fields: list[DocumentationFieldInfo]
    prompts: list[str]
    evidence_checklist: list[EvidenceItemInfo]
    related_claim_types: list[str]
    legal_tips: list[str]
    disclaimer: str


# ── Guided intake schemas ──────────────────────────────────────────


class IntakeAnswerOptionInfo(BaseModel):
    """A single answer option within a question."""

    key: str
    label: str
    help_text: str


class IntakeQuestionInfo(BaseModel):
    """A single intake question with its options."""

    question_id: str
    question_text: str
    help_text: str
    options: list[IntakeAnswerOptionInfo]
    allow_multiple: bool
    show_if: list[str] | None = None


class IntakeQuestionsResponse(BaseModel):
    """Response body for GET /api/intake-questions."""

    questions: list[IntakeQuestionInfo]


def _validate_intake_answers(v: list[str]) -> list[str]:
    """Shared validation for intake answer keys."""
    from employee_help.tools.intake import AnswerKey

    valid_keys = {k.value for k in AnswerKey}
    for answer in v:
        if answer not in valid_keys:
            raise ValueError(f"Invalid answer key: {answer!r}")
    return v


class IntakeRequest(BaseModel):
    """Request body for POST /api/intake."""

    answers: list[str] = Field(..., min_length=1, max_length=30)

    @field_validator("answers")
    @classmethod
    def validate_answer_keys(cls, v: list[str]) -> list[str]:
        return _validate_intake_answers(v)


class IntakeSummaryRequest(BaseModel):
    """Request body for POST /api/intake-summary."""

    answers: list[str] = Field(..., min_length=1, max_length=30)

    @field_validator("answers")
    @classmethod
    def validate_answer_keys(cls, v: list[str]) -> list[str]:
        return _validate_intake_answers(v)


class ToolRecommendationInfo(BaseModel):
    """A tool recommendation with pre-filled parameters."""

    tool_name: str
    tool_label: str
    tool_path: str
    description: str
    prefill_params: dict[str, str]


class IdentifiedIssueInfo(BaseModel):
    """An identified employment issue with recommendations."""

    issue_type: str
    issue_label: str
    confidence: str
    description: str
    related_claim_types: list[str]
    tools: list[ToolRecommendationInfo]
    has_deadline_urgency: bool


class IntakeResponse(BaseModel):
    """Response body for POST /api/intake."""

    identified_issues: list[IdentifiedIssueInfo]
    is_government_employee: bool
    employment_status: str
    summary: str
    disclaimer: str


class UnpaidWagesRequest(BaseModel):
    """Request body for POST /api/unpaid-wages."""

    hourly_rate: float = Field(..., gt=0, le=1000)
    unpaid_hours: float = Field(..., ge=0, le=10000)
    employment_status: EmploymentStatus = EmploymentStatus.still_employed
    termination_date: date | None = None
    final_wages_paid_date: date | None = None
    missed_meal_breaks: int = Field(default=0, ge=0, le=1000)
    missed_rest_breaks: int = Field(default=0, ge=0, le=1000)
    unpaid_since: date | None = None

    @field_validator("termination_date")
    @classmethod
    def validate_termination_date(cls, v: date | None, info) -> date | None:
        if v is not None and v > date.today():
            raise ValueError("Termination date cannot be in the future.")
        return v

    @field_validator("final_wages_paid_date")
    @classmethod
    def validate_final_wages_paid_date(cls, v: date | None, info) -> date | None:
        if v is not None and v > date.today():
            raise ValueError("Final wages paid date cannot be in the future.")
        return v

    @field_validator("unpaid_since")
    @classmethod
    def validate_unpaid_since(cls, v: date | None) -> date | None:
        if v is not None and v > date.today():
            raise ValueError("Unpaid since date cannot be in the future.")
        return v

    @model_validator(mode="after")
    def validate_cross_field_rules(self):
        if self.employment_status != EmploymentStatus.still_employed:
            if self.termination_date is None:
                raise ValueError(
                    "Termination date is required when employment status is not 'still_employed'."
                )
        if self.final_wages_paid_date is not None and self.termination_date is not None:
            if self.final_wages_paid_date < self.termination_date:
                raise ValueError(
                    "Final wages paid date cannot be before termination date."
                )
        return self


class WageBreakdownInfo(BaseModel):
    """A single line item in the wage breakdown."""

    category: str
    label: str
    amount: str
    legal_citation: str
    description: str
    notes: str


class UnpaidWagesResponse(BaseModel):
    """Response body for POST /api/unpaid-wages."""

    items: list[WageBreakdownInfo]
    total: str
    hourly_rate: str
    unpaid_hours: str
    disclaimer: str
