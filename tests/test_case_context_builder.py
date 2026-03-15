"""Tests for LITIGAGENTv2 CaseContextBuilder (V2.1a.5)."""

from pathlib import Path

import pytest

from employee_help.casefile.context import (
    AttorneyView,
    ClaimView,
    CourtView,
    DateView,
    EmploymentPeriodView,
    FinancialView,
    PartyView,
)
from employee_help.casefile.context_builder import CaseContextBuilder
from employee_help.storage.case_fact_storage import CaseFactStorage
from employee_help.storage.models import (
    CaseFact,
    ExtractionMethod,
    FactCategory,
)
from employee_help.storage.storage import Storage


@pytest.fixture
def storage(tmp_path: Path) -> Storage:
    db_path = tmp_path / "test_builder.db"
    s = Storage(db_path=db_path)
    yield s
    s.close()


@pytest.fixture
def fact_storage(storage: Storage) -> CaseFactStorage:
    return CaseFactStorage(conn=storage._conn)


@pytest.fixture
def case_id(storage: Storage) -> str:
    now = "2026-03-15T00:00:00+00:00"
    storage._conn.execute(
        "INSERT INTO cases (id, name, user_id, organization_id, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("c1", "Smith v. Acme Corp", "u1", "o1", "active", now, now),
    )
    storage._conn.commit()
    return "c1"


def _fact(case_id: str = "c1", **overrides) -> CaseFact:
    defaults = {
        "case_id": case_id,
        "category": FactCategory.PARTY,
        "fact_type": "plaintiff",
        "value": {"name": "Alice", "role": "plaintiff", "party_type": "individual"},
        "extraction_method": ExtractionMethod.REGEX,
        "confidence": 0.85,
    }
    defaults.update(overrides)
    return CaseFact(**defaults)


class TestBuildEmpty:
    def test_empty_case(self, fact_storage, case_id):
        ctx = CaseContextBuilder().build(case_id, "Smith v. Acme Corp", fact_storage)
        assert ctx.case_id == "c1"
        assert ctx.case_name == "Smith v. Acme Corp"
        assert ctx.parties == []
        assert ctx.court is None
        assert ctx.attorneys == []
        assert ctx.employment_history == []
        assert ctx.claims == []
        assert ctx.key_dates == []
        assert ctx.financials == []
        assert ctx.fact_count == 0
        assert ctx.confirmed_count == 0
        assert ctx.extraction_sources == {}


class TestBuildParties:
    def test_builds_parties(self, fact_storage, case_id):
        fact_storage.add_fact(_fact(case_id, value={
            "name": "Alice", "role": "plaintiff", "party_type": "individual",
        }))
        fact_storage.add_fact(_fact(case_id, fact_type="defendant", value={
            "name": "Acme Corp", "role": "defendant", "party_type": "entity",
        }))
        fact_storage.add_fact(_fact(case_id, fact_type="doe", value={
            "name": "Does 1-50", "role": "defendant", "party_type": "doe", "count": 50,
        }))

        ctx = CaseContextBuilder().build(case_id, "Test", fact_storage)
        assert len(ctx.parties) == 3
        assert ctx.plaintiff_names == ["Alice"]
        assert "Acme Corp" in ctx.defendant_names
        doe = [p for p in ctx.parties if p.party_type == "doe"][0]
        assert doe.count == 50


class TestBuildCourt:
    def test_single_court(self, fact_storage, case_id):
        fact_storage.add_fact(_fact(case_id, category=FactCategory.COURT,
                                    fact_type="court", value={
            "court": "Superior Court of California",
            "county": "Los Angeles",
            "department": "7",
            "judge": "Hon. Sarah Chen",
        }))
        ctx = CaseContextBuilder().build(case_id, "Test", fact_storage)
        assert ctx.court is not None
        assert ctx.court.court == "Superior Court of California"
        assert ctx.court.county == "Los Angeles"
        assert ctx.court.department == "7"
        assert ctx.court.judge == "Hon. Sarah Chen"

    def test_court_resolution_confirmed_wins(self, fact_storage, case_id):
        """Confirmed court fact wins over unconfirmed with higher confidence."""
        fact_storage.add_fact(_fact(case_id, category=FactCategory.COURT,
                                    fact_type="court", confidence=0.95, value={
            "court": "Superior Court", "county": "San Diego",
        }))
        fact_storage.add_fact(_fact(case_id, category=FactCategory.COURT,
                                    fact_type="court", confidence=0.70,
                                    confirmed=True, value={
            "court": "Superior Court", "county": "Los Angeles",
        }))
        ctx = CaseContextBuilder().build(case_id, "Test", fact_storage)
        assert ctx.court.county == "Los Angeles"

    def test_court_resolution_highest_confidence(self, fact_storage, case_id):
        """Among unconfirmed, highest confidence wins."""
        fact_storage.add_fact(_fact(case_id, category=FactCategory.COURT,
                                    fact_type="court", confidence=0.60, value={
            "court": "Superior Court", "county": "San Diego",
        }))
        fact_storage.add_fact(_fact(case_id, category=FactCategory.COURT,
                                    fact_type="court", confidence=0.90, value={
            "court": "Superior Court", "county": "Los Angeles",
        }))
        ctx = CaseContextBuilder().build(case_id, "Test", fact_storage)
        assert ctx.court.county == "Los Angeles"


