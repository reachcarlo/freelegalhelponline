"""Unit tests for the statute of limitations deadline calculator."""

from __future__ import annotations

from datetime import date

import pytest

from employee_help.tools.deadlines import (
    CLAIM_TYPE_LABELS,
    DEADLINE_RULES,
    DISCLAIMER,
    ClaimType,
    DeadlineResult,
    UrgencyLevel,
    _add_months,
    _add_years,
    calculate_deadlines,
)


# ── Helpers ──────────────────────────────────────────────────────────

AS_OF = date(2026, 3, 1)  # Fixed reference for deterministic tests


# ── All claim types produce results ─────────────────────────────────


@pytest.mark.parametrize("claim_type", list(ClaimType))
def test_all_claim_types_return_results(claim_type: ClaimType):
    results = calculate_deadlines(claim_type, date(2025, 1, 15), as_of=AS_OF)
    assert len(results) > 0
    assert all(isinstance(r, DeadlineResult) for r in results)


@pytest.mark.parametrize("claim_type", list(ClaimType))
def test_all_claim_types_have_labels(claim_type: ClaimType):
    assert claim_type in CLAIM_TYPE_LABELS
    assert len(CLAIM_TYPE_LABELS[claim_type]) > 0


@pytest.mark.parametrize("claim_type", list(ClaimType))
def test_all_claim_types_have_rules(claim_type: ClaimType):
    assert claim_type in DEADLINE_RULES
    assert len(DEADLINE_RULES[claim_type]) >= 2


# ── Sorted output ───────────────────────────────────────────────────


def test_results_sorted_by_deadline_date():
    results = calculate_deadlines(ClaimType.feha_discrimination, date(2025, 1, 1), as_of=AS_OF)
    dates = [r.deadline_date for r in results]
    assert dates == sorted(dates)


# ── All fields populated ────────────────────────────────────────────


def test_result_fields_populated():
    results = calculate_deadlines(ClaimType.wage_theft, date(2025, 6, 15), as_of=AS_OF)
    for r in results:
        assert r.name
        assert r.description
        assert r.filing_entity
        assert r.legal_citation
        assert r.portal_url
        assert isinstance(r.deadline_date, date)
        assert isinstance(r.days_remaining, int)
        assert isinstance(r.urgency, UrgencyLevel)


# ── FEHA deadlines ──────────────────────────────────────────────────


def test_feha_crd_3_years():
    results = calculate_deadlines(ClaimType.feha_discrimination, date(2024, 6, 1), as_of=AS_OF)
    crd = next(r for r in results if "CRD" in r.name)
    assert crd.deadline_date == date(2027, 6, 1)


def test_feha_eeoc_300_days():
    results = calculate_deadlines(ClaimType.feha_discrimination, date(2025, 6, 1), as_of=AS_OF)
    eeoc = next(r for r in results if "EEOC" in r.name)
    assert eeoc.deadline_date == date(2025, 6, 1) + __import__("datetime").timedelta(days=300)


def test_feha_civil_suit_4_years():
    results = calculate_deadlines(ClaimType.feha_discrimination, date(2024, 1, 1), as_of=AS_OF)
    suit = next(r for r in results if "Civil Suit" in r.name)
    assert suit.deadline_date == date(2028, 1, 1)


# ── Wage theft deadlines ────────────────────────────────────────────


def test_wage_theft_dlse_3_years():
    results = calculate_deadlines(ClaimType.wage_theft, date(2024, 3, 15), as_of=AS_OF)
    dlse = next(r for r in results if "DLSE" in r.name)
    assert dlse.deadline_date == date(2027, 3, 15)


def test_wage_theft_written_4_years():
    results = calculate_deadlines(ClaimType.wage_theft, date(2023, 7, 1), as_of=AS_OF)
    written = next(r for r in results if "Written" in r.name)
    assert written.deadline_date == date(2027, 7, 1)


# ── Wrongful termination deadlines ──────────────────────────────────


def test_wrongful_term_tort_2_years():
    results = calculate_deadlines(ClaimType.wrongful_termination, date(2025, 1, 1), as_of=AS_OF)
    tort = next(r for r in results if "Tort" in r.name)
    assert tort.deadline_date == date(2027, 1, 1)


