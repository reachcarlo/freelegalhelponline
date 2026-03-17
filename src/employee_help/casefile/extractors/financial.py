"""FinancialExtractor — regex parser for dollar amounts in California litigation documents.

Extracts demand amounts, compensation figures, pay rates, damages amounts,
and other significant financial figures from the text of court filings
and employment documents.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class FinancialResult:
    """A financial amount extracted from document text."""

    label: str  # "Demand", "Compensation", "Hourly rate", etc.
    amount: float  # Dollar amount
    amount_type: str  # "demand", "compensation", "hourly_rate", "damages", "settlement", "pay", "penalty"


# ── Dollar amount pattern ────────────────────────────────────────────

# Matches "$1,234.56", "$450,000", "$36.06", etc.
_DOLLAR_RE = re.compile(r"\$\s*([\d,]+(?:\.\d{1,2})?)")

# ── Contextual patterns ──────────────────────────────────────────────

# Demand amounts: "Settlement Demand: $450,000" / "demand payment of $25,000"
_DEMAND_RE = re.compile(
    r"(?i)(?:(?:settlement\s+)?demand|demand\s+(?:for\s+)?payment)"
    r"(?:\s+(?:in\s+the\s+amount\s+of|of|for))?\s*:?\s*"
)

# Settlement amounts: "settled for $125,000" / "settlement amount: $125,000"
# Does NOT match "settlement demand" (that's a demand, not a settlement).
_SETTLEMENT_RE = re.compile(
    r"(?i)(?:settl(?:e[d]?)\s+for\s+"
    r"|settlement\s+amount\s*:?\s*"
    r"|settlement\s+(?:of|in\s+the\s+amount\s+of)\s+)"
)

# Salary / compensation: "base salary of $95,000" / "compensation: $95,000"
_COMPENSATION_RE = re.compile(
    r"(?i)(?:(?:base|annual|yearly)\s+)?(?:salary|compensation)\s*"
    r"(?:of|will\s+be|is|was)?\s*:?\s*"
)

# Hourly rate (pre-context): "hourly rate of $36.06"
_HOURLY_PRE_RE = re.compile(
    r"(?i)(?:hourly\s+rate|rate\s+of\s+pay)\s*(?:of|is|was)?\s*:?\s*"
)

# Hourly rate (post-context): "$36.06 per hour" / "$36.06/hr"
_HOURLY_POST_RE = re.compile(
    r"\$\s*([\d,]+(?:\.\d{1,2})?)\s*(?:per\s+hour|/\s*(?:hr|hour))",
    re.IGNORECASE,
)

# Gross pay
_GROSS_PAY_RE = re.compile(r"(?i)gross\s+pay\s*:?\s*")

# Net pay
_NET_PAY_RE = re.compile(r"(?i)net\s+pay\s*:?\s*")

# Damages: "general damages of $100,000" / "punitive damages: $50,000"
_DAMAGES_RE = re.compile(
    r"(?i)((?:general|special|punitive|compensatory|actual"
    r"|statutory|liquidated)\s+)?"
    r"damages\s*(?:of|in\s+the\s+amount\s+of|totaling)?\s*:?\s*"
)

# Unpaid wages / overtime / commissions
_UNPAID_RE = re.compile(
    r"(?i)unpaid\s+(?:wages|overtime|compensation|commissions?)\s*"
    r"(?:of|in\s+the\s+amount\s+of|totaling)?\s*:?\s*"
)

# Penalties
_PENALTY_RE = re.compile(
    r"(?i)(?:(?:waiting\s+time\s+)?penalt(?:y|ies))\s*"
    r"(?:of|totaling|in\s+the\s+amount\s+of)?\s*:?\s*"
)


def _parse_dollar_amount(text: str) -> float | None:
    """Parse the first dollar amount found in text. Returns None on failure."""
    m = _DOLLAR_RE.search(text)
    if m:
        raw = m.group(1).replace(",", "")
        try:
            val = float(raw)
            if val > 0:
                return val
        except ValueError:
            pass
    return None


def _find_amount_after(text: str, pos: int) -> float | None:
    """Find the first dollar amount in text starting at pos (within 100 chars)."""
    window = text[pos : pos + 100]
    return _parse_dollar_amount(window)


class FinancialExtractor:
    """Extracts financial amounts with contextual labels from litigation document text.

    Designed for Tier 1 (deterministic) extraction. Scans full text for
    dollar amount patterns surrounded by contextual cues (e.g., "demand",
    "salary", "damages") and returns labeled FinancialResult tuples.
    """

    def extract(self, text: str) -> list[FinancialResult]:
        """Extract labeled financial amounts from document text.

        Args:
            text: The full extracted text of the document.

        Returns:
            List of FinancialResult with label, amount, and amount_type.
            Deduplicated by (amount, amount_type) — keeps first occurrence.
        """
        if not text or not text.strip():
            return []

        results: list[FinancialResult] = []

        # Demand amounts
        self._extract_contextual(
            text, _DEMAND_RE, "Demand", "demand", results,
        )

        # Settlement amounts
        self._extract_contextual(
            text, _SETTLEMENT_RE, "Settlement", "settlement", results,
        )

        # Salary / compensation
        self._extract_contextual(
            text, _COMPENSATION_RE, "Compensation", "compensation", results,
        )

        # Hourly rates (pre-context: "hourly rate of $X")
        self._extract_contextual(
            text, _HOURLY_PRE_RE, "Hourly rate", "hourly_rate", results,
        )

        # Hourly rates (post-context: "$X per hour")
        self._extract_hourly_post(text, results)

        # Gross pay
        self._extract_contextual(
            text, _GROSS_PAY_RE, "Gross pay", "pay", results,
        )

        # Net pay
        self._extract_contextual(
            text, _NET_PAY_RE, "Net pay", "pay", results,
        )

        # Damages (with optional prefix like "punitive", "general")
        self._extract_damages(text, results)

        # Unpaid wages / overtime
        self._extract_contextual(
            text, _UNPAID_RE, "Unpaid wages", "pay", results,
        )

        # Penalties
        self._extract_contextual(
            text, _PENALTY_RE, "Penalty", "penalty", results,
        )

        return self._deduplicate(results)

    @staticmethod
    def _extract_contextual(
        text: str,
        context_re: re.Pattern[str],
        label: str,
        amount_type: str,
        results: list[FinancialResult],
    ) -> None:
        """Find dollar amounts that appear after a contextual pattern match."""
        for m in context_re.finditer(text):
            amount = _find_amount_after(text, m.start())
            if amount is not None:
                results.append(
                    FinancialResult(
                        label=label, amount=amount, amount_type=amount_type,
                    )
                )

    @staticmethod
    def _extract_hourly_post(text: str, results: list[FinancialResult]) -> None:
        """Extract hourly rates from post-context patterns like '$36.06 per hour'."""
        for m in _HOURLY_POST_RE.finditer(text):
            raw = m.group(1).replace(",", "")
            try:
                val = float(raw)
                if val > 0:
                    results.append(
                        FinancialResult(
                            label="Hourly rate",
                            amount=val,
                            amount_type="hourly_rate",
                        )
                    )
            except ValueError:
                pass

    @staticmethod
    def _extract_damages(text: str, results: list[FinancialResult]) -> None:
        """Extract damages amounts, capturing the damage type prefix."""
        for m in _DAMAGES_RE.finditer(text):
            amount = _find_amount_after(text, m.start())
            if amount is not None:
                prefix = m.group(1)
                if prefix:
                    label = f"{prefix.strip().capitalize()} damages"
                else:
                    label = "Damages"
                results.append(
                    FinancialResult(
                        label=label, amount=amount, amount_type="damages",
                    )
                )

    @staticmethod
    def _deduplicate(results: list[FinancialResult]) -> list[FinancialResult]:
        """Remove duplicates by (amount, amount_type), keeping first occurrence."""
        seen: set[tuple[float, str]] = set()
        deduped: list[FinancialResult] = []
        for r in results:
            key = (r.amount, r.amount_type)
            if key not in seen:
                seen.add(key)
                deduped.append(r)
        return deduped
