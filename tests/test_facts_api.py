"""Tests for V2.1c.2: GET /api/cases/{case_id}/facts endpoint."""

from __future__ import annotations

import sqlite3

import pytest

from employee_help.api.casefile_schemas import CaseFactListResponse, CaseFactResponse
from employee_help.storage.case_fact_storage import CaseFactStorage
from employee_help.storage.models import (
    CaseFact,
    ExtractionMethod,
    FactCategory,
)


CASE_ID = "case-facts-test"
FILE_ID = "file-complaint"


def _make_db() -> sqlite3.Connection:
    """Create an in-memory SQLite DB with case_facts schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("""
        CREATE TABLE case_facts (
            id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            category TEXT NOT NULL,
            fact_type TEXT NOT NULL,
            value TEXT NOT NULL,
            source_file_id TEXT,
            extraction_method TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0.5,
            confirmed INTEGER NOT NULL DEFAULT 0,
            superseded_by TEXT,
            effective_date TEXT,
            created_at TEXT NOT NULL
        )
    """)
    return conn


def _make_fact(
    category: FactCategory,
    fact_type: str,
    value: dict,
    *,
    confidence: float = 0.7,
    confirmed: bool = False,
    source_file_id: str = FILE_ID,
) -> CaseFact:
    return CaseFact(
        case_id=CASE_ID,
        category=category,
        fact_type=fact_type,
        value=value,
        source_file_id=source_file_id,
        extraction_method=ExtractionMethod.REGEX,
        confidence=confidence,
        confirmed=confirmed,
    )


class TestFactsEndpointEmpty:
    """Facts endpoint for a case with no facts returns empty list."""

    def setup_method(self):
        self.conn = _make_db()
        self.storage = CaseFactStorage(conn=self.conn)

    def teardown_method(self):
        self.conn.close()

    def test_empty_case_returns_empty_facts(self):
        """A case with no facts returns an empty list with total=0."""
        facts = self.storage.list_current_facts(CASE_ID)
        resp = CaseFactListResponse(
            facts=[],
            total=len(facts),
        )
        assert resp.facts == []
        assert resp.total == 0


class TestFactsEndpointWithFacts:
    """Facts endpoint returns facts with optional category filter."""

    def setup_method(self):
        self.conn = _make_db()
        self.storage = CaseFactStorage(conn=self.conn)

        # Seed facts across categories
        self.storage.add_fact(_make_fact(
            FactCategory.PARTY, "plaintiff",
            {"name": "Maria Martinez", "role": "plaintiff", "party_type": "individual"},
        ))
        self.storage.add_fact(_make_fact(
            FactCategory.PARTY, "defendant",
            {"name": "Acme Corp", "role": "defendant", "party_type": "entity"},
        ))
        self.storage.add_fact(_make_fact(
            FactCategory.COURT, "court_info",
            {"court": "Superior Court of California", "county": "Los Angeles"},
        ))
        self.storage.add_fact(_make_fact(
            FactCategory.EMPLOYMENT, "position_held",
            {"employer": "Acme Corp", "position": "Analyst", "start_date": "2019-03-01"},
        ))
        self.storage.add_fact(_make_fact(
            FactCategory.DATE, "filing",
            {"label": "Complaint filed", "date": "2026-01-15", "date_type": "filing"},
        ))

    def teardown_method(self):
        self.conn.close()

    def test_list_all_facts(self):
        """Without category filter, returns all current facts."""
        facts = self.storage.list_current_facts(CASE_ID)
        resp = CaseFactListResponse(
            facts=[
                CaseFactResponse(
                    id=f.id,
                    case_id=f.case_id,
                    category=f.category.value,
                    fact_type=f.fact_type,
                    value=f.value,
                    source_file_id=f.source_file_id,
                    extraction_method=f.extraction_method.value,
                    confidence=f.confidence,
                    confirmed=f.confirmed,
                    superseded_by=f.superseded_by,
                    effective_date=f.effective_date,
                    created_at=f.created_at.isoformat(),
                )
                for f in facts
            ],
            total=len(facts),
        )
        assert resp.total == 5
        assert len(resp.facts) == 5
        categories = {f.category for f in resp.facts}
        assert categories == {"party", "court", "employment", "date"}

    def test_filter_by_category_party(self):
        """Filter by category=party returns only party facts."""
        facts = self.storage.list_current_facts(CASE_ID, category="party")
        resp = CaseFactListResponse(
            facts=[
                CaseFactResponse(
                    id=f.id,
                    case_id=f.case_id,
                    category=f.category.value,
                    fact_type=f.fact_type,
                    value=f.value,
                    source_file_id=f.source_file_id,
                    extraction_method=f.extraction_method.value,
                    confidence=f.confidence,
                    confirmed=f.confirmed,
                    created_at=f.created_at.isoformat(),
                )
                for f in facts
            ],
            total=len(facts),
        )
        assert resp.total == 2
        assert all(f.category == "party" for f in resp.facts)
        names = {f.value["name"] for f in resp.facts}
        assert names == {"Maria Martinez", "Acme Corp"}

    def test_filter_by_category_court(self):
        """Filter by category=court returns only court facts."""
        facts = self.storage.list_current_facts(CASE_ID, category="court")
        assert len(facts) == 1
        assert facts[0].category == FactCategory.COURT
        assert facts[0].value["court"] == "Superior Court of California"

    def test_response_schema_serialization(self):
        """CaseFactResponse serializes all fields correctly."""
        facts = self.storage.list_current_facts(CASE_ID, category="employment")
        assert len(facts) == 1
        f = facts[0]
        resp = CaseFactResponse(
            id=f.id,
            case_id=f.case_id,
            category=f.category.value,
            fact_type=f.fact_type,
            value=f.value,
            source_file_id=f.source_file_id,
            extraction_method=f.extraction_method.value,
            confidence=f.confidence,
            confirmed=f.confirmed,
            superseded_by=f.superseded_by,
            effective_date=f.effective_date,
            created_at=f.created_at.isoformat(),
        )
        data = resp.model_dump()
        assert data["category"] == "employment"
        assert data["fact_type"] == "position_held"
        assert data["value"]["employer"] == "Acme Corp"
        assert data["value"]["position"] == "Analyst"
        assert data["extraction_method"] == "regex"
        assert data["confidence"] == 0.7
        assert data["confirmed"] is False
        assert data["superseded_by"] is None
        assert data["source_file_id"] == FILE_ID


class TestFactsSupersededExcluded:
    """Superseded facts are excluded from the endpoint."""

    def setup_method(self):
        self.conn = _make_db()
        self.storage = CaseFactStorage(conn=self.conn)

    def teardown_method(self):
        self.conn.close()

    def test_superseded_facts_not_returned(self):
        """Facts that have been superseded are excluded from list_current_facts."""
        old = self.storage.add_fact(_make_fact(
            FactCategory.FINANCIAL, "demand_amount",
            {"label": "Initial demand", "amount": 50000},
        ))
        new = _make_fact(
            FactCategory.FINANCIAL, "demand_amount",
            {"label": "Revised demand", "amount": 75000},
        )
        self.storage.supersede(old.id, new)

        facts = self.storage.list_current_facts(CASE_ID)
        assert len(facts) == 1
        assert facts[0].value["amount"] == 75000
        assert facts[0].superseded_by is None