# ── Retaliation deadlines ───────────────────────────────────────────


def test_retaliation_dlse_6_months():
    results = calculate_deadlines(ClaimType.retaliation_whistleblower, date(2026, 1, 15), as_of=AS_OF)
    dlse = next(r for r in results if "DLSE" in r.name)
    assert dlse.deadline_date == date(2026, 7, 15)


def test_retaliation_court_3_years():
    results = calculate_deadlines(ClaimType.retaliation_whistleblower, date(2024, 5, 1), as_of=AS_OF)
    court = next(r for r in results if "Court" in r.name)
    assert court.deadline_date == date(2027, 5, 1)


# ── PAGA deadlines ──────────────────────────────────────────────────


def test_paga_lwda_1_year():
    results = calculate_deadlines(ClaimType.paga, date(2025, 9, 1), as_of=AS_OF)
    lwda = next(r for r in results if "LWDA Notice" in r.name)
    assert lwda.deadline_date == date(2026, 9, 1)


# ── CFRA deadlines ──────────────────────────────────────────────────


def test_cfra_crd_3_years():
    results = calculate_deadlines(ClaimType.cfra_family_leave, date(2024, 4, 1), as_of=AS_OF)
    crd = next(r for r in results if "CRD" in r.name)
    assert crd.deadline_date == date(2027, 4, 1)


# ── Government employee deadlines ───────────────────────────────────


def test_gov_tort_claim_6_months():
    results = calculate_deadlines(ClaimType.government_employee, date(2026, 1, 1), as_of=AS_OF)
    tort = next(r for r in results if "Tort Claim" in r.name)
    assert tort.deadline_date == date(2026, 7, 1)


def test_gov_court_12_months():
    results = calculate_deadlines(ClaimType.government_employee, date(2025, 6, 1), as_of=AS_OF)
    court = next(r for r in results if "Court" in r.name)
    assert court.deadline_date == date(2026, 6, 1)


# ── Misclassification deadlines ─────────────────────────────────────


def test_misclassification_ucl_4_years():
    results = calculate_deadlines(ClaimType.misclassification, date(2023, 1, 1), as_of=AS_OF)
    ucl = next(r for r in results if "UCL" in r.name)
    assert ucl.deadline_date == date(2027, 1, 1)


# ── Urgency classification ──────────────────────────────────────────


def test_urgency_expired():
    # Incident 5 years ago → all deadlines expired
    results = calculate_deadlines(ClaimType.wrongful_termination, date(2020, 1, 1), as_of=AS_OF)
    assert all(r.urgency == UrgencyLevel.expired for r in results)
    assert all(r.days_remaining < 0 for r in results)


def test_urgency_critical_under_30_days():
    # Incident date chosen so the 2-year deadline is ~15 days away
    incident = date(2024, 3, 16)  # 2yr deadline = 2026-03-16, 15 days from AS_OF
    results = calculate_deadlines(ClaimType.wrongful_termination, incident, as_of=AS_OF)
    tort = next(r for r in results if "Tort" in r.name)
    assert tort.days_remaining == 15
    assert tort.urgency == UrgencyLevel.critical


def test_urgency_urgent_under_90_days():
    # 2-year deadline ~60 days away
    incident = date(2024, 4, 30)  # 2yr = 2026-04-30, 60 days from AS_OF
    results = calculate_deadlines(ClaimType.wrongful_termination, incident, as_of=AS_OF)
    tort = next(r for r in results if "Tort" in r.name)
    assert tort.days_remaining == 60
    assert tort.urgency == UrgencyLevel.urgent


def test_urgency_normal_over_90_days():
    incident = date(2025, 1, 1)  # 2yr = 2027-01-01, 306 days from AS_OF
    results = calculate_deadlines(ClaimType.wrongful_termination, incident, as_of=AS_OF)
    tort = next(r for r in results if "Tort" in r.name)
    assert tort.days_remaining > 90
    assert tort.urgency == UrgencyLevel.normal


# ── Boundary values for urgency ──────────────────────────────────────


