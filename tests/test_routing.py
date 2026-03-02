"""Unit tests for the agency routing guide."""

from __future__ import annotations

import pytest

from employee_help.tools.deadlines import ClaimType
from employee_help.tools.routing import (
    AGENCIES,
    DISCLAIMER,
    ISSUE_TYPE_LABELS,
    AgencyRecommendation,
    IssueType,
    Priority,
    get_agency_routing,
)


# ── All issue types produce results ──────────────────────────────────


@pytest.mark.parametrize("issue_type", list(IssueType))
def test_all_issue_types_return_results(issue_type: IssueType):
    results = get_agency_routing(issue_type)
    assert len(results) > 0
    assert all(isinstance(r, AgencyRecommendation) for r in results)


@pytest.mark.parametrize("issue_type", list(IssueType))
def test_all_issue_types_have_labels(issue_type: IssueType):
    assert issue_type in ISSUE_TYPE_LABELS
    assert len(ISSUE_TYPE_LABELS[issue_type]) > 0


# ── All fields populated ─────────────────────────────────────────────


@pytest.mark.parametrize("issue_type", list(IssueType))
def test_all_fields_populated(issue_type: IssueType):
    results = get_agency_routing(issue_type)
    for r in results:
        assert r.agency.name
        assert r.agency.acronym
        assert r.agency.description
        assert r.agency.handles
        assert r.agency.portal_url
        assert len(r.agency.filing_methods) > 0
        assert r.agency.process_overview
        assert r.agency.typical_timeline
        assert isinstance(r.priority, Priority)
        assert r.reason
        assert r.what_to_file


# ── Specific routing: primary agencies ───────────────────────────────


def test_discrimination_primary_is_crd():
    results = get_agency_routing(IssueType.discrimination)
    primary = [r for r in results if r.priority == Priority.primary]
    assert len(primary) == 1
    assert primary[0].agency.acronym == "CRD"


def test_harassment_primary_is_crd():
    results = get_agency_routing(IssueType.harassment)
    primary = [r for r in results if r.priority == Priority.primary]
    assert len(primary) == 1
    assert primary[0].agency.acronym == "CRD"


def test_unpaid_wages_primary_is_dlse():
    results = get_agency_routing(IssueType.unpaid_wages)
    primary = [r for r in results if r.priority == Priority.primary]
    assert len(primary) == 1
    assert primary[0].agency.acronym == "DLSE"


def test_wrongful_termination_primary_is_court():
    results = get_agency_routing(IssueType.wrongful_termination)
    primary = [r for r in results if r.priority == Priority.primary]
    assert len(primary) == 1
    assert primary[0].agency.acronym == "Court"


def test_workplace_safety_primary_is_cal_osha():
    results = get_agency_routing(IssueType.workplace_safety)
    primary = [r for r in results if r.priority == Priority.primary]
    assert len(primary) == 1
    assert primary[0].agency.acronym == "Cal/OSHA"


def test_unemployment_primary_is_edd():
    results = get_agency_routing(IssueType.unemployment_benefits)
    primary = [r for r in results if r.priority == Priority.primary]
    assert len(primary) == 1
    assert primary[0].agency.acronym == "EDD"


def test_disability_insurance_primary_is_edd():
    results = get_agency_routing(IssueType.disability_insurance)
    primary = [r for r in results if r.priority == Priority.primary]
    assert len(primary) == 1
    assert primary[0].agency.acronym == "EDD"


def test_paid_family_leave_primary_is_edd():
    results = get_agency_routing(IssueType.paid_family_leave)
    primary = [r for r in results if r.priority == Priority.primary]
    assert len(primary) == 1
    assert primary[0].agency.acronym == "EDD"


def test_family_medical_leave_primary_is_crd():
    results = get_agency_routing(IssueType.family_medical_leave)
    primary = [r for r in results if r.priority == Priority.primary]
    assert len(primary) == 1
    assert primary[0].agency.acronym == "CRD"


def test_misclassification_primary_is_dlse():
    results = get_agency_routing(IssueType.misclassification)
    primary = [r for r in results if r.priority == Priority.primary]
    assert len(primary) == 1
    assert primary[0].agency.acronym == "DLSE"


def test_meal_rest_breaks_primary_is_dlse():
    results = get_agency_routing(IssueType.meal_rest_breaks)
    primary = [r for r in results if r.priority == Priority.primary]
    assert len(primary) == 1
    assert primary[0].agency.acronym == "DLSE"


def test_retaliation_primary_is_dlse():
    results = get_agency_routing(IssueType.retaliation)
    primary = [r for r in results if r.priority == Priority.primary]
    assert len(primary) == 1
    assert primary[0].agency.acronym == "DLSE"


def test_whistleblower_primary_is_dlse():
    results = get_agency_routing(IssueType.whistleblower)
    primary = [r for r in results if r.priority == Priority.primary]
    assert len(primary) == 1
    assert primary[0].agency.acronym == "DLSE"


