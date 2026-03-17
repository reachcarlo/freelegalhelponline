"""EmploymentExtractor — regex/heuristic parser for employment details.

Extracts employer name, position/title, department, and compensation
from pay stubs, offer letters, and complaint allegations in California
litigation documents.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class EmploymentResult:
    """An employment detail extracted from document text."""

    field: str  # "employer", "position", "department", "compensation"
    value: str  # Human-readable display value
    # Structured compensation data (only populated when field="compensation")
    compensation_rate: float | None = None
    compensation_type: str | None = None  # "salary", "hourly"
    pay_period: str | None = None  # "annual", "monthly", "biweekly"


# ── Employer patterns ────────────────────────────────────────────────

# Labeled: "Employer: Acme Corp" / "Company Name: Acme Corp"
_EMPLOYER_LABEL_RE = re.compile(
    r"(?i)(?:employer|company(?:\s+name)?)\s*:\s*(.+?)(?:\s*\n|$)",
)

# Contextual: "employed by/at/with X" / "worked for/at X" / "hired by X"
_EMPLOYER_CONTEXT_RE = re.compile(
    r"(?i)\b(?:employed\s+(?:by|at|with)"
    r"|work(?:ed|ing|s)?\s+(?:for|at)"
    r"|hired\s+by"
    r"|employment\s+(?:with|at))"
    r"\s+(.+?)"
    r"(?=\s+(?:as|in|from|on|since|for|during|where"
    r"|began|ended|was|is|has|had|will|until|commenced)\s|\s*[,.]|\s*\n|$)",
)

# Compound: "employed/hired by X as (a/an) Y" — captures both employer and position
_EMPLOYED_BY_AS_RE = re.compile(
    r"(?i)\b(?:employed|hired)\s+(?:by|at|with)\s+"
    r"(.+?)"
    r"\s+as\s+(?:an?\s+)?"
    r"(.+?)"
    r"(?=\s+(?:in|at|for|with|from|on|since)\s|\s*[,.]|\s*\n|$)",
)

# ── Position/title patterns ──────────────────────────────────────────

# Labeled: "Position: Analyst" / "Job Title: Senior Analyst"
_POSITION_LABEL_RE = re.compile(
    r"(?i)(?:position|job\s+title|title|role)\s*:\s*(.+?)(?:\s*\n|$)",
)

# "position of X" / "role of X"
_POSITION_OF_RE = re.compile(
    r"(?i)\b(?:position|role)\s+of\s+(?:an?\s+)?"
    r"(.+?)"
    r"(?=\s+(?:in|at|for|with|from|on|since)\s|\s*[,.]|\s*\n|$)",
)

# "employed/worked/hired as X"
_EMPLOYED_AS_RE = re.compile(
    r"(?i)\b(?:employed|work(?:ed|ing|s)?|hired)\s+as\s+(?:an?\s+)?"
    r"(.+?)"
    r"(?=\s+(?:in|at|for|with|from|on|since|by)\s|\s*[,.]|\s*\n|$)",
)

# ── Department patterns ──────────────────────────────────────────────

# Labeled: "Department: Finance" / "Dept: HR"
_DEPARTMENT_LABEL_RE = re.compile(
    r"(?i)(?:department|dept\.?)\s*:\s*(.+?)(?:\s*\n|$)",
)

# Contextual: "in the Finance department"
_DEPARTMENT_CONTEXT_RE = re.compile(
    r"(?i)\bin\s+the\s+(.+?)\s+department\b",
)

# ── Compensation patterns ────────────────────────────────────────────

# Salary: "salary of/will be/is/was $X" or "base salary: $X"
_SALARY_RE = re.compile(
    r"(?i)\b(?:(?:base|annual|yearly)\s+)?salary\s*"
    r"(?:of|will\s+be|is|was)?\s*:?\s*"
    r"\$\s*([\d,]+(?:\.\d{1,2})?)",
)

# Annual/yearly compensation: "annual compensation: $X"
_ANNUAL_COMP_RE = re.compile(
    r"(?i)\b(?:annual|yearly)\s+compensation\s*"
    r"(?:of|will\s+be|is|was)?\s*:?\s*"
    r"\$\s*([\d,]+(?:\.\d{1,2})?)",
)

# Hourly rate (pre-context): "hourly rate of $X"
_HOURLY_PRE_RE = re.compile(
    r"(?i)\bhourly\s+rate\s*(?:of|is|was)?\s*:?\s*"
    r"\$\s*([\d,]+(?:\.\d{1,2})?)",
)

# Hourly rate (post-context): "$X per hour" / "$X/hr"
_HOURLY_POST_RE = re.compile(
    r"(?i)\$\s*([\d,]+(?:\.\d{1,2})?)\s*(?:per\s+hour|/\s*(?:hr|hour))",
)

# Pay rate: "Pay Rate: $X" (type inferred from amount)
_PAY_RATE_RE = re.compile(
    r"(?i)\bpay\s+rate\s*:\s*\$\s*([\d,]+(?:\.\d{1,2})?)",
)


def _parse_dollar(raw: str) -> float | None:
    """Parse a dollar amount string (without $) into a float."""
    cleaned = raw.replace(",", "")
    try:
        val = float(cleaned)
        return val if val > 0 else None
    except ValueError:
        return None


class EmploymentExtractor:
    """Extracts employment details from litigation document text.

    Designed for Tier 1 (deterministic) extraction. Scans text for
    employer name, position/title, department, and compensation
    commonly found in pay stubs, offer letters, and complaint allegations.
    """

    def extract(self, text: str) -> list[EmploymentResult]:
        """Extract employment details from document text.

        Args:
            text: The full extracted text of the document.

        Returns:
            List of EmploymentResult with field, value, and optional
            structured compensation data. Deduplicated by (field, value).
        """
        if not text or not text.strip():
            return []

        results: list[EmploymentResult] = []

        self._extract_employers(text, results)
        self._extract_employed_by_as(text, results)
        self._extract_positions(text, results)
        self._extract_departments(text, results)
        self._extract_compensation(text, results)

        return self._deduplicate(results)

    @staticmethod
    def _extract_employers(text: str, results: list[EmploymentResult]) -> None:
        """Extract employer names from labeled and contextual patterns."""
        for m in _EMPLOYER_LABEL_RE.finditer(text):
            name = m.group(1).strip()
            if name:
                results.append(EmploymentResult(field="employer", value=name))

        for m in _EMPLOYER_CONTEXT_RE.finditer(text):
            name = m.group(1).strip()
            if name:
                results.append(EmploymentResult(field="employer", value=name))

    @staticmethod
    def _extract_employed_by_as(
        text: str, results: list[EmploymentResult],
    ) -> None:
        """Extract employer + position from 'employed/hired by X as Y' patterns."""
        for m in _EMPLOYED_BY_AS_RE.finditer(text):
            employer = m.group(1).strip()
            position = m.group(2).strip()
            if employer:
                results.append(EmploymentResult(field="employer", value=employer))
            if position:
                results.append(EmploymentResult(field="position", value=position))

    @staticmethod
    def _extract_positions(text: str, results: list[EmploymentResult]) -> None:
        """Extract position/title from labeled and contextual patterns."""
        for m in _POSITION_LABEL_RE.finditer(text):
            pos = m.group(1).strip()
            if pos:
                results.append(EmploymentResult(field="position", value=pos))

        for m in _POSITION_OF_RE.finditer(text):
            pos = m.group(1).strip()
            if pos:
                results.append(EmploymentResult(field="position", value=pos))

        for m in _EMPLOYED_AS_RE.finditer(text):
            pos = m.group(1).strip()
            if pos:
                results.append(EmploymentResult(field="position", value=pos))

    @staticmethod
    def _extract_departments(text: str, results: list[EmploymentResult]) -> None:
        """Extract department from labeled and contextual patterns."""
        for m in _DEPARTMENT_LABEL_RE.finditer(text):
            dept = m.group(1).strip()
            if dept:
                results.append(EmploymentResult(field="department", value=dept))

        for m in _DEPARTMENT_CONTEXT_RE.finditer(text):
            dept = m.group(1).strip()
            if dept:
                results.append(EmploymentResult(field="department", value=dept))

    @staticmethod
    def _extract_compensation(text: str, results: list[EmploymentResult]) -> None:
        """Extract compensation details from text."""
        # Salary
        for m in _SALARY_RE.finditer(text):
            rate = _parse_dollar(m.group(1))
            if rate is not None:
                results.append(EmploymentResult(
                    field="compensation",
                    value=f"${rate:,.2f} salary",
                    compensation_rate=rate,
                    compensation_type="salary",
                    pay_period="annual",
                ))

        # Annual compensation
        for m in _ANNUAL_COMP_RE.finditer(text):
            rate = _parse_dollar(m.group(1))
            if rate is not None:
                results.append(EmploymentResult(
                    field="compensation",
                    value=f"${rate:,.2f} annual",
                    compensation_rate=rate,
                    compensation_type="salary",
                    pay_period="annual",
                ))

        # Hourly rate (pre-context)
        for m in _HOURLY_PRE_RE.finditer(text):
            rate = _parse_dollar(m.group(1))
            if rate is not None:
                results.append(EmploymentResult(
                    field="compensation",
                    value=f"${rate:,.2f}/hr",
                    compensation_rate=rate,
                    compensation_type="hourly",
                ))

        # Hourly rate (post-context)
        for m in _HOURLY_POST_RE.finditer(text):
            rate = _parse_dollar(m.group(1))
            if rate is not None:
                results.append(EmploymentResult(
                    field="compensation",
                    value=f"${rate:,.2f}/hr",
                    compensation_rate=rate,
                    compensation_type="hourly",
                ))

        # Pay rate (infer type from amount: < $200 likely hourly)
        for m in _PAY_RATE_RE.finditer(text):
            rate = _parse_dollar(m.group(1))
            if rate is not None:
                comp_type = "hourly" if rate < 200 else "salary"
                value = f"${rate:,.2f}/hr" if comp_type == "hourly" else f"${rate:,.2f} salary"
                results.append(EmploymentResult(
                    field="compensation",
                    value=value,
                    compensation_rate=rate,
                    compensation_type=comp_type,
                ))

    @staticmethod
    def _deduplicate(results: list[EmploymentResult]) -> list[EmploymentResult]:
        """Remove duplicates by (field, value), keeping first occurrence."""
        seen: set[tuple[str, str]] = set()
        deduped: list[EmploymentResult] = []
        for r in results:
            key = (r.field, r.value)
            if key not in seen:
                seen.add(key)
                deduped.append(r)
        return deduped
