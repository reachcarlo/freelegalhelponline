"""Data models for discovery document generation.

Pure data — no DB, no ML, no external services.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class PartyRole(str, Enum):
    """Which side of the case the user is on."""

    PLAINTIFF = "plaintiff"
    DEFENDANT = "defendant"


class DiscoveryToolType(str, Enum):
    """The four (five) discovery tool outputs we support."""

    FROGS_GENERAL = "frogs_general"  # DISC-001
    FROGS_EMPLOYMENT = "frogs_employment"  # DISC-002
    SROGS = "srogs"  # Special Interrogatories
    RFPDS = "rfpds"  # Request for Production of Documents
    RFAS = "rfas"  # Requests for Admission


class ClaimType(str, Enum):
    """California employment claim types for discovery mapping."""

    FEHA_DISCRIMINATION = "feha_discrimination"
    FEHA_HARASSMENT = "feha_harassment"
    FEHA_RETALIATION = "feha_retaliation"
    FEHA_FAILURE_TO_PREVENT = "feha_failure_to_prevent"
    FEHA_FAILURE_TO_ACCOMMODATE = "feha_failure_to_accommodate"
    FEHA_FAILURE_INTERACTIVE_PROCESS = "feha_failure_interactive_process"
    WRONGFUL_TERMINATION_PUBLIC_POLICY = "wrongful_termination_public_policy"
    BREACH_IMPLIED_CONTRACT = "breach_implied_contract"
    BREACH_COVENANT_GOOD_FAITH = "breach_covenant_good_faith"
    WAGE_THEFT = "wage_theft"
    MEAL_REST_BREAK = "meal_rest_break"
    OVERTIME = "overtime"
    MISCLASSIFICATION = "misclassification"
    WHISTLEBLOWER_RETALIATION = "whistleblower_retaliation"
    LABOR_CODE_RETALIATION = "labor_code_retaliation"
    CFRA_FMLA = "cfra_fmla"
    DEFAMATION = "defamation"
    IIED = "intentional_infliction_emotional_distress"
    NIED = "negligent_infliction_emotional_distress"
    PAGA = "paga"
    UNFAIR_BUSINESS_PRACTICES = "unfair_business_practices"


CLAIM_TYPE_LABELS: dict[ClaimType, str] = {
    ClaimType.FEHA_DISCRIMINATION: "FEHA Discrimination",
    ClaimType.FEHA_HARASSMENT: "FEHA Harassment",
    ClaimType.FEHA_RETALIATION: "FEHA Retaliation",
    ClaimType.FEHA_FAILURE_TO_PREVENT: "FEHA Failure to Prevent",
    ClaimType.FEHA_FAILURE_TO_ACCOMMODATE: "FEHA Failure to Accommodate",
    ClaimType.FEHA_FAILURE_INTERACTIVE_PROCESS: "FEHA Failure to Engage Interactive Process",
    ClaimType.WRONGFUL_TERMINATION_PUBLIC_POLICY: "Wrongful Termination in Violation of Public Policy",
    ClaimType.BREACH_IMPLIED_CONTRACT: "Breach of Implied Contract",
    ClaimType.BREACH_COVENANT_GOOD_FAITH: "Breach of Implied Covenant of Good Faith and Fair Dealing",
    ClaimType.WAGE_THEFT: "Wage Theft / Unpaid Wages",
    ClaimType.MEAL_REST_BREAK: "Meal and Rest Break Violations",
    ClaimType.OVERTIME: "Overtime Violations",
    ClaimType.MISCLASSIFICATION: "Worker Misclassification",
    ClaimType.WHISTLEBLOWER_RETALIATION: "Whistleblower Retaliation (Lab. Code 1102.5)",
    ClaimType.LABOR_CODE_RETALIATION: "Labor Code Retaliation (Lab. Code 98.6)",
    ClaimType.CFRA_FMLA: "CFRA / FMLA Family Leave Violations",
    ClaimType.DEFAMATION: "Defamation",
    ClaimType.IIED: "Intentional Infliction of Emotional Distress",
    ClaimType.NIED: "Negligent Infliction of Emotional Distress",
    ClaimType.PAGA: "PAGA (Private Attorneys General Act)",
    ClaimType.UNFAIR_BUSINESS_PRACTICES: "Unfair Business Practices (Bus. & Prof. Code 17200)",
}


class WageClaimType(str, Enum):
    """Specific wage claim sub-types."""

    UNPAID_WAGES = "unpaid_wages"
    OVERTIME = "overtime"
    MEAL_BREAKS = "meal_breaks"
    REST_BREAKS = "rest_breaks"
    MISCLASSIFICATION = "misclassification"
    WAITING_TIME = "waiting_time"
    WAGE_STATEMENT = "wage_statement"
    MINIMUM_WAGE = "minimum_wage"


class TerminationType(str, Enum):
    """How the employment ended."""

    INVOLUNTARY = "involuntary"
    VOLUNTARY = "voluntary"
    CONSTRUCTIVE = "constructive"


class ServiceMethod(str, Enum):
    """Discovery service methods with associated CCP extensions."""

    PERSONAL = "personal"
    MAIL_IN_STATE = "mail_in_state"
    MAIL_OUT_OF_STATE = "mail_out_of_state"
    MAIL_INTERNATIONAL = "mail_international"
    ELECTRONIC = "electronic"
    OVERNIGHT = "overnight"


# Additional days for each service method (CCP 1013 / 1010.6)
SERVICE_METHOD_EXTENSIONS: dict[ServiceMethod, int] = {
    ServiceMethod.PERSONAL: 0,
    ServiceMethod.MAIL_IN_STATE: 5,
    ServiceMethod.MAIL_OUT_OF_STATE: 10,
    ServiceMethod.MAIL_INTERNATIONAL: 20,
    ServiceMethod.ELECTRONIC: 2,  # court days, not calendar
    ServiceMethod.OVERNIGHT: 2,  # court days, not calendar
}


class ProtectedClass(str, Enum):
    """FEHA-protected characteristics."""

    RACE = "race"
    COLOR = "color"
    NATIONAL_ORIGIN = "national_origin"
    ANCESTRY = "ancestry"
    SEX = "sex"
    GENDER = "gender"
    GENDER_IDENTITY = "gender_identity"
    GENDER_EXPRESSION = "gender_expression"
    SEXUAL_ORIENTATION = "sexual_orientation"
    AGE = "age"
    DISABILITY_PHYSICAL = "disability_physical"
    DISABILITY_MENTAL = "disability_mental"
    MEDICAL_CONDITION = "medical_condition"
    GENETIC_INFORMATION = "genetic_information"
    MARITAL_STATUS = "marital_status"
    MILITARY_VETERAN_STATUS = "military_veteran_status"
    RELIGION = "religion"
    REPRODUCTIVE_HEALTH = "reproductive_health"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PartyInfo:
    """A named party in the case."""

    name: str
    is_entity: bool = False
    entity_type: str | None = None  # "corporation", "llc", "partnership", etc.


@dataclass(frozen=True)
class AttorneyInfo:
    """Attorney or self-represented party contact information."""

    name: str
    sbn: str  # State Bar Number (empty string for pro per)
    address: str
    city_state_zip: str
    phone: str
    email: str
    firm_name: str | None = None
    fax: str | None = None
    is_pro_per: bool = False
    attorney_for: str = ""  # e.g. "Plaintiff Jane Doe"


@dataclass(frozen=True)
class CaseInfo:
    """All case-level information needed for any discovery document."""

    case_number: str
    court_county: str
    party_role: PartyRole
    plaintiffs: tuple[PartyInfo, ...]
    defendants: tuple[PartyInfo, ...]
    attorney: AttorneyInfo

    court_name: str = "Superior Court of California"
    court_branch: str | None = None
    court_address: str | None = None
    court_city_zip: str | None = None
    judge_name: str | None = None
    department: str | None = None

    complaint_filed_date: date | None = None
    trial_date: date | None = None

    does_included: bool = True
    set_number: int = 1


@dataclass(frozen=True)
class ClaimContext:
    """Employment claim details that drive discovery suggestions."""

    claim_types: tuple[ClaimType, ...]
    employment_start_date: date
    employment_end_date: date | None = None
    is_still_employed: bool = False
    termination_type: TerminationType | None = None
    protected_classes: tuple[ProtectedClass, ...] = ()
    wage_claims: tuple[WageClaimType, ...] = ()
    adverse_actions: tuple[str, ...] = ()
    filed_govt_complaint: bool = False
    govt_complaint_agency: str | None = None


@dataclass(frozen=True)
class DiscoveryRequest:
    """A single interrogatory, request for production, or request for admission."""

    id: str  # Unique ID (e.g., "srog_employment_001")
    text: str  # Full text of the request (may contain {VARIABLE} placeholders)
    category: str  # Category slug (e.g., "employment_relationship")
    is_selected: bool = True
    is_custom: bool = False  # User-added (not from bank)
    order: int = 0  # Display/output order
    notes: str | None = None  # Internal notes (not in output)
    applicable_roles: tuple[str, ...] = ("plaintiff", "defendant")
    applicable_claims: tuple[str, ...] = ()  # empty = all claims (no gate)


@dataclass
class DiscoverySession:
    """Complete state for a discovery workflow session.

    This is mutable (not frozen) because it accumulates state across
    wizard steps. For MVP, it lives client-side. The schema supports
    future server-side persistence.
    """

    id: str  # UUID
    tool_type: DiscoveryToolType
    case_info: CaseInfo
    claim_context: ClaimContext
    requests: list[DiscoveryRequest] = field(default_factory=list)
    selected_sections: list[float] = field(default_factory=list)  # FROGs only
    definitions: dict[str, str] = field(default_factory=dict)
    production_instructions: str | None = None  # RFPDs only
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    generated_at: datetime | None = None


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SROG_LIMIT = 35
"""Maximum specially prepared interrogatories without a CCP 2030.050 declaration."""

RFA_FACT_LIMIT = 35
"""Maximum fact-based RFAs without a CCP 2033.050 declaration.
Genuineness-of-document RFAs are unlimited."""

RESPONSE_DEADLINE_DAYS = 30
"""Base response deadline for all written discovery (CCP 2030.260(a))."""

DISCOVERY_CUTOFF_DAYS_BEFORE_TRIAL = 30
"""Discovery must be completed 30 days before trial (CCP 2024.020(a))."""

MOTION_CUTOFF_DAYS_BEFORE_TRIAL = 15
"""Discovery motions must be heard 15 days before trial (CCP 2024.020(a))."""

DISCLAIMER = (
    "This tool generates discovery documents based on your selections. "
    "It does not constitute legal advice. The generated documents should be "
    "reviewed by a licensed California attorney before filing. Discovery rules "
    "are governed by CCP 2030.010-2033.420. Consult the California Rules of "
    "Court and local rules for additional formatting and filing requirements."
)
