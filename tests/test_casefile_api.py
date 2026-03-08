"""Tests for LITIGAGENT case file API routes (L1.8)."""

from __future__ import annotations

import asyncio
import io
import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from employee_help.api.casefile_schemas import (
    CaseFileDetailResponse,
    CaseFileResponse,
    CaseListResponse,
    CaseResponse,
    CreateCaseRequest,
    CreateNoteRequest,
    FileUploadResponse,
    NoteListResponse,
    NoteResponse,
    UpdateCaseRequest,
    UpdateFileTextRequest,
    UpdateNoteRequest,
)
from employee_help.casefile.processing import (
    MAX_FILE_SIZE,
    broadcast_status,
    content_hash,
    get_file_type,
    get_registry,
    get_supported_extensions,
    register_sse_client,
    save_upload,
    unregister_sse_client,
)
from employee_help.storage.case_storage import CaseStorage
from employee_help.storage.models import (
    Case,
    CaseFile,
    CaseNote,
    CaseStatus,
    FileType,
    ProcessingStatus,
)
from employee_help.storage.storage import Storage


# --- Fixtures ---


@pytest.fixture()
def db():
    """Create an in-memory SQLite database with schema."""
    storage = Storage(db_path=":memory:")
    yield storage._conn
    storage.close()


@pytest.fixture()
def case_storage(db):
    """CaseStorage backed by in-memory DB."""
    return CaseStorage(conn=db)


@pytest.fixture()
def sample_case(case_storage):
    """Create and return a sample case."""
    case = Case(name="Test Case", description="A test case")
    return case_storage.create_case(case)


@pytest.fixture()
def sample_file(case_storage, sample_case, tmp_path):
    """Create and return a sample CaseFile with a real file on disk."""
    file_path = tmp_path / "test.txt"
    file_path.write_text("Hello, world!")

    cf = CaseFile(
        case_id=sample_case.id,
        original_filename="test.txt",
        file_type=FileType.TXT,
        mime_type="text/plain",
        file_size_bytes=13,
        storage_path=str(file_path),
        upload_order=0,
    )
    return case_storage.create_case_file(cf)


# --- Schema validation tests ---


class TestSchemas:
    def test_create_case_request_valid(self):
        req = CreateCaseRequest(name="My Case", description="Desc")
        assert req.name == "My Case"
        assert req.description == "Desc"

    def test_create_case_request_name_required(self):
        with pytest.raises(Exception):
            CreateCaseRequest(name="", description="Desc")

    def test_create_case_request_name_max_length(self):
        with pytest.raises(Exception):
            CreateCaseRequest(name="A" * 201)

    def test_update_case_request_optional_fields(self):
        req = UpdateCaseRequest()
        assert req.name is None
        assert req.description is None

    def test_update_file_text_max_length(self):
        with pytest.raises(Exception):
            UpdateFileTextRequest(edited_text="A" * 1_000_001)

    def test_create_note_request_valid(self):
        req = CreateNoteRequest(content="A note")
        assert req.content == "A note"
        assert req.file_id is None

    def test_create_note_request_with_file_id(self):
        req = CreateNoteRequest(content="A note", file_id="abc-123")
        assert req.file_id == "abc-123"

    def test_create_note_empty_content_rejected(self):
        with pytest.raises(Exception):
            CreateNoteRequest(content="")

    def test_update_note_request_valid(self):
        req = UpdateNoteRequest(content="Updated note")
        assert req.content == "Updated note"


# --- Processing module tests ---


