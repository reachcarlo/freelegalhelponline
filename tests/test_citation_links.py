"""Tests for the citation linking table (4C.3).

Tests cover:
- CitationLink model creation
- Bulk insert with deduplication
- Forward lookup (citations made by a chunk)
- Reverse lookup (chunks citing a target)
- Citation count
- Delete links for a chunk
- Cascade delete when source chunk is deleted
- SET NULL when target chunk is deleted
- resolve_citation_targets (statute and case matching)
- No orphaned links after chunk deletion
"""

from __future__ import annotations

from pathlib import Path

import pytest

from employee_help.storage.models import (
    Chunk,
    CitationLink,
    ContentCategory,
    ContentType,
    Document,
    Source,
    SourceType,
)
from employee_help.storage.storage import Storage


@pytest.fixture
def storage(tmp_path: Path) -> Storage:
    db_path = tmp_path / "test.db"
    s = Storage(db_path=db_path)
    yield s
    s.close()


def _setup_source_and_run(storage: Storage) -> tuple[int, int]:
    """Create a source and a crawl run, returning (source_id, run_id)."""
    source = storage.create_source(
        Source(
            name="Test Source",
            slug="test-source",
            source_type=SourceType.AGENCY,
            base_url="https://example.com",
        )
    )
    run = storage.create_run(source_id=source.id)
    return source.id, run.id


def _insert_document(
    storage: Storage, source_id: int, run_id: int, url: str = "https://example.com/doc",
    category: ContentCategory = ContentCategory.CASE_LAW,
) -> Document:
    """Insert a document and return it."""
    doc = Document(
        source_url=url,
        title="Test Document",
        content_type=ContentType.HTML,
        raw_content="test content",
        content_hash=f"hash_{url}",
        crawl_run_id=run_id,
        source_id=source_id,
        content_category=category,
    )
    doc, _ = storage.upsert_document(doc)
    return doc


def _insert_chunk(
    storage: Storage,
    document_id: int,
    content: str = "test chunk",
    citation: str | None = None,
    category: ContentCategory = ContentCategory.CASE_LAW,
    chunk_index: int = 0,
) -> Chunk:
    """Insert a single chunk and return it with its assigned ID."""
    chunk = Chunk(
        content=content,
        content_hash=f"chunk_hash_{document_id}_{chunk_index}_{content[:20]}",
        chunk_index=chunk_index,
        heading_path="Test > Path",
        token_count=10,
        document_id=document_id,
        content_category=category,
        citation=citation,
    )
    storage.insert_chunks([chunk])
    # Retrieve to get the assigned ID
    chunks = storage.get_chunks_for_document(document_id)
    return chunks[chunk_index]


def _make_link(
    source_chunk_id: int,
    cited_text: str = "27 Cal.3d 167",
    citation_type: str = "case",
    **kwargs,
) -> CitationLink:
    """Create a CitationLink with sensible defaults."""
    return CitationLink(
        source_chunk_id=source_chunk_id,
        cited_text=cited_text,
        citation_type=citation_type,
        reporter=kwargs.get("reporter"),
        volume=kwargs.get("volume"),
        page=kwargs.get("page"),
        section=kwargs.get("section"),
        is_california=kwargs.get("is_california", True),
        target_chunk_id=kwargs.get("target_chunk_id"),
    )


# ---------------------------------------------------------------------------
# CitationLink model tests
# ---------------------------------------------------------------------------

class TestCitationLinkModel:
    def test_create_citation_link(self):
        link = CitationLink(
            source_chunk_id=1,
            cited_text="27 Cal.3d 167",
            citation_type="case",
            reporter="Cal. 3d",
            volume="27",
            page="167",
            is_california=True,
        )
        assert link.source_chunk_id == 1
        assert link.cited_text == "27 Cal.3d 167"
        assert link.citation_type == "case"
        assert link.target_chunk_id is None
        assert link.id is None

    def test_defaults(self):
        link = CitationLink(source_chunk_id=1, cited_text="test", citation_type="case")
        assert link.reporter is None
        assert link.volume is None
        assert link.page is None
        assert link.section is None
        assert link.is_california is False
        assert link.target_chunk_id is None
        assert link.created_at is not None


