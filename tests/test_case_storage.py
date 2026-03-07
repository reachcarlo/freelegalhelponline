"""Tests for CaseStorage CRUD operations (L1.2)."""

from pathlib import Path

import pytest

from employee_help.storage.case_storage import CaseStorage
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


@pytest.fixture
def storage(tmp_path: Path) -> Storage:
    db_path = tmp_path / "test.db"
    s = Storage(db_path=db_path)
    yield s
    s.close()


@pytest.fixture
def case_storage(storage: Storage) -> CaseStorage:
    return CaseStorage(conn=storage._conn)


@pytest.fixture
def sample_case() -> Case:
    return Case(name="Smith v. Acme Corp", description="Wrongful termination claim")


@pytest.fixture
def saved_case(case_storage: CaseStorage, sample_case: Case) -> Case:
    return case_storage.create_case(sample_case)


@pytest.fixture
def sample_file(saved_case: Case) -> CaseFile:
    return CaseFile(
        case_id=saved_case.id,
        original_filename="complaint.pdf",
        file_type=FileType.PDF,
        mime_type="application/pdf",
        file_size_bytes=2048,
        storage_path=f"data/cases/{saved_case.id}/complaint.pdf",
        upload_order=0,
    )


@pytest.fixture
def saved_file(case_storage: CaseStorage, sample_file: CaseFile) -> CaseFile:
    return case_storage.create_case_file(sample_file)


# ── Case CRUD ──────────────────────────────────────────────


class TestCaseCRUD:
    def test_create_case(self, case_storage, sample_case):
        case = case_storage.create_case(sample_case)
        assert case.id
        assert case.name == "Smith v. Acme Corp"
        assert case.status == CaseStatus.ACTIVE
        assert case.created_at is not None

    def test_get_case(self, case_storage, saved_case):
        fetched = case_storage.get_case(saved_case.id)
        assert fetched is not None
        assert fetched.id == saved_case.id
        assert fetched.name == saved_case.name
        assert fetched.description == saved_case.description

    def test_get_case_not_found(self, case_storage):
        assert case_storage.get_case("nonexistent") is None

    def test_list_cases(self, case_storage):
        case_storage.create_case(Case(name="Case A"))
        case_storage.create_case(Case(name="Case B"))
        cases = case_storage.list_cases()
        assert len(cases) == 2

    def test_list_cases_filter_status(self, case_storage):
        c1 = case_storage.create_case(Case(name="Active Case"))
        case_storage.create_case(Case(name="Another Active"))
        case_storage.archive_case(c1.id)
        active = case_storage.list_cases(status=CaseStatus.ACTIVE)
        archived = case_storage.list_cases(status=CaseStatus.ARCHIVED)
        assert len(active) == 1
        assert len(archived) == 1

    def test_update_case_name(self, case_storage, saved_case):
        updated = case_storage.update_case(saved_case.id, name="Jones v. Acme Corp")
        assert updated is not None
        assert updated.name == "Jones v. Acme Corp"
        assert updated.description == saved_case.description
        refetched = case_storage.get_case(saved_case.id)
        assert refetched.name == "Jones v. Acme Corp"

    def test_update_case_description(self, case_storage, saved_case):
        updated = case_storage.update_case(saved_case.id, description="Updated desc")
        assert updated.description == "Updated desc"

    def test_update_case_clear_description(self, case_storage, saved_case):
        updated = case_storage.update_case(saved_case.id, description=None)
        assert updated.description is None

    def test_update_case_not_found(self, case_storage):
        assert case_storage.update_case("nonexistent", name="X") is None

    def test_archive_case(self, case_storage, saved_case):
        assert case_storage.archive_case(saved_case.id) is True
        fetched = case_storage.get_case(saved_case.id)
        assert fetched.status == CaseStatus.ARCHIVED

    def test_archive_nonexistent(self, case_storage):
        assert case_storage.archive_case("nonexistent") is False

    def test_delete_case(self, case_storage, saved_case):
        assert case_storage.delete_case(saved_case.id) is True
        assert case_storage.get_case(saved_case.id) is None

    def test_delete_nonexistent(self, case_storage):
        assert case_storage.delete_case("nonexistent") is False


