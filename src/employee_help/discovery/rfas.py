"""Requests for Admission (RFAs) bank for California employment law.

Contains ~25 employment-specific requests for admission organized by category.
Each RFA is tagged as either "fact" or "genuineness" because the 35-item limit
(CCP 2033.030) applies only to fact-based RFAs — genuineness-of-document
requests are unlimited (CCP 2033.060).

Pure data — no DB, no ML, no external services.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import DiscoveryRequest, RFA_FACT_LIMIT


# ---------------------------------------------------------------------------
# RFA sub-type (determines whether it counts toward the 35 limit)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RFARequest(DiscoveryRequest):
    """A request for admission with a fact/genuineness designation.

    Inherits all fields from DiscoveryRequest and adds:
    - rfa_type: "fact" or "genuineness"
      Only "fact" RFAs count toward the CCP 2033.030 limit of 35.
    """

    rfa_type: str = "fact"  # "fact" or "genuineness"


# ---------------------------------------------------------------------------
# Category definitions
# ---------------------------------------------------------------------------

RFA_CATEGORIES: dict[str, str] = {
    "employment_facts": "Employment Relationship Facts",
    "adverse_action_facts": "Adverse Employment Action Facts",
    "policy_facts": "Policies and Procedures",
    "complaint_facts": "Complaints and Investigation",
    "wage_facts": "Wages and Hours",
    "document_genuineness": "Genuineness of Documents",
}


# ---------------------------------------------------------------------------
# Request bank
# ---------------------------------------------------------------------------

RFA_BANK: list[RFARequest] = [
    # --- Employment Relationship Facts (4) ---
    RFARequest(
        id="rfa_emp_001",
        text=(
            "Admit that EMPLOYEE was employed by EMPLOYER from "
            "[START DATE] to [END DATE]."
        ),
        category="employment_facts",
        rfa_type="fact",
        order=1,
    ),
    RFARequest(
        id="rfa_emp_002",
        text=(
            "Admit that at all relevant times, EMPLOYEE held the "
            "position of [JOB TITLE] at EMPLOYER."
        ),
        category="employment_facts",
        rfa_type="fact",
        order=2,
    ),
    RFARequest(
        id="rfa_emp_003",
        text=(
            "Admit that at all relevant times, [SUPERVISOR NAME] was "
            "EMPLOYEE's direct supervisor."
        ),
        category="employment_facts",
        rfa_type="fact",
        order=3,
    ),
    RFARequest(
        id="rfa_emp_004",
        text=(
            "Admit that EMPLOYEE's EMPLOYMENT with EMPLOYER was "
            "terminated on or about [TERMINATION DATE]."
        ),
        category="employment_facts",
        rfa_type="fact",
        order=4,
    ),

    # --- Adverse Employment Action Facts (5) ---
    RFARequest(
        id="rfa_adv_001",
        text=(
            "Admit that EMPLOYER took ADVERSE EMPLOYMENT ACTION against "
            "EMPLOYEE on or about [DATE]."
        ),
        category="adverse_action_facts",
        rfa_type="fact",
        order=5,
    ),
    RFARequest(
        id="rfa_adv_002",
        text=(
            "Admit that [DECISION MAKER NAME] participated in the "
            "decision to take the ADVERSE EMPLOYMENT ACTION against "
            "EMPLOYEE."
        ),
        category="adverse_action_facts",
        rfa_type="fact",
        order=6,
    ),
    RFARequest(
        id="rfa_adv_003",
        text=(
            "Admit that EMPLOYEE's job performance was rated "
            "\"satisfactory\" or above in EMPLOYEE's most recent "
            "performance evaluation prior to the ADVERSE EMPLOYMENT "
            "ACTION."
        ),
        category="adverse_action_facts",
        rfa_type="fact",
        order=7,
    ),
    RFARequest(
        id="rfa_adv_004",
        text=(
            "Admit that EMPLOYEE did not receive any written warnings "
            "or disciplinary notices in the twelve months preceding the "
            "ADVERSE EMPLOYMENT ACTION."
        ),
        category="adverse_action_facts",
        rfa_type="fact",
        order=8,
    ),
    RFARequest(
        id="rfa_adv_005",
        text=(
            "Admit that EMPLOYER did not follow its own progressive "
            "discipline policy before taking the ADVERSE EMPLOYMENT "
            "ACTION against EMPLOYEE."
        ),
        category="adverse_action_facts",
        rfa_type="fact",
        order=9,
    ),

    # --- Policy Facts (4) ---
    RFARequest(
        id="rfa_pol_001",
        text=(
            "Admit that EMPLOYER had a written anti-discrimination and "
            "anti-harassment policy in effect during EMPLOYEE's "
            "EMPLOYMENT."
        ),
        category="policy_facts",
        rfa_type="fact",
        order=10,
    ),
    RFARequest(
        id="rfa_pol_002",
        text=(
            "Admit that EMPLOYER's written policies required employees "
            "to report complaints of discrimination, harassment, or "
            "retaliation to [DEPARTMENT/PERSON]."
        ),
        category="policy_facts",
        rfa_type="fact",
        order=11,
    ),
    RFARequest(
        id="rfa_pol_003",
        text=(
            "Admit that EMPLOYER had a written progressive discipline "
            "policy in effect during EMPLOYEE's EMPLOYMENT."
        ),
        category="policy_facts",
        rfa_type="fact",
        order=12,
    ),
    RFARequest(
        id="rfa_pol_004",
        text=(
            "Admit that EMPLOYER provided EMPLOYEE with a copy of the "
            "employee handbook at the commencement of EMPLOYMENT."
        ),
        category="policy_facts",
        rfa_type="fact",
        order=13,
    ),

    # --- Complaint Facts (4) ---
    RFARequest(
        id="rfa_cmp_001",
        text=(
            "Admit that EMPLOYEE complained to EMPLOYER about "
            "[PROTECTED ACTIVITY] on or about [DATE]."
        ),
        category="complaint_facts",
        rfa_type="fact",
        order=14,
    ),
    RFARequest(
        id="rfa_cmp_002",
        text=(
            "Admit that EMPLOYER received EMPLOYEE's complaint about "
            "[PROTECTED ACTIVITY] before taking the ADVERSE EMPLOYMENT "
            "ACTION."
        ),
        category="complaint_facts",
        rfa_type="fact",
        order=15,
    ),
    RFARequest(
        id="rfa_cmp_003",
        text=(
            "Admit that EMPLOYER did not conduct a timely investigation "
            "into EMPLOYEE's complaint about [PROTECTED ACTIVITY]."
        ),
        category="complaint_facts",
        rfa_type="fact",
        order=16,
    ),
    RFARequest(
        id="rfa_cmp_004",
        text=(
            "Admit that no corrective action was taken against any "
            "PERSON as a result of EMPLOYEE's complaint about "
            "[PROTECTED ACTIVITY]."
        ),
        category="complaint_facts",
        rfa_type="fact",
        order=17,
    ),

    # --- Wage Facts (4) ---
    RFARequest(
        id="rfa_wage_001",
        text=(
            "Admit that EMPLOYEE was classified as a non-exempt "
            "employee during the EMPLOYMENT."
        ),
        category="wage_facts",
        rfa_type="fact",
        order=18,
    ),
    RFARequest(
        id="rfa_wage_002",
        text=(
            "Admit that EMPLOYEE worked more than eight hours in a "
            "workday on at least one occasion during the EMPLOYMENT."
        ),
        category="wage_facts",
        rfa_type="fact",
        order=19,
    ),
    RFARequest(
        id="rfa_wage_003",
        text=(
            "Admit that EMPLOYER did not provide EMPLOYEE with a "
            "30-minute uninterrupted meal period for each work period "
            "exceeding five hours on at least one occasion during the "
            "EMPLOYMENT."
        ),
        category="wage_facts",
        rfa_type="fact",
        order=20,
    ),
    RFARequest(
        id="rfa_wage_004",
        text=(
            "Admit that EMPLOYER did not pay EMPLOYEE all wages owed "
            "within the time required by Labor Code sections 201 and "
            "202 upon TERMINATION of EMPLOYMENT."
        ),
        category="wage_facts",
        rfa_type="fact",
        order=21,
    ),

    # --- Document Genuineness (5) — UNLIMITED, not counted toward 35 ---
    RFARequest(
        id="rfa_doc_001",
        text=(
            "Admit that the DOCUMENT attached hereto as Exhibit [X] is "
            "a true and correct copy of EMPLOYEE's personnel file "
            "maintained by EMPLOYER."
        ),
        category="document_genuineness",
        rfa_type="genuineness",
        order=22,
    ),
    RFARequest(
        id="rfa_doc_002",
        text=(
            "Admit that the DOCUMENT attached hereto as Exhibit [X] is "
            "a true and correct copy of the employee handbook provided "
            "to EMPLOYEE during the EMPLOYMENT."
        ),
        category="document_genuineness",
        rfa_type="genuineness",
        order=23,
    ),
    RFARequest(
        id="rfa_doc_003",
        text=(
            "Admit that the DOCUMENT attached hereto as Exhibit [X] is "
            "a true and correct copy of EMPLOYEE's most recent "
            "performance evaluation."
        ),
        category="document_genuineness",
        rfa_type="genuineness",
        order=24,
    ),
    RFARequest(
        id="rfa_doc_004",
        text=(
            "Admit that the DOCUMENT attached hereto as Exhibit [X] is "
            "a true and correct copy of the TERMINATION letter or "
            "notice provided to EMPLOYEE."
        ),
        category="document_genuineness",
        rfa_type="genuineness",
        order=25,
    ),
    RFARequest(
        id="rfa_doc_005",
        text=(
            "Admit that the DOCUMENT attached hereto as Exhibit [X] is "
            "a true and correct copy of EMPLOYER's written anti-"
            "discrimination and anti-harassment policy in effect at the "
            "time of the ADVERSE EMPLOYMENT ACTION."
        ),
        category="document_genuineness",
        rfa_type="genuineness",
        order=26,
    ),
]


def get_rfa_bank() -> list[RFARequest]:
    """Return a copy of the full RFA request bank."""
    return list(RFA_BANK)


def get_rfas_by_category(category: str) -> list[RFARequest]:
    """Return RFAs for a specific category."""
    return [r for r in RFA_BANK if r.category == category]


def get_rfas_for_categories(
    categories: list[str] | tuple[str, ...],
) -> list[RFARequest]:
    """Return RFAs matching any of the given categories, in order."""
    cat_set = set(categories)
    return [r for r in RFA_BANK if r.category in cat_set]


def count_fact_rfas(requests: list[RFARequest]) -> int:
    """Count selected fact-based RFAs (those subject to the 35 limit)."""
    return sum(
        1 for r in requests
        if r.is_selected and r.rfa_type == "fact"
    )


def count_genuineness_rfas(requests: list[RFARequest]) -> int:
    """Count selected genuineness-of-document RFAs (unlimited)."""
    return sum(
        1 for r in requests
        if r.is_selected and r.rfa_type == "genuineness"
    )


def exceeds_fact_limit(requests: list[RFARequest]) -> bool:
    """Check if selected fact-based RFAs exceed the 35 limit."""
    return count_fact_rfas(requests) > RFA_FACT_LIMIT


def needs_declaration(requests: list[RFARequest]) -> bool:
    """Check if a CCP 2033.050 Declaration of Necessity is required."""
    return exceeds_fact_limit(requests)
