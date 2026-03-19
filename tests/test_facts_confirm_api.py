"""Tests for V2.2a.2: PUT /api/cases/{case_id}/facts/{id}/confirm endpoint."""

from __future__ import annotations

import sqlite3

from employee_help.api.casefile_schemas import CaseFactResponse
from employee_help.storage.case_fact_storage import CaseFactStorage
from employee_help.storage.models import (
    CaseFact,
    ExtractionMethod,
    FactCategory,
)


CASE_ID = "case-confirm-test"
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
    category: FactCategory = FactCategory.PARTY,
    fact_type: str = "plaintiff",
    value: dict | None = None,
    *,
    confidence: float = 0.7,
) -> CaseFact:
    return CaseFact(
        case_id=CASE_ID,
        category=category,
        fact_type=fact_type,
        value=value or {"name": "Jane Doe", "role": "plaintiff"},
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


class TestConfirmFact:
    """PUT /api/cases/{case_id}/facts/{id}/confirm sets confirmed = True."""

    def setup_method(self):
        self.conn = _make_db()
        self.storage = CaseFactStorage(conn=self.conn)

    def teardown_method(self):
        self.conn.close()

    def test_confirm_sets_flag_and_returns_updated(self):
        """Confirming a fact sets confirmed=True and returns the updated fact."""
        fact = self.storage.add_fact(_make_fact())
        assert fact.confirmed is False

        self.storage.confirm(fact.id)

        updated = self.storage.get_fact(fact.id)
        assert updated is not None
        assert updated.confirmed is True

        resp = _fact_to_response(updated)
        assert resp.confirmed is True
        assert resp.id == fact.id

    def test_confirm_nonexistent_fact_returns_none(self):
        """get_fact returns None for a non-existent fact ID."""
        result = self.storage.get_fact("nonexistent-id")
        assert result is None

    def test_confirm_idempotent(self):
        """Confirming an already-confirmed fact is idempotent."""
        fact = self.storage.add_fact(_make_fact())

        self.storage.confirm(fact.id)
        self.storage.confirm(fact.id)

        updated = self.storage.get_fact(fact.id)
        assert updated is not None
        assert updated.confirmed is True
