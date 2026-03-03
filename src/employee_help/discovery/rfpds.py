"""Requests for Production of Documents (RFPDs) bank for California employment law.

Contains ~28 employment-specific document requests organized by category.
RFPDs have no numeric limit (CCP 2031.030 does not impose one).

Pure data — no DB, no ML, no external services.
"""

from __future__ import annotations

from .models import DiscoveryRequest


# ---------------------------------------------------------------------------
# Category definitions
# ---------------------------------------------------------------------------

RFPD_CATEGORIES: dict[str, str] = {
    "personnel_file": "Personnel Records",
    "performance_reviews": "Performance Evaluations",
    "discipline_records": "Discipline and Corrective Actions",
    "termination_docs": "Termination / Adverse Action Documents",
    "policies_handbooks": "Policies and Handbooks",
    "investigation_docs": "Investigation Documents",
    "communications": "Communications",
    "comparator_docs": "Comparator / Similarly Situated Employees",
    "compensation_records": "Compensation and Payroll Records",
    "timekeeping": "Time Records",
    "training_records": "Training Records",
    "job_descriptions": "Job Descriptions and Organizational",
    "organizational": "Organizational Charts and Structure",
    "insurance": "Insurance",
}


# ---------------------------------------------------------------------------
# Request bank
# ---------------------------------------------------------------------------