# ---------------------------------------------------------------------------
# Insert and basic retrieval
# ---------------------------------------------------------------------------

class TestInsertCitationLinks:
    def test_insert_single_link(self, storage: Storage):
        source_id, run_id = _setup_source_and_run(storage)
        doc = _insert_document(storage, source_id, run_id)
        chunk = _insert_chunk(storage, doc.id)

        link = _make_link(chunk.id)
        count = storage.insert_citation_links([link])
        assert count == 1

    def test_insert_multiple_links(self, storage: Storage):
        source_id, run_id = _setup_source_and_run(storage)
        doc = _insert_document(storage, source_id, run_id)
        chunk = _insert_chunk(storage, doc.id)

        links = [
            _make_link(chunk.id, cited_text="27 Cal.3d 167", citation_type="case"),
            _make_link(chunk.id, cited_text="Cal. Lab. Code § 1102.5", citation_type="statute"),
            _make_link(chunk.id, cited_text="100 Cal.App.4th 200", citation_type="case"),
        ]
        count = storage.insert_citation_links(links)
        assert count == 3

    def test_deduplication_on_insert(self, storage: Storage):
        source_id, run_id = _setup_source_and_run(storage)
        doc = _insert_document(storage, source_id, run_id)
        chunk = _insert_chunk(storage, doc.id)

        link = _make_link(chunk.id, cited_text="27 Cal.3d 167")
        storage.insert_citation_links([link])

        # Insert same citation again — should be skipped
        dup = _make_link(chunk.id, cited_text="27 Cal.3d 167")
        count = storage.insert_citation_links([dup])
        assert count == 0

        # Total should still be 1
        assert storage.get_citation_link_count() == 1

    def test_same_citation_different_chunks(self, storage: Storage):
        source_id, run_id = _setup_source_and_run(storage)
        doc = _insert_document(storage, source_id, run_id)
        chunk1 = _insert_chunk(storage, doc.id, content="chunk 1", chunk_index=0)
        chunk2 = _insert_chunk(storage, doc.id, content="chunk 2", chunk_index=1)

        links = [
            _make_link(chunk1.id, cited_text="27 Cal.3d 167"),
            _make_link(chunk2.id, cited_text="27 Cal.3d 167"),
        ]
        count = storage.insert_citation_links(links)
        assert count == 2


# ---------------------------------------------------------------------------
# Forward lookup (citations made by a chunk)
# ---------------------------------------------------------------------------

class TestForwardLookup:
    def test_get_citations_for_chunk(self, storage: Storage):
        source_id, run_id = _setup_source_and_run(storage)
        doc = _insert_document(storage, source_id, run_id)
        chunk = _insert_chunk(storage, doc.id)

        links = [
            _make_link(chunk.id, cited_text="27 Cal.3d 167", citation_type="case"),
            _make_link(chunk.id, cited_text="Cal. Lab. Code § 1102.5", citation_type="statute"),
        ]
        storage.insert_citation_links(links)

        results = storage.get_citations_for_chunk(chunk.id)
        assert len(results) == 2
        cited_texts = {r.cited_text for r in results}
        assert "27 Cal.3d 167" in cited_texts
        assert "Cal. Lab. Code § 1102.5" in cited_texts

    def test_returns_citation_link_objects(self, storage: Storage):
        source_id, run_id = _setup_source_and_run(storage)
        doc = _insert_document(storage, source_id, run_id)
        chunk = _insert_chunk(storage, doc.id)

        storage.insert_citation_links([
            _make_link(chunk.id, reporter="Cal. 3d", volume="27", page="167"),
        ])
        results = storage.get_citations_for_chunk(chunk.id)
        assert len(results) == 1
        assert isinstance(results[0], CitationLink)
        assert results[0].reporter == "Cal. 3d"
        assert results[0].volume == "27"
        assert results[0].page == "167"
        assert results[0].id is not None

    def test_empty_for_unknown_chunk(self, storage: Storage):
        assert storage.get_citations_for_chunk(9999) == []