def test_urgency_boundary_exactly_0_days():
    """Deadline is today → expired (0 days remaining = expired since day has started)."""
    incident = date(2024, 3, 1)  # 2yr = 2026-03-01 = AS_OF
    results = calculate_deadlines(ClaimType.wrongful_termination, incident, as_of=AS_OF)
    tort = next(r for r in results if "Tort" in r.name)
    assert tort.days_remaining == 0
    assert tort.urgency == UrgencyLevel.critical


def test_urgency_boundary_exactly_30_days():
    """At exactly 30 days → urgent (not critical)."""
    incident = date(2024, 3, 31)  # 2yr = 2026-03-31, 30 days from AS_OF
    results = calculate_deadlines(ClaimType.wrongful_termination, incident, as_of=AS_OF)
    tort = next(r for r in results if "Tort" in r.name)
    assert tort.days_remaining == 30
    assert tort.urgency == UrgencyLevel.urgent


def test_urgency_boundary_exactly_90_days():
    """At exactly 90 days → normal (not urgent)."""
    incident = date(2024, 5, 30)  # 2yr = 2026-05-30, 90 days from AS_OF
    results = calculate_deadlines(ClaimType.wrongful_termination, incident, as_of=AS_OF)
    tort = next(r for r in results if "Tort" in r.name)
    assert tort.days_remaining == 90
    assert tort.urgency == UrgencyLevel.normal


# ── Edge cases: leap year / month-end / year boundary ────────────────


def test_leap_year_feb29_incident():
    """Feb 29 incident + 2 years → Feb 28 in non-leap year."""
    incident = date(2024, 2, 29)  # 2024 is a leap year
    results = calculate_deadlines(ClaimType.wrongful_termination, incident, as_of=AS_OF)
    tort = next(r for r in results if "Tort" in r.name)
    # 2026 is not a leap year
    assert tort.deadline_date == date(2026, 2, 28)


def test_month_end_overflow_jan31_plus_6_months():
    """Jan 31 + 6 months → Jul 31 (no overflow)."""
    incident = date(2026, 1, 31)
    results = calculate_deadlines(ClaimType.retaliation_whistleblower, incident, as_of=AS_OF)
    dlse = next(r for r in results if "DLSE" in r.name)
    assert dlse.deadline_date == date(2026, 7, 31)


def test_month_end_overflow_aug31_plus_6_months():
    """Aug 31 + 6 months → Feb 28 (day clamped)."""
    incident = date(2025, 8, 31)
    results = calculate_deadlines(ClaimType.government_employee, incident, as_of=AS_OF)
    tort = next(r for r in results if "Tort Claim" in r.name)
    assert tort.deadline_date == date(2026, 2, 28)


def test_year_boundary_dec31():
    """Dec 31 incident + 3 years crosses year boundary correctly."""
    incident = date(2023, 12, 31)
    results = calculate_deadlines(ClaimType.wage_theft, incident, as_of=AS_OF)
    dlse = next(r for r in results if "DLSE" in r.name)
    assert dlse.deadline_date == date(2026, 12, 31)


# ── Date helpers directly ────────────────────────────────────────────


def test_add_years_normal():
    assert _add_years(date(2024, 6, 15), 3) == date(2027, 6, 15)


def test_add_years_leap_to_non_leap():
    assert _add_years(date(2024, 2, 29), 1) == date(2025, 2, 28)


def test_add_years_leap_to_leap():
    assert _add_years(date(2024, 2, 29), 4) == date(2028, 2, 29)


def test_add_months_normal():
    assert _add_months(date(2026, 1, 15), 6) == date(2026, 7, 15)


def test_add_months_day_clamp():
    assert _add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)


def test_add_months_cross_year():
    assert _add_months(date(2025, 11, 15), 3) == date(2026, 2, 15)


# ── as_of defaults to today ─────────────────────────────────────────


def test_as_of_defaults_to_today():
    """Without as_of, uses date.today() — just verify no error."""
    results = calculate_deadlines(ClaimType.feha_discrimination, date(2025, 1, 1))
    assert len(results) > 0


# ── Disclaimer constant ─────────────────────────────────────────────


def test_disclaimer_exists():
    assert "general estimates" in DISCLAIMER
    assert "attorney" in DISCLAIMER.lower()
