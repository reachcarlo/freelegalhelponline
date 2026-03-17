"""Tests for V2.1c.3: Pydantic response schemas for CaseContext and CaseFact."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from employee_help.api.casefile_schemas import (
    CaseContextResponse,
    CaseFactListResponse,
    CaseFactResponse,
    ClaimViewResponse,
    CourtViewResponse,
    PartyViewResponse,
)


class TestCaseContextResponseSchema:
    """CaseContextResponse defaults, validation, and JSON round-trip."""

    def test_minimal_context_uses_defaults(self):
        """Only case_id and case_name are required; everything else defaults."""
        resp = CaseContextResponse(case_id="c1", case_name="Test Case")
        data = resp.model_dump()

        assert data["case_id"] == "c1"
        assert data["case_name"] == "Test Case"
        # All list fields default to empty
        assert data["parties"] == []
        assert data["attorneys"] == []
        assert data["employment_history"] == []
        assert data["claims"] == []
        assert data["key_dates"] == []
        assert data["financials"] == []
        assert data["plaintiff_names"] == []
        assert data["defendant_names"] == []
        assert data["all_person_names"] == []
        assert data["all_entity_names"] == []
        # Optional/scalar defaults
        assert data["court"] is None
        assert data["fact_count"] == 0
        assert data["confirmed_count"] == 0
        assert data["extraction_sources"] == {}

    def test_nested_sub_models_accept_dicts(self):
        """Pydantic coerces nested dicts into sub-model instances."""
        resp = CaseContextResponse(
            case_id="c2",
            case_name="Nested Test",
            parties=[{"name": "Alice", "role": "plaintiff", "party_type": "individual"}],
            court={"court": "Superior Court", "county": "LA"},
            claims=[{"claim_type": "wrongful_termination"}],
        )
        assert isinstance(resp.parties[0], PartyViewResponse)
        assert isinstance(resp.court, CourtViewResponse)
        assert isinstance(resp.claims[0], ClaimViewResponse)
        # ClaimViewResponse.status defaults to "active"
        assert resp.claims[0].status == "active"

    def test_json_round_trip(self):
        """model_dump → model_validate produces identical object."""
        original = CaseContextResponse(
            case_id="c3",
            case_name="Round Trip",
            parties=[
                {"name": "Bob", "role": "defendant", "party_type": "entity", "count": 2},
            ],
            court={"court": "District Court", "county": "SF", "judge": "Hon. Smith"},
            fact_count=10,
            confirmed_count=3,
            extraction_sources={"party": ["file-1", "file-2"]},
            plaintiff_names=["Alice"],
            defendant_names=["Bob"],
            all_person_names=["Alice"],
            all_entity_names=["Bob"],
        )
        data = original.model_dump()
        restored = CaseContextResponse.model_validate(data)
        assert restored == original


class TestCaseFactResponseSchema:
    """CaseFactResponse defaults, required fields, and JSON round-trip."""

    MINIMAL_FACT = {
        "id": "f1",
        "case_id": "c1",
        "category": "party",
        "fact_type": "plaintiff",
        "value": {"name": "Alice"},
        "extraction_method": "regex",
        "confidence": 0.8,
        "created_at": "2026-01-15T00:00:00",
    }

    def test_defaults_for_optional_fields(self):
        """Optional fields default correctly."""
        resp = CaseFactResponse(**self.MINIMAL_FACT)
        assert resp.source_file_id is None
        assert resp.confirmed is False
        assert resp.superseded_by is None
        assert resp.effective_date is None

    def test_missing_required_field_raises(self):
        """Omitting a required field raises ValidationError."""
        incomplete = {k: v for k, v in self.MINIMAL_FACT.items() if k != "confidence"}
        with pytest.raises(ValidationError) as exc_info:
            CaseFactResponse(**incomplete)
        assert "confidence" in str(exc_info.value)

    def test_list_response_json_round_trip(self):
        """CaseFactListResponse round-trips through JSON correctly."""
        original = CaseFactListResponse(
            facts=[
                CaseFactResponse(**self.MINIMAL_FACT),
                CaseFactResponse(
                    **{**self.MINIMAL_FACT, "id": "f2", "category": "court",
                       "fact_type": "court_info", "value": {"court": "Superior Court"},
                       "confirmed": True, "source_file_id": "file-1"},
                ),
            ],
            total=2,
        )
        data = original.model_dump()
        restored = CaseFactListResponse.model_validate(data)
        assert restored == original
        assert restored.total == 2
        assert restored.facts[1].confirmed is True
        assert restored.facts[1].source_file_id == "file-1"
