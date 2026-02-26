"""Tests for evaluation metric functions."""

from __future__ import annotations

import pytest

from employee_help.evaluation.answer_metrics import (
    citation_accuracy,
    citation_completeness,
    extract_statute_citations,
    has_disclaimer,
    reading_level,
)
from employee_help.evaluation.retrieval_metrics import (
    citation_hit_at_k,
    mean_reciprocal_rank,
    precision_at_k,
    recall_at_k,
)
from employee_help.retrieval.service import RetrievalResult


def _make_result(chunk_id: int, category: str, citation: str | None = None) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        document_id=chunk_id,
        source_id=1,
        content=f"content {chunk_id}",
        heading_path="test",
        content_category=category,
        citation=citation,
        relevance_score=0.9,
    )


class TestPrecisionAtK:
    def test_perfect_precision(self):
        results = [_make_result(i, "statutory_code") for i in range(5)]
        assert precision_at_k(results, {"statutory_code"}, k=5) == 1.0

    def test_zero_precision(self):
        results = [_make_result(i, "faq") for i in range(5)]
        assert precision_at_k(results, {"statutory_code"}, k=5) == 0.0

    def test_partial_precision(self):
        results = [
            _make_result(1, "statutory_code"),
            _make_result(2, "faq"),
            _make_result(3, "statutory_code"),
            _make_result(4, "faq"),
        ]
        assert precision_at_k(results, {"statutory_code"}, k=4) == 0.5

    def test_empty_results(self):
        assert precision_at_k([], {"statutory_code"}, k=5) == 0.0


class TestRecallAtK:
    def test_perfect_recall(self):
        results = [
            _make_result(1, "statutory_code", "§ 1102.5"),
            _make_result(2, "statutory_code", "§ 12940"),
        ]
        assert recall_at_k(results, ["1102.5", "12940"], k=5) == 1.0

    def test_zero_recall(self):
        results = [_make_result(1, "statutory_code", "§ 999")]
        assert recall_at_k(results, ["1102.5"], k=5) == 0.0

    def test_no_expected(self):
        results = [_make_result(1, "faq")]
        assert recall_at_k(results, [], k=5) == 1.0

    def test_empty_results(self):
        assert recall_at_k([], ["1102.5"], k=5) == 0.0


class TestMRR:
    def test_first_result_relevant(self):
        results = [_make_result(1, "statutory_code"), _make_result(2, "faq")]
        assert mean_reciprocal_rank(results, {"statutory_code"}) == 1.0

    def test_second_result_relevant(self):
        results = [_make_result(1, "faq"), _make_result(2, "statutory_code")]
        assert mean_reciprocal_rank(results, {"statutory_code"}) == 0.5

    def test_no_relevant_results(self):
        results = [_make_result(1, "faq"), _make_result(2, "faq")]
        assert mean_reciprocal_rank(results, {"statutory_code"}) == 0.0

    def test_empty_results(self):
        assert mean_reciprocal_rank([], {"statutory_code"}) == 0.0


class TestCitationHitAtK:
    def test_hit_at_top1(self):
        results = [_make_result(1, "statutory_code", "Cal. Lab. Code § 1102.5")]
        assert citation_hit_at_k(results, "1102.5", k=1) is True

    def test_miss_at_top1(self):
        results = [_make_result(1, "statutory_code", "Cal. Lab. Code § 98.6")]
        assert citation_hit_at_k(results, "1102.5", k=1) is False

    def test_empty_results(self):
        assert citation_hit_at_k([], "1102.5", k=1) is False


class TestCitationAccuracy:
    def test_all_valid(self):
        answer_cites = ["Cal. Lab. Code § 1102.5", "Cal. Gov. Code § 12940"]
        kb_cites = {"Cal. Lab. Code § 1102.5", "Cal. Gov. Code § 12940(h)"}
        assert citation_accuracy(answer_cites, kb_cites) == 1.0

    def test_none_valid(self):
        answer_cites = ["Cal. Lab. Code § 9999"]
        kb_cites = {"Cal. Lab. Code § 1102.5"}
        assert citation_accuracy(answer_cites, kb_cites) == 0.0

    def test_no_citations(self):
        assert citation_accuracy([], set()) == 1.0


class TestCitationCompleteness:
    def test_all_found(self):
        answer_cites = ["Cal. Lab. Code § 1102.5"]
        expected = ["1102.5"]
        assert citation_completeness(answer_cites, expected) == 1.0

    def test_none_found(self):
        answer_cites = ["Cal. Lab. Code § 98.6"]
        expected = ["1102.5"]
        assert citation_completeness(answer_cites, expected) == 0.0

    def test_no_expected(self):
        assert citation_completeness(["x"], []) == 1.0


class TestHasDisclaimer:
    def test_consumer_disclaimer(self):
        text = "This information is for educational purposes only and is not legal advice."
        assert has_disclaimer(text, "consumer") is True

    def test_attorney_disclaimer(self):
        text = "This analysis should be independently verified."
        assert has_disclaimer(text, "attorney") is True

    def test_no_disclaimer(self):
        assert has_disclaimer("Just some text here.", "consumer") is False


class TestReadingLevel:
    def test_simple_text(self):
        text = "The cat sat on the mat. The dog ran in the park."
        grade = reading_level(text)
        assert grade < 10  # Simple text should be low grade level

    def test_complex_text(self):
        text = (
            "Notwithstanding the aforementioned provisions, the administrative "
            "adjudicatory proceedings shall be conducted in accordance with the "
            "procedural requirements established pursuant to the applicable "
            "statutory framework governing employment discrimination claims."
        )
        grade = reading_level(text)
        assert grade > 10  # Complex text should be high grade level


class TestExtractStatuteCitations:
    def test_extract_labor_code(self):
        text = "Under Cal. Lab. Code § 1102.5, protections apply."
        citations = extract_statute_citations(text)
        assert len(citations) >= 1
        assert any("1102.5" in c for c in citations)

    def test_extract_gov_code(self):
        text = "See Cal. Gov. Code § 12940(h) for details."
        citations = extract_statute_citations(text)
        assert len(citations) >= 1

    def test_no_citations(self):
        text = "There are no statute references here."
        citations = extract_statute_citations(text)
        assert citations == []

    def test_multiple_citations(self):
        text = (
            "Both Cal. Lab. Code § 1102.5 and Cal. Gov. Code § 12940 "
            "provide protections."
        )
        citations = extract_statute_citations(text)
        assert len(citations) >= 2
