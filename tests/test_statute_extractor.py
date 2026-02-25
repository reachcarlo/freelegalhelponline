"""Tests for the statutory code extractor and section-boundary chunking."""

import pytest

from employee_help.scraper.extractors.statute import (
    BASE_URL,
    HierarchyPath,
    StatuteSection,
    TocEntry,
    build_citation,
    parse_display_text_page,
    parse_toc_page,
)
from employee_help.processing.chunker import (
    chunk_statute_section,
    estimate_tokens,
)


# ── Fixtures ─────────────────────────────────────────────────


SAMPLE_TOC_HTML = """
<html><body>
<div id="content_anchor"></div>
<h3>Labor Code - LAB</h3>
<a href="/faces/codes_displayText.xhtml?lawCode=LAB&division=1.&title=&part=&chapter=1.&article=">
  CHAPTER 1. Definitions [2 - 27.1]
</a>
<a href="/faces/codes_displayText.xhtml?lawCode=LAB&division=2.&title=&part=3.&chapter=5.&article=">
  CHAPTER 5. Political Affiliations [1101 - 1106]
</a>
<a href="/faces/codes_displayText.xhtml?lawCode=LAB&division=2.&title=&part=3.&chapter=5.&article=1.">
  ARTICLE 1. Some Article [1101 - 1103]
</a>
<a href="/faces/codes_displayexpandedbranch.xhtml?tocCode=LAB&division=3.">
  Division 3 (not a displayText link)
</a>
</body></html>
"""


SAMPLE_DISPLAY_TEXT_HTML = """
<html><body>
<div id="content_anchor">
<h4>Labor Code - LAB</h4>
<h4>DIVISION 2. EMPLOYMENT REGULATION AND SUPERVISION [200 - 2699.8]</h4>
<h5>PART 3. Privileges and Immunities [920 - 1138.5]</h5>
<h5>CHAPTER 5. Political Affiliations [1101 - 1106]</h5>
<h6>1101.</h6>
<p>No employer shall make, adopt, or enforce any rule, regulation, or policy:</p>
<p>(a) Forbidding or preventing employees from engaging or participating in politics.</p>
<p>(b) Controlling or directing the political activities of employees.</p>
<em>(Added by Stats. 1937, Ch. 90.)</em>
<h6>1102.</h6>
<p>No employer shall coerce or influence or attempt to coerce or influence his employees through or by means of threat of discharge or loss of employment to adopt or follow or refrain from adopting or following any particular course or line of political action or political activity.</p>
<em>(Added by Stats. 1937, Ch. 90.)</em>
<h6>1102.5.</h6>
<p>(a) An employer, or any person acting on behalf of the employer, shall not retaliate against an employee for disclosing information, or because the employer believes that the employee disclosed or may disclose information, to a government or law enforcement agency.</p>
<p>(b) An employer, or any person acting on behalf of the employer, shall not retaliate against an employee for refusing to participate in an activity that would result in a violation of state or federal statute.</p>
<p>(c) An employer, or any person acting on behalf of the employer, shall not retaliate against an employee for having exercised his or her rights under subdivision (a) or (b) in any former employment.</p>
<p>(d) An employer, or any person acting on behalf of the employer, shall not retaliate against an employee because the employee is a family member of a person who has, or is perceived to have, engaged in any acts protected under this section.</p>
<em>(Amended by Stats. 2023, Ch. 612, Sec. 2. (SB 497) Effective January 1, 2024.)</em>
</div>
</body></html>
"""


SAMPLE_DISPLAY_TEXT_NO_CONTENT_ANCHOR = """
<html><body>
<h5>CHAPTER 1. Test [1 - 5]</h5>
<h6>1.</h6>
<p>Section one text.</p>
<em>(Added by Stats. 2020, Ch. 1.)</em>
<h6>2.</h6>
<p>Section two text.</p>
<em>(Added by Stats. 2020, Ch. 1.)</em>
</body></html>
"""


# ── Citation Tests ───────────────────────────────────────────


class TestBuildCitation:
    def test_labor_code(self):
        assert build_citation("LAB", "1102.5") == "Cal. Lab. Code § 1102.5"

    def test_government_code(self):
        assert build_citation("GOV", "12940") == "Cal. Gov. Code § 12940"

    def test_unemployment_insurance_code(self):
        assert build_citation("UIC", "1256") == "Cal. Unemp. Ins. Code § 1256"

    def test_unknown_code(self):
        assert build_citation("XYZ", "100") == "Cal. XYZ § 100"

    def test_decimal_section_number(self):
        assert build_citation("LAB", "226.7") == "Cal. Lab. Code § 226.7"

    def test_code_civil_procedure(self):
        assert build_citation("CCP", "340") == "Cal. Code Civ. Proc. § 340"

    def test_business_professions(self):
        assert build_citation("BPC", "16600") == "Cal. Bus. & Prof. Code § 16600"


