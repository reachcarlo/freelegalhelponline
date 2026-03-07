"""Special Interrogatories (SROGs) request bank for California employment law.

Contains role-aware employment-specific interrogatories organized by category.
Plaintiff-side, defendant-side, and shared requests are all in one bank;
filtering by role happens via filter functions in filters.py.

CCP 2030.030: Maximum 35 specially prepared interrogatories without
a CCP 2030.050 Declaration of Necessity.

Pure data — no DB, no ML, no external services.
"""

from __future__ import annotations

from .models import DiscoveryRequest, SROG_LIMIT


# ---------------------------------------------------------------------------
# Category definitions (16 categories)
# ---------------------------------------------------------------------------

SROG_CATEGORIES: dict[str, str] = {
    # Shared
    "employment_relationship": "Employment Relationship",
    # Plaintiff
    "adverse_action": "Adverse Employment Actions",
    "comparator_treatment": "Comparator / Similarly Situated Employees",
    "decision_makers": "Decision Makers",
    "investigation": "Investigation and Complaints",
    "policies": "Policies and Procedures",
    "damages": "Damages",
    "wages_hours": "Wages and Hours",
    "contention_interrogatories": "Contention Interrogatories (Affirmative Defenses)",
    "accommodation": "Accommodation and Interactive Process",
    "communications": "Communications",
    # Defendant
    "factual_basis": "Factual Basis for Claims",
    "emotional_distress": "Emotional Distress and Medical Treatment",
    "mitigation": "Mitigation of Damages",
    "prior_employment": "Prior Employment and Claims History",
    "social_media_recordings": "Social Media, Communications, and Recordings",
}


# ---------------------------------------------------------------------------
# Request bank
# ---------------------------------------------------------------------------

