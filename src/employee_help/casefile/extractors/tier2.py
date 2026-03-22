"""Tier2Extractor — LLM-based metadata extraction for litigation documents.

Uses Claude tool_use for structured output: extracts causes of action mapped
to ClaimType, employment relationship details, protected classes, and factual
allegations from complaint text.  Produces CaseFact objects ready for storage.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from jinja2 import Environment, FileSystemLoader

from employee_help.casefile.classifiers import DocumentType
from employee_help.discovery.models import CLAIM_TYPE_LABELS, ClaimType
from employee_help.generation.llm import LLMClient
from employee_help.storage.models import (
    CaseFact,
    ExtractionMethod,
    FactCategory,
)

if TYPE_CHECKING:
    from employee_help.privacy.engine import ObfuscationEngine

logger = structlog.get_logger(__name__)

# Max text length to send to LLM (roughly ~100k tokens at ~4 chars/token)
_MAX_TEXT_LENGTH = 400_000

# Confidence for LLM-extracted facts (higher than Tier 1 regex)
_LLM_CLAIM_CONFIDENCE = 0.85
_LLM_EMPLOYMENT_CONFIDENCE = 0.80
_LLM_PARTY_CONFIDENCE = 0.80
_LLM_DATE_CONFIDENCE = 0.75
_LLM_FINANCIAL_CONFIDENCE = 0.75

# Document types that Tier 2 can process
TIER2_DOC_TYPES = frozenset({
    DocumentType.COMPLAINT,
    DocumentType.ANSWER,
    DocumentType.DEMAND_LETTER,
})

PROMPTS_DIR = Path("config/prompts")

# ClaimType values for the tool schema enum
_CLAIM_TYPE_VALUES = [ct.value for ct in ClaimType]

# Claim type data for the Jinja2 template
_CLAIM_TYPE_TEMPLATE_DATA = [
    {"value": ct.value, "label": CLAIM_TYPE_LABELS.get(ct, ct.value)}
    for ct in ClaimType
]

# ── Tool schema for structured extraction ──────────────────────────────

EXTRACTION_TOOL = {
    "name": "submit_extraction",
    "description": (
        "Submit structured metadata extracted from a California employment "
        "litigation document."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "claims": {
                "type": "array",
                "description": "Causes of action / legal claims identified in the document.",
                "items": {
                    "type": "object",
                    "properties": {
                        "claim_type": {
                            "type": "string",
                            "enum": _CLAIM_TYPE_VALUES,
                            "description": "The California employment claim type.",
                        },
                        "status": {
                            "type": "string",
                            "enum": ["active", "dropped", "amended", "settled"],
                            "description": "Claim status. Default 'active' for new filings.",
                        },
                        "protected_class": {
                            "type": "string",
                            "description": (
                                "Protected class if applicable (e.g., race, gender, "
                                "age, disability, national_origin, religion, sexual_orientation)."
                            ),
                        },
                        "reason": {
                            "type": "string",
                            "description": "Brief summary of the factual basis for this claim.",
                        },
                        "confidence": {
                            "type": "number",
                            "description": "Confidence 0.0-1.0 that this claim is correctly identified.",
                        },
                    },
                    "required": ["claim_type", "status", "confidence"],
                },
            },
            "employment_periods": {
                "type": "array",
                "description": "Employment relationship details mentioned in the document.",
                "items": {
                    "type": "object",
                    "properties": {
                        "employer": {
                            "type": "string",
                            "description": "Employer name.",
                        },
                        "position": {
                            "type": "string",
                            "description": "Job title or position.",
                        },
                        "department": {
                            "type": "string",
                            "description": "Department or unit.",
                        },
                        "start_date": {
                            "type": "string",
                            "description": "Employment start date (ISO format YYYY-MM-DD).",
                        },
                        "end_date": {
                            "type": "string",
                            "description": "Employment end date (ISO format YYYY-MM-DD), null if current.",
                        },
                        "compensation_rate": {
                            "type": "number",
                            "description": "Compensation amount.",
                        },
                        "compensation_type": {
                            "type": "string",
                            "description": "Type of compensation (salary, hourly, commission).",
                        },
                        "pay_period": {
                            "type": "string",
                            "description": "Pay period (annual, monthly, biweekly, weekly, hourly).",
                        },
                        "change_reason": {
                            "type": "string",
                            "description": "Reason for employment change (terminated, resigned, laid_off, demoted).",
                        },
                    },
                    "required": ["employer"],
                },
            },
            "parties": {
                "type": "array",
                "description": "Parties identified in the document.",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Full name of the party.",
                        },
                        "role": {
                            "type": "string",
                            "enum": ["plaintiff", "defendant", "witness", "supervisor", "manager"],
                            "description": "Role in the litigation or employment relationship.",
                        },
                        "party_type": {
                            "type": "string",
                            "enum": ["individual", "entity"],
                            "description": "Whether the party is an individual or entity.",
                        },
                    },
                    "required": ["name", "role"],
                },
            },
            "key_dates": {
                "type": "array",
                "description": "Important dates mentioned in the document.",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {
                            "type": "string",
                            "description": "Description of the event (e.g., 'Termination Date', 'DFEH Complaint Filed').",
                        },
                        "date": {
                            "type": "string",
                            "description": "Date in ISO format YYYY-MM-DD.",
                        },
                        "date_type": {
                            "type": "string",
                            "enum": [
                                "hire_date", "termination_date", "complaint_filed",
                                "incident_date", "notice_date", "deadline",
                                "eeoc_filed", "dfeh_filed", "right_to_sue",
                                "other",
                            ],
                            "description": "Type of date for categorization.",
                        },
                    },
                    "required": ["label", "date"],
                },
            },
            "damages": {
                "type": "array",
                "description": "Monetary amounts or damages claimed.",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {
                            "type": "string",
                            "description": "Description (e.g., 'Lost Wages', 'Emotional Distress Damages').",
                        },
                        "amount": {
                            "type": "number",
                            "description": "Dollar amount if specified.",
                        },
                        "amount_type": {
                            "type": "string",
                            "enum": ["demand", "settlement", "damages", "wages", "penalty", "other"],
                            "description": "Type of financial amount.",
                        },
                    },
                    "required": ["label"],
                },
            },
            "factual_summary": {
                "type": "string",
                "description": (
                    "A concise 2-4 sentence summary of the key factual allegations "
                    "in the document. Focus on what happened, to whom, and when."
                ),
            },
        },
        "required": ["claims", "employment_periods", "parties", "key_dates", "damages"],
    },
}

# ── System prompt ──────────────────────────────────────────────────────

_FALLBACK_SYSTEM_PROMPT = """\
You are a legal document analyzer specializing in California employment law.

