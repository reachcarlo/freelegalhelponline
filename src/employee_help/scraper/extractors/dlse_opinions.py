"""DLSE Opinion Letters loader.

Discovers, downloads, and parses DLSE (Division of Labor Standards Enforcement)
opinion letters from dir.ca.gov. These are interpretive guidance documents issued
by the California Labor Commissioner (1983–2019) addressing real employment
questions — overtime, meal breaks, commissions, tips, uniforms — by applying
Labor Code sections to specific fact patterns.

Architecture:
- Two-phase process: scrape HTML index pages for metadata → download PDFs → parse
- Uses httpx for HTTP requests, BeautifulSoup for HTML parsing, pdfplumber for PDFs
- Converts each letter to a StatuteSection for pipeline compatibility
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

import httpx
import pdfplumber
import structlog
from bs4 import BeautifulSoup

from employee_help.scraper.extractors.statute import HierarchyPath, StatuteSection

logger = structlog.get_logger(__name__)

# Ensure _heading_path_override support is patched onto StatuteSection.
# The CACI loader applies the same patch; this is idempotent.
if not hasattr(StatuteSection.heading_path.fget, "_patched"):

    @property  # type: ignore[misc]
    def _patched_heading_path(self: StatuteSection) -> str:
        override = getattr(self, "_heading_path_override", None)
        if override:
            return override
        return self.hierarchy.to_path_string()

    _patched_heading_path.fget._patched = True  # type: ignore[attr-defined]
    StatuteSection.heading_path = _patched_heading_path  # type: ignore[assignment]

INDEX_BY_SUBJECT = "https://www.dir.ca.gov/dlse/opinionletters-bysubject.htm"
INDEX_BY_DATE = "https://www.dir.ca.gov/dlse/opinionletters-bydate.htm"

# Pattern to match PDF links in opinion letter index pages
_PDF_LINK_RE = re.compile(r"/dlse/opinions/.*\.pdf$", re.IGNORECASE)

# Pattern to detect withdrawn entries in table text
_WITHDRAWN_RE = re.compile(r"\bwithdrawn\b", re.IGNORECASE)

# Requesting letter suffix
_RL_SUFFIX_RE = re.compile(r"-RL\.pdf$", re.IGNORECASE)

# Pattern to extract date from filename like "2019.01.03.pdf" or "2019-01-03.pdf"
_DATE_FROM_FILENAME_RE = re.compile(r"(\d{4})[.\-](\d{2})[.\-](\d{2})")

# Signature block markers for stripping
_SIGNATURE_RE = re.compile(
    r"^(Sincerely|Very truly yours|Respectfully),?\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Statute citation patterns for extraction
_STATUTE_CITE_PATTERNS = [
    re.compile(r"Labor\s+Code\s+(?:section|§)\s*(\d+(?:\.\d+)?)", re.IGNORECASE),
    re.compile(r"Lab\.\s*Code,?\s*§\s*(\d+(?:\.\d+)?)", re.IGNORECASE),
    re.compile(r"Government\s+Code\s+(?:section|§)\s*(\d+(?:\.\d+)?)", re.IGNORECASE),
    re.compile(r"Gov\.\s*Code,?\s*§\s*(\d+(?:\.\d+)?)", re.IGNORECASE),
]


@dataclass
class OpinionLetterMeta:
    """Metadata for a single DLSE opinion letter."""

    date: str  # "2019-01-03"
    pdf_url: str  # Full URL to PDF
    subject: str  # Topic from index (e.g., "Overtime")
    description: str  # Brief description from index table
    filename: str  # "2019.01.03.pdf"


class DLSEOpinionIndexScraper:
    """Scrapes DLSE opinion letter index pages to discover PDF URLs and metadata."""

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout
        self.logger = structlog.get_logger(__name__)

    def scrape_by_subject(self, html: str) -> list[OpinionLetterMeta]:
        """Parse the by-subject index page HTML into OpinionLetterMeta objects."""
        soup = BeautifulSoup(html, "lxml")
        letters: list[OpinionLetterMeta] = []

        current_subject = "General"

        # The by-subject page organizes letters under subject headings.
        # Look for tables and headings to extract metadata.
        for table in soup.find_all("table"):
            # Check for a subject heading before/above the table
            prev = table.find_previous_sibling(["h2", "h3", "h4", "strong", "b", "p"])
            if prev:
                subject_text = prev.get_text(strip=True)
                if subject_text and len(subject_text) < 100:
                    current_subject = subject_text

            for row in table.find_all("tr"):
                cells = row.find_all(["td", "th"])
                if not cells:
                    continue

                # Find PDF link in this row
                link = row.find("a", href=_PDF_LINK_RE)
                if not link:
                    continue

                href = link.get("href", "")
                if not href:
                    continue

                # Skip requesting letters
                if _RL_SUFFIX_RE.search(href):
                    continue

                # Check if withdrawn
                row_text = row.get_text(" ", strip=True)
                if _WITHDRAWN_RE.search(row_text):
                    continue

                # Resolve relative URL
                pdf_url = urljoin(INDEX_BY_SUBJECT, href)
                filename = Path(href).name

                # Extract date from filename
                date = self._extract_date(filename)

                # Build description from cell text
                description = row_text[:200].strip()

                letters.append(
                    OpinionLetterMeta(
                        date=date,
                        pdf_url=pdf_url,
                        subject=current_subject,
                        description=description,
                        filename=filename,
                    )
                )

        self.logger.info("index_by_subject_parsed", letters=len(letters))
        return letters

    def scrape_by_date(self, html: str) -> list[OpinionLetterMeta]:
        """Parse the by-date index page HTML into OpinionLetterMeta objects."""
        soup = BeautifulSoup(html, "lxml")
        letters: list[OpinionLetterMeta] = []

        for link in soup.find_all("a", href=_PDF_LINK_RE):
            href = link.get("href", "")
            if not href:
                continue

            # Skip requesting letters
            if _RL_SUFFIX_RE.search(href):
                continue

            # Check parent row or surrounding text for withdrawn
            parent = link.find_parent("tr")
            if parent and _WITHDRAWN_RE.search(parent.get_text(" ", strip=True)):
                continue

            # Also check the link text itself and immediate context
            link_text = link.get_text(strip=True)
            if _WITHDRAWN_RE.search(link_text):
                continue

            pdf_url = urljoin(INDEX_BY_DATE, href)
            filename = Path(href).name
            date = self._extract_date(filename)

            # Try to get description from table row
            description = ""
            if parent:
                description = parent.get_text(" ", strip=True)[:200].strip()
            else:
                description = link_text

            letters.append(
                OpinionLetterMeta(
                    date=date,
                    pdf_url=pdf_url,
                    subject="General",
                    description=description,
                    filename=filename,
                )
            )

        self.logger.info("index_by_date_parsed", letters=len(letters))
        return letters

    @staticmethod
    def _extract_date(filename: str) -> str:
        """Extract a date string from a filename like '2019.01.03.pdf'."""
        m = _DATE_FROM_FILENAME_RE.search(filename)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        # Fall back to filename without extension
        return Path(filename).stem

    def discover(self, client: httpx.Client | None = None) -> list[OpinionLetterMeta]:
        """Fetch both index pages and return deduplicated letter metadata.

        Prefers metadata from the by-subject page (richer topic info).
        Falls back to by-date page for letters not found on subject page.
        """
        own_client = client is None
        if own_client:
            client = httpx.Client(timeout=self.timeout, follow_redirects=True)

        try:
            # Fetch both index pages
            subject_letters: list[OpinionLetterMeta] = []
            date_letters: list[OpinionLetterMeta] = []

            try:
                resp = client.get(INDEX_BY_SUBJECT)
                resp.raise_for_status()
                subject_letters = self.scrape_by_subject(resp.text)
            except httpx.HTTPError as e:
                self.logger.warning("subject_index_fetch_failed", error=str(e))

            try:
                resp = client.get(INDEX_BY_DATE)
                resp.raise_for_status()
                date_letters = self.scrape_by_date(resp.text)
            except httpx.HTTPError as e:
                self.logger.warning("date_index_fetch_failed", error=str(e))

            # Deduplicate: prefer subject page entries (richer metadata)
            seen_filenames: dict[str, OpinionLetterMeta] = {}
            for letter in subject_letters:
                seen_filenames[letter.filename] = letter
            for letter in date_letters:
                if letter.filename not in seen_filenames:
                    seen_filenames[letter.filename] = letter

            result = list(seen_filenames.values())
            self.logger.info(
                "discovery_complete",
                subject_count=len(subject_letters),
                date_count=len(date_letters),
                deduplicated=len(result),
            )
            return result

        finally:
            if own_client:
                client.close()


class DLSEOpinionLoader:
    """Downloads and parses DLSE opinion letter PDFs into StatuteSection objects."""

    def __init__(
        self,
        download_dir: Path = Path("data/dlse_opinions"),
        rate_limit: float = 2.0,
        timeout: float = 30.0,
    ) -> None:
        self.download_dir = download_dir
        self.rate_limit = rate_limit
        self.timeout = timeout
        self.logger = structlog.get_logger(__name__)

    def discover_letters(self) -> list[OpinionLetterMeta]:
        """Discover opinion letters from DLSE index pages."""
        scraper = DLSEOpinionIndexScraper(timeout=self.timeout)
        return scraper.discover()

    def download_pdfs(
        self,
        letters: list[OpinionLetterMeta],
        skip_existing: bool = True,
    ) -> list[tuple[OpinionLetterMeta, Path]]:
        """Download PDFs for the given letters.

        Returns list of (metadata, local_path) tuples for successfully downloaded files.
        """
        self.download_dir.mkdir(parents=True, exist_ok=True)

        downloaded: list[tuple[OpinionLetterMeta, Path]] = []
        client = httpx.Client(timeout=self.timeout, follow_redirects=True)

        try:
            for letter in letters:
                local_path = self.download_dir / letter.filename

                if skip_existing and local_path.exists():
                    self.logger.debug("pdf_exists_skipping", filename=letter.filename)
                    downloaded.append((letter, local_path))
                    continue

                try:
                    resp = client.get(letter.pdf_url)
                    resp.raise_for_status()
                    local_path.write_bytes(resp.content)
                    downloaded.append((letter, local_path))
                    self.logger.debug(
                        "pdf_downloaded",
                        filename=letter.filename,
                        size=len(resp.content),
                    )

                    if self.rate_limit > 0:
                        time.sleep(self.rate_limit)

                except httpx.HTTPError as e:
                    self.logger.warning(
                        "pdf_download_failed",
                        filename=letter.filename,
                        url=letter.pdf_url,
                        error=str(e),
                    )
                    continue

        finally:
            client.close()

        self.logger.info(
            "download_complete",
            requested=len(letters),
            downloaded=len(downloaded),
        )
        return downloaded

    @staticmethod
    def parse_pdf(pdf_path: Path) -> str:
        """Extract text from a PDF using pdfplumber.

        Returns empty string for image-only/scanned PDFs.
        """
        try:
            with pdfplumber.open(pdf_path) as pdf:
                pages = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        pages.append(text)
                return "\n\n".join(pages)
        except Exception as e:
            logger.warning("pdf_parse_error", path=str(pdf_path), error=str(e))
            return ""

    @staticmethod
    def strip_signature(text: str) -> str:
        """Strip signature block from end of letter text."""
        match = _SIGNATURE_RE.search(text)
        if match:
            return text[: match.start()].rstrip()
        return text

    @staticmethod
    def extract_cited_statutes(text: str) -> list[str]:
        """Extract statute citations from opinion letter text.

        Returns list of citation strings like "Labor Code section 510".
        """
        citations: list[str] = []
        seen: set[str] = set()
        for pattern in _STATUTE_CITE_PATTERNS:
            for match in pattern.finditer(text):
                full_match = match.group(0)
                if full_match not in seen:
                    seen.add(full_match)
                    citations.append(full_match)
        return citations

    def _build_statute_section(
        self, letter: OpinionLetterMeta, body_text: str
    ) -> StatuteSection:
        """Convert a parsed opinion letter to a StatuteSection."""
        # Prepend metadata header for retrieval context
        header = f"DLSE Opinion Letter dated {letter.date}\nSubject: {letter.subject}\n\n"
        full_text = header + body_text

        hierarchy = HierarchyPath(code_name="DLSE Opinion Letters")

        citation = f"DLSE Opinion Letter {letter.date} ({letter.subject})"
        heading_path = f"DLSE Opinion Letters > {letter.subject} > {letter.date}"

        section = StatuteSection(
            section_number=letter.date,
            code_abbreviation="DLSE",
            text=full_text,
            citation=citation,
            hierarchy=hierarchy,
            source_url=letter.pdf_url,
        )
        # Use heading_path override (same pattern as CACI)
        section._heading_path_override = heading_path
        return section

    def to_statute_sections(self) -> list[StatuteSection]:
        """Full pipeline: discover → download → parse → convert to StatuteSections."""
        letters = self.discover_letters()
        if not letters:
            self.logger.warning("no_opinion_letters_discovered")
            return []

        self.logger.info("opinion_letters_discovered", count=len(letters))

        downloaded = self.download_pdfs(letters)
        sections: list[StatuteSection] = []
        skipped = 0

        for letter, pdf_path in downloaded:
            text = self.parse_pdf(pdf_path)
            if not text.strip():
                self.logger.warning(
                    "empty_pdf_skipped",
                    filename=letter.filename,
                )
                skipped += 1
                continue

            body = self.strip_signature(text)
            section = self._build_statute_section(letter, body)
            sections.append(section)

        self.logger.info(
            "opinion_sections_created",
            total_discovered=len(letters),
            downloaded=len(downloaded),
            sections=len(sections),
            skipped_empty=skipped,
        )
        return sections
