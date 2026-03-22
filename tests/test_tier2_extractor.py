"""Tests for Tier2Extractor — LLM-based metadata extraction (V2.2c.1–V2.2c.2).

All tests mock the LLM client to avoid real API calls. Tests verify:
- Claims mapped to ClaimType enum values
- Employment relationship extraction
- Protected class extraction
- Party extraction
- Date extraction
- Financial/damages extraction
- Factual summary
- Error handling
- Jinja2 prompt template rendering (V2.2c.2)
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from employee_help.casefile.classifiers import DocumentType
from employee_help.casefile.extractors.tier2 import (
    EXTRACTION_TOOL,
    TIER2_DOC_TYPES,
    Tier2ExtractionError,
    Tier2Extractor,
    Tier2Result,
    _clamp_confidence,
    _is_valid_claim_type,
    build_system_prompt,
)
from employee_help.discovery.models import CLAIM_TYPE_LABELS, ClaimType
from employee_help.storage.models import (
    CaseFact,
    ExtractionMethod,
    FactCategory,
)

CASE_ID = "case-tier2-001"
FILE_ID = "file-complaint-001"


def _mock_llm(tool_input: dict) -> MagicMock:
    """Create a mock LLMClient that returns the given tool_input."""
    client = MagicMock()
    client.generate_with_tools.return_value = {
        "tool_name": "submit_extraction",
        "tool_input": tool_input,
        "input_tokens": 1500,
        "output_tokens": 400,
        "model": "claude-sonnet-4-6",
        "duration_ms": 2000,
    }
    return client


# ── Claim extraction tests ────────────────────────────────────────────


class TestClaimExtraction:
    def test_single_feha_discrimination_claim(self):
        llm = _mock_llm({
            "claims": [{
                "claim_type": "feha_discrimination",
                "status": "active",
                "protected_class": "race",
                "reason": "Plaintiff was terminated because of her race",
                "confidence": 0.92,
            }],
            "employment_periods": [],
            "parties": [],
            "key_dates": [],
            "damages": [],
        })
        extractor = Tier2Extractor(llm)
        result = extractor.extract("complaint text...", CASE_ID, FILE_ID)

        assert len(result.facts) == 1
        fact = result.facts[0]
        assert fact.category == FactCategory.CLAIM
        assert fact.fact_type == "claim"
        assert fact.value["claim_type"] == "feha_discrimination"
        assert fact.value["status"] == "active"
        assert fact.value["protected_class"] == "race"
        assert fact.value["reason"] == "Plaintiff was terminated because of her race"
        assert fact.extraction_method == ExtractionMethod.LLM
        assert fact.confidence == 0.92
        assert fact.source_file_id == FILE_ID
        assert fact.case_id == CASE_ID

    def test_multiple_claims(self):
        llm = _mock_llm({
            "claims": [
                {
                    "claim_type": "feha_discrimination",
                    "status": "active",
                    "protected_class": "age",
                    "confidence": 0.9,
                },
                {
                    "claim_type": "feha_retaliation",
                    "status": "active",
                    "confidence": 0.85,
                },
                {
                    "claim_type": "wrongful_termination_public_policy",
                    "status": "active",
                    "confidence": 0.88,
                },
            ],
            "employment_periods": [],
            "parties": [],
            "key_dates": [],
            "damages": [],
        })
        extractor = Tier2Extractor(llm)
        result = extractor.extract("complaint text...", CASE_ID, FILE_ID)

        assert len(result.facts) == 3
        types = [f.value["claim_type"] for f in result.facts]
        assert "feha_discrimination" in types
        assert "feha_retaliation" in types
        assert "wrongful_termination_public_policy" in types

    def test_invalid_claim_type_skipped(self):
        llm = _mock_llm({
            "claims": [
                {
                    "claim_type": "feha_discrimination",
                    "status": "active",
                    "confidence": 0.9,
                },
                {
                    "claim_type": "made_up_claim_type",
                    "status": "active",
                    "confidence": 0.8,
                },
            ],
            "employment_periods": [],
            "parties": [],
            "key_dates": [],
            "damages": [],
        })
        extractor = Tier2Extractor(llm)
        result = extractor.extract("complaint text...", CASE_ID, FILE_ID)

        # Only the valid claim should be included
        assert len(result.facts) == 1
        assert result.facts[0].value["claim_type"] == "feha_discrimination"

    def test_claim_without_protected_class(self):
        llm = _mock_llm({
            "claims": [{
                "claim_type": "wage_theft",
                "status": "active",
                "confidence": 0.95,
            }],
            "employment_periods": [],
            "parties": [],
            "key_dates": [],
            "damages": [],
        })
        extractor = Tier2Extractor(llm)
        result = extractor.extract("complaint text...", CASE_ID, FILE_ID)

        assert len(result.facts) == 1
        assert "protected_class" not in result.facts[0].value


# ── Employment extraction tests ───────────────────────────────────────


class TestEmploymentExtraction:
    def test_full_employment_period(self):
        llm = _mock_llm({
            "claims": [],
            "employment_periods": [{
                "employer": "Acme Corp",
                "position": "Senior Engineer",
                "department": "Engineering",
                "start_date": "2020-01-15",
                "end_date": "2025-06-30",
                "compensation_rate": 150000,
                "compensation_type": "salary",
                "pay_period": "annual",
                "change_reason": "terminated",
            }],
            "parties": [],
            "key_dates": [],
            "damages": [],
        })
        extractor = Tier2Extractor(llm)
        result = extractor.extract("complaint text...", CASE_ID, FILE_ID)

        assert len(result.facts) == 1
        fact = result.facts[0]
        assert fact.category == FactCategory.EMPLOYMENT
        assert fact.fact_type == "employment_period"
        assert fact.value["employer"] == "Acme Corp"
        assert fact.value["position"] == "Senior Engineer"
        assert fact.value["department"] == "Engineering"
        assert fact.value["start_date"] == "2020-01-15"
        assert fact.value["end_date"] == "2025-06-30"
        assert fact.value["compensation_rate"] == 150000
        assert fact.value["change_reason"] == "terminated"
        assert fact.extraction_method == ExtractionMethod.LLM
        assert fact.effective_date == "2020-01-15"

    def test_multiple_employment_periods(self):
        llm = _mock_llm({
            "claims": [],
            "employment_periods": [
                {
                    "employer": "Acme Corp",
                    "position": "Junior Engineer",
                    "start_date": "2018-03-01",
                    "end_date": "2020-01-14",
                },
                {
                    "employer": "Acme Corp",
                    "position": "Senior Engineer",
                    "start_date": "2020-01-15",
                    "end_date": "2025-06-30",
                    "change_reason": "terminated",
                },
            ],
            "parties": [],
            "key_dates": [],
            "damages": [],
        })
        extractor = Tier2Extractor(llm)
        result = extractor.extract("complaint text...", CASE_ID, FILE_ID)

        assert len(result.facts) == 2
        positions = [f.value.get("position") for f in result.facts]
        assert "Junior Engineer" in positions
        assert "Senior Engineer" in positions

    def test_empty_employment_skipped(self):
        """Employment entry with no fields should be skipped."""
        llm = _mock_llm({
            "claims": [],
            "employment_periods": [{}],
            "parties": [],
            "key_dates": [],
            "damages": [],
        })
        extractor = Tier2Extractor(llm)
        result = extractor.extract("complaint text...", CASE_ID, FILE_ID)

        assert len(result.facts) == 0


# ── Protected class / party extraction tests ──────────────────────────


class TestPartyExtraction:
    def test_plaintiff_and_defendant(self):
        llm = _mock_llm({
            "claims": [],
            "employment_periods": [],
            "parties": [
                {"name": "Maria Martinez", "role": "plaintiff", "party_type": "individual"},
                {"name": "Acme Corp", "role": "defendant", "party_type": "entity"},
            ],
            "key_dates": [],
            "damages": [],
        })
        extractor = Tier2Extractor(llm)
        result = extractor.extract("complaint text...", CASE_ID, FILE_ID)

        assert len(result.facts) == 2
        plaintiff = [f for f in result.facts if f.fact_type == "plaintiff"][0]
        defendant = [f for f in result.facts if f.fact_type == "defendant"][0]

        assert plaintiff.value["name"] == "Maria Martinez"
        assert plaintiff.value["party_type"] == "individual"
        assert plaintiff.category == FactCategory.PARTY

        assert defendant.value["name"] == "Acme Corp"
        assert defendant.value["party_type"] == "entity"

    def test_non_party_roles(self):
        llm = _mock_llm({
            "claims": [],
            "employment_periods": [],
            "parties": [
                {"name": "John Smith", "role": "supervisor"},
                {"name": "Jane Doe", "role": "witness"},
            ],
            "key_dates": [],
            "damages": [],
        })
        extractor = Tier2Extractor(llm)
        result = extractor.extract("complaint text...", CASE_ID, FILE_ID)

        assert len(result.facts) == 2
        # Non-plaintiff/defendant roles get fact_type "party_identified"
        for fact in result.facts:
            assert fact.fact_type == "party_identified"

    def test_empty_name_skipped(self):
        llm = _mock_llm({
            "claims": [],
            "employment_periods": [],
            "parties": [
                {"name": "", "role": "plaintiff"},
                {"name": "  ", "role": "defendant"},
            ],
            "key_dates": [],
            "damages": [],
        })
        extractor = Tier2Extractor(llm)
        result = extractor.extract("complaint text...", CASE_ID, FILE_ID)

        assert len(result.facts) == 0


# ── Date extraction tests ─────────────────────────────────────────────


class TestDateExtraction:
    def test_key_dates_extracted(self):
        llm = _mock_llm({
            "claims": [],
            "employment_periods": [],
            "parties": [],
            "key_dates": [
                {"label": "Termination Date", "date": "2025-06-30", "date_type": "termination_date"},
                {"label": "DFEH Complaint Filed", "date": "2025-09-15", "date_type": "dfeh_filed"},
            ],
            "damages": [],
        })
        extractor = Tier2Extractor(llm)
        result = extractor.extract("complaint text...", CASE_ID, FILE_ID)

        assert len(result.facts) == 2
        term = [f for f in result.facts if f.value["label"] == "Termination Date"][0]
        assert term.category == FactCategory.DATE
        assert term.fact_type == "key_date"
        assert term.value["date"] == "2025-06-30"
        assert term.value["date_type"] == "termination_date"
        assert term.effective_date == "2025-06-30"
        assert term.extraction_method == ExtractionMethod.LLM

    def test_empty_date_or_label_skipped(self):
        llm = _mock_llm({
            "claims": [],
            "employment_periods": [],
            "parties": [],
            "key_dates": [
                {"label": "", "date": "2025-01-01"},
                {"label": "Some event", "date": ""},
            ],
            "damages": [],
        })
        extractor = Tier2Extractor(llm)
        result = extractor.extract("complaint text...", CASE_ID, FILE_ID)

        assert len(result.facts) == 0


# ── Financial/damages extraction tests ────────────────────────────────


class TestFinancialExtraction:
    def test_damages_extracted(self):
        llm = _mock_llm({
            "claims": [],
            "employment_periods": [],
            "parties": [],
            "key_dates": [],
            "damages": [
                {"label": "Lost Wages", "amount": 250000, "amount_type": "damages"},
                {"label": "Emotional Distress", "amount": 100000, "amount_type": "damages"},
            ],
        })
        extractor = Tier2Extractor(llm)
        result = extractor.extract("complaint text...", CASE_ID, FILE_ID)

        assert len(result.facts) == 2
        wages = [f for f in result.facts if f.value["label"] == "Lost Wages"][0]
        assert wages.category == FactCategory.FINANCIAL
        assert wages.fact_type == "financial_event"
        assert wages.value["amount"] == 250000
        assert wages.value["amount_type"] == "damages"
        assert wages.extraction_method == ExtractionMethod.LLM

    def test_damages_without_amount(self):
        """Damages that say 'according to proof' often lack a specific amount."""
        llm = _mock_llm({
            "claims": [],
            "employment_periods": [],
            "parties": [],
            "key_dates": [],
            "damages": [
                {"label": "Punitive Damages"},
            ],
        })
        extractor = Tier2Extractor(llm)
        result = extractor.extract("complaint text...", CASE_ID, FILE_ID)

        assert len(result.facts) == 1
        assert "amount" not in result.facts[0].value

    def test_empty_label_skipped(self):
        llm = _mock_llm({
            "claims": [],
            "employment_periods": [],
            "parties": [],
            "key_dates": [],
            "damages": [{"label": "", "amount": 100}],
        })
        extractor = Tier2Extractor(llm)
        result = extractor.extract("complaint text...", CASE_ID, FILE_ID)

        assert len(result.facts) == 0


# ── Full extraction integration tests ─────────────────────────────────


class TestFullExtraction:
    def test_comprehensive_complaint_extraction(self):
        """Simulate a realistic complaint producing all fact categories."""
        llm = _mock_llm({
            "claims": [
                {
                    "claim_type": "feha_discrimination",
                    "status": "active",
                    "protected_class": "national_origin",
                    "reason": "Plaintiff was harassed due to national origin",
                    "confidence": 0.92,
                },
                {
                    "claim_type": "wrongful_termination_public_policy",
                    "status": "active",
                    "confidence": 0.88,
                },
            ],
            "employment_periods": [{
                "employer": "TechCo Inc",
                "position": "Software Developer",
                "start_date": "2021-03-15",
                "end_date": "2025-08-01",
                "compensation_rate": 130000,
                "compensation_type": "salary",
                "pay_period": "annual",
                "change_reason": "terminated",
            }],
            "parties": [
                {"name": "Juan Garcia", "role": "plaintiff", "party_type": "individual"},
                {"name": "TechCo Inc", "role": "defendant", "party_type": "entity"},
                {"name": "Bob Manager", "role": "supervisor"},
            ],
            "key_dates": [
                {"label": "Hire Date", "date": "2021-03-15", "date_type": "hire_date"},
                {"label": "Termination", "date": "2025-08-01", "date_type": "termination_date"},
            ],
            "damages": [
                {"label": "Lost Wages", "amount": 200000, "amount_type": "damages"},
            ],
            "factual_summary": (
                "Plaintiff was employed by TechCo as a Software Developer from "
                "March 2021 until wrongful termination in August 2025."
            ),
        })
        extractor = Tier2Extractor(llm)
        result = extractor.extract("full complaint text...", CASE_ID, FILE_ID)

        # 2 claims + 1 employment + 3 parties + 2 dates + 1 damage = 9 facts
        assert len(result.facts) == 9

        # Check categories
        cats = [f.category for f in result.facts]
        assert cats.count(FactCategory.CLAIM) == 2
        assert cats.count(FactCategory.EMPLOYMENT) == 1
        assert cats.count(FactCategory.PARTY) == 3
        assert cats.count(FactCategory.DATE) == 2
        assert cats.count(FactCategory.FINANCIAL) == 1

        # All facts should be LLM-extracted
        assert all(f.extraction_method == ExtractionMethod.LLM for f in result.facts)
        assert all(f.source_file_id == FILE_ID for f in result.facts)
        assert all(f.case_id == CASE_ID for f in result.facts)

        # Factual summary
        assert result.factual_summary is not None
        assert "TechCo" in result.factual_summary

        # Token usage
        assert result.input_tokens == 1500
        assert result.output_tokens == 400


# ── Edge cases and error handling ──────────────────────────────────────


class TestEdgeCases:
    def test_empty_text_returns_empty(self):
        llm = MagicMock()
        extractor = Tier2Extractor(llm)
        result = extractor.extract("", CASE_ID, FILE_ID)

        assert len(result.facts) == 0
        assert result.input_tokens == 0
        llm.generate_with_tools.assert_not_called()

    def test_whitespace_only_text_returns_empty(self):
        llm = MagicMock()
        extractor = Tier2Extractor(llm)
        result = extractor.extract("   \n\t  ", CASE_ID, FILE_ID)

        assert len(result.facts) == 0
        llm.generate_with_tools.assert_not_called()

    def test_llm_error_raises_tier2_error(self):
        llm = MagicMock()
        llm.generate_with_tools.side_effect = RuntimeError("API down")
        extractor = Tier2Extractor(llm)

        with pytest.raises(Tier2ExtractionError, match="LLM extraction failed"):
            extractor.extract("complaint text...", CASE_ID, FILE_ID)

    def test_empty_tool_input_returns_empty(self):
        llm = MagicMock()
        llm.generate_with_tools.return_value = {
            "tool_name": "submit_extraction",
            "tool_input": {},
            "input_tokens": 100,
            "output_tokens": 10,
        }
        extractor = Tier2Extractor(llm)
        result = extractor.extract("complaint text...", CASE_ID, FILE_ID)

        assert len(result.facts) == 0

    def test_confidence_clamped(self):
        llm = _mock_llm({
            "claims": [
                {"claim_type": "wage_theft", "status": "active", "confidence": 1.5},
                {"claim_type": "overtime", "status": "active", "confidence": -0.3},
            ],
            "employment_periods": [],
            "parties": [],
            "key_dates": [],
            "damages": [],
        })
        extractor = Tier2Extractor(llm)
        result = extractor.extract("complaint text...", CASE_ID, FILE_ID)

        assert result.facts[0].confidence == 1.0
        assert result.facts[1].confidence == 0.0

    def test_doc_type_passed_to_system_prompt(self):
        llm = _mock_llm({
            "claims": [],
            "employment_periods": [],
            "parties": [],
            "key_dates": [],
            "damages": [],
        })
        extractor = Tier2Extractor(llm)
        extractor.extract("text", CASE_ID, FILE_ID, doc_type=DocumentType.DEMAND_LETTER)

        call_args = llm.generate_with_tools.call_args
        system_prompt = call_args.kwargs.get("system_prompt") or call_args[0][0]
        assert "demand letter" in system_prompt

    def test_custom_model_passed(self):
        llm = _mock_llm({
            "claims": [],
            "employment_periods": [],
            "parties": [],
            "key_dates": [],
            "damages": [],
        })
        extractor = Tier2Extractor(llm, model="claude-haiku-4-5-20251001")
        extractor.extract("text", CASE_ID, FILE_ID)

        call_args = llm.generate_with_tools.call_args
        assert call_args.kwargs.get("model") == "claude-haiku-4-5-20251001"


# ── can_extract tests ─────────────────────────────────────────────────


class TestCanExtract:
    def test_complaint_supported(self):
        extractor = Tier2Extractor(MagicMock())
        assert extractor.can_extract(DocumentType.COMPLAINT) is True

    def test_answer_supported(self):
        extractor = Tier2Extractor(MagicMock())
        assert extractor.can_extract(DocumentType.ANSWER) is True

    def test_demand_letter_supported(self):
        extractor = Tier2Extractor(MagicMock())
        assert extractor.can_extract(DocumentType.DEMAND_LETTER) is True

    def test_generic_not_supported(self):
        extractor = Tier2Extractor(MagicMock())
        assert extractor.can_extract(DocumentType.GENERIC) is False

    def test_email_not_supported(self):
        extractor = Tier2Extractor(MagicMock())
        assert extractor.can_extract(DocumentType.EMAIL) is False


# ── Helper function tests ─────────────────────────────────────────────


class TestHelpers:
    def test_valid_claim_types(self):
        for ct in ClaimType:
            assert _is_valid_claim_type(ct.value) is True

    def test_invalid_claim_type(self):
        assert _is_valid_claim_type("not_a_real_claim") is False
        assert _is_valid_claim_type("") is False

    def test_clamp_confidence(self):
        assert _clamp_confidence(0.5) == 0.5
        assert _clamp_confidence(0.0) == 0.0
        assert _clamp_confidence(1.0) == 1.0
        assert _clamp_confidence(1.5) == 1.0
        assert _clamp_confidence(-0.5) == 0.0


# ── Tool schema tests ─────────────────────────────────────────────────


class TestToolSchema:
    def test_tool_has_all_claim_types(self):
        """Ensure the tool schema enum matches ClaimType."""
        schema_claims = EXTRACTION_TOOL["input_schema"]["properties"]["claims"]["items"]["properties"]["claim_type"]["enum"]
        for ct in ClaimType:
            assert ct.value in schema_claims

    def test_tool_name(self):
        assert EXTRACTION_TOOL["name"] == "submit_extraction"

    def test_required_fields(self):
        required = EXTRACTION_TOOL["input_schema"]["required"]
        assert "claims" in required
        assert "employment_periods" in required
        assert "parties" in required
        assert "key_dates" in required
        assert "damages" in required


# ── Prompt template tests (V2.2c.2) ──────────────────────────────────


class TestPromptTemplate:
    def test_template_renders_with_all_claim_types(self):
        """Template includes every ClaimType enum value and label."""
        prompt = build_system_prompt(DocumentType.COMPLAINT)

        for ct in ClaimType:
            assert ct.value in prompt, f"Missing claim type value: {ct.value}"
            label = CLAIM_TYPE_LABELS[ct]
            assert label in prompt, f"Missing claim type label: {label}"

    def test_template_renders_doc_type_specific_content(self):
        """Template content varies by document type."""
        complaint_prompt = build_system_prompt(DocumentType.COMPLAINT)
        demand_prompt = build_system_prompt(DocumentType.DEMAND_LETTER)
        answer_prompt = build_system_prompt(DocumentType.ANSWER)

        # Each should mention its doc type
        assert "complaint" in complaint_prompt
        assert "demand letter" in demand_prompt
        assert "answer" in answer_prompt

        # Complaint-specific guidance
        assert "plaintiff's employment with the defendant" in complaint_prompt
        assert "plaintiff's employment with the defendant" not in demand_prompt

        # Demand-letter-specific guidance
        assert "damages calculations" in demand_prompt
        assert "damages calculations" not in complaint_prompt

        # Answer-specific guidance
        assert "admits or denies" in answer_prompt
        assert "admits or denies" not in complaint_prompt
