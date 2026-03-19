"""Tests for V2.2a.3: POST /api/cases/{case_id}/facts/{id}/supersede endpoint."""

from __future__ import annotations

import sqlite3

from employee_help.api.casefile_schemas import CaseFactListResponse, CaseFactResponse
from employee_help.storage.case_fact_storage import CaseFactStorage
from employee_help.storage.models import (
    CaseFact,
    ExtractionMethod,
    FactCategory,
)


CASE_ID = "case-supersede-test"
FILE_ID = "file-complaint"


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


def _make_fact(
    category: FactCategory = FactCategory.FINANCIAL,
    fact_type: str = "demand_amount",
    value: dict | None = None,
    *,
    confidence: float = 0.7,
) -> CaseFact:
    return CaseFact(
        case_id=CASE_ID,
        category=category,
        fact_type=fact_type,
        value=value or {"label": "Initial demand", "amount": 50000},
        source_file_id=FILE_ID,
        extraction_method=ExtractionMethod.REGEX,
        confidence=confidence,
    )


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


class TestSupersedeFact:
    """POST /api/cases/{case_id}/facts/{id}/supersede creates a new MANUAL fact."""

    def setup_method(self):
        self.conn = _make_db()
        self.storage = CaseFactStorage(conn=self.conn)

    def teardown_method(self):
        self.conn.close()

    def test_supersede_creates_manual_fact(self):
        """Superseding creates a new fact with method=MANUAL, confidence=1.0, confirmed=True."""
        old = self.storage.add_fact(_make_fact())

        new_fact = CaseFact(
            case_id=CASE_ID,
            category=FactCategory.FINANCIAL,
            fact_type="demand_amount",
            value={"label": "Revised demand", "amount": 75000},
            extraction_method=ExtractionMethod.MANUAL,
            confidence=1.0,
            confirmed=True,
        )
        created = self.storage.supersede(old.id, new_fact)

        resp = _fact_to_response(created)
        assert resp.extraction_method == "manual"
        assert resp.confidence == 1.0
        assert resp.confirmed is True
        assert resp.value["amount"] == 75000
        assert resp.superseded_by is None  # new fact is not itself superseded

    def test_supersede_links_old_fact(self):
        """Old fact's superseded_by points to the new fact."""
        old = self.storage.add_fact(_make_fact())

        new_fact = CaseFact(
            case_id=CASE_ID,
            category=FactCategory.FINANCIAL,
            fact_type="demand_amount",
            value={"label": "Revised demand", "amount": 75000},
            extraction_method=ExtractionMethod.MANUAL,
            confidence=1.0,
            confirmed=True,
        )
        created = self.storage.supersede(old.id, new_fact)

        old_updated = self.storage.get_fact(old.id)
        assert old_updated is not None
        assert old_updated.superseded_by == created.id

    def test_supersede_current_facts_excludes_old(self):
        """list_current_facts returns only the new fact, not the superseded one."""
        old = self.storage.add_fact(_make_fact())

        new_fact = CaseFact(
            case_id=CASE_ID,
            category=FactCategory.FINANCIAL,
            fact_type="demand_amount",
            value={"label": "Revised demand", "amount": 75000},
            extraction_method=ExtractionMethod.MANUAL,
            confidence=1.0,
            confirmed=True,
        )
        created = self.storage.supersede(old.id, new_fact)

        current = self.storage.list_current_facts(CASE_ID)
        assert len(current) == 1
        assert current[0].id == created.id
        assert current[0].value["amount"] == 75000

    def test_supersede_history_includes_both(self):
        """list_all_facts (history) returns both old and new facts."""
        old = self.storage.add_fact(_make_fact())

        new_fact = CaseFact(
            case_id=CASE_ID,
            category=FactCategory.FINANCIAL,
            fact_type="demand_amount",
            value={"label": "Revised demand", "amount": 75000},
            extraction_method=ExtractionMethod.MANUAL,
            confidence=1.0,
            confirmed=True,
        )
        self.storage.supersede(old.id, new_fact)

        all_facts = self.storage.list_all_facts(CASE_ID)
        assert len(all_facts) == 2

        resp = CaseFactListResponse(
            facts=[_fact_to_response(f) for f in all_facts],
            total=len(all_facts),
        )
        assert resp.total == 2
        amounts = [f.value["amount"] for f in resp.facts]
        assert 50000 in amounts
        assert 75000 in amounts

    def test_supersede_nonexistent_fact(self):
        """get_fact returns None for a non-existent fact ID (404 path)."""
        result = self.storage.get_fact("nonexistent-id")
        assert result is None
