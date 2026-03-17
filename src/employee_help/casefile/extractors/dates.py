"""DateExtractor — regex parser for dates in California litigation documents.

Extracts filing dates, employment dates, trial dates, discovery cutoffs,
and other significant dates from the text of court filings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class DateResult:
    """A date extracted from document text."""

    label: str  # "Complaint filed", "Employment start", etc.
    date: str  # ISO format YYYY-MM-DD
    date_type: str  # "filing", "employment", "trial", "discovery_cutoff", "deadline", "event"


# ── Month names ──────────────────────────────────────────────────────

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9,
    "oct": 10, "nov": 11, "dec": 12,
}

# ── Date format patterns ─────────────────────────────────────────────

# "January 15, 2026" / "Jan 15, 2026" / "Jan. 15, 2026"
_MONTH_NAME_RE = re.compile(
    r"(?i)\b((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May"
    r"|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?"
    r"|Nov(?:ember)?|Dec(?:ember)?)\.?)\s+(\d{1,2}),?\s+(\d{4})\b"
)

# "01/15/2026" or "1/15/2026"
_SLASH_DATE_RE = re.compile(
    r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b"
)

# "2026-01-15" (ISO)
_ISO_DATE_RE = re.compile(
    r"\b(\d{4})-(\d{2})-(\d{2})\b"
)

# ── Contextual patterns ──────────────────────────────────────────────
# Each pattern captures surrounding context to label the date.

# Filing dates: "Filed: January 15, 2026" or "Filing Date: ..."
_FILING_RE = re.compile(
    r"(?i)(?:filed|filing\s+date)\s*:?\s*"
    r"((?:(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May"
    r"|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?"
    r"|Nov(?:ember)?|Dec(?:ember)?)\.?\s+\d{1,2},?\s+\d{4})"
    r"|\d{1,2}/\d{1,2}/\d{4}"
    r"|(\d{4}-\d{2}-\d{2}))"
)

# Trial date: "Trial date: ..." or "set for trial on ..."
_TRIAL_RE = re.compile(
    r"(?i)(?:trial\s+(?:date|set|scheduled))\s*:?\s*(?:for\s+|on\s+)?"
)

# Discovery cutoff: "Discovery cutoff: ..." or "Discovery cut-off ..."
_DISCOVERY_CUTOFF_RE = re.compile(
    r"(?i)(?:discovery\s+(?:cut-?off|deadline|closes?))\s*:?\s*"
)

# Employment start: "start date ..." / "hired on ..." / "commenced employment on ..."
_EMPLOYMENT_START_RE = re.compile(
    r"(?i)(?:start\s+date\s*(?:will\s+be|is|was|of)?\s*:?\s*"
    r"|(?:hired|commenced\s+employment)\s+(?:on\s+)?)"
)

# Employment end: "terminated effective ..." / "last day of employment ..."
# "termination date ..." / "separation date ..."
_EMPLOYMENT_END_RE = re.compile(
    r"(?i)(?:terminat(?:ed|ion)\s+(?:effective|date)\s*:?\s*"
    r"|last\s+day\s+of\s+employment\s*(?:will\s+be|is|was)?\s*:?\s*"
    r"|separation\s+date\s*:?\s*"
    r"|effective\s+(?:date\s+of\s+)?termination\s*:?\s*)"
)

# Deadline: "deadline ..." / "due date ..." / "due by ..."
_DEADLINE_RE = re.compile(
    r"(?i)(?:(?:response\s+)?deadline\s*:?\s*"
    r"|due\s+(?:date\s*:?\s*|by\s+|on\s+))"
)

# Pay period: "Pay Period: 01/01/2025 - 01/15/2025"
_PAY_PERIOD_RE = re.compile(
    r"(?i)pay\s+period\s*:?\s*"
    r"(\d{1,2}/\d{1,2}/\d{4})\s*[-–—]\s*(\d{1,2}/\d{1,2}/\d{4})"
)

# Check date: "Check Date: 01/20/2025"
_CHECK_DATE_RE = re.compile(
    r"(?i)check\s+date\s*:?\s*"
)

# Review period: "Review Period: January 2024 - December 2024"
_REVIEW_PERIOD_RE = re.compile(
    r"(?i)review\s+period\s*:?\s*"
    r"((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May"
    r"|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?"
    r"|Nov(?:ember)?|Dec(?:ember)?)\.?)\s+(\d{4})\s*[-–—]\s*"
    r"((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May"
    r"|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?"
    r"|Nov(?:ember)?|Dec(?:ember)?)\.?)\s+(\d{4})"
)


def _parse_month_day_year(text: str) -> str | None:
    """Try to parse a date string into ISO format. Returns None on failure."""
    # Try "Month DD, YYYY"
    m = _MONTH_NAME_RE.search(text)
    if m:
        month_str = m.group(1).rstrip(".").lower()
        month = _MONTHS.get(month_str)
        if month:
            day = int(m.group(2))
            year = int(m.group(3))
            if 1 <= day <= 31 and 1900 <= year <= 2100:
                return f"{year:04d}-{month:02d}-{day:02d}"

    # Try "MM/DD/YYYY"
    m = _SLASH_DATE_RE.search(text)
    if m:
        month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= month <= 12 and 1 <= day <= 31 and 1900 <= year <= 2100:
            return f"{year:04d}-{month:02d}-{day:02d}"

    # Try "YYYY-MM-DD"
    m = _ISO_DATE_RE.search(text)
    if m:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= month <= 12 and 1 <= day <= 31 and 1900 <= year <= 2100:
            return f"{year:04d}-{month:02d}-{day:02d}"

    return None


def _find_date_after(text: str, pos: int) -> str | None:
    """Find the first parseable date in text starting at pos (within 100 chars)."""
    window = text[pos : pos + 100]
    return _parse_month_day_year(window)


class DateExtractor:
    """Extracts dates with contextual labels from litigation document text.

    Designed for Tier 1 (deterministic) extraction. Scans full text for
    date patterns surrounded by contextual cues (e.g., "filed", "terminated",
    "trial date") and returns labeled DateResult tuples.
    """

    def extract(self, text: str) -> list[DateResult]:
        """Extract labeled dates from document text.

        Args:
            text: The full extracted text of the document.

        Returns:
            List of DateResult with label, ISO date, and date_type.
            Deduplicated by (date, date_type) — keeps first occurrence.
        """
        if not text or not text.strip():
            return []

        results: list[DateResult] = []

        # Filing dates
        self._extract_contextual(
            text, _FILING_RE, "Filed", "filing", results,
        )

        # Trial dates
        self._extract_contextual(
            text, _TRIAL_RE, "Trial date", "trial", results,
        )

        # Discovery cutoff
        self._extract_contextual(
            text, _DISCOVERY_CUTOFF_RE, "Discovery cutoff", "discovery_cutoff",
            results,
        )

        # Employment start dates
        self._extract_contextual(
            text, _EMPLOYMENT_START_RE, "Employment start", "employment",
            results,
        )

        # Employment end dates
        self._extract_contextual(
            text, _EMPLOYMENT_END_RE, "Employment end", "employment",
            results,
        )

        # Deadlines
        self._extract_contextual(
            text, _DEADLINE_RE, "Deadline", "deadline", results,
        )

        # Check dates
        self._extract_contextual(
            text, _CHECK_DATE_RE, "Check date", "event", results,
        )

        # Pay periods (special: two dates)
        self._extract_pay_periods(text, results)

        # Review periods (special: month-year range)
        self._extract_review_periods(text, results)

        return self._deduplicate(results)

    @staticmethod
    def _extract_contextual(
        text: str,
        context_re: re.Pattern[str],
        label: str,
        date_type: str,
        results: list[DateResult],
    ) -> None:
        """Find dates that appear after a contextual pattern match."""
        for m in context_re.finditer(text):
            date = _find_date_after(text, m.start())
            if date:
                results.append(DateResult(label=label, date=date, date_type=date_type))

    @staticmethod
    def _extract_pay_periods(text: str, results: list[DateResult]) -> None:
        """Extract pay period date ranges."""
        for m in _PAY_PERIOD_RE.finditer(text):
            start = _parse_month_day_year(m.group(1))
            end = _parse_month_day_year(m.group(2))
            if start:
                results.append(
                    DateResult(label="Pay period start", date=start, date_type="event")
                )
            if end:
                results.append(
                    DateResult(label="Pay period end", date=end, date_type="event")
                )

    @staticmethod
    def _extract_review_periods(text: str, results: list[DateResult]) -> None:
        """Extract review period date ranges (Month YYYY - Month YYYY)."""
        for m in _REVIEW_PERIOD_RE.finditer(text):
            start_month = _MONTHS.get(m.group(1).rstrip(".").lower())
            start_year = int(m.group(2))
            end_month = _MONTHS.get(m.group(3).rstrip(".").lower())
            end_year = int(m.group(4))
            if start_month and end_month:
                results.append(
                    DateResult(
                        label="Review period start",
                        date=f"{start_year:04d}-{start_month:02d}-01",
                        date_type="event",
                    )
                )
                # End of review period: last day of the month (approximate with 28)
                results.append(
                    DateResult(
                        label="Review period end",
                        date=f"{end_year:04d}-{end_month:02d}-28",
                        date_type="event",
                    )
                )

    @staticmethod
    def _deduplicate(results: list[DateResult]) -> list[DateResult]:
        """Remove duplicates by (date, date_type), keeping first occurrence."""
        seen: set[tuple[str, str]] = set()
        deduped: list[DateResult] = []
        for r in results:
            key = (r.date, r.date_type)
            if key not in seen:
                seen.add(key)
                deduped.append(r)
        return deduped
