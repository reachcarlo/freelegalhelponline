"""Tests for the eyecite citation extraction module."""

from __future__ import annotations

import pytest

from employee_help.processing.citation_extractor import (
    ExtractedCitation,
    extract_california_citations,
    extract_case_citations,
    extract_citations,
    extract_statute_citations,
    resolve_short_citations,
)


# ---------------------------------------------------------------------------
# Full California case citations
# ---------------------------------------------------------------------------


class TestFullCaliforniaCaseCitations:
    def test_cal_supreme_court_citation(self):
        text = "Yanowitz v. L'Oreal USA, Inc. (2005) 36 Cal.4th 1028"
        cites = extract_citations(text)
        assert len(cites) >= 1
        case = next(c for c in cites if c.citation_type == "case")
        assert case.volume == "36"
        assert case.reporter is not None
        assert "Cal." in case.reporter
        assert case.page == "1028"
        assert case.is_california is True

    def test_cal_appellate_citation(self):
        text = "Harris v. City of Santa Monica (2013) 56 Cal.4th 203"
        cites = extract_citations(text)
        assert len(cites) >= 1
        case = next(c for c in cites if c.citation_type == "case")
        assert case.volume == "56"
        assert case.page == "203"
        assert case.is_california is True

    def test_cal_app_5th_citation(self):
        text = "Smith v. Jones (2023) 95 Cal.App.5th 123"
        cites = extract_citations(text)
        assert len(cites) >= 1
        case = next(c for c in cites if c.citation_type == "case")
        assert case.is_california is True

    def test_cal_rptr_citation(self):
        text = "See Doe v. Roe, 150 Cal.Rptr.3d 456 (2022)"
        cites = extract_citations(text)
        assert len(cites) >= 1
        case = next(c for c in cites if c.citation_type == "case")
        assert case.is_california is True
        assert case.volume == "150"

    def test_year_extraction(self):
        text = "Tameny v. Atlantic Richfield Co. (1980) 27 Cal.3d 167"
        cites = extract_citations(text)
        case = next(c for c in cites if c.citation_type == "case")
        assert case.year == "1980"

    def test_span_positions(self):
        text = "As noted in Yanowitz v. L'Oreal USA, Inc. (2005) 36 Cal.4th 1028, the court held..."
        cites = extract_citations(text)
        case = next(c for c in cites if c.citation_type == "case")
        start, end = case.span
        assert start >= 0
        assert end > start
        # The span should be within the text bounds
        assert end <= len(text) + 10  # allow some tolerance for whitespace normalization


# ---------------------------------------------------------------------------
# Federal case citations (NOT California)
# ---------------------------------------------------------------------------


class TestFederalCaseCitations:
    def test_us_supreme_court_citation(self):
        text = "Bush v. Gore, 531 U.S. 98 (2000)"
        cites = extract_citations(text)
        assert len(cites) >= 1
        case = next(c for c in cites if c.citation_type == "case")
        assert case.is_california is False
        assert case.volume == "531"
        assert case.page == "98"

    def test_federal_reporter_citation(self):
        text = "The court in Smith v. Widget Corp., 450 F.3d 1200 (9th Cir. 2006) held..."
        cites = extract_citations(text)
        assert len(cites) >= 1
        case = next(c for c in cites if c.citation_type == "case")
        assert case.is_california is False

    def test_federal_supp_citation(self):
        text = "Jones v. County of Los Angeles, 300 F.Supp.3d 500 (C.D. Cal. 2018)"
        cites = extract_citations(text)
        assert len(cites) >= 1
        case = next(c for c in cites if c.citation_type == "case")
        # F.Supp reporter is federal, not California
        assert case.is_california is False


# ---------------------------------------------------------------------------
# Statutory citations
# ---------------------------------------------------------------------------


class TestStatutoryCitations:
    def test_gov_code_citation(self):
        text = "Cal. Gov. Code \u00a7 12940"
        cites = extract_citations(text)
        statute_cites = [c for c in cites if c.citation_type == "statute"]
        assert len(statute_cites) >= 1
        s = statute_cites[0]
        assert s.section == "12940"
        assert s.is_california is True

    def test_labor_code_citation(self):
        text = "Cal. Lab. Code \u00a7 1102.5"
        cites = extract_citations(text)
        statute_cites = [c for c in cites if c.citation_type == "statute"]
        assert len(statute_cites) >= 1
        s = statute_cites[0]
        assert s.section is not None
        assert "1102.5" in s.section
        assert s.is_california is True

    def test_bus_prof_code_citation(self):
        text = "Cal. Bus. & Prof. Code \u00a7 17200"
        cites = extract_citations(text)
        statute_cites = [c for c in cites if c.citation_type == "statute"]
        assert len(statute_cites) >= 1
        s = statute_cites[0]
        assert s.is_california is True

    def test_civ_proc_code_citation(self):
        text = "Cal. Civ. Proc. Code \u00a7 1021.5"
        cites = extract_citations(text)
        statute_cites = [c for c in cites if c.citation_type == "statute"]
        assert len(statute_cites) >= 1
        s = statute_cites[0]
        assert s.is_california is True

    def test_unemp_ins_code_citation(self):
        text = "Cal. Unemp. Ins. Code \u00a7 1256"
        cites = extract_citations(text)
        statute_cites = [c for c in cites if c.citation_type == "statute"]
        assert len(statute_cites) >= 1
        assert statute_cites[0].is_california is True