class TestProcessingModule:
    def test_get_file_type_pdf(self):
        assert get_file_type("pdf") == FileType.PDF

    def test_get_file_type_docx(self):
        assert get_file_type("docx") == FileType.DOCX

    def test_get_file_type_txt(self):
        assert get_file_type("txt") == FileType.TXT

    def test_get_file_type_eml(self):
        assert get_file_type("eml") == FileType.EML

    def test_get_file_type_msg(self):
        assert get_file_type("msg") == FileType.MSG

    def test_get_file_type_mbox(self):
        assert get_file_type("mbox") == FileType.EML

    def test_get_file_type_image_extensions(self):
        for ext in ("png", "jpg", "jpeg", "tiff", "tif"):
            assert get_file_type(ext) == FileType.IMAGE

    def test_get_file_type_case_insensitive(self):
        assert get_file_type("PDF") == FileType.PDF
        assert get_file_type("Docx") == FileType.DOCX

    def test_get_file_type_unknown(self):
        assert get_file_type("xyz") is None

    def test_get_supported_extensions(self):
        exts = get_supported_extensions()
        assert "pdf" in exts
        assert "docx" in exts
        assert "txt" in exts
        assert "eml" in exts
        assert "msg" in exts
        assert "mbox" in exts
        assert "md" in exts

    def test_content_hash_deterministic(self):
        h1 = content_hash("hello")
        h2 = content_hash("hello")
        assert h1 == h2
        assert len(h1) == 64  # SHA-256

    def test_content_hash_different_inputs(self):
        h1 = content_hash("hello")
        h2 = content_hash("world")
        assert h1 != h2

    def test_get_registry_returns_registry(self):
        registry = get_registry()
        assert registry is not None
        exts = registry.registered_extensions
        assert "pdf" in exts
        assert "docx" in exts
        assert "txt" in exts
        assert "eml" in exts

    def test_get_registry_singleton(self):
        r1 = get_registry()
        r2 = get_registry()
        assert r1 is r2

    def test_save_upload(self, tmp_path):
        from employee_help.casefile import processing

        old_dir = processing.CASES_DIR
        processing.CASES_DIR = tmp_path / "cases"
        try:
            path = save_upload("case-1", "file-1", "test.txt", b"content")
            assert path.exists()
            assert path.read_bytes() == b"content"
            assert "case-1" in str(path)
            assert "file-1" in str(path)
        finally:
            processing.CASES_DIR = old_dir

    def test_save_upload_sanitizes_filename(self, tmp_path):
        from employee_help.casefile import processing

        old_dir = processing.CASES_DIR
        processing.CASES_DIR = tmp_path / "cases"
        try:
            path = save_upload("c1", "f1", "path/with/slashes.txt", b"data")
            assert "/" not in path.name.replace("cases/", "")
        finally:
            processing.CASES_DIR = old_dir

    def test_max_file_size_is_50mb(self):
        assert MAX_FILE_SIZE == 50 * 1024 * 1024


# --- SSE broadcast tests ---


class TestSSEBroadcast:
    @pytest.fixture(autouse=True)
    def _clean_queues(self):
        """Clear global SSE queues between tests."""
        from employee_help.casefile import processing

        processing._status_queues.clear()
        yield
        processing._status_queues.clear()

    def test_register_and_unregister_client(self):
        q = register_sse_client("case-1")
        assert q is not None
        unregister_sse_client("case-1", q)

    def test_register_multiple_clients(self):
        q1 = register_sse_client("case-1")
        q2 = register_sse_client("case-1")
        assert q1 is not q2
        unregister_sse_client("case-1", q1)
        unregister_sse_client("case-1", q2)

    def test_unregister_nonexistent_is_safe(self):
        q = asyncio.Queue()
        unregister_sse_client("nonexistent", q)  # Should not raise

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_client(self):
        q = register_sse_client("case-1")
        await broadcast_status("case-1", {"file_id": "f1", "status": "ready"})
        event = q.get_nowait()
        assert event["file_id"] == "f1"
        assert event["status"] == "ready"
        unregister_sse_client("case-1", q)

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_multiple_clients(self):
        q1 = register_sse_client("case-1")
        q2 = register_sse_client("case-1")
        await broadcast_status("case-1", {"file_id": "f1", "status": "processing"})
        assert q1.get_nowait()["status"] == "processing"
        assert q2.get_nowait()["status"] == "processing"
        unregister_sse_client("case-1", q1)
        unregister_sse_client("case-1", q2)

    @pytest.mark.asyncio
    async def test_broadcast_to_nonexistent_case_is_safe(self):
        await broadcast_status("nonexistent", {"status": "ready"})


# --- Case CRUD route tests ---


