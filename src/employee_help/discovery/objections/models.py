"""Data models for the discovery objection drafter.

Pure data — no DB, no ML, no external services.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ObjectionCategory(str, Enum):
    """Functional categories of discovery objections."""

    FORM = "form"
    SUBSTANTIVE = "substantive"
    BURDEN = "burden"
    DEVICE_SPECIFIC = "device_specific"


class Verbosity(str, Enum):
    """Verbosity level for objection explanations."""

    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


class ObjectionStrength(str, Enum):
    """LLM-assessed strength of an objection for a specific request."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ResponseDiscoveryType(str, Enum):
    """Discovery device types for response/objection workflows.

    Separate from DiscoveryToolType which describes request generation tools.
    """

    INTERROGATORIES = "interrogatories"
    RFPS = "rfps"
    RFAS = "rfas"


DISCOVERY_TYPE_LABELS: dict[ResponseDiscoveryType, str] = {
    ResponseDiscoveryType.INTERROGATORIES: "Special Interrogatories",
    ResponseDiscoveryType.RFPS: "Requests for Production",
    ResponseDiscoveryType.RFAS: "Requests for Admission",
}

DISCOVERY_TYPE_SINGULAR: dict[ResponseDiscoveryType, str] = {
    ResponseDiscoveryType.INTERROGATORIES: "Interrogatory",
    ResponseDiscoveryType.RFPS: "Request for Production",
    ResponseDiscoveryType.RFAS: "Request for Admission",
}


class PartyRole(str, Enum):
    """Which side of the case the user is on."""

    PLAINTIFF = "plaintiff"
    DEFENDANT = "defendant"


# ---------------------------------------------------------------------------
# Citation dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StatutoryCitation:
    """A statutory citation in the knowledge base."""

    code: str  # "CCP", "Evid. Code", "Cal. Const."
    section: str  # "§2017.010"
    description: str = ""


@dataclass(frozen=True)
class CaseCitation:
    """A case law citation in the knowledge base."""

    name: str  # "Emerson Electric Co. v. Superior Court"
    year: int  # 1997
    citation: str  # "(1997) 16 Cal.4th 1101, 1108"
    reporter_key: str  # "16 Cal.4th 1101" — unique ID for validation
    holding: str = ""
    use: str = ""  # When to cite this case


# ---------------------------------------------------------------------------
# Knowledge base dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ObjectionGround:
    """A single objection ground from the knowledge base."""

    ground_id: str
    label: str
    category: ObjectionCategory
    description: str
    last_verified: str
    statutory_citations: tuple[StatutoryCitation, ...]
    case_citations: tuple[CaseCitation, ...]
    applies_to: tuple[ResponseDiscoveryType, ...]
    sample_language: dict[Verbosity, str]
    strength_signals: tuple[str, ...]


# ---------------------------------------------------------------------------
# Request parsing dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ObjectionRequest:
    """A single parsed discovery request to generate objections for."""

    request_number: int | str
    request_text: str
    discovery_type: ResponseDiscoveryType


@dataclass
class ParsedRequest:
    """A request extracted by the parser, with edit metadata."""

    id: str  # Unique ID for frontend state management
    request_number: int | str
    request_text: str
    discovery_type: ResponseDiscoveryType
    is_selected: bool = True


@dataclass(frozen=True)
class SkippedSection:
    """A non-request section detected and skipped by the parser."""

    section_type: str  # "definitions", "instructions", "caption", "pos", "identification"
    content: str
    defined_terms: tuple[str, ...] = ()  # Only for definitions sections


@dataclass(frozen=True)
class ExtractedMetadata:
    """Metadata extracted from the discovery document by the parser."""

    propounding_party: str = ""
    responding_party: str = ""
    set_number: int | None = None
    case_name: str = ""


@dataclass
class ParseResult:
    """Complete result from parsing a discovery document."""

    requests: list[ParsedRequest]
    skipped_sections: list[SkippedSection]
    metadata: ExtractedMetadata
    detected_type: ResponseDiscoveryType | None
    is_response_shell: bool = False
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Analysis result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class GeneratedObjection:
    """A single generated objection for a specific request."""

    ground: ObjectionGround
    explanation: str  # LLM-generated, request-specific
    verbosity: Verbosity
    strength: ObjectionStrength
    statutory_citations: list[StatutoryCitation]
    case_citations: list[CaseCitation]
    citation_warnings: list[str] = field(default_factory=list)


@dataclass
class AnalysisResult:
    """Complete analysis result for a single request."""

    request: ObjectionRequest
    objections: list[GeneratedObjection]
    no_objections_rationale: str | None = None
    formatted_output: str = ""


@dataclass
class BatchAnalysisResult:
    """Complete result from analyzing a batch of requests."""

    results: list[AnalysisResult]
    model_used: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_estimate: float = 0.0
    duration_ms: int = 0
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Template dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ObjectionTemplate:
    """A template for formatting objection output."""

    name: str
    template: str
    separator: str = "; "


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TEMPLATE = ObjectionTemplate(
    name="Default",
    template="Objection: {OBJECTION}: {EXPLANATION} ({STATUTORY_CITATION}; {CASE_CITATION})",
    separator="; ",
)

FORMAL_TEMPLATE = ObjectionTemplate(
    name="Formal/Narrative",
    template=(
        "Responding Party objects on the following grounds: "
        "Pursuant to {STATUTORY_CITATION}, {OBJECTION}: {EXPLANATION}. "
        "{CASE_CITATION}."
    ),
    separator=". ",
)

CONCISE_TEMPLATE = ObjectionTemplate(
    name="Concise",
    template="{OBJECTION} ({STATUTORY_CITATION}).",
    separator="; ",
)

BUILT_IN_TEMPLATES = (DEFAULT_TEMPLATE, FORMAL_TEMPLATE, CONCISE_TEMPLATE)

WAIVER_PREAMBLE = (
    "Subject to and without waiving the foregoing objections, "
    "Responding Party responds as follows:"
)

DISCLAIMER = (
    "This tool provides draft objections for attorney review. "
    "All objections must be reviewed by a licensed attorney before service. "
    "Meritless objections may result in sanctions under CCP §2023.010(e) "
    "and §2023.050."
)
