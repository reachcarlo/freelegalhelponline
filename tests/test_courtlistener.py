"""Tests for the CourtListener API client.

Uses respx to mock httpx requests and unittest.mock to patch time.sleep
for fast test execution.
"""

from unittest.mock import patch

import httpx
import pytest
import respx

from employee_help.scraper.extractors.courtlistener import (
    API_BASE,
    AuthenticationError,
    CourtListenerClient,
    CourtListenerError,
    RateLimitError,
    SearchResult,
    _parse_retry_after,
)


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def client():
    """Create a CourtListenerClient with a test token."""
    c = CourtListenerClient(api_token="test-token-123", max_retries=2)
    yield c
    c.close()


# ── Sample response data ──────────────────────────────────────

SEARCH_RESPONSE = {
    "count": 42,
    "next": f"{API_BASE}/search/?cursor=cD0yMDIz",
    "previous": None,
    "results": [
        {
            "caseName": "Smith v. Employer, Inc.",
            "court_id": "cal",
            "dateFiled": "2023-06-15",
            "cluster_id": 12345,
            "citation": ["45 Cal.App.5th 123"],
            "citeCount": 8,
        },
        {
            "caseName": "Jones v. Widget Corp.",
            "court_id": "calctapp2d",
            "dateFiled": "2022-11-01",
            "cluster_id": 67890,
            "citation": ["92 Cal.App.5th 456"],
            "citeCount": 3,
        },
    ],
}

SEARCH_PAGE_2 = {
    "count": 42,
    "next": None,
    "previous": f"{API_BASE}/search/?cursor=prev123",
    "results": [
        {
            "caseName": "Davis v. Corporation",
            "court_id": "cal",
            "dateFiled": "2021-03-20",
            "cluster_id": 11111,
            "citation": ["10 Cal.5th 789"],
            "citeCount": 15,
        },
    ],
}

OPINION_RESPONSE = {
    "id": 99999,
    "cluster": f"{API_BASE}/clusters/12345/",
    "html_with_citations": "<p>The court held that under Labor Code section 1102.5...</p>",
    "plain_text": "The court held that under Labor Code section 1102.5...",
    "type": "lead-opinion",
    "opinions_cited": [
        f"{API_BASE}/opinions/11111/",
        f"{API_BASE}/opinions/22222/",
    ],
}

CLUSTER_RESPONSE = {
    "id": 12345,
    "case_name": "Smith v. Employer, Inc.",
    "case_name_full": "John Smith v. Employer, Inc.",
    "date_filed": "2023-06-15",
    "citations": [
        {"volume": 45, "reporter": "Cal.App.5th", "page": "123", "type": 2},
    ],
    "sub_opinions": [f"{API_BASE}/opinions/99999/"],
    "precedential_status": "Published",
    "docket": f"{API_BASE}/dockets/54321/",
}

CITATION_LOOKUP_RESPONSE = [
    {
        "citation": "45 Cal.App.5th 123",
        "normalized_citations": ["45 Cal.App.5th 123"],
        "start_index": 42,
        "end_index": 62,
        "status": 200,
        "error_message": "",
        "clusters": [
            {
                "id": 12345,
                "case_name": "Smith v. Employer, Inc.",
                "absolute_url": "/opinion/12345/smith-v-employer-inc/",
                "date_filed": "2023-06-15",
            }
        ],
    }
]

CITING_OPINIONS_RESPONSE = {
    "count": 2,
    "next": None,
    "previous": None,
    "results": [
        {
            "id": 501,
            "citing_opinion": f"{API_BASE}/opinions/99999/",
            "cited_opinion": f"{API_BASE}/opinions/88888/",
            "depth": 3,
        },
    ],
}


# ── Authentication ────────────────────────────────────────────


class TestAuthentication:
    def test_token_in_authorization_header(self):
        """Client sends Authorization: Token header on every request."""
        with CourtListenerClient(api_token="my-secret-token") as c:
            assert c._client.headers["Authorization"] == "Token my-secret-token"

    def test_missing_token_raises(self):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(AuthenticationError, match="API token required"):
                CourtListenerClient(api_token="")

    def test_env_var_fallback(self):
        with patch.dict("os.environ", {"COURTLISTENER_API_TOKEN": "env-token"}):
            with CourtListenerClient() as c:
                assert c._client.headers["Authorization"] == "Token env-token"

    @respx.mock
    def test_401_raises_authentication_error(self, client):
        respx.get(f"{API_BASE}/search/").mock(
            return_value=httpx.Response(401, json={"detail": "Invalid token."})
        )
        with pytest.raises(AuthenticationError, match="authentication failed"):
            client.search_opinions("test query")


