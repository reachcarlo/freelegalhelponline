"""Tests for LITIGAGENTv2 CaseFactStorage CRUD (V2.1a.3)."""

from pathlib import Path

import pytest

from employee_help.storage.case_fact_storage import CaseFactStorage
from employee_help.storage.models import (
    CaseFact,
    ExtractionMethod,
    FactCategory,
)
from employee_help.storage.storage import Storage


@pytest.fixture
def storage(tmp_path: Path) -> Storage:
    db_path = tmp_path / "test_fact_crud.db"
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
        ("c1", "Test Case", "u1", "o1", "active", now, now),
    )
    storage._conn.commit()
    return "c1"


def _make_fact(case_id: str = "c1", **overrides) -> CaseFact:
    defaults = {
        "case_id": case_id,
        "category": FactCategory.PARTY,
        "fact_type": "plaintiff",
        "value": {"name": "Alice"},
        "extraction_method": ExtractionMethod.REGEX,
        "confidence": 0.85,
    }
    defaults.update(overrides)
    return CaseFact(**defaults)


class TestAddFact:
    def test_add_and_retrieve(self, fact_storage, case_id):
        fact = _make_fact(case_id)
        result = fact_storage.add_fact(fact)
        assert result.id == fact.id

        facts = fact_storage.list_current_facts(case_id)
        assert len(facts) == 1
        assert facts[0].id == fact.id
        assert facts[0].value == {"name": "Alice"}
        assert facts[0].category == FactCategory.PARTY
        assert facts[0].extraction_method == ExtractionMethod.REGEX
        assert facts[0].confidence == 0.85
        assert facts[0].confirmed is False
        assert facts[0].superseded_by is None

    def test_add_multiple_facts(self, fact_storage, case_id):
        f1 = _make_fact(case_id, fact_type="plaintiff")
        f2 = _make_fact(case_id, fact_type="defendant", value={"name": "Bob"})
        fact_storage.add_fact(f1)
        fact_storage.add_fact(f2)

        facts = fact_storage.list_current_facts(case_id)
        assert len(facts) == 2

    def test_add_fact_with_all_fields(self, fact_storage, case_id, storage):
        now = "2026-03-15T00:00:00+00:00"
        storage._conn.execute(
            "INSERT INTO case_files (id, case_id, original_filename, file_type, mime_type, "
            "file_size_bytes, storage_path, upload_order, processing_status, text_dirty, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("file-1", case_id, "doc.pdf", "pdf", "application/pdf", 1024,
             "data/cases/c1/doc.pdf", 0, "ready", 0, now, now),
        )
        storage._conn.commit()
        fact = _make_fact(
            case_id,
            source_file_id="file-1",
            confirmed=True,
            effective_date="2026-01-15",
        )
        fact_storage.add_fact(fact)
        retrieved = fact_storage.list_current_facts(case_id)[0]
        assert retrieved.source_file_id == "file-1"
        assert retrieved.confirmed is True
        assert retrieved.effective_date == "2026-01-15"


class TestSupersede:
    def test_supersede_sets_pointer(self, fact_storage, case_id):
        old = _make_fact(case_id, fact_type="demand", category=FactCategory.FINANCIAL,
                         value={"amount": 50000})
        fact_storage.add_fact(old)

        new = _make_fact(case_id, fact_type="demand", category=FactCategory.FINANCIAL,
                         value={"amount": 100000},
                         extraction_method=ExtractionMethod.MANUAL,
                         confidence=1.0, confirmed=True)
        fact_storage.supersede(old.id, new)

        all_facts = fact_storage.list_all_facts(case_id, category="financial")
        assert len(all_facts) == 2

        old_fact = next(f for f in all_facts if f.id == old.id)
        assert old_fact.superseded_by == new.id

        new_fact = next(f for f in all_facts if f.id == new.id)
        assert new_fact.superseded_by is None

    def test_superseded_excluded_from_current(self, fact_storage, case_id):
        old = _make_fact(case_id, value={"name": "Old"})
        fact_storage.add_fact(old)

        new = _make_fact(case_id, value={"name": "New"})
        fact_storage.supersede(old.id, new)

        current = fact_storage.list_current_facts(case_id)
        assert len(current) == 1
        assert current[0].id == new.id


class TestConfirm:
    def test_confirm_sets_flag(self, fact_storage, case_id):
        fact = _make_fact(case_id)
        fact_storage.add_fact(fact)
        assert fact_storage.list_current_facts(case_id)[0].confirmed is False

        fact_storage.confirm(fact.id)
        assert fact_storage.list_current_facts(case_id)[0].confirmed is True

    def test_confirm_idempotent(self, fact_storage, case_id):
        fact = _make_fact(case_id, confirmed=True)
        fact_storage.add_fact(fact)
        fact_storage.confirm(fact.id)
        assert fact_storage.list_current_facts(case_id)[0].confirmed is True