# ── Hierarchy Tests ──────────────────────────────────────────


class TestHierarchyPath:
    def test_full_path(self):
        h = HierarchyPath(
            code_name="LAB",
            division="DIVISION 2. Employment",
            part="PART 3. Privileges",
            chapter="CHAPTER 5. Political",
        )
        assert "LAB" in h.to_path_string()
        assert "DIVISION 2" in h.to_path_string()
        assert "CHAPTER 5" in h.to_path_string()

    def test_minimal_path(self):
        h = HierarchyPath(code_name="LAB")
        assert h.to_path_string() == "LAB"

    def test_skipped_levels(self):
        h = HierarchyPath(code_name="GOV", division="Division 3", chapter="Chapter 1")
        path = h.to_path_string()
        assert "GOV" in path
        assert "Division 3" in path
        assert "Chapter 1" in path


# ── TOC Parsing Tests ────────────────────────────────────────


class TestParseTocPage:
    def test_finds_display_text_links(self):
        entries = parse_toc_page(SAMPLE_TOC_HTML, "LAB")
        # Should find 3 displayText links, not the expandedbranch link
        assert len(entries) == 3

    def test_all_entries_have_urls(self):
        entries = parse_toc_page(SAMPLE_TOC_HTML, "LAB")
        for entry in entries:
            assert "codes_displayText.xhtml" in entry.url
            assert entry.url.startswith("http")

    def test_hierarchy_has_code_name(self):
        entries = parse_toc_page(SAMPLE_TOC_HTML, "LAB")
        for entry in entries:
            assert entry.hierarchy.code_name == "LAB"

    def test_filter_by_division(self):
        entries = parse_toc_page(SAMPLE_TOC_HTML, "LAB", target_divisions=["2."])
        # Only entries with division=2. should be included
        assert all("division=2." in e.url for e in entries)
        assert len(entries) == 2  # Chapter 5 and Article 1

    def test_filter_excludes_other_divisions(self):
        entries = parse_toc_page(SAMPLE_TOC_HTML, "LAB", target_divisions=["99."])
        assert len(entries) == 0

    def test_no_filter_returns_all(self):
        entries = parse_toc_page(SAMPLE_TOC_HTML, "LAB", target_divisions=None)
        assert len(entries) == 3

    def test_filter_excludes_empty_division_entries(self):
        """Links with empty division= should be excluded when filtering."""
        html = """
        <html><body>
        <a href="/faces/codes_displayText.xhtml?lawCode=GOV&division=3.&title=2.&chapter=1.">
          Chapter 1 [100 - 200]
        </a>
        <a href="/faces/codes_displayText.xhtml?lawCode=GOV&division=&title=1.&chapter=1.">
          Title 1 Chapter (no division)
        </a>
        </body></html>
        """
        entries = parse_toc_page(html, "GOV", target_divisions=["3."])
        assert len(entries) == 1
        assert "division=3." in entries[0].url


# ── Section Parsing Tests ────────────────────────────────────