class TestCaseCRUDRoutes:
    def test_create_case(self, case_storage):
        case = Case(name="New Case", description="Description")
        created = case_storage.create_case(case)
        assert created.name == "New Case"
        assert created.description == "Description"
        assert created.status == CaseStatus.ACTIVE

    def test_list_cases(self, case_storage):
        case_storage.create_case(Case(name="Case 1"))
        case_storage.create_case(Case(name="Case 2"))
        cases = case_storage.list_cases()
        assert len(cases) >= 2

    def test_list_cases_filter_active(self, case_storage):
        c1 = case_storage.create_case(Case(name="Active"))
        c2 = case_storage.create_case(Case(name="Archived"))
        case_storage.archive_case(c2.id)
        active = case_storage.list_cases(status=CaseStatus.ACTIVE)
        ids = [c.id for c in active]
        assert c1.id in ids
        assert c2.id not in ids

    def test_get_case(self, case_storage, sample_case):
        fetched = case_storage.get_case(sample_case.id)
        assert fetched is not None
        assert fetched.name == sample_case.name

    def test_get_case_not_found(self, case_storage):
        assert case_storage.get_case("nonexistent") is None

    def test_update_case_name(self, case_storage, sample_case):
        updated = case_storage.update_case(sample_case.id, name="Renamed")
        assert updated is not None
        assert updated.name == "Renamed"

    def test_update_case_description(self, case_storage, sample_case):
        updated = case_storage.update_case(sample_case.id, description="New desc")
        assert updated is not None
        assert updated.description == "New desc"

    def test_archive_case(self, case_storage, sample_case):
        assert case_storage.archive_case(sample_case.id)
        fetched = case_storage.get_case(sample_case.id)
        assert fetched.status == CaseStatus.ARCHIVED

    def test_archive_nonexistent(self, case_storage):
        assert not case_storage.archive_case("nonexistent")


# --- File management route tests ---


class TestFileManagementRoutes:
    def test_create_case_file(self, case_storage, sample_case, tmp_path):
        file_path = tmp_path / "doc.pdf"
        file_path.write_bytes(b"fake pdf")
        cf = CaseFile(
            case_id=sample_case.id,
            original_filename="doc.pdf",
            file_type=FileType.PDF,
            mime_type="application/pdf",
            file_size_bytes=8,
            storage_path=str(file_path),
            upload_order=0,
        )
        created = case_storage.create_case_file(cf)
        assert created.processing_status == ProcessingStatus.QUEUED
        assert created.original_filename == "doc.pdf"

    def test_list_case_files(self, case_storage, sample_case, tmp_path):
        for i in range(3):
            fp = tmp_path / f"file{i}.txt"
            fp.write_text(f"content {i}")
            cf = CaseFile(
                case_id=sample_case.id,
                original_filename=f"file{i}.txt",
                file_type=FileType.TXT,
                mime_type="text/plain",
                file_size_bytes=9,
                storage_path=str(fp),
                upload_order=i,
            )
            case_storage.create_case_file(cf)
        files = case_storage.list_case_files(sample_case.id)
        assert len(files) == 3
        assert files[0].upload_order < files[1].upload_order

    def test_get_case_file(self, case_storage, sample_file):
        fetched = case_storage.get_case_file(sample_file.id)
        assert fetched is not None
        assert fetched.original_filename == "test.txt"

    def test_get_case_file_not_found(self, case_storage):
        assert case_storage.get_case_file("nonexistent") is None

    def test_update_file_status(self, case_storage, sample_file):
        case_storage.update_case_file_status(
            sample_file.id, ProcessingStatus.PROCESSING
        )
        fetched = case_storage.get_case_file(sample_file.id)
        assert fetched.processing_status == ProcessingStatus.PROCESSING

    def test_update_file_status_with_error(self, case_storage, sample_file):
        case_storage.update_case_file_status(
            sample_file.id,
            ProcessingStatus.ERROR,
            error_message="Extraction failed",
        )
        fetched = case_storage.get_case_file(sample_file.id)
        assert fetched.processing_status == ProcessingStatus.ERROR
        assert fetched.error_message == "Extraction failed"

    def test_update_file_text(self, case_storage, sample_file):
        updated = case_storage.update_case_file_text(
            sample_file.id,
            extracted_text="Extracted content",
            edited_text="Extracted content",
            content_hash="abc123",
        )
        assert updated is not None
        assert updated.extracted_text == "Extracted content"
        assert updated.edited_text == "Extracted content"
        assert not updated.text_dirty

    def test_update_file_text_marks_dirty(self, case_storage, sample_file):
        case_storage.update_case_file_text(
            sample_file.id,
            extracted_text="Original",
        )
        updated = case_storage.update_case_file_text(
            sample_file.id,
            edited_text="Modified",
        )
        assert updated.text_dirty is True

    def test_delete_case_file(self, case_storage, sample_file):
        assert case_storage.delete_case_file(sample_file.id)
        assert case_storage.get_case_file(sample_file.id) is None

    def test_get_next_upload_order(self, case_storage, sample_case, tmp_path):
        assert case_storage.get_next_upload_order(sample_case.id) == 0
        fp = tmp_path / "f.txt"
        fp.write_text("x")
        cf = CaseFile(
            case_id=sample_case.id,
            original_filename="f.txt",
            file_type=FileType.TXT,
            mime_type="text/plain",
            file_size_bytes=1,
            storage_path=str(fp),
            upload_order=0,
        )
        case_storage.create_case_file(cf)
        assert case_storage.get_next_upload_order(sample_case.id) == 1