# ── Search Opinions ───────────────────────────────────────────


class TestSearchOpinions:
    @respx.mock
    def test_basic_search(self, client):
        route = respx.get(f"{API_BASE}/search/").mock(
            return_value=httpx.Response(200, json=SEARCH_RESPONSE)
        )
        result = client.search_opinions("wrongful termination")
        assert isinstance(result, SearchResult)
        assert len(result.results) == 2
        assert result.count == 42
        assert result.next_url is not None
        assert result.previous_url is None
        # Verify query params
        request = route.calls[0].request
        assert "q=wrongful+termination" in str(request.url) or "q=wrongful%20termination" in str(request.url)

    @respx.mock
    def test_search_with_court_filter(self, client):
        route = respx.get(f"{API_BASE}/search/").mock(
            return_value=httpx.Response(200, json=SEARCH_RESPONSE)
        )
        client.search_opinions("FEHA", courts=["cal", "calctapp"])
        request = route.calls[0].request
        url_str = str(request.url)
        assert "court=cal" in url_str
        assert "court=calctapp" in url_str

    @respx.mock
    def test_search_with_date_filters(self, client):
        route = respx.get(f"{API_BASE}/search/").mock(
            return_value=httpx.Response(200, json=SEARCH_RESPONSE)
        )
        client.search_opinions(
            "Labor Code",
            filed_after="2020-01-01",
            filed_before="2025-12-31",
        )
        request = route.calls[0].request
        url_str = str(request.url)
        assert "filed_after=2020-01-01" in url_str
        assert "filed_before=2025-12-31" in url_str

    @respx.mock
    def test_search_with_status_and_order(self, client):
        route = respx.get(f"{API_BASE}/search/").mock(
            return_value=httpx.Response(200, json=SEARCH_RESPONSE)
        )
        client.search_opinions(
            "retaliation",
            status="precedential",
            order_by="dateFiled desc",
        )
        request = route.calls[0].request
        url_str = str(request.url)
        assert "status=precedential" in url_str

    @respx.mock
    def test_search_empty_results(self, client):
        empty = {"count": 0, "next": None, "previous": None, "results": []}
        respx.get(f"{API_BASE}/search/").mock(
            return_value=httpx.Response(200, json=empty)
        )
        result = client.search_opinions("xyznonexistent12345")
        assert result.results == []
        assert result.count == 0
        assert result.next_url is None


# ── Pagination ────────────────────────────────────────────────


class TestPagination:
    @respx.mock
    def test_fetch_next_page(self, client):
        # Route matches the cursor URL used in fetch_next_page
        respx.get(url__regex=r".*/search/\?cursor=").mock(
            return_value=httpx.Response(200, json=SEARCH_PAGE_2)
        )
        initial = SearchResult(
            results=SEARCH_RESPONSE["results"],
            count=42,
            next_url=SEARCH_RESPONSE["next"],
            previous_url=None,
        )
        page2 = client.fetch_next_page(initial)
        assert page2 is not None
        assert len(page2.results) == 1
        assert page2.results[0]["caseName"] == "Davis v. Corporation"
        assert page2.next_url is None

    def test_fetch_next_page_none_when_no_more(self, client):
        no_next = SearchResult(results=[], count=0, next_url=None, previous_url=None)
        assert client.fetch_next_page(no_next) is None

    @respx.mock
    def test_paginate_all_pages(self, client):
        # Use side_effect for sequential responses on the same base URL
        respx.get(url__regex=r".*/search/").mock(
            side_effect=[
                httpx.Response(200, json=SEARCH_RESPONSE),
                httpx.Response(200, json=SEARCH_PAGE_2),
            ]
        )
        initial = client.search_opinions("test")
        pages = list(client.paginate(initial))
        assert len(pages) == 2
        assert len(pages[0]) == 2  # first page has 2 results
        assert len(pages[1]) == 1  # second page has 1 result

    @respx.mock
    def test_paginate_max_pages(self, client):
        respx.get(url__regex=r".*/search/").mock(
            return_value=httpx.Response(200, json=SEARCH_RESPONSE)
        )
        # Should not fetch page 2 when max_pages=1
        initial = client.search_opinions("test")
        pages = list(client.paginate(initial, max_pages=1))
        assert len(pages) == 1


