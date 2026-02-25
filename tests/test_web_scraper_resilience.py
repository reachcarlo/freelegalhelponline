"""Tests for web scraper retry logic, circuit breaker, and content validation.

Uses respx to mock httpx requests and unittest.mock to patch time.sleep
for fast test execution.
"""

from unittest.mock import patch

import httpx
import pytest
import respx

from employee_help.scraper.extractors.statute import (
    StatutoryExtractor,
    _is_proxy_error,
)


# ── Proxy Error Detection Tests ─────────────────────────────


class TestIsProxyError:
    def test_detects_proxy_error(self):
        assert _is_proxy_error("<html><body><h1>Proxy Error</h1></body></html>")

    def test_detects_502_bad_gateway(self):
        assert _is_proxy_error("<html><body>502 Bad Gateway</body></html>")

    def test_detects_503_service_unavailable(self):
        assert _is_proxy_error("<html><body>503 Service Unavailable</body></html>")

    def test_normal_html_not_error(self):
        assert not _is_proxy_error("<html><body><h1>Labor Code</h1></body></html>")

    def test_empty_string_not_error(self):
        assert not _is_proxy_error("")

    def test_case_insensitive(self):
        assert _is_proxy_error("<html><body>PROXY ERROR</body></html>")

    def test_only_checks_first_2000_chars(self):
        # Proxy error text deep in the body should not trigger
        html = "x" * 2500 + "Proxy Error"
        assert not _is_proxy_error(html)


# ── Retry Logic Tests ───────────────────────────────────────


class TestRetryLogic:
    @respx.mock
    def test_success_on_first_attempt(self):
        """Normal successful request - no retry needed."""
        route = respx.get("https://leginfo.legislature.ca.gov/test").mock(
            return_value=httpx.Response(200, text="<html>OK</html>")
        )

        with patch("employee_help.scraper.extractors.statute.time.sleep"):
            with StatutoryExtractor("LAB", rate_limit=0) as ext:
                result = ext._fetch("https://leginfo.legislature.ca.gov/test")

        assert result == "<html>OK</html>"
        assert route.call_count == 1

    @respx.mock
    def test_retry_succeeds_after_502(self):
        """Retry recovers from a transient 502 error."""
        route = respx.get("https://leginfo.legislature.ca.gov/test").mock(
            side_effect=[
                httpx.Response(502),
                httpx.Response(200, text="<html>OK</html>"),
            ]
        )

        with patch("employee_help.scraper.extractors.statute.time.sleep"):
            with StatutoryExtractor("LAB", rate_limit=0) as ext:
                result = ext._fetch("https://leginfo.legislature.ca.gov/test")

        assert result == "<html>OK</html>"
        assert route.call_count == 2

    @respx.mock
    def test_retry_succeeds_after_multiple_failures(self):
        """Retry recovers after two consecutive failures."""
        route = respx.get("https://leginfo.legislature.ca.gov/test").mock(
            side_effect=[
                httpx.Response(500),
                httpx.Response(502),
                httpx.Response(200, text="<html>OK</html>"),
            ]
        )

        with patch("employee_help.scraper.extractors.statute.time.sleep"):
            with StatutoryExtractor("LAB", rate_limit=0) as ext:
                result = ext._fetch("https://leginfo.legislature.ca.gov/test")

        assert result == "<html>OK</html>"
        assert route.call_count == 3

    @respx.mock
    def test_retry_exhausted_raises(self):
        """All retries exhausted raises HTTPStatusError."""
        route = respx.get("https://leginfo.legislature.ca.gov/test").mock(
            side_effect=[
                httpx.Response(502),
                httpx.Response(502),
                httpx.Response(502),
                httpx.Response(502),
            ]
        )

        with patch("employee_help.scraper.extractors.statute.time.sleep"):
            with StatutoryExtractor("LAB", rate_limit=0) as ext:
                with pytest.raises(httpx.HTTPStatusError):
                    ext._fetch("https://leginfo.legislature.ca.gov/test")

        assert route.call_count == 4  # 1 initial + 3 retries

    @respx.mock
    def test_retry_on_connect_error(self):
        """Retry recovers from connection errors."""
        route = respx.get("https://leginfo.legislature.ca.gov/test").mock(
            side_effect=[
                httpx.ConnectError("Connection refused"),
                httpx.Response(200, text="<html>OK</html>"),
            ]
        )

        with patch("employee_help.scraper.extractors.statute.time.sleep"):
            with StatutoryExtractor("LAB", rate_limit=0) as ext:
                result = ext._fetch("https://leginfo.legislature.ca.gov/test")

        assert result == "<html>OK</html>"
        assert route.call_count == 2

    @respx.mock
    def test_retry_on_read_timeout(self):
        """Retry recovers from read timeouts."""
        route = respx.get("https://leginfo.legislature.ca.gov/test").mock(
            side_effect=[
                httpx.ReadTimeout("Read timed out"),
                httpx.Response(200, text="<html>OK</html>"),
            ]
        )

        with patch("employee_help.scraper.extractors.statute.time.sleep"):
            with StatutoryExtractor("LAB", rate_limit=0) as ext:
                result = ext._fetch("https://leginfo.legislature.ca.gov/test")

        assert result == "<html>OK</html>"

    @respx.mock
    def test_exponential_backoff_timing(self):
        """Verify exponential backoff delays: 2s, 4s, 8s."""
        respx.get("https://leginfo.legislature.ca.gov/test").mock(
            side_effect=[
                httpx.Response(502),
                httpx.Response(502),
                httpx.Response(502),
                httpx.Response(502),
            ]
        )

        with patch("employee_help.scraper.extractors.statute.time.sleep") as mock_sleep:
            with StatutoryExtractor("LAB", rate_limit=0) as ext:
                with pytest.raises(httpx.HTTPStatusError):
                    ext._fetch("https://leginfo.legislature.ca.gov/test")

        # Should have 3 backoff sleeps (between retries).
        # Filter by exact integer values to exclude rate-limit sleeps (~3.0s).
        backoff_calls = [
            c for c in mock_sleep.call_args_list
            if c.args and c.args[0] in (2, 4, 8)
        ]
        assert len(backoff_calls) == 3
        assert backoff_calls[0].args[0] == 2  # 2^1
        assert backoff_calls[1].args[0] == 4  # 2^2
        assert backoff_calls[2].args[0] == 8  # 2^3


