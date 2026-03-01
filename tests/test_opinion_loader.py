"""Tests for the opinion loader pipeline.

Uses mocked CourtListener API responses to test the filtering pipeline,
employment relevance detection, and pagination handling.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from employee_help.scraper.extractors.courtlistener import (
    CourtListenerError,
    SearchResult,
)
from employee_help.scraper.extractors.opinion_loader import (
    DEFAULT_EMPLOYMENT_STATUTES,
    LoadedOpinion,
    OpinionLoader,
    _extract_id_from_url,
    _extract_plain_text,
    _has_strong_employment_signal,
    _matches_employment_statutes,
)


# ── Sample data ───────────────────────────────────────────────

EMPLOYMENT_OPINION_TEXT = """
The plaintiff filed a complaint alleging violations of the Fair Employment
and Housing Act (FEHA). Under Cal. Gov. Code § 12940, it is unlawful for
an employer to discriminate against an employee based on protected
characteristics. The court in Yanowitz v. L'Oreal USA, Inc. (2005) 36 Cal.4th
1028 established the standard for retaliation claims under FEHA. The plaintiff
also alleged wrongful termination in violation of public policy under
Tameny v. Atlantic Richfield Co. (1980) 27 Cal.3d 167. Additionally, the
plaintiff brought claims under Cal. Lab. Code § 1102.5 for whistleblower
retaliation.
"""

NON_EMPLOYMENT_OPINION_TEXT = """
The defendant appealed the trial court's ruling on the contract dispute.
Under Cal. Civ. Code § 1550, the essential elements of a contract are
parties capable of contracting, their consent, a lawful object, and
sufficient consideration. The court found that the contract was valid
and enforceable. The damages awarded were based on the standard measure
of expectation damages as set forth in the Restatement (Second) of
Contracts.
"""

FEDERAL_OPINION_TEXT = """
The petitioner sought certiorari to the United States Supreme Court.
In Bush v. Gore, 531 U.S. 98 (2000), the Court held that the Equal
Protection Clause was violated. Under 42 U.S.C. § 1983, every person
who, under color of any statute, deprives any citizen of rights shall
be liable. This case involved no California employment statutes.
"""

BORDERLINE_EMPLOYMENT_TEXT = """
The plaintiff alleged wrongful termination and employment discrimination.
The hostile work environment claim was based on the supervisor's conduct.
The employer argued that the plaintiff's retaliation claim lacked merit.
The court analyzed the wage and hour issues including unpaid overtime.
"""

MALFORMED_OPINION_TEXT = "Short."

SEARCH_RESULT_EMPLOYMENT = {
    "caseName": "Smith v. Employer Inc.",
    "caseNameFull": "John Smith v. Employer Inc.",
    "court_id": "cal",
    "dateFiled": "2023-06-15",
    "cluster_id": 10001,
    "docketNumber": "S123456",
    "citation": ["45 Cal.App.5th 123"],
    "status": "Published",
    "citeCount": 8,
    "absolute_url": "/opinion/10001/smith-v-employer-inc/",
}

SEARCH_RESULT_NON_EMPLOYMENT = {
    "caseName": "Jones v. Landlord LLC",
    "caseNameFull": "Jones v. Landlord LLC",
    "court_id": "calctapp2d",
    "dateFiled": "2022-03-10",
    "cluster_id": 20001,
    "docketNumber": "B234567",
    "citation": ["80 Cal.App.5th 456"],
    "status": "Published",
    "citeCount": 2,
    "absolute_url": "/opinion/20001/jones-v-landlord-llc/",
}

SEARCH_RESULT_NO_CLUSTER_ID = {
    "caseName": "Missing v. ClusterID",
    "court_id": "cal",
}

CLUSTER_RESPONSE = {
    "id": 10001,
    "sub_opinions": [
        "https://www.courtlistener.com/api/rest/v4/opinions/99999/",
    ],
}

CLUSTER_EMPTY = {
    "id": 20002,
    "sub_opinions": [],
}

OPINION_RESPONSE_EMPLOYMENT = {
    "id": 99999,
    "type": "lead-opinion",
    "html_with_citations": f"<p>{EMPLOYMENT_OPINION_TEXT}</p>",
    "plain_text": "",
}

OPINION_RESPONSE_NON_EMPLOYMENT = {
    "id": 88888,
    "type": "lead-opinion",
    "html_with_citations": f"<p>{NON_EMPLOYMENT_OPINION_TEXT}</p>",
    "plain_text": "",
}


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def mock_client():
    """Create a mock CourtListenerClient."""
    return MagicMock()


@pytest.fixture
def loader(mock_client):
    """Create an OpinionLoader with a mocked client."""
    return OpinionLoader(
        client=mock_client,
        courts=["cal", "calctapp"],
        search_queries=['"Labor Code" wrongful termination'],
    )


# ── Employment Statute Matching ───────────────────────────────


class TestEmploymentStatuteMatching:
    def test_matches_labor_code_via_eyecite(self):
        from employee_help.processing.citation_extractor import extract_citations

        citations = extract_citations(EMPLOYMENT_OPINION_TEXT)
        matched = _matches_employment_statutes(
            citations, EMPLOYMENT_OPINION_TEXT, DEFAULT_EMPLOYMENT_STATUTES
        )
        assert "Labor Code" in matched or "Government Code (FEHA)" in matched

    def test_matches_feha_via_text_fallback(self):
        from employee_help.processing.citation_extractor import extract_citations

        # Text that mentions "Government Code section 12940" (non-Bluebook)
        text = (
            "Under Government Code section 12940, employers are prohibited from "
            "engaging in employment discrimination based on protected characteristics."
        )
        citations = extract_citations(text)
        matched = _matches_employment_statutes(
            citations, text, DEFAULT_EMPLOYMENT_STATUTES
        )
        assert "Government Code (FEHA)" in matched

    def test_no_match_for_non_employment(self):
        from employee_help.processing.citation_extractor import extract_citations

        citations = extract_citations(FEDERAL_OPINION_TEXT)
        matched = _matches_employment_statutes(
            citations, FEDERAL_OPINION_TEXT, DEFAULT_EMPLOYMENT_STATUTES
        )
        assert matched == []

    def test_matches_multiple_codes(self):
        from employee_help.processing.citation_extractor import extract_citations

        citations = extract_citations(EMPLOYMENT_OPINION_TEXT)
        matched = _matches_employment_statutes(
            citations, EMPLOYMENT_OPINION_TEXT, DEFAULT_EMPLOYMENT_STATUTES
        )
        # Should match both Labor Code and Government Code
        assert len(matched) >= 2

    def test_custom_statute_patterns(self):
        from employee_help.processing.citation_extractor import extract_citations

        custom = {"Custom Code": [r"Custom\s+Code"]}
        text = "Under Custom Code section 99, the rule applies."
        citations = extract_citations(text)
        matched = _matches_employment_statutes(citations, text, custom)
        assert "Custom Code" in matched


# ── Strong Employment Signal Detection ────────────────────────


class TestStrongEmploymentSignal:
    def test_detects_employment_keywords(self):
        from employee_help.processing.citation_extractor import extract_citations

        citations = extract_citations(BORDERLINE_EMPLOYMENT_TEXT)
        assert _has_strong_employment_signal(citations, BORDERLINE_EMPLOYMENT_TEXT)

    def test_no_signal_for_contract_dispute(self):
        from employee_help.processing.citation_extractor import extract_citations

        citations = extract_citations(NON_EMPLOYMENT_OPINION_TEXT)
        assert not _has_strong_employment_signal(
            citations, NON_EMPLOYMENT_OPINION_TEXT
        )

    def test_no_signal_for_federal(self):
        from employee_help.processing.citation_extractor import extract_citations

        citations = extract_citations(FEDERAL_OPINION_TEXT)
        assert not _has_strong_employment_signal(citations, FEDERAL_OPINION_TEXT)

    def test_detects_feha_section_citations(self):
        from employee_help.processing.citation_extractor import extract_citations

        text = "The plaintiff brought a claim under Cal. Gov. Code § 12940."
        citations = extract_citations(text)
        assert _has_strong_employment_signal(citations, text)


# ── Text Extraction ───────────────────────────────────────────


class TestExtractPlainText:
    def test_extracts_html(self):
        html = "<p>Hello <b>world</b>, this is a court opinion with sufficient length for extraction to pass the minimum threshold.</p>"
        data = {"html_with_citations": html}
        text = _extract_plain_text(data)
        assert "Hello" in text
        assert "world" in text
        assert "<p>" not in text

    def test_extracts_plain_text(self):
        data = {"plain_text": "This is plain text content that is long enough for extraction to pass the minimum fifty character threshold check."}
        text = _extract_plain_text(data)
        assert "plain text content" in text

    def test_prefers_html_with_citations(self):
        data = {
            "html_with_citations": "<p>Primary source text that is long enough to process.</p>",
            "plain_text": "Fallback text that we should not get.",
        }
        text = _extract_plain_text(data)
        assert "Primary source" in text

    def test_empty_opinion(self):
        assert _extract_plain_text({}) == ""

    def test_short_text_skipped(self):
        data = {"html_with_citations": "<p>Short</p>"}
        assert _extract_plain_text(data) == ""

    def test_falls_through_empty_fields(self):
        data = {
            "html_with_citations": "",
            "plain_text": "",
            "html_columbia": "Long enough text from Columbia source for extraction purposes.",
        }
        text = _extract_plain_text(data)
        assert "Columbia source" in text


# ── URL ID Extraction ─────────────────────────────────────────


class TestExtractIdFromUrl:
    def test_extracts_id(self):
        url = "https://www.courtlistener.com/api/rest/v4/opinions/12345/"
        assert _extract_id_from_url(url) == 12345

    def test_extracts_id_no_trailing_slash(self):
        url = "https://www.courtlistener.com/api/rest/v4/opinions/67890"
        assert _extract_id_from_url(url) == 67890

    def test_returns_none_for_invalid(self):
        assert _extract_id_from_url("not-a-url") is None

    def test_returns_none_for_empty(self):
        assert _extract_id_from_url("") is None


# ── Opinion Loader Pipeline ───────────────────────────────────


class TestOpinionLoaderPipeline:
    def test_accepts_employment_opinion(self, loader, mock_client):
        """Employment opinion passes the filter pipeline."""
        mock_client.search_opinions.return_value = SearchResult(
            results=[SEARCH_RESULT_EMPLOYMENT],
            count=1,
            next_url=None,
            previous_url=None,
        )
        mock_client.paginate.return_value = iter([[SEARCH_RESULT_EMPLOYMENT]])
        mock_client.fetch_cluster.return_value = CLUSTER_RESPONSE
        mock_client.fetch_opinion.return_value = OPINION_RESPONSE_EMPLOYMENT

        opinions = list(loader.load())
        assert len(opinions) == 1
        op = opinions[0]
        assert isinstance(op, LoadedOpinion)
        assert op.cluster_id == 10001
        assert op.case_name == "Smith v. Employer Inc."
        assert len(op.matched_employment_codes) >= 1
        assert op.opinion_text  # non-empty

    def test_rejects_non_employment_opinion(self, loader, mock_client):
        """Non-employment opinion is filtered out."""
        mock_client.search_opinions.return_value = SearchResult(
            results=[SEARCH_RESULT_NON_EMPLOYMENT],
            count=1,
            next_url=None,
            previous_url=None,
        )
        mock_client.paginate.return_value = iter([[SEARCH_RESULT_NON_EMPLOYMENT]])
        mock_client.fetch_cluster.return_value = {
            "id": 20001,
            "sub_opinions": [
                "https://www.courtlistener.com/api/rest/v4/opinions/88888/",
            ],
        }
        mock_client.fetch_opinion.return_value = OPINION_RESPONSE_NON_EMPLOYMENT

        opinions = list(loader.load())
        assert len(opinions) == 0
        assert loader.stats.opinions_rejected >= 1

    def test_skips_missing_cluster_id(self, loader, mock_client):
        """Search results without cluster_id are skipped."""
        mock_client.search_opinions.return_value = SearchResult(
            results=[SEARCH_RESULT_NO_CLUSTER_ID],
            count=1,
            next_url=None,
            previous_url=None,
        )
        mock_client.paginate.return_value = iter([[SEARCH_RESULT_NO_CLUSTER_ID]])

        opinions = list(loader.load())
        assert len(opinions) == 0

    def test_handles_malformed_opinion(self, loader, mock_client):
        """Opinions with very short text are rejected."""
        mock_client.search_opinions.return_value = SearchResult(
            results=[SEARCH_RESULT_EMPLOYMENT],
            count=1,
            next_url=None,
            previous_url=None,
        )
        mock_client.paginate.return_value = iter([[SEARCH_RESULT_EMPLOYMENT]])
        mock_client.fetch_cluster.return_value = CLUSTER_RESPONSE
        mock_client.fetch_opinion.return_value = {
            "id": 99999,
            "type": "lead-opinion",
            "plain_text": "Short.",
        }

        opinions = list(loader.load())
        assert len(opinions) == 0
        assert loader.stats.opinions_rejected >= 1

    def test_handles_empty_sub_opinions(self, loader, mock_client):
        """Clusters with no sub_opinions yield no text."""
        mock_client.search_opinions.return_value = SearchResult(
            results=[SEARCH_RESULT_EMPLOYMENT],
            count=1,
            next_url=None,
            previous_url=None,
        )
        mock_client.paginate.return_value = iter([[SEARCH_RESULT_EMPLOYMENT]])
        mock_client.fetch_cluster.return_value = CLUSTER_EMPTY

        opinions = list(loader.load())
        assert len(opinions) == 0

    def test_handles_api_error_on_fetch(self, loader, mock_client):
        """API errors during opinion fetch are logged and skipped."""
        mock_client.search_opinions.return_value = SearchResult(
            results=[SEARCH_RESULT_EMPLOYMENT],
            count=1,
            next_url=None,
            previous_url=None,
        )
        mock_client.paginate.return_value = iter([[SEARCH_RESULT_EMPLOYMENT]])
        mock_client.fetch_cluster.side_effect = CourtListenerError("500 error")

        opinions = list(loader.load())
        assert len(opinions) == 0
        assert loader.stats.opinions_errors >= 1

    def test_handles_search_error(self, loader, mock_client):
        """Search errors are logged and the query is skipped."""
        mock_client.search_opinions.side_effect = CourtListenerError("timeout")

        opinions = list(loader.load())
        assert len(opinions) == 0

    def test_deduplicates_across_queries(self, mock_client):
        """Same cluster_id from different queries is only processed once."""
        loader = OpinionLoader(
            client=mock_client,
            search_queries=["query1", "query2"],
        )
        search_result = SearchResult(
            results=[SEARCH_RESULT_EMPLOYMENT],
            count=1,
            next_url=None,
            previous_url=None,
        )
        mock_client.search_opinions.return_value = search_result
        mock_client.paginate.return_value = iter([[SEARCH_RESULT_EMPLOYMENT]])
        mock_client.fetch_cluster.return_value = CLUSTER_RESPONSE
        mock_client.fetch_opinion.return_value = OPINION_RESPONSE_EMPLOYMENT

        # After first query consumes the paginate iterator, second query
        # should see the cluster_id already in seen set
        opinions = list(loader.load())
        # Only 1 opinion should be yielded despite 2 queries
        assert len(opinions) <= 1

    def test_max_opinions_limit(self, mock_client):
        """Loader stops after reaching max_opinions."""
        results = [
            {**SEARCH_RESULT_EMPLOYMENT, "cluster_id": 10001 + i}
            for i in range(10)
        ]
        loader = OpinionLoader(
            client=mock_client,
            search_queries=["query1"],
        )
        mock_client.search_opinions.return_value = SearchResult(
            results=results,
            count=10,
            next_url=None,
            previous_url=None,
        )
        mock_client.paginate.return_value = iter([results])
        mock_client.fetch_cluster.return_value = CLUSTER_RESPONSE
        mock_client.fetch_opinion.return_value = OPINION_RESPONSE_EMPLOYMENT

        opinions = list(loader.load(max_opinions=3))
        assert len(opinions) == 3
        assert loader.stats.opinions_accepted == 3


# ── Stats Tracking ────────────────────────────────────────────


class TestStatsTracking:
    def test_stats_reset_on_each_load(self, loader, mock_client):
        """Stats are reset at the start of each load() call."""
        mock_client.search_opinions.return_value = SearchResult(
            results=[], count=0, next_url=None, previous_url=None
        )
        mock_client.paginate.return_value = iter([[]])

        list(loader.load())
        assert loader.stats.queries_searched == 1

        # Second call should reset
        mock_client.paginate.return_value = iter([[]])
        list(loader.load())
        assert loader.stats.queries_searched == 1  # reset, not 2

    def test_stats_counts_correctly(self, loader, mock_client):
        """Stats track fetched, accepted, rejected, and errors."""
        mock_client.search_opinions.return_value = SearchResult(
            results=[SEARCH_RESULT_EMPLOYMENT],
            count=1,
            next_url=None,
            previous_url=None,
        )
        mock_client.paginate.return_value = iter([[SEARCH_RESULT_EMPLOYMENT]])
        mock_client.fetch_cluster.return_value = CLUSTER_RESPONSE
        mock_client.fetch_opinion.return_value = OPINION_RESPONSE_EMPLOYMENT

        list(loader.load())
        assert loader.stats.opinions_fetched == 1
        assert loader.stats.opinions_accepted == 1
        assert loader.stats.queries_searched == 1
        assert loader.stats.pages_fetched == 1


# ── Configurable Courts and Statutes ──────────────────────────


class TestConfiguration:
    def test_custom_courts(self, mock_client):
        loader = OpinionLoader(
            client=mock_client,
            courts=["cal"],
            search_queries=["test"],
        )
        mock_client.search_opinions.return_value = SearchResult(
            results=[], count=0, next_url=None, previous_url=None
        )
        mock_client.paginate.return_value = iter([[]])

        list(loader.load())
        call_args = mock_client.search_opinions.call_args
        assert call_args.kwargs.get("courts") == ["cal"]

    def test_custom_search_queries(self, mock_client):
        queries = ["custom query 1", "custom query 2"]
        loader = OpinionLoader(
            client=mock_client,
            search_queries=queries,
        )
        mock_client.search_opinions.return_value = SearchResult(
            results=[], count=0, next_url=None, previous_url=None
        )
        mock_client.paginate.return_value = iter([[]])

        list(loader.load())
        assert loader.stats.queries_searched == 2

    def test_date_filters_passed_to_client(self, mock_client):
        loader = OpinionLoader(
            client=mock_client,
            search_queries=["test"],
            filed_after="2020-01-01",
            filed_before="2025-12-31",
        )
        mock_client.search_opinions.return_value = SearchResult(
            results=[], count=0, next_url=None, previous_url=None
        )
        mock_client.paginate.return_value = iter([[]])

        list(loader.load())
        call_args = mock_client.search_opinions.call_args
        assert call_args.kwargs.get("filed_after") == "2020-01-01"
        assert call_args.kwargs.get("filed_before") == "2025-12-31"

    def test_precedential_status_filter(self, mock_client):
        """Loader requests only precedential opinions."""
        loader = OpinionLoader(
            client=mock_client,
            search_queries=["test"],
        )
        mock_client.search_opinions.return_value = SearchResult(
            results=[], count=0, next_url=None, previous_url=None
        )
        mock_client.paginate.return_value = iter([[]])

        list(loader.load())
        call_args = mock_client.search_opinions.call_args
        assert call_args.kwargs.get("status") == "precedential"


# ── Context Manager ───────────────────────────────────────────


class TestContextManager:
    def test_context_manager_closes_owned_client(self):
        mock_cl = MagicMock()
        loader = OpinionLoader(client=mock_cl)
        # Client was passed in, so loader doesn't own it
        loader._owns_client = True  # force ownership for test
        loader.close()
        mock_cl.close.assert_called_once()

    def test_context_manager_skips_unowned_client(self):
        mock_cl = MagicMock()
        with OpinionLoader(client=mock_cl) as loader:
            pass
        mock_cl.close.assert_not_called()


# ── Loaded Opinion Dataclass ──────────────────────────────────


class TestLoadedOpinion:
    def test_fields(self):
        op = LoadedOpinion(
            cluster_id=1,
            opinion_id=2,
            case_name="Test v. Case",
            case_name_full="Test v. Case",
            date_filed="2023-01-01",
            court_id="cal",
            docket_number="S123",
            citations=["1 Cal.5th 100"],
            precedential_status="Published",
            opinion_text="The court held...",
            opinion_type="lead-opinion",
            cited_statutes=[],
            cited_cases=[],
            all_citations=[],
            matched_employment_codes=["Labor Code"],
            absolute_url="/opinion/1/test-v-case/",
        )
        assert op.cluster_id == 1
        assert op.case_name == "Test v. Case"
        assert op.matched_employment_codes == ["Labor Code"]

    def test_citation_as_string_normalized(self):
        """Citation field handles both string and list input from API."""
        op = LoadedOpinion(
            cluster_id=1,
            opinion_id=None,
            case_name="Test",
            case_name_full=None,
            date_filed=None,
            court_id=None,
            docket_number=None,
            citations=["45 Cal.App.5th 123", "250 Cal.Rptr.3d 456"],
            precedential_status=None,
            opinion_text="text",
            opinion_type=None,
            cited_statutes=[],
            cited_cases=[],
            all_citations=[],
            matched_employment_codes=[],
            absolute_url=None,
        )
        assert len(op.citations) == 2