# ── Government employee: CalHR prerequisite ──────────────────────────


_GOV_CALHR_ISSUES = [
    IssueType.unpaid_wages,
    IssueType.discrimination,
    IssueType.harassment,
    IssueType.retaliation,
    IssueType.family_medical_leave,
    IssueType.meal_rest_breaks,
]


@pytest.mark.parametrize("issue_type", _GOV_CALHR_ISSUES)
def test_gov_employee_adds_calhr_prerequisite(issue_type: IssueType):
    results = get_agency_routing(issue_type, is_government_employee=True)
    prereqs = [r for r in results if r.priority == Priority.prerequisite]
    assert len(prereqs) == 1
    assert prereqs[0].agency.acronym == "CalHR"


@pytest.mark.parametrize("issue_type", _GOV_CALHR_ISSUES)
def test_non_gov_employee_no_calhr_prerequisite(issue_type: IssueType):
    results = get_agency_routing(issue_type, is_government_employee=False)
    prereqs = [r for r in results if r.priority == Priority.prerequisite]
    assert len(prereqs) == 0


# ── Government employee: tort claim prerequisite ─────────────────────


_GOV_TORT_ISSUES = [
    IssueType.wrongful_termination,
    IssueType.whistleblower,
]


@pytest.mark.parametrize("issue_type", _GOV_TORT_ISSUES)
def test_gov_employee_adds_tort_prerequisite(issue_type: IssueType):
    results = get_agency_routing(issue_type, is_government_employee=True)
    prereqs = [r for r in results if r.priority == Priority.prerequisite]
    assert len(prereqs) == 1
    assert "tort claim" in prereqs[0].what_to_file.lower()


# ── Government employee: no change for some issue types ──────────────


_GOV_NO_CHANGE_ISSUES = [
    IssueType.workplace_safety,
    IssueType.unemployment_benefits,
    IssueType.disability_insurance,
    IssueType.paid_family_leave,
    IssueType.misclassification,
]


@pytest.mark.parametrize("issue_type", _GOV_NO_CHANGE_ISSUES)
def test_gov_employee_no_change(issue_type: IssueType):
    normal = get_agency_routing(issue_type, is_government_employee=False)
    gov = get_agency_routing(issue_type, is_government_employee=True)
    assert len(normal) == len(gov)


# ── Sort order: prerequisite → primary → alternative ─────────────────


def test_sort_order_prerequisite_first():
    results = get_agency_routing(IssueType.discrimination, is_government_employee=True)
    priorities = [r.priority for r in results]
    assert priorities[0] == Priority.prerequisite
    # Check overall ordering
    order = {Priority.prerequisite: 0, Priority.primary: 1, Priority.alternative: 2}
    values = [order[p] for p in priorities]
    assert values == sorted(values)


# ── Related claim type cross-validation ──────────────────────────────


_VALID_CLAIM_TYPES = {ct.value for ct in ClaimType}


@pytest.mark.parametrize("issue_type", list(IssueType))
def test_related_claim_type_valid(issue_type: IssueType):
    """related_claim_type values must map to ClaimType enum values or be None."""
    results = get_agency_routing(issue_type)
    for r in results:
        if r.related_claim_type is not None:
            assert r.related_claim_type in _VALID_CLAIM_TYPES, (
                f"{issue_type.value} recommendation has invalid related_claim_type: {r.related_claim_type}"
            )


# ── Cross-link expectations ──────────────────────────────────────────


def test_wage_issues_link_to_wage_theft():
    for issue in [IssueType.unpaid_wages, IssueType.meal_rest_breaks]:
        results = get_agency_routing(issue)
        primary = next(r for r in results if r.priority == Priority.primary)
        assert primary.related_claim_type == "wage_theft"


def test_discrimination_links_to_feha():
    results = get_agency_routing(IssueType.discrimination)
    primary = next(r for r in results if r.priority == Priority.primary)
    assert primary.related_claim_type == "feha_discrimination"


def test_safety_has_no_claim_type():
    results = get_agency_routing(IssueType.workplace_safety)
    primary = next(r for r in results if r.priority == Priority.primary)
    assert primary.related_claim_type is None


def test_edd_issues_have_no_claim_type():
    for issue in [IssueType.unemployment_benefits, IssueType.disability_insurance, IssueType.paid_family_leave]:
        results = get_agency_routing(issue)
        primary = next(r for r in results if r.priority == Priority.primary)
        assert primary.related_claim_type is None


# ── Agency registry ──────────────────────────────────────────────────


def test_agency_registry_has_8_agencies():
    assert len(AGENCIES) == 8


def test_all_agencies_have_portal_url():
    for key, agency in AGENCIES.items():
        assert agency.portal_url, f"Agency {key} has no portal_url"


# ── Disclaimer ───────────────────────────────────────────────────────


def test_disclaimer_exists():
    assert "general information" in DISCLAIMER
    assert "attorney" in DISCLAIMER.lower()
    assert "not legal advice" in DISCLAIMER.lower()