SROG_BANK: list[DiscoveryRequest] = [
    # ===================================================================
    # SHARED — Employment Relationship (4)
    # ===================================================================
    DiscoveryRequest(
        id="srog_emp_001",
        text=(
            "State the date on which {EMPLOYEE}'s EMPLOYMENT with {EMPLOYER} "
            "commenced, each job title held by {EMPLOYEE}, and the dates "
            "{EMPLOYEE} held each such title."
        ),
        category="employment_relationship",
        applicable_roles=("plaintiff", "defendant"),
        order=1,
    ),
    DiscoveryRequest(
        id="srog_emp_002",
        text=(
            "IDENTIFY each supervisor of {EMPLOYEE} during the EMPLOYMENT, "
            "including the dates of each supervisory relationship and each "
            "supervisor's job title."
        ),
        category="employment_relationship",
        applicable_roles=("plaintiff", "defendant"),
        order=2,
    ),
    DiscoveryRequest(
        id="srog_emp_003",
        text=(
            "State {EMPLOYEE}'s compensation at each stage of the EMPLOYMENT, "
            "including base salary or hourly rate, bonuses, commissions, and "
            "any other forms of compensation, and the dates of any changes."
        ),
        category="employment_relationship",
        applicable_roles=("plaintiff", "defendant"),
        order=3,
    ),
    DiscoveryRequest(
        id="srog_emp_004",
        text=(
            "State the terms and conditions of {EMPLOYEE}'s EMPLOYMENT, "
            "including whether the EMPLOYMENT was at-will, governed by a "
            "written or oral contract, or subject to a collective bargaining "
            "agreement."
        ),
        category="employment_relationship",
        applicable_roles=("plaintiff", "defendant"),
        order=4,
    ),

    # ===================================================================
    # PLAINTIFF — Adverse Employment Actions (6)
    # ===================================================================
    DiscoveryRequest(
        id="srog_adv_001",
        text=(
            "State the name, job title, and job duties of each PERSON who "
            "participated in, recommended, or approved the decision to take "
            "each ADVERSE EMPLOYMENT ACTION against {EMPLOYEE}."
        ),
        category="adverse_action",
        applicable_roles=("plaintiff",),
        order=5,
    ),
    DiscoveryRequest(
        id="srog_adv_002",
        text=(
            "IDENTIFY all DOCUMENTS that YOU reviewed, considered, or relied "
            "upon in making the decision to take each ADVERSE EMPLOYMENT "
            "ACTION against {EMPLOYEE}."
        ),
        category="adverse_action",
        applicable_roles=("plaintiff",),
        order=6,
    ),
    DiscoveryRequest(
        id="srog_adv_003",
        text=(
            "State with specificity each reason for each ADVERSE EMPLOYMENT "
            "ACTION taken against {EMPLOYEE}, including all facts supporting "
            "each stated reason."
        ),
        category="adverse_action",
        applicable_roles=("plaintiff",),
        order=7,
    ),
    DiscoveryRequest(
        id="srog_adv_004",
        text=(
            "State the date on which the decision was first made to take "
            "each ADVERSE EMPLOYMENT ACTION against {EMPLOYEE}, and IDENTIFY "
            "each PERSON involved in making that decision."
        ),
        category="adverse_action",
        applicable_roles=("plaintiff",),
        order=8,
    ),
    DiscoveryRequest(
        id="srog_adv_005",
        text=(
            "State whether {EMPLOYEE} was given any warnings, written or oral, "
            "prior to each ADVERSE EMPLOYMENT ACTION, and for each warning "
            "state the date, the substance, and the PERSON who gave it."
        ),
        category="adverse_action",
        applicable_roles=("plaintiff",),
        order=9,
    ),
    DiscoveryRequest(
        id="srog_adv_006",
        text=(
            "State whether {EMPLOYER} followed its own policies and procedures "
            "in taking each ADVERSE EMPLOYMENT ACTION against {EMPLOYEE}, and "
            "if not, explain each deviation."
        ),
        category="adverse_action",
        applicable_roles=("plaintiff",),
        order=10,
    ),

    # ===================================================================
    # PLAINTIFF — Comparator Treatment (4)
    # ===================================================================
    DiscoveryRequest(
        id="srog_comp_001",
        text=(
            "IDENTIFY each PERSON who held the same or a similar job title "
            "as {EMPLOYEE} during the two years preceding {EMPLOYEE}'s "
            "TERMINATION, and state the dates of their employment and "
            "their protected characteristics, if known."
        ),
        category="comparator_treatment",
        applicable_roles=("plaintiff",),
        order=11,
    ),
    DiscoveryRequest(
        id="srog_comp_002",
        text=(
            "For each similarly situated employee identified in the preceding "
            "interrogatory, state whether that PERSON was subjected to any "
            "ADVERSE EMPLOYMENT ACTION for conduct similar to that attributed "
            "to {EMPLOYEE}, and if so, describe the action taken."
        ),
        category="comparator_treatment",
        applicable_roles=("plaintiff",),
        order=12,
    ),
    DiscoveryRequest(
        id="srog_comp_003",
        text=(
            "IDENTIFY each PERSON who was hired, promoted, or transferred "
            "into {EMPLOYEE}'s former position after each ADVERSE EMPLOYMENT "
            "ACTION, and state their qualifications, protected characteristics, "
            "compensation, and the date of hire, promotion, or transfer."
        ),
        category="comparator_treatment",
        applicable_roles=("plaintiff",),
        order=13,
    ),
    DiscoveryRequest(
        id="srog_comp_004",
        text=(
            "State whether any other employees who engaged in conduct similar "
            "to the conduct attributed to {EMPLOYEE} as a basis for the ADVERSE "
            "EMPLOYMENT ACTION were treated differently, and if so, describe "
            "how they were treated and IDENTIFY each such employee."
        ),
        category="comparator_treatment",
        applicable_roles=("plaintiff",),
        order=14,
    ),

    # ===================================================================
    # PLAINTIFF — Decision Makers (3)
    # ===================================================================
    DiscoveryRequest(
        id="srog_dec_001",
        text=(
            "IDENTIFY each PERSON who had authority to hire, discipline, "
            "demote, promote, or terminate {EMPLOYEE} at any time during the "
            "EMPLOYMENT."
        ),
        category="decision_makers",
        applicable_roles=("plaintiff",),
        order=15,
    ),
    DiscoveryRequest(
        id="srog_dec_002",
        text=(
            "State whether any PERSON who participated in the decision to "
            "take ADVERSE EMPLOYMENT ACTION against {EMPLOYEE} made any "
            "COMMUNICATIONS regarding {EMPLOYEE}'s protected characteristics, "
            "and for each such COMMUNICATION, state the date, substance, "
            "speaker, and recipient(s)."
        ),
        category="decision_makers",
        applicable_roles=("plaintiff",),
        order=16,
    ),
    DiscoveryRequest(
        id="srog_dec_003",
        text=(
            "For each PERSON who participated in any ADVERSE EMPLOYMENT "
            "ACTION against {EMPLOYEE}, state whether that PERSON is still "
            "employed by {EMPLOYER}, and if not, state the date and reason "
            "for separation."
        ),
        category="decision_makers",
        applicable_roles=("plaintiff",),
        order=17,
    ),

    # ===================================================================
    # PLAINTIFF — Investigation and Complaints (5)
    # ===================================================================
    DiscoveryRequest(
        id="srog_inv_001",
        text=(
            "State whether {EMPLOYEE} made any complaints, whether written or "
            "oral, to {EMPLOYER} RELATING TO discrimination, harassment, "
            "retaliation, or any other unlawful conduct, and for each "
            "complaint state the date, manner, recipient, and substance."
        ),
        category="investigation",
        applicable_roles=("plaintiff",),
        order=18,
    ),
    DiscoveryRequest(
        id="srog_inv_002",
        text=(
            "For each complaint identified in the preceding interrogatory, "
            "state what investigation, if any, {EMPLOYER} conducted, IDENTIFY "
            "each PERSON who participated in the investigation, and state "
            "the findings and conclusions reached."
        ),
        category="investigation",
        applicable_roles=("plaintiff",),
        order=19,
    ),
    DiscoveryRequest(
        id="srog_inv_003",
        text=(
            "State whether {EMPLOYER} received any complaints from other "
            "employees about the same PERSON(S) who are alleged to have "
            "engaged in the conduct giving rise to this action, and for "
            "each such complaint, state the date, the complainant, and "
            "the substance."
        ),
        category="investigation",
        applicable_roles=("plaintiff",),
        order=20,
    ),
    DiscoveryRequest(
        id="srog_inv_004",
        text=(
            "State whether any corrective or disciplinary action was taken "
            "against any PERSON as a result of any investigation into "
            "{EMPLOYEE}'s complaints, and for each action, state the date, "
            "the PERSON disciplined, and the nature of the action."
        ),
        category="investigation",
        applicable_roles=("plaintiff",),
        order=21,
    ),
    DiscoveryRequest(
        id="srog_inv_005",
        text=(
            "State whether {EMPLOYEE} filed any complaint with the Department "
            "of Fair Employment and Housing (now Civil Rights Department), "
            "the Equal Employment Opportunity Commission, or any other "
            "governmental agency RELATING TO the conduct giving rise to "
            "this action, and for each filing state the date, agency, "
            "and case or charge number."
        ),
        category="investigation",
        applicable_roles=("plaintiff",),
        order=22,
    ),

    # ===================================================================
    # PLAINTIFF — Policies and Procedures (4)
    # ===================================================================
    DiscoveryRequest(
        id="srog_pol_001",
        text=(
            "IDENTIFY each written policy, handbook, manual, guideline, "
            "or procedure that applied to {EMPLOYEE}'s EMPLOYMENT, including "
            "the date(s) each was in effect and the custodian of each "
            "DOCUMENT."
        ),
        category="policies",
        applicable_roles=("plaintiff",),
        order=23,
    ),
    DiscoveryRequest(
        id="srog_pol_002",
        text=(
            "State whether {EMPLOYER} had a written anti-discrimination, "
            "anti-harassment, or anti-retaliation policy in effect during "
            "{EMPLOYEE}'s EMPLOYMENT, and if so, describe the complaint "
            "procedure set forth therein."
        ),
        category="policies",
        applicable_roles=("plaintiff",),
        order=24,
    ),
    DiscoveryRequest(
        id="srog_pol_003",
        text=(
            "State whether {EMPLOYER} provided {EMPLOYEE} with training on "
            "its anti-discrimination, anti-harassment, or anti-retaliation "
            "policies, and if so, state the date(s), type, and duration "
            "of each training."
        ),
        category="policies",
        applicable_roles=("plaintiff",),
        order=25,
    ),
    DiscoveryRequest(
        id="srog_pol_004",
        text=(
            "State whether {EMPLOYER}'s policies and procedures regarding "
            "discipline and TERMINATION were applied consistently to all "
            "employees in {EMPLOYEE}'s department or position, and if not, "
            "describe each inconsistency."
        ),
        category="policies",
        applicable_roles=("plaintiff",),
        order=26,
    ),

    # ===================================================================
    # PLAINTIFF — Damages (4)
    # ===================================================================
    DiscoveryRequest(
        id="srog_dam_001",
        text=(
            "State the total amount of economic damages YOU contend {EMPLOYEE} "
            "has suffered as a result of each ADVERSE EMPLOYMENT ACTION, "
            "broken down by category (lost wages, lost benefits, out-of-pocket "
            "expenses, and any other economic loss)."
        ),
        category="damages",
        applicable_roles=("plaintiff",),
        order=27,
    ),
    DiscoveryRequest(
        id="srog_dam_002",
        text=(
            "State whether {EMPLOYEE} has sought or obtained other employment "
            "since the ADVERSE EMPLOYMENT ACTION, and for each such "
            "employment, state the employer's name, job title, start date, "
            "and compensation."
        ),
        category="damages",
        applicable_roles=("plaintiff",),
        order=28,
    ),
    DiscoveryRequest(
        id="srog_dam_003",
        text=(
            "IDENTIFY each HEALTH CARE PROVIDER from whom {EMPLOYEE} has "
            "received treatment for any physical, mental, or emotional "
            "condition attributed to the ADVERSE EMPLOYMENT ACTION, and "
            "state the dates and nature of treatment."
        ),
        category="damages",
        applicable_roles=("plaintiff",),
        order=29,
    ),
    DiscoveryRequest(
        id="srog_dam_004",
        text=(
            "State the total amount of non-economic damages YOU contend "
            "{EMPLOYEE} has suffered, including emotional distress, "
            "humiliation, and loss of enjoyment of life, and describe the "
            "factual basis for each category."
        ),
        category="damages",
        applicable_roles=("plaintiff",),
        order=30,
    ),

    # ===================================================================
    # PLAINTIFF — Wages and Hours (5, wage-claim-gated)
    # ===================================================================
    DiscoveryRequest(
        id="srog_wage_001",
        text=(
            "State {EMPLOYEE}'s classification as exempt or non-exempt under "
            "the applicable Wage Order during each period of the EMPLOYMENT, "
            "and state the basis for each classification."
        ),
        category="wages_hours",
        applicable_roles=("plaintiff",),
        applicable_claims=(
            "wage_theft", "meal_rest_break", "overtime", "misclassification",
        ),
        order=31,
    ),
    DiscoveryRequest(
        id="srog_wage_002",
        text=(
            "State the number of hours {EMPLOYEE} was scheduled to work each "
            "week, the hours actually worked, and whether {EMPLOYEE} was "
            "compensated for all hours worked, including overtime."
        ),
        category="wages_hours",
        applicable_roles=("plaintiff",),
        applicable_claims=(
            "wage_theft", "meal_rest_break", "overtime", "misclassification",
        ),
        order=32,
    ),
    DiscoveryRequest(
        id="srog_wage_003",
        text=(
            "State whether {EMPLOYEE} was provided with all meal periods and "
            "rest breaks required by law, and if not, state each date on "
            "which a meal period or rest break was missed, shortened, or "
            "interrupted, and the circumstances."
        ),
        category="wages_hours",
        applicable_roles=("plaintiff",),
        applicable_claims=(
            "wage_theft", "meal_rest_break", "overtime", "misclassification",
        ),
        order=33,
    ),
    DiscoveryRequest(
        id="srog_wage_004",
        text=(
            "State the total amount of unpaid wages, overtime premiums, "
            "meal period premiums, rest break premiums, and waiting time "
            "penalties YOU contend are owed to {EMPLOYEE}, and state how "
            "each amount was calculated."
        ),
        category="wages_hours",
        applicable_roles=("plaintiff",),
        applicable_claims=(
            "wage_theft", "meal_rest_break", "overtime", "misclassification",
        ),
        order=34,
    ),
    DiscoveryRequest(
        id="srog_wage_005",
        text=(
            "IDENTIFY each PERSON responsible for tracking, recording, "
            "or approving {EMPLOYEE}'s work hours, and state the method "
            "used to record {EMPLOYEE}'s time worked."
        ),
        category="wages_hours",
        applicable_roles=("plaintiff",),
        applicable_claims=(
            "wage_theft", "meal_rest_break", "overtime", "misclassification",
        ),
        order=35,
    ),

    # ===================================================================
    # PLAINTIFF — Contention Interrogatories (3, new)
    # ===================================================================
    DiscoveryRequest(
        id="srog_cont_001",
        text=(
            "State ALL FACTS upon which YOU contend that the ADVERSE "
            "EMPLOYMENT ACTION taken against {EMPLOYEE} was for the stated "
            "legitimate business reason(s), including the identity of each "
            "PERSON with knowledge of such facts."
        ),
        category="contention_interrogatories",
        applicable_roles=("plaintiff",),
        order=36,
    ),
    DiscoveryRequest(
        id="srog_cont_002",
        text=(
            "State ALL FACTS supporting each affirmative defense asserted "
            "in YOUR answer to {EMPLOYEE}'s complaint, including the identity "
            "of each PERSON with knowledge of such facts and each DOCUMENT "
            "that supports the defense."
        ),
        category="contention_interrogatories",
        applicable_roles=("plaintiff",),
        order=37,
    ),
    DiscoveryRequest(
        id="srog_cont_003",
        text=(
            "State ALL FACTS supporting YOUR contention that {EMPLOYER} "
            "took all reasonable steps necessary to prevent the "
            "discrimination, harassment, and/or retaliation alleged in "
            "this action, including the identity of each PERSON responsible "
            "for implementing such steps."
        ),
        category="contention_interrogatories",
        applicable_roles=("plaintiff",),
        order=38,
    ),

    # ===================================================================
    # PLAINTIFF — Accommodation and Interactive Process (2, FEHA-gated, new)
    # ===================================================================
    DiscoveryRequest(
        id="srog_accom_001",
        text=(
            "Describe every step {EMPLOYER} took to engage in the interactive "
            "process with {EMPLOYEE} after learning of {EMPLOYEE}'s need for "
            "reasonable accommodation, including the date of each step, the "
            "PERSON(S) involved, and the substance of each communication."
        ),
        category="accommodation",
        applicable_roles=("plaintiff",),
        applicable_claims=(
            "feha_failure_to_accommodate",
            "feha_failure_interactive_process",
        ),
        order=39,
    ),
    DiscoveryRequest(
        id="srog_accom_002",
        text=(
            "IDENTIFY every accommodation considered by {EMPLOYER} for "
            "{EMPLOYEE}, and for each accommodation, state whether it was "
            "provided or denied, the reason for any denial, and the PERSON "
            "who made the decision."
        ),
        category="accommodation",
        applicable_roles=("plaintiff",),
        applicable_claims=(
            "feha_failure_to_accommodate",
            "feha_failure_interactive_process",
        ),
        order=40,
    ),

    # ===================================================================
    # PLAINTIFF — Communications (3, new)
    # ===================================================================
    DiscoveryRequest(
        id="srog_comm_001",
        text=(
            "IDENTIFY all COMMUNICATIONS between any decision-maker involved "
            "in the ADVERSE EMPLOYMENT ACTION against {EMPLOYEE} and any "
            "other PERSON concerning {EMPLOYEE}'s performance, complaints, "
            "accommodation requests, or protected activity, and for each "
            "COMMUNICATION state the date, participants, and substance."
        ),
        category="communications",
        applicable_roles=("plaintiff",),
        order=41,
    ),
    DiscoveryRequest(
        id="srog_comm_002",
        text=(
            "IDENTIFY all COMMUNICATIONS between any agent, employee, or "
            "representative of {EMPLOYER} and any outside PERSON or entity "
            "concerning {EMPLOYEE}'s TERMINATION, the claims in this action, "
            "or the events giving rise to this action."
        ),
        category="communications",
        applicable_roles=("plaintiff",),
        order=42,
    ),
    DiscoveryRequest(
        id="srog_comm_003",
        text=(
            "IDENTIFY any PERSON who expressed disagreement with, objection "
            "to, or concern about the decision to take the ADVERSE "
            "EMPLOYMENT ACTION against {EMPLOYEE}, and for each such PERSON "
            "state the date, manner, and substance of the disagreement."
        ),
        category="communications",
        applicable_roles=("plaintiff",),
        order=43,
    ),

    # ===================================================================
    # DEFENDANT — Factual Basis for Claims (4, new)
    # ===================================================================
    DiscoveryRequest(
        id="srog_fact_001",
        text=(
            "State ALL FACTS upon which YOU base each cause of action "
            "alleged against {EMPLOYER} in YOUR complaint, including the "
            "identity of each PERSON with knowledge of such facts."
        ),
        category="factual_basis",
        applicable_roles=("defendant",),
        order=44,
    ),
    DiscoveryRequest(
        id="srog_fact_002",
        text=(
            "For each instance of discrimination, harassment, or retaliation "
            "alleged in YOUR complaint, state the date, location, PERSON(S) "
            "involved, and describe specifically what was said or done."
        ),
        category="factual_basis",
        applicable_roles=("defendant",),
        order=45,
    ),
    DiscoveryRequest(
        id="srog_fact_003",
        text=(
            "IDENTIFY each PERSON who made any statement reflecting "
            "discriminatory animus toward YOU or YOUR protected "
            "characteristic, and for each such statement, state the date, "
            "the exact words used, and the identity of all witnesses."
        ),
        category="factual_basis",
        applicable_roles=("defendant",),
        order=46,
    ),
    DiscoveryRequest(
        id="srog_fact_004",
        text=(
            "State ALL FACTS supporting YOUR contention that {EMPLOYER}'s "
            "stated reason for the ADVERSE EMPLOYMENT ACTION was pretextual, "
            "including the identity of each PERSON with knowledge of such "
            "facts and each DOCUMENT supporting the contention."
        ),
        category="factual_basis",
        applicable_roles=("defendant",),
        order=47,
    ),

    # ===================================================================
    # DEFENDANT — Emotional Distress and Medical Treatment (4, new)
    # ===================================================================
    DiscoveryRequest(
        id="srog_emo_001",
        text=(
            "Describe each symptom of emotional distress YOU contend was "
            "caused by the ADVERSE EMPLOYMENT ACTION, including the date "
            "each symptom first appeared and whether the symptom continues "
            "to the present."
        ),
        category="emotional_distress",
        applicable_roles=("defendant",),
        order=48,
    ),
    DiscoveryRequest(
        id="srog_emo_002",
        text=(
            "IDENTIFY each HEALTH CARE PROVIDER from whom YOU have received "
            "treatment for any emotional or mental health condition during "
            "the five years preceding YOUR EMPLOYMENT with {EMPLOYER} "
            "through the present, and state the dates, nature, and frequency "
            "of treatment."
        ),
        category="emotional_distress",
        applicable_roles=("defendant",),
        order=49,
    ),
    DiscoveryRequest(
        id="srog_emo_003",
        text=(
            "IDENTIFY each prescription medication YOU have taken for any "
            "emotional or mental health condition during the period beginning "
            "five years before YOUR EMPLOYMENT with {EMPLOYER} through the "
            "present, and state the prescribing provider, dates, dosage, "
            "and condition treated."
        ),
        category="emotional_distress",
        applicable_roles=("defendant",),
        order=50,
    ),
    DiscoveryRequest(
        id="srog_emo_004",
        text=(
            "State whether YOU were diagnosed with or treated for any "
            "emotional or mental health condition prior to YOUR EMPLOYMENT "
            "with {EMPLOYER}, and if so, state the condition, the date of "
            "diagnosis, and the treating provider."
        ),
        category="emotional_distress",
        applicable_roles=("defendant",),
        order=51,
    ),

    # ===================================================================
    # DEFENDANT — Mitigation of Damages (3, new)
    # ===================================================================
    DiscoveryRequest(
        id="srog_mit_001",
        text=(
            "IDENTIFY every employer or potential employer to which YOU "
            "applied for employment from the date of the ADVERSE EMPLOYMENT "
            "ACTION through the present, and for each, state the date of "
            "application, position applied for, and outcome."
        ),
        category="mitigation",
        applicable_roles=("defendant",),
        order=52,
    ),
    DiscoveryRequest(
        id="srog_mit_002",
        text=(
            "IDENTIFY every source of income YOU have received from the "
            "date of the ADVERSE EMPLOYMENT ACTION through the present, "
            "including employment income, unemployment benefits, disability "
            "benefits, severance pay, and any other source, and state the "
            "amount received from each source."
        ),
        category="mitigation",
        applicable_roles=("defendant",),
        order=53,
    ),
    DiscoveryRequest(
        id="srog_mit_003",
        text=(
            "State whether YOU declined or failed to pursue any employment "
            "opportunity from the date of the ADVERSE EMPLOYMENT ACTION "
            "through the present, and for each such opportunity, describe "
            "the position, the employer, and the reason for not pursuing it."
        ),
        category="mitigation",
        applicable_roles=("defendant",),
        order=54,
    ),

    # ===================================================================
    # DEFENDANT — Prior Employment and Claims History (2, new)
    # ===================================================================
    DiscoveryRequest(
        id="srog_prior_001",
        text=(
            "IDENTIFY every employer for which YOU worked during the ten "
            "years preceding YOUR EMPLOYMENT with {EMPLOYER}, and for each, "
            "state YOUR job title, dates of employment, compensation, and "
            "reason for leaving."
        ),
        category="prior_employment",
        applicable_roles=("defendant",),
        order=55,
    ),
    DiscoveryRequest(
        id="srog_prior_002",
        text=(
            "State whether YOU have ever filed a lawsuit, administrative "
            "charge, workers' compensation claim, or grievance against any "
            "prior employer, and for each, state the employer, the date "
            "filed, the nature of the claim, the forum, and the outcome."
        ),
        category="prior_employment",
        applicable_roles=("defendant",),
        order=56,
    ),

    # ===================================================================
    # DEFENDANT — Social Media, Communications, and Recordings (2, new)
    # ===================================================================
    DiscoveryRequest(
        id="srog_social_001",
        text=(
            "IDENTIFY all social media accounts (including but not limited "
            "to Facebook, Instagram, Twitter/X, LinkedIn, TikTok, and "
            "Snapchat) maintained by YOU during the period beginning one "
            "year before the ADVERSE EMPLOYMENT ACTION through the present."
        ),
        category="social_media_recordings",
        applicable_roles=("defendant",),
        order=57,
    ),
    DiscoveryRequest(
        id="srog_social_002",
        text=(
            "State whether YOU made any audio recording, video recording, "
            "or photograph of any event, conversation, or condition alleged "
            "in YOUR complaint, and for each, describe the date, subject "
            "matter, PERSON(S) recorded, and current custodian."
        ),
        category="social_media_recordings",
        applicable_roles=("defendant",),
        order=58,
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
