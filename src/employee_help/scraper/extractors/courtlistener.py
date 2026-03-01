"""CourtListener REST API client for California case law.

Authenticated client for the CourtListener v4 API (Free Law Project).
Supports searching opinions, fetching opinion text and cluster metadata,
citation lookup/verification, cursor-based pagination, rate limit
handling (5,000 req/hr), and retry with exponential backoff on
transient errors.

Usage:
    client = CourtListenerClient(api_token="your-token")
    results = client.search_opinions("wrongful termination", courts=["cal"])
    for page in client.paginate(results):
        for opinion_summary in page:
            opinion = client.fetch_opinion(opinion_summary["cluster_id"])
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

import httpx
import structlog

logger = structlog.get_logger(__name__)

BASE_URL = "https://www.courtlistener.com"
API_BASE = f"{BASE_URL}/api/rest/v4"

# Default rate limit: 5,000 requests/hour
DEFAULT_RATE_LIMIT = 5000
DEFAULT_RATE_WINDOW = 3600  # seconds

# Retry configuration
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # seconds
BACKOFF_MULTIPLIER = 2.0

# California court codes
CA_COURTS = frozenset(
    {
        "cal",  # Supreme Court
        "calctapp",  # Court of Appeal (all districts)
        "calctapp1d",
        "calctapp2d",
        "calctapp3d",
        "calctapp4d",
        "calctapp5d",
        "calctapp6d",
        "calappdeptsuper",  # Appellate Division of Superior Court
    }
)


class CourtListenerError(Exception):
    """Base exception for CourtListener API errors."""


class RateLimitError(CourtListenerError):
    """Raised when the API rate limit is exceeded."""

    def __init__(self, retry_after: float | None = None):
        self.retry_after = retry_after
        msg = "CourtListener rate limit exceeded"
        if retry_after is not None:
            msg += f" (retry after {retry_after}s)"
        super().__init__(msg)


class AuthenticationError(CourtListenerError):
    """Raised when authentication fails (401)."""


@dataclass
class SearchResult:
    """Container for a page of search results with pagination cursors."""

    results: list[dict]
    count: int | None
    next_url: str | None
    previous_url: str | None


@dataclass
class _RateLimitState:
    """Tracks request timestamps for rate limiting."""

    timestamps: list[float] = field(default_factory=list)
    limit: int = DEFAULT_RATE_LIMIT
    window: int = DEFAULT_RATE_WINDOW

    def record(self) -> None:
        now = time.monotonic()
        self.timestamps.append(now)

    def wait_if_needed(self) -> None:
        """Block until we're under the rate limit."""
        now = time.monotonic()
        cutoff = now - self.window
        self.timestamps = [t for t in self.timestamps if t > cutoff]
        if len(self.timestamps) >= self.limit:
            oldest = self.timestamps[0]
            sleep_time = oldest + self.window - now + 0.1
            if sleep_time > 0:
                logger.info("rate_limit_preemptive_wait", sleep_seconds=round(sleep_time, 1))
                time.sleep(sleep_time)