# ── Fetch Opinion ─────────────────────────────────────────────


class TestFetchOpinion:
    @respx.mock
    def test_fetch_opinion(self, client):
        respx.get(f"{API_BASE}/opinions/99999/").mock(
            return_value=httpx.Response(200, json=OPINION_RESPONSE)
        )
        opinion = client.fetch_opinion(99999)
        assert opinion["id"] == 99999
        assert "Labor Code" in opinion["html_with_citations"]
        assert opinion["type"] == "lead-opinion"

    @respx.mock
    def test_fetch_opinion_with_fields(self, client):
        route = respx.get(f"{API_BASE}/opinions/99999/").mock(
            return_value=httpx.Response(200, json={"id": 99999, "type": "lead-opinion"})
        )
        client.fetch_opinion(99999, fields=["id", "type"])
        request = route.calls[0].request
        url_str = str(request.url)
        assert "fields=id%2Ctype" in url_str or "fields=id,type" in url_str


# ── Fetch Cluster ─────────────────────────────────────────────


class TestFetchCluster:
    @respx.mock
    def test_fetch_cluster(self, client):
        respx.get(f"{API_BASE}/clusters/12345/").mock(
            return_value=httpx.Response(200, json=CLUSTER_RESPONSE)
        )
        cluster = client.fetch_cluster(12345)
        assert cluster["id"] == 12345
        assert cluster["case_name"] == "Smith v. Employer, Inc."
        assert cluster["precedential_status"] == "Published"
        assert len(cluster["citations"]) == 1

    @respx.mock
    def test_fetch_cluster_with_fields(self, client):
        route = respx.get(f"{API_BASE}/clusters/12345/").mock(
            return_value=httpx.Response(200, json={"id": 12345, "case_name": "Test"})
        )
        client.fetch_cluster(12345, fields=["id", "case_name"])
        request = route.calls[0].request
        url_str = str(request.url)
        assert "fields=" in url_str


# ── Citation Lookup ───────────────────────────────────────────


class TestCitationLookup:
    @respx.mock
    def test_lookup_by_text(self, client):
        respx.post(f"{API_BASE}/citation-lookup/").mock(
            return_value=httpx.Response(200, json=CITATION_LOOKUP_RESPONSE)
        )
        results = client.lookup_citation(
            text="See Smith v. Employer, Inc., 45 Cal.App.5th 123 (2023)."
        )
        assert len(results) == 1
        assert results[0]["status"] == 200
        assert results[0]["clusters"][0]["id"] == 12345

    @respx.mock
    def test_lookup_by_components(self, client):
        respx.post(f"{API_BASE}/citation-lookup/").mock(
            return_value=httpx.Response(200, json=CITATION_LOOKUP_RESPONSE)
        )
        results = client.lookup_citation(
            reporter="Cal.App.5th", volume="45", page="123"
        )
        assert len(results) == 1

    def test_lookup_missing_params_raises(self, client):
        with pytest.raises(ValueError, match="Provide either"):
            client.lookup_citation()

    def test_lookup_partial_components_raises(self, client):
        with pytest.raises(ValueError, match="Provide either"):
            client.lookup_citation(reporter="Cal.App.5th", volume="45")

    @respx.mock
    def test_lookup_not_found(self, client):
        not_found = [
            {
                "citation": "999 Cal.App.99th 999",
                "status": 404,
                "error_message": "Citation not found",
                "clusters": [],
            }
        ]
        respx.post(f"{API_BASE}/citation-lookup/").mock(
            return_value=httpx.Response(200, json=not_found)
        )
        results = client.lookup_citation(
            text="See 999 Cal.App.99th 999."
        )
        assert results[0]["status"] == 404
        assert results[0]["clusters"] == []


# ── Citation Graph ────────────────────────────────────────────


