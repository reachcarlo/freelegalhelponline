"""Tests for the automated content refresh CLI command and change detection."""

import hashlib

import pytest

from employee_help.storage.models import (
    Chunk,
    ContentCategory,
    ContentType,
    Document,
    Source,
    SourceType,
    UpsertStatus,
)
from employee_help.storage.storage import Storage


@pytest.fixture
def storage():
    s = Storage(":memory:")
    yield s
    s.close()


@pytest.fixture
def source(storage):
    src = Source(
        name="Test Source",
        slug="test",
        source_type=SourceType.AGENCY,
        base_url="https://example.com",
    )
    storage.create_source(src)
    return src


def _make_doc_and_chunks(storage, source, url, content, run_id):
    """Store a document and its chunks, returning (document, chunks_stored)."""
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    doc = Document(
        source_url=url,
        title="Test",
        content_type=ContentType.HTML,
        raw_content=content,
        content_hash=content_hash,
        language="en",
        crawl_run_id=run_id,
        source_id=source.id,
        content_category=ContentCategory.AGENCY_GUIDANCE,
    )
    stored, status = storage.upsert_document(doc)

    if status != UpsertStatus.UNCHANGED and stored.id:
        chunk = Chunk(
            content=content,
            content_hash=content_hash,
            chunk_index=0,
            heading_path="Test",
            token_count=len(content) // 4,
            document_id=stored.id,
            content_category=ContentCategory.AGENCY_GUIDANCE,
        )
        storage.insert_chunks([chunk])
        return stored, 1

    return stored, 0


class TestChangeDetection:
    def test_unchanged_content_skipped(self, storage, source):
        """Re-inserting unchanged content creates 0 new documents."""
        run1 = storage.create_run(source_id=source.id)
        _make_doc_and_chunks(storage, source, "https://example.com/page1", "Content A.", run1.id)

        doc_count_before = storage.get_document_count(source_id=source.id)
        chunk_count_before = storage.get_chunk_count(source_id=source.id)

        # Re-ingest same content
        run2 = storage.create_run(source_id=source.id)
        _, chunks_stored = _make_doc_and_chunks(
            storage, source, "https://example.com/page1", "Content A.", run2.id
        )

        doc_count_after = storage.get_document_count(source_id=source.id)
        chunk_count_after = storage.get_chunk_count(source_id=source.id)

        assert chunks_stored == 0  # upsert returned existing, no new chunks
        assert doc_count_after == doc_count_before
        assert chunk_count_after == chunk_count_before

    def test_changed_content_updated(self, storage, source):
        """Re-inserting changed content replaces the old document."""
        run1 = storage.create_run(source_id=source.id)
        _make_doc_and_chunks(
            storage, source, "https://example.com/page1", "Original content.", run1.id
        )

        doc_count_before = storage.get_document_count(source_id=source.id)

        # Re-ingest with changed content
        run2 = storage.create_run(source_id=source.id)
        stored, chunks_stored = _make_doc_and_chunks(
            storage, source, "https://example.com/page1", "Updated content.", run2.id
        )

        doc_count_after = storage.get_document_count(source_id=source.id)

        assert chunks_stored == 1  # New content, new chunks
        assert doc_count_after == doc_count_before  # Old was replaced, count stays same

    def test_new_document_added(self, storage, source):
        """New URLs create new documents."""
        run1 = storage.create_run(source_id=source.id)
        _make_doc_and_chunks(storage, source, "https://example.com/page1", "Page 1.", run1.id)

        doc_count_before = storage.get_document_count(source_id=source.id)

        run2 = storage.create_run(source_id=source.id)
        _make_doc_and_chunks(storage, source, "https://example.com/page2", "Page 2.", run2.id)

        doc_count_after = storage.get_document_count(source_id=source.id)
        assert doc_count_after == doc_count_before + 1

    def test_idempotent_refresh_no_changes(self, storage, source):
        """Two consecutive refreshes with same content produce identical counts."""
        run1 = storage.create_run(source_id=source.id)
        _make_doc_and_chunks(storage, source, "https://example.com/a", "A.", run1.id)
        _make_doc_and_chunks(storage, source, "https://example.com/b", "B.", run1.id)
        _make_doc_and_chunks(storage, source, "https://example.com/c", "C.", run1.id)

        counts_1 = (
            storage.get_document_count(source_id=source.id),
            storage.get_chunk_count(source_id=source.id),
        )

        # "Refresh" with same content
        run2 = storage.create_run(source_id=source.id)
        _make_doc_and_chunks(storage, source, "https://example.com/a", "A.", run2.id)
        _make_doc_and_chunks(storage, source, "https://example.com/b", "B.", run2.id)
        _make_doc_and_chunks(storage, source, "https://example.com/c", "C.", run2.id)

        counts_2 = (
            storage.get_document_count(source_id=source.id),
            storage.get_chunk_count(source_id=source.id),
        )

        assert counts_1 == counts_2

    def test_partial_change_updates_only_changed(self, storage, source):
        """Only changed documents get new chunks; unchanged ones are kept."""
        run1 = storage.create_run(source_id=source.id)
        _make_doc_and_chunks(storage, source, "https://example.com/a", "Unchanged.", run1.id)
        _make_doc_and_chunks(storage, source, "https://example.com/b", "Will change.", run1.id)

        chunk_count_before = storage.get_chunk_count(source_id=source.id)

        # Refresh: a unchanged, b changed
        run2 = storage.create_run(source_id=source.id)
        _, a_new = _make_doc_and_chunks(
            storage, source, "https://example.com/a", "Unchanged.", run2.id
        )
        _, b_new = _make_doc_and_chunks(
            storage, source, "https://example.com/b", "New content for B.", run2.id
        )

        assert a_new == 0  # Unchanged
        assert b_new == 1  # Changed

    def test_multiple_refreshes_converge(self, storage, source):
        """After initial ingest, repeated refreshes don't grow storage."""
        run1 = storage.create_run(source_id=source.id)
        for i in range(5):
            _make_doc_and_chunks(
                storage, source, f"https://example.com/{i}", f"Content {i}.", run1.id
            )

        baseline_docs = storage.get_document_count(source_id=source.id)
        baseline_chunks = storage.get_chunk_count(source_id=source.id)

        # Run three refreshes
        for refresh_num in range(3):
            run = storage.create_run(source_id=source.id)
            for i in range(5):
                _make_doc_and_chunks(
                    storage, source, f"https://example.com/{i}", f"Content {i}.", run.id
                )

        final_docs = storage.get_document_count(source_id=source.id)
        final_chunks = storage.get_chunk_count(source_id=source.id)

        assert final_docs == baseline_docs
        assert final_chunks == baseline_chunks
