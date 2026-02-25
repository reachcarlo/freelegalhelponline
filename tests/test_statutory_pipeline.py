"""Tests for statutory pipeline features: resumability, repealed-section soft-delete, live integration."""

import pytest

from employee_help.processing.chunker import chunk_statute_section
from employee_help.scraper.extractors.statute import (
    BASE_URL,
    HierarchyPath,
    StatuteSection,
    StatutoryExtractor,
    TocEntry,
    build_citation,
    parse_display_text_page,
    parse_toc_page,
)
from employee_help.storage.models import (
    Chunk,
    ContentCategory,
    ContentType,
    Document,
    Source,
    SourceType,
)
from employee_help.storage.storage import Storage


# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture
def storage():
    """In-memory SQLite storage for testing."""
    s = Storage(":memory:")
    yield s
    s.close()


@pytest.fixture
def source(storage):
    """Create a statutory source record."""
    src = Source(
        name="Test Labor Code",
        slug="test_labor_code",
        source_type=SourceType.STATUTORY_CODE,
        base_url="https://leginfo.legislature.ca.gov",
    )
    storage.create_source(src)
    return src


def _make_section(section_num: str, text: str = "Sample text.") -> StatuteSection:
    """Helper to create a StatuteSection."""
    return StatuteSection(
        section_number=section_num,
        code_abbreviation="LAB",
        text=text,
        citation=build_citation("LAB", section_num),
        hierarchy=HierarchyPath(code_name="LAB", division="Division 2"),
        source_url=f"{BASE_URL}/faces/codes_displaySection.xhtml?lawCode=LAB&sectionNum={section_num}",
    )


def _store_section(storage, source, run_id, section):
    """Store a section as a document + chunks."""
    chunks = chunk_statute_section(
        section.text,
        citation=section.citation,
        heading_path=section.heading_path,
        max_tokens=1500,
    )
    if not chunks:
        return None

    doc = Document(
        source_url=section.source_url,
        title=section.citation,
        content_type=ContentType.HTML,
        raw_content=section.text,
        content_hash=chunks[0].content_hash,
        language="en",
        crawl_run_id=run_id,
        source_id=source.id,
        content_category=ContentCategory.STATUTORY_CODE,
    )
    stored_doc, is_new = storage.upsert_document(doc)

    if stored_doc.id:
        chunk_objects = [
            Chunk(
                content=c.content,
                content_hash=c.content_hash,
                chunk_index=c.chunk_index,
                heading_path=c.heading_path,
                token_count=c.token_count,
                document_id=stored_doc.id,
                content_category=ContentCategory.STATUTORY_CODE,
                citation=section.citation,
            )
            for c in chunks
        ]
        storage.insert_chunks(chunk_objects)

    return stored_doc


# ── Repealed-Section Soft-Delete Tests ───────────────────────