class TestParseDisplayTextPage:
    def test_extracts_sections(self):
        hierarchy = HierarchyPath(code_name="LAB", division="Division 2", chapter="Chapter 5")
        sections = parse_display_text_page(SAMPLE_DISPLAY_TEXT_HTML, "LAB", hierarchy)
        assert len(sections) == 3

    def test_section_numbers(self):
        hierarchy = HierarchyPath(code_name="LAB")
        sections = parse_display_text_page(SAMPLE_DISPLAY_TEXT_HTML, "LAB", hierarchy)
        numbers = [s.section_number for s in sections]
        assert "1101" in numbers
        assert "1102" in numbers
        assert "1102.5" in numbers

    def test_citation_format(self):
        hierarchy = HierarchyPath(code_name="LAB")
        sections = parse_display_text_page(SAMPLE_DISPLAY_TEXT_HTML, "LAB", hierarchy)
        s1102_5 = [s for s in sections if s.section_number == "1102.5"][0]
        assert s1102_5.citation == "Cal. Lab. Code § 1102.5"

    def test_section_text_not_empty(self):
        hierarchy = HierarchyPath(code_name="LAB")
        sections = parse_display_text_page(SAMPLE_DISPLAY_TEXT_HTML, "LAB", hierarchy)
        for section in sections:
            assert len(section.text) > 0

    def test_1102_5_has_subdivisions(self):
        hierarchy = HierarchyPath(code_name="LAB")
        sections = parse_display_text_page(SAMPLE_DISPLAY_TEXT_HTML, "LAB", hierarchy)
        s = [s for s in sections if s.section_number == "1102.5"][0]
        # Should find (a), (b), (c), (d)
        assert "a" in s.subdivisions
        assert "b" in s.subdivisions

    def test_amendment_info_extracted(self):
        hierarchy = HierarchyPath(code_name="LAB")
        sections = parse_display_text_page(SAMPLE_DISPLAY_TEXT_HTML, "LAB", hierarchy)
        s = [s for s in sections if s.section_number == "1102.5"][0]
        assert s.amendment_info is not None
        assert "2023" in s.amendment_info

    def test_effective_date_extracted(self):
        hierarchy = HierarchyPath(code_name="LAB")
        sections = parse_display_text_page(SAMPLE_DISPLAY_TEXT_HTML, "LAB", hierarchy)
        s = [s for s in sections if s.section_number == "1102.5"][0]
        assert s.effective_date is not None
        assert "2024" in s.effective_date

    def test_source_url_constructed(self):
        hierarchy = HierarchyPath(code_name="LAB")
        sections = parse_display_text_page(SAMPLE_DISPLAY_TEXT_HTML, "LAB", hierarchy)
        s = [s for s in sections if s.section_number == "1102.5"][0]
        assert "codes_displaySection.xhtml" in s.source_url
        assert "lawCode=LAB" in s.source_url
        assert "sectionNum=1102.5" in s.source_url

    def test_hierarchy_updated_from_page(self):
        hierarchy = HierarchyPath(code_name="LAB")
        sections = parse_display_text_page(SAMPLE_DISPLAY_TEXT_HTML, "LAB", hierarchy)
        s = sections[0]
        # Page headings should have updated the hierarchy
        assert "DIVISION 2" in s.hierarchy.division
        assert "CHAPTER 5" in s.hierarchy.chapter

    def test_fallback_without_content_anchor(self):
        hierarchy = HierarchyPath(code_name="LAB")
        sections = parse_display_text_page(
            SAMPLE_DISPLAY_TEXT_NO_CONTENT_ANCHOR, "LAB", hierarchy
        )
        assert len(sections) == 2
        assert sections[0].section_number == "1"
        assert sections[1].section_number == "2"

    def test_amendment_text_excluded_from_section_text(self):
        hierarchy = HierarchyPath(code_name="LAB")
        sections = parse_display_text_page(SAMPLE_DISPLAY_TEXT_HTML, "LAB", hierarchy)
        s = [s for s in sections if s.section_number == "1102.5"][0]
        # The amendment info should NOT be in the section text
        assert "Amended by Stats" not in s.text


# ── Section-Boundary Chunking Tests ──────────────────────────


class TestSectionBoundaryChunking:
    def test_small_section_is_one_chunk(self):
        text = "This is a short statute section about employee rights."
        chunks = chunk_statute_section(text, "Cal. Lab. Code § 100", "LAB > Div 1")
        assert len(chunks) == 1
        assert chunks[0].content == text

    def test_empty_text_returns_empty(self):
        chunks = chunk_statute_section("", "Cal. Lab. Code § 100", "LAB")
        assert len(chunks) == 0

    def test_whitespace_only_returns_empty(self):
        chunks = chunk_statute_section("   \n\n  ", "Cal. Lab. Code § 100", "LAB")
        assert len(chunks) == 0

    def test_large_section_splits(self):
        # Create a section with multiple subdivisions that exceeds max_tokens
        parts = []
        for letter in "abcdefghij":
            parts.append(f"({letter}) " + "This is a substantial subdivision text. " * 20)
        text = "\n\n".join(parts)

        chunks = chunk_statute_section(
            text, "Cal. Lab. Code § 999", "LAB > Div 2", max_tokens=500
        )
        assert len(chunks) > 1

    def test_split_chunks_have_citation_header(self):
        parts = []
        for letter in "abcdefghij":
            parts.append(f"({letter}) " + "Substantial text content. " * 20)
        text = "\n\n".join(parts)

        chunks = chunk_statute_section(
            text, "Cal. Lab. Code § 999", "LAB > Div 2", max_tokens=500
        )
        # Second and subsequent chunks should have citation header
        if len(chunks) > 1:
            assert "[Cal. Lab. Code § 999]" in chunks[1].content

    def test_heading_path_preserved(self):
        text = "(a) Test section text."
        chunks = chunk_statute_section(text, "Cal. Lab. Code § 1", "LAB > Division 1 > Chapter 2")
        assert chunks[0].heading_path == "LAB > Division 1 > Chapter 2"

    def test_chunk_index_sequential(self):
        parts = []
        for letter in "abcdefghij":
            parts.append(f"({letter}) " + "Substantial text content. " * 20)
        text = "\n\n".join(parts)

        chunks = chunk_statute_section(text, "Cal. Lab. Code § 1", "LAB", max_tokens=500)
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_content_hash_unique(self):
        parts = []
        for letter in "abcde":
            parts.append(f"({letter}) Unique content for subdivision {letter}. " * 15)
        text = "\n\n".join(parts)

        chunks = chunk_statute_section(text, "Cal. Lab. Code § 1", "LAB", max_tokens=300)
        hashes = [c.content_hash for c in chunks]
        assert len(hashes) == len(set(hashes))  # All unique

    def test_token_count_populated(self):
        text = "(a) An employer shall not retaliate against an employee."
        chunks = chunk_statute_section(text, "Cal. Lab. Code § 1", "LAB")
        assert chunks[0].token_count > 0
        assert chunks[0].token_count == estimate_tokens(text)