class CourtListenerClient:
    """Authenticated REST client for the CourtListener v4 API.

    Args:
        api_token: CourtListener API token. Falls back to
            COURTLISTENER_API_TOKEN environment variable.
        timeout: HTTP request timeout in seconds.
        max_retries: Maximum retries on transient errors (500, 502, 503, 504).
        rate_limit: Maximum requests per rate window.
        rate_window: Rate limit window in seconds.
    """

    def __init__(
        self,
        api_token: str | None = None,
        *,
        timeout: float = 30.0,
        max_retries: int = MAX_RETRIES,
        rate_limit: int = DEFAULT_RATE_LIMIT,
        rate_window: int = DEFAULT_RATE_WINDOW,
    ):
        self._token = api_token or os.environ.get("COURTLISTENER_API_TOKEN", "")
        if not self._token:
            raise AuthenticationError(
                "CourtListener API token required. Set COURTLISTENER_API_TOKEN "
                "environment variable or pass api_token parameter."
            )

        self._timeout = timeout
        self._max_retries = max_retries
        self._rate_state = _RateLimitState(limit=rate_limit, window=rate_window)
        self._client = httpx.Client(
            headers={
                "Authorization": f"Token {self._token}",
                "Accept": "application/json",
            },
            timeout=timeout,
            follow_redirects=True,
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> CourtListenerClient:
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict | None = None,
        data: dict | None = None,
    ) -> httpx.Response:
        """Make an HTTP request with rate limiting and retry logic.

        Handles:
        - Pre-emptive rate limit throttling
        - 429 responses with Retry-After header
        - Retry with exponential backoff on 500/502/503/504
        - 401 authentication errors

        Returns:
            httpx.Response with successful status code.

        Raises:
            RateLimitError: If rate limit exceeded after retries.
            AuthenticationError: If 401 received.
            CourtListenerError: On other API errors.
        """
        self._rate_state.wait_if_needed()

        backoff = INITIAL_BACKOFF
        last_exception: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.request(
                    method, url, params=params, data=data
                )
                self._rate_state.record()

                if response.status_code == 200:
                    return response

                if response.status_code == 401:
                    raise AuthenticationError(
                        "CourtListener authentication failed. Check your API token."
                    )

                if response.status_code == 429:
                    retry_after = _parse_retry_after(response)
                    if attempt < self._max_retries:
                        wait = retry_after if retry_after is not None else backoff
                        logger.warning(
                            "rate_limit_429",
                            attempt=attempt + 1,
                            retry_after=wait,
                        )
                        time.sleep(wait)
                        backoff *= BACKOFF_MULTIPLIER
                        continue
                    raise RateLimitError(retry_after=retry_after)

                if response.status_code in {500, 502, 503, 504}:
                    if attempt < self._max_retries:
                        logger.warning(
                            "transient_error_retry",
                            status=response.status_code,
                            attempt=attempt + 1,
                            backoff=backoff,
                        )
                        time.sleep(backoff)
                        backoff *= BACKOFF_MULTIPLIER
                        continue
                    raise CourtListenerError(
                        f"CourtListener API error {response.status_code} "
                        f"after {self._max_retries + 1} attempts"
                    )

                raise CourtListenerError(
                    f"CourtListener API error: {response.status_code} — "
                    f"{response.text[:200]}"
                )

            except httpx.TransportError as exc:
                last_exception = exc
                if attempt < self._max_retries:
                    logger.warning(
                        "transport_error_retry",
                        error=str(exc),
                        attempt=attempt + 1,
                        backoff=backoff,
                    )
                    time.sleep(backoff)
                    backoff *= BACKOFF_MULTIPLIER
                    continue
                raise CourtListenerError(
                    f"CourtListener connection error after {self._max_retries + 1} "
                    f"attempts: {exc}"
                ) from last_exception

        # Should not reach here, but just in case
        raise CourtListenerError("Unexpected retry exhaustion")  # pragma: no cover

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search_opinions(
        self,
        query: str,
        *,
        courts: list[str] | None = None,
        filed_after: str | None = None,
        filed_before: str | None = None,
        status: str | None = None,
        order_by: str | None = None,
    ) -> SearchResult:
        """Search for opinion clusters matching a query.

        Args:
            query: Free-text search query (supports boolean operators).
            courts: Court ID codes to filter (e.g., ["cal", "calctapp"]).
            filed_after: ISO date (YYYY-MM-DD) for minimum filing date.
            filed_before: ISO date (YYYY-MM-DD) for maximum filing date.
            status: Precedential status filter (e.g., "precedential").
            order_by: Sort field (e.g., "dateFiled desc", "score desc").

        Returns:
            SearchResult with first page of results and pagination cursors.
        """
        params: dict[str, str | list[str]] = {"q": query, "type": "o"}
        if courts:
            params["court"] = courts
        if filed_after:
            params["filed_after"] = filed_after
        if filed_before:
            params["filed_before"] = filed_before
        if status:
            params["status"] = status
        if order_by:
            params["order_by"] = order_by

        response = self._request("GET", f"{API_BASE}/search/", params=params)
        data = response.json()

        return SearchResult(
            results=data.get("results", []),
            count=data.get("count"),
            next_url=data.get("next"),
            previous_url=data.get("previous"),
        )

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    def fetch_next_page(self, search_result: SearchResult) -> SearchResult | None:
        """Fetch the next page of results using the cursor URL.

        Args:
            search_result: A previous SearchResult with a next_url.

        Returns:
            Next SearchResult, or None if no more pages.
        """
        if not search_result.next_url:
            return None

        response = self._request("GET", search_result.next_url)
        data = response.json()

        return SearchResult(
            results=data.get("results", []),
            count=data.get("count"),
            next_url=data.get("next"),
            previous_url=data.get("previous"),
        )

    def paginate(
        self, initial: SearchResult, *, max_pages: int | None = None
    ):
        """Iterate through all pages of a search result.

        Args:
            initial: The first SearchResult from a search call.
            max_pages: Maximum number of pages to fetch (None = unlimited).

        Yields:
            List of result dicts for each page.
        """
        current = initial
        page = 0

        while current is not None:
            if current.results:
                yield current.results
            page += 1
            if max_pages is not None and page >= max_pages:
                break
            current = self.fetch_next_page(current)

    # ------------------------------------------------------------------
    # Opinions
    # ------------------------------------------------------------------

    def fetch_opinion(
        self, opinion_id: int, *, fields: list[str] | None = None
    ) -> dict:
        """Fetch a single opinion by ID.

        Args:
            opinion_id: The opinion ID.
            fields: Optional list of fields to return (reduces payload).
                Recommended: ["id", "html_with_citations", "type",
                "plain_text", "opinions_cited", "cluster"]

        Returns:
            Opinion data dict.
        """
        params = {}
        if fields:
            params["fields"] = ",".join(fields)

        response = self._request(
            "GET", f"{API_BASE}/opinions/{opinion_id}/", params=params
        )
        return response.json()

    # ------------------------------------------------------------------
    # Clusters (case metadata)
    # ------------------------------------------------------------------

    def fetch_cluster(
        self, cluster_id: int, *, fields: list[str] | None = None
    ) -> dict:
        """Fetch a cluster (case metadata) by ID.

        A cluster groups all opinions from a single case hearing
        (lead opinion, concurrences, dissents).

        Args:
            cluster_id: The cluster ID.
            fields: Optional list of fields to return.
                Recommended: ["id", "case_name", "case_name_full",
                "date_filed", "citations", "sub_opinions",
                "precedential_status", "docket"]

        Returns:
            Cluster data dict.
        """
        params = {}
        if fields:
            params["fields"] = ",".join(fields)

        response = self._request(
            "GET", f"{API_BASE}/clusters/{cluster_id}/", params=params
        )
        return response.json()

    # ------------------------------------------------------------------
    # Citation lookup
    # ------------------------------------------------------------------

    def lookup_citation(
        self,
        *,
        text: str | None = None,
        reporter: str | None = None,
        volume: str | None = None,
        page: str | None = None,
    ) -> list[dict]:
        """Look up and verify citations against CourtListener's database.

        Supports two modes:
        1. Text mode: parse citations from free text.
        2. Direct mode: look up a specific volume/reporter/page.

        Args:
            text: Free text containing citations to look up.
            reporter: Reporter abbreviation (e.g., "Cal.App.5th").
            volume: Volume number.
            page: Page number.

        Returns:
            List of citation lookup results. Each result contains:
            - citation: matched citation text
            - status: 200 (found), 300 (ambiguous), 404 (not found)
            - clusters: list of matching case clusters

        Raises:
            ValueError: If neither text nor reporter/volume/page provided.
        """
        if text:
            form_data = {"text": text}
        elif reporter and volume and page:
            form_data = {"reporter": reporter, "volume": volume, "page": page}
        else:
            raise ValueError(
                "Provide either 'text' or all of 'reporter', 'volume', 'page'"
            )

        response = self._request(
            "POST", f"{API_BASE}/citation-lookup/", data=form_data
        )
        return response.json()

    # ------------------------------------------------------------------
    # Citation graph
    # ------------------------------------------------------------------

    def fetch_citing_opinions(
        self, opinion_id: int
    ) -> SearchResult:
        """Find opinions that cite a given opinion.

        Args:
            opinion_id: The opinion ID to find citations for.

        Returns:
            SearchResult of citing opinion links.
        """
        response = self._request(
            "GET",
            f"{API_BASE}/opinions-cited/",
            params={"cited_opinion": str(opinion_id)},
        )
        data = response.json()
        return SearchResult(
            results=data.get("results", []),
            count=data.get("count"),
            next_url=data.get("next"),
            previous_url=data.get("previous"),
        )


def _parse_retry_after(response: httpx.Response) -> float | None:
    """Extract Retry-After value from response headers."""
    value = response.headers.get("Retry-After") or response.headers.get("retry-after")
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
