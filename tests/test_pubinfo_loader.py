"""Tests for the PUBINFO database loader (PubinfoLoader).

Tests cover:
- .dat file parsing (tab-split, backtick-unquote, NULL handling)
- .lob file resolution (column 15 → file content)
- Filtering by law_code, division, active_flg
- HTML-to-text conversion
- Conversion to StatuteSection objects
- Citation accuracy
- Pipeline integration (end-to-end: ZIP → chunks in DB)
"""

import io
import zipfile
from pathlib import Path

import pytest

from employee_help.scraper.extractors.pubinfo import (
    PubinfoLoader,
    PubinfoSection,
    _unquote,
    _unquote_required,
    html_to_text,
)
from employee_help.scraper.extractors.statute import (
    HierarchyPath,
    StatuteSection,
    build_citation,
)


# ── Helpers ─────────────────────────────────────────────────


def _make_dat_row(
    id: str = "1",
    law_code: str = "LAB",
    section_num: str = "1102.5",
    op_statues: str = "2023",
    op_chapter: str = "612",
    op_section: str = "2",
    effective_date: str = "2024-01-01",
    law_section_version_id: str = "100",
    division: str = "2.",
    title: str = "NULL",
    part: str = "3.",
    chapter: str = "5.",
    article: str = "NULL",
    history: str = "Amended by Stats. 2023, Ch. 612, Sec. 2.",
    lob_file: str = "law_section_1.lob",
    active_flg: str = "Y",
    trans_uid: str = "user1",
    trans_update: str = "2024-01-15",
) -> str:
    """Build a single tab-delimited row for LAW_SECTION_TBL.dat."""
    def q(val: str) -> str:
        """Backtick-quote a value unless it's NULL."""
        return val if val == "NULL" else f"`{val}`"

    cols = [
        q(id), q(law_code), q(section_num), q(op_statues), q(op_chapter),
        q(op_section), q(effective_date), q(law_section_version_id),
        q(division), q(title), q(part), q(chapter), q(article),
        q(history), q(lob_file), q(active_flg), q(trans_uid), q(trans_update),
    ]
    return "\t".join(cols)


SAMPLE_LOB_HTML = """<html><body>
<p>(a) An employer shall not retaliate against an employee for disclosing
information to a government or law enforcement agency.</p>
<p>(b) An employer shall not retaliate against an employee for refusing
to participate in an activity that would result in a violation of law.</p>
</body></html>"""

SAMPLE_LOB_HTML_SIMPLE = "<p>Section one text about employment rights.</p>"


