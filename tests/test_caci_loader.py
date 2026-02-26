"""Tests for the CACI (California Civil Jury Instructions) PDF loader."""

from __future__ import annotations

import io
import re
from unittest.mock import MagicMock, patch

import pytest

from employee_help.scraper.extractors.caci import (
    EMPLOYMENT_SERIES,
    CACIInstruction,
    CACILoader,
    _get_series_name,
    _is_employment_instruction,
    _is_toc_page,
    _parse_instruction_number,
    _strip_page_header_footer,
)


class TestHelperFunctions:
    """Tests for module-level helper functions."""

    def test_parse_instruction_number_plain(self):
        assert _parse_instruction_number("2430") == 2430

    def test_parse_instruction_number_with_letter(self):
        assert _parse_instruction_number("2521A") == 2521

    def test_is_employment_instruction_in_range(self):
        assert _is_employment_instruction("2400") is True
        assert _is_employment_instruction("2500") is True
        assert _is_employment_instruction("2600") is True
        assert _is_employment_instruction("2700") is True
        assert _is_employment_instruction("2800") is True
        assert _is_employment_instruction("4600") is True

    def test_is_employment_instruction_out_of_range(self):
        assert _is_employment_instruction("1000") is False
        assert _is_employment_instruction("3000") is False
        assert _is_employment_instruction("4500") is False

    def test_is_employment_instruction_letter_suffix(self):
        assert _is_employment_instruction("2521A") is True
        assert _is_employment_instruction("2766B") is True

    def test_get_series_name(self):
        assert _get_series_name("2430") == "Wrongful Termination"
        assert _get_series_name("2500") == "FEHA Discrimination and Harassment"
        assert _get_series_name("2600") == "CFRA Leave"
        assert _get_series_name("2700") == "Labor Code Violations"
        assert _get_series_name("2800") == "Workers' Compensation"
        assert _get_series_name("4600") == "Whistleblower Protection"

    def test_get_series_name_letter_suffix(self):
        assert _get_series_name("2521A") == "FEHA Discrimination and Harassment"

    def test_is_toc_page_series_header(self):
        text = "WRONGFUL TERMINATION\n2400. Breach of ...\n2401. Breach of ..."
        assert _is_toc_page(text) is True

    def test_is_toc_page_volume_toc(self):
        # Page with 3+ instruction number matches
        text = "Volume 1\n2400. First\n2401. Second\n2402. Third\n"
        assert _is_toc_page(text) is True

    def test_is_toc_page_content_page(self):
        # Content page with just one instruction start
        text = "2400. Breach of Employment Contract\nSome body text here...\n"
        assert _is_toc_page(text) is False

    def test_is_toc_page_empty(self):
        assert _is_toc_page("") is False
        assert _is_toc_page("   ") is False

    def test_strip_page_header_footer(self):
        text = "CACI No. 2400 WRONGFULTERMINATION\nSome content here\n1460"
        cleaned = _strip_page_header_footer(text)
        assert "CACI No. 2400" not in cleaned
        assert "1460" not in cleaned
        assert "Some content here" in cleaned

    def test_strip_page_header_right_format(self):
        text = "WRONGFULTERMINATION CACI No. 2401\nMore content\n1463"
        cleaned = _strip_page_header_footer(text)
        assert "CACI No. 2401" not in cleaned
        assert "More content" in cleaned

    def test_strip_vf_headers(self):
        text = "VF-2400 WRONGFULTERMINATION\nVerdict form content\n1505"
        cleaned = _strip_page_header_footer(text)
        assert "VF-2400" not in cleaned

    def test_strip_page_header_letter_suffix(self):
        text = "CACI No. 2521A FAIREMPLOYMENTANDHOUSINGACT\nHarassment content\n1661"
        cleaned = _strip_page_header_footer(text)
        assert "CACI No. 2521A" not in cleaned
        assert "Harassment content" in cleaned


