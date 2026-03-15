"""Tests for LITIGAGENTv2 case_facts + case_artifacts schema (V2.1a.2)."""

import json
import sqlite3
from pathlib import Path

import pytest

from employee_help.storage.storage import Storage


@pytest.fixture
def storage(tmp_path: Path) -> Storage:
    db_path = tmp_path / "test_facts.db"
    s = Storage(db_path=db_path)
    yield s
    s.close()


def _get_columns(storage: Storage, table: str) -> dict[str, str]:
    rows = storage._conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row["name"]: row["type"] for row in rows}


def _get_index_names(storage: Storage, table: str) -> list[str]:
    rows = storage._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=?",
        (table,),
    ).fetchall()
    return [row["name"] for row in rows]


def _table_exists(storage: Storage, table: str) -> bool:
    row = storage._conn.execute(
        "SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row[0] == 1


class TestCaseFactsSchema:
    def test_table_exists(self, storage):
        assert _table_exists(storage, "case_facts")

    def test_columns(self, storage):
        cols = _get_columns(storage, "case_facts")
        expected = {
            "id", "case_id", "category", "fact_type", "value",
            "source_file_id", "extraction_method", "confidence",
            "confirmed", "superseded_by", "effective_date", "created_at",
        }
        assert expected == set(cols.keys())

    def test_indexes(self, storage):
        indexes = _get_index_names(storage, "case_facts")
        assert "idx_case_facts_current" in indexes
        assert "idx_case_facts_source" in indexes
        assert "idx_case_facts_type" in indexes

    def test_partial_index_current(self, storage):
        """The 'current' index is a partial index on superseded_by IS NULL."""
        row = storage._conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='idx_case_facts_current'"
        ).fetchone()
        assert "WHERE superseded_by IS NULL" in row[0]

    def test_cascade_delete_on_case(self, storage):
        """Deleting a case should cascade-delete its facts."""
        now = "2026-03-15T00:00:00+00:00"
        storage._conn.execute(
            "INSERT INTO cases (id, name, user_id, organization_id, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("c1", "Test Case", "u1", "o1", "active", now, now),
        )
        storage._conn.execute(
            "INSERT INTO case_facts (id, case_id, category, fact_type, value, "
            "extraction_method, confidence, confirmed, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("f1", "c1", "party", "plaintiff", '{"name":"Alice"}', "regex", 0.9, 0, now),
        )
        storage._conn.commit()

        storage._conn.execute("DELETE FROM cases WHERE id = ?", ("c1",))
        storage._conn.commit()

        row = storage._conn.execute(
            "SELECT count(*) FROM case_facts WHERE case_id = ?", ("c1",)
        ).fetchone()
        assert row[0] == 0

    def test_source_file_set_null(self, storage):
        """Deleting a case file should SET NULL on fact's source_file_id."""
        now = "2026-03-15T00:00:00+00:00"
        storage._conn.execute(
            "INSERT INTO cases (id, name, user_id, organization_id, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("c1", "Test Case", "u1", "o1", "active", now, now),
        )
        storage._conn.execute(
            "INSERT INTO case_files (id, case_id, original_filename, file_type, mime_type, "
            "file_size_bytes, storage_path, upload_order, processing_status, text_dirty, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("file1", "c1", "doc.pdf", "pdf", "application/pdf", 1024,
             "data/cases/c1/doc.pdf", 0, "ready", 0, now, now),
        )
        storage._conn.execute(
            "INSERT INTO case_facts (id, case_id, category, fact_type, value, "
            "source_file_id, extraction_method, confidence, confirmed, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("f1", "c1", "party", "plaintiff", '{"name":"Bob"}', "file1", "llm", 0.8, 0, now),
        )
        storage._conn.commit()

        storage._conn.execute("DELETE FROM case_files WHERE id = ?", ("file1",))
        storage._conn.commit()

        fact = storage._conn.execute(
            "SELECT * FROM case_facts WHERE id = ?", ("f1",)
        ).fetchone()
        assert fact is not None
        assert fact["source_file_id"] is None

    def test_superseded_by_self_ref_set_null(self, storage):
        """Deleting a superseding fact should SET NULL on old fact's superseded_by."""
        now = "2026-03-15T00:00:00+00:00"
        storage._conn.execute(
            "INSERT INTO cases (id, name, user_id, organization_id, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("c1", "Test Case", "u1", "o1", "active", now, now),
        )
        # Insert old fact, then new fact that supersedes it
        storage._conn.execute(
            "INSERT INTO case_facts (id, case_id, category, fact_type, value, "
            "extraction_method, confidence, confirmed, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("f-new", "c1", "financial", "demand", '{"amount":100000}', "manual", 1.0, 1, now),
        )
        storage._conn.execute(
            "INSERT INTO case_facts (id, case_id, category, fact_type, value, "
            "extraction_method, confidence, confirmed, superseded_by, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("f-old", "c1", "financial", "demand", '{"amount":50000}', "regex", 0.7, 0, "f-new", now),
        )
        storage._conn.commit()

        # Delete the superseding fact
        storage._conn.execute("DELETE FROM case_facts WHERE id = ?", ("f-new",))
        storage._conn.commit()

        old = storage._conn.execute(
            "SELECT * FROM case_facts WHERE id = ?", ("f-old",)
        ).fetchone()
        assert old is not None
        assert old["superseded_by"] is None