# ── Case File CRUD ─────────────────────────────────────────


class TestCaseFileCRUD:
    def test_create_case_file(self, case_storage, sample_file):
        cf = case_storage.create_case_file(sample_file)
        assert cf.id
        assert cf.original_filename == "complaint.pdf"
        assert cf.processing_status == ProcessingStatus.QUEUED
        assert cf.text_dirty is False

    def test_get_case_file(self, case_storage, saved_file):
        fetched = case_storage.get_case_file(saved_file.id)
        assert fetched is not None
        assert fetched.original_filename == "complaint.pdf"
        assert fetched.file_type == FileType.PDF

    def test_get_case_file_not_found(self, case_storage):
        assert case_storage.get_case_file("nonexistent") is None

    def test_list_case_files(self, case_storage, saved_case):
        for i, name in enumerate(["a.pdf", "b.docx", "c.txt"]):
            ft = FileType.PDF if name.endswith(".pdf") else (
                FileType.DOCX if name.endswith(".docx") else FileType.TXT
            )
            case_storage.create_case_file(CaseFile(
                case_id=saved_case.id,
                original_filename=name,
                file_type=ft,
                mime_type="application/octet-stream",
                file_size_bytes=100,
                storage_path=f"data/cases/{saved_case.id}/{name}",
                upload_order=i,
            ))
        files = case_storage.list_case_files(saved_case.id)
        assert len(files) == 3
        assert files[0].original_filename == "a.pdf"
        assert files[2].original_filename == "c.txt"

    def test_update_case_file_status(self, case_storage, saved_file):
        case_storage.update_case_file_status(
            saved_file.id, ProcessingStatus.PROCESSING
        )
        fetched = case_storage.get_case_file(saved_file.id)
        assert fetched.processing_status == ProcessingStatus.PROCESSING

    def test_update_case_file_status_error(self, case_storage, saved_file):
        case_storage.update_case_file_status(
            saved_file.id, ProcessingStatus.ERROR, error_message="Corrupted PDF"
        )
        fetched = case_storage.get_case_file(saved_file.id)
        assert fetched.processing_status == ProcessingStatus.ERROR
        assert fetched.error_message == "Corrupted PDF"

    def test_update_case_file_text_extraction(self, case_storage, saved_file):
        updated = case_storage.update_case_file_text(
            saved_file.id,
            extracted_text="The plaintiff alleges...",
            page_count=5,
            content_hash="sha256abc",
        )
        assert updated is not None
        assert updated.extracted_text == "The plaintiff alleges..."
        assert updated.edited_text == "The plaintiff alleges..."  # auto-copied
        assert updated.text_dirty is False
        assert updated.page_count == 5
        assert updated.content_hash == "sha256abc"

    def test_update_case_file_edited_text_sets_dirty(self, case_storage, saved_file):
        case_storage.update_case_file_text(
            saved_file.id, extracted_text="Original text"
        )
        updated = case_storage.update_case_file_text(
            saved_file.id, edited_text="Attorney-edited text"
        )
        assert updated.text_dirty is True
        assert updated.extracted_text == "Original text"
        assert updated.edited_text == "Attorney-edited text"

    def test_update_case_file_text_not_found(self, case_storage):
        assert case_storage.update_case_file_text("nonexistent", extracted_text="x") is None

    def test_delete_case_file(self, case_storage, saved_file):
        assert case_storage.delete_case_file(saved_file.id) is True
        assert case_storage.get_case_file(saved_file.id) is None

    def test_get_next_upload_order_empty(self, case_storage, saved_case):
        assert case_storage.get_next_upload_order(saved_case.id) == 0

    def test_get_next_upload_order_increments(self, case_storage, saved_file):
        next_order = case_storage.get_next_upload_order(saved_file.case_id)
        assert next_order == 1

    def test_file_metadata_roundtrip(self, case_storage, saved_case):
        cf = CaseFile(
            case_id=saved_case.id,
            original_filename="email.eml",
            file_type=FileType.EML,
            mime_type="message/rfc822",
            file_size_bytes=5000,
            storage_path="data/cases/x/email.eml",
            upload_order=0,
            metadata={"from": "boss@acme.com", "subject": "Your termination"},
        )
        saved = case_storage.create_case_file(cf)
        fetched = case_storage.get_case_file(saved.id)
        assert fetched.metadata == {"from": "boss@acme.com", "subject": "Your termination"}