class TestCACIInstruction:
    """Tests for CACIInstruction dataclass."""

    def test_citation(self):
        inst = CACIInstruction(number="2430", title="Test", series="Wrongful Termination")
        assert inst.citation == "CACI No. 2430"

    def test_citation_letter_suffix(self):
        inst = CACIInstruction(number="2521A", title="Test", series="FEHA")
        assert inst.citation == "CACI No. 2521A"

    def test_to_statute_sections_all_sections(self):
        inst = CACIInstruction(
            number="2430",
            title="Wrongful Discharge",
            series="Wrongful Termination",
            instruction_text="Elements of claim...",
            directions_for_use="When to give this instruction...",
            sources_and_authority="Case law citations...",
            secondary_sources="Treatise references...",
        )
        sections = inst.to_statute_sections()
        # 3 sections: instruction text, directions, sources (secondary merged)
        assert len(sections) == 3

    def test_to_statute_sections_headings(self):
        inst = CACIInstruction(
            number="2430",
            title="Wrongful Discharge",
            series="Wrongful Termination",
            instruction_text="Elements...",
            directions_for_use="Directions...",
            sources_and_authority="Sources...",
        )
        sections = inst.to_statute_sections()
        headings = [s.heading_path for s in sections]
        assert any("Instruction Text" in h for h in headings)
        assert any("Directions for Use" in h for h in headings)
        assert any("Sources and Authority" in h for h in headings)
        # All should have the hierarchy
        for h in headings:
            assert "CACI > Wrongful Termination > No. 2430" in h

    def test_to_statute_sections_citations(self):
        inst = CACIInstruction(
            number="2500",
            title="Disparate Treatment",
            series="FEHA",
            instruction_text="Text...",
        )
        sections = inst.to_statute_sections()
        assert all(s.citation == "CACI No. 2500" for s in sections)

    def test_to_statute_sections_unique_urls(self):
        """Each section should have a unique source_url for upsert_document dedup."""
        inst = CACIInstruction(
            number="2430",
            title="Test",
            series="Wrongful Termination",
            instruction_text="Text...",
            directions_for_use="Directions...",
            sources_and_authority="Sources...",
        )
        sections = inst.to_statute_sections()
        urls = [s.source_url for s in sections]
        assert len(urls) == len(set(urls)), "source_url must be unique per section"
        # Each URL should contain the instruction number
        for url in urls:
            assert "2430" in url

    def test_to_statute_sections_empty_sections_skipped(self):
        inst = CACIInstruction(
            number="2400",
            title="Test",
            series="Wrongful Termination",
            instruction_text="Only instruction text.",
            directions_for_use="",
            sources_and_authority="",
        )
        sections = inst.to_statute_sections()
        assert len(sections) == 1
        assert "Instruction Text" in sections[0].heading_path

    def test_secondary_sources_merged_into_sources(self):
        inst = CACIInstruction(
            number="2430",
            title="Test",
            series="Wrongful Termination",
            instruction_text="Text...",
            sources_and_authority="Main sources.",
            secondary_sources="Secondary treatises.",
        )
        sections = inst.to_statute_sections()
        sources_section = [s for s in sections if "Sources" in s.heading_path]
        assert len(sources_section) == 1
        assert "Secondary Sources" in sources_section[0].text
        assert "Secondary treatises." in sources_section[0].text


class TestCACILoaderInit:
    """Tests for CACILoader initialization."""

    def test_init_raises_on_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="CACI PDF not found"):
            CACILoader(tmp_path / "nonexistent.pdf")

    def test_init_with_valid_path(self, tmp_path):
        pdf_path = tmp_path / "test.pdf"
        pdf_path.touch()
        loader = CACILoader(pdf_path)
        assert loader.pdf_path == pdf_path


