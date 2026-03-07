"""Requests for Production of Documents (RFPDs) bank for California employment law.

Contains role-aware employment-specific document requests organized by category.
Plaintiff-side, defendant-side, and shared requests are all in one bank;
filtering by role happens via filter functions in filters.py.

RFPDs have no numeric limit (CCP 2031.030 does not impose one).

Pure data — no DB, no ML, no external services.
"""

from __future__ import annotations

from .models import DiscoveryRequest


# ---------------------------------------------------------------------------
# Category definitions (24 categories)
# ---------------------------------------------------------------------------

RFPD_CATEGORIES: dict[str, str] = {
    # Plaintiff (existing)
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
    # Plaintiff (new)
    "esi": "Electronically Stored Information",
    "litigation_hold": "Litigation Hold and Preservation",
    "accommodation_docs": "Reasonable Accommodation Documents",
    # Defendant (new)
    "medical_records": "Medical and Therapy Records",
    "financial_records": "Financial Records and Tax Returns",
    "job_search_docs": "Job Search and Mitigation Documents",
    "prior_employment_docs": "Prior Employment Records",
    "personal_records": "Diaries, Journals, and Personal Notes",
    "social_media_docs": "Social Media and Recordings",
    "govt_agency_docs": "Government Agency Communications",
}


# ---------------------------------------------------------------------------
# Request bank
# ---------------------------------------------------------------------------

