"""P2.7 integration tests: ObjectionAnalyzer with obfuscation enabled.

Verifies that:
- Request texts are obfuscated before the LLM sees them.
- LLM explanation output is deobfuscated before the user sees it.
- no_objections_rationale is deobfuscated.
- Engine=None (disabled) preserves existing behavior exactly.
- Legal citations in request texts are not obfuscated.
- SSN in request text is hard-redacted (irreversible).
- Batch chunking works correctly with obfuscation.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from employee_help.discovery.objections.analyzer import ObjectionAnalyzer
from employee_help.discovery.objections.knowledge_base import ObjectionKnowledgeBase
from employee_help.discovery.objections.models import (
    ObjectionRequest,
    ResponseDiscoveryType,
    Verbosity,
    PartyRole,
)
from employee_help.privacy.engine import ObfuscationEngine
from employee_help.privacy.recognizers import EntityRecognizer


# ── Helpers ──────────────────────────────────────────────────────


def _no_ner_engine() -> ObfuscationEngine:
    """Engine with regex-only recognition (no spaCy)."""
    rec = EntityRecognizer()
    rec._nlp = None
    rec._ner_loaded = True
    return ObfuscationEngine(recognizer=rec)


def _mock_llm_response(
    analyses: list[dict[str, Any]],
    model: str = "claude-haiku-4-5-20251001",
) -> dict[str, Any]:
    """Build a fake generate_with_tools return value."""
    return {
        "tool_input": {"request_analyses": analyses},
        "input_tokens": 100,
        "output_tokens": 50,
        "model": model,
    }


def _make_analyzer(
    llm_response: dict[str, Any] | None = None,
    obfuscation_engine: ObfuscationEngine | None = None,
) -> tuple[ObjectionAnalyzer, MagicMock]:
    """Build an ObjectionAnalyzer with a mock LLM."""
    mock_llm = MagicMock()
    if llm_response is not None:
        mock_llm.generate_with_tools.return_value = llm_response

    kb = ObjectionKnowledgeBase()
    analyzer = ObjectionAnalyzer(
        mock_llm, kb, obfuscation_engine=obfuscation_engine
    )
    return analyzer, mock_llm


# ── Tests: Obfuscation on ────────────────────────────────────────


class TestRequestTextObfuscation:
    """Request texts containing PII are obfuscated before reaching the LLM."""

    def test_email_obfuscated_in_request_text(self):
        """Email in request text is replaced with placeholder before LLM call."""
        engine = _no_ner_engine()
        response = _mock_llm_response([{
            "request_number": 1,
            "applicable_objections": [],
        }])
        analyzer, mock_llm = _make_analyzer(response, obfuscation_engine=engine)

        req = ObjectionRequest(
            request_number=1,
            request_text="Produce all emails sent to john@acme.com regarding the incident.",
            discovery_type=ResponseDiscoveryType.INTERROGATORIES,
        )
        analyzer.analyze_single(req)

        call_args = mock_llm.generate_with_tools.call_args
        user_message = call_args.kwargs.get("user_message") or call_args[1].get("user_message")
        if user_message is None:
            # Positional args
            user_message = call_args[0][1] if len(call_args[0]) > 1 else call_args.kwargs["user_message"]

        assert "john@acme.com" not in user_message
        assert "EMAIL_1" in user_message

    def test_phone_obfuscated_in_request_text(self):
        """Phone number in request text is replaced with placeholder."""
        engine = _no_ner_engine()
        response = _mock_llm_response([{
            "request_number": 1,
            "applicable_objections": [],
        }])
        analyzer, mock_llm = _make_analyzer(response, obfuscation_engine=engine)

        req = ObjectionRequest(
            request_number=1,
            request_text="Calls made to (555) 123-4567 on the date in question.",
            discovery_type=ResponseDiscoveryType.INTERROGATORIES,
        )
        analyzer.analyze_single(req)

        call_args = mock_llm.generate_with_tools.call_args
        user_message = call_args.kwargs.get("user_message") or call_args[0][1]
        assert "(555) 123-4567" not in user_message
        assert "PHONE_1" in user_message

    def test_ssn_hard_redacted(self):
        """SSN in request text is irreversibly redacted."""
        engine = _no_ner_engine()
        response = _mock_llm_response([{
            "request_number": 1,
            "applicable_objections": [{
                "ground_id": "privacy",
                "explanation": "Contains [REDACTED] which is sensitive.",
                "strength": "high",
            }],
        }])
        analyzer, mock_llm = _make_analyzer(response, obfuscation_engine=engine)

        req = ObjectionRequest(
            request_number=1,
            request_text="Employee SSN 123-45-6789 should be produced.",
            discovery_type=ResponseDiscoveryType.INTERROGATORIES,
        )
        result = analyzer.analyze_single(req)

        # SSN should be redacted in what the LLM sees
        call_args = mock_llm.generate_with_tools.call_args
        user_message = call_args.kwargs.get("user_message") or call_args[0][1]
        assert "123-45-6789" not in user_message
        assert "[REDACTED]" in user_message

        # [REDACTED] stays as-is in the explanation (irreversible)
        assert result.objections[0].explanation == "Contains [REDACTED] which is sensitive."


class TestExplanationDeobfuscation:
    """LLM explanation output is deobfuscated before the user sees it."""

    def test_explanation_deobfuscated(self):
        """Placeholders in explanation are replaced with real values."""
        engine = _no_ner_engine()
        # LLM sees EMAIL_1 and uses it in explanation
        response = _mock_llm_response([{
            "request_number": 1,
            "applicable_objections": [{
                "ground_id": "privacy",
                "explanation": "The email EMAIL_1 is private and should not be disclosed.",
                "strength": "high",
            }],
        }])
        analyzer, _ = _make_analyzer(response, obfuscation_engine=engine)

        req = ObjectionRequest(
            request_number=1,
            request_text="Produce all emails sent to jane@example.com.",
            discovery_type=ResponseDiscoveryType.INTERROGATORIES,
        )
        result = analyzer.analyze_single(req)

        explanation = result.objections[0].explanation
        assert "jane@example.com" in explanation
        assert "EMAIL_1" not in explanation

    def test_no_objections_rationale_deobfuscated(self):
        """Placeholders in no_objections_rationale are replaced with real values."""
        engine = _no_ner_engine()
        response = _mock_llm_response([{
            "request_number": 1,
            "applicable_objections": [],
            "no_objections_rationale": "The request for documents about EMAIL_1 is straightforward.",
        }])
        analyzer, _ = _make_analyzer(response, obfuscation_engine=engine)

        req = ObjectionRequest(
            request_number=1,
            request_text="Produce documents mentioning alice@corp.com.",
            discovery_type=ResponseDiscoveryType.INTERROGATORIES,
        )
        result = analyzer.analyze_single(req)

        assert "alice@corp.com" in result.no_objections_rationale
        assert "EMAIL_1" not in result.no_objections_rationale


class TestLegalCitationPreservation:
    """Legal citations in request text are not obfuscated."""

    def test_statute_citation_preserved(self):
        """Cal. Lab. Code citations pass through unmodified."""
        engine = _no_ner_engine()
        response = _mock_llm_response([{
            "request_number": 1,
            "applicable_objections": [],
        }])
        analyzer, mock_llm = _make_analyzer(response, obfuscation_engine=engine)

        req = ObjectionRequest(
            request_number=1,
            request_text="Under Cal. Lab. Code § 1102.5, produce all whistleblower complaints.",
            discovery_type=ResponseDiscoveryType.RFPS,
        )
        analyzer.analyze_single(req)

        call_args = mock_llm.generate_with_tools.call_args
        user_message = call_args.kwargs.get("user_message") or call_args[0][1]
        assert "Cal. Lab. Code § 1102.5" in user_message

    def test_mixed_pii_and_citation(self):
        """PII is obfuscated but legal citation is preserved in same text."""
        engine = _no_ner_engine()
        response = _mock_llm_response([{
            "request_number": 1,
            "applicable_objections": [],
        }])
        analyzer, mock_llm = _make_analyzer(response, obfuscation_engine=engine)

        req = ObjectionRequest(
            request_number=1,
            request_text=(
                "Per Cal. Gov. Code § 12940, produce emails to john@acme.com "
                "regarding harassment."
            ),
            discovery_type=ResponseDiscoveryType.RFPS,
        )
        analyzer.analyze_single(req)

        call_args = mock_llm.generate_with_tools.call_args
        user_message = call_args.kwargs.get("user_message") or call_args[0][1]
        assert "Cal. Gov. Code § 12940" in user_message
        assert "john@acme.com" not in user_message
        assert "EMAIL_1" in user_message


class TestNoEngine:
    """Engine=None (disabled) preserves existing behavior exactly."""

    def test_no_engine_request_text_unchanged(self):
        """Without engine, request text passes through as-is."""
        response = _mock_llm_response([{
            "request_number": 1,
            "applicable_objections": [],
        }])
        analyzer, mock_llm = _make_analyzer(response, obfuscation_engine=None)

        req = ObjectionRequest(
            request_number=1,
            request_text="Produce emails to john@acme.com about the incident.",
            discovery_type=ResponseDiscoveryType.INTERROGATORIES,
        )
        analyzer.analyze_single(req)

        call_args = mock_llm.generate_with_tools.call_args
        user_message = call_args.kwargs.get("user_message") or call_args[0][1]
        assert "john@acme.com" in user_message

    def test_no_engine_explanation_unchanged(self):
        """Without engine, explanation text passes through as-is."""
        response = _mock_llm_response([{
            "request_number": 1,
            "applicable_objections": [{
                "ground_id": "privacy",
                "explanation": "Contains EMAIL_1 placeholder text.",
                "strength": "medium",
            }],
        }])
        analyzer, _ = _make_analyzer(response, obfuscation_engine=None)

        req = ObjectionRequest(
            request_number=1,
            request_text="Test request",
            discovery_type=ResponseDiscoveryType.INTERROGATORIES,
        )
        result = analyzer.analyze_single(req)
        # Without engine, the literal "EMAIL_1" stays as-is
        assert "EMAIL_1" in result.objections[0].explanation


class TestBatchWithObfuscation:
    """Batch processing works correctly with obfuscation."""

    def test_multiple_requests_same_context(self):
        """Multiple requests in same chunk share one obfuscation context."""
        engine = _no_ner_engine()
        response = _mock_llm_response([
            {
                "request_number": 1,
                "applicable_objections": [{
                    "ground_id": "privacy",
                    "explanation": "EMAIL_1 appears here.",
                    "strength": "medium",
                }],
            },
            {
                "request_number": 2,
                "applicable_objections": [{
                    "ground_id": "privacy",
                    "explanation": "Same EMAIL_1 also appears in this request.",
                    "strength": "medium",
                }],
            },
        ])
        analyzer, mock_llm = _make_analyzer(response, obfuscation_engine=engine)

        requests = [
            ObjectionRequest(
                1, "Produce emails to john@acme.com.",
                ResponseDiscoveryType.RFPS,
            ),
            ObjectionRequest(
                2, "Also produce documents referencing john@acme.com.",
                ResponseDiscoveryType.RFPS,
            ),
        ]
        batch = analyzer.analyze_batch(requests)

        # Both explanations should have the real email restored
        assert "john@acme.com" in batch.results[0].objections[0].explanation
        assert "john@acme.com" in batch.results[1].objections[0].explanation

        # LLM should have seen obfuscated text
        call_args = mock_llm.generate_with_tools.call_args
        user_message = call_args.kwargs.get("user_message") or call_args[0][1]
        assert "john@acme.com" not in user_message

    def test_multiple_entities_across_requests(self):
        """Different PII across requests gets distinct placeholders."""
        engine = _no_ner_engine()
        response = _mock_llm_response([
            {
                "request_number": 1,
                "applicable_objections": [],
            },
            {
                "request_number": 2,
                "applicable_objections": [],
            },
        ])
        analyzer, mock_llm = _make_analyzer(response, obfuscation_engine=engine)

        requests = [
            ObjectionRequest(
                1, "Emails to alice@example.com.",
                ResponseDiscoveryType.INTERROGATORIES,
            ),
            ObjectionRequest(
                2, "Phone records for (555) 987-6543.",
                ResponseDiscoveryType.INTERROGATORIES,
            ),
        ]
        analyzer.analyze_batch(requests)

        call_args = mock_llm.generate_with_tools.call_args
        user_message = call_args.kwargs.get("user_message") or call_args[0][1]
        assert "alice@example.com" not in user_message
        assert "(555) 987-6543" not in user_message
        assert "EMAIL_1" in user_message
        assert "PHONE_1" in user_message


class TestEdgeCases:
    """Edge cases for obfuscation in ObjectionAnalyzer."""

    def test_empty_request_text(self):
        """Empty request text doesn't crash obfuscation."""
        engine = _no_ner_engine()
        response = _mock_llm_response([{
            "request_number": 1,
            "applicable_objections": [],
        }])
        analyzer, _ = _make_analyzer(response, obfuscation_engine=engine)

        req = ObjectionRequest(
            request_number=1,
            request_text="",
            discovery_type=ResponseDiscoveryType.INTERROGATORIES,
        )
        result = analyzer.analyze_single(req)
        assert result.objections == []

    def test_no_pii_passthrough(self):
        """Request text with no PII passes through unchanged."""
        engine = _no_ner_engine()
        response = _mock_llm_response([{
            "request_number": 1,
            "applicable_objections": [],
        }])
        analyzer, mock_llm = _make_analyzer(response, obfuscation_engine=engine)

        text = "State all facts supporting your claim of wrongful termination."
        req = ObjectionRequest(
            request_number=1,
            request_text=text,
            discovery_type=ResponseDiscoveryType.INTERROGATORIES,
        )
        analyzer.analyze_single(req)

        call_args = mock_llm.generate_with_tools.call_args
        user_message = call_args.kwargs.get("user_message") or call_args[0][1]
        assert text in user_message

    def test_empty_batch(self):
        """Empty batch returns empty result."""
        engine = _no_ner_engine()
        analyzer, _ = _make_analyzer(obfuscation_engine=engine)
        batch = analyzer.analyze_batch([])
        assert batch.results == []
