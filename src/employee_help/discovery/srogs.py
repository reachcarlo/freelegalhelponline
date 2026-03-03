"""Special Interrogatories (SROGs) request bank for California employment law.

Contains ~35 employment-specific interrogatories organized by category.
The guided workflow pre-selects categories based on claim type, and
attorneys can add/remove individual interrogatories.

CCP 2030.030: Maximum 35 specially prepared interrogatories without
a CCP 2030.050 Declaration of Necessity.

Pure data — no DB, no ML, no external services.
"""

from __future__ import annotations

from .models import DiscoveryRequest, SROG_LIMIT


# ---------------------------------------------------------------------------
# Category definitions
# ---------------------------------------------------------------------------

SROG_CATEGORIES: dict[str, str] = {
    "employment_relationship": "Employment Relationship",
    "adverse_action": "Adverse Employment Actions",
    "comparator_treatment": "Comparator / Similarly Situated Employees",
    "decision_makers": "Decision Makers",
    "investigation": "Investigation and Complaints",
    "policies": "Policies and Procedures",
    "damages": "Damages",
    "wages_hours": "Wages and Hours",
}


# ---------------------------------------------------------------------------
# Request bank
# ---------------------------------------------------------------------------

SROG_BANK: list[DiscoveryRequest] = [
    # --- Employment Relationship (4) ---
    DiscoveryRequest(
        id="srog_emp_001",
        text=(
            "State the date on which EMPLOYEE's EMPLOYMENT with EMPLOYER "
            "commenced, each job title held by EMPLOYEE, and the dates "
            "EMPLOYEE held each such title."
        ),
        category="employment_relationship",
        order=1,
    ),
    DiscoveryRequest(
        id="srog_emp_002",
        text=(
            "IDENTIFY each supervisor of EMPLOYEE during the EMPLOYMENT, "
            "including the dates of each supervisory relationship and each "
            "supervisor's job title."
        ),
        category="employment_relationship",
        order=2,
    ),
    DiscoveryRequest(
        id="srog_emp_003",
        text=(
            "State EMPLOYEE's compensation at each stage of the EMPLOYMENT, "
            "including base salary or hourly rate, bonuses, commissions, and "
            "any other forms of compensation, and the dates of any changes."
        ),
        category="employment_relationship",
        order=3,
    ),
    DiscoveryRequest(
        id="srog_emp_004",
        text=(
            "State the terms and conditions of EMPLOYEE's EMPLOYMENT, "
            "including whether the EMPLOYMENT was at-will, governed by a "
            "written or oral contract, or subject to a collective bargaining "
            "agreement."
        ),
        category="employment_relationship",
        order=4,
    ),

    # --- Adverse Employment Actions (6) ---
    DiscoveryRequest(
        id="srog_adv_001",
        text=(
            "State the name, job title, and job duties of each PERSON who "
            "participated in, recommended, or approved the decision to take "
            "each ADVERSE EMPLOYMENT ACTION against EMPLOYEE."
        ),
        category="adverse_action",
        order=5,
    ),
    DiscoveryRequest(
        id="srog_adv_002",
        text=(
            "IDENTIFY all DOCUMENTS that YOU reviewed, considered, or relied "
            "upon in making the decision to take each ADVERSE EMPLOYMENT "
            "ACTION against EMPLOYEE."
        ),
        category="adverse_action",
        order=6,
    ),
    DiscoveryRequest(
        id="srog_adv_003",
        text=(
            "State with specificity each reason for each ADVERSE EMPLOYMENT "
            "ACTION taken against EMPLOYEE, including all facts supporting "
            "each stated reason."
        ),
        category="adverse_action",
        order=7,
    ),
    DiscoveryRequest(
        id="srog_adv_004",
        text=(
            "State the date on which the decision was first made to take "
            "each ADVERSE EMPLOYMENT ACTION against EMPLOYEE, and IDENTIFY "
            "each PERSON involved in making that decision."
        ),
        category="adverse_action",
        order=8,
    ),
    DiscoveryRequest(
        id="srog_adv_005",
        text=(
            "State whether EMPLOYEE was given any warnings, written or oral, "
            "prior to each ADVERSE EMPLOYMENT ACTION, and for each warning "
            "state the date, the substance, and the PERSON who gave it."
        ),
        category="adverse_action",
        order=9,
    ),
    DiscoveryRequest(
        id="srog_adv_006",
        text=(
            "State whether EMPLOYER followed its own policies and procedures "
            "in taking each ADVERSE EMPLOYMENT ACTION against EMPLOYEE, and "
            "if not, explain each deviation."
        ),
        category="adverse_action",
        order=10,
    ),

    # --- Comparator Treatment (4) ---
    DiscoveryRequest(
        id="srog_comp_001",
        text=(
            "IDENTIFY each PERSON who held the same or a similar job title "
            "as EMPLOYEE during the two years preceding EMPLOYEE's "
            "TERMINATION, and state the dates of their employment and "
            "their protected characteristics, if known."
        ),
        category="comparator_treatment",
        order=11,
    ),
    DiscoveryRequest(
        id="srog_comp_002",
        text=(
            "For each similarly situated employee identified in the preceding "
            "interrogatory, state whether that PERSON was subjected to any "
            "ADVERSE EMPLOYMENT ACTION for conduct similar to that attributed "
            "to EMPLOYEE, and if so, describe the action taken."
        ),
        category="comparator_treatment",
        order=12,
    ),
    DiscoveryRequest(
        id="srog_comp_003",
        text=(
            "IDENTIFY each PERSON who was hired, promoted, or transferred "
            "into EMPLOYEE's former position after each ADVERSE EMPLOYMENT "
            "ACTION, and state their qualifications, protected characteristics, "
            "compensation, and the date of hire, promotion, or transfer."
        ),
        category="comparator_treatment",
        order=13,
    ),
    DiscoveryRequest(
        id="srog_comp_004",
        text=(
            "State whether any other employees who engaged in conduct similar "
            "to the conduct attributed to EMPLOYEE as a basis for the ADVERSE "
            "EMPLOYMENT ACTION were treated differently, and if so, describe "
            "how they were treated and IDENTIFY each such employee."
        ),
        category="comparator_treatment",
        order=14,
    ),

    # --- Decision Makers (3) ---
    DiscoveryRequest(
        id="srog_dec_001",
        text=(
            "IDENTIFY each PERSON who had authority to hire, discipline, "
            "demote, promote, or terminate EMPLOYEE at any time during the "
            "EMPLOYMENT."
        ),
        category="decision_makers",
        order=15,
    ),
    DiscoveryRequest(
        id="srog_dec_002",
        text=(
            "State whether any PERSON who participated in the decision to "
            "take ADVERSE EMPLOYMENT ACTION against EMPLOYEE made any "
            "COMMUNICATIONS regarding EMPLOYEE's protected characteristics, "
            "and for each such COMMUNICATION, state the date, substance, "
            "speaker, and recipient(s)."
        ),
        category="decision_makers",
        order=16,
    ),
    DiscoveryRequest(
        id="srog_dec_003",
        text=(
            "For each PERSON who participated in any ADVERSE EMPLOYMENT "
            "ACTION against EMPLOYEE, state whether that PERSON is still "
            "employed by EMPLOYER, and if not, state the date and reason "
            "for separation."
        ),
        category="decision_makers",
        order=17,
    ),

    # --- Investigation and Complaints (5) ---
    DiscoveryRequest(
        id="srog_inv_001",
        text=(
            "State whether EMPLOYEE made any complaints, whether written or "
            "oral, to EMPLOYER RELATING TO discrimination, harassment, "
            "retaliation, or any other unlawful conduct, and for each "
            "complaint state the date, manner, recipient, and substance."
        ),
        category="investigation",
        order=18,
    ),
    DiscoveryRequest(
        id="srog_inv_002",
        text=(
            "For each complaint identified in the preceding interrogatory, "
            "state what investigation, if any, EMPLOYER conducted, IDENTIFY "
            "each PERSON who participated in the investigation, and state "
            "the findings and conclusions reached."
        ),
        category="investigation",
        order=19,
    ),
    DiscoveryRequest(
        id="srog_inv_003",
        text=(
            "State whether EMPLOYER received any complaints from other "
            "employees about the same PERSON(S) who are alleged to have "
            "engaged in the conduct giving rise to this action, and for "
            "each such complaint, state the date, the complainant, and "
            "the substance."
        ),
        category="investigation",
        order=20,
    ),
    DiscoveryRequest(
        id="srog_inv_004",
        text=(
            "State whether any corrective or disciplinary action was taken "
            "against any PERSON as a result of any investigation into "
            "EMPLOYEE's complaints, and for each action, state the date, "
            "the PERSON disciplined, and the nature of the action."
        ),
        category="investigation",
        order=21,
    ),
    DiscoveryRequest(
        id="srog_inv_005",
        text=(
            "State whether EMPLOYEE filed any complaint with the Department "
            "of Fair Employment and Housing (now Civil Rights Department), "
            "the Equal Employment Opportunity Commission, or any other "
            "governmental agency RELATING TO the conduct giving rise to "
            "this action, and for each filing state the date, agency, "
            "and case or charge number."
        ),
        category="investigation",
        order=22,
    ),

    # --- Policies and Procedures (4) ---
    DiscoveryRequest(
        id="srog_pol_001",
        text=(
            "IDENTIFY each written policy, handbook, manual, guideline, "
            "or procedure that applied to EMPLOYEE's EMPLOYMENT, including "
            "the date(s) each was in effect and the custodian of each "
            "DOCUMENT."
        ),
        category="policies",
        order=23,
    ),
    DiscoveryRequest(
        id="srog_pol_002",
        text=(
            "State whether EMPLOYER had a written anti-discrimination, "
            "anti-harassment, or anti-retaliation policy in effect during "
            "EMPLOYEE's EMPLOYMENT, and if so, describe the complaint "
            "procedure set forth therein."
        ),
        category="policies",
        order=24,
    ),
    DiscoveryRequest(
        id="srog_pol_003",
        text=(
            "State whether EMPLOYER provided EMPLOYEE with training on "
            "its anti-discrimination, anti-harassment, or anti-retaliation "
            "policies, and if so, state the date(s), type, and duration "
            "of each training."
        ),
        category="policies",
        order=25,
    ),
    DiscoveryRequest(
        id="srog_pol_004",
        text=(
            "State whether EMPLOYER's policies and procedures regarding "
            "discipline and TERMINATION were applied consistently to all "
            "employees in EMPLOYEE's department or position, and if not, "
            "describe each inconsistency."
        ),
        category="policies",
        order=26,
    ),

    # --- Damages (4) ---
    DiscoveryRequest(
        id="srog_dam_001",
        text=(
            "State the total amount of economic damages YOU contend EMPLOYEE "
            "has suffered as a result of each ADVERSE EMPLOYMENT ACTION, "
            "broken down by category (lost wages, lost benefits, out-of-pocket "
            "expenses, and any other economic loss)."
        ),
        category="damages",
        order=27,
    ),
    DiscoveryRequest(
        id="srog_dam_002",
        text=(
            "State whether EMPLOYEE has sought or obtained other employment "
            "since the ADVERSE EMPLOYMENT ACTION, and for each such "
            "employment, state the employer's name, job title, start date, "
            "and compensation."
        ),
        category="damages",
        order=28,
    ),
    DiscoveryRequest(
        id="srog_dam_003",
        text=(
            "IDENTIFY each HEALTH CARE PROVIDER from whom EMPLOYEE has "
            "received treatment for any physical, mental, or emotional "
            "condition attributed to the ADVERSE EMPLOYMENT ACTION, and "
            "state the dates and nature of treatment."
        ),
        category="damages",
        order=29,
    ),
    DiscoveryRequest(
        id="srog_dam_004",
        text=(
            "State the total amount of non-economic damages YOU contend "
            "EMPLOYEE has suffered, including emotional distress, "
            "humiliation, and loss of enjoyment of life, and describe the "
            "factual basis for each category."
        ),
        category="damages",
        order=30,
    ),

    # --- Wages and Hours (5) ---
    DiscoveryRequest(
        id="srog_wage_001",
        text=(
            "State EMPLOYEE's classification as exempt or non-exempt under "
            "the applicable Wage Order during each period of the EMPLOYMENT, "
            "and state the basis for each classification."
        ),
        category="wages_hours",
        order=31,
    ),
    DiscoveryRequest(
        id="srog_wage_002",
        text=(
            "State the number of hours EMPLOYEE was scheduled to work each "
            "week, the hours actually worked, and whether EMPLOYEE was "
            "compensated for all hours worked, including overtime."
        ),
        category="wages_hours",
        order=32,
    ),
    DiscoveryRequest(
        id="srog_wage_003",
        text=(
            "State whether EMPLOYEE was provided with all meal periods and "
            "rest breaks required by law, and if not, state each date on "
            "which a meal period or rest break was missed, shortened, or "
            "interrupted, and the circumstances."
        ),
        category="wages_hours",
        order=33,
    ),
    DiscoveryRequest(
        id="srog_wage_004",
        text=(
            "State the total amount of unpaid wages, overtime premiums, "
            "meal period premiums, rest break premiums, and waiting time "
            "penalties YOU contend are owed to EMPLOYEE, and state how "
            "each amount was calculated."
        ),
        category="wages_hours",
        order=34,
    ),
    DiscoveryRequest(
        id="srog_wage_005",
        text=(
            "IDENTIFY each PERSON responsible for tracking, recording, "
            "or approving EMPLOYEE's work hours, and state the method "
            "used to record EMPLOYEE's time worked."
        ),
        category="wages_hours",
        order=35,
    ),
]


def get_srog_bank() -> list[DiscoveryRequest]:
    """Return a copy of the full SROG request bank."""
    return list(SROG_BANK)


def get_srogs_by_category(category: str) -> list[DiscoveryRequest]:
    """Return SROGs for a specific category."""
    return [r for r in SROG_BANK if r.category == category]


def get_srogs_for_categories(
    categories: list[str] | tuple[str, ...],
) -> list[DiscoveryRequest]:
    """Return SROGs matching any of the given categories, in order."""
    cat_set = set(categories)
    return [r for r in SROG_BANK if r.category in cat_set]


def count_selected(requests: list[DiscoveryRequest]) -> int:
    """Count the number of selected (is_selected=True) requests."""
    return sum(1 for r in requests if r.is_selected)


def exceeds_limit(requests: list[DiscoveryRequest]) -> bool:
    """Check if selected requests exceed the 35 SROG limit."""
    return count_selected(requests) > SROG_LIMIT


def needs_declaration(requests: list[DiscoveryRequest]) -> bool:
    """Check if a CCP 2030.050 Declaration of Necessity is required."""
    return exceeds_limit(requests)