# ---------------------------------------------------------------------------
# Mixed text with both case and statute citations
# ---------------------------------------------------------------------------


class TestMixedCitations:
    def test_mixed_case_and_statute(self):
        text = (
            "Under Cal. Gov. Code \u00a7 12940, employers are prohibited from "
            "discrimination. See Yanowitz v. L'Oreal USA, Inc. (2005) "
            "36 Cal.4th 1028 for the standard."
        )
        cites = extract_citations(text)
        case_cites = [c for c in cites if c.citation_type == "case"]
        statute_cites = [c for c in cites if c.citation_type == "statute"]
        assert len(case_cites) >= 1
        assert len(statute_cites) >= 1
        # Both should be California
        assert all(c.is_california for c in case_cites)
        assert all(c.is_california for c in statute_cites)

    def test_multiple_case_citations(self):
        text = (
            "In Tameny v. Atlantic Richfield Co. (1980) 27 Cal.3d 167, the court "
            "established the framework later applied in Gantt v. Sentry Insurance "
            "(1992) 1 Cal.4th 1083."
        )
        cites = extract_citations(text)
        case_cites = [c for c in cites if c.citation_type == "case"]
        assert len(case_cites) >= 2
        volumes = {c.volume for c in case_cites}
        assert "27" in volumes
        assert "1" in volumes


# ---------------------------------------------------------------------------
# California reporter format variations
# ---------------------------------------------------------------------------


class TestCaliforniaReporterFormats:
    def test_cal_2d(self):
        text = "Smith v. Jones, 50 Cal.2d 300 (1958)"
        cites = extract_case_citations(text)
        assert len(cites) >= 1
        assert cites[0].is_california is True

    def test_cal_3d(self):
        text = "Doe v. Roe (1975) 15 Cal.3d 100"
        cites = extract_case_citations(text)
        assert len(cites) >= 1
        assert cites[0].is_california is True

    def test_cal_5th(self):
        text = "ABC v. XYZ (2024) 100 Cal.5th 500"
        cites = extract_case_citations(text)
        assert len(cites) >= 1
        assert cites[0].is_california is True

    def test_cal_app_3d(self):
        text = "Williams v. State (1985) 170 Cal.App.3d 250"
        cites = extract_case_citations(text)
        assert len(cites) >= 1
        assert cites[0].is_california is True

    def test_cal_rptr_2d(self):
        text = "Garcia v. City, 200 Cal.Rptr.2d 100 (2003)"
        cites = extract_case_citations(text)
        assert len(cites) >= 1
        assert cites[0].is_california is True


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_text(self):
        assert extract_citations("") == []

    def test_whitespace_only(self):
        assert extract_citations("   \n\t  ") == []

    def test_no_citations(self):
        text = "This is a paragraph about employment law with no citations."
        assert extract_citations(text) == []

    def test_pin_cite(self):
        text = "Yanowitz v. L'Oreal USA, Inc. (2005) 36 Cal.4th 1028, 1042"
        cites = extract_citations(text)
        case = next(c for c in cites if c.citation_type == "case")
        # Pin cite may or may not be captured depending on eyecite version
        # but the main citation should still be found
        assert case.volume == "36"
        assert case.page == "1028"

    def test_string_cite_multiple(self):
        text = (
            "See 36 Cal.4th 1028; 56 Cal.4th 203; 27 Cal.3d 167."
        )
        cites = extract_citations(text)
        # Should find at least some of these short-form citations
        assert len(cites) >= 1

    def test_citation_type_field(self):
        text = "Yanowitz v. L'Oreal USA, Inc. (2005) 36 Cal.4th 1028"
        cites = extract_citations(text)
        case = next(c for c in cites if c.citation_type == "case")
        assert case.citation_type == "case"

    def test_dataclass_fields(self):
        """Verify ExtractedCitation has all expected fields."""
        cite = ExtractedCitation(
            text="test",
            citation_type="case",
            volume="1",
            reporter="Cal.",
            page="100",
            pin_cite=None,
            year="2020",
            court=None,
            plaintiff="Smith",
            defendant="Jones",
            section=None,
            span=(0, 10),
            is_california=True,
        )
        assert cite.text == "test"
        assert cite.citation_type == "case"
        assert cite.volume == "1"
        assert cite.reporter == "Cal."
        assert cite.page == "100"
        assert cite.year == "2020"
        assert cite.plaintiff == "Smith"
        assert cite.defendant == "Jones"
        assert cite.span == (0, 10)
        assert cite.is_california is True


