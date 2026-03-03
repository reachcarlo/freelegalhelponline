"""DLSE Enforcement Policies and Interpretations Manual loader.

Parses the official DLSE enforcement manual PDF (352 pages, ~53 chapters)
into per-chapter StatuteSection objects for the statutory pipeline.

The manual is the definitive source of DLSE policy interpretations covering
wages, overtime, meal breaks, exemptions, independent contractors, and more.
Published by the Division of Labor Standards Enforcement and revised periodically.

Architecture:
- Downloads single PDF from dir.ca.gov (or uses cached copy)
- Parses with pdfplumber, splits into chapters by heading detection
- Each chapter becomes a StatuteSection → chunked by the pipeline
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
import pdfplumber
import structlog

from employee_help.scraper.extractors.statute import HierarchyPath, StatuteSection

logger = structlog.get_logger(__name__)

MANUAL_PDF_URL = "https://www.dir.ca.gov/dlse/DLSEManual/dlse_enfcmanual.pdf"

# Page header that appears on every content page (stripped during parsing)
_PAGE_HEADER_RE = re.compile(
    r"^DIVISION OF LABOR STANDARDS ENFORCEMENT$|"
    r"^POLICIES AND INTERPRETATIONS MANUAL$",
    re.MULTILINE,
)

# Chapter heading: "2 WAGES." or "44. MINIMUM WAGE OBLIGATION." or "28 INDEPENDENT CONTRACTOR vs. EMPLOYEE."
# Must start with mostly uppercase title after a 1-2 digit number.
# Allows optional period after number (some chapters use "44." format).
# Allows lowercase words (vs., of), digits (2014), smart apostrophes.
_CHAPTER_START_RE = re.compile(
    r"^(\d{1,2})\.?\s+([A-Z][A-Za-z0-9\s—–\-,&().\'/\u2019]+)$"
)

# Subsection pattern: "2.1", "44.1.3", etc. — used to exclude from chapter detection
_SUBSECTION_RE = re.compile(r"^\d{1,2}\.\d")

# Introduction heading (chapter 1 has no number prefix)
_INTRO_RE = re.compile(r"^INTRODUCTION$")

# Page number footers like "2 - 1", "44 - 1", "JUNE, 2002 5 - 5", "DECEMBER 2022"
_PAGE_FOOTER_RE = re.compile(
    r"^\d{1,2}\s*-\s*\d{1,2}$|"
    r"^(?:JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)"
    r"[,]?\s*\d{4}",
    re.IGNORECASE,
)

# Combined footer: "JUNE, 2002 5 - 5" or "DECEMBER 2022" followed by page num
_TRAILING_FOOTER_RE = re.compile(
    r"(?:JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)"
    r"[,]?\s*\d{4}\s*\d{0,2}\s*-?\s*\d{0,2}\s*$",
    re.IGNORECASE,
)

# Ensure _heading_path_override support is patched onto StatuteSection.
if not hasattr(StatuteSection.heading_path.fget, "_patched"):

    @property  # type: ignore[misc]
    def _patched_heading_path(self: StatuteSection) -> str:
        override = getattr(self, "_heading_path_override", None)
        if override:
            return override
        return self.hierarchy.to_path_string()

    _patched_heading_path.fget._patched = True  # type: ignore[attr-defined]
    StatuteSection.heading_path = _patched_heading_path  # type: ignore[assignment]

# Number of TOC pages at the start (0-indexed pages 1-8, i.e. PDF pages 2-9)
_TOC_START_PAGE = 1  # 0-indexed
_TOC_END_PAGE = 8  # inclusive, 0-indexed

# Addendum marker — everything from here on is index/reference material, not substantive
_ADDENDUM_MARKERS = ("Opinion Letter Index", "ADDENDUM", "Following is a compilation")


@dataclass
class ManualChapter:
    """A parsed chapter from the DLSE enforcement manual."""

    number: str  # e.g., "1", "44"
    title: str  # e.g., "WAGES", "MINIMUM WAGE OBLIGATION"
    text: str  # Full chapter text (all sections)
    start_page: int  # 0-indexed page where chapter starts

    @property
    def clean_title(self) -> str:
        """Title with proper casing for display."""
        # Strip trailing periods and clean up
        title = self.title.rstrip(".").strip()
        # Title case, preserving acronyms like IWC, DLSE, ERISA
        words = title.split()
        result = []
        acronyms = {"IWC", "DLSE", "ERISA", "CAL-WARN", "CFR", "VS", "VS."}
        for word in words:
            if word.upper() in acronyms:
                result.append(word.upper())
            elif word in ("—", "–", "-", "&", "OF", "OR", "AND", "THE", "TO", "IN", "FOR", "BY", "FROM"):
                result.append(word.lower())
            else:
                result.append(word.capitalize())
        # Always capitalize first word
        if result:
            result[0] = result[0].capitalize() if result[0][0].islower() else result[0]
        return " ".join(result)


class DLSEManualLoader:
    """Loads and parses the DLSE Enforcement Policies and Interpretations Manual."""

    def __init__(
        self,
        pdf_path: Path | None = None,
        download_dir: Path = Path("data/dlse_manual"),
        timeout: float = 60.0,
    ) -> None:
        self.pdf_path = pdf_path
        self.download_dir = download_dir
        self.timeout = timeout
        self.logger = structlog.get_logger(__name__)

    def ensure_pdf(self) -> Path:
        """Download the manual PDF if not already cached.

        Returns path to the local PDF file.
        """
        if self.pdf_path and self.pdf_path.exists():
            return self.pdf_path

        self.download_dir.mkdir(parents=True, exist_ok=True)
        local_path = self.download_dir / "dlse_enfcmanual.pdf"

        if local_path.exists():
            self.logger.debug("manual_pdf_cached", path=str(local_path))
            return local_path

        self.logger.info("downloading_manual_pdf", url=MANUAL_PDF_URL)
        client = httpx.Client(timeout=self.timeout, follow_redirects=True)
        try:
            resp = client.get(MANUAL_PDF_URL)
            resp.raise_for_status()
            local_path.write_bytes(resp.content)
            self.logger.info(
                "manual_pdf_downloaded",
                size=len(resp.content),
                path=str(local_path),
            )
        finally:
            client.close()

        return local_path

    def extract_pages(self, pdf_path: Path) -> list[str]:
        """Extract text from all PDF pages via pdfplumber."""
        pages: list[str] = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                pages.append(text)
        self.logger.info("pages_extracted", count=len(pages))
        return pages

    @staticmethod
    def clean_page_text(text: str) -> str:
        """Strip page headers, footers, and page numbers from a single page."""
        lines = text.split("\n")
        cleaned: list[str] = []

        for line in lines:
            stripped = line.strip()

            # Skip the standard two-line page header
            if _PAGE_HEADER_RE.match(stripped):
                continue

            # Skip standalone page number footers like "2 - 1" or "44 - 1"
            if re.match(r"^\d{1,2}\s*-\s*\d{1,2}$", stripped):
                continue

            # Skip date-only footer lines like "JUNE, 2002" or "DECEMBER 2022"
            if re.match(
                r"^(?:JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|"
                r"OCTOBER|NOVEMBER|DECEMBER)[,]?\s*\d{4}$",
                stripped,
                re.IGNORECASE,
            ):
                continue

            cleaned.append(line)

        result = "\n".join(cleaned).strip()

        # Strip trailing combined footer (e.g., "JUNE, 2002 5 - 5" at end of text)
        result = _TRAILING_FOOTER_RE.sub("", result).rstrip()

        return result

    def parse_chapters(self, pages: list[str]) -> list[ManualChapter]:
        """Parse chapter boundaries from extracted page text.

        Strategy:
        1. Skip title page (page 0) and TOC pages (pages 1-8)
        2. Detect chapter starts via heading regex or INTRODUCTION marker
        3. Accumulate text across pages until next chapter or addendum
        4. Stop at addendum markers
        """
        chapters: list[ManualChapter] = []
        current_number: str | None = None
        current_title: str = ""
        current_lines: list[str] = []
        current_start_page: int = 0

        for page_idx, raw_text in enumerate(pages):
            # Skip title page and TOC
            if page_idx <= _TOC_END_PAGE:
                continue

            cleaned = self.clean_page_text(raw_text)
            if not cleaned:
                continue

            # Check for addendum markers — stop processing
            for marker in _ADDENDUM_MARKERS:
                if marker in cleaned:
                    # Flush current chapter before stopping
                    if current_number is not None:
                        chapters.append(
                            ManualChapter(
                                number=current_number,
                                title=current_title,
                                text="\n".join(current_lines).strip(),
                                start_page=current_start_page,
                            )
                        )
                    self.logger.info(
                        "addendum_reached",
                        page=page_idx + 1,
                        chapters_parsed=len(chapters) + (1 if current_number else 0),
                    )
                    return chapters

            lines = cleaned.split("\n")

            for line in lines:
                stripped = line.strip()
                if not stripped:
                    current_lines.append("")
                    continue

                # Check for Introduction heading (chapter 1, no number prefix)
                if _INTRO_RE.match(stripped) and current_number is None:
                    current_number = "1"
                    current_title = "INTRODUCTION"
                    current_lines = []
                    current_start_page = page_idx
                    continue

                # Check for chapter heading
                m = _CHAPTER_START_RE.match(stripped)
                if m and not _SUBSECTION_RE.match(stripped):
                    num = m.group(1)
                    title = m.group(2).strip()

                    # Require title to be at least 4 chars and mostly uppercase
                    alpha_chars = [c for c in title if c.isalpha()]
                    upper_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars) if alpha_chars else 0
                    if len(title) >= 4 and upper_ratio >= 0.6:
                        # Flush previous chapter
                        if current_number is not None:
                            chapters.append(
                                ManualChapter(
                                    number=current_number,
                                    title=current_title,
                                    text="\n".join(current_lines).strip(),
                                    start_page=current_start_page,
                                )
                            )

                        current_number = num
                        current_title = title
                        current_lines = []
                        current_start_page = page_idx
                        continue

                # Accumulate text
                if current_number is not None:
                    current_lines.append(stripped)

        # Flush final chapter
        if current_number is not None:
            chapters.append(
                ManualChapter(
                    number=current_number,
                    title=current_title,
                    text="\n".join(current_lines).strip(),
                    start_page=current_start_page,
                )
            )

        self.logger.info("chapters_parsed", count=len(chapters))
        return chapters

    def to_statute_sections(
        self, chapters: list[ManualChapter] | None = None
    ) -> list[StatuteSection]:
        """Convert parsed chapters to StatuteSection objects.

        If chapters is None, downloads/parses the PDF first.
        """
        if chapters is None:
            pdf_path = self.ensure_pdf()
            pages = self.extract_pages(pdf_path)
            chapters = self.parse_chapters(pages)

        hierarchy = HierarchyPath(code_name="DLSE Enforcement Manual")
        base_url = MANUAL_PDF_URL

        sections: list[StatuteSection] = []
        for chapter in chapters:
            if not chapter.text.strip():
                self.logger.warning(
                    "empty_chapter_skipped",
                    chapter=chapter.number,
                    title=chapter.title,
                )
                continue

            citation = f"DLSE Enforcement Manual Ch. {chapter.number}"
            heading_path = f"DLSE Enforcement Manual > {chapter.clean_title}"
            # Unique source_url per chapter for upsert dedup
            source_url = f"{base_url}#chapter-{chapter.number}"

            section = StatuteSection(
                section_number=chapter.number,
                code_abbreviation="DLSE-Manual",
                text=chapter.text,
                citation=citation,
                hierarchy=hierarchy,
                source_url=source_url,
            )
            section._heading_path_override = heading_path
            sections.append(section)

        self.logger.info(
            "manual_sections_created",
            chapters=len(chapters),
            sections=len(sections),
        )
        return sections