class TestBuildAttorneys:
    def test_builds_attorneys(self, fact_storage, case_id):
        fact_storage.add_fact(_fact(case_id, category=FactCategory.ATTORNEY,
                                    fact_type="attorney", value={
            "name": "David Kim", "side": "plaintiff",
            "bar_number": "298451", "firm": "Kim & Associates",
            "email": "david@kimlaw.com",
        }))
        fact_storage.add_fact(_fact(case_id, category=FactCategory.ATTORNEY,
                                    fact_type="attorney", value={
            "name": "Jane Doe", "side": "defendant",
        }))

        ctx = CaseContextBuilder().build(case_id, "Test", fact_storage)
        assert len(ctx.attorneys) == 2
        pk = [a for a in ctx.attorneys if a.name == "David Kim"][0]
        assert pk.firm == "Kim & Associates"
        assert pk.bar_number == "298451"


class TestBuildEmployment:
    def test_accumulates_ordered_by_start_date(self, fact_storage, case_id):
        """Employment facts accumulate as history, ordered by start_date."""
        fact_storage.add_fact(_fact(case_id, category=FactCategory.EMPLOYMENT,
                                    fact_type="position", value={
            "employer": "Acme Corp", "position": "Senior Analyst",
            "start_date": "2021-06-15", "end_date": "2025-11-15",
            "change_reason": "promoted",
        }))
        fact_storage.add_fact(_fact(case_id, category=FactCategory.EMPLOYMENT,
                                    fact_type="position", value={
            "employer": "Acme Corp", "position": "Analyst",
            "start_date": "2019-03-01", "end_date": "2021-06-15",
            "change_reason": "hired",
        }))

        ctx = CaseContextBuilder().build(case_id, "Test", fact_storage)
        assert len(ctx.employment_history) == 2
        # First entry should be the earlier start_date
        assert ctx.employment_history[0].position == "Analyst"
        assert ctx.employment_history[0].start_date == "2019-03-01"
        assert ctx.employment_history[1].position == "Senior Analyst"
        assert ctx.employment_history[1].start_date == "2021-06-15"

    def test_employment_not_deduplicated(self, fact_storage, case_id):
        """Same employer with different periods are kept separate."""
        for i in range(3):
            fact_storage.add_fact(_fact(case_id, category=FactCategory.EMPLOYMENT,
                                        fact_type="position", value={
                "employer": "Acme Corp", "position": f"Role {i}",
                "start_date": f"20{20+i}-01-01",
            }))
        ctx = CaseContextBuilder().build(case_id, "Test", fact_storage)
        assert len(ctx.employment_history) == 3


class TestBuildClaims:
    def test_builds_claims(self, fact_storage, case_id):
        fact_storage.add_fact(_fact(case_id, category=FactCategory.CLAIM,
                                    fact_type="claim", value={
            "claim_type": "feha_discrimination", "status": "active",
            "protected_class": "race",
        }))
        fact_storage.add_fact(_fact(case_id, category=FactCategory.CLAIM,
                                    fact_type="claim", value={
            "claim_type": "wage_theft", "status": "dropped",
            "reason": "Dropped in First Amended Complaint",
        }))

        ctx = CaseContextBuilder().build(case_id, "Test", fact_storage)
        assert len(ctx.claims) == 2
        assert len(ctx.active_claims) == 1
        assert ctx.active_claims[0].claim_type == "feha_discrimination"


