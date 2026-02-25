"""Citation regression test suite — golden dataset of 50+ known-correct citations.

Ensures that build_citation() and the parsing pipeline produce accurate
California statutory citation strings. Run on every CI build to prevent
citation parsing regressions from future code changes.

Golden data sourced from leginfo.legislature.ca.gov and hand-verified
against standard California legal citation formats.
"""

import pytest

from employee_help.scraper.extractors.statute import (
    HierarchyPath,
    StatuteSection,
    build_citation,
    parse_display_text_page,
)


# ── Golden Dataset: Known-Correct Citations ──────────────────
#
# Format: (code_abbreviation, section_number, expected_citation)
#

GOLDEN_CITATIONS = [
    # ── Labor Code ────────────────────────────────────────────
    ("LAB", "1", "Cal. Lab. Code § 1"),
    ("LAB", "2", "Cal. Lab. Code § 2"),
    ("LAB", "98.6", "Cal. Lab. Code § 98.6"),
    ("LAB", "200", "Cal. Lab. Code § 200"),
    ("LAB", "201", "Cal. Lab. Code § 201"),
    ("LAB", "203", "Cal. Lab. Code § 203"),
    ("LAB", "204", "Cal. Lab. Code § 204"),
    ("LAB", "226", "Cal. Lab. Code § 226"),
    ("LAB", "226.7", "Cal. Lab. Code § 226.7"),
    ("LAB", "510", "Cal. Lab. Code § 510"),
    ("LAB", "512", "Cal. Lab. Code § 512"),
    ("LAB", "558.1", "Cal. Lab. Code § 558.1"),
    ("LAB", "1101", "Cal. Lab. Code § 1101"),
    ("LAB", "1102", "Cal. Lab. Code § 1102"),
    ("LAB", "1102.5", "Cal. Lab. Code § 1102.5"),
    ("LAB", "1198.5", "Cal. Lab. Code § 1198.5"),
    ("LAB", "2699", "Cal. Lab. Code § 2699"),
    ("LAB", "2699.3", "Cal. Lab. Code § 2699.3"),
    ("LAB", "2810.5", "Cal. Lab. Code § 2810.5"),
    ("LAB", "3700", "Cal. Lab. Code § 3700"),
    ("LAB", "6300", "Cal. Lab. Code § 6300"),
    ("LAB", "6310", "Cal. Lab. Code § 6310"),
    ("LAB", "6311", "Cal. Lab. Code § 6311"),
    # ── Government Code (FEHA) ────────────────────────────────
    ("GOV", "12900", "Cal. Gov. Code § 12900"),
    ("GOV", "12920", "Cal. Gov. Code § 12920"),
    ("GOV", "12926", "Cal. Gov. Code § 12926"),
    ("GOV", "12940", "Cal. Gov. Code § 12940"),
    ("GOV", "12945", "Cal. Gov. Code § 12945"),
    ("GOV", "12945.2", "Cal. Gov. Code § 12945.2"),
    ("GOV", "12960", "Cal. Gov. Code § 12960"),
    ("GOV", "12965", "Cal. Gov. Code § 12965"),
    ("GOV", "12989", "Cal. Gov. Code § 12989"),
    ("GOV", "12996", "Cal. Gov. Code § 12996"),
    # ── Government Code (Whistleblower) ───────────────────────
    ("GOV", "8547", "Cal. Gov. Code § 8547"),
    ("GOV", "8547.1", "Cal. Gov. Code § 8547.1"),
    ("GOV", "8547.12", "Cal. Gov. Code § 8547.12"),
    # ── Unemployment Insurance Code ───────────────────────────
    ("UIC", "1", "Cal. Unemp. Ins. Code § 1"),
    ("UIC", "1256", "Cal. Unemp. Ins. Code § 1256"),
    ("UIC", "2601", "Cal. Unemp. Ins. Code § 2601"),
    ("UIC", "3301", "Cal. Unemp. Ins. Code § 3301"),
    # ── Business & Professions Code ───────────────────────────
    ("BPC", "16600", "Cal. Bus. & Prof. Code § 16600"),
    ("BPC", "16600.5", "Cal. Bus. & Prof. Code § 16600.5"),
    ("BPC", "16607", "Cal. Bus. & Prof. Code § 16607"),
    ("BPC", "17200", "Cal. Bus. & Prof. Code § 17200"),
    ("BPC", "17204", "Cal. Bus. & Prof. Code § 17204"),
    # ── Code of Civil Procedure ───────────────────────────────
    ("CCP", "340", "Cal. Code Civ. Proc. § 340"),
    ("CCP", "425.16", "Cal. Code Civ. Proc. § 425.16"),
    ("CCP", "1021.5", "Cal. Code Civ. Proc. § 1021.5"),
    # ── Civil Code ────────────────────────────────────────────
    ("CIV", "51", "Cal. Civ. Code § 51"),
    ("CIV", "52", "Cal. Civ. Code § 52"),
    ("CIV", "1708.5", "Cal. Civ. Code § 1708.5"),
    # ── Health & Safety Code ──────────────────────────────────
    ("HSC", "25100", "Cal. Health & Safety Code § 25100"),
    ("HSC", "25250", "Cal. Health & Safety Code § 25250"),
    # ── Education Code ────────────────────────────────────────
    ("EDC", "49110", "Cal. Educ. Code § 49110"),
    ("EDC", "49145", "Cal. Educ. Code § 49145"),
]


class TestCitationGoldenDataset:
    """Test build_citation against the golden dataset of 50+ known-correct citations."""

    @pytest.mark.parametrize(
        "code_abbrev,section_num,expected",
        GOLDEN_CITATIONS,
        ids=[f"{c}-{s}" for c, s, _ in GOLDEN_CITATIONS],
    )
    def test_citation_matches_golden(self, code_abbrev, section_num, expected):
        """Each citation must exactly match the expected golden value."""
        result = build_citation(code_abbrev, section_num)
        assert result == expected, f"Expected '{expected}', got '{result}'"


