"""CCR Title 2 FEHA Regulations loader.

Fetches FEHA implementing regulations (CCR Title 2, Division 4.1, Chapter 5,
Subchapter 2) from Cornell LII. These regulations define practical terms that
FEHA leaves vague — reasonable accommodation, undue hardship, interactive
process, harassment training requirements, pregnancy disability leave, etc.

Architecture:
- Hardcoded manifest of ~80 section numbers across 11 articles (stable since 2016)
- Fetches each section from law.cornell.edu/regulations/california/2-CCR-{section}
- Parses with BeautifulSoup (div.statereg-text for body, div.statereg-notes for notes)
- Caches raw HTML locally to avoid redundant fetches
- Converts to StatuteSection objects for the statutory pipeline
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

CORNELL_BASE_URL = "https://www.law.cornell.edu/regulations/california"

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

# Patterns to detect reserved/renumbered sections (skip these)
_SKIP_PATTERNS = re.compile(r"\[(?:Renumbered|Reserved|Repealed)\]", re.IGNORECASE)


@dataclass
class CCRArticle:
    """An article within the FEHA regulations with its section numbers."""

    number: int
    name: str
    sections: list[str]


@dataclass
class CCRSection:
    """A parsed regulation section from Cornell LII."""

    number: str  # e.g., "11068"
    title: str  # e.g., "Reasonable Accommodation"
    text: str  # Full body text
    article: CCRArticle
    authority: str = ""  # Authority cited note
    reference: str = ""  # Reference note


# ── FEHA Regulation Manifest ────────────────────────────────
# CCR Title 2, Division 4.1, Chapter 5, Subchapter 2
# Articles 1-2, 4-11 (Article 3 is reserved)


FEHA_ARTICLES: list[CCRArticle] = [
    CCRArticle(
        number=1,
        name="General Matters",
        sections=[
            "11006", "11007", "11008", "11009",
        ],
    ),
    CCRArticle(
        number=2,
        name="Definitions",
        sections=[
            "11023", "11024", "11025", "11026", "11027", "11028", "11029",
            "11030", "11031", "11032", "11033", "11034",
        ],
    ),
    # Article 3 is reserved — no sections
    CCRArticle(
        number=4,
        name="Prohibited Practices",
        sections=[
            "11039", "11040", "11041", "11042", "11043", "11044",
            "11045", "11046", "11047", "11048", "11049",
            "11050", "11051", "11052", "11053", "11054",
        ],
    ),
    CCRArticle(
        number=5,
        name="Reasonable Accommodation and Interactive Process",
        sections=[
            "11064", "11065", "11066", "11067", "11068", "11069",
            "11070", "11071",
        ],
    ),
    CCRArticle(
        number=6,
        name="Harassment and Discrimination Prevention and Correction",
        sections=[
            "11019", "11020", "11021", "11022", "11023.1",
        ],
    ),
    CCRArticle(
        number=7,
        name="California Family Rights Act",
        sections=[
            "11087", "11088", "11089", "11090", "11091", "11092",
            "11093", "11094", "11095", "11096", "11097",
        ],
    ),
    CCRArticle(
        number=8,
        name="Pregnancy Disability Leave",
        sections=[
            "11035", "11036", "11037", "11038",
        ],
    ),
    CCRArticle(
        number=9,
        name="National Origin and Ancestry Discrimination",
        sections=[
            "11027.1", "11028.1",
        ],
    ),
    CCRArticle(
        number=9.5,
        name="Sex, Gender, Gender Identity, and Gender Expression Discrimination",
        sections=[
            "11030.1", "11031.1", "11034.1",
        ],
    ),
    CCRArticle(
        number=10,
        name="Religious Creed Discrimination",
        sections=[
            "11056", "11057", "11058", "11059", "11060", "11061", "11062",
        ],
    ),
    CCRArticle(
        number=11,
        name="New Parent Leave Act",
        sections=[
            "11098", "11099", "11100",
        ],
    ),
]


def get_all_section_numbers() -> list[str]:
    """Return all section numbers from the manifest, in order."""
    numbers: list[str] = []
    for article in FEHA_ARTICLES:
        numbers.extend(article.sections)
    return numbers


def get_article_for_section(section_number: str) -> CCRArticle | None:
    """Find the article that contains a given section number."""
    for article in FEHA_ARTICLES:
        if section_number in article.sections:
            return article
    return None


class CCRLoader:
    """Loads FEHA regulations from Cornell LII."""

    def __init__(
        self,
        rate_limit: float = 2.0,
        timeout: float = 30.0,
        cache_dir: Path = Path("data/ccr"),
    ) -> None:
        self.rate_limit = rate_limit
        self.timeout = timeout
        self.cache_dir = cache_dir
        self.logger = structlog.get_logger(__name__)

    def _cache_path(self, section_number: str) -> Path:
        """Return the local cache path for a section's HTML."""
        return self.cache_dir / f"2-CCR-{section_number}.html"

    def fetch_section(
        self,
        section_number: str,
        client: httpx.Client,
    ) -> CCRSection | None:
        """Fetch and parse a single regulation section.

        Uses local cache if available. Returns None for 404s, reserved/
        renumbered sections, or parse failures.
        """
        cache_path = self._cache_path(section_number)

        # Use cache if available
        if cache_path.exists():
            html = cache_path.read_text(encoding="utf-8")
            self.logger.debug("ccr_cache_hit", section=section_number)
        else:
            url = f"{CORNELL_BASE_URL}/2-CCR-{section_number}"
            try:
                resp = client.get(url)
                if resp.status_code == 404:
                    self.logger.warning("ccr_section_not_found", section=section_number)
                    return None
                resp.raise_for_status()
                html = resp.text
            except httpx.HTTPError as e:
                self.logger.error(
                    "ccr_fetch_error",
                    section=section_number,
                    error=str(e),
                )
                return None

            # Cache the HTML
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(html, encoding="utf-8")

        article = get_article_for_section(section_number)
        return self._parse_section_page(html, section_number, article)

    def _parse_section_page(
        self,
        html: str,
        section_number: str,
        article: CCRArticle | None,
    ) -> CCRSection | None:
        """Parse a Cornell LII regulation page into a CCRSection.

        Returns None if the section is reserved/renumbered or has no body text.
        """
        soup = BeautifulSoup(html, "html.parser")

        # Extract title from h1
        h1 = soup.find("h1")
        if not h1:
            self.logger.warning("ccr_no_h1", section=section_number)
            return None

        h1_text = h1.get_text(strip=True)

        # Skip reserved/renumbered sections
        if _SKIP_PATTERNS.search(h1_text):
            self.logger.info(
                "ccr_section_skipped",
                section=section_number,
                reason=h1_text,
            )
            return None

        # Parse title: "Cal. Code Regs. Tit. 2, § 11068 - Reasonable Accommodation"
        title = ""
        title_match = re.search(r"§\s*[\d.]+\s*-\s*(.+)$", h1_text)
        if title_match:
            title = title_match.group(1).strip()
        else:
            title = h1_text

        # Extract body text from div.statereg-text
        body_div = soup.find("div", class_="statereg-text")
        if not body_div:
            self.logger.warning("ccr_no_body", section=section_number)
            return None

        # Get text preserving subdivision structure
        body_text = self._extract_body_text(body_div)
        if not body_text.strip():
            self.logger.warning("ccr_empty_body", section=section_number)
            return None

        # Extract authority and reference from notes
        authority = ""
        reference = ""
        notes_div = soup.find("div", class_="statereg-notes")
        if notes_div:
            notes_text = notes_div.get_text(separator="\n")
            auth_match = re.search(
                r"Authority cited:\s*(.+?)(?:\n|Reference:)",
                notes_text,
                re.DOTALL,
            )
            if auth_match:
                authority = auth_match.group(1).strip()
            ref_match = re.search(
                r"Reference:\s*(.+?)(?:\n\n|\Z)",
                notes_text,
                re.DOTALL,
            )
            if ref_match:
                reference = ref_match.group(1).strip()

        return CCRSection(
            number=section_number,
            title=title,
            text=body_text,
            article=article or CCRArticle(number=0, name="Unknown", sections=[]),
            authority=authority,
            reference=reference,
        )

    @staticmethod
    def _extract_body_text(body_div) -> str:
        """Extract regulation body text preserving subdivision structure.

        Cornell LII uses div.subsect with indent levels for (a)/(b)/(1)/(A) etc.
        We reconstruct readable text from these nested divs.
        """
        lines: list[str] = []

        for element in body_div.find_all("div", class_="subsect"):
            text = element.get_text(separator=" ").strip()
            # Clean up excessive whitespace
            text = re.sub(r"\s+", " ", text)
            if text:
                lines.append(text)

        if lines:
            return "\n\n".join(lines)

        # Fallback: just get all text if no subsect divs found
        text = body_div.get_text(separator="\n")
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        return text

    def load_all(self) -> list[CCRSection]:
        """Fetch all sections from the manifest.

        Uses rate limiting between requests. Skips cached sections.
        """
        all_sections: list[CCRSection] = []
        section_numbers = get_all_section_numbers()

        self.logger.info(
            "ccr_load_start",
            total_sections=len(section_numbers),
        )

        with httpx.Client(
            timeout=self.timeout,
            follow_redirects=True,
            headers={"User-Agent": "EmployeeHelp/1.0 (legal-research)"},
        ) as client:
            for i, section_num in enumerate(section_numbers):
                section = self.fetch_section(section_num, client)
                if section:
                    all_sections.append(section)
                    self.logger.debug(
                        "ccr_section_loaded",
                        section=section_num,
                        title=section.title,
                        progress=f"{i + 1}/{len(section_numbers)}",
                    )

                # Rate limit (skip for cached sections)
                if not self._cache_path(section_num).exists() and i < len(section_numbers) - 1:
                    time.sleep(self.rate_limit)

        self.logger.info(
            "ccr_load_complete",
            loaded=len(all_sections),
            total=len(section_numbers),
            skipped=len(section_numbers) - len(all_sections),
        )

        return all_sections

    def to_statute_sections(
        self, sections: list[CCRSection] | None = None
    ) -> list[StatuteSection]:
        """Convert parsed CCR sections to StatuteSection objects.

        If sections is None, fetches all sections first.
        """
        if sections is None:
            sections = self.load_all()

        hierarchy = HierarchyPath(code_name="CCR Title 2")
        results: list[StatuteSection] = []

        for section in sections:
            citation = f"2 CCR § {section.number}"
            article_label = (
                f"Art. {section.article.number} ({section.article.name})"
                if section.article.number
                else "Unknown"
            )
            heading_path = (
                f"CCR Title 2 > FEHA Regulations > {article_label} "
                f"> § {section.number} {section.title}"
            )
            source_url = f"{CORNELL_BASE_URL}/2-CCR-{section.number}"

            # Include authority/reference as appendix to body text
            full_text = section.text
            if section.authority:
                full_text += f"\n\nAuthority cited: {section.authority}"
            if section.reference:
                full_text += f"\nReference: {section.reference}"

            statute = StatuteSection(
                section_number=section.number,
                code_abbreviation="2-CCR",
                text=full_text,
                citation=citation,
                hierarchy=hierarchy,
                source_url=source_url,
            )
            statute._heading_path_override = heading_path
            results.append(statute)

        self.logger.info(
            "ccr_statute_sections_created",
            count=len(results),
        )
        return results