# ---------------------------------------------------------------------------
# Reverse lookup (chunks citing a target)
# ---------------------------------------------------------------------------

class TestReverseLookup:
    def test_get_citing_chunks(self, storage: Storage):
        source_id, run_id = _setup_source_and_run(storage)
        doc = _insert_document(storage, source_id, run_id)
        case_chunk = _insert_chunk(storage, doc.id, content="opinion text", chunk_index=0)

        doc2 = _insert_document(
            storage, source_id, run_id,
            url="https://example.com/statute",
            category=ContentCategory.STATUTORY_CODE,
        )
        statute_chunk = _insert_chunk(
            storage, doc2.id,
            content="Labor Code section 1102.5",
            citation="Cal. Lab. Code § 1102.5",
            category=ContentCategory.STATUTORY_CODE,
        )

        link = _make_link(
            case_chunk.id,
            cited_text="Cal. Lab. Code § 1102.5",
            citation_type="statute",
            target_chunk_id=statute_chunk.id,
        )
        storage.insert_citation_links([link])

        results = storage.get_citing_chunks(statute_chunk.id)
        assert len(results) == 1
        assert results[0].source_chunk_id == case_chunk.id

    def test_multiple_citing_chunks(self, storage: Storage):
        source_id, run_id = _setup_source_and_run(storage)

        # Target statute chunk
        doc_statute = _insert_document(
            storage, source_id, run_id,
            url="https://example.com/statute",
            category=ContentCategory.STATUTORY_CODE,
        )
        target = _insert_chunk(
            storage, doc_statute.id,
            content="Lab Code 1102.5",
            citation="Cal. Lab. Code § 1102.5",
            category=ContentCategory.STATUTORY_CODE,
        )

        # Two case chunks cite the same statute
        doc1 = _insert_document(storage, source_id, run_id, url="https://example.com/case1")
        chunk1 = _insert_chunk(storage, doc1.id, content="case 1")

        doc2 = _insert_document(storage, source_id, run_id, url="https://example.com/case2")
        chunk2 = _insert_chunk(storage, doc2.id, content="case 2")

        links = [
            _make_link(chunk1.id, cited_text="§ 1102.5", target_chunk_id=target.id),
            _make_link(chunk2.id, cited_text="§ 1102.5", target_chunk_id=target.id),
        ]
        storage.insert_citation_links(links)

        results = storage.get_citing_chunks(target.id)
        assert len(results) == 2
        source_ids = {r.source_chunk_id for r in results}
        assert chunk1.id in source_ids
        assert chunk2.id in source_ids

    def test_empty_for_uncited_chunk(self, storage: Storage):
        assert storage.get_citing_chunks(9999) == []


# ---------------------------------------------------------------------------
# Count and delete
# ---------------------------------------------------------------------------

class TestCountAndDelete:
    def test_citation_link_count(self, storage: Storage):
        source_id, run_id = _setup_source_and_run(storage)
        doc = _insert_document(storage, source_id, run_id)
        chunk = _insert_chunk(storage, doc.id)

        assert storage.get_citation_link_count() == 0

        storage.insert_citation_links([
            _make_link(chunk.id, cited_text="cite1"),
            _make_link(chunk.id, cited_text="cite2"),
        ])
        assert storage.get_citation_link_count() == 2

    def test_delete_links_for_chunk(self, storage: Storage):
        source_id, run_id = _setup_source_and_run(storage)
        doc = _insert_document(storage, source_id, run_id)
        chunk = _insert_chunk(storage, doc.id)

        storage.insert_citation_links([
            _make_link(chunk.id, cited_text="cite1"),
            _make_link(chunk.id, cited_text="cite2"),
        ])
        assert storage.get_citation_link_count() == 2

        deleted = storage.delete_citation_links_for_chunk(chunk.id)
        assert deleted == 2
        assert storage.get_citation_link_count() == 0

    def test_delete_returns_zero_when_none(self, storage: Storage):
        assert storage.delete_citation_links_for_chunk(9999) == 0


