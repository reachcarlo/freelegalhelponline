"""Tests for cross-source duplicate detection."""

import pytest

from employee_help.storage.models import (
    Chunk,
    ContentCategory,
    ContentType,
    Document,
    Source,
    SourceType,
)
from employee_help.storage.storage import Storage


@pytest.fixture
def storage():
    s = Storage(":memory:")
    yield s
    s.close()


@pytest.fixture
def agency_source(storage):
    src = Source(
        name="CRD",
        slug="crd",
        source_type=SourceType.AGENCY,
        base_url="https://calcivilrights.ca.gov",
    )
    storage.create_source(src)
    return src


@pytest.fixture
def statutory_source(storage):
    src = Source(
        name="Labor Code",
        slug="labor_code",
        source_type=SourceType.STATUTORY_CODE,
        base_url="https://leginfo.legislature.ca.gov",
    )
    storage.create_source(src)
    return src


@pytest.fixture
def second_agency(storage):
    src = Source(
        name="DIR",
        slug="dir",
        source_type=SourceType.AGENCY,
        base_url="https://dir.ca.gov",
    )
    storage.create_source(src)
    return src


_store_counter = 0


def _store_chunk(storage, source, content, citation=None, category=ContentCategory.AGENCY_GUIDANCE):
    """Helper to store a document + chunk with given content.

    Each call gets a unique source_url to prevent upsert dedup collisions
    between documents from different sources that share the same content.
    """
    import hashlib
    global _store_counter
    _store_counter += 1
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    run = storage.create_run(source_id=source.id)
    doc = Document(
        source_url=f"https://{source.slug}.example.com/doc/{_store_counter}",
        title="Test",
        content_type=ContentType.HTML,
        raw_content=content,
        content_hash=content_hash,
        language="en",
        crawl_run_id=run.id,
        source_id=source.id,
        content_category=category,
    )
    stored, _ = storage.upsert_document(doc)
    chunk = Chunk(
        content=content,
        content_hash=content_hash,
        chunk_index=0,
        heading_path="Test",
        token_count=len(content) // 4,
        document_id=stored.id,
        content_category=category,
        citation=citation,
    )
    storage.insert_chunks([chunk])
    return chunk


class TestCrossSourceDuplicateDetection:
    def test_no_duplicates_returns_empty(self, storage, agency_source, statutory_source):
        """When no content is shared across sources, returns empty list."""
        _store_chunk(storage, agency_source, "Unique agency content.")
        _store_chunk(storage, statutory_source, "Unique statutory content.")

        dupes = storage.find_cross_source_duplicates()
        assert len(dupes) == 0

    def test_same_content_different_sources_detected(self, storage, agency_source, statutory_source):
        """Identical content across two sources is flagged as a duplicate."""
        shared_text = "An employer shall not discriminate against any employee."
        _store_chunk(
            storage, agency_source, shared_text,
            category=ContentCategory.AGENCY_GUIDANCE,
        )
        _store_chunk(
            storage, statutory_source, shared_text,
            citation="Cal. Lab. Code § 1102.5",
            category=ContentCategory.STATUTORY_CODE,
        )

        dupes = storage.find_cross_source_duplicates()
        assert len(dupes) == 1
        assert len(dupes[0]["occurrences"]) == 2

        sources = {occ["source_slug"] for occ in dupes[0]["occurrences"]}
        assert sources == {"crd", "labor_code"}

    def test_same_content_same_source_not_flagged(self, storage, agency_source):
        """Duplicate content within the SAME source is NOT a cross-source duplicate."""
        text = "This text appears twice in the same source."
        _store_chunk(storage, agency_source, text)
        # Store again with different URL
        import hashlib
        run = storage.create_run(source_id=agency_source.id)
        doc = Document(
            source_url="https://example.com/other-page",
            title="Test 2",
            content_type=ContentType.HTML,
            raw_content=text,
            content_hash=hashlib.sha256(text.encode()).hexdigest(),
            language="en",
            crawl_run_id=run.id,
            source_id=agency_source.id,
            content_category=ContentCategory.AGENCY_GUIDANCE,
        )
        stored, _ = storage.upsert_document(doc)
        chunk = Chunk(
            content=text,
            content_hash=hashlib.sha256(text.encode()).hexdigest(),
            chunk_index=0,
            heading_path="Test",
            token_count=len(text) // 4,
            document_id=stored.id,
            content_category=ContentCategory.AGENCY_GUIDANCE,
        )
        storage.insert_chunks([chunk])

        dupes = storage.find_cross_source_duplicates()
        assert len(dupes) == 0

    def test_multiple_duplicate_groups(self, storage, agency_source, statutory_source, second_agency):
        """Multiple distinct duplicate groups are reported separately."""
        text_a = "First shared content about wages."
        text_b = "Second shared content about discrimination."

        _store_chunk(storage, agency_source, text_a)
        _store_chunk(storage, statutory_source, text_a)
        _store_chunk(storage, agency_source, text_b)
        _store_chunk(storage, second_agency, text_b)

        dupes = storage.find_cross_source_duplicates()
        assert len(dupes) == 2

    def test_duplicate_preserves_both_categories(self, storage, agency_source, statutory_source):
        """Both content_categories are preserved in the duplicate report."""
        shared = "The employer shall provide reasonable accommodation."
        _store_chunk(
            storage, agency_source, shared,
            category=ContentCategory.AGENCY_GUIDANCE,
        )
        _store_chunk(
            storage, statutory_source, shared,
            citation="Cal. Gov. Code § 12940",
            category=ContentCategory.STATUTORY_CODE,
        )

        dupes = storage.find_cross_source_duplicates()
        assert len(dupes) == 1
        categories = {occ["content_category"] for occ in dupes[0]["occurrences"]}
        assert "agency_guidance" in categories
        assert "statutory_code" in categories

    def test_duplicate_report_includes_citation(self, storage, agency_source, statutory_source):
        """Citation metadata is included in the duplicate report."""
        shared = "No employer shall coerce employees."
        _store_chunk(storage, agency_source, shared)
        _store_chunk(
            storage, statutory_source, shared,
            citation="Cal. Lab. Code § 1102",
        )

        dupes = storage.find_cross_source_duplicates()
        citations = [occ["citation"] for occ in dupes[0]["occurrences"]]
        assert "Cal. Lab. Code § 1102" in citations

    def test_empty_database_returns_empty(self, storage):
        """Empty database returns no duplicates."""
        dupes = storage.find_cross_source_duplicates()
        assert dupes == []

    def test_three_way_duplicate(self, storage, agency_source, statutory_source, second_agency):
        """Content shared across three sources is correctly reported."""
        shared = "Protected activity includes filing a complaint."
        _store_chunk(storage, agency_source, shared)
        _store_chunk(storage, statutory_source, shared)
        _store_chunk(storage, second_agency, shared)

        dupes = storage.find_cross_source_duplicates()
        assert len(dupes) == 1
        assert len(dupes[0]["occurrences"]) == 3
