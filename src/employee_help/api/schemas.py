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


class SourceFreshnessInfo(BaseModel):
    """Freshness info for a single source."""

    slug: str
    age_days: float | None = None
    status: str = "unknown"


class SourceRefreshStatusInfo(BaseModel):
    """Per-source refresh status for /api/refresh-status."""

    slug: str
    source_type: str
    last_refreshed_at: str | None = None
    age_days: float | None = None
    max_age_days: int = 7
    status: str = "unknown"
    consecutive_failures: int = 0
    cron_hint: str = ""


class RefreshStatusResponse(BaseModel):
    """Response body for GET /api/refresh-status."""

    knowledge_base: str = "unknown"
    sources_stale: int = 0
    sources_fresh: int = 0
    sources_never_run: int = 0
    sources: list[SourceRefreshStatusInfo] = []


class DashboardSourceInfo(BaseModel):
    """Per-source detail for the dashboard."""

    slug: str
    name: str
    source_type: str
    tier: str = "unknown"
    content_category: str = "unknown"
    extraction_method: str = "unknown"
    document_count: int = 0
    chunk_count: int = 0
    last_refreshed_at: str | None = None
    age_days: float | None = None
    max_age_days: int = 7
    status: str = "unknown"
    static: bool = False
    cron_hint: str = ""
    last_run_status: str | None = None
    last_run_summary: dict = {}
    first_ingested_at: str | None = None
    consecutive_failures: int = 0


class DashboardResponse(BaseModel):
    """Response body for GET /api/dashboard."""

    knowledge_base: str = "unknown"
    total_sources: int = 0
    total_documents: int = 0
    total_chunks: int = 0
    sources_fresh: int = 0
    sources_stale: int = 0
    sources_never_run: int = 0
    sources: list[DashboardSourceInfo] = []


class HealthResponse(BaseModel):
    """Response body for GET /api/health."""

    status: str = "ok"
    embedding_model_loaded: bool = False
    vector_store_connected: bool = False
    knowledge_base: str = "unknown"
    sources_stale: int = 0
    oldest_source: SourceFreshnessInfo | None = None


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


# ── Discovery tool schemas ──────────────────────────────────────────


class PartyInfoSchema(BaseModel):
    """A named party in the case."""

    name: str = Field(..., min_length=1, max_length=200)
    is_entity: bool = False
    entity_type: str | None = Field(default=None, max_length=50)

    @field_validator("name", mode="before")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        if isinstance(v, str):
            return sanitize_text(v)
        return v


class AttorneyInfoSchema(BaseModel):
    """Attorney or self-represented party contact information."""

    name: str = Field(..., min_length=1, max_length=200)
    sbn: str = Field(..., max_length=20)
    address: str = Field(..., min_length=1, max_length=300)
    city_state_zip: str = Field(..., min_length=1, max_length=200)
    phone: str = Field(..., min_length=1, max_length=30)
    email: str = Field(..., min_length=1, max_length=200)
    firm_name: str | None = Field(default=None, max_length=200)
    fax: str | None = Field(default=None, max_length=30)
    is_pro_per: bool = False
    attorney_for: str = Field(default="", max_length=200)

    @field_validator("name", "address", "city_state_zip", "email", mode="before")
    @classmethod
    def sanitize_fields(cls, v: str) -> str:
        if isinstance(v, str):
            return sanitize_text(v)
        return v


class CaseInfoSchema(BaseModel):
    """Case-level information for discovery document generation."""

    case_number: str = Field(..., min_length=1, max_length=50)
    court_county: str = Field(..., min_length=1, max_length=100)
    party_role: str = Field(..., pattern=r"^(plaintiff|defendant)$")
    plaintiffs: list[PartyInfoSchema] = Field(..., min_length=1, max_length=20)
    defendants: list[PartyInfoSchema] = Field(..., min_length=1, max_length=20)
    attorney: AttorneyInfoSchema

    court_name: str = Field(default="Superior Court of California", max_length=200)
    court_branch: str | None = Field(default=None, max_length=200)
    court_address: str | None = Field(default=None, max_length=300)
    court_city_zip: str | None = Field(default=None, max_length=200)
    judge_name: str | None = Field(default=None, max_length=200)
    department: str | None = Field(default=None, max_length=50)

    complaint_filed_date: date | None = None
    trial_date: date | None = None
    does_included: bool = True
    set_number: int = Field(default=1, ge=1, le=10)

    @field_validator("case_number", "court_county", mode="before")
    @classmethod
    def sanitize_case_fields(cls, v: str) -> str:
        if isinstance(v, str):
            return sanitize_text(v)
        return v


class DiscoveryRequestSchema(BaseModel):
    """A single discovery request item (SROG, RFPD, or RFA)."""

    id: str
    text: str
    category: str
    is_selected: bool = True
    is_custom: bool = False
    order: int = 0
    notes: str | None = None
    rfa_type: str | None = None  # "fact" or "genuineness" (RFAs only)


