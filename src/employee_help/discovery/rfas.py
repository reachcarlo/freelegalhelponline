"""Requests for Admission (RFAs) bank for California employment law.

Contains role-aware employment-specific requests for admission organized
by category. Plaintiff-side, defendant-side, and shared requests are all
in one bank; filtering by role happens via filter functions in filters.py.

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
# Category definitions (17 categories)
# ---------------------------------------------------------------------------

RFA_CATEGORIES: dict[str, str] = {
    # Shared
    "employment_facts": "Employment Relationship Facts",
    "document_genuineness": "Genuineness of Documents",
    # Plaintiff (existing)
    "adverse_action_facts": "Adverse Employment Action Facts",
    "policy_facts": "Policies and Procedures",
    "complaint_facts": "Complaints and Investigation",
    "wage_facts": "Wages and Hours",
    # Plaintiff (new)
    "discrimination_facts": "Discrimination, Harassment, and Retaliation",
    "comparator_facts": "Comparator and Similar Treatment",
    "damages_facts": "Damages and Benefits",
    "accommodation_facts": "Disability Accommodation",
    # Defendant (new)
    "performance_facts": "Performance and Disciplinary History",
    "policies_compliance": "Policies and Complaint Procedures",
    "legitimate_reasons": "Legitimate Business Reasons",
    "damages_limitations": "Damages Limitations",
    "mitigation_facts": "Mitigation of Damages",
    "prior_claims": "Prior Employment and Claims",
    "direct_evidence": "Lack of Direct Evidence",
}


# ---------------------------------------------------------------------------
# Request bank
# ---------------------------------------------------------------------------

RFA_BANK: list[RFARequest] = [
    # ===================================================================
    # SHARED — Employment Relationship Facts (4)
    # ===================================================================
    RFARequest(
        id="rfa_emp_001",
        text=(
            "Admit that {EMPLOYEE} was employed by {EMPLOYER} from "
            "[START DATE] to [END DATE]."
        ),
        category="employment_facts",
        rfa_type="fact",
        applicable_roles=("plaintiff", "defendant"),
        order=1,
    ),
    RFARequest(
        id="rfa_emp_002",
        text=(
            "Admit that at all relevant times, {EMPLOYEE} held the "
            "position of [JOB TITLE] at {EMPLOYER}."
        ),
        category="employment_facts",
        rfa_type="fact",
        applicable_roles=("plaintiff", "defendant"),
        order=2,
    ),
    RFARequest(
        id="rfa_emp_003",
        text=(
            "Admit that at all relevant times, [SUPERVISOR NAME] was "
            "{EMPLOYEE}'s direct supervisor."
        ),
        category="employment_facts",
        rfa_type="fact",
        applicable_roles=("plaintiff", "defendant"),
        order=3,
    ),
    RFARequest(
        id="rfa_emp_004",
        text=(
            "Admit that {EMPLOYEE}'s EMPLOYMENT with {EMPLOYER} was "
            "terminated on or about [TERMINATION DATE]."
        ),
        category="employment_facts",
        rfa_type="fact",
        applicable_roles=("plaintiff", "defendant"),
        order=4,
    ),

    # ===================================================================
    # PLAINTIFF — Adverse Employment Action Facts (5)
    # ===================================================================
    RFARequest(
        id="rfa_adv_001",
        text=(
            "Admit that {EMPLOYER} took ADVERSE EMPLOYMENT ACTION against "
            "{EMPLOYEE} on or about [DATE]."
        ),
        category="adverse_action_facts",
        rfa_type="fact",
        applicable_roles=("plaintiff",),
        order=5,
    ),
    RFARequest(
        id="rfa_adv_002",
        text=(
            "Admit that [DECISION MAKER NAME] participated in the "
            "decision to take the ADVERSE EMPLOYMENT ACTION against "
            "{EMPLOYEE}."
        ),
        category="adverse_action_facts",
        rfa_type="fact",
        applicable_roles=("plaintiff",),
        order=6,
    ),
    RFARequest(
        id="rfa_adv_003",
        text=(
            "Admit that {EMPLOYEE}'s job performance was rated "
            "\"satisfactory\" or above in {EMPLOYEE}'s most recent "
            "performance evaluation prior to the ADVERSE EMPLOYMENT "
            "ACTION."
        ),
        category="adverse_action_facts",
        rfa_type="fact",
        applicable_roles=("plaintiff",),
        order=7,
    ),
    RFARequest(
        id="rfa_adv_004",
        text=(
            "Admit that {EMPLOYEE} did not receive any written warnings "
            "or disciplinary notices in the twelve months preceding the "
            "ADVERSE EMPLOYMENT ACTION."
        ),
        category="adverse_action_facts",
        rfa_type="fact",
        applicable_roles=("plaintiff",),
        order=8,
    ),
    RFARequest(
        id="rfa_adv_005",
        text=(
            "Admit that {EMPLOYER} did not follow its own progressive "
            "discipline policy before taking the ADVERSE EMPLOYMENT "
            "ACTION against {EMPLOYEE}."
        ),
        category="adverse_action_facts",
        rfa_type="fact",
        applicable_roles=("plaintiff",),
        order=9,
    ),

    # ===================================================================
    # PLAINTIFF — Policy Facts (4)
    # ===================================================================
    RFARequest(
        id="rfa_pol_001",
        text=(
            "Admit that {EMPLOYER} had a written anti-discrimination and "
            "anti-harassment policy in effect during {EMPLOYEE}'s "
            "EMPLOYMENT."
        ),
        category="policy_facts",
        rfa_type="fact",
        applicable_roles=("plaintiff",),
        order=10,
    ),
    RFARequest(
        id="rfa_pol_002",
        text=(
            "Admit that {EMPLOYER}'s written policies required employees "
            "to report complaints of discrimination, harassment, or "
            "retaliation to [DEPARTMENT/PERSON]."
        ),
        category="policy_facts",
        rfa_type="fact",
        applicable_roles=("plaintiff",),
        order=11,
    ),
    RFARequest(
        id="rfa_pol_003",
        text=(
            "Admit that {EMPLOYER} had a written progressive discipline "
            "policy in effect during {EMPLOYEE}'s EMPLOYMENT."
        ),
        category="policy_facts",
        rfa_type="fact",
        applicable_roles=("plaintiff",),
        order=12,
    ),
    RFARequest(
        id="rfa_pol_004",
        text=(
            "Admit that {EMPLOYER} provided {EMPLOYEE} with a copy of the "
            "employee handbook at the commencement of EMPLOYMENT."
        ),
        category="policy_facts",
        rfa_type="fact",
        applicable_roles=("plaintiff",),
        order=13,
    ),

    # ===================================================================
    # PLAINTIFF — Complaint Facts (4)
    # ===================================================================
    RFARequest(
        id="rfa_cmp_001",
        text=(
            "Admit that {EMPLOYEE} complained to {EMPLOYER} about "
            "[PROTECTED ACTIVITY] on or about [DATE]."
        ),
        category="complaint_facts",
        rfa_type="fact",
        applicable_roles=("plaintiff",),
        order=14,
    ),
    RFARequest(
        id="rfa_cmp_002",
        text=(
            "Admit that {EMPLOYER} received {EMPLOYEE}'s complaint about "
            "[PROTECTED ACTIVITY] before taking the ADVERSE EMPLOYMENT "
            "ACTION."
        ),
        category="complaint_facts",
        rfa_type="fact",
        applicable_roles=("plaintiff",),
        order=15,
    ),
    RFARequest(
        id="rfa_cmp_003",
        text=(
            "Admit that {EMPLOYER} did not conduct a timely investigation "
            "into {EMPLOYEE}'s complaint about [PROTECTED ACTIVITY]."
        ),
        category="complaint_facts",
        rfa_type="fact",
        applicable_roles=("plaintiff",),
        order=16,
    ),
    RFARequest(
        id="rfa_cmp_004",
        text=(
            "Admit that no corrective action was taken against any "
            "PERSON as a result of {EMPLOYEE}'s complaint about "
            "[PROTECTED ACTIVITY]."
        ),
        category="complaint_facts",
        rfa_type="fact",
        applicable_roles=("plaintiff",),
        order=17,
    ),

    # ===================================================================
    # PLAINTIFF — Wage Facts (4, wage-claim-gated)
    # ===================================================================
    RFARequest(
        id="rfa_wage_001",
        text=(
            "Admit that {EMPLOYEE} was classified as a non-exempt "
            "employee during the EMPLOYMENT."
        ),
        category="wage_facts",
        rfa_type="fact",
        applicable_roles=("plaintiff",),
        applicable_claims=(
            "wage_theft", "meal_rest_break", "overtime", "misclassification",
        ),
        order=18,
    ),
    RFARequest(
        id="rfa_wage_002",
        text=(
            "Admit that {EMPLOYEE} worked more than eight hours in a "
            "workday on at least one occasion during the EMPLOYMENT."
        ),
        category="wage_facts",
        rfa_type="fact",
        applicable_roles=("plaintiff",),
        applicable_claims=(
            "wage_theft", "meal_rest_break", "overtime", "misclassification",
        ),
        order=19,
    ),
    RFARequest(
        id="rfa_wage_003",
        text=(
            "Admit that {EMPLOYER} did not provide {EMPLOYEE} with a "
            "30-minute uninterrupted meal period for each work period "
            "exceeding five hours on at least one occasion during the "
            "EMPLOYMENT."
        ),
        category="wage_facts",
        rfa_type="fact",
        applicable_roles=("plaintiff",),
        applicable_claims=(
            "wage_theft", "meal_rest_break", "overtime", "misclassification",
        ),
        order=20,
    ),
    RFARequest(
        id="rfa_wage_004",
        text=(
            "Admit that {EMPLOYER} did not pay {EMPLOYEE} all wages owed "
            "within the time required by Labor Code sections 201 and "
            "202 upon TERMINATION of EMPLOYMENT."
        ),
        category="wage_facts",
        rfa_type="fact",
        applicable_roles=("plaintiff",),
        applicable_claims=(
            "wage_theft", "meal_rest_break", "overtime", "misclassification",
        ),
        order=21,
    ),

    # ===================================================================
    # SHARED — Document Genuineness (7 — UNLIMITED, not counted toward 35)
    # ===================================================================
    RFARequest(
        id="rfa_doc_001",
        text=(
            "Admit that the DOCUMENT attached hereto as Exhibit [X] is "
            "a true and correct copy of {EMPLOYEE}'s personnel file "
            "maintained by {EMPLOYER}."
        ),
        category="document_genuineness",
        rfa_type="genuineness",
        applicable_roles=("plaintiff", "defendant"),
        order=22,
    ),
    RFARequest(
        id="rfa_doc_002",
        text=(
            "Admit that the DOCUMENT attached hereto as Exhibit [X] is "
            "a true and correct copy of the employee handbook provided "
            "to {EMPLOYEE} during the EMPLOYMENT."
        ),
        category="document_genuineness",
        rfa_type="genuineness",
        applicable_roles=("plaintiff", "defendant"),
        order=23,
    ),
    RFARequest(
        id="rfa_doc_003",
        text=(
            "Admit that the DOCUMENT attached hereto as Exhibit [X] is "
            "a true and correct copy of {EMPLOYEE}'s most recent "
            "performance evaluation."
        ),
        category="document_genuineness",
        rfa_type="genuineness",
        applicable_roles=("plaintiff", "defendant"),
        order=24,
    ),
    RFARequest(
        id="rfa_doc_004",
        text=(
            "Admit that the DOCUMENT attached hereto as Exhibit [X] is "
            "a true and correct copy of the TERMINATION letter or "
            "notice provided to {EMPLOYEE}."
        ),
        category="document_genuineness",
        rfa_type="genuineness",
        applicable_roles=("plaintiff", "defendant"),
        order=25,
    ),
    RFARequest(
        id="rfa_doc_005",
        text=(
            "Admit that the DOCUMENT attached hereto as Exhibit [X] is "
            "a true and correct copy of {EMPLOYER}'s written anti-"
            "discrimination and anti-harassment policy in effect at the "
            "time of the ADVERSE EMPLOYMENT ACTION."
        ),
        category="document_genuineness",
        rfa_type="genuineness",
        applicable_roles=("plaintiff", "defendant"),
        order=26,
    ),
    RFARequest(
        id="rfa_doc_006",
        text=(
            "Admit that the DOCUMENT attached hereto as Exhibit [X] is "
            "a genuine copy and was maintained in the ordinary course "
            "of {EMPLOYER}'s business."
        ),
        category="document_genuineness",
        rfa_type="genuineness",
        applicable_roles=("plaintiff", "defendant"),
        order=27,
    ),
    RFARequest(
        id="rfa_doc_007",
        text=(
            "Admit that the DOCUMENT attached hereto as Exhibit [X] is "
            "a true and correct copy of COMMUNICATIONS sent or received "
            "by {EMPLOYER} concerning {EMPLOYEE}."
        ),
        category="document_genuineness",
        rfa_type="genuineness",
        applicable_roles=("plaintiff", "defendant"),
        order=28,
    ),

    # ===================================================================
    # PLAINTIFF — Discrimination, Harassment, and Retaliation (5, new)
    # ===================================================================
    RFARequest(
        id="rfa_discrim_001",
        text=(
            "Admit that {EMPLOYEE}'s [PROTECTED CHARACTERISTIC] was a "
            "motivating reason for the ADVERSE EMPLOYMENT ACTION taken "
            "against {EMPLOYEE}."
        ),
        category="discrimination_facts",
        rfa_type="fact",
        applicable_roles=("plaintiff",),
        order=29,
    ),
    RFARequest(
        id="rfa_discrim_002",
        text=(
            "Admit that the ADVERSE EMPLOYMENT ACTION against {EMPLOYEE} "
            "occurred within [TIME PERIOD] of {EMPLOYEE}'s engagement in "
            "protected activity."
        ),
        category="discrimination_facts",
        rfa_type="fact",
        applicable_roles=("plaintiff",),
        order=30,
    ),
    RFARequest(
        id="rfa_discrim_003",
        text=(
            "Admit that [ALLEGED HARASSER] made specific statements or "
            "engaged in specific conduct directed at {EMPLOYEE} because "
            "of {EMPLOYEE}'s [PROTECTED CHARACTERISTIC]."
        ),
        category="discrimination_facts",
        rfa_type="fact",
        applicable_roles=("plaintiff",),
        order=31,
    ),
    RFARequest(
        id="rfa_discrim_004",
        text=(
            "Admit that other employees complained about [ALLEGED "
            "HARASSER]'s conduct toward them prior to {EMPLOYEE}'s "
            "complaint."
        ),
        category="discrimination_facts",
        rfa_type="fact",
        applicable_roles=("plaintiff",),
        order=32,
    ),
    RFARequest(
        id="rfa_discrim_005",
        text=(
            "Admit that {EMPLOYER} did not offer {EMPLOYEE} any "
            "alternative position or transfer in lieu of the ADVERSE "
            "EMPLOYMENT ACTION."
        ),
        category="discrimination_facts",
        rfa_type="fact",
        applicable_roles=("plaintiff",),
        order=33,
    ),

    # ===================================================================
    # PLAINTIFF — Comparator and Similar Treatment (3, new)
    # ===================================================================
    RFARequest(
        id="rfa_comparator_001",
        text=(
            "Admit that [COMPARATOR NAME] held the same or substantially "
            "similar position as {EMPLOYEE} at the time of the ADVERSE "
            "EMPLOYMENT ACTION."
        ),
        category="comparator_facts",
        rfa_type="fact",
        applicable_roles=("plaintiff",),
        order=34,
    ),
    RFARequest(
        id="rfa_comparator_002",
        text=(
            "Admit that [COMPARATOR NAME] engaged in the same or similar "
            "conduct as that attributed to {EMPLOYEE} and was not "
            "subjected to the same ADVERSE EMPLOYMENT ACTION."
        ),
        category="comparator_facts",
        rfa_type="fact",
        applicable_roles=("plaintiff",),
        order=35,
    ),
    RFARequest(
        id="rfa_comparator_003",
        text=(
            "Admit that [COMPARATOR NAME] is not a member of the same "
            "protected class as {EMPLOYEE}."
        ),
        category="comparator_facts",
        rfa_type="fact",
        applicable_roles=("plaintiff",),
        order=36,
    ),

    # ===================================================================
    # PLAINTIFF — Damages and Benefits (2, new)
    # ===================================================================
    RFARequest(
        id="rfa_damages_001",
        text=(
            "Admit that {EMPLOYEE}'s annual base salary at the time of "
            "the ADVERSE EMPLOYMENT ACTION was [AMOUNT]."
        ),
        category="damages_facts",
        rfa_type="fact",
        applicable_roles=("plaintiff",),
        order=37,
    ),
    RFARequest(
        id="rfa_damages_002",
        text=(
            "Admit that {EMPLOYEE} was eligible for health insurance, "
            "retirement benefits, and/or bonus compensation at the time "
            "of the ADVERSE EMPLOYMENT ACTION."
        ),
        category="damages_facts",
        rfa_type="fact",
        applicable_roles=("plaintiff",),
        order=38,
    ),

    # ===================================================================
    # PLAINTIFF — Disability Accommodation (3, FEHA-gated, new)
    # ===================================================================
    RFARequest(
        id="rfa_accom_001",
        text=(
            "Admit that {EMPLOYEE} requested a reasonable accommodation "
            "from {EMPLOYER} on or about [DATE]."
        ),
        category="accommodation_facts",
        rfa_type="fact",
        applicable_roles=("plaintiff",),
        applicable_claims=(
            "feha_failure_to_accommodate",
            "feha_failure_interactive_process",
        ),
        order=39,
    ),
    RFARequest(
        id="rfa_accom_002",
        text=(
            "Admit that {EMPLOYER} did not engage in a timely, good-faith "
            "interactive process with {EMPLOYEE} after receiving "
            "{EMPLOYEE}'s request for reasonable accommodation."
        ),
        category="accommodation_facts",
        rfa_type="fact",
        applicable_roles=("plaintiff",),
        applicable_claims=(
            "feha_failure_to_accommodate",
            "feha_failure_interactive_process",
        ),
        order=40,
    ),
    RFARequest(
        id="rfa_accom_003",
        text=(
            "Admit that the accommodation requested by {EMPLOYEE} would "
            "not have imposed an undue hardship on {EMPLOYER}'s operations."
        ),
        category="accommodation_facts",
        rfa_type="fact",
        applicable_roles=("plaintiff",),
        applicable_claims=(
            "feha_failure_to_accommodate",
            "feha_failure_interactive_process",
        ),
        order=41,
    ),

    # ===================================================================
    # DEFENDANT — Performance and Disciplinary History (5, new)
    # ===================================================================
    RFARequest(
        id="rfa_perf_001",
        text=(
            "Admit that YOU received a written warning from {EMPLOYER} "
            "on or about [DATE] regarding [SPECIFIC ISSUE]."
        ),
        category="performance_facts",
        rfa_type="fact",
        applicable_roles=("defendant",),
        order=42,
    ),
    RFARequest(
        id="rfa_perf_002",
        text=(
            "Admit that YOU were verbally counseled by YOUR supervisor "
            "about [SPECIFIC ISSUE] on or about [DATE]."
        ),
        category="performance_facts",
        rfa_type="fact",
        applicable_roles=("defendant",),
        order=43,
    ),
    RFARequest(
        id="rfa_perf_003",
        text=(
            "Admit that YOUR performance evaluation dated [DATE] noted "
            "deficiencies in [SPECIFIC AREA]."
        ),
        category="performance_facts",
        rfa_type="fact",
        applicable_roles=("defendant",),
        order=44,
    ),
    RFARequest(
        id="rfa_perf_004",
        text=(
            "Admit that YOU were aware that [SPECIFIC PERFORMANCE "
            "STANDARD] was a requirement of YOUR position at {EMPLOYER}."
        ),
        category="performance_facts",
        rfa_type="fact",
        applicable_roles=("defendant",),
        order=45,
    ),
    RFARequest(
        id="rfa_perf_005",
        text=(
            "Admit that YOU failed to meet [SPECIFIC METRIC OR STANDARD] "
            "during the period of [DATE RANGE]."
        ),
        category="performance_facts",
        rfa_type="fact",
        applicable_roles=("defendant",),
        order=46,
    ),

    # ===================================================================
    # DEFENDANT — Policies and Complaint Procedures (6, new)
    # ===================================================================
    RFARequest(
        id="rfa_polcomp_001",
        text=(
            "Admit that YOU received a copy of {EMPLOYER}'s employee "
            "handbook during YOUR EMPLOYMENT."
        ),
        category="policies_compliance",
        rfa_type="fact",
        applicable_roles=("defendant",),
        order=47,
    ),
    RFARequest(
        id="rfa_polcomp_002",
        text=(
            "Admit that YOU signed an acknowledgment of receipt of "
            "{EMPLOYER}'s employee handbook."
        ),
        category="policies_compliance",
        rfa_type="fact",
        applicable_roles=("defendant",),
        order=48,
    ),
    RFARequest(
        id="rfa_polcomp_003",
        text=(
            "Admit that {EMPLOYER}'s employee handbook contained an "
            "anti-discrimination and anti-harassment policy."
        ),
        category="policies_compliance",
        rfa_type="fact",
        applicable_roles=("defendant",),
        order=49,
    ),
    RFARequest(
        id="rfa_polcomp_004",
        text=(
            "Admit that {EMPLOYER}'s employee handbook described a "
            "complaint procedure for reporting discrimination, "
            "harassment, or retaliation."
        ),
        category="policies_compliance",
        rfa_type="fact",
        applicable_roles=("defendant",),
        order=50,
    ),
    RFARequest(
        id="rfa_polcomp_005",
        text=(
            "Admit that YOU did not utilize {EMPLOYER}'s internal "
            "complaint procedure to report the conduct alleged in "
            "YOUR complaint prior to the ADVERSE EMPLOYMENT ACTION."
        ),
        category="policies_compliance",
        rfa_type="fact",
        applicable_roles=("defendant",),
        order=51,
    ),
    RFARequest(
        id="rfa_polcomp_006",
        text=(
            "Admit that YOU attended anti-harassment training provided "
            "by {EMPLOYER} during YOUR EMPLOYMENT."
        ),
        category="policies_compliance",
        rfa_type="fact",
        applicable_roles=("defendant",),
        order=52,
    ),

    # ===================================================================
    # DEFENDANT — Legitimate Business Reasons (3, new)
    # ===================================================================
    RFARequest(
        id="rfa_legit_001",
        text=(
            "Admit that [DECISION MAKER NAME] stated that the reason for "
            "the ADVERSE EMPLOYMENT ACTION was [STATED REASON]."
        ),
        category="legitimate_reasons",
        rfa_type="fact",
        applicable_roles=("defendant",),
        order=53,
    ),
    RFARequest(
        id="rfa_legit_002",
        text=(
            "Admit that YOUR supervisor met with YOU to discuss YOUR "
            "performance on or about [DATE]."
        ),
        category="legitimate_reasons",
        rfa_type="fact",
        applicable_roles=("defendant",),
        order=54,
    ),
    RFARequest(
        id="rfa_legit_003",
        text=(
            "Admit that YOU engaged in the specific conduct cited by "
            "{EMPLOYER} as the basis for the ADVERSE EMPLOYMENT ACTION "
            "on or about [DATE]."
        ),
        category="legitimate_reasons",
        rfa_type="fact",
        applicable_roles=("defendant",),
        order=55,
    ),

    # ===================================================================
    # DEFENDANT — Damages Limitations (4, new)
    # ===================================================================
    RFARequest(
        id="rfa_damlim_001",
        text=(
            "Admit that YOU did not seek treatment from a medical doctor "
            "for any physical condition caused by the ADVERSE EMPLOYMENT "
            "ACTION."
        ),
        category="damages_limitations",
        rfa_type="fact",
        applicable_roles=("defendant",),
        order=56,
    ),
    RFARequest(
        id="rfa_damlim_002",
        text=(
            "Admit that YOU did not seek treatment from a mental health "
            "professional for any emotional distress caused by the "
            "ADVERSE EMPLOYMENT ACTION."
        ),
        category="damages_limitations",
        rfa_type="fact",
        applicable_roles=("defendant",),
        order=57,
    ),
    RFARequest(
        id="rfa_damlim_003",
        text=(
            "Admit that YOU experienced symptoms of anxiety or depression "
            "prior to YOUR EMPLOYMENT with {EMPLOYER}."
        ),
        category="damages_limitations",
        rfa_type="fact",
        applicable_roles=("defendant",),
        order=58,
    ),
    RFARequest(
        id="rfa_damlim_004",
        text=(
            "Admit that YOU received unemployment benefits or severance "
            "pay after the TERMINATION of YOUR EMPLOYMENT with {EMPLOYER}."
        ),
        category="damages_limitations",
        rfa_type="fact",
        applicable_roles=("defendant",),
        order=59,
    ),

    # ===================================================================
    # DEFENDANT — Mitigation of Damages (3, new)
    # ===================================================================
    RFARequest(
        id="rfa_mitigation_001",
        text=(
            "Admit that YOU did not apply for any employment during the "
            "[TIME PERIOD] following the ADVERSE EMPLOYMENT ACTION."
        ),
        category="mitigation_facts",
        rfa_type="fact",
        applicable_roles=("defendant",),
        order=60,
    ),
    RFARequest(
        id="rfa_mitigation_002",
        text=(
            "Admit that YOU were offered a position by [EMPLOYER NAME] "
            "and declined the offer."
        ),
        category="mitigation_facts",
        rfa_type="fact",
        applicable_roles=("defendant",),
        order=61,
    ),
    RFARequest(
        id="rfa_mitigation_003",
        text=(
            "Admit that YOU earned income of [AMOUNT] during the twelve "
            "months following the ADVERSE EMPLOYMENT ACTION."
        ),
        category="mitigation_facts",
        rfa_type="fact",
        applicable_roles=("defendant",),
        order=62,
    ),

    # ===================================================================
    # DEFENDANT — Prior Employment and Claims (3, new)
    # ===================================================================
    RFARequest(
        id="rfa_priorclaim_001",
        text=(
            "Admit that YOU filed a complaint, charge, or lawsuit against "
            "a prior employer alleging discrimination, harassment, or "
            "retaliation."
        ),
        category="prior_claims",
        rfa_type="fact",
        applicable_roles=("defendant",),
        order=63,
    ),
    RFARequest(
        id="rfa_priorclaim_002",
        text=(
            "Admit that YOUR EMPLOYMENT with [PRIOR EMPLOYER NAME] was "
            "terminated."
        ),
        category="prior_claims",
        rfa_type="fact",
        applicable_roles=("defendant",),
        order=64,
    ),
    RFARequest(
        id="rfa_priorclaim_003",
        text=(
            "Admit that YOU did not disclose [SPECIFIC FACT] on YOUR "
            "employment application with {EMPLOYER}."
        ),
        category="prior_claims",
        rfa_type="fact",
        applicable_roles=("defendant",),
        order=65,
    ),

    # ===================================================================
    # DEFENDANT — Lack of Direct Evidence (2, new)
    # ===================================================================
    RFARequest(
        id="rfa_direct_001",
        text=(
            "Admit that no PERSON made any statement to YOU expressly "
            "referencing YOUR [PROTECTED CHARACTERISTIC] as a reason "
            "for the ADVERSE EMPLOYMENT ACTION."
        ),
        category="direct_evidence",
        rfa_type="fact",
        applicable_roles=("defendant",),
        order=66,
    ),
    RFARequest(
        id="rfa_direct_002",
        text=(
            "Admit that no PERSON made any derogatory comment about YOUR "
            "[PROTECTED CHARACTERISTIC] in YOUR presence during YOUR "
            "EMPLOYMENT with {EMPLOYER}."
        ),
        category="direct_evidence",
        rfa_type="fact",
        applicable_roles=("defendant",),
        order=67,
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
