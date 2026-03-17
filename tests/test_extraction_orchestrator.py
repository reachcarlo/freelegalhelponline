"""Tests for ExtractionOrchestrator (V2.1b.6)."""

import sqlite3

import pytest

from employee_help.casefile.classifiers import DocumentType
from employee_help.casefile.extraction import ExtractionOrchestrator
from employee_help.storage.case_fact_storage import CaseFactStorage
from employee_help.storage.models import (
    CaseFact,
    ExtractionMethod,
    FactCategory,
)

CASE_ID = "case-001"
FILE_ID = "file-001"


# ── Schema setup for in-memory DB ──────────────────────────────────


def _make_db() -> sqlite3.Connection:
    """Create an in-memory SQLite DB with schema for case_facts."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=OFF")  # No FK parent tables in tests
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


# ── Orchestrator unit tests ────────────────────────────────────────


class TestClassification:
    def setup_method(self):
        self.orch = ExtractionOrchestrator()

    def test_complaint_classified(self):
        text = """
COMPLAINT FOR DAMAGES

SUPERIOR COURT OF CALIFORNIA, COUNTY OF LOS ANGELES

MARIA MARTINEZ,
    Plaintiff,

v.

ACME CORP, a California corporation,
    Defendant.

Case No. 26STCV12345

GENERAL ALLEGATIONS

1. Plaintiff alleges as follows.
"""
        doc_type, _ = self.orch.extract_facts(text, "complaint.pdf", CASE_ID, FILE_ID)
        assert doc_type == DocumentType.COMPLAINT

    def test_pay_stub_classified(self):
        text = """
EARNINGS STATEMENT

Employer: Acme Corp
Employee: Maria Martinez
Pay Period: 01/01/2025 - 01/15/2025

Gross Pay:    $3,533.70
Net Pay:      $2,558.37
"""
        doc_type, _ = self.orch.extract_facts(text, "paystub.pdf", CASE_ID, FILE_ID)
        assert doc_type == DocumentType.PAY_STUB

    def test_empty_text_returns_generic(self):
        doc_type, facts = self.orch.extract_facts("", "file.pdf", CASE_ID, FILE_ID)
        assert doc_type == DocumentType.GENERIC
        assert facts == []


class TestCaptionExtraction:
    def setup_method(self):
        self.orch = ExtractionOrchestrator()

    def test_complaint_extracts_parties(self):
        text = """
SUPERIOR COURT OF CALIFORNIA, COUNTY OF LOS ANGELES

MARIA MARTINEZ,
    Plaintiff,

v.

ACME CORP, a California corporation,
    Defendant.

Case No. 26STCV12345

COMPLAINT FOR DAMAGES

1. Plaintiff alleges as follows.
"""
        _, facts = self.orch.extract_facts(text, "complaint.pdf", CASE_ID, FILE_ID)
        party_facts = [f for f in facts if f.category == FactCategory.PARTY]
        assert len(party_facts) >= 2
        names = {f.value["name"] for f in party_facts}
        assert any("MARIA MARTINEZ" in n for n in names)
        assert any("ACME CORP" in n for n in names)

    def test_complaint_extracts_court(self):
        text = """
SUPERIOR COURT OF CALIFORNIA, COUNTY OF LOS ANGELES

MARIA MARTINEZ,
    Plaintiff,

v.

ACME CORP,
    Defendant.

Case No. 26STCV12345
Dept. 7

COMPLAINT FOR DAMAGES

1. Plaintiff alleges as follows.
"""
        _, facts = self.orch.extract_facts(text, "complaint.pdf", CASE_ID, FILE_ID)
        court_facts = [f for f in facts if f.category == FactCategory.COURT]
        assert len(court_facts) >= 1
        court = court_facts[0].value
        assert "los angeles" in court.get("county", "").lower()
        assert "26STCV12345" in court.get("case_number", "")

    def test_generic_doc_no_caption_extraction(self):
        text = "This is a generic document with no court filing structure."
        _, facts = self.orch.extract_facts(text, "notes.txt", CASE_ID, FILE_ID)
        party_facts = [f for f in facts if f.category == FactCategory.PARTY]
        court_facts = [f for f in facts if f.category == FactCategory.COURT]
        assert party_facts == []
        assert court_facts == []


class TestDateExtraction:
    def setup_method(self):
        self.orch = ExtractionOrchestrator()

    def test_complaint_dates(self):
        text = """
Filed: January 15, 2026

1. Plaintiff was hired on March 1, 2019.

Trial date: March 10, 2027
"""
        _, facts = self.orch.extract_facts(text, "complaint.pdf", CASE_ID, FILE_ID)
        date_facts = [f for f in facts if f.category == FactCategory.DATE]
        dates = {f.value["date"] for f in date_facts}
        assert "2026-01-15" in dates
        assert "2019-03-01" in dates
        assert "2027-03-10" in dates

    def test_date_facts_have_effective_date(self):
        text = "Filed: January 15, 2026"
        _, facts = self.orch.extract_facts(text, "doc.pdf", CASE_ID, FILE_ID)
        date_facts = [f for f in facts if f.category == FactCategory.DATE]
        assert len(date_facts) >= 1
        assert date_facts[0].effective_date == "2026-01-15"


class TestFinancialExtraction:
    def setup_method(self):
        self.orch = ExtractionOrchestrator()

    def test_demand_amounts(self):
        text = "Settlement Demand: $450,000.00"
        _, facts = self.orch.extract_facts(text, "demand.pdf", CASE_ID, FILE_ID)
        fin_facts = [f for f in facts if f.category == FactCategory.FINANCIAL]
        assert len(fin_facts) >= 1
        assert fin_facts[0].value["amount"] == 450000.0
        assert fin_facts[0].value["amount_type"] == "demand"


class TestEmploymentExtraction:
    def setup_method(self):
        self.orch = ExtractionOrchestrator()

    def test_employment_composite_fact(self):
        text = """