Your task is to extract structured metadata from litigation documents \
(complaints, answers, demand letters). Extract ALL relevant information \
you can identify — causes of action, employment details, parties, dates, \
and damages.

## Claim Mapping Rules

Map causes of action to the closest matching claim type from the enum.

## Protected Classes

When a FEHA claim mentions a protected class, extract it. Common values:
race, color, national_origin, ancestry, religion, sex, gender, \
gender_identity, gender_expression, sexual_orientation, marital_status, \
age, disability, medical_condition, genetic_information, military_status, \
pregnancy.

## Employment Details

Extract all employment periods mentioned. Include dates when available. \
For complaints, the plaintiff's employment with the defendant is most important.

## Confidence

Set confidence between 0.5 and 1.0:
- 0.9-1.0: Explicitly stated cause of action with clear heading
- 0.7-0.9: Clearly described but not as a formal heading
- 0.5-0.7: Implied or ambiguous reference

## Important

- Extract only what is actually stated or clearly implied in the text.
- Do not invent or assume facts not present in the document.
- For dates, use ISO format (YYYY-MM-DD). If only month/year, use the 1st.
- If an amount is not specified numerically, omit the amount field.
- For the factual summary, be objective and concise.\
"""


def build_system_prompt(doc_type: DocumentType = DocumentType.COMPLAINT) -> str:
    """Build the Tier 2 extraction system prompt from the Jinja2 template.

    Falls back to an inline prompt if the template file is not found.

    Args:
        doc_type: The document type being extracted.

    Returns:
        Rendered system prompt string.
    """
    try:
        env = Environment(
            loader=FileSystemLoader(str(PROMPTS_DIR)),
            autoescape=False,
        )
        template = env.get_template("extract_metadata.j2")
        return template.render(
            doc_type=doc_type.value,
            claim_types=_CLAIM_TYPE_TEMPLATE_DATA,
        )
    except Exception:
        logger.warning("tier2_template_fallback", doc_type=doc_type.value)
        return _FALLBACK_SYSTEM_PROMPT


class Tier2Extractor:
    """LLM-based metadata extractor for litigation documents.

    Takes extracted text from a case file and uses Claude tool_use to
    produce structured CaseFact objects for claims, employment details,
    parties, dates, and damages.

    This is NOT a FileExtractor (which extracts text from bytes). Instead,
    it operates on already-extracted text and produces higher-confidence
    facts than the Tier 1 regex extractors.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        *,
        model: str | None = None,
        obfuscation_engine: ObfuscationEngine | None = None,
    ) -> None:
        """Initialize with an LLM client.

        Args:
            llm_client: Configured LLMClient instance.
            model: Specific model to use. Defaults to attorney model (Sonnet).
            obfuscation_engine: Optional privacy engine. When provided, text is
                obfuscated before sending to the LLM and results are
                deobfuscated before returning.
        """
        self._llm = llm_client
        self._model = model
        self._obfuscation_engine = obfuscation_engine

    def extract(
        self,
        text: str,
        case_id: str,
        file_id: str,
        doc_type: DocumentType = DocumentType.COMPLAINT,
    ) -> Tier2Result:
        """Extract structured metadata from document text via LLM.

        Args:
            text: Extracted text content of the document.
            case_id: The case this file belongs to.
            file_id: The source file ID.
            doc_type: Document type (for context in the prompt).

        Returns:
            Tier2Result with facts and usage metadata.

        Raises:
            Tier2ExtractionError: If the LLM call fails or returns invalid data.
        """
        if not text or not text.strip():
            return Tier2Result(facts=[], input_tokens=0, output_tokens=0)

        # Truncate very long documents
        truncated = text[:_MAX_TEXT_LENGTH] if len(text) > _MAX_TEXT_LENGTH else text

        # Obfuscate text before sending to LLM (V2.2c.5)
        obf_ctx = None
        if self._obfuscation_engine is not None:
            obf_ctx = self._obfuscation_engine.create_context()
            truncated = self._obfuscation_engine.obfuscate(truncated, obf_ctx)
            logger.debug(
                "tier2_obfuscated",
                file_id=file_id,
                entity_count=obf_ctx.entity_count,
            )

        system_prompt = build_system_prompt(doc_type)

        user_message = (
            f"--- DOCUMENT TEXT ---\n{truncated}\n--- END DOCUMENT ---\n\n"
            "Extract all structured metadata from this document."
        )

        try:
            result = self._llm.generate_with_tools(
                system_prompt=system_prompt,
                user_message=user_message,
                tools=[EXTRACTION_TOOL],
                model=self._model,
                mode="attorney",
                max_tokens=4096,
                temperature=0.0,
                tool_choice={"type": "tool", "name": "submit_extraction"},
            )
        except Exception as e:
            logger.error("tier2_extraction_failed", error=str(e), file_id=file_id)
            raise Tier2ExtractionError(f"LLM extraction failed: {e}") from e

        tool_input = result.get("tool_input", {})
        if not tool_input:
            logger.warning("tier2_empty_response", file_id=file_id)
            return Tier2Result(
                facts=[],
                input_tokens=result.get("input_tokens", 0),
                output_tokens=result.get("output_tokens", 0),
            )

        # Deobfuscate structured output before creating CaseFacts (V2.2c.5)
        if obf_ctx is not None:
            _deobfuscate_extraction(tool_input, obf_ctx)

        # Parse structured output into CaseFacts
        facts = self._parse_extraction(tool_input, case_id, file_id)

        logger.info(
            "tier2_extraction_complete",
            file_id=file_id,
            fact_count=len(facts),
            claims=len(tool_input.get("claims", [])),
            employment_periods=len(tool_input.get("employment_periods", [])),
            parties=len(tool_input.get("parties", [])),
            key_dates=len(tool_input.get("key_dates", [])),
            damages=len(tool_input.get("damages", [])),
            input_tokens=result.get("input_tokens", 0),
            output_tokens=result.get("output_tokens", 0),
        )

        return Tier2Result(
            facts=facts,
            factual_summary=tool_input.get("factual_summary"),
            input_tokens=result.get("input_tokens", 0),
            output_tokens=result.get("output_tokens", 0),
            model=result.get("model", ""),
            duration_ms=result.get("duration_ms", 0),
            raw_output=tool_input,
        )

    def can_extract(self, doc_type: DocumentType) -> bool:
        """Check if this extractor handles the given document type."""
        return doc_type in TIER2_DOC_TYPES

    def _parse_extraction(
        self,
        data: dict,
        case_id: str,
        file_id: str,
    ) -> list[CaseFact]:
        """Convert LLM tool output into CaseFact objects."""
        facts: list[CaseFact] = []

        # Claims → FactCategory.CLAIM
        for claim in data.get("claims", []):
            claim_type_raw = claim.get("claim_type", "")
            # Validate against ClaimType enum
            if not _is_valid_claim_type(claim_type_raw):
                logger.warning(
                    "tier2_unknown_claim_type",
                    claim_type=claim_type_raw,
                    file_id=file_id,
                )
                continue

            value: dict = {
                "claim_type": claim_type_raw,
                "status": claim.get("status", "active"),
            }
            if claim.get("protected_class"):
                value["protected_class"] = claim["protected_class"]
            if claim.get("reason"):
                value["reason"] = claim["reason"]

            confidence = _clamp_confidence(
                claim.get("confidence", _LLM_CLAIM_CONFIDENCE)
            )

            facts.append(CaseFact(
                case_id=case_id,
                category=FactCategory.CLAIM,
                fact_type="claim",
                value=value,
                source_file_id=file_id,
                extraction_method=ExtractionMethod.LLM,
                confidence=confidence,
            ))

        # Employment periods → FactCategory.EMPLOYMENT
        for emp in data.get("employment_periods", []):
            emp_value: dict = {}
            if emp.get("employer"):
                emp_value["employer"] = emp["employer"]
            if emp.get("position"):
                emp_value["position"] = emp["position"]
            if emp.get("department"):
                emp_value["department"] = emp["department"]
            if emp.get("start_date"):
                emp_value["start_date"] = emp["start_date"]
            if emp.get("end_date"):
                emp_value["end_date"] = emp["end_date"]
            if emp.get("compensation_rate") is not None:
                emp_value["compensation_rate"] = emp["compensation_rate"]
            if emp.get("compensation_type"):
                emp_value["compensation_type"] = emp["compensation_type"]
            if emp.get("pay_period"):
                emp_value["pay_period"] = emp["pay_period"]
            if emp.get("change_reason"):
                emp_value["change_reason"] = emp["change_reason"]

            if not emp_value:
                continue

            effective = emp.get("start_date")

            facts.append(CaseFact(
                case_id=case_id,
                category=FactCategory.EMPLOYMENT,
                fact_type="employment_period",
                value=emp_value,
                source_file_id=file_id,
                extraction_method=ExtractionMethod.LLM,
                confidence=_LLM_EMPLOYMENT_CONFIDENCE,
                effective_date=effective,
            ))

        # Parties → FactCategory.PARTY
        for party in data.get("parties", []):
            name = party.get("name", "").strip()
            if not name:
                continue

            role = party.get("role", "plaintiff")
            # Map role to fact_type
            if role in ("plaintiff",):
                fact_type = "plaintiff"
            elif role in ("defendant",):
                fact_type = "defendant"
            else:
                fact_type = "party_identified"

            party_value: dict = {"name": name, "role": role}
            if party.get("party_type"):
                party_value["party_type"] = party["party_type"]

            facts.append(CaseFact(
                case_id=case_id,
                category=FactCategory.PARTY,
                fact_type=fact_type,
                value=party_value,
                source_file_id=file_id,
                extraction_method=ExtractionMethod.LLM,
                confidence=_LLM_PARTY_CONFIDENCE,
            ))

        # Key dates → FactCategory.DATE
        for dt in data.get("key_dates", []):
            date_val = dt.get("date", "").strip()
            label = dt.get("label", "").strip()
            if not date_val or not label:
                continue

            date_value: dict = {
                "label": label,
                "date": date_val,
            }
            if dt.get("date_type"):
                date_value["date_type"] = dt["date_type"]

            facts.append(CaseFact(
                case_id=case_id,
                category=FactCategory.DATE,
                fact_type="key_date",
                value=date_value,
                source_file_id=file_id,
                extraction_method=ExtractionMethod.LLM,
                confidence=_LLM_DATE_CONFIDENCE,
                effective_date=date_val,
            ))

        # Damages → FactCategory.FINANCIAL
        for dmg in data.get("damages", []):
            label = dmg.get("label", "").strip()
            if not label:
                continue

            fin_value: dict = {"label": label}
            if dmg.get("amount") is not None:
                fin_value["amount"] = dmg["amount"]
            if dmg.get("amount_type"):
                fin_value["amount_type"] = dmg["amount_type"]

            facts.append(CaseFact(
                case_id=case_id,
                category=FactCategory.FINANCIAL,
                fact_type="financial_event",
                value=fin_value,
                source_file_id=file_id,
                extraction_method=ExtractionMethod.LLM,
                confidence=_LLM_FINANCIAL_CONFIDENCE,
            ))

        return facts


