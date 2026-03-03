"""Tests for the DLSE Enforcement Policies and Interpretations Manual loader.

Uses unittest.mock for pdfplumber and httpx, plus respx for HTTP mocking.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from employee_help.scraper.extractors.dlse_manual import (
    MANUAL_PDF_URL,
    DLSEManualLoader,
    ManualChapter,
    _CHAPTER_START_RE,
    _SUBSECTION_RE,
)


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def loader(tmp_path):
    return DLSEManualLoader(download_dir=tmp_path)


def _make_page_text(header: bool = True, body: str = "") -> str:
    """Build a mock PDF page with optional standard header."""
    parts = []
    if header:
        parts.append("DIVISION OF LABOR STANDARDS ENFORCEMENT")
        parts.append("POLICIES AND INTERPRETATIONS MANUAL")
    parts.append(body)
    return "\n".join(parts)


def _make_chapter_page(number: int, title: str, body: str) -> str:
    """Build a mock PDF page containing a chapter heading and body text."""
    return _make_page_text(body=f"{number} {title}\n{body}")


# ── Regex Tests ──────────────────────────────────────────────


class TestChapterRegex:
    """Tests for chapter heading detection regex."""

    def test_simple_chapter(self):
        m = _CHAPTER_START_RE.match("2 WAGES.")
        assert m
        assert m.group(1) == "2"
        assert m.group(2).strip() == "WAGES."

    def test_chapter_with_period_number(self):
        m = _CHAPTER_START_RE.match("44. MINIMUM WAGE OBLIGATION.")
        assert m
        assert m.group(1) == "44"

    def test_chapter_with_dash(self):
        m = _CHAPTER_START_RE.match("17 RETALIATION AND DISCRIMINATION — PROTECTED RIGHTS")
        assert m
        assert m.group(1) == "17"

    def test_chapter_with_lowercase_words(self):
        m = _CHAPTER_START_RE.match("28 INDEPENDENT CONTRACTOR vs. EMPLOYEE.")
        assert m
        assert m.group(1) == "28"

    def test_chapter_with_year(self):
        m = _CHAPTER_START_RE.match("30 HEALTHY WORKPLACES, HEALTHY FAMILIES ACT OF 2014")
        assert m
        assert m.group(1) == "30"

    def test_chapter_with_apostrophe(self):
        m = _CHAPTER_START_RE.match("25 CONSTRUCTION INDUSTRY CONTRACTORS\u2019 REQUIREMENTS.")
        assert m
        assert m.group(1) == "25"

    def test_subsection_not_matched(self):
        assert _SUBSECTION_RE.match("2.1 Initially, it is necessary")
        assert _SUBSECTION_RE.match("44.1.3 Minimum Wage Covers")

    def test_intro_not_matched_by_chapter_re(self):
        """INTRODUCTION has no number prefix, handled separately."""
        assert _CHAPTER_START_RE.match("INTRODUCTION") is None


# ── Page Cleaning Tests ──────────────────────────────────────


class TestCleanPageText:

    def test_strips_standard_header(self):
        text = _make_page_text(body="2.1 Some content here")
        cleaned = DLSEManualLoader.clean_page_text(text)
        assert "DIVISION OF LABOR STANDARDS ENFORCEMENT" not in cleaned
        assert "POLICIES AND INTERPRETATIONS MANUAL" not in cleaned
        assert "2.1 Some content here" in cleaned

    def test_strips_page_number_footer(self):
        text = _make_page_text(body="Some content\n2 - 1")
        cleaned = DLSEManualLoader.clean_page_text(text)
        assert "2 - 1" not in cleaned
        assert "Some content" in cleaned

    def test_strips_date_footer(self):
        text = _make_page_text(body="Some content\nJUNE, 2002")
        cleaned = DLSEManualLoader.clean_page_text(text)
        assert "JUNE, 2002" not in cleaned

    def test_strips_trailing_combined_footer(self):
        text = _make_page_text(body="Some content\nDECEMBER 2022")
        cleaned = DLSEManualLoader.clean_page_text(text)
        assert "DECEMBER 2022" not in cleaned

    def test_preserves_body_content(self):
        text = _make_page_text(body="Important legal content about wages.")
        cleaned = DLSEManualLoader.clean_page_text(text)
        assert "Important legal content about wages." in cleaned

    def test_empty_page(self):
        cleaned = DLSEManualLoader.clean_page_text("")
        assert cleaned == ""


# ── Chapter Parsing Tests ────────────────────────────────────


class TestParseChapters:

    def test_parses_single_chapter(self, loader):
        pages = [""] * 9  # Title + TOC pages (skipped)
        pages.append(_make_page_text(body="INTRODUCTION\n1.1 Primary function of DLSE."))
        chapters = loader.parse_chapters(pages)
        assert len(chapters) == 1
        assert chapters[0].number == "1"
        assert chapters[0].title == "INTRODUCTION"
        assert "Primary function" in chapters[0].text

    def test_parses_multiple_chapters(self, loader):
        pages = [""] * 9  # TOC
        pages.append(_make_page_text(body="INTRODUCTION\n1.1 Intro text."))
        pages.append(_make_chapter_page(2, "WAGES.", "2.1 Wages defined."))
        pages.append(_make_chapter_page(3, "WAGES PAYABLE ON TERMINATION.", "3.1 Labor Code."))
        chapters = loader.parse_chapters(pages)
        assert len(chapters) == 3
        assert chapters[0].number == "1"
        assert chapters[1].number == "2"
        assert chapters[2].number == "3"

    def test_chapter_accumulates_multi_page(self, loader):
        pages = [""] * 9
        pages.append(_make_chapter_page(2, "WAGES.", "2.1 First part."))
        pages.append(_make_page_text(body="2.2 Second part on next page."))
        pages.append(_make_chapter_page(3, "TERMINATION.", "3.1 New chapter."))
        chapters = loader.parse_chapters(pages)
        assert len(chapters) == 2
        assert "First part" in chapters[0].text
        assert "Second part" in chapters[0].text

    def test_stops_at_addendum(self, loader):
        pages = [""] * 9
        pages.append(_make_chapter_page(2, "WAGES.", "2.1 Content."))
        pages.append(_make_page_text(body="Opinion Letter Index\nSome index data."))
        chapters = loader.parse_chapters(pages)
        assert len(chapters) == 1

    def test_skips_toc_pages(self, loader):
        pages = []
        pages.append("Title page")
        for i in range(8):
            pages.append(f"TABLE OF CONTENTS page {i}")
        pages.append(_make_chapter_page(2, "WAGES.", "2.1 Content."))
        chapters = loader.parse_chapters(pages)
        assert len(chapters) == 1
        assert chapters[0].number == "2"

    def test_chapter_with_period_number_format(self, loader):
        """Chapter 44 uses '44. MINIMUM WAGE OBLIGATION.' format."""
        pages = [""] * 9
        pages.append(_make_page_text(body="44. MINIMUM WAGE OBLIGATION.\n44.1 The chart below."))
        chapters = loader.parse_chapters(pages)
        assert len(chapters) == 1
        assert chapters[0].number == "44"

    def test_empty_pages_handled(self, loader):
        pages = [""] * 9
        pages.append("")
        pages.append("")
        pages.append(_make_chapter_page(2, "WAGES.", "2.1 Content."))
        chapters = loader.parse_chapters(pages)
        assert len(chapters) == 1

    def test_subsection_not_treated_as_chapter(self, loader):
        pages = [""] * 9
        pages.append(_make_chapter_page(2, "WAGES.", "2.1 Subsection one.\n2.2 Subsection two."))
        chapters = loader.parse_chapters(pages)
        assert len(chapters) == 1
        assert "Subsection one" in chapters[0].text
        assert "Subsection two" in chapters[0].text


# ── ManualChapter Tests ──────────────────────────────────────


class TestManualChapter:

    def test_clean_title_basic(self):
        ch = ManualChapter(number="2", title="WAGES.", text="", start_page=0)
        assert ch.clean_title == "Wages"

    def test_clean_title_multi_word(self):
        ch = ManualChapter(number="3", title="WAGES PAYABLE ON TERMINATION.", text="", start_page=0)
        assert ch.clean_title == "Wages Payable On Termination"

    def test_clean_title_preserves_acronyms(self):
        ch = ManualChapter(number="50", title="IWC ORDERS EXEMPTIONS.", text="", start_page=0)
        assert "IWC" in ch.clean_title

    def test_clean_title_with_dash(self):
        ch = ManualChapter(number="17", title="RETALIATION AND DISCRIMINATION — PROTECTED RIGHTS", text="", start_page=0)
        cleaned = ch.clean_title
        assert "Retaliation" in cleaned
        assert "Protected" in cleaned


# ── PDF Download Tests ───────────────────────────────────────


class TestEnsurePdf:

    def test_returns_existing_pdf_path(self, tmp_path):
        pdf_path = tmp_path / "manual.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")
        loader = DLSEManualLoader(pdf_path=pdf_path)
        result = loader.ensure_pdf()
        assert result == pdf_path

    def test_returns_cached_download(self, tmp_path):
        cached = tmp_path / "dlse_enfcmanual.pdf"
        cached.write_bytes(b"%PDF-1.4 cached")
        loader = DLSEManualLoader(download_dir=tmp_path)
        result = loader.ensure_pdf()
        assert result == cached

    @respx.mock
    def test_downloads_pdf_when_missing(self, tmp_path):
        respx.get(MANUAL_PDF_URL).mock(
            return_value=httpx.Response(200, content=b"%PDF-1.4 fresh")
        )
        loader = DLSEManualLoader(download_dir=tmp_path)
        result = loader.ensure_pdf()
        assert result.exists()
        assert result.read_bytes() == b"%PDF-1.4 fresh"

    @respx.mock
    def test_download_failure_raises(self, tmp_path):
        respx.get(MANUAL_PDF_URL).mock(
            return_value=httpx.Response(500)
        )
        loader = DLSEManualLoader(download_dir=tmp_path)
        with pytest.raises(httpx.HTTPStatusError):
            loader.ensure_pdf()


# ── Page Extraction Tests ────────────────────────────────────


class TestExtractPages:

    def test_extracts_all_pages(self, tmp_path):
        mock_page1 = MagicMock()
        mock_page1.extract_text.return_value = "Page 1 text"
        mock_page2 = MagicMock()
        mock_page2.extract_text.return_value = "Page 2 text"

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page1, mock_page2]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF")

        loader = DLSEManualLoader(download_dir=tmp_path)
        with patch("employee_help.scraper.extractors.dlse_manual.pdfplumber") as mock_pdfplumber:
            mock_pdfplumber.open.return_value = mock_pdf
            pages = loader.extract_pages(pdf_path)

        assert len(pages) == 2
        assert pages[0] == "Page 1 text"

    def test_handles_none_page_text(self, tmp_path):
        mock_page = MagicMock()
        mock_page.extract_text.return_value = None

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF")

        loader = DLSEManualLoader(download_dir=tmp_path)
        with patch("employee_help.scraper.extractors.dlse_manual.pdfplumber") as mock_pdfplumber:
            mock_pdfplumber.open.return_value = mock_pdf
            pages = loader.extract_pages(pdf_path)

        assert pages == [""]


# ── StatuteSection Conversion Tests ──────────────────────────


class TestToStatuteSections:

    def test_converts_chapters_to_sections(self):
        chapters = [
            ManualChapter(number="2", title="WAGES.", text="Section about wages.", start_page=13),
            ManualChapter(number="3", title="TERMINATION.", text="Section about termination.", start_page=17),
        ]
        loader = DLSEManualLoader()
        sections = loader.to_statute_sections(chapters)
        assert len(sections) == 2

    def test_section_fields_correct(self):
        chapters = [
            ManualChapter(number="2", title="WAGES.", text="Content about wages.", start_page=13),
        ]
        loader = DLSEManualLoader()
        sections = loader.to_statute_sections(chapters)
        s = sections[0]
        assert s.section_number == "2"
        assert s.code_abbreviation == "DLSE-Manual"
        assert s.citation == "DLSE Enforcement Manual Ch. 2"
        assert "Content about wages." in s.text
        assert s.source_url == f"{MANUAL_PDF_URL}#chapter-2"

    def test_heading_path_format(self):
        chapters = [
            ManualChapter(number="17", title="RETALIATION AND DISCRIMINATION — PROTECTED RIGHTS", text="Content.", start_page=66),
        ]
        loader = DLSEManualLoader()
        sections = loader.to_statute_sections(chapters)
        hp = sections[0].heading_path
        assert hp.startswith("DLSE Enforcement Manual > ")
        assert "Retaliation" in hp

    def test_unique_source_urls(self):
        chapters = [
            ManualChapter(number="2", title="WAGES.", text="A", start_page=13),
            ManualChapter(number="3", title="TERMINATION.", text="B", start_page=17),
        ]
        loader = DLSEManualLoader()
        sections = loader.to_statute_sections(chapters)
        urls = [s.source_url for s in sections]
        assert len(set(urls)) == 2

    def test_skips_empty_chapters(self):
        chapters = [
            ManualChapter(number="2", title="WAGES.", text="Content.", start_page=13),
            ManualChapter(number="3", title="EMPTY.", text="", start_page=17),
        ]
        loader = DLSEManualLoader()
        sections = loader.to_statute_sections(chapters)
        assert len(sections) == 1
        assert sections[0].section_number == "2"

    def test_full_pipeline_with_mocked_pdf(self, tmp_path):
        """Test to_statute_sections() without chapters arg triggers PDF parsing."""
        loader = DLSEManualLoader(download_dir=tmp_path)

        # Build mock pages
        mock_pages = [""] * 9  # TOC
        mock_pages.append(_make_chapter_page(2, "WAGES.", "2.1 Wages content."))
        mock_pages.append(_make_chapter_page(3, "TERMINATION.", "3.1 Term content."))

        pdf_path = tmp_path / "dlse_enfcmanual.pdf"
        pdf_path.write_bytes(b"%PDF")

        with (
            patch.object(loader, "ensure_pdf", return_value=pdf_path),
            patch.object(loader, "extract_pages", return_value=mock_pages),
        ):
            sections = loader.to_statute_sections()

        assert len(sections) == 2


# ── Config + Integration Tests ───────────────────────────────


class TestDLSEManualConfig:

    def test_config_loads_from_yaml(self):
        from employee_help.config import load_source_config

        config = load_source_config("config/sources/dlse_manual.yaml")
        assert config.slug == "dlse_manual"
        assert config.source_type.value == "statutory_code"
        assert config.statutory is not None
        assert config.statutory.method == "dlse_manual"
        assert config.statutory.code_abbreviation == "DLSE-Manual"
        assert config.extraction.content_category == "enforcement_manual"

    def test_content_category_enum_exists(self):
        from employee_help.storage.models import ContentCategory

        cat = ContentCategory("enforcement_manual")
        assert cat == ContentCategory.ENFORCEMENT_MANUAL

    def test_enforcement_manual_in_consumer_categories(self):
        from employee_help.retrieval.service import CONSUMER_CATEGORIES

        assert "enforcement_manual" in CONSUMER_CATEGORIES


@pytest.mark.slow
class TestDLSEManualLive:
    """Integration tests that parse the real DLSE manual PDF.

    Only run with: pytest -m slow
    """

    def test_parse_all_chapters_from_real_pdf(self):
        pdf_path = Path("data/dlse_manual/dlse_enfcmanual.pdf")
        if not pdf_path.exists():
            pytest.skip("Manual PDF not downloaded")

        loader = DLSEManualLoader(pdf_path=pdf_path)
        pages = loader.extract_pages(pdf_path)
        chapters = loader.parse_chapters(pages)
        # Expect 50+ chapters (manual has 56 chapters 1-56)
        assert len(chapters) >= 50

    def test_all_chapters_have_content(self):
        pdf_path = Path("data/dlse_manual/dlse_enfcmanual.pdf")
        if not pdf_path.exists():
            pytest.skip("Manual PDF not downloaded")

        loader = DLSEManualLoader(pdf_path=pdf_path)
        pages = loader.extract_pages(pdf_path)
        chapters = loader.parse_chapters(pages)
        for ch in chapters:
            assert ch.text.strip(), f"Chapter {ch.number} ({ch.title}) has no text"
            assert len(ch.text) > 50, f"Chapter {ch.number} suspiciously short: {len(ch.text)} chars"

    def test_to_statute_sections_produces_results(self):
        pdf_path = Path("data/dlse_manual/dlse_enfcmanual.pdf")
        if not pdf_path.exists():
            pytest.skip("Manual PDF not downloaded")

        loader = DLSEManualLoader(pdf_path=pdf_path)
        sections = loader.to_statute_sections()
        assert len(sections) >= 50
        for s in sections:
            assert s.text.strip()
            assert s.citation
            assert s.source_url