# ── Proxy Error Retry Tests ─────────────────────────────────


class TestProxyErrorRetry:
    @respx.mock
    def test_proxy_error_body_triggers_retry(self):
        """200 response with proxy error body should be retried."""
        route = respx.get("https://leginfo.legislature.ca.gov/test").mock(
            side_effect=[
                httpx.Response(200, text="<html><body>Proxy Error</body></html>"),
                httpx.Response(200, text="<html><body>Real content</body></html>"),
            ]
        )

        with patch("employee_help.scraper.extractors.statute.time.sleep"):
            with StatutoryExtractor("LAB", rate_limit=0) as ext:
                result = ext._fetch("https://leginfo.legislature.ca.gov/test")

        assert result == "<html><body>Real content</body></html>"
        assert route.call_count == 2

    @respx.mock
    def test_proxy_error_exhausts_retries(self):
        """Persistent proxy errors exhaust retries and raise."""
        respx.get("https://leginfo.legislature.ca.gov/test").mock(
            side_effect=[
                httpx.Response(200, text="<html>502 Bad Gateway</html>"),
                httpx.Response(200, text="<html>502 Bad Gateway</html>"),
                httpx.Response(200, text="<html>502 Bad Gateway</html>"),
                httpx.Response(200, text="<html>502 Bad Gateway</html>"),
            ]
        )

        with patch("employee_help.scraper.extractors.statute.time.sleep"):
            with StatutoryExtractor("LAB", rate_limit=0) as ext:
                with pytest.raises(RuntimeError, match="Proxy error"):
                    ext._fetch("https://leginfo.legislature.ca.gov/test")


# ── Circuit Breaker Tests ───────────────────────────────────


class TestCircuitBreaker:
    @respx.mock
    def test_circuit_breaker_trips_at_threshold(self):
        """Circuit breaker trips when >50% of requests fail (after ≥6 requests)."""
        url = "https://leginfo.legislature.ca.gov/test"

        # Pre-load 6 failure responses (max_retries=0 means 1 attempt each)
        respx.get(url).mock(
            side_effect=[
                httpx.Response(502),
                httpx.Response(502),
                httpx.Response(502),
                httpx.Response(502),
                httpx.Response(502),
                httpx.Response(502),
            ]
        )

        with patch("employee_help.scraper.extractors.statute.time.sleep"):
            with StatutoryExtractor("LAB", rate_limit=0) as ext:
                # Make 6 failed requests (max_retries=0 → 1 attempt each)
                for _ in range(6):
                    try:
                        ext._fetch(url, max_retries=0)
                    except httpx.HTTPStatusError:
                        pass

                # 7th request should trigger circuit breaker before HTTP call
                with pytest.raises(RuntimeError, match="Circuit breaker"):
                    ext._fetch(url)

    @respx.mock
    def test_circuit_breaker_allows_when_under_threshold(self):
        """Circuit breaker allows requests when failure rate is acceptable."""
        url = "https://leginfo.legislature.ca.gov/test"

        # Pre-load: 3 successes, 2 failures, 1 success
        respx.get(url).mock(
            side_effect=[
                httpx.Response(200, text="OK"),  # success 1
                httpx.Response(200, text="OK"),  # success 2
                httpx.Response(200, text="OK"),  # success 3
                httpx.Response(502),             # failure 1
                httpx.Response(502),             # failure 2
                httpx.Response(200, text="OK"),  # success 4
            ]
        )

        with patch("employee_help.scraper.extractors.statute.time.sleep"):
            with StatutoryExtractor("LAB", rate_limit=0) as ext:
                # 3 successes
                for _ in range(3):
                    ext._fetch(url)

                # 2 failures (max_retries=0)
                for _ in range(2):
                    try:
                        ext._fetch(url, max_retries=0)
                    except httpx.HTTPStatusError:
                        pass

                # 6th request: _request_count=5 < 6, circuit breaker skipped
                result = ext._fetch(url)
                assert result == "OK"

    def test_error_count_starts_at_zero(self):
        """Fresh extractor has zero error count."""
        ext = StatutoryExtractor("LAB")
        assert ext._error_count == 0
        assert ext._request_count == 0

    @respx.mock
    def test_error_count_increments_on_failure(self):
        """Error count tracks failed requests."""
        url = "https://leginfo.legislature.ca.gov/test"
        respx.get(url).mock(
            side_effect=[
                httpx.Response(502),
                httpx.Response(502),
                httpx.Response(502),
                httpx.Response(502),
            ]
        )

        with patch("employee_help.scraper.extractors.statute.time.sleep"):
            with StatutoryExtractor("LAB", rate_limit=0) as ext:
                with pytest.raises(httpx.HTTPStatusError):
                    ext._fetch(url)
                # 1 initial + 3 retries = 4 requests, all failed
                assert ext._error_count == 4


# ── Context Manager Tests ───────────────────────────────────


class TestContextManager:
    def test_fetch_without_context_manager_raises(self):
        """_fetch() raises RuntimeError if not used as context manager."""
        ext = StatutoryExtractor("LAB")
        with pytest.raises(RuntimeError, match="context manager"):
            ext._fetch("https://example.com")