# ── Case Note CRUD ─────────────────────────────────────────


class TestCaseNoteCRUD:
    def test_create_note(self, case_storage, saved_case):
        note = case_storage.create_note(
            CaseNote(case_id=saved_case.id, content="Key witness: Jane Doe")
        )
        assert note.id
        assert note.content == "Key witness: Jane Doe"
        assert note.file_id is None

    def test_create_file_linked_note(self, case_storage, saved_file):
        note = case_storage.create_note(
            CaseNote(
                case_id=saved_file.case_id,
                content="Page 3 is critical",
                file_id=saved_file.id,
            )
        )
        assert note.file_id == saved_file.id

    def test_get_note(self, case_storage, saved_case):
        created = case_storage.create_note(
            CaseNote(case_id=saved_case.id, content="Test note")
        )
        fetched = case_storage.get_note(created.id)
        assert fetched is not None
        assert fetched.content == "Test note"

    def test_get_note_not_found(self, case_storage):
        assert case_storage.get_note("nonexistent") is None

    def test_list_notes(self, case_storage, saved_case):
        case_storage.create_note(CaseNote(case_id=saved_case.id, content="Note 1"))
        case_storage.create_note(CaseNote(case_id=saved_case.id, content="Note 2"))
        notes = case_storage.list_notes(saved_case.id)
        assert len(notes) == 2

    def test_list_notes_filter_by_file(self, case_storage, saved_file):
        # Case-level note
        case_storage.create_note(
            CaseNote(case_id=saved_file.case_id, content="General note")
        )
        # File-linked note
        case_storage.create_note(
            CaseNote(
                case_id=saved_file.case_id,
                content="File note",
                file_id=saved_file.id,
            )
        )
        all_notes = case_storage.list_notes(saved_file.case_id)
        file_notes = case_storage.list_notes(saved_file.case_id, file_id=saved_file.id)
        assert len(all_notes) == 2
        assert len(file_notes) == 1
        assert file_notes[0].content == "File note"

    def test_update_note(self, case_storage, saved_case):
        note = case_storage.create_note(
            CaseNote(case_id=saved_case.id, content="Original")
        )
        updated = case_storage.update_note(note.id, "Revised content")
        assert updated is not None
        assert updated.content == "Revised content"
        refetched = case_storage.get_note(note.id)
        assert refetched.content == "Revised content"

    def test_update_note_not_found(self, case_storage):
        assert case_storage.update_note("nonexistent", "x") is None

    def test_delete_note(self, case_storage, saved_case):
        note = case_storage.create_note(
            CaseNote(case_id=saved_case.id, content="To delete")
        )
        assert case_storage.delete_note(note.id) is True
        assert case_storage.get_note(note.id) is None

    def test_delete_note_not_found(self, case_storage):
        assert case_storage.delete_note("nonexistent") is False


# ── Case Chunk CRUD ────────────────────────────────────────


class TestCaseChunkCRUD:
    def test_insert_and_get_chunks(self, case_storage, saved_file):
        chunks = [
            CaseChunk(
                file_id=saved_file.id,
                case_id=saved_file.case_id,
                chunk_index=i,
                content=f"Chunk {i} content",
                heading_path=f"complaint.pdf > Page {i + 1}",
                token_count=5,
                content_hash=f"hash_{i}",
            )
            for i in range(3)
        ]
        case_storage.insert_case_chunks(chunks)
        fetched = case_storage.get_case_chunks(file_id=saved_file.id)
        assert len(fetched) == 3
        assert fetched[0].chunk_index == 0
        assert fetched[2].content == "Chunk 2 content"

    def test_get_chunks_by_case(self, case_storage, saved_file):
        case_storage.insert_case_chunks([
            CaseChunk(
                file_id=saved_file.id,
                case_id=saved_file.case_id,
                chunk_index=0,
                content="Case-level chunk",
                heading_path="complaint.pdf > Page 1",
                token_count=3,
                content_hash="h1",
            )
        ])
        fetched = case_storage.get_case_chunks(case_id=saved_file.case_id)
        assert len(fetched) == 1

    def test_delete_chunks_for_file(self, case_storage, saved_file):
        case_storage.insert_case_chunks([
            CaseChunk(
                file_id=saved_file.id,
                case_id=saved_file.case_id,
                chunk_index=0,
                content="To be deleted",
                heading_path="test",
                token_count=3,
                content_hash="hd",
            )
        ])
        deleted = case_storage.delete_case_chunks_for_file(saved_file.id)
        assert deleted == 1
        assert case_storage.get_case_chunks(file_id=saved_file.id) == []

    def test_get_case_chunk_count(self, case_storage, saved_file):
        case_storage.insert_case_chunks([
            CaseChunk(
                file_id=saved_file.id,
                case_id=saved_file.case_id,
                chunk_index=i,
                content=f"C{i}",
                heading_path="test",
                token_count=1,
                content_hash=f"hc{i}",
            )
            for i in range(5)
        ])
        assert case_storage.get_case_chunk_count(saved_file.case_id) == 5