class TestBuildDates:
    def test_dates_ordered_chronologically(self, fact_storage, case_id):
        fact_storage.add_fact(_fact(case_id, category=FactCategory.DATE,
                                    fact_type="date", value={
            "label": "Trial date", "date": "2027-03-10", "date_type": "trial",
        }))
        fact_storage.add_fact(_fact(case_id, category=FactCategory.DATE,
                                    fact_type="date", value={
            "label": "Complaint filed", "date": "2026-01-15", "date_type": "filing",
        }))

        ctx = CaseContextBuilder().build(case_id, "Test", fact_storage)
        assert len(ctx.key_dates) == 2
        assert ctx.key_dates[0].label == "Complaint filed"
        assert ctx.key_dates[1].label == "Trial date"


class TestBuildFinancials:
    def test_financials_ordered_chronologically(self, fact_storage, case_id):
        fact_storage.add_fact(_fact(case_id, category=FactCategory.FINANCIAL,
                                    fact_type="demand", value={
            "label": "Counter-offer", "amount": 125000, "date": "2026-02-15",
        }))
        fact_storage.add_fact(_fact(case_id, category=FactCategory.FINANCIAL,
                                    fact_type="demand", value={
            "label": "Initial demand", "amount": 450000, "date": "2025-12-01",
        }))
        fact_storage.add_fact(_fact(case_id, category=FactCategory.FINANCIAL,
                                    fact_type="demand", value={
            "label": "Revised demand", "amount": 350000, "date": "2026-03-01",
        }))

        ctx = CaseContextBuilder().build(case_id, "Test", fact_storage)
        assert len(ctx.financials) == 3
        assert ctx.financials[0].label == "Initial demand"
        assert ctx.financials[2].label == "Revised demand"
        assert ctx.current_demand.amount == 350000


class TestSupersedExcluded:
    def test_superseded_facts_excluded(self, fact_storage, case_id):
        """Superseded facts should not appear in the built context."""
        old = _fact(case_id, category=FactCategory.FINANCIAL,
                    fact_type="demand", value={
            "label": "Initial demand", "amount": 50000,
        })
        fact_storage.add_fact(old)

        new = _fact(case_id, category=FactCategory.FINANCIAL,
                    fact_type="demand", value={
            "label": "Initial demand", "amount": 100000,
        }, confidence=1.0, confirmed=True)
        fact_storage.supersede(old.id, new)

        ctx = CaseContextBuilder().build(case_id, "Test", fact_storage)
        assert len(ctx.financials) == 1
        assert ctx.financials[0].amount == 100000


class TestProvenance:
    def test_fact_count_and_confirmed(self, fact_storage, case_id):
        fact_storage.add_fact(_fact(case_id, confirmed=True))
        fact_storage.add_fact(_fact(case_id, fact_type="defendant", value={
            "name": "Bob", "role": "defendant", "party_type": "entity",
        }))
        fact_storage.add_fact(_fact(case_id, category=FactCategory.COURT,
                                    fact_type="court", confirmed=True, value={
            "court": "Superior Court",
        }))

        ctx = CaseContextBuilder().build(case_id, "Test", fact_storage)
        assert ctx.fact_count == 3
        assert ctx.confirmed_count == 2

    def test_extraction_sources(self, fact_storage, case_id, storage):
        now = "2026-03-15T00:00:00+00:00"
        for fid in ("f1", "f2"):
            storage._conn.execute(
                "INSERT INTO case_files (id, case_id, original_filename, file_type, mime_type, "
                "file_size_bytes, storage_path, upload_order, processing_status, text_dirty, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (fid, case_id, "doc.pdf", "pdf", "application/pdf", 1024,
                 f"data/cases/c1/{fid}.pdf", 0, "ready", 0, now, now),
            )
        storage._conn.commit()

        fact_storage.add_fact(_fact(case_id, source_file_id="f1"))
        fact_storage.add_fact(_fact(case_id, fact_type="defendant",
                                    source_file_id="f1", value={
            "name": "Bob", "role": "defendant", "party_type": "entity",
        }))
        fact_storage.add_fact(_fact(case_id, category=FactCategory.COURT,
                                    fact_type="court", source_file_id="f2", value={
            "court": "Superior Court",
        }))
        # Fact without source_file_id (manual entry)
        fact_storage.add_fact(_fact(case_id, category=FactCategory.DATE,
                                    fact_type="date", value={
            "label": "Trial", "date": "2027-01-01",
        }))

        ctx = CaseContextBuilder().build(case_id, "Test", fact_storage)
        assert "party" in ctx.extraction_sources
        assert ctx.extraction_sources["party"] == ["f1"]
        assert ctx.extraction_sources["court"] == ["f2"]
        assert "date" not in ctx.extraction_sources  # no source_file_id


