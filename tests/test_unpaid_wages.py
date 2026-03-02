"""Unit tests for the unpaid wages calculator."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from employee_help.tools.unpaid_wages import (
    DISCLAIMER,
    EmploymentStatus,
    UnpaidWagesResult,
    WageBreakdownItem,
    calculate_unpaid_wages,
)


# ── Basic unpaid wages ──────────────────────────────────────────────


def test_basic_unpaid_wages():
    result = calculate_unpaid_wages(
        hourly_rate=Decimal("25.00"),
        unpaid_hours=Decimal("40"),
    )
    assert result.items[0].category == "unpaid_wages"
    assert result.items[0].amount == "1000.00"
    assert result.total == "1000.00"


def test_fractional_hours():
    result = calculate_unpaid_wages(
        hourly_rate=Decimal("20.00"),
        unpaid_hours=Decimal("10.5"),
    )
    assert result.items[0].amount == "210.00"


def test_zero_hours():
    result = calculate_unpaid_wages(
        hourly_rate=Decimal("25.00"),
        unpaid_hours=Decimal("0"),
    )
    assert result.items[0].amount == "0.00"
    assert result.total == "0.00"


def test_very_small_rate():
    result = calculate_unpaid_wages(
        hourly_rate=Decimal("0.01"),
        unpaid_hours=Decimal("100"),
    )
    assert result.items[0].amount == "1.00"


def test_large_hours():
    result = calculate_unpaid_wages(
        hourly_rate=Decimal("50.00"),
        unpaid_hours=Decimal("5000"),
    )
    assert result.items[0].amount == "250000.00"


def test_echoed_rate_and_hours():
    result = calculate_unpaid_wages(
        hourly_rate=Decimal("25.50"),
        unpaid_hours=Decimal("40"),
    )
    assert result.hourly_rate == "25.50"
    assert result.unpaid_hours == "40.00"


# ── Meal break premiums ────────────────────────────────────────────


def test_meal_break_premiums():
    result = calculate_unpaid_wages(
        hourly_rate=Decimal("20.00"),
        unpaid_hours=Decimal("0"),
        missed_meal_breaks=5,
    )
    meal_items = [i for i in result.items if i.category == "meal_break_premium"]
    assert len(meal_items) == 1
    assert meal_items[0].amount == "100.00"
    assert "226.7" in meal_items[0].legal_citation


def test_no_meal_breaks_no_item():
    result = calculate_unpaid_wages(
        hourly_rate=Decimal("20.00"),
        unpaid_hours=Decimal("8"),
        missed_meal_breaks=0,
    )
    meal_items = [i for i in result.items if i.category == "meal_break_premium"]
    assert len(meal_items) == 0


# ── Rest break premiums ────────────────────────────────────────────


def test_rest_break_premiums():
    result = calculate_unpaid_wages(
        hourly_rate=Decimal("30.00"),
        unpaid_hours=Decimal("0"),
        missed_rest_breaks=3,
    )
    rest_items = [i for i in result.items if i.category == "rest_break_premium"]
    assert len(rest_items) == 1
    assert rest_items[0].amount == "90.00"
    assert "226.7" in rest_items[0].legal_citation


def test_no_rest_breaks_no_item():
    result = calculate_unpaid_wages(
        hourly_rate=Decimal("20.00"),
        unpaid_hours=Decimal("8"),
        missed_rest_breaks=0,
    )
    rest_items = [i for i in result.items if i.category == "rest_break_premium"]
    assert len(rest_items) == 0


# ── Meal + rest combined ───────────────────────────────────────────


def test_meal_and_rest_combined():
    result = calculate_unpaid_wages(
        hourly_rate=Decimal("20.00"),
        unpaid_hours=Decimal("0"),
        missed_meal_breaks=2,
        missed_rest_breaks=3,
    )
    meal = next(i for i in result.items if i.category == "meal_break_premium")
    rest = next(i for i in result.items if i.category == "rest_break_premium")
    assert meal.amount == "40.00"
    assert rest.amount == "60.00"
    assert result.total == "100.00"


# ── Waiting time penalties ─────────────────────────────────────────


def test_waiting_penalty_terminated_never_paid():
    """Terminated, wages never paid, 30+ days ago → max 30 day penalty."""
    term_date = date(2025, 1, 1)
    result = calculate_unpaid_wages(
        hourly_rate=Decimal("25.00"),
        unpaid_hours=Decimal("8"),
        employment_status=EmploymentStatus.terminated,
        termination_date=term_date,
        final_wages_paid_date=None,
        as_of=date(2025, 3, 1),
    )
    penalty = [i for i in result.items if i.category == "waiting_time_penalty"]
    assert len(penalty) == 1
    # daily_wage = 25 × 8 = 200, capped at 30 days = $6000
    assert penalty[0].amount == "6000.00"


def test_waiting_penalty_terminated_paid_late():
    """Terminated, final wages paid 10 days late."""
    term_date = date(2025, 6, 1)
    paid_date = date(2025, 6, 11)
    result = calculate_unpaid_wages(
        hourly_rate=Decimal("20.00"),
        unpaid_hours=Decimal("8"),
        employment_status=EmploymentStatus.terminated,
        termination_date=term_date,
        final_wages_paid_date=paid_date,
        as_of=date(2025, 7, 1),
    )
    penalty = next(i for i in result.items if i.category == "waiting_time_penalty")
    # daily_wage = 20 × 8 = 160, 10 days late = $1600
    assert penalty.amount == "1600.00"
    assert "10" in penalty.description


def test_waiting_penalty_terminated_paid_on_time():
    """Terminated, wages paid on termination date → $0 penalty."""
    term_date = date(2025, 6, 1)
    result = calculate_unpaid_wages(
        hourly_rate=Decimal("20.00"),
        unpaid_hours=Decimal("8"),
        employment_status=EmploymentStatus.terminated,
        termination_date=term_date,
        final_wages_paid_date=term_date,
        as_of=date(2025, 7, 1),
    )
    penalty = next(i for i in result.items if i.category == "waiting_time_penalty")
    assert penalty.amount == "0.00"
    assert "on time" in penalty.notes.lower()


def test_waiting_penalty_quit_with_notice():
    """Quit with 72+ hours notice → due on last day."""
    term_date = date(2025, 6, 15)
    result = calculate_unpaid_wages(
        hourly_rate=Decimal("25.00"),
        unpaid_hours=Decimal("8"),
        employment_status=EmploymentStatus.quit_with_notice,
        termination_date=term_date,
        final_wages_paid_date=None,
        as_of=date(2025, 6, 20),
    )
    penalty = next(i for i in result.items if i.category == "waiting_time_penalty")
    # Due on term_date (6/15), as_of 6/20 → 5 days late
    # daily_wage = 25 × 8 = 200, 5 days = $1000
    assert penalty.amount == "1000.00"


def test_waiting_penalty_quit_without_notice():
    """Quit without notice → due within 72 hours (3 calendar days)."""
    term_date = date(2025, 6, 15)
    result = calculate_unpaid_wages(
        hourly_rate=Decimal("25.00"),
        unpaid_hours=Decimal("8"),
        employment_status=EmploymentStatus.quit_without_notice,
        termination_date=term_date,
        final_wages_paid_date=None,
        as_of=date(2025, 6, 25),
    )
    penalty = next(i for i in result.items if i.category == "waiting_time_penalty")
    # Due 3 days after term = 6/18, as_of 6/25 → 7 days late
    # daily_wage = 25 × 8 = 200, 7 days = $1400
    assert penalty.amount == "1400.00"


def test_waiting_penalty_still_employed_no_penalty():
    """Still employed → no waiting time penalty item at all."""
    result = calculate_unpaid_wages(
        hourly_rate=Decimal("25.00"),
        unpaid_hours=Decimal("8"),
        employment_status=EmploymentStatus.still_employed,
    )
    penalty = [i for i in result.items if i.category == "waiting_time_penalty"]
    assert len(penalty) == 0


def test_waiting_penalty_capped_at_30_days():
    """Penalty days capped at 30 regardless of how late."""
    term_date = date(2025, 1, 1)
    result = calculate_unpaid_wages(
        hourly_rate=Decimal("10.00"),
        unpaid_hours=Decimal("8"),
        employment_status=EmploymentStatus.terminated,
        termination_date=term_date,
        final_wages_paid_date=None,
        as_of=date(2025, 12, 31),
    )
    penalty = next(i for i in result.items if i.category == "waiting_time_penalty")
    # daily_wage = 10 × 8 = 80, max 30 days = $2400
    assert penalty.amount == "2400.00"
    assert "30" in penalty.description


def test_waiting_penalty_quit_without_notice_paid_early():
    """Quit without notice, paid before 72-hour deadline → $0."""
    term_date = date(2025, 6, 15)
    paid_date = date(2025, 6, 16)  # Paid next day, before 72hr deadline
    result = calculate_unpaid_wages(
        hourly_rate=Decimal("20.00"),
        unpaid_hours=Decimal("8"),
        employment_status=EmploymentStatus.quit_without_notice,
        termination_date=term_date,
        final_wages_paid_date=paid_date,
    )
    penalty = next(i for i in result.items if i.category == "waiting_time_penalty")
    assert penalty.amount == "0.00"


# ── Prejudgment interest ──────────────────────────────────────────


def test_interest_calculation():
    """10% per annum simple interest."""
    result = calculate_unpaid_wages(
        hourly_rate=Decimal("50.00"),
        unpaid_hours=Decimal("100"),
        unpaid_since=date(2025, 1, 1),
        as_of=date(2026, 1, 1),
    )
    interest = [i for i in result.items if i.category == "interest"]
    assert len(interest) == 1
    # $5000 × 10% × (365/365) = $500.00
    assert interest[0].amount == "500.00"
    assert "3287" in interest[0].legal_citation


def test_interest_partial_year():
    """Interest for a partial year."""
    result = calculate_unpaid_wages(
        hourly_rate=Decimal("100.00"),
        unpaid_hours=Decimal("10"),
        unpaid_since=date(2025, 1, 1),
        as_of=date(2025, 7, 2),  # 182 days
    )
    interest = next(i for i in result.items if i.category == "interest")
    # $1000 × 0.10 × 182/365 = $49.86
    assert interest.amount == "49.86"


def test_no_unpaid_since_no_interest():
    """No unpaid_since → no interest line item."""
    result = calculate_unpaid_wages(
        hourly_rate=Decimal("25.00"),
        unpaid_hours=Decimal("40"),
    )
    interest = [i for i in result.items if i.category == "interest"]
    assert len(interest) == 0


def test_no_interest_when_zero_wages():
    """Zero unpaid wages → no interest even if unpaid_since provided."""
    result = calculate_unpaid_wages(
        hourly_rate=Decimal("25.00"),
        unpaid_hours=Decimal("0"),
        unpaid_since=date(2024, 1, 1),
        as_of=date(2025, 1, 1),
    )
    interest = [i for i in result.items if i.category == "interest"]
    assert len(interest) == 0


# ── Legal citations ───────────────────────────────────────────────


def test_all_items_have_legal_citations():
    result = calculate_unpaid_wages(
        hourly_rate=Decimal("25.00"),
        unpaid_hours=Decimal("40"),
        employment_status=EmploymentStatus.terminated,
        termination_date=date(2025, 1, 1),
        missed_meal_breaks=2,
        missed_rest_breaks=1,
        unpaid_since=date(2024, 6, 1),
        as_of=date(2025, 6, 1),
    )
    for item in result.items:
        assert item.legal_citation, f"Item {item.category} has no legal_citation"
        assert len(item.legal_citation) > 0


def test_all_items_have_descriptions():
    result = calculate_unpaid_wages(
        hourly_rate=Decimal("25.00"),
        unpaid_hours=Decimal("40"),
        employment_status=EmploymentStatus.terminated,
        termination_date=date(2025, 1, 1),
        missed_meal_breaks=2,
        missed_rest_breaks=1,
        unpaid_since=date(2024, 6, 1),
        as_of=date(2025, 6, 1),
    )
    for item in result.items:
        assert item.description, f"Item {item.category} has no description"


# ── Total ─────────────────────────────────────────────────────────


def test_total_equals_sum_of_items():
    result = calculate_unpaid_wages(
        hourly_rate=Decimal("25.00"),
        unpaid_hours=Decimal("40"),
        employment_status=EmploymentStatus.terminated,
        termination_date=date(2025, 1, 1),
        missed_meal_breaks=3,
        missed_rest_breaks=2,
        unpaid_since=date(2024, 6, 1),
        as_of=date(2025, 6, 1),
    )
    item_sum = sum(Decimal(item.amount) for item in result.items)
    assert Decimal(result.total) == item_sum


# ── Decimal precision ────────────────────────────────────────────


def test_decimal_precision_two_places():
    result = calculate_unpaid_wages(
        hourly_rate=Decimal("17.33"),
        unpaid_hours=Decimal("3"),
    )
    assert result.items[0].amount == "51.99"
    assert "." in result.total
    assert len(result.total.split(".")[1]) == 2


# ── Combined scenario ────────────────────────────────────────────


def test_combined_full_scenario():
    """All components present: wages + breaks + penalty + interest."""
    result = calculate_unpaid_wages(
        hourly_rate=Decimal("30.00"),
        unpaid_hours=Decimal("80"),
        employment_status=EmploymentStatus.terminated,
        termination_date=date(2025, 1, 1),
        final_wages_paid_date=None,
        missed_meal_breaks=5,
        missed_rest_breaks=3,
        unpaid_since=date(2024, 7, 1),
        as_of=date(2025, 7, 1),
    )
    categories = [item.category for item in result.items]
    assert "unpaid_wages" in categories
    assert "meal_break_premium" in categories
    assert "rest_break_premium" in categories
    assert "waiting_time_penalty" in categories
    assert "interest" in categories
    assert len(result.items) == 5

    # Verify individual amounts
    wages = next(i for i in result.items if i.category == "unpaid_wages")
    assert wages.amount == "2400.00"  # 80 × 30

    meal = next(i for i in result.items if i.category == "meal_break_premium")
    assert meal.amount == "150.00"  # 5 × 30

    rest = next(i for i in result.items if i.category == "rest_break_premium")
    assert rest.amount == "90.00"  # 3 × 30

    penalty = next(i for i in result.items if i.category == "waiting_time_penalty")
    assert penalty.amount == "7200.00"  # 240/day × 30 days

    interest = next(i for i in result.items if i.category == "interest")
    # $2400 × 0.10 × 365/365 = $240.00
    assert interest.amount == "240.00"


# ── Enum ─────────────────────────────────────────────────────────


def test_employment_status_enum_values():
    assert EmploymentStatus.still_employed.value == "still_employed"
    assert EmploymentStatus.terminated.value == "terminated"
    assert EmploymentStatus.quit_with_notice.value == "quit_with_notice"
    assert EmploymentStatus.quit_without_notice.value == "quit_without_notice"
    assert len(EmploymentStatus) == 4


# ── Disclaimer ───────────────────────────────────────────────────


def test_disclaimer_contains_key_phrases():
    assert "general estimates" in DISCLAIMER
    assert "attorney" in DISCLAIMER.lower()
    assert "California labor law" in DISCLAIMER


# ── Dataclass immutability ────────────────────────────────────────


def test_result_is_frozen():
    result = calculate_unpaid_wages(
        hourly_rate=Decimal("25.00"),
        unpaid_hours=Decimal("8"),
    )
    with pytest.raises(AttributeError):
        result.total = "999.99"


def test_item_is_frozen():
    result = calculate_unpaid_wages(
        hourly_rate=Decimal("25.00"),
        unpaid_hours=Decimal("8"),
    )
    with pytest.raises(AttributeError):
        result.items[0].amount = "999.99"
