"""Tests for Tier 2 obfuscation integration (V2.2c.5).

Verifies that:
1. Text is obfuscated before being sent to the LLM
2. Structured output (party names, employer names, summaries) is deobfuscated
3. Without an obfuscation engine, raw text is sent (backward compat)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from employee_help.casefile.classifiers import DocumentType
from employee_help.casefile.extractors.tier2 import (
    Tier2Extractor,
    Tier2Result,
    _deobfuscate_extraction,
)
from employee_help.privacy.context import ObfuscationContext
from employee_help.privacy.engine import ObfuscationEngine
from employee_help.storage.models import ExtractionMethod, FactCategory


# ── Fixtures ──────────────────────────────────────────────────────


COMPLAINT_TEXT = (
    "COMPLAINT FOR DAMAGES\n\n"
    "SUPERIOR COURT OF CALIFORNIA, COUNTY OF LOS ANGELES\n\n"
    "John Smith, Plaintiff, v. Acme Corporation, Defendant.\n\n"
    "FIRST CAUSE OF ACTION — FEHA Discrimination\n"
    "Plaintiff John Smith alleges age-based discrimination "
    "by his employer Acme Corporation."
)


def _mock_llm_response(*, obfuscated: bool = False):
    """Build a mock LLM response with tool_input.

    When obfuscated=True, party names use placeholders to simulate
    what the LLM would return when given obfuscated input.
    """
    if obfuscated:
        plaintiff_name = "PERSON_1"
        defendant_name = "COMPANY_1"
        summary = "PERSON_1 alleges age-based discrimination by COMPANY_1."
        employer = "COMPANY_1"
        reason = "PERSON_1 was discriminated against by COMPANY_1."
    else:
        plaintiff_name = "John Smith"
        defendant_name = "Acme Corporation"
        summary = "John Smith alleges age-based discrimination by Acme Corporation."
        employer = "Acme Corporation"
        reason = "John Smith was discriminated against by Acme Corporation."

    return {
        "tool_input": {
            "claims": [
                {
                    "claim_type": "feha_discrimination",
                    "status": "active",
                    "protected_class": "age",
                    "reason": reason,
                    "confidence": 0.92,
                },
            ],
            "employment_periods": [
                {
                    "employer": employer,
                    "position": "Software Engineer",
                },
            ],
            "parties": [
                {"name": plaintiff_name, "role": "plaintiff", "party_type": "individual"},
                {"name": defendant_name, "role": "defendant", "party_type": "entity"},
            ],
            "key_dates": [],
            "damages": [],
            "factual_summary": summary,
        },
        "input_tokens": 1000,
        "output_tokens": 300,
        "model": "claude-sonnet-4-6",
        "duration_ms": 500,
    }


# ── Tests ──────────────────────────────────────────────────────────


class TestTier2Obfuscation:
    def test_text_obfuscated_before_llm_call(self):
        """When obfuscation engine is provided, text sent to LLM has
        entity placeholders instead of real names."""
        from employee_help.privacy.recognizers import RecognizedEntity

        mock_llm = MagicMock()
        mock_llm.generate_with_tools.return_value = _mock_llm_response(obfuscated=True)

        # Mock the recognizer to detect person/company names
        # (without spaCy, only regex entities are detected by default)
        mock_recognizer = MagicMock()
        mock_recognizer.scan.return_value = [
            RecognizedEntity(entity_type="PERSON", value="John Smith", start=0, end=10),
            RecognizedEntity(entity_type="COMPANY", value="Acme Corporation", start=0, end=16),
        ]

        engine = ObfuscationEngine(recognizer=mock_recognizer)
        extractor = Tier2Extractor(mock_llm, obfuscation_engine=engine)

        result = extractor.extract(
            COMPLAINT_TEXT, "case-1", "file-1",
            doc_type=DocumentType.COMPLAINT,
        )

        # Verify the LLM received obfuscated text
        call_kwargs = mock_llm.generate_with_tools.call_args
        user_message = call_kwargs.kwargs.get("user_message") or call_kwargs[1].get("user_message", "")
        if not user_message:
            # Try positional
            user_message = call_kwargs[0][1] if len(call_kwargs[0]) > 1 else ""

        # Real names should NOT appear in the text sent to LLM
        assert "John Smith" not in user_message
        assert "Acme Corporation" not in user_message

        # Placeholders should appear instead
        assert "PERSON_" in user_message or "COMPANY_" in user_message

        # But the returned facts should have REAL names (deobfuscated)
        party_facts = [f for f in result.facts if f.category == FactCategory.PARTY]
        party_names = [f.value["name"] for f in party_facts]
        assert "John Smith" in party_names
        assert "Acme Corporation" in party_names

        # Factual summary should also be deobfuscated
        assert "John Smith" in result.factual_summary
        assert "Acme Corporation" in result.factual_summary

    def test_deobfuscation_restores_all_fields(self):
        """_deobfuscate_extraction restores placeholders in all relevant
        fields: parties, employment, claims, dates, damages, summary."""
        ctx = ObfuscationContext()
        ctx.seed("PERSON", "Jane Doe")
        ctx.seed("COMPANY", "Widget Corp")

        data = {
            "claims": [
                {
                    "claim_type": "wrongful_termination_public_policy",
                    "status": "active",
                    "reason": "PERSON_1 was fired by COMPANY_1 for whistleblowing.",
                    "confidence": 0.9,
                },
            ],
            "employment_periods": [
                {
                    "employer": "COMPANY_1",
                    "position": "PERSON_1's position was Manager",
                    "department": "Engineering",
                },
            ],
            "parties": [
                {"name": "PERSON_1", "role": "plaintiff"},
                {"name": "COMPANY_1", "role": "defendant"},
            ],
            "key_dates": [
                {"label": "PERSON_1 was terminated", "date": "2025-06-15"},
            ],
            "damages": [
                {"label": "PERSON_1 lost wages from COMPANY_1", "amount": 50000},
            ],
            "factual_summary": "PERSON_1 alleges wrongful termination by COMPANY_1.",
        }

        _deobfuscate_extraction(data, ctx)

        # Parties
        assert data["parties"][0]["name"] == "Jane Doe"
        assert data["parties"][1]["name"] == "Widget Corp"

        # Employment
        assert data["employment_periods"][0]["employer"] == "Widget Corp"
        assert "Jane Doe" in data["employment_periods"][0]["position"]

        # Claims
        assert "Jane Doe" in data["claims"][0]["reason"]
        assert "Widget Corp" in data["claims"][0]["reason"]

        # Key dates
        assert "Jane Doe" in data["key_dates"][0]["label"]

        # Damages
        assert "Jane Doe" in data["damages"][0]["label"]
        assert "Widget Corp" in data["damages"][0]["label"]

        # Summary
        assert "Jane Doe" in data["factual_summary"]
        assert "Widget Corp" in data["factual_summary"]

    def test_no_engine_sends_raw_text(self):
        """Without an obfuscation engine, raw text is sent to the LLM
        (backward compatibility)."""
        mock_llm = MagicMock()
        mock_llm.generate_with_tools.return_value = _mock_llm_response(obfuscated=False)

        # No obfuscation engine — default behavior
        extractor = Tier2Extractor(mock_llm)

        result = extractor.extract(
            COMPLAINT_TEXT, "case-1", "file-1",
            doc_type=DocumentType.COMPLAINT,
        )

        # Verify the LLM received raw, unobfuscated text
        call_kwargs = mock_llm.generate_with_tools.call_args
        user_message = call_kwargs.kwargs.get("user_message") or call_kwargs[1].get("user_message", "")
        if not user_message:
            user_message = call_kwargs[0][1] if len(call_kwargs[0]) > 1 else ""

        assert "John Smith" in user_message
        assert "Acme Corporation" in user_message

        # Facts should have real names directly from the LLM response
        party_facts = [f for f in result.facts if f.category == FactCategory.PARTY]
        party_names = [f.value["name"] for f in party_facts]
        assert "John Smith" in party_names
        assert "Acme Corporation" in party_names