class TestMixedBag:
    def test_full_case_assembly(self, fact_storage, case_id):
        """Gate check: build from a mixed bag of facts across all categories."""
        # Parties
        fact_storage.add_fact(_fact(case_id, value={
            "name": "Maria Martinez", "role": "plaintiff", "party_type": "individual",
        }))
        fact_storage.add_fact(_fact(case_id, fact_type="defendant", value={
            "name": "Acme Corp", "role": "defendant", "party_type": "entity",
        }))
        fact_storage.add_fact(_fact(case_id, fact_type="doe", value={
            "name": "Does 1-50", "role": "defendant", "party_type": "doe", "count": 50,
        }))

        # Court
        fact_storage.add_fact(_fact(case_id, category=FactCategory.COURT,
                                    fact_type="court", value={
            "court": "Superior Court of California", "county": "Los Angeles",
            "department": "7", "judge": "Hon. Sarah Chen",
        }))

        # Attorneys
        fact_storage.add_fact(_fact(case_id, category=FactCategory.ATTORNEY,
                                    fact_type="attorney", value={
            "name": "David Kim", "side": "plaintiff",
            "bar_number": "298451", "firm": "Kim & Associates",
        }))

        # Employment history (out of order, should be sorted)
        fact_storage.add_fact(_fact(case_id, category=FactCategory.EMPLOYMENT,
                                    fact_type="position", value={
            "employer": "Acme Corp", "position": "Senior Analyst",
            "compensation_rate": 95000, "compensation_type": "salary",
            "pay_period": "annual",
            "start_date": "2021-06-15", "end_date": "2025-11-15",
            "change_reason": "promoted",
        }))
        fact_storage.add_fact(_fact(case_id, category=FactCategory.EMPLOYMENT,
                                    fact_type="position", value={
            "employer": "Acme Corp", "position": "Analyst",
            "compensation_rate": 75000, "compensation_type": "salary",
            "pay_period": "annual",
            "start_date": "2019-03-01", "end_date": "2021-06-15",
            "change_reason": "hired",
        }))

        # Claims
        fact_storage.add_fact(_fact(case_id, category=FactCategory.CLAIM,
                                    fact_type="claim", value={
            "claim_type": "feha_discrimination", "status": "active",
            "protected_class": "race",
        }))
        fact_storage.add_fact(_fact(case_id, category=FactCategory.CLAIM,
                                    fact_type="claim", value={
            "claim_type": "wage_theft", "status": "dropped",
            "reason": "Dropped in FAC",
        }))

        # Dates
        fact_storage.add_fact(_fact(case_id, category=FactCategory.DATE,
                                    fact_type="date", value={
            "label": "Complaint filed", "date": "2026-01-15", "date_type": "filing",
        }))
        fact_storage.add_fact(_fact(case_id, category=FactCategory.DATE,
                                    fact_type="date", value={
            "label": "Trial date", "date": "2027-03-10", "date_type": "trial",
        }))

        # Financials
        fact_storage.add_fact(_fact(case_id, category=FactCategory.FINANCIAL,
                                    fact_type="demand", value={
            "label": "Initial demand", "amount": 450000, "date": "2025-12-01",
        }))
        fact_storage.add_fact(_fact(case_id, category=FactCategory.FINANCIAL,
                                    fact_type="demand", value={
            "label": "Counter-offer", "amount": 125000, "date": "2026-02-15",
        }))

        ctx = CaseContextBuilder().build(case_id, "Smith v. Acme Corp", fact_storage)

        # Verify all categories present
        assert len(ctx.parties) == 3
        assert ctx.plaintiff_names == ["Maria Martinez"]
        assert "Acme Corp" in ctx.defendant_names
        assert ctx.court is not None
        assert ctx.court.judge == "Hon. Sarah Chen"
        assert len(ctx.attorneys) == 1
        assert len(ctx.employment_history) == 2
        assert ctx.employment_history[0].position == "Analyst"
        assert ctx.employment_history[1].position == "Senior Analyst"
        assert len(ctx.claims) == 2
        assert len(ctx.active_claims) == 1
        assert len(ctx.key_dates) == 2
        assert ctx.key_dates[0].date == "2026-01-15"
        assert len(ctx.financials) == 2
        assert ctx.current_demand.amount == 125000  # Counter-offer is a demand label
        assert ctx.fact_count == 13
        assert ctx.confirmed_count == 0
        assert ctx.all_person_names == ["Maria Martinez", "David Kim"]
        assert "Acme Corp" in ctx.all_entity_names
        assert "Kim & Associates" in ctx.all_entity_names
