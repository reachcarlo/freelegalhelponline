"""Tests for V2.1b.7: re-extraction on file delete/reprocess."""

import sqlite3

import pytest

from employee_help.casefile.extraction import ExtractionOrchestrator
from employee_help.storage.case_fact_storage import CaseFactStorage
from employee_help.storage.models import FactCategory

CASE_ID = "case-reextract"
FILE_ID_A = "file-a"
FILE_ID_B = "file-b"


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


COMPLAINT_TEXT = """\
COMPLAINT FOR DAMAGES

SUPERIOR COURT OF CALIFORNIA, COUNTY OF LOS ANGELES

MARIA MARTINEZ,
    Plaintiff,

v.

ACME CORP, a California corporation,
    Defendant.

Case No. 26STCV12345

1. Plaintiff was employed by ACME CORP as an Analyst.
2. Plaintiff's annual salary was $95,000.
3. Plaintiff was hired on March 1, 2019.
"""

PAY_STUB_TEXT = """\
EARNINGS STATEMENT

Employer: Acme Corp
Employee: Maria Martinez
Position: Senior Analyst
Department: Finance
Pay Rate: $36.06

Pay Period: 01/01/2025 - 01/15/2025
Gross Pay:    $3,533.70
"""


class TestDeleteFactsOnFileDelete:
    """Facts are removed when a file is deleted."""

    def setup_method(self):
        self.conn = _make_db()
        self.storage = CaseFactStorage(conn=self.conn)
        self.orch = ExtractionOrchestrator()

    def teardown_method(self):
        self.conn.close()

    def test_delete_removes_facts_for_file(self):
        """Deleting a file's facts leaves other files' facts intact."""
        # Extract facts for two different files
        _, facts_a = self.orch.extract_facts(
            COMPLAINT_TEXT, "complaint.pdf", CASE_ID, FILE_ID_A,
        )
        _, facts_b = self.orch.extract_facts(
            PAY_STUB_TEXT, "paystub.pdf", CASE_ID, FILE_ID_B,
        )
        for f in facts_a:
            self.storage.add_fact(f)
        for f in facts_b:
            self.storage.add_fact(f)

        total_before = len(self.storage.list_current_facts(CASE_ID))
        assert total_before == len(facts_a) + len(facts_b)

        # Delete facts for file A
        deleted = self.storage.delete_facts_for_file(FILE_ID_A)
        assert deleted == len(facts_a)

        # File B facts remain
        remaining = self.storage.list_current_facts(CASE_ID)
        assert len(remaining) == len(facts_b)
        assert all(f.source_file_id == FILE_ID_B for f in remaining)


class TestReprocessClearsThenReextracts:
    """Reprocessing deletes old facts and re-extracts fresh ones."""

    def setup_method(self):
        self.conn = _make_db()
        self.storage = CaseFactStorage(conn=self.conn)
        self.orch = ExtractionOrchestrator()

    def teardown_method(self):
        self.conn.close()

    def test_reprocess_replaces_facts(self):
        """Simulates the reprocess flow: delete old facts → re-extract."""
        # Initial extraction
        _, facts_v1 = self.orch.extract_facts(
            COMPLAINT_TEXT, "complaint.pdf", CASE_ID, FILE_ID_A,
        )
        for f in facts_v1:
            self.storage.add_fact(f)
        count_v1 = len(self.storage.list_current_facts(CASE_ID))
        assert count_v1 == len(facts_v1)

        # Simulate reprocess: delete old → extract from updated text
        self.storage.delete_facts_for_file(FILE_ID_A)
        assert len(self.storage.list_current_facts(CASE_ID)) == 0

        _, facts_v2 = self.orch.extract_facts(
            PAY_STUB_TEXT, "paystub.pdf", CASE_ID, FILE_ID_A,
        )
        for f in facts_v2:
            self.storage.add_fact(f)

        # New facts replace old
        current = self.storage.list_current_facts(CASE_ID)
        assert len(current) == len(facts_v2)

        # Should have employment facts from pay stub, not complaint parties
        categories = {f.category for f in current}
        assert FactCategory.EMPLOYMENT in categories
        # Complaint-only categories should be gone
        assert FactCategory.PARTY not in categories
        assert FactCategory.COURT not in categories

    def test_reprocess_idempotent_on_same_text(self):
        """Re-extracting the same text produces the same fact count."""
        _, facts_v1 = self.orch.extract_facts(
            COMPLAINT_TEXT, "complaint.pdf", CASE_ID, FILE_ID_A,
        )
        for f in facts_v1:
            self.storage.add_fact(f)
        count_v1 = len(self.storage.list_current_facts(CASE_ID))

        # Reprocess with same text
        self.storage.delete_facts_for_file(FILE_ID_A)
        _, facts_v2 = self.orch.extract_facts(
            COMPLAINT_TEXT, "complaint.pdf", CASE_ID, FILE_ID_A,
        )
        for f in facts_v2:
            self.storage.add_fact(f)
        count_v2 = len(self.storage.list_current_facts(CASE_ID))

        assert count_v1 == count_v2
        # IDs are different (new UUIDs) but categories match
        cats_v1 = sorted(f.category.value for f in facts_v1)
        cats_v2 = sorted(f.category.value for f in facts_v2)
        assert cats_v1 == cats_v2


class TestDeleteNonexistentFile:
    """Deleting facts for a file with no facts is a no-op."""

    def setup_method(self):
        self.conn = _make_db()
        self.storage = CaseFactStorage(conn=self.conn)

    def teardown_method(self):
        self.conn.close()

    def test_delete_nonexistent_returns_zero(self):
        deleted = self.storage.delete_facts_for_file("nonexistent-file-id")
        assert deleted == 0