# ---------------------------------------------------------------------------
# Short-form and Id. citation resolution
# ---------------------------------------------------------------------------


class TestShortFormResolution:
    def test_supra_resolution(self):
        text = (
            "In Tameny v. Atlantic Richfield Co. (1980) 27 Cal.3d 167, the court held "
            "that wrongful termination claims are actionable. Later courts followed "
            "Tameny, supra, at 170."
        )
        grouped = resolve_short_citations([], text)
        # Should have at least one group
        assert len(grouped) >= 1
        # The group for the full Tameny citation should have multiple entries
        for key, group in grouped.items():
            if "27" in key and "167" in key:
                # Full cite + supra = at least 2
                assert len(group) >= 2
                types = {c.citation_type for c in group}
                assert "case" in types
                assert "supra" in types
                break

    def test_id_resolution(self):
        text = (
            "In Yanowitz v. L'Oreal USA, Inc. (2005) 36 Cal.4th 1028, the court "
            "established the standard. Id. at 1042."
        )
        grouped = resolve_short_citations([], text)
        assert len(grouped) >= 1
        for key, group in grouped.items():
            if "36" in key:
                types = {c.citation_type for c in group}
                assert "case" in types
                assert "id" in types
                break

    def test_empty_text_resolution(self):
        assert resolve_short_citations([], "") == {}

    def test_no_citations_resolution(self):
        text = "No legal citations here at all."
        assert resolve_short_citations([], text) == {}

    def test_california_propagation_in_resolution(self):
        """Short-form citations should inherit California status from their antecedent."""
        text = (
            "In Tameny v. Atlantic Richfield Co. (1980) 27 Cal.3d 167, the court "
            "established this rule. Tameny, supra, at 170."
        )
        grouped = resolve_short_citations([], text)
        for key, group in grouped.items():
            if "27" in key:
                # All citations in a California case group should be marked CA
                for cite in group:
                    assert cite.is_california is True
                break


# ---------------------------------------------------------------------------
# Jurisdiction filtering
# ---------------------------------------------------------------------------


class TestJurisdictionFiltering:
    def test_california_only(self):
        text = (
            "In Tameny v. Atlantic Richfield Co. (1980) 27 Cal.3d 167 and "
            "Bush v. Gore, 531 U.S. 98 (2000), different standards apply."
        )
        ca_cites = extract_california_citations(text)
        # Should include Tameny but not Bush
        assert all(c.is_california for c in ca_cites)
        reporters = [c.reporter for c in ca_cites if c.reporter]
        assert any("Cal." in r for r in reporters)
        assert not any("U.S." in r for r in reporters)

    def test_california_statute_filtering(self):
        text = "Under Cal. Gov. Code \u00a7 12940 and 42 U.S.C. \u00a7 2000e..."
        ca_cites = extract_california_citations(text)
        assert len(ca_cites) >= 1
        # Only California statutes should be included
        assert all(c.is_california for c in ca_cites)

    def test_mixed_jurisdiction_counts(self):
        text = (
            "See Tameny v. Atlantic Richfield Co. (1980) 27 Cal.3d 167; "
            "see also Smith v. Widget Corp., 450 F.3d 1200 (9th Cir. 2006)."
        )
        all_cites = extract_citations(text)
        ca_cites = extract_california_citations(text)
        # California citations should be a subset
        assert len(ca_cites) <= len(all_cites)


# ---------------------------------------------------------------------------
# Convenience function tests
# ---------------------------------------------------------------------------


class TestConvenienceFunctions:
    def test_extract_case_citations_filters(self):
        text = (
            "See Cal. Lab. Code \u00a7 1102.5 and "
            "Tameny v. Atlantic Richfield Co. (1980) 27 Cal.3d 167."
        )
        case_cites = extract_case_citations(text)
        # Should only have case-type citations
        for c in case_cites:
            assert c.citation_type in {"case", "short_case", "id", "supra"}

    def test_extract_statute_citations_filters(self):
        text = (
            "See Cal. Lab. Code \u00a7 1102.5 and "
            "Tameny v. Atlantic Richfield Co. (1980) 27 Cal.3d 167."
        )
        statute_cites = extract_statute_citations(text)
        for c in statute_cites:
            assert c.citation_type == "statute"

    def test_extract_citations_remove_ambiguous_default(self):
        """Default remove_ambiguous=True should not raise."""
        text = "See 36 Cal.4th 1028."
        cites = extract_citations(text)
        # Should work without error
        assert isinstance(cites, list)

    def test_extract_citations_remove_ambiguous_false(self):
        """Explicit remove_ambiguous=False should not raise."""
        text = "See 36 Cal.4th 1028."
        cites = extract_citations(text, remove_ambiguous=False)
        assert isinstance(cites, list)