# ── Edge Cases ───────────────────────────────────────────────


class TestCitationEdgeCases:
    def test_decimal_section_number(self):
        assert build_citation("LAB", "1102.5") == "Cal. Lab. Code § 1102.5"

    def test_long_decimal_section(self):
        assert build_citation("GOV", "8547.12") == "Cal. Gov. Code § 8547.12"

    def test_section_number_with_single_digit(self):
        assert build_citation("LAB", "1") == "Cal. Lab. Code § 1"

    def test_four_digit_section(self):
        assert build_citation("LAB", "2699") == "Cal. Lab. Code § 2699"

    def test_five_digit_section(self):
        assert build_citation("GOV", "12940") == "Cal. Gov. Code § 12940"

    def test_unknown_code_fallback(self):
        """Unknown code abbreviations get a generic Cal. prefix."""
        assert build_citation("XYZ", "100") == "Cal. XYZ § 100"

    def test_all_known_codes_have_prefixes(self):
        """Every code in our manifest should have a known citation prefix."""
        known_codes = ["LAB", "GOV", "UIC", "BPC", "CCP", "CIV", "HSC", "EDC"]
        from employee_help.scraper.extractors.statute import CITATION_PREFIXES
        for code in known_codes:
            assert code in CITATION_PREFIXES, f"Missing prefix for {code}"

    def test_section_symbol_present(self):
        """All citations must contain the § symbol."""
        for code, num, expected in GOLDEN_CITATIONS:
            result = build_citation(code, num)
            assert "§" in result

    def test_no_double_spaces(self):
        """No citation should contain double spaces."""
        for code, num, _ in GOLDEN_CITATIONS:
            result = build_citation(code, num)
            assert "  " not in result


# ── Parse-to-Citation Integration Tests ──────────────────────


SAMPLE_MULTI_SECTION_HTML = """
<html><body>
<div id="content_anchor">
<h4>Labor Code - LAB</h4>
<h4>DIVISION 2. EMPLOYMENT REGULATION AND SUPERVISION [200 - 2699.8]</h4>
<h5>PART 1. Compensation [200 - 558.1]</h5>
<h5>CHAPTER 1. Payment of Wages [200 - 273]</h5>
<h6>200.</h6>
<p>As used in this article:</p>
<p>(a) "Wages" includes all amounts for labor performed.</p>
<em>(Amended by Stats. 2000, Ch. 876, Sec. 3.)</em>
<h6>201.</h6>
<p>If an employer discharges an employee, the wages earned and unpaid at the time of discharge are due and payable immediately.</p>
<em>(Amended by Stats. 2002, Ch. 48, Sec. 1. Effective January 1, 2003.)</em>
<h6>203.</h6>
<p>If an employer willfully fails to pay wages, the employer shall be liable for the wages of the employee from the due date.</p>
<em>(Amended by Stats. 2019, Ch. 271, Sec. 1. Effective January 1, 2020.)</em>
<h6>226.</h6>
<p>(a) An employer shall furnish each employee an accurate itemized statement in writing.</p>
<p>(b) An employer is in compliance if the itemized statement is furnished in a timely manner.</p>
<em>(Amended by Stats. 2023, Ch. 331, Sec. 1. Effective January 1, 2024.)</em>
<h6>226.7.</h6>
<p>If an employer fails to provide an employee a meal period or rest period, the employer shall pay the employee one additional hour of pay.</p>
<em>(Added by Stats. 2000, Ch. 492, Sec. 2. Effective January 1, 2001.)</em>
</div>
</body></html>
"""


class TestParseToGoldenCitation:
    """Verify that parsing HTML produces citations matching the golden dataset."""

    def test_parsed_sections_have_correct_citations(self):
        hierarchy = HierarchyPath(code_name="LAB")
        sections = parse_display_text_page(
            SAMPLE_MULTI_SECTION_HTML, "LAB", hierarchy
        )

        expected_citations = {
            "200": "Cal. Lab. Code § 200",
            "201": "Cal. Lab. Code § 201",
            "203": "Cal. Lab. Code § 203",
            "226": "Cal. Lab. Code § 226",
            "226.7": "Cal. Lab. Code § 226.7",
        }

        for section in sections:
            assert section.section_number in expected_citations
            assert section.citation == expected_citations[section.section_number]

    def test_all_sections_extracted(self):
        hierarchy = HierarchyPath(code_name="LAB")
        sections = parse_display_text_page(
            SAMPLE_MULTI_SECTION_HTML, "LAB", hierarchy
        )
        assert len(sections) == 5

    def test_decimal_section_number_parsed_correctly(self):
        hierarchy = HierarchyPath(code_name="LAB")
        sections = parse_display_text_page(
            SAMPLE_MULTI_SECTION_HTML, "LAB", hierarchy
        )
        decimal_sections = [s for s in sections if "." in s.section_number]
        assert len(decimal_sections) == 1
        assert decimal_sections[0].section_number == "226.7"
        assert decimal_sections[0].citation == "Cal. Lab. Code § 226.7"

    def test_statute_section_heading_path_includes_citation(self):
        """StatuteSection.heading_path should include the hierarchy."""
        hierarchy = HierarchyPath(code_name="LAB")
        sections = parse_display_text_page(
            SAMPLE_MULTI_SECTION_HTML, "LAB", hierarchy
        )
        for s in sections:
            assert "LAB" in s.heading_path
            assert "DIVISION 2" in s.heading_path