# --- Note CRUD tests ---


class TestNoteCRUD:
    def test_create_note(self, case_storage, sample_case):
        note = CaseNote(case_id=sample_case.id, content="A note")
        created = case_storage.create_note(note)
        assert created.content == "A note"
        assert created.file_id is None

    def test_create_note_with_file_id(self, case_storage, sample_case, sample_file):
        note = CaseNote(
            case_id=sample_case.id,
            content="File note",
            file_id=sample_file.id,
        )
        created = case_storage.create_note(note)
        assert created.file_id == sample_file.id

    def test_list_notes(self, case_storage, sample_case):
        case_storage.create_note(
            CaseNote(case_id=sample_case.id, content="Note 1")
        )
        case_storage.create_note(
            CaseNote(case_id=sample_case.id, content="Note 2")
        )
        notes = case_storage.list_notes(sample_case.id)
        assert len(notes) == 2

    def test_list_notes_filter_by_file(
        self, case_storage, sample_case, sample_file
    ):
        case_storage.create_note(
            CaseNote(case_id=sample_case.id, content="General note")
        )
        case_storage.create_note(
            CaseNote(
                case_id=sample_case.id,
                content="File note",
                file_id=sample_file.id,
            )
        )
        file_notes = case_storage.list_notes(
            sample_case.id, file_id=sample_file.id
        )
        assert len(file_notes) == 1
        assert file_notes[0].content == "File note"

    def test_update_note(self, case_storage, sample_case):
        note = case_storage.create_note(
            CaseNote(case_id=sample_case.id, content="Original")
        )
        updated = case_storage.update_note(note.id, "Updated")
        assert updated is not None
        assert updated.content == "Updated"

    def test_update_note_not_found(self, case_storage):
        assert case_storage.update_note("nonexistent", "x") is None

    def test_delete_note(self, case_storage, sample_case):
        note = case_storage.create_note(
            CaseNote(case_id=sample_case.id, content="To delete")
        )
        assert case_storage.delete_note(note.id)
        assert case_storage.get_note(note.id) is None

    def test_delete_note_not_found(self, case_storage):
        assert not case_storage.delete_note("nonexistent")


# --- Background processing tests ---


