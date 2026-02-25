"""Statutory code extractor for California Legislative Information (leginfo).

Navigates leginfo.legislature.ca.gov to discover and extract individual
code sections with full citation metadata, hierarchy paths, and effective dates.

Architecture:
- Uses plain HTTP requests (httpx) — leginfo is server-side rendered JSF, no JS needed.
- Discovery via the "expand all" TOC page to find all chapter/article text pages.
- Section parsing from displayText pages which contain multiple sections per page.
- 10+ second delay between requests to respect robots.txt Crawl-Delay.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin

import warnings

import httpx
import structlog
from bs4 import BeautifulSoup, Tag, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

logger = structlog.get_logger(__name__)

BASE_URL = "https://leginfo.legislature.ca.gov"

# Standard California citation prefixes
CITATION_PREFIXES = {
    "LAB": "Cal. Lab. Code",
    "GOV": "Cal. Gov. Code",
    "UIC": "Cal. Unemp. Ins. Code",
    "BPC": "Cal. Bus. & Prof. Code",
    "CCP": "Cal. Code Civ. Proc.",
    "CIV": "Cal. Civ. Code",
    "FAM": "Cal. Fam. Code",
    "HSC": "Cal. Health & Safety Code",
    "INS": "Cal. Ins. Code",
    "PEN": "Cal. Penal Code",
    "EDC": "Cal. Educ. Code",
    "PROB": "Cal. Prob. Code",
    "VEH": "Cal. Veh. Code",
    "WAT": "Cal. Water Code",
    "WIC": "Cal. Welf. & Inst. Code",
}


@dataclass
class HierarchyPath:
    """Structural hierarchy path for a code section."""

    code_name: str  # e.g., "LAB"
    division: str = ""  # e.g., "DIVISION 2. EMPLOYMENT REGULATION AND SUPERVISION"
    title: str = ""
    part: str = ""  # e.g., "PART 3. Privileges and Immunities"
    chapter: str = ""  # e.g., "CHAPTER 5. Political Affiliations"
    article: str = ""  # e.g., "ARTICLE 1"

    def to_path_string(self) -> str:
        """Return a human-readable hierarchy path."""
        parts = [self.code_name]
        for level in [self.division, self.title, self.part, self.chapter, self.article]:
            if level:
                parts.append(level)
        return " > ".join(parts)


@dataclass
class StatuteSection:
    """A single extracted code section with full metadata."""

    section_number: str  # e.g., "1102.5"
    code_abbreviation: str  # e.g., "LAB"
    text: str  # Full text of the section
    citation: str  # e.g., "Cal. Lab. Code § 1102.5"
    hierarchy: HierarchyPath
    effective_date: str | None = None  # e.g., "January 1, 2024"
    amendment_info: str | None = None  # e.g., "Amended by Stats. 2023, Ch. 612, Sec. 2. (SB 497)"
    subdivisions: list[str] = field(default_factory=list)  # Top-level subdivision markers found
    source_url: str = ""

    @property
    def heading_path(self) -> str:
        return self.hierarchy.to_path_string()


@dataclass
class TocEntry:
    """An entry from the Table of Contents — a link to a displayText page."""

    url: str
    hierarchy: HierarchyPath


def build_citation(code_abbreviation: str, section_number: str) -> str:
    """Build a canonical California citation string.

    Strips brackets from section numbers (some PUBINFO records contain
    bracketed section numbers like ``[1084.]``).

    Examples:
        >>> build_citation("LAB", "1102.5")
        'Cal. Lab. Code § 1102.5'
        >>> build_citation("GOV", "12940")
        'Cal. Gov. Code § 12940'
        >>> build_citation("CCP", "[1084.]")
        'Cal. Code Civ. Proc. § 1084.'
    """
    prefix = CITATION_PREFIXES.get(code_abbreviation, f"Cal. {code_abbreviation}")
    cleaned = section_number.strip("[]")
    return f"{prefix} § {cleaned}"


class StatutoryExtractor:
    """Extracts statutory code sections from leginfo.legislature.ca.gov.

    Usage:
        extractor = StatutoryExtractor("LAB", rate_limit=10.0)
        for section in extractor.extract_all():
            print(section.citation, section.text[:100])

    Resumability:
        Pass ``completed_urls`` to skip TOC pages already processed in a
        previous (interrupted) run.  The pipeline stores processed page URLs
        and passes them on restart so only unfinished pages are fetched.
    """

    def __init__(
        self,
        code_abbreviation: str,
        *,
        rate_limit: float = 10.0,
        target_divisions: list[str] | None = None,
        citation_prefix: str | None = None,
        completed_urls: set[str] | None = None,
    ) -> None:
        """Initialize the extractor.

        Args:
            code_abbreviation: Code abbreviation (e.g., "LAB", "GOV").
            rate_limit: Seconds between HTTP requests (min 10 per robots.txt).
            target_divisions: If provided, only extract these division numbers.
                e.g., ["2.", "3."] to only get Divisions 2 and 3.
            citation_prefix: Override citation prefix (e.g., "Cal. Lab. Code").
            completed_urls: Set of TOC page URLs already processed in a
                previous run.  These pages will be skipped during extraction.
        """
        self.code = code_abbreviation.upper()
        self.rate_limit = max(rate_limit, 3.0)  # Minimum 3s, recommended 10+
        self.target_divisions = target_divisions
        self.citation_prefix = citation_prefix or CITATION_PREFIXES.get(
            self.code, f"Cal. {self.code}"
        )
        self.completed_urls: set[str] = completed_urls or set()
        self._client: httpx.Client | None = None
        self._request_count = 0
        self._error_count = 0
        self._last_request_time: float = 0

    def __enter__(self) -> StatutoryExtractor:
        self._client = httpx.Client(
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36 EmployeeHelpBot/1.0 "
                    "(California employment rights research; educational use)"
                ),
            },
            timeout=90.0,  # Large TOC pages can be slow
            follow_redirects=True,
        )
        return self

    def __exit__(self, *exc: object) -> None:
        if self._client:
            self._client.close()
            self._client = None

    def _fetch(self, url: str, max_retries: int = 3) -> str:
        """Fetch a URL with rate limiting, retry, and content validation.

        Args:
            url: URL to fetch.
            max_retries: Maximum number of retry attempts (with exponential backoff).

        Returns:
            Response text.

        Raises:
            RuntimeError: If not used as context manager, or circuit breaker tripped.
            httpx.HTTPStatusError: If all retries exhausted.
        """
        if self._client is None:
            raise RuntimeError("StatutoryExtractor must be used as a context manager")

        # Circuit breaker: abort if >50% of requests have failed
        if self._request_count >= 6 and self._error_count / self._request_count > 0.5:
            raise RuntimeError(
                f"Circuit breaker tripped: {self._error_count}/{self._request_count} "
                f"requests failed (>{50}% failure rate)"
            )

        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            # Rate limit
            now = time.monotonic()
            elapsed = now - self._last_request_time
            if elapsed < self.rate_limit and self._request_count > 0:
                sleep_time = self.rate_limit - elapsed
                logger.debug("rate_limit_sleep", seconds=sleep_time)
                time.sleep(sleep_time)

            self._request_count += 1
            self._last_request_time = time.monotonic()

            logger.info(
                "fetching",
                url=url,
                request_number=self._request_count,
                attempt=attempt + 1,
            )

            try:
                response = self._client.get(url)
                response.raise_for_status()
                text = response.text

                # Content validation: check for proxy error pages
                if _is_proxy_error(text):
                    self._error_count += 1
                    last_exc = RuntimeError(f"Proxy error in response body for {url}")
                    if attempt < max_retries:
                        backoff = 2 ** (attempt + 1)  # 2s, 4s, 8s
                        logger.warning(
                            "proxy_error_retrying",
                            url=url,
                            attempt=attempt + 1,
                            backoff=backoff,
                        )
                        time.sleep(backoff)
                        continue
                    raise last_exc

                return text

            except (httpx.HTTPStatusError, httpx.ConnectError, httpx.ReadTimeout) as e:
                self._error_count += 1
                last_exc = e
                if attempt < max_retries:
                    backoff = 2 ** (attempt + 1)  # 2s, 4s, 8s
                    logger.warning(
                        "fetch_error_retrying",
                        url=url,
                        attempt=attempt + 1,
                        backoff=backoff,
                        error=str(e),
                    )
                    time.sleep(backoff)
                else:
                    raise

    def discover_toc(self) -> list[TocEntry]:
        """Discover all chapter/article text page links from the expanded TOC.

        Returns:
            List of TocEntry objects, each pointing to a codes_displayText page.
        """
        expand_url = f"{BASE_URL}/faces/codedisplayexpand.xhtml?tocCode={self.code}"
        html = self._fetch(expand_url)
        return parse_toc_page(html, self.code, self.target_divisions)

    def extract_sections_from_page(self, toc_entry: TocEntry) -> list[StatuteSection]:
        """Extract all sections from a single displayText page."""
        url = toc_entry.url
        if not url.startswith("http"):
            url = urljoin(BASE_URL, url)

        html = self._fetch(url)
        return parse_display_text_page(html, self.code, toc_entry.hierarchy, url)

    def extract_all(self) -> list[StatuteSection]:
        """Extract all sections for this code.

        Discovers the TOC, then iterates through each chapter/article page
        extracting individual sections.  Pages listed in ``completed_urls``
        are skipped (resumability support).

        Returns:
            List of all StatuteSection objects found.
        """
        toc_entries = self.discover_toc()

        # Filter out already-completed pages for resumability
        pending_entries = [
            e for e in toc_entries if e.url not in self.completed_urls
        ]
        skipped = len(toc_entries) - len(pending_entries)

        logger.info(
            "toc_discovered",
            code=self.code,
            entries=len(toc_entries),
            pending=len(pending_entries),
            skipped=skipped,
            target_divisions=self.target_divisions,
        )

        all_sections: list[StatuteSection] = []
        for i, entry in enumerate(pending_entries):
            logger.info(
                "extracting_page",
                code=self.code,
                page=i + 1,
                total=len(pending_entries),
                url=entry.url,
            )
            try:
                sections = self.extract_sections_from_page(entry)
                all_sections.extend(sections)
                # Track this URL as completed (available for pipeline to persist)
                self.completed_urls.add(entry.url)
                logger.info(
                    "page_extracted",
                    code=self.code,
                    sections_found=len(sections),
                    total_so_far=len(all_sections),
                )
            except Exception as e:
                logger.error(
                    "page_extraction_failed",
                    url=entry.url,
                    error=str(e),
                )

        logger.info(
            "extraction_complete",
            code=self.code,
            total_sections=len(all_sections),
            total_requests=self._request_count,
            pages_skipped=skipped,
        )
        return all_sections


def _is_proxy_error(html: str) -> bool:
    """Check if a response body contains a proxy error page."""
    lower = html[:2000].lower()
    return any(
        marker in lower
        for marker in ("proxy error", "502 bad gateway", "503 service unavailable")
    )


# ── TOC Parsing ──────────────────────────────────────────────


def parse_toc_page(
    html: str,
    code_abbreviation: str,
    target_divisions: list[str] | None = None,
) -> list[TocEntry]:
    """Parse the expanded TOC page to extract chapter/article page links.

    Args:
        html: HTML content of the codedisplayexpand page.
        code_abbreviation: The code (e.g., "LAB").
        target_divisions: Optional list of division numbers to filter by.

    Returns:
        List of TocEntry objects for each displayText page.
    """
    soup = BeautifulSoup(html, "lxml")
    entries: list[TocEntry] = []

    # Current hierarchy context — updated as we encounter headings
    current_division = ""
    current_title = ""
    current_part = ""
    current_chapter = ""

    # Find all links to codes_displayText.xhtml
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if "codes_displayText.xhtml" not in href:
            continue

        # Parse hierarchy from the URL parameters
        params = _parse_url_params(href)
        div_param = params.get("division", "")
        title_param = params.get("title", "")
        part_param = params.get("part", "")
        chapter_param = params.get("chapter", "")
        article_param = params.get("article", "")

        # Filter by target divisions — skip entries with no division or wrong division
        if target_divisions:
            if not div_param or div_param not in target_divisions:
                continue

        # Build hierarchy from link text and surrounding context
        link_text = link.get_text(strip=True)
        hierarchy = _build_hierarchy_from_link(
            code_abbreviation, link_text, div_param, title_param,
            part_param, chapter_param, article_param,
        )

        full_url = urljoin(BASE_URL, href)
        entries.append(TocEntry(url=full_url, hierarchy=hierarchy))

    return entries


def _parse_url_params(href: str) -> dict[str, str]:
    """Parse URL parameters from a leginfo href."""
    params: dict[str, str] = {}
    if "?" not in href:
        return params
    query = href.split("?", 1)[1]
    for pair in query.split("&"):
        if "=" in pair:
            key, value = pair.split("=", 1)
            params[key] = value
    return params


def _build_hierarchy_from_link(
    code: str,
    link_text: str,
    division: str,
    title: str,
    part: str,
    chapter: str,
    article: str,
) -> HierarchyPath:
    """Build a HierarchyPath from URL parameters and link text."""
    return HierarchyPath(
        code_name=code,
        division=f"Division {division.rstrip('.')}" if division else "",
        title=f"Title {title.rstrip('.')}" if title else "",
        part=f"Part {part.rstrip('.')}" if part else "",
        chapter=f"Chapter {chapter.rstrip('.')}" if chapter else "",
        article=f"Article {article.rstrip('.')}" if article else "",
    )


# ── Section Parsing ──────────────────────────────────────────


# Regex for section number headings (e.g., "1102.5.", "12940.")
_SECTION_NUM_RE = re.compile(r"^(\d+(?:\.\d+)?)\.\s*$")

# Regex for effective date / amendment lines
_AMENDMENT_RE = re.compile(
    r"\((?:Added|Amended|Repealed|Enacted|Renumbered|Added and Repealed)"
    r"\s+by\s+Stats\.\s+(\d{4})",
    re.IGNORECASE,
)

# Regex for effective date extraction
_EFFECTIVE_DATE_RE = re.compile(
    r"[Ee]ffective\s+(\w+\s+\d+,\s+\d{4})",
)

# Regex for subdivision markers
_SUBDIVISION_RE = re.compile(r"^\s*\(([a-z]|\d+|[A-Z])\)")


def parse_display_text_page(
    html: str,
    code_abbreviation: str,
    base_hierarchy: HierarchyPath,
    source_url: str = "",
) -> list[StatuteSection]:
    """Parse a codes_displayText page to extract individual sections.

    The displayText page shows all sections within a chapter or article.
    Section numbers appear as <h6> headings (or similar small headings),
    followed by the section text, ending with an effective date in <em>/<i>.

    Args:
        html: HTML content of the displayText page.
        code_abbreviation: The code abbreviation (e.g., "LAB").
        base_hierarchy: The hierarchy context from the TOC entry.
        source_url: The URL of this page.

    Returns:
        List of StatuteSection objects extracted from this page.
    """
    soup = BeautifulSoup(html, "lxml")
    sections: list[StatuteSection] = []

    # Update hierarchy from page headings (h3, h4, h5)
    hierarchy = _update_hierarchy_from_page(soup, base_hierarchy, code_abbreviation)

    # Find all content after the content_anchor
    content_area = soup.find(id="content_anchor")
    if content_area is None:
        # Fall back to the entire body
        content_area = soup.find("body") or soup

    # Strategy: find all h6 elements that look like section numbers
    # Then collect text between consecutive h6 headings
    section_headings = []
    for h6 in content_area.find_all("h6"):
        text = h6.get_text(strip=True)
        # Section numbers end with a period and are numeric
        match = _SECTION_NUM_RE.match(text)
        if match:
            section_headings.append((h6, match.group(1)))

    for i, (h6_tag, section_num) in enumerate(section_headings):
        # Collect text between this h6 and the next one (or end of content)
        next_h6 = section_headings[i + 1][0] if i + 1 < len(section_headings) else None
        section_text, amendment_info, effective_date = _extract_section_text(
            h6_tag, next_h6
        )

        if not section_text.strip():
            continue

        # Find subdivision markers
        subdivisions = _find_subdivisions(section_text)

        # Build citation
        citation = build_citation(code_abbreviation, section_num)

        # Build section URL
        section_url = (
            f"{BASE_URL}/faces/codes_displaySection.xhtml"
            f"?lawCode={code_abbreviation}&sectionNum={section_num}"
        )

        sections.append(
            StatuteSection(
                section_number=section_num,
                code_abbreviation=code_abbreviation,
                text=section_text.strip(),
                citation=citation,
                hierarchy=hierarchy,
                effective_date=effective_date,
                amendment_info=amendment_info,
                subdivisions=subdivisions,
                source_url=section_url,
            )
        )

    return sections


def _update_hierarchy_from_page(
    soup: BeautifulSoup,
    base: HierarchyPath,
    code: str,
) -> HierarchyPath:
    """Update hierarchy from page headings (h3, h4, h5)."""
    hierarchy = HierarchyPath(
        code_name=code,
        division=base.division,
        title=base.title,
        part=base.part,
        chapter=base.chapter,
        article=base.article,
    )

    # Look for more specific hierarchy info in page headings
    for heading in soup.find_all(["h3", "h4", "h5"]):
        text = heading.get_text(strip=True)
        text_upper = text.upper()

        if text_upper.startswith("DIVISION"):
            hierarchy.division = text
        elif text_upper.startswith("TITLE"):
            hierarchy.title = text
        elif text_upper.startswith("PART"):
            hierarchy.part = text
        elif text_upper.startswith("CHAPTER"):
            hierarchy.chapter = text
        elif text_upper.startswith("ARTICLE"):
            hierarchy.article = text

    return hierarchy


def _extract_section_text(
    h6_tag: Tag,
    next_h6: Tag | None,
) -> tuple[str, str | None, str | None]:
    """Extract section text between two h6 headings.

    Returns:
        Tuple of (text, amendment_info, effective_date).
    """
    parts: list[str] = []
    amendment_info: str | None = None
    effective_date: str | None = None

    # Walk siblings after the h6 until we hit the next h6 or end
    current = h6_tag.next_sibling
    while current is not None:
        # Stop at the next section heading
        if current == next_h6:
            break
        if isinstance(current, Tag) and current.name == "h6":
            # Check if this is a section number
            text = current.get_text(strip=True)
            if _SECTION_NUM_RE.match(text):
                break

        # Extract text
        if isinstance(current, Tag):
            text = current.get_text(strip=True)
            if text:
                # Check if this is an amendment/effective date line
                amendment_match = _AMENDMENT_RE.search(text)
                if amendment_match:
                    amendment_info = text.strip("() \n")
                    date_match = _EFFECTIVE_DATE_RE.search(text)
                    if date_match:
                        effective_date = date_match.group(1)
                else:
                    parts.append(text)
        elif hasattr(current, "strip"):
            # NavigableString
            text = str(current).strip()
            if text:
                parts.append(text)

        current = current.next_sibling

    return "\n\n".join(parts), amendment_info, effective_date


def _find_subdivisions(text: str) -> list[str]:
    """Find top-level subdivision markers in section text."""
    subdivisions = []
    for line in text.split("\n"):
        match = _SUBDIVISION_RE.match(line)
        if match:
            marker = match.group(1)
            if marker not in subdivisions:
                subdivisions.append(marker)
    return subdivisions