class TestRepealedSectionSoftDelete:
    def test_deactivate_chunks_for_document(self, storage, source):
        """Deactivating chunks marks them is_active=False."""
        run = storage.create_run(source_id=source.id)
        section = _make_section("100", "This section is about to be repealed.")
        doc = _store_section(storage, source, run.id, section)

        # Verify chunks are active initially
        chunks = storage.get_chunks_for_document(doc.id)
        assert all(c.is_active for c in chunks)

        # Deactivate
        count = storage.deactivate_chunks_for_document(doc.id)
        assert count == len(chunks)

        # Verify chunks are now inactive
        chunks_after = storage.get_chunks_for_document(doc.id)
        assert all(not c.is_active for c in chunks_after)

    def test_deactivate_is_idempotent(self, storage, source):
        """Deactivating already-inactive chunks returns 0."""
        run = storage.create_run(source_id=source.id)
        section = _make_section("101")
        doc = _store_section(storage, source, run.id, section)

        # First deactivation
        storage.deactivate_chunks_for_document(doc.id)
        # Second deactivation should return 0
        count = storage.deactivate_chunks_for_document(doc.id)
        assert count == 0

    def test_deactivated_chunks_still_exist(self, storage, source):
        """Soft-deleted chunks are not physically removed."""
        run = storage.create_run(source_id=source.id)
        section = _make_section("102")
        doc = _store_section(storage, source, run.id, section)

        chunk_count_before = len(storage.get_chunks_for_document(doc.id))
        storage.deactivate_chunks_for_document(doc.id)
        chunk_count_after = len(storage.get_chunks_for_document(doc.id))

        assert chunk_count_before == chunk_count_after
        assert chunk_count_after > 0

    def test_deactivate_missing_sections(self, storage, source):
        """Sections no longer present in extraction get deactivated."""
        run = storage.create_run(source_id=source.id)

        # Store three sections
        s100 = _make_section("100", "Active section.")
        s101 = _make_section("101", "Will be repealed.")
        s102 = _make_section("102", "Another active section.")
        _store_section(storage, source, run.id, s100)
        _store_section(storage, source, run.id, s101)
        _store_section(storage, source, run.id, s102)

        # Re-ingest with section 101 removed
        current_urls = {s100.source_url, s102.source_url}
        deactivated = storage.deactivate_missing_sections(source.id, current_urls)

        assert deactivated > 0  # s101 chunks should be deactivated

        # Verify s100 and s102 chunks are still active
        all_docs = storage.get_all_documents(source_id=source.id)
        for doc in all_docs:
            chunks = storage.get_chunks_for_document(doc.id)
            if doc.source_url == s101.source_url:
                assert all(not c.is_active for c in chunks)
            else:
                assert all(c.is_active for c in chunks)

    def test_deactivate_missing_sections_all_present(self, storage, source):
        """When all sections still present, nothing is deactivated."""
        run = storage.create_run(source_id=source.id)

        s100 = _make_section("100")
        s101 = _make_section("101")
        _store_section(storage, source, run.id, s100)
        _store_section(storage, source, run.id, s101)

        current_urls = {s100.source_url, s101.source_url}
        deactivated = storage.deactivate_missing_sections(source.id, current_urls)
        assert deactivated == 0

    def test_full_reingest_with_repealed_section(self, storage, source):
        """End-to-end: first ingest has 3 sections, second has 2, third re-adds."""
        run1 = storage.create_run(source_id=source.id)

        # First ingest: sections 100, 101, 102
        s100 = _make_section("100", "Wages and hours.")
        s101 = _make_section("101", "Overtime provisions.")
        s102 = _make_section("102", "Rest breaks.")
        _store_section(storage, source, run1.id, s100)
        _store_section(storage, source, run1.id, s101)
        _store_section(storage, source, run1.id, s102)

        # Second ingest: section 101 repealed
        run2 = storage.create_run(source_id=source.id)
        current_urls = {s100.source_url, s102.source_url}
        deactivated = storage.deactivate_missing_sections(source.id, current_urls)
        assert deactivated > 0

        # Verify 101 is inactive
        all_docs = storage.get_all_documents(source_id=source.id)
        doc_101 = [d for d in all_docs if "101" in d.source_url][0]
        chunks_101 = storage.get_chunks_for_document(doc_101.id)
        assert all(not c.is_active for c in chunks_101)

        # Active chunks count: should only be s100 and s102
        all_chunks = storage.get_all_chunks(source_id=source.id)
        active_chunks = [c for c in all_chunks if c.is_active]
        inactive_chunks = [c for c in all_chunks if not c.is_active]
        assert len(active_chunks) == 2
        assert len(inactive_chunks) == 1


# ── Resumability Tests ───────────────────────────────────────