class TestBackgroundProcessing:
    @pytest.mark.asyncio
    async def test_process_file_success(self, case_storage, sample_case, tmp_path):
        # Write a real text file
        file_path = tmp_path / "hello.txt"
        file_path.write_text("Hello, this is a test document.")

        cf = CaseFile(
            case_id=sample_case.id,
            original_filename="hello.txt",
            file_type=FileType.TXT,
            mime_type="text/plain",
            file_size_bytes=30,
            storage_path=str(file_path),
            upload_order=0,
        )
        cf = case_storage.create_case_file(cf)

        from employee_help.casefile.processing import process_file

        await process_file(case_storage, cf.id, sample_case.id)

        updated = case_storage.get_case_file(cf.id)
        assert updated.processing_status == ProcessingStatus.READY
        assert "Hello, this is a test document." in updated.extracted_text
        assert updated.edited_text == updated.extracted_text
        assert updated.content_hash is not None

    @pytest.mark.asyncio
    async def test_process_file_not_found(self, case_storage, sample_case):
        from employee_help.casefile.processing import process_file

        # Should not raise — just log error
        await process_file(case_storage, "nonexistent", sample_case.id)

    @pytest.mark.asyncio
    async def test_process_file_missing_on_disk(
        self, case_storage, sample_case, tmp_path
    ):
        file_path = tmp_path / "missing.txt"
        cf = CaseFile(
            case_id=sample_case.id,
            original_filename="missing.txt",
            file_type=FileType.TXT,
            mime_type="text/plain",
            file_size_bytes=10,
            storage_path=str(file_path),
            upload_order=0,
        )
        cf = case_storage.create_case_file(cf)

        from employee_help.casefile.processing import process_file

        await process_file(case_storage, cf.id, sample_case.id)

        updated = case_storage.get_case_file(cf.id)
        assert updated.processing_status == ProcessingStatus.ERROR
        assert "not found on disk" in updated.error_message

    @pytest.mark.asyncio
    async def test_process_file_broadcasts_status(
        self, case_storage, sample_case, tmp_path
    ):
        file_path = tmp_path / "broadcast.txt"
        file_path.write_text("Test content")

        cf = CaseFile(
            case_id=sample_case.id,
            original_filename="broadcast.txt",
            file_type=FileType.TXT,
            mime_type="text/plain",
            file_size_bytes=12,
            storage_path=str(file_path),
            upload_order=0,
        )
        cf = case_storage.create_case_file(cf)

        # Register SSE client
        q = register_sse_client(sample_case.id)

        from employee_help.casefile.processing import process_file

        await process_file(case_storage, cf.id, sample_case.id)

        # Should have received processing + ready events
        events = []
        while not q.empty():
            events.append(q.get_nowait())

        statuses = [e["status"] for e in events]
        assert "processing" in statuses
        assert "ready" in statuses

        unregister_sse_client(sample_case.id, q)

    @pytest.mark.asyncio
    async def test_process_file_error_broadcasts(
        self, case_storage, sample_case, tmp_path
    ):
        # File exists but has unsupported extension for the registry
        file_path = tmp_path / "bad.xyz"
        file_path.write_bytes(b"whatever")

        cf = CaseFile(
            case_id=sample_case.id,
            original_filename="bad.xyz",
            file_type=FileType.TXT,
            mime_type="application/octet-stream",
            file_size_bytes=8,
            storage_path=str(file_path),
            upload_order=0,
        )
        cf = case_storage.create_case_file(cf)

        q = register_sse_client(sample_case.id)

        from employee_help.casefile.processing import process_file

        await process_file(case_storage, cf.id, sample_case.id)

        events = []
        while not q.empty():
            events.append(q.get_nowait())

        error_events = [e for e in events if e.get("status") == "error"]
        assert len(error_events) >= 1

        unregister_sse_client(sample_case.id, q)


# --- Route helper tests ---


class TestRouteHelpers:
    def test_case_response_format(self, sample_case):
        from employee_help.api.casefile_routes import _case_response

        resp = _case_response(sample_case, file_count=5)
        assert resp.id == sample_case.id
        assert resp.name == sample_case.name
        assert resp.file_count == 5
        assert resp.status == "active"

    def test_file_response_format(self, sample_file):
        from employee_help.api.casefile_routes import _file_response

        resp = _file_response(sample_file)
        assert resp.id == sample_file.id
        assert resp.original_filename == "test.txt"
        assert resp.processing_status == "queued"

    def test_file_detail_response_includes_text(self, case_storage, sample_file):
        case_storage.update_case_file_text(
            sample_file.id, extracted_text="Extracted"
        )
        updated = case_storage.get_case_file(sample_file.id)

        from employee_help.api.casefile_routes import _file_detail_response

        resp = _file_detail_response(updated)
        assert resp.extracted_text == "Extracted"
        assert resp.edited_text == "Extracted"  # Auto-set by update_case_file_text

    def test_note_response_format(self, case_storage, sample_case):
        note = case_storage.create_note(
            CaseNote(case_id=sample_case.id, content="Test note")
        )
        from employee_help.api.casefile_routes import _note_response

        resp = _note_response(note)
        assert resp.id == note.id
        assert resp.content == "Test note"
        assert resp.case_id == sample_case.id


# --- Integration tests (route functions with mocked deps) ---


