"""Unpaid wages calculator.

Pure computation — no DB, no ML, no external services.
Users provide wage details and the calculator computes total damages
including unpaid wages, waiting time penalties, meal/rest break premiums,
and prejudgment interest under California law.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum


class EmploymentStatus(str, Enum):
    """Employment status for waiting-time penalty calculation."""

    still_employed = "still_employed"
    terminated = "terminated"  # Fired — final wages due immediately
    quit_with_notice = "quit_with_notice"  # 72+ hours notice — due on last day
    quit_without_notice = "quit_without_notice"  # No notice — due within 72 hours


@dataclass(frozen=True)
class WageBreakdownItem:
    """A single line item in the wage breakdown."""

    category: str  # "unpaid_wages", "waiting_time_penalty", "meal_break_premium", "rest_break_premium", "interest"
    label: str  # Human-readable name
    amount: str  # Formatted as string (from Decimal, 2 decimal places)
    legal_citation: str  # e.g. "Lab. Code \u00a7203"
    description: str  # Explanation of how calculated
    notes: str = ""


@dataclass(frozen=True)
class UnpaidWagesResult:
    """Complete unpaid wages calculation result."""

    items: list[WageBreakdownItem]
    total: str  # Sum of all items, formatted
    hourly_rate: str  # Echo back for display
    unpaid_hours: str  # Echo back


DISCLAIMER = (
    "This calculator provides general estimates based on California labor law. "
    "Actual amounts may vary depending on your specific employment agreement, "
    "applicable exemptions, collective bargaining agreements, overtime rates, "
    "and other factors. Waiting time penalties and interest calculations are "
    "simplified estimates. Consult a licensed California employment attorney "
    "for advice about your specific situation."
)


def _fmt(d: Decimal) -> str:
    """Format a Decimal to 2 decimal places."""
    return str(d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def calculate_unpaid_wages(
    *,
    hourly_rate: Decimal,
    unpaid_hours: Decimal,
    employment_status: EmploymentStatus = EmploymentStatus.still_employed,
    termination_date: date | None = None,
    final_wages_paid_date: date | None = None,
    missed_meal_breaks: int = 0,
    missed_rest_breaks: int = 0,
    unpaid_since: date | None = None,
    as_of: date | None = None,
) -> UnpaidWagesResult:
    """Calculate total unpaid wages and related damages.

    Args:
        hourly_rate: Employee's hourly pay rate.
        unpaid_hours: Total hours of unpaid work.
        employment_status: Current employment status.
        termination_date: Date employment ended (required if not still_employed).
        final_wages_paid_date: Date employer paid final wages (None = still unpaid).
        missed_meal_breaks: Number of missed meal breaks.
        missed_rest_breaks: Number of missed rest breaks.
        unpaid_since: Date wages have been owed since (for interest calculation).
        as_of: Reference date for calculations (defaults to today).

    Returns:
        UnpaidWagesResult with itemized breakdown and total.
    """
    if as_of is None:
        as_of = date.today()

    items: list[WageBreakdownItem] = []

    # 1. Unpaid wages
    unpaid_wages_amount = hourly_rate * unpaid_hours
    items.append(
        WageBreakdownItem(
            category="unpaid_wages",
            label="Unpaid Wages",
            amount=_fmt(unpaid_wages_amount),
            legal_citation="Lab. Code \u00a7\u00a7200\u2013204",
            description=f"{_fmt(unpaid_hours)} hours \u00d7 ${_fmt(hourly_rate)}/hr",
        )
    )

    # 2. Meal break premiums
    if missed_meal_breaks > 0:
        meal_amount = hourly_rate * missed_meal_breaks
        items.append(
            WageBreakdownItem(
                category="meal_break_premium",
                label="Meal Break Premiums",
                amount=_fmt(meal_amount),
                legal_citation="Lab. Code \u00a7226.7(c)",
                description=f"{missed_meal_breaks} missed break(s) \u00d7 ${_fmt(hourly_rate)}/hr (1 hour premium per violation)",
            )
        )

    # 3. Rest break premiums
    if missed_rest_breaks > 0:
        rest_amount = hourly_rate * missed_rest_breaks
        items.append(
            WageBreakdownItem(
                category="rest_break_premium",
                label="Rest Break Premiums",
                amount=_fmt(rest_amount),
                legal_citation="Lab. Code \u00a7226.7(c)",
                description=f"{missed_rest_breaks} missed break(s) \u00d7 ${_fmt(hourly_rate)}/hr (1 hour premium per violation)",
            )
        )

    # 4. Waiting time penalties (only if not still employed)
    if employment_status != EmploymentStatus.still_employed and termination_date is not None:
        daily_wage = hourly_rate * Decimal("8")

        # Determine when payment was due
        if employment_status == EmploymentStatus.quit_without_notice:
            payment_due_date = termination_date + timedelta(days=3)
        else:
            # terminated or quit_with_notice: due on last day
            payment_due_date = termination_date

        # Determine the comparison date
        paid_date = final_wages_paid_date if final_wages_paid_date is not None else as_of

        if paid_date > payment_due_date:
            days_late = min((paid_date - payment_due_date).days, 30)
            penalty_amount = daily_wage * days_late
            paid_note = ""
            if final_wages_paid_date is not None:
                paid_note = f"Final wages paid {final_wages_paid_date.isoformat()} ({days_late} day(s) late)"
            else:
                paid_note = f"Final wages still unpaid as of {as_of.isoformat()} ({days_late} day(s) late, capped at 30)"
            items.append(
                WageBreakdownItem(
                    category="waiting_time_penalty",
                    label="Waiting Time Penalty",
                    amount=_fmt(penalty_amount),
                    legal_citation="Lab. Code \u00a7203",
                    description=f"${_fmt(daily_wage)}/day \u00d7 {days_late} day(s)",
                    notes=paid_note,
                )
            )
        else:
            items.append(
                WageBreakdownItem(
                    category="waiting_time_penalty",
                    label="Waiting Time Penalty",
                    amount="0.00",
                    legal_citation="Lab. Code \u00a7203",
                    description="No penalty \u2014 final wages paid on time",
                    notes="Final wages paid on time",
                )
            )

    # 5. Prejudgment interest (only on unpaid wages, only if unpaid_since provided)
    if unpaid_since is not None and unpaid_wages_amount > 0:
        days = (as_of - unpaid_since).days
        if days > 0:
            interest = unpaid_wages_amount * Decimal("0.10") * Decimal(str(days)) / Decimal("365")
            items.append(
                WageBreakdownItem(
                    category="interest",
                    label="Prejudgment Interest",
                    amount=_fmt(interest),
                    legal_citation="Civ. Code \u00a73287(a); Cal. Const. Art. XV \u00a71",
                    description=f"10% per annum on ${_fmt(unpaid_wages_amount)} for {days} day(s)",
                )
            )

    # Calculate total
    total = sum(Decimal(item.amount) for item in items)

    return UnpaidWagesResult(
        items=items,
        total=_fmt(total),
        hourly_rate=_fmt(hourly_rate),
        unpaid_hours=_fmt(unpaid_hours),
    )