class TestCitationGraph:
    @respx.mock
    def test_fetch_citing_opinions(self, client):
        respx.get(f"{API_BASE}/opinions-cited/").mock(
            return_value=httpx.Response(200, json=CITING_OPINIONS_RESPONSE)
        )
        result = client.fetch_citing_opinions(99999)
        assert isinstance(result, SearchResult)
        assert len(result.results) == 1
        assert result.results[0]["depth"] == 3


# ── Rate Limit Handling ───────────────────────────────────────


class TestRateLimitHandling:
    @respx.mock
    @patch("employee_help.scraper.extractors.courtlistener.time.sleep")
    def test_429_retry_with_retry_after(self, mock_sleep, client):
        """Client retries after 429 using Retry-After header."""
        respx.get(f"{API_BASE}/search/").mock(
            side_effect=[
                httpx.Response(
                    429,
                    headers={"Retry-After": "2"},
                    json={"detail": "Rate limit exceeded"},
                ),
                httpx.Response(200, json=SEARCH_RESPONSE),
            ]
        )
        result = client.search_opinions("test")
        assert len(result.results) == 2
        # Should have slept for the Retry-After duration
        mock_sleep.assert_called()
        sleep_arg = mock_sleep.call_args[0][0]
        assert sleep_arg == 2.0

    @respx.mock
    @patch("employee_help.scraper.extractors.courtlistener.time.sleep")
    def test_429_exhausts_retries(self, mock_sleep, client):
        """Client raises RateLimitError after exhausting retries on 429."""
        respx.get(f"{API_BASE}/search/").mock(
            return_value=httpx.Response(
                429,
                headers={"Retry-After": "60"},
                json={"detail": "Rate limit exceeded"},
            )
        )
        with pytest.raises(RateLimitError) as exc_info:
            client.search_opinions("test")
        assert exc_info.value.retry_after == 60.0

    @respx.mock
    @patch("employee_help.scraper.extractors.courtlistener.time.sleep")
    def test_429_without_retry_after_uses_backoff(self, mock_sleep, client):
        """Client falls back to exponential backoff when no Retry-After header."""
        respx.get(f"{API_BASE}/search/").mock(
            side_effect=[
                httpx.Response(429, json={"detail": "Rate limit exceeded"}),
                httpx.Response(200, json=SEARCH_RESPONSE),
            ]
        )
        result = client.search_opinions("test")
        assert len(result.results) == 2
        # Should have used initial backoff (1.0s) since no Retry-After
        mock_sleep.assert_called()
        sleep_arg = mock_sleep.call_args[0][0]
        assert sleep_arg == 1.0


# ── Retry on Transient Errors ─────────────────────────────────