class TestRouteIntegration:
    @pytest.fixture()
    def mock_deps(self, case_storage):
        """Patch get_case_storage to return test case_storage."""
        with patch(
            "employee_help.api.casefile_routes._get_case_storage",
            return_value=case_storage,
        ):
            yield case_storage

    @pytest.mark.asyncio
    async def test_create_case_route(self, mock_deps):
        from employee_help.api.casefile_routes import create_case

        body = CreateCaseRequest(name="API Case", description="Via route")
        resp = await create_case(body)
        assert resp.name == "API Case"
        assert resp.status == "active"

    @pytest.mark.asyncio
    async def test_list_cases_route(self, mock_deps):
        from employee_help.api.casefile_routes import create_case, list_cases

        await create_case(CreateCaseRequest(name="Case A"))
        await create_case(CreateCaseRequest(name="Case B"))
        resp = await list_cases(status=None)
        assert len(resp.cases) >= 2

    @pytest.mark.asyncio
    async def test_get_case_route(self, mock_deps):
        from employee_help.api.casefile_routes import create_case, get_case

        created = await create_case(CreateCaseRequest(name="Get Me"))
        resp = await get_case(created.id)
        assert resp.name == "Get Me"

    @pytest.mark.asyncio
    async def test_get_case_not_found_route(self, mock_deps):
        from employee_help.api.casefile_routes import get_case

        with pytest.raises(Exception) as exc_info:
            await get_case("nonexistent")
        assert "404" in str(exc_info.value.status_code)

    @pytest.mark.asyncio
    async def test_update_case_route(self, mock_deps):
        from employee_help.api.casefile_routes import create_case, update_case

        created = await create_case(CreateCaseRequest(name="Old Name"))
        resp = await update_case(
            created.id, UpdateCaseRequest(name="New Name")
        )
        assert resp.name == "New Name"

    @pytest.mark.asyncio
    async def test_archive_case_route(self, mock_deps):
        from employee_help.api.casefile_routes import archive_case, create_case

        created = await create_case(CreateCaseRequest(name="Archive Me"))
        await archive_case(created.id)

        fetched = mock_deps.get_case(created.id)
        assert fetched.status == CaseStatus.ARCHIVED

    @pytest.mark.asyncio
    async def test_archive_case_not_found(self, mock_deps):
        from employee_help.api.casefile_routes import archive_case

        with pytest.raises(Exception) as exc_info:
            await archive_case("nonexistent")
        assert "404" in str(exc_info.value.status_code)

    @pytest.mark.asyncio
    async def test_list_files_route(self, mock_deps, sample_case, tmp_path):
        from employee_help.api.casefile_routes import list_files

        # Create a file
        fp = tmp_path / "test.txt"
        fp.write_text("x")
        cf = CaseFile(
            case_id=sample_case.id,
            original_filename="test.txt",
            file_type=FileType.TXT,
            mime_type="text/plain",
            file_size_bytes=1,
            storage_path=str(fp),
            upload_order=0,
        )
        mock_deps.create_case_file(cf)

        resp = await list_files(sample_case.id)
        assert len(resp) == 1
        assert resp[0].original_filename == "test.txt"

    @pytest.mark.asyncio
    async def test_get_file_route(self, mock_deps, sample_case, sample_file):
        from employee_help.api.casefile_routes import get_file

        resp = await get_file(sample_case.id, sample_file.id)
        assert resp.original_filename == "test.txt"

    @pytest.mark.asyncio
    async def test_get_file_not_found(self, mock_deps, sample_case):
        from employee_help.api.casefile_routes import get_file

        with pytest.raises(Exception) as exc_info:
            await get_file(sample_case.id, "nonexistent")
        assert "404" in str(exc_info.value.status_code)

    @pytest.mark.asyncio
    async def test_get_file_wrong_case(self, mock_deps, sample_file):
        from employee_help.api.casefile_routes import get_file

        other_case = mock_deps.create_case(Case(name="Other"))
        with pytest.raises(Exception) as exc_info:
            await get_file(other_case.id, sample_file.id)
        assert "404" in str(exc_info.value.status_code)

    @pytest.mark.asyncio
    async def test_update_file_text_route(
        self, mock_deps, sample_case, sample_file
    ):
        from employee_help.api.casefile_routes import update_file_text

        # First set extracted text so there's something to compare
        mock_deps.update_case_file_text(
            sample_file.id, extracted_text="Original"
        )

        body = UpdateFileTextRequest(edited_text="Edited content")
        resp = await update_file_text(sample_case.id, sample_file.id, body)
        assert resp.edited_text == "Edited content"
        assert resp.text_dirty is True

    @pytest.mark.asyncio
    async def test_delete_file_route(
        self, mock_deps, sample_case, sample_file
    ):
        from employee_help.api.casefile_routes import delete_file

        await delete_file(sample_case.id, sample_file.id)
        assert mock_deps.get_case_file(sample_file.id) is None

    @pytest.mark.asyncio
    async def test_delete_file_not_found(self, mock_deps, sample_case):
        from employee_help.api.casefile_routes import delete_file

        with pytest.raises(Exception) as exc_info:
            await delete_file(sample_case.id, "nonexistent")
        assert "404" in str(exc_info.value.status_code)

    @pytest.mark.asyncio
    async def test_reprocess_file_route(
        self, mock_deps, sample_case, sample_file
    ):
        from employee_help.api.casefile_routes import reprocess_file

        resp = await reprocess_file(sample_case.id, sample_file.id)
        assert resp.processing_status == "queued"

        # Wait briefly for background task
        await asyncio.sleep(0.1)

    @pytest.mark.asyncio
    async def test_create_note_route(self, mock_deps, sample_case):
        from employee_help.api.casefile_routes import create_note

        body = CreateNoteRequest(content="A note via route")
        resp = await create_note(sample_case.id, body)
        assert resp.content == "A note via route"
        assert resp.case_id == sample_case.id

    @pytest.mark.asyncio
    async def test_create_note_with_file(
        self, mock_deps, sample_case, sample_file
    ):
        from employee_help.api.casefile_routes import create_note

        body = CreateNoteRequest(
            content="File note", file_id=sample_file.id
        )
        resp = await create_note(sample_case.id, body)
        assert resp.file_id == sample_file.id

    @pytest.mark.asyncio
    async def test_create_note_invalid_file(self, mock_deps, sample_case):
        from employee_help.api.casefile_routes import create_note

        body = CreateNoteRequest(content="Bad file", file_id="nonexistent")
        with pytest.raises(Exception) as exc_info:
            await create_note(sample_case.id, body)
        assert "404" in str(exc_info.value.status_code)

    @pytest.mark.asyncio
    async def test_list_notes_route(self, mock_deps, sample_case):
        from employee_help.api.casefile_routes import create_note, list_notes

        await create_note(
            sample_case.id, CreateNoteRequest(content="Note 1")
        )
        await create_note(
            sample_case.id, CreateNoteRequest(content="Note 2")
        )
        resp = await list_notes(sample_case.id, file_id=None)
        assert len(resp.notes) == 2

    @pytest.mark.asyncio
    async def test_update_note_route(self, mock_deps, sample_case):
        from employee_help.api.casefile_routes import create_note, update_note

        created = await create_note(
            sample_case.id, CreateNoteRequest(content="Original")
        )
        resp = await update_note(
            sample_case.id,
            created.id,
            UpdateNoteRequest(content="Updated"),
        )
        assert resp.content == "Updated"

    @pytest.mark.asyncio
    async def test_update_note_not_found(self, mock_deps, sample_case):
        from employee_help.api.casefile_routes import update_note

        with pytest.raises(Exception) as exc_info:
            await update_note(
                sample_case.id,
                "nonexistent",
                UpdateNoteRequest(content="x"),
            )
        assert "404" in str(exc_info.value.status_code)

    @pytest.mark.asyncio
    async def test_delete_note_route(self, mock_deps, sample_case):
        from employee_help.api.casefile_routes import create_note, delete_note

        created = await create_note(
            sample_case.id, CreateNoteRequest(content="Delete me")
        )
        await delete_note(sample_case.id, created.id)
        assert mock_deps.get_note(created.id) is None

    @pytest.mark.asyncio
    async def test_delete_note_not_found(self, mock_deps, sample_case):
        from employee_help.api.casefile_routes import delete_note

        with pytest.raises(Exception) as exc_info:
            await delete_note(sample_case.id, "nonexistent")
        assert "404" in str(exc_info.value.status_code)

    @pytest.mark.asyncio
    async def test_download_file_not_found(self, mock_deps, sample_case):
        from employee_help.api.casefile_routes import download_file

        with pytest.raises(Exception) as exc_info:
            await download_file(sample_case.id, "nonexistent")
        assert "404" in str(exc_info.value.status_code)

    @pytest.mark.asyncio
    async def test_list_cases_filter_status(self, mock_deps):
        from employee_help.api.casefile_routes import create_case, list_cases

        c = await create_case(CreateCaseRequest(name="Filter Case"))
        mock_deps.archive_case(c.id)

        resp = await list_cases(status="archived")
        ids = [r.id for r in resp.cases]
        assert c.id in ids

    @pytest.mark.asyncio
    async def test_list_cases_invalid_status(self, mock_deps):
        from employee_help.api.casefile_routes import list_cases

        with pytest.raises(Exception) as exc_info:
            await list_cases(status="invalid_status")
        assert "400" in str(exc_info.value.status_code)