class TestListCurrentFacts:
    def test_filter_by_category(self, fact_storage, case_id):
        fact_storage.add_fact(_make_fact(case_id, category=FactCategory.PARTY,
                                         fact_type="plaintiff"))
        fact_storage.add_fact(_make_fact(case_id, category=FactCategory.EMPLOYMENT,
                                         fact_type="position"))
        fact_storage.add_fact(_make_fact(case_id, category=FactCategory.PARTY,
                                         fact_type="defendant"))

        party_facts = fact_storage.list_current_facts(case_id, category="party")
        assert len(party_facts) == 2
        assert all(f.category == FactCategory.PARTY for f in party_facts)

        emp_facts = fact_storage.list_current_facts(case_id, category="employment")
        assert len(emp_facts) == 1

    def test_empty_case(self, fact_storage, case_id):
        assert fact_storage.list_current_facts(case_id) == []


class TestListAllFacts:
    def test_includes_superseded(self, fact_storage, case_id):
        old = _make_fact(case_id, value={"v": 1})
        fact_storage.add_fact(old)
        new = _make_fact(case_id, value={"v": 2})
        fact_storage.supersede(old.id, new)

        all_facts = fact_storage.list_all_facts(case_id)
        assert len(all_facts) == 2

    def test_filter_by_category(self, fact_storage, case_id):
        fact_storage.add_fact(_make_fact(case_id, category=FactCategory.PARTY))
        fact_storage.add_fact(_make_fact(case_id, category=FactCategory.DATE,
                                         fact_type="filing"))

        assert len(fact_storage.list_all_facts(case_id, category="party")) == 1
        assert len(fact_storage.list_all_facts(case_id, category="date")) == 1


class TestListFactsForFile:
    def test_returns_facts_for_file(self, fact_storage, case_id, storage):
        now = "2026-03-15T00:00:00+00:00"
        storage._conn.execute(
            "INSERT INTO case_files (id, case_id, original_filename, file_type, mime_type, "
            "file_size_bytes, storage_path, upload_order, processing_status, text_dirty, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("f1", case_id, "doc.pdf", "pdf", "application/pdf", 1024,
             "data/cases/c1/doc.pdf", 0, "ready", 0, now, now),
        )
        storage._conn.commit()

        fact_storage.add_fact(_make_fact(case_id, source_file_id="f1", fact_type="plaintiff"))
        fact_storage.add_fact(_make_fact(case_id, source_file_id="f1", fact_type="defendant"))
        fact_storage.add_fact(_make_fact(case_id, source_file_id=None, fact_type="manual_note"))

        file_facts = fact_storage.list_facts_for_file("f1")
        assert len(file_facts) == 2
        assert all(f.source_file_id == "f1" for f in file_facts)

    def test_empty_for_unknown_file(self, fact_storage, case_id):
        assert fact_storage.list_facts_for_file("nonexistent") == []


class TestDeleteFactsForFile:
    def test_deletes_and_returns_count(self, fact_storage, case_id, storage):
        now = "2026-03-15T00:00:00+00:00"
        storage._conn.execute(
            "INSERT INTO case_files (id, case_id, original_filename, file_type, mime_type, "
            "file_size_bytes, storage_path, upload_order, processing_status, text_dirty, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("f1", case_id, "doc.pdf", "pdf", "application/pdf", 1024,
             "data/cases/c1/doc.pdf", 0, "ready", 0, now, now),
        )
        storage._conn.commit()

        fact_storage.add_fact(_make_fact(case_id, source_file_id="f1", fact_type="p1"))
        fact_storage.add_fact(_make_fact(case_id, source_file_id="f1", fact_type="p2"))
        fact_storage.add_fact(_make_fact(case_id, source_file_id=None, fact_type="manual"))

        deleted = fact_storage.delete_facts_for_file("f1")
        assert deleted == 2

        remaining = fact_storage.list_current_facts(case_id)
        assert len(remaining) == 1
        assert remaining[0].fact_type == "manual"

    def test_delete_nonexistent_returns_zero(self, fact_storage):
        assert fact_storage.delete_facts_for_file("nonexistent") == 0


class TestFactCount:
    def test_counts_current_and_confirmed(self, fact_storage, case_id):
        f1 = _make_fact(case_id, fact_type="p1")
        f2 = _make_fact(case_id, fact_type="p2", confirmed=True)
        f3 = _make_fact(case_id, fact_type="p3")
        fact_storage.add_fact(f1)
        fact_storage.add_fact(f2)
        fact_storage.add_fact(f3)

        total, confirmed = fact_storage.fact_count(case_id)
        assert total == 3
        assert confirmed == 1

    def test_excludes_superseded(self, fact_storage, case_id):
        old = _make_fact(case_id, fact_type="old")
        fact_storage.add_fact(old)
        new = _make_fact(case_id, fact_type="new")
        fact_storage.supersede(old.id, new)

        total, confirmed = fact_storage.fact_count(case_id)
        assert total == 1
        assert confirmed == 0

    def test_empty_case(self, fact_storage, case_id):
        total, confirmed = fact_storage.fact_count(case_id)
        assert total == 0
        assert confirmed == 0
