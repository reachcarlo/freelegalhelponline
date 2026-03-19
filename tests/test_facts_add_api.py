"""Tests for V2.2a.4: POST /api/cases/{case_id}/facts — add manual fact endpoint."""

from __future__ import annotations

import sqlite3

from employee_help.api.casefile_schemas import CaseFactResponse
from employee_help.storage.case_fact_storage import CaseFactStorage
from employee_help.storage.models import (
    CaseFact,
    ExtractionMethod,
    FactCategory,
)


CASE_ID = "case-add-fact-test"


def _make_db() -> sqlite3.Connection:
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


def _fact_to_response(f: CaseFact) -> CaseFactResponse:
    return CaseFactResponse(
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


class TestAddManualFact:
    """POST /api/cases/{case_id}/facts creates a new MANUAL fact."""

    def setup_method(self):
        self.conn = _make_db()
        self.storage = CaseFactStorage(conn=self.conn)

    def teardown_method(self):
        self.conn.close()

    def test_add_manual_fact_creates_with_correct_attributes(self):
        """Manual fact has method=MANUAL, confidence=1.0, confirmed=True."""
        fact = CaseFact(
            case_id=CASE_ID,
            category=FactCategory.PARTY,
            fact_type="plaintiff",
            value={"name": "John Smith", "role": "plaintiff"},
            extraction_method=ExtractionMethod.MANUAL,
            confidence=1.0,
            confirmed=True,
        )
        created = self.storage.add_fact(fact)

        resp = _fact_to_response(created)
        assert resp.extraction_method == "manual"
        assert resp.confidence == 1.0
        assert resp.confirmed is True
        assert resp.value["name"] == "John Smith"
        assert resp.case_id == CASE_ID
        assert resp.superseded_by is None

    def test_add_manual_fact_with_source_file(self):
        """Manual fact can optionally link to a source_file_id."""
        fact = CaseFact(
            case_id=CASE_ID,
            category=FactCategory.EMPLOYMENT,
            fact_type="employer",
            value={"employer": "Acme Corp", "position": "Engineer"},
            source_file_id="file-offer-letter",
            extraction_method=ExtractionMethod.MANUAL,
            confidence=1.0,
            confirmed=True,
        )
        created = self.storage.add_fact(fact)

        resp = _fact_to_response(created)
        assert resp.source_file_id == "file-offer-letter"
        assert resp.extraction_method == "manual"

    def test_add_manual_fact_with_effective_date(self):
        """Manual fact can include an effective_date."""
        fact = CaseFact(
            case_id=CASE_ID,
            category=FactCategory.DATE,
            fact_type="termination_date",
            value={"label": "Termination", "date": "2025-06-15"},
            extraction_method=ExtractionMethod.MANUAL,
            confidence=1.0,
            confirmed=True,
            effective_date="2025-06-15",
        )
        created = self.storage.add_fact(fact)

        resp = _fact_to_response(created)
        assert resp.effective_date == "2025-06-15"
        assert resp.fact_type == "termination_date"

    def test_add_manual_fact_appears_in_current_facts(self):
        """Newly added manual fact is returned by list_current_facts."""
        fact = CaseFact(
            case_id=CASE_ID,
            category=FactCategory.FINANCIAL,
            fact_type="salary",
            value={"label": "Annual salary", "amount": 120000},
            extraction_method=ExtractionMethod.MANUAL,
            confidence=1.0,
            confirmed=True,
        )
        created = self.storage.add_fact(fact)

        current = self.storage.list_current_facts(CASE_ID)
        assert len(current) == 1
        assert current[0].id == created.id
        assert current[0].value["amount"] == 120000