class DiscoverySuggestRequest(BaseModel):
    """Request body for POST /api/discovery/suggest."""

    claim_types: list[str] = Field(..., min_length=1, max_length=10)
    party_role: str = Field(..., pattern=r"^(plaintiff|defendant)$")
    tool_type: str = Field(...)
    has_rfas: bool = False
    responding_is_entity: bool = False

    @field_validator("tool_type")
    @classmethod
    def validate_tool_type(cls, v: str) -> str:
        valid = {"frogs_general", "frogs_employment", "srogs", "rfpds", "rfas"}
        if v not in valid:
            raise ValueError(f"Invalid tool_type: {v!r}. Must be one of {sorted(valid)}")
        return v

    @field_validator("claim_types")
    @classmethod
    def validate_claim_types(cls, v: list[str]) -> list[str]:
        from employee_help.discovery.models import ClaimType

        valid = {ct.value for ct in ClaimType}
        for ct in v:
            if ct not in valid:
                raise ValueError(f"Invalid claim_type: {ct!r}")
        return v


class SuggestedSectionInfo(BaseModel):
    """A suggested DISC-001 or DISC-002 section."""

    section_number: str
    title: str = ""
    description: str = ""


class SuggestedCategoryInfo(BaseModel):
    """A suggested category for SROG/RFPD/RFA banks."""

    category: str
    label: str
    request_count: int = 0


class DiscoverySuggestResponse(BaseModel):
    """Response body for POST /api/discovery/suggest."""

    tool_type: str
    party_role: str
    suggested_sections: list[SuggestedSectionInfo] = []
    suggested_categories: list[SuggestedCategoryInfo] = []
    total_suggested: int = 0


class DiscoveryGenerateRequest(BaseModel):
    """Request body for POST /api/discovery/generate."""

    tool_type: str = Field(...)
    case_info: CaseInfoSchema
    selected_sections: list[str] = Field(default_factory=list, max_length=200)
    selected_requests: list[DiscoveryRequestSchema] = Field(
        default_factory=list, max_length=200
    )
    adverse_actions: list[str] = Field(default_factory=list, max_length=20)
    custom_definitions: dict[str, str] | None = None
    include_definitions: bool = True

    @field_validator("tool_type")
    @classmethod
    def validate_tool_type(cls, v: str) -> str:
        valid = {"frogs_general", "frogs_employment", "srogs", "rfpds", "rfas"}
        if v not in valid:
            raise ValueError(f"Invalid tool_type: {v!r}. Must be one of {sorted(valid)}")
        return v

    @model_validator(mode="after")
    def validate_selections(self):
        """Ensure the right selection fields are populated for the tool type."""
        if self.tool_type in ("frogs_general", "frogs_employment"):
            if not self.selected_sections:
                raise ValueError(
                    f"selected_sections is required for {self.tool_type}"
                )
        elif self.tool_type in ("srogs", "rfpds", "rfas"):
            if not self.selected_requests:
                raise ValueError(
                    f"selected_requests is required for {self.tool_type}"
                )
        return self


class DiscoveryBankItemInfo(BaseModel):
    """A single item in a discovery request bank."""

    id: str
    text: str
    category: str
    order: int
    rfa_type: str | None = None
    applicable_roles: list[str] | None = None
    applicable_claims: list[str] | None = None


class DiscoveryBankCategoryInfo(BaseModel):
    """A category in a discovery request bank."""

    key: str
    label: str
    count: int


class DiscoveryBankResponse(BaseModel):
    """Response body for GET /api/discovery/banks/{tool}."""

    tool_type: str
    categories: list[DiscoveryBankCategoryInfo]
    items: list[DiscoveryBankItemInfo]
    total_items: int
    limit: int | None = None  # 35 for SROGs/RFAs, None for RFPDs


class DiscoveryDefinitionInfo(BaseModel):
    """A single legal definition."""

    term: str
    definition: str


class DiscoveryDefinitionsResponse(BaseModel):
    """Response body for GET /api/discovery/definitions."""

    definitions: list[DiscoveryDefinitionInfo]
    production_instructions: str


# ── Proof of Service schemas ─────────────────────────────────────────


class POSGenerateRequest(BaseModel):
    """Request body for POST /api/discovery/generate-pos."""

    case_info: CaseInfoSchema
    server_name: str = Field(..., min_length=1, max_length=200)
    server_address: str = Field(..., min_length=1, max_length=300)
    served_party_name: str = Field(..., min_length=1, max_length=200)
    served_party_address: str = Field(..., min_length=1, max_length=500)
    service_method: str = Field(..., pattern=r"^(personal|mail_in_state|mail_out_of_state|mail_international|electronic|overnight)$")
    service_date: date
    documents_served: list[str] = Field(..., min_length=1, max_length=20)

    @field_validator("server_name", "served_party_name", mode="before")
    @classmethod
    def sanitize_names(cls, v: str) -> str:
        if isinstance(v, str):
            return sanitize_text(v)
        return v

    @field_validator("documents_served")
    @classmethod
    def validate_document_names(cls, v: list[str]) -> list[str]:
        for name in v:
            if not name.strip():
                raise ValueError("Document name cannot be empty")
            if len(name) > 200:
                raise ValueError("Document name too long (max 200 chars)")
        return v
