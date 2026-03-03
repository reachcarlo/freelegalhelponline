"""CCR Title 8 (Industrial Relations) loader.

Discovers and downloads California Code of Regulations Title 8 sections
from Cornell LII (law.cornell.edu). These are workplace safety, wage/hour,
and employment regulations that supplement statutory codes.

Architecture:
- Two-phase process: crawl TOC hierarchy to discover section URLs →
  download and parse individual section pages → convert to StatuteSection
- Uses httpx for HTTP requests, BeautifulSoup for HTML parsing
- Local HTML file cache avoids redundant network requests
- Converts each section to a StatuteSection for pipeline compatibility
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import structlog
from bs4 import BeautifulSoup

from employee_help.scraper.extractors.statute import HierarchyPath, StatuteSection

logger = structlog.get_logger(__name__)

# Ensure _heading_path_override support is patched onto StatuteSection.
# Other loaders (DLSE, CACI) apply the same patch; this is idempotent.
if not hasattr(StatuteSection.heading_path.fget, "_patched"):

    @property  # type: ignore[misc]
    def _patched_heading_path(self: StatuteSection) -> str:
        override = getattr(self, "_heading_path_override", None)
        if override:
            return override
        return self.hierarchy.to_path_string()

    _patched_heading_path.fget._patched = True  # type: ignore[attr-defined]
    StatuteSection.heading_path = _patched_heading_path  # type: ignore[assignment]


BASE_URL = "https://www.law.cornell.edu"
TITLE_URL = f"{BASE_URL}/regulations/california/title-8"

# Matches individual section URLs like /regulations/california/8-CCR-3207
SECTION_URL_RE = re.compile(r"/regulations/california/8-CCR-(\d+(?:\.\d+)?(?:\.\d+)?)$")

# Matches TOC child links (divisions, chapters, subchapters, groups, articles)
TOC_CHILD_RE = re.compile(
    r"/regulations/california/title-8/"
    r"(?:division-[\w.]+)"
    r"(?:/chapter-[\w.]+)?"
    r"(?:/subchapter-[\w.]+)?"
    r"(?:/group-[\w.]+)?"
    r"(?:/article-[\w.]+)?$"
)

# Detect figure/table links to skip
FIGURE_TABLE_RE = re.compile(r"(?:figure|table|appendix|plate)\b", re.IGNORECASE)

# Detect [Repealed] in link text
REPEALED_RE = re.compile(r"\[Repealed\]", re.IGNORECASE)

# Detect [Reserved] in link text
RESERVED_RE = re.compile(r"\[Reserved\]", re.IGNORECASE)

# Maximum recursion depth for TOC crawling
MAX_TOC_DEPTH = 8

# Extract section number from page title like "Cal. Code Regs. Tit. 8, § 3207 - Definitions"
TITLE_SECTION_RE = re.compile(r"§\s*(\d+(?:\.\d+)*)")

# Extract authority/reference from note text
AUTHORITY_RE = re.compile(r"Authority\s+cited?:\s*(.+)", re.IGNORECASE)
REFERENCE_RE = re.compile(r"Reference:\s*(.+)", re.IGNORECASE)


@dataclass
class SectionMeta:
    """Metadata for a single CCR Title 8 section discovered from the TOC."""

    section_number: str  # e.g., "3207"
    title: str  # e.g., "Definitions"
    url: str  # Full URL to section page
    hierarchy_path: list[str]  # e.g., ["Division 1", "Chapter 4", ...]
    is_repealed: bool = False


class CCRTitle8TOCCrawler:
    """Phase 1: Recursive TOC discovery of CCR Title 8 sections from Cornell LII."""

    def __init__(
        self,
        cache_dir: Path = Path("data/ccr_title8/toc"),
        rate_limit: float = 2.0,
        timeout: float = 30.0,
    ) -> None:
        self.cache_dir = cache_dir
        self.rate_limit = rate_limit
        self.timeout = timeout
        self.logger = structlog.get_logger(__name__)

    def _fetch_page(self, url: str, client: httpx.Client) -> str:
        """Fetch a page with local HTML file cache."""
        # Build cache filename from URL path
        path_part = url.replace(BASE_URL, "").strip("/").replace("/", "_")
        cache_file = self.cache_dir / f"{path_part}.html"

        if cache_file.exists():
            self.logger.debug("toc_cache_hit", url=url)
            return cache_file.read_text(encoding="utf-8")

        resp = client.get(url)
        resp.raise_for_status()
        html = resp.text

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(html, encoding="utf-8")
        self.logger.debug("toc_page_fetched", url=url)

        if self.rate_limit > 0:
            time.sleep(self.rate_limit)

        return html

    def _extract_links(self, html: str) -> list[tuple[str, str]]:
        """Extract (href, link_text) pairs from a TOC page."""
        soup = BeautifulSoup(html, "lxml")
        links: list[tuple[str, str]] = []

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            text = a_tag.get_text(strip=True)

            # Make absolute
            if href.startswith("/"):
                href = BASE_URL + href

            links.append((href, text))

        return links

    def _crawl_toc_recursive(
        self,
        url: str,
        client: httpx.Client,
        hierarchy: list[str],
        depth: int = 0,
    ) -> list[SectionMeta]:
        """Recursively crawl TOC pages, collecting section links.

        Follows child TOC links (division→chapter→subchapter→group→article)
        and collects individual section links matching the 8-CCR-{number} pattern.
        """
        if depth > MAX_TOC_DEPTH:
            self.logger.warning("toc_max_depth_reached", url=url, depth=depth)
            return []

        try:
            html = self._fetch_page(url, client)
        except httpx.HTTPError as e:
            self.logger.warning("toc_fetch_failed", url=url, error=str(e))
            return []

        links = self._extract_links(html)
        sections: list[SectionMeta] = []
        child_toc_urls: list[tuple[str, str]] = []

        for href, text in links:
            # Skip figures/tables/appendices
            if FIGURE_TABLE_RE.search(text):
                continue

            # Check for individual section links
            section_match = SECTION_URL_RE.search(href)
            if section_match:
                section_number = section_match.group(1)
                # Parse title from link text like "§ 3207 - Definitions"
                title = text
                if " - " in title:
                    title = title.split(" - ", 1)[1].strip()
                elif "§" in title:
                    # Just the section number, no title
                    title = ""

                is_repealed = bool(REPEALED_RE.search(text))
                is_reserved = bool(RESERVED_RE.search(text))

                # Skip reserved sections (they have no content)
                if is_reserved:
                    continue

                sections.append(
                    SectionMeta(
                        section_number=section_number,
                        title=title,
                        url=href,
                        hierarchy_path=list(hierarchy),
                        is_repealed=is_repealed,
                    )
                )
                continue

            # Check for child TOC links
            if TOC_CHILD_RE.search(href):
                # Only follow if it's a deeper level than current URL
                # Skip [Repealed] groups/subchapters (no content to crawl)
                if href != url and len(href) > len(url) and not REPEALED_RE.search(text):
                    child_toc_urls.append((href, text))

        # Recurse into child TOC pages
        for child_url, child_text in child_toc_urls:
            # Extract hierarchy label from link text (e.g., "Chapter 4 - Division of Industrial Safety")
            label = child_text.strip()
            # Remove article/section range info in parentheses
            label = re.sub(r"\s*\(.*?\)\s*$", "", label).strip()

            child_hierarchy = hierarchy + [label]
            child_sections = self._crawl_toc_recursive(
                child_url, client, child_hierarchy, depth + 1
            )
            sections.extend(child_sections)

        return sections

    def discover(
        self,
        target_divisions: list[str] | None = None,
        client: httpx.Client | None = None,
    ) -> list[SectionMeta]:
        """Discover all CCR Title 8 sections for the given divisions.

        Args:
            target_divisions: Division numbers to crawl (e.g., ["1"]).
                              None or empty means all divisions.
            client: Optional httpx client to use.

        Returns:
            Deduplicated list of SectionMeta objects.
        """
        own_client = client is None
        if own_client:
            client = httpx.Client(
                timeout=self.timeout,
                follow_redirects=True,
                headers={"User-Agent": "EmployeeHelp/1.0 (legal research tool)"},
            )

        try:
            # Fetch the title-level TOC to find division links
            html = self._fetch_page(TITLE_URL, client)
            links = self._extract_links(html)

            # Find division URLs
            division_urls: list[tuple[str, str]] = []
            for href, text in links:
                if "/title-8/division-" in href and TOC_CHILD_RE.search(href):
                    # Extract division number
                    div_match = re.search(r"/division-(\d+)", href)
                    if div_match:
                        div_num = div_match.group(1)
                        if target_divisions and div_num not in target_divisions:
                            continue
                        division_urls.append((href, text))

            self.logger.info(
                "divisions_found",
                total=len(division_urls),
                target=target_divisions,
            )

            all_sections: list[SectionMeta] = []
            for div_url, div_text in division_urls:
                label = re.sub(r"\s*\(.*?\)\s*$", "", div_text).strip()
                sections = self._crawl_toc_recursive(
                    div_url, client, [label], depth=1
                )
                all_sections.extend(sections)
                self.logger.info(
                    "division_crawled",
                    division=label,
                    sections=len(sections),
                )

            # Deduplicate by section number
            seen: dict[str, SectionMeta] = {}
            for section in all_sections:
                if section.section_number not in seen:
                    seen[section.section_number] = section

            result = list(seen.values())
            self.logger.info(
                "toc_discovery_complete",
                total_raw=len(all_sections),
                deduplicated=len(result),
            )
            return result

        finally:
            if own_client:
                client.close()


class CCRTitle8Loader:
    """Phase 2: Download, parse, and convert CCR Title 8 sections to StatuteSections."""

    def __init__(
        self,
        cache_dir: Path = Path("data/ccr_title8"),
        rate_limit: float = 2.0,
        timeout: float = 30.0,
        target_divisions: list[str] | None = None,
    ) -> None:
        self.cache_dir = cache_dir
        self.sections_cache = cache_dir / "sections"
        self.rate_limit = rate_limit
        self.timeout = timeout
        self.target_divisions = target_divisions
        self.logger = structlog.get_logger(__name__)

    def _fetch_section(self, url: str, client: httpx.Client) -> str:
        """Fetch a section page with local HTML cache."""
        # Build cache filename from section number in URL
        section_match = SECTION_URL_RE.search(url)
        if section_match:
            cache_file = self.sections_cache / f"8-CCR-{section_match.group(1)}.html"
        else:
            path_part = url.replace(BASE_URL, "").strip("/").replace("/", "_")
            cache_file = self.sections_cache / f"{path_part}.html"

        if cache_file.exists():
            self.logger.debug("section_cache_hit", url=url)
            return cache_file.read_text(encoding="utf-8")

        resp = client.get(url)
        resp.raise_for_status()
        html = resp.text

        self.sections_cache.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(html, encoding="utf-8")
        self.logger.debug("section_fetched", url=url)

        if self.rate_limit > 0:
            time.sleep(self.rate_limit)

        return html

    @staticmethod
    def parse_section_page(html: str) -> dict[str, str]:
        """Parse a section page and extract regulatory text, authority, and references.

        Returns dict with keys: text, title, authority, reference
        """
        soup = BeautifulSoup(html, "lxml")

        # Extract title from the page heading
        title = ""
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)

        # Find the main content area — Cornell LII uses <div id="block-..."> or
        # similar content wrappers. Look for the regulation text.
        # Strategy: find all <p> tags in the main content area and collect text.
        text_parts: list[str] = []
        authority = ""
        reference = ""

        # Try to find the main content div
        # Cornell LII typically uses a content region with the regulation text
        content_div = (
            soup.find("div", class_="field-name-body")
            or soup.find("div", id="block-system-main")
            or soup.find("article")
            or soup.find("div", class_="content")
            or soup.find("main")
        )

        if content_div is None:
            content_div = soup.body or soup

        # Collect all text blocks from the content area
        for element in content_div.find_all(["p", "div", "li", "blockquote"]):
            element_text = element.get_text(separator=" ", strip=True)
            if not element_text:
                continue

            # Check for authority/reference in note sections
            auth_match = AUTHORITY_RE.search(element_text)
            if auth_match:
                authority = auth_match.group(1).strip()
                continue

            ref_match = REFERENCE_RE.search(element_text)
            if ref_match:
                reference = ref_match.group(1).strip()
                continue

            # Skip navigation/breadcrumb elements
            if element.find_parent(["nav", "header", "footer"]):
                continue

            # Skip very short lines that look like nav elements
            if len(element_text) < 5 and not any(c.isalpha() for c in element_text):
                continue

            text_parts.append(element_text)

        # Deduplicate adjacent identical lines (from nested elements)
        deduped: list[str] = []
        for part in text_parts:
            if not deduped or part != deduped[-1]:
                deduped.append(part)

        body_text = "\n\n".join(deduped)

        return {
            "text": body_text,
            "title": title,
            "authority": authority,
            "reference": reference,
        }

    def _build_statute_section(
        self, meta: SectionMeta, parsed: dict[str, str]
    ) -> StatuteSection:
        """Convert parsed section data to a StatuteSection."""
        # Build citation like "Cal. Code Regs. tit. 8, § 3207"
        citation = f"Cal. Code Regs. tit. 8, § {meta.section_number}"

        # Build heading path like "CCR Title 8 > Division 1 > Chapter 4 > ... > § 3207 Title"
        path_parts = ["CCR Title 8"] + meta.hierarchy_path
        section_label = f"§ {meta.section_number}"
        if meta.title:
            section_label += f" {meta.title}"
        path_parts.append(section_label)
        heading_path = " > ".join(path_parts)

        # Prepend authority/reference metadata if present
        text = parsed["text"]
        metadata_parts: list[str] = []
        if parsed.get("authority"):
            metadata_parts.append(f"Authority: {parsed['authority']}")
        if parsed.get("reference"):
            metadata_parts.append(f"Reference: {parsed['reference']}")
        if metadata_parts:
            text = text + "\n\n" + "\n".join(metadata_parts)

        hierarchy = HierarchyPath(code_name="8-CCR")

        section = StatuteSection(
            section_number=meta.section_number,
            code_abbreviation="8-CCR",
            text=text,
            citation=citation,
            hierarchy=hierarchy,
            source_url=meta.url,
        )
        section._heading_path_override = heading_path
        return section

    def to_statute_sections(self) -> list[StatuteSection]:
        """Full pipeline: discover → download → parse → convert to StatuteSections."""
        # Phase 1: TOC discovery
        crawler = CCRTitle8TOCCrawler(
            cache_dir=self.cache_dir / "toc",
            rate_limit=self.rate_limit,
            timeout=self.timeout,
        )

        client = httpx.Client(
            timeout=self.timeout,
            follow_redirects=True,
            headers={"User-Agent": "EmployeeHelp/1.0 (legal research tool)"},
        )

        try:
            discovered = crawler.discover(
                target_divisions=self.target_divisions,
                client=client,
            )

            if not discovered:
                self.logger.warning("no_ccr_sections_discovered")
                return []

            self.logger.info("ccr_sections_discovered", count=len(discovered))

            # Phase 2: Download and parse each section
            sections: list[StatuteSection] = []
            skipped = 0
            errors = 0

            for meta in discovered:
                # Skip repealed sections
                if meta.is_repealed:
                    skipped += 1
                    self.logger.debug(
                        "repealed_section_skipped",
                        section=meta.section_number,
                    )
                    continue

                try:
                    html = self._fetch_section(meta.url, client)
                    parsed = self.parse_section_page(html)

                    if not parsed["text"].strip():
                        self.logger.warning(
                            "empty_section_skipped",
                            section=meta.section_number,
                        )
                        skipped += 1
                        continue

                    section = self._build_statute_section(meta, parsed)
                    sections.append(section)

                except httpx.HTTPError as e:
                    self.logger.warning(
                        "section_fetch_failed",
                        section=meta.section_number,
                        url=meta.url,
                        error=str(e),
                    )
                    errors += 1
                    continue

            self.logger.info(
                "ccr_sections_created",
                discovered=len(discovered),
                sections=len(sections),
                skipped=skipped,
                errors=errors,
            )
            return sections

        finally:
            client.close()