# ── Result / Error types ───────────────────────────────────────────────


class Tier2Result:
    """Result of a Tier 2 LLM extraction."""

    __slots__ = (
        "facts", "factual_summary", "input_tokens", "output_tokens",
        "model", "duration_ms", "raw_output",
    )

    def __init__(
        self,
        facts: list[CaseFact],
        factual_summary: str | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        model: str = "",
        duration_ms: int = 0,
        raw_output: dict | None = None,
    ) -> None:
        self.facts = facts
        self.factual_summary = factual_summary
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.model = model
        self.duration_ms = duration_ms
        self.raw_output = raw_output or {}


class Tier2ExtractionError(Exception):
    """Raised when Tier 2 LLM extraction fails."""


# ── Helpers ────────────────────────────────────────────────────────────


def _is_valid_claim_type(value: str) -> bool:
    """Check if a string is a valid ClaimType enum value."""
    try:
        ClaimType(value)
        return True
    except ValueError:
        return False


def _clamp_confidence(value: float) -> float:
    """Clamp confidence to [0.0, 1.0]."""
    return max(0.0, min(1.0, value))


def _deobfuscate_extraction(
    data: dict,
    ctx: ObfuscationContext,
) -> None:
    """Deobfuscate placeholder values in the structured LLM output in-place.

    Walks the extraction dict and replaces placeholders (``PERSON_1``,
    ``COMPANY_1``, etc.) with their real values in all string fields that
    may contain entity references.
    """
    deobfuscate = ctx.deobfuscate

    # Parties — name is the critical field
    for party in data.get("parties", []):
        if party.get("name"):
            party["name"] = deobfuscate(party["name"])

    # Employment periods — employer, position, department
    for emp in data.get("employment_periods", []):
        for key in ("employer", "position", "department", "change_reason"):
            if emp.get(key):
                emp[key] = deobfuscate(emp[key])

    # Claims — reason, protected_class (usually legal terms, but may have names)
    for claim in data.get("claims", []):
        for key in ("reason", "protected_class"):
            if claim.get(key):
                claim[key] = deobfuscate(claim[key])

    # Key dates — label may reference people/companies
    for dt in data.get("key_dates", []):
        if dt.get("label"):
            dt["label"] = deobfuscate(dt["label"])

    # Damages — label
    for dmg in data.get("damages", []):
        if dmg.get("label"):
            dmg["label"] = deobfuscate(dmg["label"])

    # Factual summary
    if data.get("factual_summary"):
        data["factual_summary"] = deobfuscate(data["factual_summary"])