Employer: Acme Corp
Position: Senior Analyst
Department: Finance
Pay Rate: $36.06
"""
        _, facts = self.orch.extract_facts(text, "paystub.pdf", CASE_ID, FILE_ID)
        emp_facts = [f for f in facts if f.category == FactCategory.EMPLOYMENT]
        assert len(emp_facts) >= 1
        composite = emp_facts[0].value
        assert composite["employer"] == "Acme Corp"
        assert composite["position"] == "Senior Analyst"
        assert composite["department"] == "Finance"
        assert composite["compensation_rate"] == 36.06

    def test_employment_no_data(self):
        text = "This document has no employment information."
        _, facts = self.orch.extract_facts(text, "notes.txt", CASE_ID, FILE_ID)
        emp_facts = [f for f in facts if f.category == FactCategory.EMPLOYMENT]
        assert emp_facts == []


class TestFactMetadata:
    def setup_method(self):
        self.orch = ExtractionOrchestrator()

    def test_facts_have_correct_metadata(self):
        text = "Employer: Acme Corp"
        _, facts = self.orch.extract_facts(text, "doc.pdf", CASE_ID, FILE_ID)
        assert len(facts) >= 1
        fact = facts[0]
        assert fact.case_id == CASE_ID
        assert fact.source_file_id == FILE_ID
        assert fact.extraction_method == ExtractionMethod.REGEX
        assert 0.0 < fact.confidence <= 1.0
        assert fact.confirmed is False
        assert fact.superseded_by is None


class TestStorageIntegration:
    """Integration tests: orchestrator → CaseFactStorage round-trip."""

    def setup_method(self):
        self.orch = ExtractionOrchestrator()
        self.conn = _make_db()
        self.storage = CaseFactStorage(conn=self.conn)

    def teardown_method(self):
        self.conn.close()

    def test_facts_persist_and_query(self):
        text = """
COMPLAINT FOR DAMAGES

SUPERIOR COURT OF CALIFORNIA, COUNTY OF LOS ANGELES

MARIA MARTINEZ,
    Plaintiff,

v.

ACME CORP, a California corporation,
    Defendant.

Case No. 26STCV12345

1. Plaintiff alleges as follows.
2. Plaintiff was employed by ACME CORP as an Analyst.
3. Plaintiff worked in the Finance department.
4. Plaintiff's annual salary was $95,000.
5. Plaintiff was hired on March 1, 2019.
"""
        doc_type, facts = self.orch.extract_facts(
            text, "complaint.pdf", CASE_ID, FILE_ID,
        )
        assert doc_type == DocumentType.COMPLAINT

        # Persist all facts
        for fact in facts:
            self.storage.add_fact(fact)

        # Query back
        all_facts = self.storage.list_current_facts(CASE_ID)
        assert len(all_facts) == len(facts)

        # Verify categories present
        categories = {f.category for f in all_facts}
        assert FactCategory.PARTY in categories
        assert FactCategory.COURT in categories
        assert FactCategory.DATE in categories
        assert FactCategory.EMPLOYMENT in categories

    def test_delete_facts_for_file(self):
        text = "Employer: Acme Corp"
        _, facts = self.orch.extract_facts(text, "doc.pdf", CASE_ID, FILE_ID)
        for fact in facts:
            self.storage.add_fact(fact)

        assert len(self.storage.list_current_facts(CASE_ID)) > 0

        # Delete facts for file
        deleted = self.storage.delete_facts_for_file(FILE_ID)
        assert deleted > 0
        assert len(self.storage.list_current_facts(CASE_ID)) == 0

    def test_full_pay_stub_extraction(self):
        text = """
EARNINGS STATEMENT

Employer: Acme Corp
Employee: Maria Martinez
Position: Senior Analyst
Department: Finance
Pay Rate: $36.06

Pay Period: 01/01/2025 - 01/15/2025
Gross Pay:    $3,533.70
Net Pay:      $2,558.37
"""
        doc_type, facts = self.orch.extract_facts(
            text, "paystub.pdf", CASE_ID, FILE_ID,
        )
        assert doc_type == DocumentType.PAY_STUB

        for fact in facts:
            self.storage.add_fact(fact)

        all_facts = self.storage.list_current_facts(CASE_ID)

        # Should have employment, financial, and date facts
        categories = {f.category for f in all_facts}
        assert FactCategory.EMPLOYMENT in categories
        assert FactCategory.FINANCIAL in categories
        assert FactCategory.DATE in categories

        # Employment composite fact should have employer + position + department + compensation
        emp_facts = self.storage.list_current_facts(CASE_ID, category="employment")
        composite = emp_facts[0].value
        assert composite["employer"] == "Acme Corp"
        assert composite["position"] == "Senior Analyst"
        assert composite["department"] == "Finance"
        assert composite["compensation_rate"] == 36.06
