"""Tests for V2.2a.1: GET /api/cases/{case_id}/facts/history endpoint."""

from __future__ import annotations

import sqlite3

from employee_help.api.casefile_schemas import CaseFactListResponse, CaseFactResponse
from employee_help.storage.case_fact_storage import CaseFactStorage
from employee_help.storage.models import (
    CaseFact,
    ExtractionMethod,
    FactCategory,
)


CASE_ID = "case-history-test"
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
    category: FactCategory,
    fact_type: str,
    value: dict,
    *,
    confidence: float = 0.7,
) -> CaseFact:
    return CaseFact(
        case_id=CASE_ID,
        category=category,
        fact_type=fact_type,
        value=value,
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


class TestFactsHistoryIncludesSuperseded:
    """History endpoint returns ALL facts including superseded ones."""

    def setup_method(self):
        self.conn = _make_db()
        self.storage = CaseFactStorage(conn=self.conn)

    def teardown_method(self):
        self.conn.close()

    def test_history_includes_superseded_facts(self):
        """list_all_facts returns both current and superseded facts."""
        old = self.storage.add_fact(_make_fact(
            FactCategory.FINANCIAL, "demand_amount",
            {"label": "Initial demand", "amount": 50000},
        ))
        new_fact = _make_fact(
            FactCategory.FINANCIAL, "demand_amount",
            {"label": "Revised demand", "amount": 75000},
        )
        new = self.storage.supersede(old.id, new_fact)

        # list_current_facts excludes superseded
        current = self.storage.list_current_facts(CASE_ID)
        assert len(current) == 1

        # list_all_facts includes both
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

        # Superseded fact has superseded_by pointing to new fact
        superseded = [f for f in resp.facts if f.superseded_by is not None]
        assert len(superseded) == 1
        assert superseded[0].value["amount"] == 50000
        assert superseded[0].superseded_by == new.id


class TestFactsHistoryOrdering:
    """History facts are ordered by created_at (oldest first)."""

    def setup_method(self):
        self.conn = _make_db()
        self.storage = CaseFactStorage(conn=self.conn)

    def teardown_method(self):
        self.conn.close()

    def test_history_ordered_by_created_at(self):
        """Facts are returned in chronological order (created_at ascending)."""
        f1 = self.storage.add_fact(_make_fact(
            FactCategory.PARTY, "plaintiff",
            {"name": "Jane Doe", "role": "plaintiff"},
        ))
        f2 = self.storage.add_fact(_make_fact(
            FactCategory.COURT, "court_info",
            {"court": "Superior Court", "county": "LA"},
        ))
        f3 = self.storage.add_fact(_make_fact(
            FactCategory.DATE, "filing",
            {"label": "Filed", "date": "2026-01-15"},
        ))

        all_facts = self.storage.list_all_facts(CASE_ID)
        assert len(all_facts) == 3

        # Verify chronological order
        timestamps = [f.created_at for f in all_facts]
        assert timestamps == sorted(timestamps)

        # Verify IDs match insertion order
        ids = [f.id for f in all_facts]
        assert ids == [f1.id, f2.id, f3.id]


class TestFactsHistoryCategoryFilter:
    """History endpoint supports optional category filter."""

    def setup_method(self):
        self.conn = _make_db()
        self.storage = CaseFactStorage(conn=self.conn)

        # Seed across categories, with one superseded
        self.old_party = self.storage.add_fact(_make_fact(
            FactCategory.PARTY, "plaintiff",
            {"name": "J. Doe", "role": "plaintiff"},
        ))
        new_party = _make_fact(
            FactCategory.PARTY, "plaintiff",
            {"name": "Jane Doe", "role": "plaintiff"},
        )
        self.new_party = self.storage.supersede(self.old_party.id, new_party)
        self.storage.add_fact(_make_fact(
            FactCategory.COURT, "court_info",
            {"court": "Superior Court"},
        ))

    def teardown_method(self):
        self.conn.close()

    def test_history_filter_by_category(self):
        """Category filter on history returns all facts in that category, including superseded."""
        party_facts = self.storage.list_all_facts(CASE_ID, category="party")
        assert len(party_facts) == 2  # old + new

        court_facts = self.storage.list_all_facts(CASE_ID, category="court")
        assert len(court_facts) == 1

        # Unfiltered returns all 3
        all_facts = self.storage.list_all_facts(CASE_ID)
        assert len(all_facts) == 3