class TestCACILoaderParsing:
    """Tests for CACILoader PDF parsing (using mocked PDF pages)."""

    def _make_loader_with_pages(self, pages: list[str], tmp_path) -> CACILoader:
        """Create a CACILoader with mocked _extract_pages."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.touch()
        loader = CACILoader(pdf_path)
        loader._extract_pages = lambda: pages  # type: ignore[assignment]
        return loader

    def test_parse_single_instruction(self, tmp_path):
        pages = [
            (
                "2430. Wrongful Discharge in Violation of Public Policy\n"
                "[Name of plaintiff] claims wrongful discharge.\n"
                "1. That defendant discharged plaintiff;\n"
                "2. That the discharge violated public policy.\n"
                "New September 2003; Revised June 2006\n"
                "Directions for Use\n"
                "The judge should determine whether the reason is valid.\n"
                "Sources and Authority\n"
                "Case law: Tameny v. Atlantic Richfield Co.\n"
                "Secondary Sources\n"
                "3 Witkin, Summary of California Law\n"
                "1540\n"
            ),
        ]
        loader = self._make_loader_with_pages(pages, tmp_path)
        instructions = loader.parse_instructions()

        assert len(instructions) == 1
        inst = instructions[0]
        assert inst.number == "2430"
        assert "Wrongful Discharge" in inst.title
        assert inst.series == "Wrongful Termination"
        assert "[Name of plaintiff]" in inst.instruction_text
        assert "judge should determine" in inst.directions_for_use
        assert "Tameny" in inst.sources_and_authority
        assert "Witkin" in inst.secondary_sources

    def test_skip_toc_pages(self, tmp_path):
        pages = [
            # TOC page (series header)
            (
                "WRONGFUL TERMINATION\n"
                "2400. Breach of Employment Contract\n"
                "2401. Breach Actual or Constructive\n"
                "2430. Wrongful Discharge\n"
                "1457\n"
            ),
            # Content page
            (
                "2430. Wrongful Discharge\n"
                "[Name of plaintiff] claims wrongful discharge.\n"
                "New September 2003\n"
                "1540\n"
            ),
        ]
        loader = self._make_loader_with_pages(pages, tmp_path)
        instructions = loader.parse_instructions()

        assert len(instructions) == 1
        assert instructions[0].number == "2430"

    def test_skip_vf_entries(self, tmp_path):
        pages = [
            (
                "2430. Wrongful Discharge\n"
                "[Name of plaintiff] claims wrongful discharge.\n"
                "New September 2003\n"
                "1540\n"
            ),
            (
                "VF-2400. Breach of Employment Contract\n"
                "We answer the questions submitted...\n"
                "1505\n"
            ),
        ]
        loader = self._make_loader_with_pages(pages, tmp_path)
        instructions = loader.parse_instructions()

        assert len(instructions) == 1
        assert instructions[0].number == "2430"

    def test_skip_reserved_entries(self, tmp_path):
        pages = [
            (
                "2430. Wrongful Discharge\n"
                "Some text.\n"
                "New September 2003\n"
                "2431. Reserved for Future Use\n"
                "1540\n"
            ),
        ]
        loader = self._make_loader_with_pages(pages, tmp_path)
        instructions = loader.parse_instructions()

        assert len(instructions) == 1
        assert instructions[0].number == "2430"

    def test_filter_employment_series_only(self, tmp_path):
        pages = [
            # Non-employment instruction
            (
                "1000. General Negligence\n"
                "Some negligence text.\n"
                "New September 2003\n"
                "100\n"
            ),
            # Employment instruction
            (
                "2500. Disparate Treatment\n"
                "Discrimination claims...\n"
                "New September 2003\n"
                "1530\n"
            ),
        ]
        loader = self._make_loader_with_pages(pages, tmp_path)
        instructions = loader.parse_instructions()

        assert len(instructions) == 1
        assert instructions[0].number == "2500"

    def test_letter_suffix_instructions(self, tmp_path):
        pages = [
            (
                "2521A. Work Environment Harassment—Conduct Directed at\n"
                "Plaintiff—Essential Factual Elements\n"
                "[Name of plaintiff] claims harassment.\n"
                "New December 2007\n"
                "1660\n"
            ),
        ]
        loader = self._make_loader_with_pages(pages, tmp_path)
        instructions = loader.parse_instructions()

        assert len(instructions) == 1
        assert instructions[0].number == "2521A"
        assert instructions[0].series == "FEHA Discrimination and Harassment"

    def test_multi_page_instruction(self, tmp_path):
        pages = [
            (
                "2430. Wrongful Discharge\n"
                "[Name of plaintiff] claims wrongful discharge.\n"
                "New September 2003\n"
                "Directions for Use\n"
                "First page of directions.\n"
                "1540\n"
            ),
            (
                "CACI No. 2430 WRONGFULTERMINATION\n"
                "Continuation of directions.\n"
                "Sources and Authority\n"
                "Case citations here.\n"
                "1541\n"
            ),
        ]
        loader = self._make_loader_with_pages(pages, tmp_path)
        instructions = loader.parse_instructions()

        assert len(instructions) == 1
        inst = instructions[0]
        assert "First page of directions" in inst.directions_for_use
        assert "Continuation of directions" in inst.directions_for_use
        assert "Case citations" in inst.sources_and_authority

    def test_date_line_stripped_from_instruction_text(self, tmp_path):
        pages = [
            (
                "2400. At-Will Presumption\n"
                "Employment is at will.\n"
                "New September 2003; Revised June 2006\n"
                "Directions for Use\n"
                "Some directions.\n"
                "1459\n"
            ),
        ]
        loader = self._make_loader_with_pages(pages, tmp_path)
        instructions = loader.parse_instructions()

        assert "New September 2003" not in instructions[0].instruction_text
        assert "Employment is at will" in instructions[0].instruction_text

    def test_to_statute_sections_integration(self, tmp_path):
        pages = [
            (
                "2430. Wrongful Discharge\n"
                "[Name of plaintiff] claims wrongful discharge.\n"
                "New September 2003\n"
                "Directions for Use\n"
                "Give this instruction when...\n"
                "Sources and Authority\n"
                "Tameny v. Atlantic Richfield\n"
                "1540\n"
            ),
        ]
        loader = self._make_loader_with_pages(pages, tmp_path)
        sections = loader.to_statute_sections()

        assert len(sections) == 3
        assert all(s.citation == "CACI No. 2430" for s in sections)
        assert all(s.code_abbreviation == "CACI" for s in sections)
        assert any("Instruction Text" in s.heading_path for s in sections)


class TestCACILoaderLive:
    """Tests against the real CACI PDF (only run if file exists)."""

    @pytest.fixture
    def loader(self):
        from pathlib import Path
        pdf_path = Path("data/caci/caci_2026.pdf")
        if not pdf_path.exists():
            pytest.skip("CACI PDF not available")
        return CACILoader(pdf_path)

    @pytest.mark.slow
    def test_parse_employment_instructions_count(self, loader):
        """Should parse ~100+ employment instructions."""
        instructions = loader.parse_instructions()
        assert len(instructions) >= 100
        assert len(instructions) <= 200

    @pytest.mark.slow
    def test_all_instructions_have_text(self, loader):
        """Every parsed instruction should have non-empty instruction text."""
        instructions = loader.parse_instructions()
        for inst in instructions:
            assert inst.instruction_text.strip(), (
                f"{inst.citation} has empty instruction_text"
            )

    @pytest.mark.slow
    def test_no_duplicate_instructions(self, loader):
        """No instruction number should appear more than once."""
        instructions = loader.parse_instructions()
        numbers = [inst.number for inst in instructions]
        assert len(numbers) == len(set(numbers)), (
            f"Duplicates found: {[n for n in numbers if numbers.count(n) > 1]}"
        )

    @pytest.mark.slow
    def test_all_series_represented(self, loader):
        """All 6 employment series should have at least one instruction."""
        instructions = loader.parse_instructions()
        series_found = {inst.series for inst in instructions}
        expected = {
            "Wrongful Termination",
            "FEHA Discrimination and Harassment",
            "CFRA Leave",
            "Labor Code Violations",
            "Workers' Compensation",
            "Whistleblower Protection",
        }
        assert expected == series_found

    @pytest.mark.slow
    def test_2521a_harassment_parsed(self, loader):
        """CACI 2521A (sexual harassment) should be correctly parsed."""
        instructions = loader.parse_instructions()
        inst_2521a = next(
            (i for i in instructions if i.number == "2521A"), None
        )
        assert inst_2521a is not None, "2521A not found"
        assert "harassment" in inst_2521a.title.lower()
        assert inst_2521a.instruction_text
        assert inst_2521a.directions_for_use
        assert inst_2521a.sources_and_authority

    @pytest.mark.slow
    def test_statute_sections_count(self, loader):
        """Should produce 250-500 StatuteSections (3 per instruction avg)."""
        sections = loader.to_statute_sections()
        assert 250 <= len(sections) <= 500
