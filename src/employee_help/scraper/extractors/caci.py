"""CACI (California Civil Jury Instructions) PDF loader.

Parses the official Judicial Council CACI PDF to extract employment-related
jury instructions (series 2400-2899, 4600-4699) with per-section chunking.

Each instruction is split into up to 4 sections for optimal retrieval:
  - Instruction Text: core content (claim elements, burdens of proof)
  - Directions for Use: practical guidance on when/how to use
  - Sources and Authority: case law citations supporting each element
  - Secondary Sources: treatise references (merged with Sources if short)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber
import structlog

from employee_help.scraper.extractors.statute import HierarchyPath, StatuteSection

logger = structlog.get_logger(__name__)

# Employment-related CACI series ranges
EMPLOYMENT_SERIES = [
    (2400, 2499),  # Wrongful Termination
    (2500, 2599),  # FEHA Discrimination & Harassment
    (2600, 2699),  # CFRA Leave
    (2700, 2799),  # Labor Code Violations
    (2800, 2899),  # Workers' Comp Discrimination
    (4600, 4699),  # Whistleblower Protection
]

# Series names for heading path hierarchy
SERIES_NAMES = {
    24: "Wrongful Termination",
    25: "FEHA Discrimination and Harassment",
    26: "CFRA Leave",
    27: "Labor Code Violations",
    28: "Workers' Compensation",
    46: "Whistleblower Protection",
}

# Regex for instruction start: "2430. Title..." or "2521A. Title..."
_INSTRUCTION_START_RE = re.compile(r"^(\d{4}[A-Z]?)\.\s+(.+)")

# Regex for VF (Verdict Form) entries — skip these
_VF_START_RE = re.compile(r"^VF-\d{4}")

# Regex for continuation page headers
# "CACI No. 2401 WRONGFULTERMINATION" or "WRONGFULTERMINATION CACI No. 2401"
# Also "CACI No. 2521A FAIREMPLOYMENTANDHOUSINGACT"
_HEADER_CACI_LEFT_RE = re.compile(r"^CACI\s+No\.\s+\d+[A-Z]?\s+\S+")
_HEADER_CACI_RIGHT_RE = re.compile(r"^\S+\s+CACI\s+No\.\s+\d+[A-Z]?$")
# VF continuation: "VF-2400 WRONGFULTERMINATION" or "WRONGFULTERMINATION VF-2400"
_HEADER_VF_LEFT_RE = re.compile(r"^VF-\d+\s+\S+")
_HEADER_VF_RIGHT_RE = re.compile(r"^\S+\s+VF-\d+$")

# Section delimiters within an instruction
_DIRECTIONS_RE = re.compile(r"^Directions\s+for\s+Use$")
_SOURCES_RE = re.compile(r"^Sources\s+and\s+Authority$")
_SECONDARY_RE = re.compile(r"^Secondary\s+Sources$")

# Date line marking end of instruction text body
_DATE_LINE_RE = re.compile(
    r"^(New|Revised|Renumbered|Revoked|Restored)\s+\w+\s+\d{4}"
)

# Page number at end of page (just a number on its own line)
_PAGE_NUMBER_RE = re.compile(r"^\d{3,4}$")

# Series TOC page header (series name with spaces, all caps)
_SERIES_TOC_NAMES = {
    "WRONGFUL TERMINATION",
    "FAIR EMPLOYMENT AND HOUSING ACT",
    "CALIFORNIA FAMILY RIGHTS ACT",
    "LABOR CODE ACTIONS",
    "WORKERS' COMPENSATION",
    "WHISTLEBLOWER PROTECTION",
}


@dataclass
class CACIInstruction:
    """A parsed CACI jury instruction with all sections."""

    number: str  # e.g., "2430"
    title: str  # e.g., "Wrongful Discharge in Violation of Public Policy—Essential Factual Elements"
    series: str  # e.g., "Wrongful Termination"
    instruction_text: str = ""
    directions_for_use: str = ""
    sources_and_authority: str = ""
    secondary_sources: str = ""

    @property
    def citation(self) -> str:
        return f"CACI No. {self.number}"

    def to_statute_sections(self) -> list[StatuteSection]:
        """Convert to StatuteSection objects for pipeline compatibility.

        Each non-empty section becomes a separate StatuteSection with distinct
        heading_path suffixes for retrieval differentiation.
        """
        sections: list[StatuteSection] = []
        base_url = "https://www.courts.ca.gov/partners/317.htm"
        base_heading = f"CACI > {self.series} > No. {self.number} — {self.title}"

        hierarchy = HierarchyPath(code_name="CACI")

        section_map = [
            ("instruction_text", "Instruction Text", self.instruction_text),
            ("directions_for_use", "Directions for Use", self.directions_for_use),
            ("sources_and_authority", "Sources and Authority", self.sources_and_authority),
        ]

        # Merge secondary sources into sources_and_authority if present
        merged_sources = self.sources_and_authority
        if self.secondary_sources:
            if merged_sources:
                merged_sources = merged_sources.rstrip() + "\n\nSecondary Sources\n" + self.secondary_sources
            else:
                merged_sources = self.secondary_sources
            # Update the sources entry in section_map
            section_map[2] = ("sources_and_authority", "Sources and Authority", merged_sources)

        for key, label, text in section_map:
            text = text.strip()
            if not text:
                continue

            heading_path = f"{base_heading} > {label}"
            citation = self.citation
            # Each section needs a unique source_url for upsert_document dedup
            section_url = f"{base_url}#CACI-{self.number}-{key}"

            sections.append(
                StatuteSection(
                    section_number=self.number,
                    code_abbreviation="CACI",
                    text=text,
                    citation=citation,
                    hierarchy=hierarchy,
                    source_url=section_url,
                )
            )
            # Override heading_path since HierarchyPath.to_path_string() only returns "CACI"
            sections[-1]._heading_path_override = heading_path

        return sections


def _parse_instruction_number(number_str: str) -> int:
    """Extract the numeric part of an instruction number (e.g., '2521A' -> 2521)."""
    return int(re.match(r"(\d+)", number_str).group(1))


def _is_employment_instruction(number_str: str) -> bool:
    """Check if an instruction number belongs to an employment-related series."""
    num = _parse_instruction_number(number_str)
    return any(start <= num <= end for start, end in EMPLOYMENT_SERIES)


def _get_series_name(number_str: str) -> str:
    """Get the series name for an instruction number."""
    num = _parse_instruction_number(number_str)
    prefix = num // 100
    return SERIES_NAMES.get(prefix, f"Series {prefix}00")


def _is_toc_page(text: str) -> bool:
    """Check if a page is a TOC page (listing of instruction titles).

    Uses two heuristics:
    1. First line matches a known series TOC header
    2. Page has 3+ instruction number matches (volume-level TOC pages)
    """
    if not text.strip():
        return False
    first_line = text.strip().split("\n")[0].strip()
    if first_line in _SERIES_TOC_NAMES:
        return True
    # Volume TOC pages and series listings have many instruction numbers
    matches = re.findall(r"^\d{4}[A-Z]?\.\s+", text, re.MULTILINE)
    return len(matches) >= 3


def _strip_page_header_footer(text: str) -> str:
    """Remove continuation page headers and page number footers."""
    lines = text.split("\n")
    cleaned: list[str] = []

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Skip page numbers (last non-empty line is typically a 3-4 digit number)
        if _PAGE_NUMBER_RE.match(stripped):
            continue

        # Skip continuation page headers
        if _HEADER_CACI_LEFT_RE.match(stripped):
            continue
        if _HEADER_CACI_RIGHT_RE.match(stripped):
            continue
        if _HEADER_VF_LEFT_RE.match(stripped):
            continue
        if _HEADER_VF_RIGHT_RE.match(stripped):
            continue

        # Skip "This version provided by..." footer lines
        if stripped.startswith("This version provided b"):
            continue

        cleaned.append(line)

    return "\n".join(cleaned)


class CACILoader:
    """Loads and parses CACI jury instructions from the official PDF."""

    def __init__(self, pdf_path: str | Path) -> None:
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"CACI PDF not found: {self.pdf_path}")
        self.logger = structlog.get_logger(__name__)

    def parse_instructions(self) -> list[CACIInstruction]:
        """Parse all employment-related instructions from the PDF.

        Returns:
            List of CACIInstruction objects for employment series only.
        """
        self.logger.info("caci_parse_start", pdf=str(self.pdf_path))

        raw_pages = self._extract_pages()
        instructions = self._parse_instruction_boundaries(raw_pages)

        # Filter to employment-related series
        employment = [
            inst for inst in instructions
            if _is_employment_instruction(inst.number)
        ]

        self.logger.info(
            "caci_parse_complete",
            total_parsed=len(instructions),
            employment_filtered=len(employment),
        )
        return employment

    def _extract_pages(self) -> list[str]:
        """Extract text from all PDF pages."""
        pages: list[str] = []
        with pdfplumber.open(self.pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                pages.append(text)
        return pages

    def _parse_instruction_boundaries(
        self, pages: list[str]
    ) -> list[CACIInstruction]:
        """Parse instruction boundaries across all pages.

        Strategy:
        1. Skip TOC pages and VF (Verdict Form) pages
        2. Detect instruction starts via "NNNN. Title..." pattern
        3. Accumulate text across pages until next instruction
        4. Split accumulated text into sections (instruction text, directions, etc.)
        """
        instructions: list[CACIInstruction] = []
        current_number: str | None = None
        current_title: str = ""
        current_text_lines: list[str] = []
        in_vf_section = False

        for page_idx, raw_text in enumerate(pages):
            if not raw_text.strip():
                continue

            # Skip TOC pages
            if _is_toc_page(raw_text):
                continue

            # Check if this is a VF page
            first_line = raw_text.strip().split("\n")[0].strip()
            if _VF_START_RE.match(first_line):
                # Starting a VF section — flush current instruction and skip
                if current_number is not None:
                    inst = self._build_instruction(
                        current_number, current_title, current_text_lines
                    )
                    if inst:
                        instructions.append(inst)
                    current_number = None
                    current_title = ""
                    current_text_lines = []
                in_vf_section = True
                continue

            # Check continuation page headers for VF
            if in_vf_section:
                if _HEADER_VF_LEFT_RE.match(first_line) or _HEADER_VF_RIGHT_RE.match(first_line):
                    continue
                # If we see a new non-VF instruction start, exit VF mode
                if _INSTRUCTION_START_RE.match(first_line):
                    in_vf_section = False
                elif _is_toc_page(raw_text):
                    in_vf_section = False
                    continue
                else:
                    continue

            # Clean headers/footers from the page
            cleaned = _strip_page_header_footer(raw_text)
            if not cleaned.strip():
                continue

            lines = cleaned.split("\n")

            for line in lines:
                stripped = line.strip()
                if not stripped:
                    current_text_lines.append("")
                    continue

                # Check for new instruction start
                m = _INSTRUCTION_START_RE.match(stripped)
                if m:
                    # Check it's not a "Reserved" or range entry
                    number_str = m.group(1)
                    title_part = m.group(2).strip()

                    if "Reserved" in title_part:
                        continue

                    # Flush previous instruction
                    if current_number is not None:
                        inst = self._build_instruction(
                            current_number, current_title, current_text_lines
                        )
                        if inst:
                            instructions.append(inst)

                    current_number = number_str
                    current_title = title_part
                    current_text_lines = []
                    continue

                # Accumulate text for current instruction
                if current_number is not None:
                    current_text_lines.append(stripped)

        # Flush final instruction
        if current_number is not None:
            inst = self._build_instruction(
                current_number, current_title, current_text_lines
            )
            if inst:
                instructions.append(inst)

        return instructions

    def _build_instruction(
        self,
        number: str,
        title_start: str,
        text_lines: list[str],
    ) -> CACIInstruction | None:
        """Build a CACIInstruction from accumulated text lines.

        Splits the accumulated text into sections:
        instruction_text, directions_for_use, sources_and_authority, secondary_sources.
        """
        if not text_lines:
            return None

        # The title may span multiple lines before the instruction body starts.
        # Reconstruct full title: lines before the date line or body content.
        # The first lines after the instruction number are title continuation,
        # then the instruction body starts.
        full_title = title_start
        body_start_idx = 0

        # Title continuation is at most 3 lines (for long wrapped titles).
        # After that, everything is body text.
        max_title_lines = 3

        for i, line in enumerate(text_lines):
            # Date line marks end of title continuation (it appears AFTER the body)
            if _DATE_LINE_RE.match(line):
                body_start_idx = i
                break
            # Body starts when we see content that looks like instruction text
            if (
                line.startswith("[Name of")
                or line.startswith("[")
                or line.startswith("An ")
                or line.startswith("A ")
                or line.startswith("The ")
                or line.startswith("If ")
                or line.startswith("In ")
                or line.startswith("\"")
                or line.startswith("\u201c")  # left smart quote
                or line.startswith("1.")
                or re.match(r"^[A-Z][a-z]+ [a-z]", line)  # Sentence pattern
            ):
                body_start_idx = i
                break
            # Limit title continuation to max_title_lines
            if i >= max_title_lines:
                body_start_idx = i
                break
            # Otherwise this line is title continuation
            full_title += " " + line

        # Clean up title (remove line-break artifacts)
        full_title = re.sub(r"\s+", " ", full_title).strip()
        # Remove trailing statute reference in parens if it wraps
        # e.g., "(Gov.\nCode, § 12940(a))" → "(Gov. Code, § 12940(a))"

        series_name = _get_series_name(number)

        # Split remaining lines into sections
        section_lines = text_lines[body_start_idx:]
        instruction_text_lines: list[str] = []
        directions_lines: list[str] = []
        sources_lines: list[str] = []
        secondary_lines: list[str] = []

        current_section = "instruction"

        for line in section_lines:
            if _DIRECTIONS_RE.match(line):
                current_section = "directions"
                continue
            if _SOURCES_RE.match(line):
                current_section = "sources"
                continue
            if _SECONDARY_RE.match(line):
                current_section = "secondary"
                continue

            if current_section == "instruction":
                instruction_text_lines.append(line)
            elif current_section == "directions":
                directions_lines.append(line)
            elif current_section == "sources":
                sources_lines.append(line)
            elif current_section == "secondary":
                secondary_lines.append(line)

        # The instruction text includes everything up to "Directions for Use"
        # but the date line should be excluded from instruction text
        inst_text = self._clean_section(instruction_text_lines)
        # Remove trailing date lines from instruction text
        inst_text = self._strip_date_line(inst_text)

        instruction = CACIInstruction(
            number=number,
            title=full_title,
            series=series_name,
            instruction_text=inst_text,
            directions_for_use=self._clean_section(directions_lines),
            sources_and_authority=self._clean_section(sources_lines),
            secondary_sources=self._clean_section(secondary_lines),
        )

        return instruction

    @staticmethod
    def _clean_section(lines: list[str]) -> str:
        """Join lines and clean up whitespace."""
        text = "\n".join(lines)
        # Collapse multiple blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def _strip_date_line(text: str) -> str:
        """Remove the date/revision line from the end of instruction text."""
        lines = text.rstrip().split("\n")
        # Walk backwards to find and remove date lines
        while lines:
            last = lines[-1].strip()
            if not last:
                lines.pop()
                continue
            if _DATE_LINE_RE.match(last):
                lines.pop()
                # Also remove any preceding blank lines
                while lines and not lines[-1].strip():
                    lines.pop()
                break
            break
        return "\n".join(lines).rstrip()

    def to_statute_sections(
        self, instructions: list[CACIInstruction] | None = None
    ) -> list[StatuteSection]:
        """Convert parsed instructions to StatuteSection objects.

        If instructions is None, parses the PDF first.
        """
        if instructions is None:
            instructions = self.parse_instructions()

        sections: list[StatuteSection] = []
        for inst in instructions:
            sections.extend(inst.to_statute_sections())

        self.logger.info(
            "caci_sections_created",
            instructions=len(instructions),
            sections=len(sections),
        )
        return sections


# Monkey-patch StatuteSection to support heading_path override for CACI
_original_heading_path = StatuteSection.heading_path.fget


@property  # type: ignore[misc]
def _patched_heading_path(self: StatuteSection) -> str:
    override = getattr(self, "_heading_path_override", None)
    if override:
        return override
    return self.hierarchy.to_path_string()


StatuteSection.heading_path = _patched_heading_path  # type: ignore[assignment]