class TestCaseArtifactsSchema:
    def test_table_exists(self, storage):
        assert _table_exists(storage, "case_artifacts")

    def test_columns(self, storage):
        cols = _get_columns(storage, "case_artifacts")
        expected = {
            "id", "case_id", "artifact_type", "tool_source",
            "summary", "file_path", "metadata", "created_at", "created_by",
        }
        assert expected == set(cols.keys())

    def test_indexes(self, storage):
        indexes = _get_index_names(storage, "case_artifacts")
        assert "idx_case_artifacts_case" in indexes
        assert "idx_case_artifacts_type" in indexes

    def test_cascade_delete_on_case(self, storage):
        """Deleting a case should cascade-delete its artifacts."""
        now = "2026-03-15T00:00:00+00:00"
        storage._conn.execute(
            "INSERT INTO cases (id, name, user_id, organization_id, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("c1", "Test Case", "u1", "o1", "active", now, now),
        )
        storage._conn.execute(
            "INSERT INTO case_artifacts (id, case_id, artifact_type, tool_source, "
            "created_at) VALUES (?, ?, ?, ?, ?)",
            ("a1", "c1", "discovery_set", "discovery/srogs", now),
        )
        storage._conn.commit()

        storage._conn.execute("DELETE FROM cases WHERE id = ?", ("c1",))
        storage._conn.commit()

        row = storage._conn.execute(
            "SELECT count(*) FROM case_artifacts WHERE case_id = ?", ("c1",)
        ).fetchone()
        assert row[0] == 0

    def test_insert_with_metadata(self, storage):
        """Artifacts can store JSON metadata."""
        now = "2026-03-15T00:00:00+00:00"
        storage._conn.execute(
            "INSERT INTO cases (id, name, user_id, organization_id, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("c1", "Test Case", "u1", "o1", "active", now, now),
        )
        meta = json.dumps({"request_count": 15, "tool": "srogs"})
        storage._conn.execute(
            "INSERT INTO case_artifacts (id, case_id, artifact_type, tool_source, "
            "summary, metadata, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("a1", "c1", "discovery_set", "discovery/srogs", "15 SROGs", meta, now),
        )
        storage._conn.commit()

        row = storage._conn.execute(
            "SELECT * FROM case_artifacts WHERE id = ?", ("a1",)
        ).fetchone()
        assert json.loads(row["metadata"])["request_count"] == 15


class TestMigration:
    def test_migration_creates_tables_on_existing_db(self, tmp_path):
        """Migrations should create the new tables on a pre-existing DB."""
        db_path = tmp_path / "migrate.db"
        # First create a DB (this runs all migrations + schema)
        s = Storage(db_path=db_path)
        assert _table_exists(s, "case_facts")
        assert _table_exists(s, "case_artifacts")
        s.close()

        # Reopen — migrations are idempotent
        s2 = Storage(db_path=db_path)
        assert _table_exists(s2, "case_facts")
        assert _table_exists(s2, "case_artifacts")
        s2.close()

    def test_existing_tables_unaffected(self, storage):
        """Fact store tables don't interfere with existing tables."""
        for table in ("cases", "case_files", "case_notes", "case_chunks",
                      "sources", "documents", "chunks", "users"):
            assert _table_exists(storage, table)

    def test_foreign_key_enforcement(self, storage):
        """Inserting a fact with non-existent case_id should fail."""
        now = "2026-03-15T00:00:00+00:00"
        with pytest.raises(sqlite3.IntegrityError):
            storage._conn.execute(
                "INSERT INTO case_facts (id, case_id, category, fact_type, value, "
                "extraction_method, confidence, confirmed, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("f1", "nonexistent", "party", "plaintiff", '{}', "regex", 0.5, 0, now),
            )