# ---------------------------------------------------------------------------
# Cascade behavior
# ---------------------------------------------------------------------------

class TestCascadeBehavior:
    def test_source_chunk_cascade_delete(self, storage: Storage):
        """When a source chunk is deleted, its citation links are removed."""
        source_id, run_id = _setup_source_and_run(storage)
        doc = _insert_document(storage, source_id, run_id)
        chunk = _insert_chunk(storage, doc.id)

        storage.insert_citation_links([_make_link(chunk.id)])
        assert storage.get_citation_link_count() == 1

        # Delete the chunk's document (cascades to chunks, which cascades to links)
        storage._conn.execute("DELETE FROM chunks WHERE id = ?", (chunk.id,))
        storage._conn.commit()
        assert storage.get_citation_link_count() == 0

    def test_target_chunk_set_null(self, storage: Storage):
        """When a target chunk is deleted, target_chunk_id is set to NULL."""
        source_id, run_id = _setup_source_and_run(storage)

        doc1 = _insert_document(storage, source_id, run_id, url="https://example.com/case")
        source_chunk = _insert_chunk(storage, doc1.id, content="citing case")

        doc2 = _insert_document(
            storage, source_id, run_id,
            url="https://example.com/statute",
            category=ContentCategory.STATUTORY_CODE,
        )
        target_chunk = _insert_chunk(
            storage, doc2.id,
            content="statute text",
            category=ContentCategory.STATUTORY_CODE,
        )

        storage.insert_citation_links([
            _make_link(source_chunk.id, target_chunk_id=target_chunk.id),
        ])

        # Verify target is set
        links = storage.get_citations_for_chunk(source_chunk.id)
        assert links[0].target_chunk_id == target_chunk.id

        # Delete target chunk
        storage._conn.execute("DELETE FROM chunks WHERE id = ?", (target_chunk.id,))
        storage._conn.commit()

        # Link still exists but target is NULL
        links = storage.get_citations_for_chunk(source_chunk.id)
        assert len(links) == 1
        assert links[0].target_chunk_id is None


# ---------------------------------------------------------------------------
# Resolve citation targets
# ---------------------------------------------------------------------------

