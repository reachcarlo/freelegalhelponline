"""Tests for LITIGAGENTv2 CaseFact dataclass and related enums (V2.1a.1)."""

from datetime import datetime

import pytest

from employee_help.storage.models import (
    CaseFact,
    ExtractionMethod,
    FactCategory,
)


class TestFactCategory:
    def test_all_categories(self):
        expected = {"party", "employment", "claim", "date", "financial", "court", "attorney"}
        assert {c.value for c in FactCategory} == expected

    def test_string_serialization(self):
        """FactCategory is a str enum — usable directly as a string."""
        assert FactCategory.PARTY == "party"
        assert str(FactCategory.COURT) == "FactCategory.COURT"
        assert FactCategory.CLAIM.value == "claim"


class TestExtractionMethod:
    def test_all_methods(self):
        expected = {"regex", "llm", "manual"}
        assert {m.value for m in ExtractionMethod} == expected

    def test_string_serialization(self):
        assert ExtractionMethod.REGEX == "regex"
        assert ExtractionMethod.MANUAL == "manual"


class TestCaseFact:
    def _make_fact(self, **overrides) -> CaseFact:
        defaults = {
            "case_id": "case-1",
            "category": FactCategory.PARTY,
            "fact_type": "plaintiff",
            "value": {"name": "Maria Martinez", "role": "plaintiff", "party_type": "individual"},
            "extraction_method": ExtractionMethod.REGEX,
            "confidence": 0.85,
        }
        defaults.update(overrides)
        return CaseFact(**defaults)

    def test_defaults_and_auto_uuid(self):
        fact = self._make_fact()
        assert fact.case_id == "case-1"
        assert fact.category == FactCategory.PARTY
        assert fact.fact_type == "plaintiff"
        assert fact.value["name"] == "Maria Martinez"
        assert fact.extraction_method == ExtractionMethod.REGEX
        assert fact.confidence == 0.85
        # Auto-generated defaults
        assert len(fact.id) == 36  # UUID format
        assert fact.source_file_id is None
        assert fact.confirmed is False
        assert fact.superseded_by is None
        assert fact.effective_date is None
        assert isinstance(fact.created_at, datetime)

    def test_unique_ids(self):
        f1 = self._make_fact()
        f2 = self._make_fact()
        assert f1.id != f2.id

    def test_frozen_immutability(self):
        fact = self._make_fact()
        with pytest.raises(AttributeError):
            fact.confirmed = True  # type: ignore[misc]
        with pytest.raises(AttributeError):
            fact.superseded_by = "other-id"  # type: ignore[misc]

    def test_all_fields_explicit(self):
        fact = CaseFact(
            id="fact-123",
            case_id="case-42",
            category=FactCategory.EMPLOYMENT,
            fact_type="position_held",
            value={
                "employer": "Acme Corp",
                "position": "Analyst",
                "start_date": "2019-03-01",
                "end_date": "2021-06-15",
            },
            source_file_id="file-7",
            extraction_method=ExtractionMethod.LLM,
            confidence=0.65,
            confirmed=True,
            superseded_by="fact-456",
            effective_date="2019-03-01",
        )
        assert fact.id == "fact-123"
        assert fact.category == FactCategory.EMPLOYMENT
        assert fact.source_file_id == "file-7"
        assert fact.extraction_method == ExtractionMethod.LLM
        assert fact.confirmed is True
        assert fact.superseded_by == "fact-456"
        assert fact.effective_date == "2019-03-01"
        assert fact.value["position"] == "Analyst"

    def test_manual_fact_convention(self):
        """Manual facts should have confidence 1.0 and confirmed True by convention."""
        fact = self._make_fact(
            extraction_method=ExtractionMethod.MANUAL,
            confidence=1.0,
            confirmed=True,
            source_file_id=None,
        )
        assert fact.extraction_method == ExtractionMethod.MANUAL
        assert fact.confidence == 1.0
        assert fact.confirmed is True
        assert fact.source_file_id is None
