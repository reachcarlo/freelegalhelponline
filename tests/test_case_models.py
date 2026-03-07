"""Tests for LITIGAGENT case domain models and SQLite schema (L1.1)."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from employee_help.storage.models import (
    Case,
    CaseChunk,
    CaseFile,
    CaseNote,
    CaseStatus,
    FileType,
    ProcessingStatus,
)
from employee_help.storage.storage import Storage


# --- Domain Model Tests ---


class TestCaseModel:
    def test_defaults(self):
        case = Case(name="Smith v. Acme Corp")
        assert case.name == "Smith v. Acme Corp"
        assert case.status == CaseStatus.ACTIVE
        assert case.description is None
        assert case.id  # UUID auto-generated
        assert len(case.id) == 36  # UUID format

    def test_auto_uuid(self):
        c1 = Case(name="Case A")
        c2 = Case(name="Case B")
        assert c1.id != c2.id

    def test_explicit_id(self):
        case = Case(name="Test", id="custom-id")
        assert case.id == "custom-id"


class TestCaseFileModel:
    def test_defaults(self):
        cf = CaseFile(
            case_id="case-1",
            original_filename="complaint.pdf",
            file_type=FileType.PDF,
            mime_type="application/pdf",
            file_size_bytes=1024,
            storage_path="data/cases/case-1/complaint.pdf",
            upload_order=0,
        )
        assert cf.processing_status == ProcessingStatus.QUEUED
        assert cf.text_dirty is False
        assert cf.extracted_text is None
        assert cf.edited_text is None
        assert cf.ocr_confidence is None
        assert cf.page_count is None
        assert cf.metadata is None
        assert cf.content_hash is None
        assert cf.id
        assert len(cf.id) == 36

    def test_all_file_types(self):
        expected = {"pdf", "docx", "xlsx", "csv", "eml", "msg", "txt", "image", "pptx"}
        assert {ft.value for ft in FileType} == expected

    def test_all_processing_statuses(self):
        expected = {"queued", "processing", "ready", "error"}
        assert {ps.value for ps in ProcessingStatus} == expected


class TestCaseNoteModel:
    def test_defaults(self):
        note = CaseNote(case_id="case-1", content="Key witness identified")
        assert note.file_id is None
        assert note.id
        assert len(note.id) == 36

    def test_file_linked_note(self):
        note = CaseNote(
            case_id="case-1",
            content="Page 3 has the smoking gun",
            file_id="file-1",
        )
        assert note.file_id == "file-1"


class TestCaseChunkModel:
    def test_defaults(self):
        chunk = CaseChunk(
            file_id="file-1",
            case_id="case-1",
            chunk_index=0,
            content="The plaintiff alleges...",
            heading_path="complaint.pdf > Page 1",
            token_count=5,
            content_hash="abc123",
        )
        assert chunk.is_active is True
        assert chunk.id
        assert len(chunk.id) == 36


# --- Schema Tests ---


@pytest.fixture
def storage(tmp_path: Path) -> Storage:
    db_path = tmp_path / "test_case.db"
    s = Storage(db_path=db_path)
    yield s
    s.close()


class TestCaseSchema:
    """Verify that the case tables are created with correct columns and constraints."""

    def _table_exists(self, storage: Storage, table: str) -> bool:
        row = storage._conn.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        return row[0] == 1

    def _get_columns(self, storage: Storage, table: str) -> dict[str, str]:
        rows = storage._conn.execute(f"PRAGMA table_info({table})").fetchall()
        return {row["name"]: row["type"] for row in rows}

    def _get_index_names(self, storage: Storage, table: str) -> list[str]:
        rows = storage._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=?",
            (table,),
        ).fetchall()
        return [row["name"] for row in rows]

    def test_cases_table_exists(self, storage):
        assert self._table_exists(storage, "cases")

    def test_case_files_table_exists(self, storage):
        assert self._table_exists(storage, "case_files")

    def test_case_notes_table_exists(self, storage):
        assert self._table_exists(storage, "case_notes")

    def test_case_chunks_table_exists(self, storage):
        assert self._table_exists(storage, "case_chunks")

    def test_cases_columns(self, storage):
        cols = self._get_columns(storage, "cases")
        assert "id" in cols
        assert "name" in cols
        assert "description" in cols
        assert "status" in cols
        assert "created_at" in cols
        assert "updated_at" in cols

    def test_case_files_columns(self, storage):
        cols = self._get_columns(storage, "case_files")
        expected = {
            "id", "case_id", "original_filename", "file_type", "mime_type",
            "file_size_bytes", "storage_path", "upload_order",
            "processing_status", "error_message", "extracted_text",
            "edited_text", "text_dirty", "ocr_confidence", "page_count",
            "metadata", "content_hash", "created_at", "updated_at",
        }
        assert expected.issubset(set(cols.keys()))

    def test_case_notes_columns(self, storage):
        cols = self._get_columns(storage, "case_notes")
        expected = {"id", "case_id", "file_id", "content", "created_at", "updated_at"}
        assert expected.issubset(set(cols.keys()))

    def test_case_chunks_columns(self, storage):
        cols = self._get_columns(storage, "case_chunks")
        expected = {
            "id", "file_id", "case_id", "chunk_index", "content",
            "heading_path", "token_count", "content_hash", "is_active",
            "created_at",
        }
        assert expected.issubset(set(cols.keys()))

    def test_case_files_indexes(self, storage):
        indexes = self._get_index_names(storage, "case_files")
        assert "idx_case_files_case_id" in indexes
        assert "idx_case_files_status" in indexes

    def test_case_notes_indexes(self, storage):
        indexes = self._get_index_names(storage, "case_notes")
        assert "idx_case_notes_case_id" in indexes
        assert "idx_case_notes_file_id" in indexes

    def test_case_chunks_indexes(self, storage):
        indexes = self._get_index_names(storage, "case_chunks")
        assert "idx_case_chunks_case_id" in indexes
        assert "idx_case_chunks_file_id" in indexes
        assert "idx_case_chunks_hash" in indexes

    def test_case_files_cascade_delete(self, storage):
        """Deleting a case should cascade-delete its files."""
        now = "2026-03-06T00:00:00+00:00"
        storage._conn.execute(
            "INSERT INTO cases (id, name, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("c1", "Test Case", "active", now, now),
        )
        storage._conn.execute(
            "INSERT INTO case_files (id, case_id, original_filename, file_type, mime_type, "
            "file_size_bytes, storage_path, upload_order, processing_status, text_dirty, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("f1", "c1", "test.pdf", "pdf", "application/pdf", 1024,
             "data/cases/c1/test.pdf", 0, "queued", 0, now, now),
        )
        storage._conn.commit()

        # Delete the case
        storage._conn.execute("DELETE FROM cases WHERE id = ?", ("c1",))
        storage._conn.commit()

        row = storage._conn.execute(
            "SELECT count(*) FROM case_files WHERE case_id = ?", ("c1",)
        ).fetchone()
        assert row[0] == 0

    def test_case_chunks_cascade_on_file_delete(self, storage):
        """Deleting a file should cascade-delete its chunks."""
        now = "2026-03-06T00:00:00+00:00"
        storage._conn.execute(
            "INSERT INTO cases (id, name, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("c1", "Test Case", "active", now, now),
        )
        storage._conn.execute(
            "INSERT INTO case_files (id, case_id, original_filename, file_type, mime_type, "
            "file_size_bytes, storage_path, upload_order, processing_status, text_dirty, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("f1", "c1", "test.pdf", "pdf", "application/pdf", 1024,
             "data/cases/c1/test.pdf", 0, "queued", 0, now, now),
        )
        storage._conn.execute(
            "INSERT INTO case_chunks (id, file_id, case_id, chunk_index, content, "
            "heading_path, token_count, content_hash, is_active, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("ch1", "f1", "c1", 0, "chunk text", "test.pdf > Page 1", 3, "hash1", 1, now),
        )
        storage._conn.commit()

        # Delete the file
        storage._conn.execute("DELETE FROM case_files WHERE id = ?", ("f1",))
        storage._conn.commit()

        row = storage._conn.execute(
            "SELECT count(*) FROM case_chunks WHERE file_id = ?", ("f1",)
        ).fetchone()
        assert row[0] == 0

    def test_case_notes_file_set_null(self, storage):
        """Deleting a file should SET NULL on notes' file_id (not cascade-delete notes)."""
        now = "2026-03-06T00:00:00+00:00"
        storage._conn.execute(
            "INSERT INTO cases (id, name, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("c1", "Test Case", "active", now, now),
        )
        storage._conn.execute(
            "INSERT INTO case_files (id, case_id, original_filename, file_type, mime_type, "
            "file_size_bytes, storage_path, upload_order, processing_status, text_dirty, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("f1", "c1", "test.pdf", "pdf", "application/pdf", 1024,
             "data/cases/c1/test.pdf", 0, "queued", 0, now, now),
        )
        storage._conn.execute(
            "INSERT INTO case_notes (id, case_id, file_id, content, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("n1", "c1", "f1", "Important note", now, now),
        )
        storage._conn.commit()

        # Delete the file
        storage._conn.execute("DELETE FROM case_files WHERE id = ?", ("f1",))
        storage._conn.commit()

        note = storage._conn.execute(
            "SELECT * FROM case_notes WHERE id = ?", ("n1",)
        ).fetchone()
        assert note is not None  # Note survives
        assert note["file_id"] is None  # file_id set to NULL

    def test_existing_tables_unaffected(self, storage):
        """Case tables don't interfere with existing knowledge-base tables."""
        for table in ("sources", "crawl_runs", "documents", "chunks", "citation_links"):
            assert self._table_exists(storage, table)

    def test_foreign_keys_enforced(self, storage):
        """Inserting a case_file with a non-existent case_id should fail."""
        now = "2026-03-06T00:00:00+00:00"
        with pytest.raises(sqlite3.IntegrityError):
            storage._conn.execute(
                "INSERT INTO case_files (id, case_id, original_filename, file_type, mime_type, "
                "file_size_bytes, storage_path, upload_order, processing_status, text_dirty, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("f1", "nonexistent", "test.pdf", "pdf", "application/pdf", 1024,
                 "data/cases/x/test.pdf", 0, "queued", 0, now, now),
            )

    def test_status_default(self, storage):
        """Cases default to 'active' status."""
        now = "2026-03-06T00:00:00+00:00"
        storage._conn.execute(
            "INSERT INTO cases (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("c1", "Test", now, now),
        )
        storage._conn.commit()
        row = storage._conn.execute("SELECT status FROM cases WHERE id = ?", ("c1",)).fetchone()
        assert row["status"] == "active"

    def test_processing_status_default(self, storage):
        """Case files default to 'queued' processing status."""
        now = "2026-03-06T00:00:00+00:00"
        storage._conn.execute(
            "INSERT INTO cases (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("c1", "Test", now, now),
        )
        storage._conn.execute(
            "INSERT INTO case_files (id, case_id, original_filename, file_type, mime_type, "
            "file_size_bytes, storage_path, upload_order, text_dirty, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("f1", "c1", "test.pdf", "pdf", "application/pdf", 1024,
             "data/cases/c1/test.pdf", 0, 0, now, now),
        )
        storage._conn.commit()
        row = storage._conn.execute(
            "SELECT processing_status FROM case_files WHERE id = ?", ("f1",)
        ).fetchone()
        assert row["processing_status"] == "queued"