# ── Integration / Cross-Entity ─────────────────────────────


class TestCaseStorageIntegration:
    def test_cascade_delete_case_removes_files_and_chunks(
        self, case_storage, saved_file
    ):
        case_storage.insert_case_chunks([
            CaseChunk(
                file_id=saved_file.id,
                case_id=saved_file.case_id,
                chunk_index=0,
                content="chunk",
                heading_path="test",
                token_count=1,
                content_hash="hx",
            )
        ])
        case_storage.create_note(
            CaseNote(case_id=saved_file.case_id, content="note")
        )
        case_storage.delete_case(saved_file.case_id)
        assert case_storage.list_case_files(saved_file.case_id) == []
        assert case_storage.get_case_chunks(case_id=saved_file.case_id) == []
        assert case_storage.list_notes(saved_file.case_id) == []

    def test_delete_file_preserves_notes_with_null_file_id(
        self, case_storage, saved_file
    ):
        note = case_storage.create_note(
            CaseNote(
                case_id=saved_file.case_id,
                content="Linked note",
                file_id=saved_file.id,
            )
        )
        case_storage.delete_case_file(saved_file.id)
        refetched = case_storage.get_note(note.id)
        assert refetched is not None
        assert refetched.file_id is None

    def test_case_isolation(self, case_storage):
        c1 = case_storage.create_case(Case(name="Case 1"))
        c2 = case_storage.create_case(Case(name="Case 2"))

        f1 = case_storage.create_case_file(CaseFile(
            case_id=c1.id, original_filename="a.pdf", file_type=FileType.PDF,
            mime_type="application/pdf", file_size_bytes=100,
            storage_path="p1", upload_order=0,
        ))
        f2 = case_storage.create_case_file(CaseFile(
            case_id=c2.id, original_filename="b.pdf", file_type=FileType.PDF,
            mime_type="application/pdf", file_size_bytes=100,
            storage_path="p2", upload_order=0,
        ))

        assert len(case_storage.list_case_files(c1.id)) == 1
        assert len(case_storage.list_case_files(c2.id)) == 1
        assert case_storage.list_case_files(c1.id)[0].original_filename == "a.pdf"

    def test_conn_sharing_with_storage(self, storage, case_storage):
        """CaseStorage and Storage share the same connection without conflict."""
        # Knowledge-base operations still work
        from employee_help.storage.models import Source, SourceType

        src = storage.create_source(Source(
            name="Test", slug="test-src",
            source_type=SourceType.AGENCY, base_url="https://example.com",
        ))
        assert src.id is not None

        # Case operations work on the same DB
        case = case_storage.create_case(Case(name="Test Case"))
        assert case_storage.get_case(case.id) is not None

    def test_own_connection_mode(self, tmp_path):
        """CaseStorage can create its own connection from db_path."""
        db = tmp_path / "own.db"
        # First create schema via Storage
        s = Storage(db_path=db)
        s.close()
        # Now use CaseStorage independently
        with CaseStorage(db_path=db) as cs:
            case = cs.create_case(Case(name="Independent"))
            assert cs.get_case(case.id).name == "Independent"