RFPD_BANK: list[DiscoveryRequest] = [
    # ===================================================================
    # PLAINTIFF — Personnel Records (3)
    # ===================================================================
    DiscoveryRequest(
        id="rfpd_pers_001",
        text=(
            "All DOCUMENTS constituting, evidencing, or RELATING TO the "
            "{EMPLOYEE}'s complete personnel file, including but not limited to "
            "the employment application, resume, offer letter, and all "
            "documents required to be maintained pursuant to Labor Code "
            "section 1198.5."
        ),
        category="personnel_file",
        applicable_roles=("plaintiff",),
        order=1,
    ),
    DiscoveryRequest(
        id="rfpd_pers_002",
        text=(
            "All DOCUMENTS RELATING TO any benefits provided to {EMPLOYEE} "
            "during the EMPLOYMENT, including health insurance, retirement "
            "plans, stock options, bonuses, and any other employee benefits."
        ),
        category="personnel_file",
        applicable_roles=("plaintiff",),
        order=2,
    ),
    DiscoveryRequest(
        id="rfpd_pers_003",
        text=(
            "All DOCUMENTS RELATING TO {EMPLOYEE}'s immigration status, "
            "work authorization, or I-9 Employment Eligibility Verification "
            "form maintained during the EMPLOYMENT."
        ),
        category="personnel_file",
        applicable_roles=("plaintiff",),
        order=3,
    ),

    # ===================================================================
    # PLAINTIFF — Performance Evaluations (2)
    # ===================================================================
    DiscoveryRequest(
        id="rfpd_perf_001",
        text=(
            "All DOCUMENTS constituting, evidencing, or RELATING TO any "
            "performance evaluation, review, assessment, or rating of "
            "{EMPLOYEE} during the entire period of EMPLOYMENT."
        ),
        category="performance_reviews",
        applicable_roles=("plaintiff",),
        order=4,
    ),
    DiscoveryRequest(
        id="rfpd_perf_002",
        text=(
            "All DOCUMENTS RELATING TO any commendation, award, recognition, "
            "or positive feedback given to {EMPLOYEE} during the EMPLOYMENT."
        ),
        category="performance_reviews",
        applicable_roles=("plaintiff",),
        order=5,
    ),

    # ===================================================================
    # PLAINTIFF — Discipline and Corrective Actions (2)
    # ===================================================================
    DiscoveryRequest(
        id="rfpd_disc_001",
        text=(
            "All DOCUMENTS constituting, evidencing, or RELATING TO any "
            "warning, reprimand, counseling, or other disciplinary action "
            "taken against {EMPLOYEE} during the EMPLOYMENT."
        ),
        category="discipline_records",
        applicable_roles=("plaintiff",),
        order=6,
    ),
    DiscoveryRequest(
        id="rfpd_disc_002",
        text=(
            "All DOCUMENTS RELATING TO any performance improvement plan "
            "(PIP) or corrective action plan issued to {EMPLOYEE} during "
            "the EMPLOYMENT."
        ),
        category="discipline_records",
        applicable_roles=("plaintiff",),
        order=7,
    ),

    # ===================================================================
    # PLAINTIFF — Termination / Adverse Action Documents (3)
    # ===================================================================
    DiscoveryRequest(
        id="rfpd_term_001",
        text=(
            "All DOCUMENTS constituting, evidencing, or RELATING TO the "
            "decision to take each ADVERSE EMPLOYMENT ACTION against "
            "{EMPLOYEE}, including all memoranda, notes, emails, and other "
            "COMMUNICATIONS discussing or recommending the action."
        ),
        category="termination_docs",
        applicable_roles=("plaintiff",),
        order=8,
    ),
    DiscoveryRequest(
        id="rfpd_term_002",
        text=(
            "All DOCUMENTS constituting or RELATING TO any separation "
            "agreement, severance agreement, release, or waiver presented "
            "to {EMPLOYEE} in connection with the TERMINATION."
        ),
        category="termination_docs",
        applicable_roles=("plaintiff",),
        order=9,
    ),
    DiscoveryRequest(
        id="rfpd_term_003",
        text=(
            "All DOCUMENTS RELATING TO the notification of {EMPLOYEE}'s "
            "TERMINATION, including any COBRA notices, final pay stubs, "
            "and any DOCUMENTS provided to {EMPLOYEE} at the time of "
            "TERMINATION."
        ),
        category="termination_docs",
        applicable_roles=("plaintiff",),
        order=10,
    ),

    # ===================================================================
    # PLAINTIFF — Policies and Handbooks (3)
    # ===================================================================
    DiscoveryRequest(
        id="rfpd_pol_001",
        text=(
            "All employee handbooks, policy manuals, and codes of conduct "
            "in effect during any part of {EMPLOYEE}'s EMPLOYMENT, including "
            "all revisions and amendments."
        ),
        category="policies_handbooks",
        applicable_roles=("plaintiff",),
        order=11,
    ),
    DiscoveryRequest(
        id="rfpd_pol_002",
        text=(
            "All DOCUMENTS constituting {EMPLOYER}'s policies and procedures "
            "RELATING TO anti-discrimination, anti-harassment, anti-retaliation, "
            "equal employment opportunity, and complaint procedures in effect "
            "during any part of {EMPLOYEE}'s EMPLOYMENT."
        ),
        category="policies_handbooks",
        applicable_roles=("plaintiff",),
        order=12,
    ),
    DiscoveryRequest(
        id="rfpd_pol_003",
        text=(
            "All DOCUMENTS constituting {EMPLOYER}'s policies and procedures "
            "RELATING TO discipline, progressive discipline, and TERMINATION "
            "in effect during any part of {EMPLOYEE}'s EMPLOYMENT."
        ),
        category="policies_handbooks",
        applicable_roles=("plaintiff",),
        order=13,
    ),

    # ===================================================================
    # PLAINTIFF — Investigation Documents (3)
    # ===================================================================
    DiscoveryRequest(
        id="rfpd_inv_001",
        text=(
            "All DOCUMENTS constituting, evidencing, or RELATING TO any "
            "investigation conducted by {EMPLOYER} or any third party into "
            "any complaint, grievance, or allegation made by {EMPLOYEE}."
        ),
        category="investigation_docs",
        applicable_roles=("plaintiff",),
        order=14,
    ),
    DiscoveryRequest(
        id="rfpd_inv_002",
        text=(
            "All DOCUMENTS constituting, evidencing, or RELATING TO any "
            "investigation conducted by {EMPLOYER} into allegations of "
            "discrimination, harassment, or retaliation involving the same "
            "department, supervisor, or alleged perpetrator as in this action."
        ),
        category="investigation_docs",
        applicable_roles=("plaintiff",),
        order=15,
    ),
    DiscoveryRequest(
        id="rfpd_inv_003",
        text=(
            "All DOCUMENTS RELATING TO any complaint or charge filed by "
            "{EMPLOYEE} with any governmental agency, including all "
            "correspondence, position statements, and responses submitted "
            "by {EMPLOYER}."
        ),
        category="investigation_docs",
        applicable_roles=("plaintiff",),
        order=16,
    ),

    # ===================================================================
    # PLAINTIFF — Communications (2)
    # ===================================================================
    DiscoveryRequest(
        id="rfpd_comm_001",
        text=(
            "All COMMUNICATIONS between any agents, employees, or "
            "representatives of {EMPLOYER} RELATING TO {EMPLOYEE}, the "
            "ADVERSE EMPLOYMENT ACTION, or the subject matter of this "
            "action, for the period beginning one year before the first "
            "ADVERSE EMPLOYMENT ACTION through the present."
        ),
        category="communications",
        applicable_roles=("plaintiff",),
        order=17,
    ),
    DiscoveryRequest(
        id="rfpd_comm_002",
        text=(
            "All COMMUNICATIONS between {EMPLOYER} and {EMPLOYEE} during the "
            "last six months of EMPLOYMENT, including but not limited to "
            "emails, text messages, instant messages, and written memoranda."
        ),
        category="communications",
        applicable_roles=("plaintiff",),
        order=18,
    ),

    # ===================================================================
    # PLAINTIFF — Comparator Documents (2)
    # ===================================================================
    DiscoveryRequest(
        id="rfpd_comp_001",
        text=(
            "All DOCUMENTS RELATING TO other employees who held the same or "
            "similar position as {EMPLOYEE} and who were subjected to "
            "discipline or TERMINATION within two years of {EMPLOYEE}'s "
            "ADVERSE EMPLOYMENT ACTION, including the disciplinary records "
            "and reasons for action."
        ),
        category="comparator_docs",
        applicable_roles=("plaintiff",),
        order=19,
    ),
    DiscoveryRequest(
        id="rfpd_comp_002",
        text=(
            "All DOCUMENTS RELATING TO the qualifications, experience, and "
            "performance of any PERSON who was selected for the position "
            "or opportunity that {EMPLOYEE} contends was denied on a "
            "discriminatory or retaliatory basis."
        ),
        category="comparator_docs",
        applicable_roles=("plaintiff",),
        order=20,
    ),

    # ===================================================================
    # PLAINTIFF — Compensation and Payroll (3)
    # ===================================================================
    DiscoveryRequest(
        id="rfpd_pay_001",
        text=(
            "All DOCUMENTS RELATING TO {EMPLOYEE}'s compensation, including "
            "pay stubs, wage statements, W-2 forms, 1099 forms, and any "
            "DOCUMENTS showing payments made to {EMPLOYEE} during the "
            "EMPLOYMENT."
        ),
        category="compensation_records",
        applicable_roles=("plaintiff",),
        order=21,
    ),
    DiscoveryRequest(
        id="rfpd_pay_002",
        text=(
            "All DOCUMENTS RELATING TO {EMPLOYER}'s pay scales, salary "
            "ranges, and compensation structures for the position(s) held "
            "by {EMPLOYEE} and comparable positions."
        ),
        category="compensation_records",
        applicable_roles=("plaintiff",),
        order=22,
    ),
    DiscoveryRequest(
        id="rfpd_pay_003",
        text=(
            "All DOCUMENTS RELATING TO any bonus, commission, incentive, "
            "or other variable compensation paid or owed to {EMPLOYEE}."
        ),
        category="compensation_records",
        applicable_roles=("plaintiff",),
        order=23,
    ),

    # ===================================================================
    # PLAINTIFF — Time Records (1, wage-claim-gated)
    # ===================================================================
    DiscoveryRequest(
        id="rfpd_time_001",
        text=(
            "All DOCUMENTS RELATING TO {EMPLOYEE}'s work hours, including "
            "time cards, time sheets, electronic time records, scheduling "
            "records, and any DOCUMENTS showing hours worked, meal periods, "
            "and rest breaks taken by {EMPLOYEE}."
        ),
        category="timekeeping",
        applicable_roles=("plaintiff",),
        applicable_claims=(
            "wage_theft", "meal_rest_break", "overtime", "misclassification",
        ),
        order=24,
    ),

    # ===================================================================
    # PLAINTIFF — Training Records (1)
    # ===================================================================
    DiscoveryRequest(
        id="rfpd_train_001",
        text=(
            "All DOCUMENTS RELATING TO any training provided to {EMPLOYEE} "
            "or to {EMPLOYEE}'s supervisors on anti-discrimination, "
            "anti-harassment, anti-retaliation, reasonable accommodation, "
            "or related employment law topics."
        ),
        category="training_records",
        applicable_roles=("plaintiff",),
        order=25,
    ),

    # ===================================================================
    # PLAINTIFF — Job Descriptions (1)
    # ===================================================================
    DiscoveryRequest(
        id="rfpd_job_001",
        text=(
            "All DOCUMENTS constituting or RELATING TO the job description, "
            "essential functions, and qualifications for each position held "
            "by {EMPLOYEE} during the EMPLOYMENT."
        ),
        category="job_descriptions",
        applicable_roles=("plaintiff",),
        order=26,
    ),

    # ===================================================================
    # PLAINTIFF — Organizational (1)
    # ===================================================================
    DiscoveryRequest(
        id="rfpd_org_001",
        text=(
            "All organizational charts, reporting structures, and chain "
            "of command DOCUMENTS for {EMPLOYEE}'s department or division "
            "during the EMPLOYMENT."
        ),
        category="organizational",
        applicable_roles=("plaintiff",),
        order=27,
    ),

    # ===================================================================
    # PLAINTIFF — Insurance (1)
    # ===================================================================
    DiscoveryRequest(
        id="rfpd_ins_001",
        text=(
            "All DOCUMENTS constituting, evidencing, or RELATING TO any "
            "insurance policy that may provide coverage for the claims "
            "alleged in this action, including the declarations page, "
            "policy limits, and any reservation of rights letters."
        ),
        category="insurance",
        applicable_roles=("plaintiff",),
        order=28,
    ),

    # ===================================================================
    # PLAINTIFF — ESI (2, new)
    # ===================================================================
    DiscoveryRequest(
        id="rfpd_esi_001",
        text=(
            "All electronically stored information in native format with "
            "metadata intact, including but not limited to emails, text "
            "messages, instant messages, voicemails, and any digital "
            "COMMUNICATIONS RELATING TO {EMPLOYEE} or the claims in "
            "this action."
        ),
        category="esi",
        applicable_roles=("plaintiff",),
        order=29,
    ),
    DiscoveryRequest(
        id="rfpd_esi_002",
        text=(
            "All electronic access logs, system audit trails, and metadata "
            "showing access to, modification of, or deletion of any "
            "DOCUMENTS RELATING TO {EMPLOYEE} or the ADVERSE EMPLOYMENT "
            "ACTION."
        ),
        category="esi",
        applicable_roles=("plaintiff",),
        order=30,
    ),

    # ===================================================================
    # PLAINTIFF — Litigation Hold and Preservation (1, new)
    # ===================================================================
    DiscoveryRequest(
        id="rfpd_lithold_001",
        text=(
            "All litigation hold notices, preservation directives, and "
            "COMMUNICATIONS RELATING TO the preservation of evidence in "
            "connection with {EMPLOYEE}'s claims or this action."
        ),
        category="litigation_hold",
        applicable_roles=("plaintiff",),
        order=31,
    ),

    # ===================================================================
    # PLAINTIFF — Accommodation Documents (3, FEHA-gated, new)
    # ===================================================================
    DiscoveryRequest(
        id="rfpd_accom_001",
        text=(
            "All DOCUMENTS RELATING TO any request for reasonable "
            "accommodation made by {EMPLOYEE}, including all COMMUNICATIONS "
            "between {EMPLOYEE} and {EMPLOYER} regarding the accommodation "
            "request and the interactive process."
        ),
        category="accommodation_docs",
        applicable_roles=("plaintiff",),
        applicable_claims=(
            "feha_failure_to_accommodate",
            "feha_failure_interactive_process",
        ),
        order=32,
    ),
    DiscoveryRequest(
        id="rfpd_accom_002",
        text=(
            "All DOCUMENTS RELATING TO {EMPLOYER}'s evaluation of "
            "{EMPLOYEE}'s ability to perform the essential functions of "
            "{EMPLOYEE}'s position with or without reasonable accommodation."
        ),
        category="accommodation_docs",
        applicable_roles=("plaintiff",),
        applicable_claims=(
            "feha_failure_to_accommodate",
            "feha_failure_interactive_process",
        ),
        order=33,
    ),
    DiscoveryRequest(
        id="rfpd_accom_003",
        text=(
            "All DOCUMENTS RELATING TO accommodations provided to other "
            "employees at the same facility or in the same position as "
            "{EMPLOYEE} during the two years preceding {EMPLOYEE}'s "
            "accommodation request through the present."
        ),
        category="accommodation_docs",
        applicable_roles=("plaintiff",),
        applicable_claims=(
            "feha_failure_to_accommodate",
            "feha_failure_interactive_process",
        ),
        order=34,
    ),

    # ===================================================================
    # DEFENDANT — Medical and Therapy Records (3, new)
    # ===================================================================
    DiscoveryRequest(
        id="rfpd_med_001",
        text=(
            "All DOCUMENTS RELATING TO any medical, psychological, "
            "psychiatric, or counseling treatment YOU have received for "
            "any emotional or mental health condition from the date of "
            "the ADVERSE EMPLOYMENT ACTION through the present."
        ),
        category="medical_records",
        applicable_roles=("defendant",),
        order=35,
    ),
    DiscoveryRequest(
        id="rfpd_med_002",
        text=(
            "All DOCUMENTS RELATING TO any emotional or mental health "
            "treatment YOU received during the five years preceding YOUR "
            "EMPLOYMENT with {EMPLOYER}, including records from any "
            "HEALTH CARE PROVIDER."
        ),
        category="medical_records",
        applicable_roles=("defendant",),
        order=36,
    ),
    DiscoveryRequest(
        id="rfpd_med_003",
        text=(
            "All DOCUMENTS RELATING TO any prescription medication taken "
            "by YOU for any emotional or mental health condition during the "
            "period from five years before YOUR EMPLOYMENT with {EMPLOYER} "
            "through the present."
        ),
        category="medical_records",
        applicable_roles=("defendant",),
        order=37,
    ),

    # ===================================================================
    # DEFENDANT — Financial Records and Tax Returns (4, new)
    # ===================================================================
    DiscoveryRequest(
        id="rfpd_fin_001",
        text=(
            "All federal and state income tax returns filed by YOU for "
            "the tax year in which the ADVERSE EMPLOYMENT ACTION occurred "
            "through the most recent tax year."
        ),
        category="financial_records",
        applicable_roles=("defendant",),
        order=38,
    ),
    DiscoveryRequest(
        id="rfpd_fin_002",
        text=(
            "All DOCUMENTS evidencing income received by YOU from the "
            "date of the ADVERSE EMPLOYMENT ACTION through the present, "
            "including pay stubs, W-2 forms, 1099 forms, and bank "
            "statements showing deposits."
        ),
        category="financial_records",
        applicable_roles=("defendant",),
        order=39,
    ),
    DiscoveryRequest(
        id="rfpd_fin_003",
        text=(
            "All DOCUMENTS RELATING TO any severance pay, separation pay, "
            "or other payments received by YOU from {EMPLOYER} in "
            "connection with the TERMINATION."
        ),
        category="financial_records",
        applicable_roles=("defendant",),
        order=40,
    ),
    DiscoveryRequest(
        id="rfpd_fin_004",
        text=(
            "All DOCUMENTS RELATING TO any unemployment insurance benefits, "
            "disability benefits, or other government benefits received by "
            "YOU from the date of the ADVERSE EMPLOYMENT ACTION through "
            "the present."
        ),
        category="financial_records",
        applicable_roles=("defendant",),
        order=41,
    ),

    # ===================================================================
    # DEFENDANT — Job Search and Mitigation (3, new)
    # ===================================================================
    DiscoveryRequest(
        id="rfpd_jobsearch_001",
        text=(
            "All DOCUMENTS RELATING TO YOUR efforts to obtain employment "
            "from the date of the ADVERSE EMPLOYMENT ACTION through the "
            "present, including applications, resumes, cover letters, and "
            "COMMUNICATIONS with recruiters or prospective employers."
        ),
        category="job_search_docs",
        applicable_roles=("defendant",),
        order=42,
    ),
    DiscoveryRequest(
        id="rfpd_jobsearch_002",
        text=(
            "All DOCUMENTS RELATING TO any employment offer YOU received "
            "(whether accepted or declined) from the date of the ADVERSE "
            "EMPLOYMENT ACTION through the present."
        ),
        category="job_search_docs",
        applicable_roles=("defendant",),
        order=43,
    ),
    DiscoveryRequest(
        id="rfpd_jobsearch_003",
        text=(
            "All DOCUMENTS RELATING TO any self-employment, freelance, "
            "consulting, or independent contractor work performed by YOU "
            "from the date of the ADVERSE EMPLOYMENT ACTION through "
            "the present."
        ),
        category="job_search_docs",
        applicable_roles=("defendant",),
        order=44,
    ),

    # ===================================================================
    # DEFENDANT — Prior Employment Records (2, new)
    # ===================================================================
    DiscoveryRequest(
        id="rfpd_prioremp_001",
        text=(
            "All DOCUMENTS RELATING TO YOUR employment with any employer "
            "during the ten years preceding YOUR EMPLOYMENT with {EMPLOYER}, "
            "including offer letters, separation notices, and performance "
            "evaluations."
        ),
        category="prior_employment_docs",
        applicable_roles=("defendant",),
        order=45,
    ),
    DiscoveryRequest(
        id="rfpd_prioremp_002",
        text=(
            "All DOCUMENTS RELATING TO any lawsuit, administrative charge, "
            "workers' compensation claim, or grievance YOU filed against "
            "any prior employer, including complaints, responses, and "
            "settlement agreements."
        ),
        category="prior_employment_docs",
        applicable_roles=("defendant",),
        order=46,
    ),

    # ===================================================================
    # DEFENDANT — Diaries, Journals, and Personal Notes (1, new)
    # ===================================================================
    DiscoveryRequest(
        id="rfpd_personal_001",
        text=(
            "All diaries, journals, logs, calendars, and personal notes "
            "maintained by YOU that RELATE TO YOUR EMPLOYMENT with "
            "{EMPLOYER}, the ADVERSE EMPLOYMENT ACTION, or the claims "
            "in this action."
        ),
        category="personal_records",
        applicable_roles=("defendant",),
        order=47,
    ),

    # ===================================================================
    # DEFENDANT — Social Media and Recordings (2, new)
    # ===================================================================
    DiscoveryRequest(
        id="rfpd_socialmedia_001",
        text=(
            "All screenshots, printouts, or copies of social media posts, "
            "comments, or messages made by YOU RELATING TO YOUR EMPLOYMENT "
            "with {EMPLOYER}, the ADVERSE EMPLOYMENT ACTION, or YOUR "
            "emotional state, from one year before the ADVERSE EMPLOYMENT "
            "ACTION through the present."
        ),
        category="social_media_docs",
        applicable_roles=("defendant",),
        order=48,
    ),
    DiscoveryRequest(
        id="rfpd_socialmedia_002",
        text=(
            "All audio recordings, video recordings, and photographs made "
            "by YOU during YOUR EMPLOYMENT with {EMPLOYER} that RELATE TO "
            "any event, conversation, or condition alleged in YOUR complaint."
        ),
        category="social_media_docs",
        applicable_roles=("defendant",),
        order=49,
    ),

    # ===================================================================
    # DEFENDANT — Government Agency Communications (3, new)
    # ===================================================================
    DiscoveryRequest(
        id="rfpd_govt_001",
        text=(
            "All DOCUMENTS RELATING TO any charge, complaint, or "
            "communication filed by YOU with the Civil Rights Department "
            "(formerly DFEH), the Equal Employment Opportunity Commission, "
            "or any other governmental agency concerning {EMPLOYER}."
        ),
        category="govt_agency_docs",
        applicable_roles=("defendant",),
        order=50,
    ),
    DiscoveryRequest(
        id="rfpd_govt_002",
        text=(
            "All correspondence between YOU and any governmental agency "
            "RELATING TO the claims in this action, including right-to-sue "
            "letters, intake questionnaires, and investigative documents."
        ),
        category="govt_agency_docs",
        applicable_roles=("defendant",),
        order=51,
    ),
    DiscoveryRequest(
        id="rfpd_govt_003",
        text=(
            "All DOCUMENTS received by YOU from any governmental agency "
            "in connection with any investigation of YOUR claims against "
            "{EMPLOYER}."
        ),
        category="govt_agency_docs",
        applicable_roles=("defendant",),
        order=52,
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