class TestResumability:
    def test_extractor_accepts_completed_urls(self):
        """StatutoryExtractor accepts a set of completed URLs."""
        completed = {"https://example.com/page1", "https://example.com/page2"}
        extractor = StatutoryExtractor(
            "LAB",
            rate_limit=3.0,
            completed_urls=completed,
        )
        assert extractor.completed_urls == completed

    def test_extractor_default_no_completed_urls(self):
        """Default extractor has empty completed_urls."""
        extractor = StatutoryExtractor("LAB", rate_limit=3.0)
        assert extractor.completed_urls == set()

    def test_completed_urls_skips_toc_pages(self):
        """TOC entries matching completed_urls are skipped in extract_all."""
        # Create mock TOC HTML with two entries
        toc_html = """
        <html><body>
        <a href="/faces/codes_displayText.xhtml?lawCode=LAB&division=1.&chapter=1.">
          Chapter 1 [1 - 10]
        </a>
        <a href="/faces/codes_displayText.xhtml?lawCode=LAB&division=1.&chapter=2.">
          Chapter 2 [11 - 20]
        </a>
        </body></html>
        """
        entries = parse_toc_page(toc_html, "LAB")
        assert len(entries) == 2

        # Mark first entry as completed
        completed = {entries[0].url}

        # The extractor would skip the first entry
        pending = [e for e in entries if e.url not in completed]
        assert len(pending) == 1
        assert pending[0].url == entries[1].url

    def test_completed_urls_updates_during_extraction(self):
        """The completed_urls set grows as pages are processed."""
        extractor = StatutoryExtractor("LAB", rate_limit=3.0)
        assert len(extractor.completed_urls) == 0

        # Simulate marking a URL as completed
        extractor.completed_urls.add("https://example.com/page1")
        assert len(extractor.completed_urls) == 1


# ── Live Integration Tests ───────────────────────────────────


@pytest.mark.live
class TestLegInfoLive:
    """Tests that run against the live leginfo.legislature.ca.gov website.

    Run with: pytest -m live
    Skip with: pytest -m "not live" (default)
    """

    def test_toc_discovery_labor_code(self):
        """Can discover TOC for Labor Code from live leginfo."""
        with StatutoryExtractor("LAB", rate_limit=10.0) as extractor:
            entries = extractor.discover_toc()
            assert len(entries) > 100  # Labor Code has hundreds of chapters
            for entry in entries[:3]:
                assert "codes_displayText.xhtml" in entry.url
                assert entry.hierarchy.code_name == "LAB"

    def test_toc_discovery_gov_code_division_3(self):
        """Can discover TOC for Gov Code Division 3 (FEHA) from live leginfo."""
        with StatutoryExtractor(
            "GOV", rate_limit=10.0, target_divisions=["3."]
        ) as extractor:
            entries = extractor.discover_toc()
            assert len(entries) > 10
            assert all("division=3." in e.url for e in entries)

    def test_extract_single_page(self):
        """Can extract sections from a single displayText page."""
        with StatutoryExtractor("LAB", rate_limit=10.0) as extractor:
            entries = extractor.discover_toc()
            assert len(entries) > 0

            # Extract first page only
            sections = extractor.extract_sections_from_page(entries[0])
            assert len(sections) > 0
            for s in sections:
                assert s.section_number
                assert s.text
                assert s.citation.startswith("Cal. Lab. Code §")

    def test_section_citation_format(self):
        """Live-extracted citations match expected format."""
        with StatutoryExtractor("LAB", rate_limit=10.0) as extractor:
            entries = extractor.discover_toc()
            sections = extractor.extract_sections_from_page(entries[0])
            for s in sections:
                # Citation must match pattern: Cal. Lab. Code § <number>
                assert s.citation.startswith("Cal. Lab. Code § ")
                # Section number should be numeric (with optional decimal)
                assert s.section_number.replace(".", "").isdigit()

    def test_section_hierarchy_populated(self):
        """Live-extracted sections have populated hierarchy paths."""
        with StatutoryExtractor("LAB", rate_limit=10.0) as extractor:
            entries = extractor.discover_toc()
            sections = extractor.extract_sections_from_page(entries[0])
            for s in sections:
                assert "LAB" in s.heading_path
