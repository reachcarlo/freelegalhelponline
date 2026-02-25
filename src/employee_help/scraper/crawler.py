"""Web crawler for the California Civil Rights Department website.

Discovers and fetches employment-related pages and PDF documents
using Playwright for headless browser rendering.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urljoin, urlparse, urlunparse

import structlog
from playwright.sync_api import Browser, BrowserContext, Playwright, sync_playwright

from employee_help.config import CrawlConfig
from employee_help.storage.models import ContentType

logger = structlog.get_logger()


class UrlClassification(str, Enum):
    IN_SCOPE = "in_scope"
    PDF_DOWNLOAD = "pdf_download"
    OUT_OF_SCOPE = "out_of_scope"


@dataclass
class CrawlResult:
    """Result of crawling a single URL."""
    url: str
    html: str | None = None
    pdf_bytes: bytes | None = None
    classification: UrlClassification = UrlClassification.IN_SCOPE
    status_code: int | None = None
    last_modified: str | None = None
    error: str | None = None


def classify_url(
    url: str,
    allowlist_patterns: list[str],
    blocklist_patterns: list[str],
) -> UrlClassification:
    """Classify a URL as in-scope, PDF download, or out-of-scope.

    Args:
        url: The URL to classify.
        allowlist_patterns: Regex patterns — URL must match at least one.
        blocklist_patterns: Regex patterns — URL is excluded if it matches any.

    Returns:
        UrlClassification enum value.
    """
    # Normalize the URL first
    url = normalize_url(url)

    # Check blocklist first (takes priority)
    for pattern in blocklist_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            return UrlClassification.OUT_OF_SCOPE

    # PDF detection
    parsed = urlparse(url)
    if parsed.path.lower().endswith(".pdf"):
        # PDFs still need to match allowlist
        for pattern in allowlist_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return UrlClassification.PDF_DOWNLOAD
        return UrlClassification.OUT_OF_SCOPE

    # Check allowlist
    for pattern in allowlist_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            return UrlClassification.IN_SCOPE

    return UrlClassification.OUT_OF_SCOPE


def normalize_url(url: str) -> str:
    """Normalize a URL by removing fragments, trailing slashes inconsistencies, etc."""
    parsed = urlparse(url)

    # Remove fragment
    normalized = urlunparse((
        parsed.scheme,
        parsed.netloc.lower(),
        parsed.path,
        parsed.params,
        parsed.query,
        "",  # no fragment
    ))

    # Don't strip trailing slash — keep URL as-is for path comparison
    return normalized


def discover_links(page_html: str, base_url: str) -> list[str]:
    """Extract all unique links from rendered page HTML.

    Args:
        page_html: The rendered page HTML.
        base_url: The base URL for resolving relative links.

    Returns:
        List of unique, absolute URLs found on the page.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(page_html, "lxml")
    seen: set[str] = set()
    links: list[str] = []

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()

        # Skip javascript:, mailto:, tel:, etc.
        if re.match(r"^(javascript|mailto|tel|data):", href, re.IGNORECASE):
            continue

        # Resolve relative URLs
        absolute = urljoin(base_url, href)
        normalized = normalize_url(absolute)

        # Only include http(s) URLs
        if not normalized.startswith(("http://", "https://")):
            continue

        if normalized not in seen:
            seen.add(normalized)
            links.append(normalized)

    return links