RFPD_BANK: list[DiscoveryRequest] = [
    # --- Personnel Records (3) ---
    DiscoveryRequest(
        id="rfpd_pers_001",
        text=(
            "All DOCUMENTS constituting, evidencing, or RELATING TO the "
            "EMPLOYEE's complete personnel file, including but not limited to "
            "the employment application, resume, offer letter, and all "
            "documents required to be maintained pursuant to Labor Code "
            "section 1198.5."
        ),
        category="personnel_file",
        order=1,
    ),
    DiscoveryRequest(
        id="rfpd_pers_002",
        text=(
            "All DOCUMENTS RELATING TO any benefits provided to EMPLOYEE "
            "during the EMPLOYMENT, including health insurance, retirement "
            "plans, stock options, bonuses, and any other employee benefits."
        ),
        category="personnel_file",
        order=2,
    ),
    DiscoveryRequest(
        id="rfpd_pers_003",
        text=(
            "All DOCUMENTS RELATING TO EMPLOYEE's immigration status, "
            "work authorization, or I-9 Employment Eligibility Verification "
            "form maintained during the EMPLOYMENT."
        ),
        category="personnel_file",
        order=3,
    ),

    # --- Performance Evaluations (2) ---
    DiscoveryRequest(
        id="rfpd_perf_001",
        text=(
            "All DOCUMENTS constituting, evidencing, or RELATING TO any "
            "performance evaluation, review, assessment, or rating of "
            "EMPLOYEE during the entire period of EMPLOYMENT."
        ),
        category="performance_reviews",
        order=4,
    ),
    DiscoveryRequest(
        id="rfpd_perf_002",
        text=(
            "All DOCUMENTS RELATING TO any commendation, award, recognition, "
            "or positive feedback given to EMPLOYEE during the EMPLOYMENT."
        ),
        category="performance_reviews",
        order=5,
    ),

    # --- Discipline Records (2) ---
    DiscoveryRequest(
        id="rfpd_disc_001",
        text=(
            "All DOCUMENTS constituting, evidencing, or RELATING TO any "
            "warning, reprimand, counseling, or other disciplinary action "
            "taken against EMPLOYEE during the EMPLOYMENT."
        ),
        category="discipline_records",
        order=6,
    ),
    DiscoveryRequest(
        id="rfpd_disc_002",
        text=(
            "All DOCUMENTS RELATING TO any performance improvement plan "
            "(PIP) or corrective action plan issued to EMPLOYEE during "
            "the EMPLOYMENT."
        ),
        category="discipline_records",
        order=7,
    ),

    # --- Termination / Adverse Action Documents (3) ---
    DiscoveryRequest(
        id="rfpd_term_001",
        text=(
            "All DOCUMENTS constituting, evidencing, or RELATING TO the "
            "decision to take each ADVERSE EMPLOYMENT ACTION against "
            "EMPLOYEE, including all memoranda, notes, emails, and other "
            "COMMUNICATIONS discussing or recommending the action."
        ),
        category="termination_docs",
        order=8,
    ),
    DiscoveryRequest(
        id="rfpd_term_002",
        text=(
            "All DOCUMENTS constituting or RELATING TO any separation "
            "agreement, severance agreement, release, or waiver presented "
            "to EMPLOYEE in connection with the TERMINATION."
        ),
        category="termination_docs",
        order=9,
    ),
    DiscoveryRequest(
        id="rfpd_term_003",
        text=(
            "All DOCUMENTS RELATING TO the notification of EMPLOYEE's "
            "TERMINATION, including any COBRA notices, final pay stubs, "
            "and any DOCUMENTS provided to EMPLOYEE at the time of "
            "TERMINATION."
        ),
        category="termination_docs",
        order=10,
    ),

    # --- Policies and Handbooks (3) ---
    DiscoveryRequest(
        id="rfpd_pol_001",
        text=(
            "All employee handbooks, policy manuals, and codes of conduct "
            "in effect during any part of EMPLOYEE's EMPLOYMENT, including "
            "all revisions and amendments."
        ),
        category="policies_handbooks",
        order=11,
    ),
    DiscoveryRequest(
        id="rfpd_pol_002",
        text=(
            "All DOCUMENTS constituting EMPLOYER's policies and procedures "
            "RELATING TO anti-discrimination, anti-harassment, anti-retaliation, "
            "equal employment opportunity, and complaint procedures in effect "
            "during any part of EMPLOYEE's EMPLOYMENT."
        ),
        category="policies_handbooks",
        order=12,
    ),
    DiscoveryRequest(
        id="rfpd_pol_003",
        text=(
            "All DOCUMENTS constituting EMPLOYER's policies and procedures "
            "RELATING TO discipline, progressive discipline, and TERMINATION "
            "in effect during any part of EMPLOYEE's EMPLOYMENT."
        ),
        category="policies_handbooks",
        order=13,
    ),

    # --- Investigation Documents (3) ---
    DiscoveryRequest(
        id="rfpd_inv_001",
        text=(
            "All DOCUMENTS constituting, evidencing, or RELATING TO any "
            "investigation conducted by EMPLOYER or any third party into "
            "any complaint, grievance, or allegation made by EMPLOYEE."
        ),
        category="investigation_docs",
        order=14,
    ),
    DiscoveryRequest(
        id="rfpd_inv_002",
        text=(
            "All DOCUMENTS constituting, evidencing, or RELATING TO any "
            "investigation conducted by EMPLOYER into allegations of "
            "discrimination, harassment, or retaliation involving the same "
            "department, supervisor, or alleged perpetrator as in this action."
        ),
        category="investigation_docs",
        order=15,
    ),
    DiscoveryRequest(
        id="rfpd_inv_003",
        text=(
            "All DOCUMENTS RELATING TO any complaint or charge filed by "
            "EMPLOYEE with any governmental agency, including all "
            "correspondence, position statements, and responses submitted "
            "by EMPLOYER."
        ),
        category="investigation_docs",
        order=16,
    ),

    # --- Communications (2) ---
    DiscoveryRequest(
        id="rfpd_comm_001",
        text=(
            "All COMMUNICATIONS between any agents, employees, or "
            "representatives of EMPLOYER RELATING TO EMPLOYEE, the "
            "ADVERSE EMPLOYMENT ACTION, or the subject matter of this "
            "action, for the period beginning one year before the first "
            "ADVERSE EMPLOYMENT ACTION through the present."
        ),
        category="communications",
        order=17,
    ),
    DiscoveryRequest(
        id="rfpd_comm_002",
        text=(
            "All COMMUNICATIONS between EMPLOYER and EMPLOYEE during the "
            "last six months of EMPLOYMENT, including but not limited to "
            "emails, text messages, instant messages, and written memoranda."
        ),
        category="communications",
        order=18,
    ),

    # --- Comparator Documents (2) ---
    DiscoveryRequest(
        id="rfpd_comp_001",
        text=(
            "All DOCUMENTS RELATING TO other employees who held the same or "
            "similar position as EMPLOYEE and who were subjected to "
            "discipline or TERMINATION within two years of EMPLOYEE's "
            "ADVERSE EMPLOYMENT ACTION, including the disciplinary records "
            "and reasons for action."
        ),
        category="comparator_docs",
        order=19,
    ),
    DiscoveryRequest(
        id="rfpd_comp_002",
        text=(
            "All DOCUMENTS RELATING TO the qualifications, experience, and "
            "performance of any PERSON who was selected for the position "
            "or opportunity that EMPLOYEE contends was denied on a "
            "discriminatory or retaliatory basis."
        ),
        category="comparator_docs",
        order=20,
    ),

    # --- Compensation and Payroll (3) ---
    DiscoveryRequest(
        id="rfpd_pay_001",
        text=(
            "All DOCUMENTS RELATING TO EMPLOYEE's compensation, including "
            "pay stubs, wage statements, W-2 forms, 1099 forms, and any "
            "DOCUMENTS showing payments made to EMPLOYEE during the "
            "EMPLOYMENT."
        ),
        category="compensation_records",
        order=21,
    ),
    DiscoveryRequest(
        id="rfpd_pay_002",
        text=(
            "All DOCUMENTS RELATING TO EMPLOYER's pay scales, salary "
            "ranges, and compensation structures for the position(s) held "
            "by EMPLOYEE and comparable positions."
        ),
        category="compensation_records",
        order=22,
    ),
    DiscoveryRequest(
        id="rfpd_pay_003",
        text=(
            "All DOCUMENTS RELATING TO any bonus, commission, incentive, "
            "or other variable compensation paid or owed to EMPLOYEE."
        ),
        category="compensation_records",
        order=23,
    ),

    # --- Time Records (1) ---
    DiscoveryRequest(
        id="rfpd_time_001",
        text=(
            "All DOCUMENTS RELATING TO EMPLOYEE's work hours, including "
            "time cards, time sheets, electronic time records, scheduling "
            "records, and any DOCUMENTS showing hours worked, meal periods, "
            "and rest breaks taken by EMPLOYEE."
        ),
        category="timekeeping",
        order=24,
    ),

    # --- Training Records (1) ---
    DiscoveryRequest(
        id="rfpd_train_001",
        text=(
            "All DOCUMENTS RELATING TO any training provided to EMPLOYEE "
            "or to EMPLOYEE's supervisors on anti-discrimination, "
            "anti-harassment, anti-retaliation, reasonable accommodation, "
            "or related employment law topics."
        ),
        category="training_records",
        order=25,
    ),

    # --- Job Descriptions (1) ---
    DiscoveryRequest(
        id="rfpd_job_001",
        text=(
            "All DOCUMENTS constituting or RELATING TO the job description, "
            "essential functions, and qualifications for each position held "
            "by EMPLOYEE during the EMPLOYMENT."
        ),
        category="job_descriptions",
        order=26,
    ),

    # --- Organizational (1) ---
    DiscoveryRequest(
        id="rfpd_org_001",
        text=(
            "All organizational charts, reporting structures, and chain "
            "of command DOCUMENTS for EMPLOYEE's department or division "
            "during the EMPLOYMENT."
        ),
        category="organizational",
        order=27,
    ),

    # --- Insurance (1) ---
    DiscoveryRequest(
        id="rfpd_ins_001",
        text=(
            "All DOCUMENTS constituting, evidencing, or RELATING TO any "
            "insurance policy that may provide coverage for the claims "
            "alleged in this action, including the declarations page, "
            "policy limits, and any reservation of rights letters."
        ),
        category="insurance",
        order=28,
    ),
]


def get_rfpd_bank() -> list[DiscoveryRequest]:
    """Return a copy of the full RFPD request bank."""
    return list(RFPD_BANK)


def get_rfpds_by_category(category: str) -> list[DiscoveryRequest]:
    """Return RFPDs for a specific category."""
    return [r for r in RFPD_BANK if r.category == category]


def get_rfpds_for_categories(
    categories: list[str] | tuple[str, ...],
) -> list[DiscoveryRequest]:
    """Return RFPDs matching any of the given categories, in order."""
    cat_set = set(categories)
    return [r for r in RFPD_BANK if r.category in cat_set]