def _make_test_zip(
    dat_rows: list[str],
    lob_files: dict[str, str] | None = None,
) -> bytes:
    """Create an in-memory ZIP with LAW_SECTION_TBL.dat and .lob files."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        dat_content = "\n".join(dat_rows)
        zf.writestr("LAW_SECTION_TBL.dat", dat_content)

        if lob_files:
            for name, content in lob_files.items():
                zf.writestr(name, content)

    return buf.getvalue()


@pytest.fixture
def sample_zip_path(tmp_path: Path) -> Path:
    """Create a sample PUBINFO ZIP with multiple sections."""
    rows = [
        _make_dat_row(
            id="1", law_code="LAB", section_num="1102.5",
            division="2.", part="3.", chapter="5.", article="NULL",
            lob_file="law_section_1.lob", active_flg="Y",
            effective_date="2024-01-01",
            history="Amended by Stats. 2023, Ch. 612, Sec. 2.",
        ),
        _make_dat_row(
            id="2", law_code="LAB", section_num="1101",
            division="2.", part="3.", chapter="5.", article="NULL",
            lob_file="law_section_2.lob", active_flg="Y",
            effective_date="1937-01-01",
            history="Added by Stats. 1937, Ch. 90.",
        ),
        _make_dat_row(
            id="3", law_code="GOV", section_num="12940",
            division="3.", part="2.8", chapter="6.", article="NULL",
            lob_file="law_section_3.lob", active_flg="Y",
            effective_date="2024-01-01",
            history="Amended by Stats. 2023, Ch. 700.",
        ),
        _make_dat_row(
            id="4", law_code="LAB", section_num="9999",
            division="7.", part="NULL", chapter="NULL", article="NULL",
            lob_file="law_section_4.lob", active_flg="N",  # Repealed
            effective_date="2020-01-01",
            history="Repealed by Stats. 2019.",
        ),
    ]

    lob_files = {
        "law_section_1.lob": SAMPLE_LOB_HTML,
        "law_section_2.lob": "<p>No employer shall make, adopt, or enforce any rule forbidding employees from engaging in politics.</p>",
        "law_section_3.lob": "<p>It is an unlawful employment practice for an employer to discriminate against any person in employment.</p>",
        "law_section_4.lob": "<p>Repealed section text.</p>",
    }

    zip_bytes = _make_test_zip(rows, lob_files)
    zip_path = tmp_path / "pubinfo_2025.zip"
    zip_path.write_bytes(zip_bytes)
    return zip_path


# ── Unquoting Tests ─────────────────────────────────────────


class TestUnquote:
    def test_backtick_quotes_removed(self):
        assert _unquote("`LAB`") == "LAB"

    def test_null_literal_returns_none(self):
        assert _unquote("NULL") is None

    def test_plain_value_passthrough(self):
        assert _unquote("plain") == "plain"

    def test_empty_backticks(self):
        assert _unquote("``") == ""

    def test_whitespace_stripped(self):
        assert _unquote("  `value`  ") == "value"

    def test_unquote_required_returns_string(self):
        assert _unquote_required("`LAB`") == "LAB"

    def test_unquote_required_null_returns_empty(self):
        assert _unquote_required("NULL") == ""


# ── HTML-to-Text Tests ──────────────────────────────────────


class TestHtmlToText:
    def test_basic_html(self):
        text = html_to_text("<p>Hello world</p>")
        assert "Hello world" in text

    def test_nested_html(self):
        text = html_to_text("<div><p><b>Bold</b> text</p></div>")
        assert "Bold" in text
        assert "text" in text

    def test_empty_html(self):
        assert html_to_text("") == ""
        assert html_to_text("   ") == ""

    def test_strips_tags(self):
        text = html_to_text("<p>One</p><p>Two</p>")
        assert "<p>" not in text
        assert "One" in text
        assert "Two" in text

    def test_sample_lob_content(self):
        text = html_to_text(SAMPLE_LOB_HTML)
        assert "employer" in text
        assert "retaliate" in text
        assert "(a)" in text
        assert "(b)" in text


# ── Dat Parsing Tests ───────────────────────────────────────


class TestParseLawSections:
    def test_parses_all_rows(self, sample_zip_path: Path):
        loader = PubinfoLoader(sample_zip_path)
        sections = loader.parse_law_sections()
        assert len(sections) == 4

    def test_law_code_parsed(self, sample_zip_path: Path):
        loader = PubinfoLoader(sample_zip_path)
        sections = loader.parse_law_sections()
        codes = {s.law_code for s in sections}
        assert "LAB" in codes
        assert "GOV" in codes

    def test_section_num_parsed(self, sample_zip_path: Path):
        loader = PubinfoLoader(sample_zip_path)
        sections = loader.parse_law_sections()
        nums = {s.section_num for s in sections}
        assert "1102.5" in nums
        assert "1101" in nums
        assert "12940" in nums

    def test_division_parsed(self, sample_zip_path: Path):
        loader = PubinfoLoader(sample_zip_path)
        sections = loader.parse_law_sections()
        lab_1102_5 = [s for s in sections if s.section_num == "1102.5"][0]
        assert lab_1102_5.division == "2."

    def test_null_fields_are_none(self, sample_zip_path: Path):
        loader = PubinfoLoader(sample_zip_path)
        sections = loader.parse_law_sections()
        lab_1102_5 = [s for s in sections if s.section_num == "1102.5"][0]
        assert lab_1102_5.title is None  # title was NULL in test data
        assert lab_1102_5.article is None  # article was NULL in test data

    def test_effective_date_parsed(self, sample_zip_path: Path):
        loader = PubinfoLoader(sample_zip_path)
        sections = loader.parse_law_sections()
        lab_1102_5 = [s for s in sections if s.section_num == "1102.5"][0]
        assert lab_1102_5.effective_date == "2024-01-01"

    def test_history_parsed(self, sample_zip_path: Path):
        loader = PubinfoLoader(sample_zip_path)
        sections = loader.parse_law_sections()
        lab_1102_5 = [s for s in sections if s.section_num == "1102.5"][0]
        assert "2023" in lab_1102_5.history

    def test_active_flg_parsed(self, sample_zip_path: Path):
        loader = PubinfoLoader(sample_zip_path)
        sections = loader.parse_law_sections()
        active = [s for s in sections if s.section_num == "1102.5"][0]
        repealed = [s for s in sections if s.section_num == "9999"][0]
        assert active.active_flg == "Y"
        assert repealed.active_flg == "N"


# ── LOB Resolution Tests ────────────────────────────────────


class TestLobResolution:
    def test_lob_content_resolved(self, sample_zip_path: Path):
        loader = PubinfoLoader(sample_zip_path)
        sections = loader.parse_law_sections()
        lab_1102_5 = [s for s in sections if s.section_num == "1102.5"][0]
        assert "retaliate" in lab_1102_5.content_html
        assert "<p>" in lab_1102_5.content_html

    def test_all_sections_have_content(self, sample_zip_path: Path):
        loader = PubinfoLoader(sample_zip_path)
        sections = loader.parse_law_sections()
        for s in sections:
            assert s.content_html, f"Section {s.section_num} has no content"

    def test_missing_lob_gets_empty(self, tmp_path: Path):
        """Section with lob_file pointing to non-existent file gets empty content."""
        rows = [
            _make_dat_row(lob_file="missing.lob"),
        ]
        zip_bytes = _make_test_zip(rows, lob_files={})
        zip_path = tmp_path / "test.zip"
        zip_path.write_bytes(zip_bytes)

        loader = PubinfoLoader(zip_path)
        sections = loader.parse_law_sections()
        assert len(sections) == 1
        assert sections[0].content_html == ""


# ── Filtering Tests ─────────────────────────────────────────


class TestFilterSections:
    def test_filter_by_code(self, sample_zip_path: Path):
        loader = PubinfoLoader(sample_zip_path)
        sections = loader.parse_law_sections()
        filtered = loader.filter_sections(sections, target_codes=["LAB"])
        assert all(s.law_code == "LAB" for s in filtered)
        # Should get 2 active LAB sections (not the repealed one)
        assert len(filtered) == 2

    def test_filter_by_code_gov(self, sample_zip_path: Path):
        loader = PubinfoLoader(sample_zip_path)
        sections = loader.parse_law_sections()
        filtered = loader.filter_sections(sections, target_codes=["GOV"])
        assert len(filtered) == 1
        assert filtered[0].section_num == "12940"

    def test_filter_by_division(self, sample_zip_path: Path):
        loader = PubinfoLoader(sample_zip_path)
        sections = loader.parse_law_sections()
        filtered = loader.filter_sections(
            sections, target_codes=["LAB"], target_divisions=["2."]
        )
        assert all(s.division == "2." for s in filtered)
        assert len(filtered) == 2

    def test_filter_active_only(self, sample_zip_path: Path):
        loader = PubinfoLoader(sample_zip_path)
        sections = loader.parse_law_sections()
        # Include all LAB sections, active only
        filtered = loader.filter_sections(sections, target_codes=["LAB"], active_only=True)
        assert all(s.active_flg == "Y" for s in filtered)
        assert len(filtered) == 2  # Excludes section 9999

    def test_filter_include_inactive(self, sample_zip_path: Path):
        loader = PubinfoLoader(sample_zip_path)
        sections = loader.parse_law_sections()
        filtered = loader.filter_sections(sections, target_codes=["LAB"], active_only=False)
        assert len(filtered) == 3  # Includes section 9999

    def test_filter_nonexistent_code(self, sample_zip_path: Path):
        loader = PubinfoLoader(sample_zip_path)
        sections = loader.parse_law_sections()
        filtered = loader.filter_sections(sections, target_codes=["XYZ"])
        assert len(filtered) == 0

    def test_filter_nonexistent_division(self, sample_zip_path: Path):
        loader = PubinfoLoader(sample_zip_path)
        sections = loader.parse_law_sections()
        filtered = loader.filter_sections(
            sections, target_codes=["LAB"], target_divisions=["99."]
        )
        assert len(filtered) == 0

    def test_filter_multiple_codes(self, sample_zip_path: Path):
        loader = PubinfoLoader(sample_zip_path)
        sections = loader.parse_law_sections()
        filtered = loader.filter_sections(sections, target_codes=["LAB", "GOV"])
        assert len(filtered) == 3  # 2 active LAB + 1 GOV


# ── StatuteSection Conversion Tests ─────────────────────────


class TestToStatuteSections:
    def test_converts_to_statute_sections(self, sample_zip_path: Path):
        loader = PubinfoLoader(sample_zip_path)
        sections = loader.parse_law_sections()
        filtered = loader.filter_sections(sections, target_codes=["LAB"])
        result = loader.to_statute_sections(filtered)
        assert len(result) == 2
        assert all(isinstance(s, StatuteSection) for s in result)

    def test_citation_accuracy(self, sample_zip_path: Path):
        loader = PubinfoLoader(sample_zip_path)
        sections = loader.parse_law_sections()
        filtered = loader.filter_sections(sections, target_codes=["LAB"])
        result = loader.to_statute_sections(filtered)
        citations = {s.citation for s in result}
        assert "Cal. Lab. Code § 1102.5" in citations
        assert "Cal. Lab. Code § 1101" in citations

    def test_gov_code_citation(self, sample_zip_path: Path):
        loader = PubinfoLoader(sample_zip_path)
        sections = loader.parse_law_sections()
        filtered = loader.filter_sections(sections, target_codes=["GOV"])
        result = loader.to_statute_sections(filtered)
        assert result[0].citation == "Cal. Gov. Code § 12940"

    def test_hierarchy_populated(self, sample_zip_path: Path):
        loader = PubinfoLoader(sample_zip_path)
        sections = loader.parse_law_sections()
        filtered = loader.filter_sections(sections, target_codes=["LAB"])
        result = loader.to_statute_sections(filtered)
        s = [r for r in result if r.section_number == "1102.5"][0]
        assert s.hierarchy.code_name == "LAB"
        assert "2" in s.hierarchy.division
        assert "3" in s.hierarchy.part
        assert "5" in s.hierarchy.chapter

    def test_text_is_plain_text(self, sample_zip_path: Path):
        loader = PubinfoLoader(sample_zip_path)
        sections = loader.parse_law_sections()
        filtered = loader.filter_sections(sections, target_codes=["LAB"])
        result = loader.to_statute_sections(filtered)
        for s in result:
            assert "<p>" not in s.text
            assert "<html>" not in s.text
            assert len(s.text) > 0

    def test_source_url_constructed(self, sample_zip_path: Path):
        loader = PubinfoLoader(sample_zip_path)
        sections = loader.parse_law_sections()
        filtered = loader.filter_sections(sections, target_codes=["LAB"])
        result = loader.to_statute_sections(filtered)
        s = [r for r in result if r.section_number == "1102.5"][0]
        assert "codes_displaySection.xhtml" in s.source_url
        assert "lawCode=LAB" in s.source_url
        assert "sectionNum=1102.5" in s.source_url

    def test_subdivisions_detected(self, sample_zip_path: Path):
        loader = PubinfoLoader(sample_zip_path)
        sections = loader.parse_law_sections()
        filtered = loader.filter_sections(sections, target_codes=["LAB"])
        result = loader.to_statute_sections(filtered)
        s = [r for r in result if r.section_number == "1102.5"][0]
        assert "a" in s.subdivisions
        assert "b" in s.subdivisions

    def test_effective_date_preserved(self, sample_zip_path: Path):
        loader = PubinfoLoader(sample_zip_path)
        sections = loader.parse_law_sections()
        filtered = loader.filter_sections(sections, target_codes=["LAB"])
        result = loader.to_statute_sections(filtered)
        s = [r for r in result if r.section_number == "1102.5"][0]
        assert s.effective_date == "2024-01-01"

    def test_amendment_info_from_history(self, sample_zip_path: Path):
        loader = PubinfoLoader(sample_zip_path)
        sections = loader.parse_law_sections()
        filtered = loader.filter_sections(sections, target_codes=["LAB"])
        result = loader.to_statute_sections(filtered)
        s = [r for r in result if r.section_number == "1102.5"][0]
        assert s.amendment_info is not None
        assert "2023" in s.amendment_info

    def test_empty_content_skipped(self, tmp_path: Path):
        """Sections with empty HTML content should be skipped."""
        rows = [
            _make_dat_row(lob_file="empty.lob"),
        ]
        zip_bytes = _make_test_zip(rows, lob_files={"empty.lob": ""})
        zip_path = tmp_path / "test.zip"
        zip_path.write_bytes(zip_bytes)

        loader = PubinfoLoader(zip_path)
        sections = loader.parse_law_sections()
        result = loader.to_statute_sections(sections)
        assert len(result) == 0

    def test_heading_path_string(self, sample_zip_path: Path):
        loader = PubinfoLoader(sample_zip_path)
        sections = loader.parse_law_sections()
        filtered = loader.filter_sections(sections, target_codes=["LAB"])
        result = loader.to_statute_sections(filtered)
        s = [r for r in result if r.section_number == "1102.5"][0]
        path = s.heading_path
        assert "LAB" in path
        assert "Division" in path


# ── Dat Edge Cases ──────────────────────────────────────────


class TestDatEdgeCases:
    def test_short_rows_skipped(self, tmp_path: Path):
        """Rows with fewer than expected columns should be skipped."""
        rows = [
            "`1`\t`LAB`\t`100`",  # Too short
            _make_dat_row(id="2", section_num="200"),
        ]
        zip_bytes = _make_test_zip(rows, {"law_section_1.lob": "<p>Text</p>"})
        zip_path = tmp_path / "test.zip"
        zip_path.write_bytes(zip_bytes)

        loader = PubinfoLoader(zip_path)
        sections = loader.parse_law_sections()
        assert len(sections) == 1
        assert sections[0].section_num == "200"

    def test_empty_dat_file(self, tmp_path: Path):
        """Empty .dat file should produce no sections."""
        zip_bytes = _make_test_zip([], {})
        zip_path = tmp_path / "test.zip"
        zip_path.write_bytes(zip_bytes)

        loader = PubinfoLoader(zip_path)
        sections = loader.parse_law_sections()
        assert len(sections) == 0

    def test_missing_dat_file_raises(self, tmp_path: Path):
        """ZIP without LAW_SECTION_TBL.dat should raise FileNotFoundError."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("other_file.txt", "not a dat file")
        zip_path = tmp_path / "test.zip"
        zip_path.write_bytes(buf.getvalue())

        loader = PubinfoLoader(zip_path)
        with pytest.raises(FileNotFoundError, match="LAW_SECTION_TBL.dat"):
            loader.parse_law_sections()

    def test_lob_files_in_subdirectory(self, tmp_path: Path):
        """LOB files may be in a subdirectory within the ZIP."""
        rows = [
            _make_dat_row(id="1", lob_file="section.lob"),
        ]
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("LAW_SECTION_TBL.dat", "\n".join(rows))
            zf.writestr("lob_data/section.lob", "<p>Nested LOB content</p>")

        zip_path = tmp_path / "test.zip"
        zip_path.write_bytes(buf.getvalue())

        loader = PubinfoLoader(zip_path)
        sections = loader.parse_law_sections()
        assert len(sections) == 1
        assert "Nested LOB content" in sections[0].content_html