class Crawler:
    """Crawls CRD website pages and downloads PDFs using Playwright."""

    def __init__(self, config: CrawlConfig) -> None:
        self._config = config
        self._visited: set[str] = set()
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    def start(self) -> None:
        """Launch the browser."""
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)
        self._context = self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36 EmployeeHelpBot/1.0"
            )
        )

    def stop(self) -> None:
        """Close the browser and cleanup."""
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def close(self) -> None:
        """Alias for stop() for consistency with pipeline interface."""
        self.stop()

    def __enter__(self) -> Crawler:
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()

    def crawl(self) -> list[CrawlResult]:
        """Execute the full crawl starting from seed URLs.

        Returns:
            List of CrawlResult for all discovered in-scope URLs.
        """
        results: list[CrawlResult] = []
        for result in self._crawl_impl():
            results.append(result)
        return results

    def _crawl_impl(self):
        """Generator that yields CrawlResult for each discovered URL.

        Yields:
            CrawlResult for each processed URL.
        """
        queue: list[str] = list(self._config.seed_urls)
        results_count = 0

        while queue and results_count < self._config.max_pages:
            url = queue.pop(0)
            normalized = normalize_url(url)

            if normalized in self._visited:
                continue
            self._visited.add(normalized)

            classification = classify_url(
                normalized,
                self._config.allowlist_patterns,
                self._config.blocklist_patterns,
            )

            if classification == UrlClassification.OUT_OF_SCOPE:
                logger.debug("url_skipped", url=normalized, reason="out_of_scope")
                continue

            # Rate limit
            if results_count > 0:
                time.sleep(self._config.rate_limit_seconds)

            if classification == UrlClassification.PDF_DOWNLOAD:
                result = self._fetch_pdf(normalized)
            else:
                result = self._fetch_html(normalized)
                # Discover new links from this page
                if result.html and not result.error:
                    new_links = discover_links(result.html, normalized)
                    for link in new_links:
                        norm_link = normalize_url(link)
                        if norm_link not in self._visited:
                            queue.append(norm_link)

            results_count += 1
            logger.info(
                "url_fetched",
                url=normalized,
                classification=classification.value,
                status=result.status_code,
                error=result.error,
            )
            yield result

    def _fetch_html(self, url: str) -> CrawlResult:
        """Fetch and render an HTML page using Playwright."""
        try:
            page = self._context.new_page()
            response = page.goto(url, wait_until="networkidle", timeout=30000)

            status_code = response.status if response else None
            last_modified = None
            if response:
                headers = response.all_headers()
                last_modified = headers.get("last-modified")

            # Get the full rendered HTML
            html = page.content()
            page.close()

            return CrawlResult(
                url=url,
                html=html,
                classification=UrlClassification.IN_SCOPE,
                status_code=status_code,
                last_modified=last_modified,
            )
        except Exception as e:
            logger.error("fetch_html_error", url=url, error=str(e))
            return CrawlResult(
                url=url,
                classification=UrlClassification.IN_SCOPE,
                error=str(e),
            )

    def _fetch_pdf(self, url: str) -> CrawlResult:
        """Download a PDF document using Playwright's API request context."""
        try:
            response = self._context.request.get(url)

            if response.status != 200:
                return CrawlResult(
                    url=url,
                    classification=UrlClassification.PDF_DOWNLOAD,
                    status_code=response.status,
                    error=f"HTTP {response.status}",
                )

            pdf_bytes = response.body()
            last_modified = response.headers.get("last-modified")

            return CrawlResult(
                url=url,
                pdf_bytes=pdf_bytes,
                classification=UrlClassification.PDF_DOWNLOAD,
                status_code=response.status,
                last_modified=last_modified,
            )
        except Exception as e:
            logger.error("fetch_pdf_error", url=url, error=str(e))
            return CrawlResult(
                url=url,
                classification=UrlClassification.PDF_DOWNLOAD,
                error=str(e),
            )

    def extract_html(self, url: str) -> str:
        """Extract Markdown content from an HTML page.

        Args:
            url: The URL to extract content from.

        Returns:
            Extracted Markdown content, or empty string on error.
        """
        from employee_help.scraper.extractors.html import extract_html

        result = self._fetch_html(url)
        if result.error or not result.html:
            return ""
        return extract_html(result.html, url) or ""

    def extract_pdf(self, url: str) -> str:
        """Extract Markdown content from a PDF document.

        Args:
            url: The URL of the PDF to extract.

        Returns:
            Extracted Markdown content, or empty string on error.
        """
        from employee_help.scraper.extractors.pdf import extract_pdf

        result = self._fetch_pdf(url)
        if result.error or not result.pdf_bytes:
            return ""
        return extract_pdf(result.pdf_bytes, url) or ""