# ── Config Loading Tests ─────────────────────────────────────


class TestStatutoryConfigLoading:
    def test_labor_code_config_loads(self):
        from employee_help.config import load_source_config
        from employee_help.storage.models import SourceType

        config = load_source_config("config/sources/labor_code.yaml")
        assert config.slug == "labor_code"
        assert config.source_type == SourceType.STATUTORY_CODE
        assert config.statutory is not None
        assert config.statutory.code_abbreviation == "LAB"
        assert config.statutory.citation_prefix == "Cal. Lab. Code"
        assert config.chunking.strategy == "section_boundary"

    def test_gov_code_feha_config_loads(self):
        from employee_help.config import load_source_config
        from employee_help.storage.models import SourceType

        config = load_source_config("config/sources/gov_code_feha.yaml")
        assert config.slug == "gov_code_feha"
        assert config.source_type == SourceType.STATUTORY_CODE
        assert config.statutory is not None
        assert config.statutory.code_abbreviation == "GOV"
        assert config.statutory.target_divisions == ["3."]

    def test_agency_config_has_no_statutory(self):
        from employee_help.config import load_source_config

        config = load_source_config("config/sources/crd.yaml")
        assert config.statutory is None

    def test_unemp_ins_code_config_loads(self):
        from employee_help.config import load_source_config
        from employee_help.storage.models import SourceType

        config = load_source_config("config/sources/unemp_ins_code.yaml")
        assert config.slug == "unemp_ins_code"
        assert config.source_type == SourceType.STATUTORY_CODE
        assert config.statutory is not None
        assert config.statutory.code_abbreviation == "UIC"
        assert config.statutory.target_divisions == ["1."]

    def test_bus_prof_code_config_loads(self):
        from employee_help.config import load_source_config
        from employee_help.storage.models import SourceType

        config = load_source_config("config/sources/bus_prof_code.yaml")
        assert config.slug == "bus_prof_code"
        assert config.source_type == SourceType.STATUTORY_CODE
        assert config.statutory.code_abbreviation == "BPC"
        assert config.statutory.target_divisions == ["7."]

    def test_ccp_config_loads(self):
        from employee_help.config import load_source_config
        from employee_help.storage.models import SourceType

        config = load_source_config("config/sources/ccp.yaml")
        assert config.slug == "ccp"
        assert config.source_type == SourceType.STATUTORY_CODE
        assert config.statutory.code_abbreviation == "CCP"
        assert config.statutory.target_divisions == []

    def test_gov_code_whistleblower_config_loads(self):
        from employee_help.config import load_source_config
        from employee_help.storage.models import SourceType

        config = load_source_config("config/sources/gov_code_whistleblower.yaml")
        assert config.slug == "gov_code_whistleblower"
        assert config.source_type == SourceType.STATUTORY_CODE
        assert config.statutory.code_abbreviation == "GOV"
        assert config.statutory.target_divisions == ["1.", "2."]

    def test_all_configs_load_successfully(self):
        from employee_help.config import load_all_source_configs

        configs = load_all_source_configs("config/sources", enabled_only=False)
        assert len(configs) >= 10  # 4 agency + 6 statutory


# ── StatuteSection Dataclass Tests ───────────────────────────


class TestStatuteSection:
    def test_heading_path_delegates_to_hierarchy(self):
        s = StatuteSection(
            section_number="1102.5",
            code_abbreviation="LAB",
            text="test",
            citation="Cal. Lab. Code § 1102.5",
            hierarchy=HierarchyPath(code_name="LAB", division="Division 2"),
        )
        assert s.heading_path == "LAB > Division 2"