# ── Pipeline Integration Test ───────────────────────────────


class TestPipelineIntegration:
    def test_end_to_end_zip_to_chunks(self, sample_zip_path: Path, tmp_path: Path):
        """End-to-end: ZIP → PubinfoLoader → StatuteSections → chunks in DB."""
        from employee_help.processing.chunker import chunk_statute_section
        from employee_help.storage.models import (
            Chunk,
            ContentCategory,
            ContentType,
            Document,
            Source,
            SourceType,
        )
        from employee_help.storage.storage import Storage

        # 1. Load and filter sections from ZIP
        loader = PubinfoLoader(sample_zip_path)
        raw = loader.parse_law_sections()
        filtered = loader.filter_sections(raw, target_codes=["LAB"])
        sections = loader.to_statute_sections(filtered)
        assert len(sections) == 2

        # 2. Chunk each section
        all_chunks = []
        for section in sections:
            chunks = chunk_statute_section(
                section.text,
                citation=section.citation,
                heading_path=section.heading_path,
                max_tokens=2000,
            )
            all_chunks.append((section, chunks))

        # 3. Store in DB
        db_path = tmp_path / "test.db"
        storage = Storage(db_path)

        source = Source(
            name="California Labor Code",
            slug="labor_code",
            source_type=SourceType.STATUTORY_CODE,
            base_url="https://leginfo.legislature.ca.gov",
        )
        storage.create_source(source)
        run = storage.create_run(source_id=source.id)

        for section, chunks in all_chunks:
            if not chunks:
                continue
            doc = Document(
                source_url=section.source_url,
                title=section.citation,
                content_type=ContentType.HTML,
                raw_content=section.text,
                content_hash=chunks[0].content_hash,
                language="en",
                crawl_run_id=run.id,
                source_id=source.id,
                content_category=ContentCategory.STATUTORY_CODE,
            )
            stored_doc, is_new = storage.upsert_document(doc)
            assert is_new
            assert stored_doc.id is not None

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

        # 4. Verify
        doc_count = storage.get_document_count(source_id=source.id)
        chunk_count = storage.get_chunk_count(source_id=source.id)
        assert doc_count == 2
        assert chunk_count >= 2  # At least 1 chunk per section

        # Verify citation on stored chunks
        all_stored = storage.get_all_chunks(source_id=source.id)
        citations = {c.citation for c in all_stored}
        assert "Cal. Lab. Code § 1102.5" in citations
        assert "Cal. Lab. Code § 1101" in citations

        storage.close()

    def test_idempotent_upsert(self, sample_zip_path: Path, tmp_path: Path):
        """Running the same data twice should not duplicate documents."""
        from employee_help.processing.chunker import chunk_statute_section
        from employee_help.storage.models import (
            Chunk,
            ContentCategory,
            ContentType,
            Document,
            Source,
            SourceType,
        )
        from employee_help.storage.storage import Storage

        loader = PubinfoLoader(sample_zip_path)
        raw = loader.parse_law_sections()
        filtered = loader.filter_sections(raw, target_codes=["LAB"])
        sections = loader.to_statute_sections(filtered)

        db_path = tmp_path / "test.db"
        storage = Storage(db_path)
        source = Source(
            name="Labor Code", slug="labor_code",
            source_type=SourceType.STATUTORY_CODE,
            base_url="https://leginfo.legislature.ca.gov",
        )
        storage.create_source(source)

        for run_number in range(2):
            run = storage.create_run(source_id=source.id)
            for section in sections:
                chunks = chunk_statute_section(
                    section.text, citation=section.citation,
                    heading_path=section.heading_path,
                )
                if not chunks:
                    continue
                doc = Document(
                    source_url=section.source_url,
                    title=section.citation,
                    content_type=ContentType.HTML,
                    raw_content=section.text,
                    content_hash=chunks[0].content_hash,
                    language="en",
                    crawl_run_id=run.id,
                    source_id=source.id,
                    content_category=ContentCategory.STATUTORY_CODE,
                )
                stored_doc, is_new = storage.upsert_document(doc)
                if is_new and stored_doc.id:
                    chunk_objects = [
                        Chunk(
                            content=c.content, content_hash=c.content_hash,
                            chunk_index=c.chunk_index, heading_path=c.heading_path,
                            token_count=c.token_count, document_id=stored_doc.id,
                            content_category=ContentCategory.STATUTORY_CODE,
                            citation=section.citation,
                        )
                        for c in chunks
                    ]
                    storage.insert_chunks(chunk_objects)

        # Should still be exactly 2 documents after 2 runs
        assert storage.get_document_count(source_id=source.id) == 2
        storage.close()
