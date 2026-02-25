"""Tests for the SQLite storage layer."""

import tempfile
from pathlib import Path

import pytest

from employee_help.storage.models import (
    Chunk,
    ContentType,
    CrawlStatus,
    Document,
)
from employee_help.storage.storage import Storage


@pytest.fixture
def storage(tmp_path: Path) -> Storage:
    db_path = tmp_path / "test.db"
    s = Storage(db_path=db_path)
    yield s
    s.close()


@pytest.fixture
def sample_document() -> Document:
    return Document(
        source_url="https://example.com/employment",
        title="Employment Discrimination",
        content_type=ContentType.HTML,
        raw_content="<p>Test content about employment discrimination</p>",
        content_hash="abc123hash",
        crawl_run_id=1,
    )


@pytest.fixture
def sample_chunks() -> list[Chunk]:
    return [
        Chunk(
            content="California law protects individuals from discrimination.",
            content_hash="chunk_hash_1",
            chunk_index=0,
            heading_path="Employment > Protected Characteristics",
            token_count=8,
            document_id=1,
        ),
        Chunk(
            content="Employers of 5 or more employees must comply with FEHA.",
            content_hash="chunk_hash_2",
            chunk_index=1,
            heading_path="Employment > Coverage",
            token_count=11,
            document_id=1,
        ),
    ]


class TestCrawlRuns:
    def test_create_run(self, storage: Storage) -> None:
        run = storage.create_run()
        assert run.id is not None
        assert run.status == CrawlStatus.RUNNING

    def test_complete_run(self, storage: Storage) -> None:
        run = storage.create_run()
        summary = {"pages_crawled": 5, "errors": 0}
        storage.complete_run(run.id, CrawlStatus.COMPLETED, summary)

        result = storage.get_run_summary(run.id)
        assert result is not None
        assert result["status"] == "completed"
        assert result["summary"]["pages_crawled"] == 5
        assert result["completed_at"] is not None

    def test_get_latest_run(self, storage: Storage) -> None:
        storage.create_run()
        run2 = storage.create_run()

        latest = storage.get_latest_run()
        assert latest is not None
        assert latest["id"] == run2.id

    def test_get_run_summary_not_found(self, storage: Storage) -> None:
        assert storage.get_run_summary(999) is None

    def test_get_latest_run_empty(self, storage: Storage) -> None:
        assert storage.get_latest_run() is None


class TestDocuments:
    def test_insert_document(self, storage: Storage, sample_document: Document) -> None:
        storage.create_run()
        doc, is_new = storage.upsert_document(sample_document)
        assert is_new is True
        assert doc.id is not None

    def test_upsert_idempotency_same_hash(
        self, storage: Storage, sample_document: Document
    ) -> None:
        """Re-inserting a document with the same content hash should not create a new row."""
        storage.create_run()
        doc1, is_new1 = storage.upsert_document(sample_document)
        assert is_new1 is True

        doc2, is_new2 = storage.upsert_document(sample_document)
        assert is_new2 is False
        assert doc2.id == doc1.id
        assert storage.get_document_count() == 1

    def test_upsert_updates_on_changed_hash(
        self, storage: Storage, sample_document: Document
    ) -> None:
        """Re-inserting a document with a changed content hash should replace it."""
        storage.create_run()
        doc1, _ = storage.upsert_document(sample_document)
        old_id = doc1.id

        # Change the content and hash
        sample_document.raw_content = "<p>Updated content</p>"
        sample_document.content_hash = "new_hash_456"
        sample_document.id = None

        doc2, is_new = storage.upsert_document(sample_document)
        assert is_new is True
        assert doc2.id != old_id
        assert storage.get_document_count() == 1

    def test_get_document_by_url(
        self, storage: Storage, sample_document: Document
    ) -> None:
        storage.create_run()
        storage.upsert_document(sample_document)

        found = storage.get_document_by_url(sample_document.source_url)
        assert found is not None
        assert found.title == sample_document.title
        assert found.content_hash == sample_document.content_hash

    def test_get_document_by_url_not_found(self, storage: Storage) -> None:
        assert storage.get_document_by_url("https://nonexistent.com") is None

    def test_get_all_documents(
        self, storage: Storage, sample_document: Document
    ) -> None:
        storage.create_run()
        storage.upsert_document(sample_document)

        doc2 = Document(
            source_url="https://example.com/other",
            title="Other Page",
            content_type=ContentType.PDF,
            raw_content="PDF content",
            content_hash="other_hash",
            crawl_run_id=1,
        )
        storage.upsert_document(doc2)

        docs = storage.get_all_documents()
        assert len(docs) == 2


class TestChunks:
    def test_insert_and_retrieve_chunks(
        self,
        storage: Storage,
        sample_document: Document,
        sample_chunks: list[Chunk],
    ) -> None:
        storage.create_run()
        doc, _ = storage.upsert_document(sample_document)

        for c in sample_chunks:
            c.document_id = doc.id
        storage.insert_chunks(sample_chunks)

        retrieved = storage.get_chunks_for_document(doc.id)
        assert len(retrieved) == 2
        assert retrieved[0].chunk_index == 0
        assert retrieved[1].chunk_index == 1
        assert retrieved[0].heading_path == "Employment > Protected Characteristics"

    def test_chunk_count(
        self,
        storage: Storage,
        sample_document: Document,
        sample_chunks: list[Chunk],
    ) -> None:
        storage.create_run()
        doc, _ = storage.upsert_document(sample_document)
        for c in sample_chunks:
            c.document_id = doc.id
        storage.insert_chunks(sample_chunks)

        assert storage.get_chunk_count() == 2

    def test_chunks_cascade_delete_on_document_update(
        self,
        storage: Storage,
        sample_document: Document,
        sample_chunks: list[Chunk],
    ) -> None:
        """When a document is re-inserted with changed content, old chunks are deleted."""
        storage.create_run()
        doc, _ = storage.upsert_document(sample_document)
        for c in sample_chunks:
            c.document_id = doc.id
        storage.insert_chunks(sample_chunks)
        assert storage.get_chunk_count() == 2

        # Update document with new hash
        sample_document.raw_content = "New content"
        sample_document.content_hash = "updated_hash"
        sample_document.id = None
        storage.upsert_document(sample_document)

        # Old chunks should be gone
        assert storage.get_chunk_count() == 0

    def test_chunk_metadata_roundtrip(self, storage: Storage) -> None:
        storage.create_run()
        doc = Document(
            source_url="https://example.com/test",
            title="Test",
            content_type=ContentType.HTML,
            raw_content="test",
            content_hash="h1",
            crawl_run_id=1,
        )
        doc, _ = storage.upsert_document(doc)

        chunk = Chunk(
            content="Test chunk",
            content_hash="ch1",
            chunk_index=0,
            heading_path="Root",
            token_count=2,
            document_id=doc.id,
            metadata={"source_section": "FAQ", "priority": 1},
        )
        storage.insert_chunks([chunk])

        retrieved = storage.get_chunks_for_document(doc.id)
        assert retrieved[0].metadata["source_section"] == "FAQ"
        assert retrieved[0].metadata["priority"] == 1


class TestStorageLifecycle:
    def test_context_manager(self, tmp_path: Path) -> None:
        db_path = tmp_path / "ctx_test.db"
        with Storage(db_path=db_path) as s:
            run = s.create_run()
            assert run.id is not None

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        db_path = tmp_path / "nested" / "deep" / "test.db"
        with Storage(db_path=db_path) as s:
            assert db_path.parent.exists()
