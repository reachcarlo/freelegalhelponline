"""Tests for the query preprocessor."""

from __future__ import annotations

import pytest

from employee_help.retrieval.query import QueryPreprocessor


@pytest.fixture
def preprocessor():
    return QueryPreprocessor()


class TestCitationDetection:
    """Tests for citation pattern detection in queries."""

    def test_labor_code_section(self, preprocessor):
        result = preprocessor.preprocess("What does Lab. Code section 1102.5 say?")
        assert result.has_citation is True
        assert result.cited_section == "1102.5"

    def test_gov_code_section(self, preprocessor):
        result = preprocessor.preprocess("Gov. Code section 12940(h)")
        assert result.has_citation is True
        assert result.cited_section == "12940(h)"

    def test_section_symbol(self, preprocessor):
        result = preprocessor.preprocess("What is § 1102.5?")
        assert result.has_citation is True
        assert result.cited_section == "1102.5"

    def test_bare_section_reference(self, preprocessor):
        result = preprocessor.preprocess("section 12940")
        assert result.has_citation is True
        assert result.cited_section == "12940"

    def test_feha_abbreviation(self, preprocessor):
        result = preprocessor.preprocess("What does FEHA prohibit?")
        assert result.has_citation is True

    def test_no_citation(self, preprocessor):
        result = preprocessor.preprocess("Can I be fired for no reason?")
        assert result.has_citation is False
        assert result.cited_section is None

    def test_cal_labor_code_format(self, preprocessor):
        result = preprocessor.preprocess("Cal. Lab. Code § 98.6")
        assert result.has_citation is True
        assert result.cited_section == "98.6"

    def test_subdivision_reference(self, preprocessor):
        result = preprocessor.preprocess("Gov. Code section 12940(j)(1)")
        assert result.has_citation is True
        assert result.cited_section == "12940(j)(1)"


class TestTermExpansion:
    """Tests for legal abbreviation expansion."""

    def test_feha_expansion(self, preprocessor):
        result = preprocessor.preprocess("What does FEHA cover?")
        assert "Fair Employment and Housing Act" in result.expanded_terms

    def test_cfra_expansion(self, preprocessor):
        result = preprocessor.preprocess("CFRA leave requirements")
        assert "California Family Rights Act" in result.expanded_terms

    def test_dir_expansion(self, preprocessor):
        result = preprocessor.preprocess("How to file with DIR?")
        assert "Department of Industrial Relations" in result.expanded_terms

    def test_no_expansion(self, preprocessor):
        result = preprocessor.preprocess("overtime pay requirements")
        assert result.expanded_terms == []

    def test_multiple_expansions(self, preprocessor):
        result = preprocessor.preprocess("FEHA and CFRA overlap")
        assert len(result.expanded_terms) >= 2


class TestQueryNormalization:
    """Tests for query text normalization."""

    def test_whitespace_normalization(self, preprocessor):
        result = preprocessor.preprocess("  too   many    spaces  ")
        assert "  " not in result.normalized_query
        assert result.normalized_query == "too many spaces"

    def test_trailing_punctuation_stripped(self, preprocessor):
        result = preprocessor.preprocess("What is minimum wage?")
        assert result.normalized_query == "What is minimum wage"

    def test_preserves_original(self, preprocessor):
        original = "What does Lab. Code § 1102.5 say?"
        result = preprocessor.preprocess(original)
        assert result.original_query == original

    def test_empty_query(self, preprocessor):
        result = preprocessor.preprocess("")
        assert result.normalized_query == ""
        assert result.has_citation is False