class TestRetryTransientErrors:
    @respx.mock
    @patch("employee_help.scraper.extractors.courtlistener.time.sleep")
    def test_retry_on_500(self, mock_sleep, client):
        respx.get(f"{API_BASE}/opinions/1/").mock(
            side_effect=[
                httpx.Response(500),
                httpx.Response(200, json=OPINION_RESPONSE),
            ]
        )
        opinion = client.fetch_opinion(1)
        assert opinion["id"] == 99999
        mock_sleep.assert_called_once()

    @respx.mock
    @patch("employee_help.scraper.extractors.courtlistener.time.sleep")
    def test_retry_on_502(self, mock_sleep, client):
        respx.get(f"{API_BASE}/clusters/1/").mock(
            side_effect=[
                httpx.Response(502),
                httpx.Response(200, json=CLUSTER_RESPONSE),
            ]
        )
        cluster = client.fetch_cluster(1)
        assert cluster["id"] == 12345

    @respx.mock
    @patch("employee_help.scraper.extractors.courtlistener.time.sleep")
    def test_retry_on_503(self, mock_sleep, client):
        respx.get(f"{API_BASE}/opinions/1/").mock(
            side_effect=[
                httpx.Response(503),
                httpx.Response(200, json=OPINION_RESPONSE),
            ]
        )
        opinion = client.fetch_opinion(1)
        assert opinion["id"] == 99999

    @respx.mock
    @patch("employee_help.scraper.extractors.courtlistener.time.sleep")
    def test_retry_on_504(self, mock_sleep, client):
        respx.get(f"{API_BASE}/opinions/1/").mock(
            side_effect=[
                httpx.Response(504),
                httpx.Response(200, json=OPINION_RESPONSE),
            ]
        )
        opinion = client.fetch_opinion(1)
        assert opinion["id"] == 99999

    @respx.mock
    @patch("employee_help.scraper.extractors.courtlistener.time.sleep")
    def test_exhausts_retries_on_500(self, mock_sleep, client):
        """Client raises after max retries on persistent 500."""
        respx.get(f"{API_BASE}/opinions/1/").mock(
            return_value=httpx.Response(500)
        )
        with pytest.raises(CourtListenerError, match="error 500"):
            client.fetch_opinion(1)
        # max_retries=2, so 3 total attempts, 2 sleeps
        assert mock_sleep.call_count == 2

    @respx.mock
    @patch("employee_help.scraper.extractors.courtlistener.time.sleep")
    def test_exponential_backoff(self, mock_sleep, client):
        """Backoff doubles on each retry."""
        respx.get(f"{API_BASE}/opinions/1/").mock(
            return_value=httpx.Response(500)
        )
        with pytest.raises(CourtListenerError):
            client.fetch_opinion(1)
        calls = [c[0][0] for c in mock_sleep.call_args_list]
        assert calls[0] == 1.0  # initial backoff
        assert calls[1] == 2.0  # doubled

    @respx.mock
    @patch("employee_help.scraper.extractors.courtlistener.time.sleep")
    def test_retry_on_transport_error(self, mock_sleep, client):
        """Client retries on connection errors."""
        respx.get(f"{API_BASE}/opinions/1/").mock(
            side_effect=[
                httpx.ConnectError("Connection refused"),
                httpx.Response(200, json=OPINION_RESPONSE),
            ]
        )
        opinion = client.fetch_opinion(1)
        assert opinion["id"] == 99999

    @respx.mock
    @patch("employee_help.scraper.extractors.courtlistener.time.sleep")
    def test_transport_error_exhausts_retries(self, mock_sleep, client):
        """Client raises after max retries on persistent connection errors."""
        respx.get(f"{API_BASE}/opinions/1/").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        with pytest.raises(CourtListenerError, match="connection error"):
            client.fetch_opinion(1)


# ── Other Error Codes ─────────────────────────────────────────


class TestOtherErrors:
    @respx.mock
    def test_404_raises_error(self, client):
        respx.get(f"{API_BASE}/opinions/99999999/").mock(
            return_value=httpx.Response(404, json={"detail": "Not found."})
        )
        with pytest.raises(CourtListenerError, match="404"):
            client.fetch_opinion(99999999)

    @respx.mock
    def test_403_raises_error(self, client):
        respx.get(f"{API_BASE}/opinions/1/").mock(
            return_value=httpx.Response(403, json={"detail": "Forbidden"})
        )
        with pytest.raises(CourtListenerError, match="403"):
            client.fetch_opinion(1)


# ── Context Manager ───────────────────────────────────────────


class TestContextManager:
    def test_context_manager(self):
        with CourtListenerClient(api_token="test-token") as c:
            assert c._client is not None
        # After exiting, client should be closed
        assert c._client.is_closed


# ── Helper Functions ──────────────────────────────────────────


class TestParseRetryAfter:
    def test_integer_value(self):
        response = httpx.Response(429, headers={"Retry-After": "30"})
        assert _parse_retry_after(response) == 30.0

    def test_float_value(self):
        response = httpx.Response(429, headers={"Retry-After": "1.5"})
        assert _parse_retry_after(response) == 1.5

    def test_missing_header(self):
        response = httpx.Response(429)
        assert _parse_retry_after(response) is None

    def test_invalid_value(self):
        response = httpx.Response(429, headers={"Retry-After": "not-a-number"})
        assert _parse_retry_after(response) is None


# ── Constants ─────────────────────────────────────────────────


class TestConstants:
    def test_ca_courts_contains_supreme_court(self):
        from employee_help.scraper.extractors.courtlistener import CA_COURTS

        assert "cal" in CA_COURTS

    def test_ca_courts_contains_appellate(self):
        from employee_help.scraper.extractors.courtlistener import CA_COURTS

        assert "calctapp" in CA_COURTS
        assert "calctapp1d" in CA_COURTS
        assert "calctapp6d" in CA_COURTS
