"""CaptionExtractor — regex parser for California Superior Court caption blocks.

Extracts parties, case number, court info, and attorney blocks from the
caption section of California court filings (complaints, answers, motions).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CaptionParty:
    """A party extracted from a caption block."""

    name: str
    role: str  # "plaintiff", "defendant"
    party_type: str  # "individual", "entity", "doe"
    count: int | None = None  # for doe defendants


@dataclass(frozen=True)
class CaptionAttorney:
    """An attorney extracted from an attorney block."""

    name: str
    side: str  # "plaintiff", "defendant"
    bar_number: str | None = None
    firm: str | None = None
    email: str | None = None


@dataclass(frozen=True)
class CaptionResult:
    """All data extracted from a caption block."""

    parties: list[CaptionParty] = field(default_factory=list)
    case_number: str | None = None
    court: str | None = None
    county: str | None = None
    department: str | None = None
    judge: str | None = None
    attorneys: list[CaptionAttorney] = field(default_factory=list)


# ── Court & county ────────────────────────────────────────────────────

_COURT_RE = re.compile(
    r"(?i)(?:IN\s+THE\s+)?"
    r"(SUPERIOR\s+COURT\s+OF\s+(?:THE\s+STATE\s+OF\s+)?CALIFORNIA)"
    r"(?:\s*[,\n]\s*|\s+)"
    r"(?:(?:FOR\s+(?:THE\s+)?)?COUNTY\s+OF\s+([A-Z][A-Za-z\s]+?))"
    r"\s*(?:\n|$|(?=\s{2}))",
)

# ── Case number ───────────────────────────────────────────────────────

_CASE_NO_RE = re.compile(
    r"(?i)(?:Case\s+No\.?|Case\s+Number|No\.)\s*:?\s*"
    r"([A-Z0-9][\w\-/]+)",
)

# ── Department / judge ────────────────────────────────────────────────

_DEPT_RE = re.compile(
    r"(?i)(?:Dept\.?|Department)\s*:?\s*(\S+)",
)

_JUDGE_RE = re.compile(
    r"(?i)(?:Hon\.?\s+|Judge\s+)"
    r"([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)",
)

# ── Parties ───────────────────────────────────────────────────────────

# Doe defendant pattern: "DOES 1 through 50" or "DOE 1-100"
_DOE_RE = re.compile(
    r"(?i)\bDO[E]?S?\s+(\d+)\s+(?:through|thru|to|-)\s+(\d+)",
)

# "v." or "vs." separator — captures parties on either side
# Plaintiff block: non-greedy lines immediately before "Plaintiff,"
# Defendant block: lines between "v./vs." and "Defendant,"
_VS_RE = re.compile(
    r"(?:^|\n)\s*"
    r"((?:[^\n]+\n)*?[^\n]+?)"  # plaintiff name(s) — non-greedy, no DOTALL
    r"\s*,?\s*\n\s*(?:Plaintiff|Petitioner)s?\s*"
    r"[,.]?\s*\n"
    r"\s*v[s]?\.?\s*\n"
    r"\s*"
    r"((?:[^\n]+\n)*?[^\n]+?)"  # defendant name(s)
    r"\s*,?\s*\n\s*(?:Defendant|Respondent)s?\s*[,.]?",
)

# Entity indicators — suggest a party is an organization, not a person
_ENTITY_INDICATORS = re.compile(
    r"(?i)\b(?:inc\.?|corp(?:oration)?\.?|co\.?|ltd\.?|llc|llp|l\.p\."
    r"|company|associates|group|partners|enterprises|holdings"
    r"|a\s+(?:California|Delaware|Nevada|New\s+York|Florida)\s+"
    r"(?:corporation|limited\s+liability|partnership|entity))\b",
)

# ── Attorney block ────────────────────────────────────────────────────

_BAR_NO_RE = re.compile(
    r"(?i)(?:State\s+Bar\s+(?:No\.?|Number)|SBN|Bar\s+No\.?)\s*:?\s*(\d{4,7})",
)

_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
)

# Attorney name line: "NAME (SBN 123456)" or "NAME, Esq." or just a name
# followed by bar number nearby
_ATTORNEY_NAME_RE = re.compile(
    r"(?i)^([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)"
    r"(?:\s*,?\s*(?:Esq\.?|Attorney|Counsel))?",
    re.MULTILINE,
)

# "Attorney(s) for Plaintiff/Defendant"
_ATTORNEY_FOR_RE = re.compile(
    r"(?i)Attorneys?\s+for\s+(Plaintiff|Defendant|Petitioner|Respondent)s?",
)

# Law firm line: name ending with entity indicator or "Law" keywords
_FIRM_RE = re.compile(
    r"(?i)^([A-Z][A-Za-z\s&,.']+?"
    r"(?:LLP|LLC|PC|P\.C\.|APC|A\.P\.C\.|Law\s+(?:Firm|Office|Group|Corporation)"
    r"|Associates|& Associates|Attorneys))\s*$",
    re.MULTILINE,
)


class CaptionExtractor:
    """Extracts structured data from California Superior Court caption blocks.

    Designed for Tier 1 (deterministic) extraction. Parses the first ~3000
    characters of a court filing to extract parties, case number, court info,
    and attorney blocks using regex patterns.
    """

    def extract(self, text: str) -> CaptionResult:
        """Extract caption data from document text.

        Args:
            text: The full extracted text of the document.

        Returns:
            CaptionResult with all extracted fields. Fields that cannot
            be found are None or empty lists.
        """
        if not text or not text.strip():
            return CaptionResult()

        head = text[:3000]

        court, county = self._extract_court(head)
        case_number = self._extract_case_number(head)
        department = self._extract_department(head)
        judge = self._extract_judge(head)
        parties = self._extract_parties(head)
        attorneys = self._extract_attorneys(text[:5000])

        return CaptionResult(
            parties=parties,
            case_number=case_number,
            court=court,
            county=county,
            department=department,
            judge=judge,
            attorneys=attorneys,
        )

    @staticmethod
    def _extract_court(head: str) -> tuple[str | None, str | None]:
        """Extract court name and county."""
        m = _COURT_RE.search(head)
        if not m:
            return None, None
        court = re.sub(r"\s+", " ", m.group(1)).strip()
        county = m.group(2).strip() if m.group(2) else None
        return court, county

    @staticmethod
    def _extract_case_number(head: str) -> str | None:
        """Extract case number."""
        m = _CASE_NO_RE.search(head)
        return m.group(1).strip() if m else None

    @staticmethod
    def _extract_department(head: str) -> str | None:
        """Extract department number."""
        m = _DEPT_RE.search(head)
        return m.group(1).strip() if m else None

    @staticmethod
    def _extract_judge(head: str) -> str | None:
        """Extract judge name."""
        m = _JUDGE_RE.search(head)
        return m.group(1).strip() if m else None

    def _extract_parties(self, head: str) -> list[CaptionParty]:
        """Extract plaintiff(s) and defendant(s) from caption block."""
        m = _VS_RE.search(head)
        if not m:
            return []

        plaintiff_block = m.group(1)
        defendant_block = m.group(2)

        parties: list[CaptionParty] = []

        # Parse plaintiffs
        for name in self._split_party_names(plaintiff_block):
            parties.append(
                CaptionParty(
                    name=name,
                    role="plaintiff",
                    party_type=self._classify_party_type(name),
                )
            )

        # Parse defendants
        for name in self._split_party_names(defendant_block):
            doe = _DOE_RE.search(name)
            if doe:
                start, end = int(doe.group(1)), int(doe.group(2))
                parties.append(
                    CaptionParty(
                        name=name.strip(),
                        role="defendant",
                        party_type="doe",
                        count=end - start + 1,
                    )
                )
            else:
                parties.append(
                    CaptionParty(
                        name=name,
                        role="defendant",
                        party_type=self._classify_party_type(name),
                    )
                )

        return parties

    @staticmethod
    def _split_party_names(block: str) -> list[str]:
        """Split a party block into individual names.

        Handles "ALICE JONES and BOB SMITH" or semicolon/newline separated.
        """
        # Normalize whitespace
        block = re.sub(r"\s+", " ", block).strip()

        # Remove trailing descriptors like "an individual" or "a California corporation"
        # but keep them for entity classification
        # Split on semicolons, " and " (when between names), or newlines
        parts = re.split(r"\s*;\s*|\s+and\s+", block)

        names = []
        for part in parts:
            part = part.strip().rstrip(",").strip()
            if not part:
                continue
            # Clean up trailing descriptors for the name but keep raw for classification
            names.append(part)

        return names

    @staticmethod
    def _classify_party_type(name: str) -> str:
        """Classify a party as individual, entity, or doe."""
        if _DOE_RE.search(name):
            return "doe"
        if _ENTITY_INDICATORS.search(name):
            return "entity"
        return "individual"

    def _extract_attorneys(self, text: str) -> list[CaptionAttorney]:
        """Extract attorney information from attorney blocks."""
        attorneys: list[CaptionAttorney] = []

        # Find "Attorney(s) for Plaintiff/Defendant" sections
        for m in _ATTORNEY_FOR_RE.finditer(text):
            side_raw = m.group(1).lower()
            side = "plaintiff" if side_raw in ("plaintiff", "petitioner") else "defendant"

            # Look at the block before this marker (attorney info is usually above)
            block_start = max(0, m.start() - 500)
            block = text[block_start : m.end() + 200]

            atty = self._parse_attorney_block(block, side)
            if atty:
                attorneys.append(atty)

        return attorneys

    def _parse_attorney_block(
        self, block: str, side: str
    ) -> CaptionAttorney | None:
        """Parse a single attorney block for name, bar number, firm, email."""
        bar_match = _BAR_NO_RE.search(block)
        bar_number = bar_match.group(1) if bar_match else None

        email_match = _EMAIL_RE.search(block)
        email = email_match.group(0) if email_match else None

        firm_match = _FIRM_RE.search(block)
        firm = firm_match.group(1).strip() if firm_match else None

        # Find attorney name — look for name patterns
        name = self._find_attorney_name(block, bar_number, firm)
        if not name:
            return None

        return CaptionAttorney(
            name=name,
            side=side,
            bar_number=bar_number,
            firm=firm,
            email=email,
        )

    @staticmethod
    def _find_attorney_name(
        block: str, bar_number: str | None, firm: str | None
    ) -> str | None:
        """Find the attorney name in a block, avoiding firm names."""
        for m in _ATTORNEY_NAME_RE.finditer(block):
            candidate = m.group(1).strip()
            # Skip if the candidate matches the firm name
            if firm and candidate.lower() in firm.lower():
                continue
            # Skip common false positives
            if candidate.lower() in (
                "superior court",
                "state bar",
                "county of",
                "case no",
            ):
                continue
            return candidate
        return None
