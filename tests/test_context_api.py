"""Tests for V2.1c.1: GET /api/cases/{case_id}/context endpoint."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime

import pytest

from employee_help.api.casefile_schemas import CaseContextResponse
from employee_help.casefile.context_builder import CaseContextBuilder
from employee_help.storage.case_fact_storage import CaseFactStorage
from employee_help.storage.models import (
    CaseFact,
    ExtractionMethod,
    FactCategory,
)


CASE_ID = "case-ctx-test"
CASE_NAME = "Martinez v. Acme Corp"
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


class TestGetContextEndpointEmpty:
    """Context for a case with no facts returns empty structure."""

    def setup_method(self):
        self.conn = _make_db()
        self.storage = CaseFactStorage(conn=self.conn)
        self.builder = CaseContextBuilder()

    def teardown_method(self):
        self.conn.close()

    def test_empty_case_returns_valid_context(self):
        """A case with no facts should return a valid CaseContext with empty lists."""
        ctx = self.builder.build(CASE_ID, CASE_NAME, self.storage)

        # Verify structure maps to response schema
        resp = CaseContextResponse(
            case_id=ctx.case_id,
            case_name=ctx.case_name,
            parties=[],
            court=None,
            attorneys=[],
            employment_history=[],
            claims=[],
            key_dates=[],
            financials=[],
            fact_count=0,
            confirmed_count=0,
            extraction_sources={},
            plaintiff_names=[],
            defendant_names=[],
            all_person_names=[],
            all_entity_names=[],
        )
        assert resp.case_id == CASE_ID
        assert resp.case_name == CASE_NAME
        assert resp.fact_count == 0
        assert resp.parties == []
        assert resp.court is None


class TestGetContextWithFacts:
    """Context endpoint returns assembled facts from multiple categories."""

    def setup_method(self):
        self.conn = _make_db()
        self.storage = CaseFactStorage(conn=self.conn)
        self.builder = CaseContextBuilder()

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

    def test_context_includes_all_categories(self):
        """Context includes parties, court, employment, and dates."""
        ctx = self.builder.build(CASE_ID, CASE_NAME, self.storage)

        assert len(ctx.parties) == 2
        assert ctx.court is not None
        assert ctx.court.court == "Superior Court of California"
        assert ctx.court.county == "Los Angeles"
        assert len(ctx.employment_history) == 1
        assert ctx.employment_history[0].employer == "Acme Corp"
        assert len(ctx.key_dates) == 1
        assert ctx.fact_count == 5
        assert ctx.plaintiff_names == ["Maria Martinez"]
        assert ctx.defendant_names == ["Acme Corp"]

    def test_response_schema_serialization(self):
        """CaseContextResponse serializes all fields correctly."""
        ctx = self.builder.build(CASE_ID, CASE_NAME, self.storage)

        resp = CaseContextResponse(
            case_id=ctx.case_id,
            case_name=ctx.case_name,
            parties=[
                {"name": p.name, "role": p.role, "party_type": p.party_type, "count": p.count}
                for p in ctx.parties
            ],
            court=(
                {"court": ctx.court.court, "county": ctx.court.county,
                 "department": ctx.court.department, "judge": ctx.court.judge}
                if ctx.court else None
            ),
            attorneys=[],
            employment_history=[
                {"employer": e.employer, "position": e.position, "department": e.department,
                 "compensation_rate": e.compensation_rate, "compensation_type": e.compensation_type,
                 "pay_period": e.pay_period, "start_date": e.start_date, "end_date": e.end_date,
                 "change_reason": e.change_reason}
                for e in ctx.employment_history
            ],
            claims=[],
            key_dates=[
                {"label": d.label, "date": d.date, "date_type": d.date_type}
                for d in ctx.key_dates
            ],
            financials=[],
            fact_count=ctx.fact_count,
            confirmed_count=ctx.confirmed_count,
            extraction_sources=ctx.extraction_sources,
            plaintiff_names=ctx.plaintiff_names,
            defendant_names=ctx.defendant_names,
            all_person_names=ctx.all_person_names,
            all_entity_names=ctx.all_entity_names,
        )

        data = resp.model_dump()
        assert data["case_id"] == CASE_ID
        assert len(data["parties"]) == 2
        assert data["court"]["court"] == "Superior Court of California"
        assert data["employment_history"][0]["position"] == "Analyst"
        assert data["key_dates"][0]["date"] == "2026-01-15"
        assert data["plaintiff_names"] == ["Maria Martinez"]
        assert data["defendant_names"] == ["Acme Corp"]
        assert data["all_person_names"] == ["Maria Martinez"]
        assert "Acme Corp" in data["all_entity_names"]

    def test_extraction_sources_tracked(self):
        """Extraction sources map category → [file_ids]."""
        ctx = self.builder.build(CASE_ID, CASE_NAME, self.storage)

        assert "party" in ctx.extraction_sources
        assert FILE_ID in ctx.extraction_sources["party"]
        assert "court" in ctx.extraction_sources
        assert FILE_ID in ctx.extraction_sources["court"]


class TestContextConfirmedCounts:
    """Context tracks confirmed vs total fact counts."""

    def setup_method(self):
        self.conn = _make_db()
        self.storage = CaseFactStorage(conn=self.conn)
        self.builder = CaseContextBuilder()

    def teardown_method(self):
        self.conn.close()

    def test_confirmed_count_reflects_confirmed_facts(self):
        """confirmed_count increments when facts are confirmed."""
        f1 = self.storage.add_fact(_make_fact(
            FactCategory.PARTY, "plaintiff",
            {"name": "Maria Martinez", "role": "plaintiff", "party_type": "individual"},
        ))
        self.storage.add_fact(_make_fact(
            FactCategory.COURT, "court_info",
            {"court": "Superior Court", "county": "San Diego"},
        ))

        # Before confirmation
        ctx = self.builder.build(CASE_ID, CASE_NAME, self.storage)
        assert ctx.fact_count == 2
        assert ctx.confirmed_count == 0

        # Confirm one fact
        self.storage.confirm(f1.id)

        ctx = self.builder.build(CASE_ID, CASE_NAME, self.storage)
        assert ctx.fact_count == 2
        assert ctx.confirmed_count == 1