class TestResolveCitationTargets:
    def test_resolve_statute_citation(self, storage: Storage):
        source_id, run_id = _setup_source_and_run(storage)

        # Create a statute chunk with citation
        doc_statute = _insert_document(
            storage, source_id, run_id,
            url="https://example.com/lab1102.5",
            category=ContentCategory.STATUTORY_CODE,
        )
        statute_chunk = _insert_chunk(
            storage, doc_statute.id,
            content="Whistleblower protection text",
            citation="Cal. Lab. Code § 1102.5",
            category=ContentCategory.STATUTORY_CODE,
        )

        # Create a case chunk citing the statute
        doc_case = _insert_document(storage, source_id, run_id, url="https://example.com/case1")
        case_chunk = _insert_chunk(storage, doc_case.id, content="opinion text")

        link = _make_link(
            case_chunk.id,
            cited_text="Cal. Lab. Code § 1102.5",
            citation_type="statute",
            section="1102.5",
        )
        storage.insert_citation_links([link])

        # Before resolution
        links = storage.get_citations_for_chunk(case_chunk.id)
        assert links[0].target_chunk_id is None

        # Resolve
        resolved = storage.resolve_citation_targets()
        assert resolved >= 1

        # After resolution
        links = storage.get_citations_for_chunk(case_chunk.id)
        assert links[0].target_chunk_id == statute_chunk.id

    def test_resolve_case_citation(self, storage: Storage):
        source_id, run_id = _setup_source_and_run(storage)

        # Create a target case chunk
        doc_target = _insert_document(
            storage, source_id, run_id, url="https://example.com/tameny",
        )
        target_chunk = _insert_chunk(
            storage, doc_target.id,
            content="Tameny opinion text",
            citation="Tameny v. Atlantic Richfield Co. (1980) 27 Cal.3d 167",
        )

        # Create a citing case chunk
        doc_citing = _insert_document(
            storage, source_id, run_id, url="https://example.com/citing_case",
        )
        citing_chunk = _insert_chunk(storage, doc_citing.id, content="cites Tameny")

        link = _make_link(
            citing_chunk.id,
            cited_text="27 Cal.3d 167",
            citation_type="case",
            volume="27",
            reporter="Cal.3d",
            page="167",
        )
        storage.insert_citation_links([link])

        resolved = storage.resolve_citation_targets()
        assert resolved >= 1

        links = storage.get_citations_for_chunk(citing_chunk.id)
        assert links[0].target_chunk_id == target_chunk.id

    def test_resolve_skips_already_resolved(self, storage: Storage):
        source_id, run_id = _setup_source_and_run(storage)

        doc = _insert_document(storage, source_id, run_id)
        chunk = _insert_chunk(storage, doc.id)

        doc2 = _insert_document(storage, source_id, run_id, url="https://example.com/target")
        target = _insert_chunk(storage, doc2.id)

        # Insert an already-resolved link
        link = _make_link(chunk.id, target_chunk_id=target.id)
        storage.insert_citation_links([link])

        # resolve_citation_targets should not change it
        resolved = storage.resolve_citation_targets()
        links = storage.get_citations_for_chunk(chunk.id)
        assert links[0].target_chunk_id == target.id

    def test_resolve_no_match(self, storage: Storage):
        source_id, run_id = _setup_source_and_run(storage)

        doc = _insert_document(storage, source_id, run_id)
        chunk = _insert_chunk(storage, doc.id)

        # Citation with no matching chunk in KB
        link = _make_link(
            chunk.id,
            cited_text="Cal. Lab. Code § 99999",
            citation_type="statute",
            section="99999",
        )
        storage.insert_citation_links([link])

        resolved = storage.resolve_citation_targets()

        links = storage.get_citations_for_chunk(chunk.id)
        assert links[0].target_chunk_id is None


# ---------------------------------------------------------------------------
# Field preservation
# ---------------------------------------------------------------------------

class TestFieldPreservation:
    def test_all_fields_round_trip(self, storage: Storage):
        source_id, run_id = _setup_source_and_run(storage)
        doc = _insert_document(storage, source_id, run_id)
        chunk = _insert_chunk(storage, doc.id)

        link = CitationLink(
            source_chunk_id=chunk.id,
            cited_text="27 Cal.3d 167",
            citation_type="case",
            reporter="Cal. 3d",
            volume="27",
            page="167",
            section=None,
            is_california=True,
            target_chunk_id=None,
        )
        storage.insert_citation_links([link])

        results = storage.get_citations_for_chunk(chunk.id)
        result = results[0]
        assert result.cited_text == "27 Cal.3d 167"
        assert result.citation_type == "case"
        assert result.reporter == "Cal. 3d"
        assert result.volume == "27"
        assert result.page == "167"
        assert result.section is None
        assert result.is_california is True
        assert result.target_chunk_id is None
        assert result.created_at is not None

    def test_statute_fields(self, storage: Storage):
        source_id, run_id = _setup_source_and_run(storage)
        doc = _insert_document(storage, source_id, run_id)
        chunk = _insert_chunk(storage, doc.id)

        link = CitationLink(
            source_chunk_id=chunk.id,
            cited_text="Cal. Lab. Code § 1102.5",
            citation_type="statute",
            section="1102.5",
            is_california=True,
        )
        storage.insert_citation_links([link])

        results = storage.get_citations_for_chunk(chunk.id)
        assert results[0].citation_type == "statute"
        assert results[0].section == "1102.5"
