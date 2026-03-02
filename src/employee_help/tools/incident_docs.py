"""Incident documentation helper.

Pure computation — no DB, no ML, no external services.
Users select an incident type and receive type-specific guided prompts,
form fields, and evidence checklists. All incident data is stored
client-side in localStorage — no user data ever reaches this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class IncidentType(str, Enum):
    """California workplace incident types for documentation."""

    unpaid_wages = "unpaid_wages"
    discrimination = "discrimination"
    harassment = "harassment"
    wrongful_termination = "wrongful_termination"
    retaliation = "retaliation"
    family_medical_leave = "family_medical_leave"
    workplace_safety = "workplace_safety"
    misclassification = "misclassification"
    meal_rest_breaks = "meal_rest_breaks"
    whistleblower = "whistleblower"


class FieldType(str, Enum):
    """Form field types for the documentation helper."""

    text = "text"
    textarea = "textarea"
    date = "date"
    time = "time"
    number = "number"
    select = "select"
    boolean = "boolean"


class Importance(str, Enum):
    """Evidence item importance level."""

    critical = "critical"
    recommended = "recommended"
    optional = "optional"


@dataclass(frozen=True)
class DocumentationField:
    """A single form field for incident documentation."""

    name: str
    label: str
    field_type: FieldType
    placeholder: str = ""
    required: bool = False
    help_text: str = ""
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvidenceItem:
    """A single evidence checklist item."""

    description: str
    importance: Importance
    tip: str = ""


@dataclass(frozen=True)
class IncidentTypeGuide:
    """Complete documentation guidance for an incident type."""

    incident_type: IncidentType
    label: str
    description: str
    common_fields: tuple[DocumentationField, ...]
    specific_fields: tuple[DocumentationField, ...]
    prompts: tuple[str, ...]
    evidence_checklist: tuple[EvidenceItem, ...]
    related_claim_types: tuple[str, ...]
    legal_tips: tuple[str, ...]


# ── Common fields (shared across all 10 types) ──────────────────────

COMMON_FIELDS: tuple[DocumentationField, ...] = (
    DocumentationField(
        name="incident_date",
        label="Date of Incident",
        field_type=FieldType.date,
        required=True,
        help_text="When did this incident occur?",
    ),
    DocumentationField(
        name="incident_time",
        label="Time of Incident",
        field_type=FieldType.time,
        help_text="Approximate time, if you remember.",
    ),
    DocumentationField(
        name="location",
        label="Location",
        field_type=FieldType.text,
        placeholder="e.g., Main office, 3rd floor break room",
        required=True,
        help_text="Where did this happen?",
    ),
    DocumentationField(
        name="witnesses",
        label="Witnesses",
        field_type=FieldType.textarea,
        placeholder="Names and contact info of anyone who saw or heard what happened",
        help_text="List anyone present during the incident.",
    ),
    DocumentationField(
        name="narrative",
        label="What Happened",
        field_type=FieldType.textarea,
        placeholder="While details are fresh, write down exactly what happened",
        required=True,
        help_text="Describe the incident in your own words. Include who was involved, what was said, and what actions were taken.",
    ),
    DocumentationField(
        name="quotes",
        label="Exact Words Spoken",
        field_type=FieldType.textarea,
        placeholder="Write down any exact words or phrases you remember",
        help_text="Direct quotes are powerful evidence. Record them as precisely as possible.",
    ),
    DocumentationField(
        name="employer_response",
        label="Employer Response",
        field_type=FieldType.textarea,
        placeholder="How did your employer or supervisor respond?",
        help_text="Document any response from management, HR, or supervisors.",
    ),
    DocumentationField(
        name="impact",
        label="Impact on You",
        field_type=FieldType.textarea,
        placeholder="How has this affected your work, health, or well-being?",
        help_text="Describe any emotional, physical, or financial impact.",
    ),
)


# ── Per-type guides ──────────────────────────────────────────────────

INCIDENT_GUIDES: dict[IncidentType, IncidentTypeGuide] = {
    IncidentType.discrimination: IncidentTypeGuide(
        incident_type=IncidentType.discrimination,
        label="Discrimination",
        description="Document incidents where you were treated differently or unfavorably because of a protected characteristic such as race, gender, age, disability, religion, or national origin.",
        common_fields=COMMON_FIELDS,
        specific_fields=(
            DocumentationField(
                name="protected_characteristic",
                label="Protected Characteristic",
                field_type=FieldType.select,
                required=True,
                help_text="Which protected characteristic do you believe motivated the discrimination?",
                options=(
                    "Race/Ethnicity",
                    "Gender/Sex",
                    "Age (40+)",
                    "Disability",
                    "Religion",
                    "National Origin",
                    "Sexual Orientation",
                    "Gender Identity",
                    "Pregnancy",
                    "Marital Status",
                    "Military/Veteran Status",
                    "Other",
                ),
            ),
            DocumentationField(
                name="adverse_action",
                label="Adverse Action Taken",
                field_type=FieldType.textarea,
                placeholder="e.g., denied promotion, reduced hours, terminated",
                help_text="What negative action was taken against you?",
            ),
            DocumentationField(
                name="comparator_treatment",
                label="How Others Were Treated",
                field_type=FieldType.textarea,
                placeholder="Were others outside your protected group treated differently?",
                help_text="Describe how similarly-situated coworkers were treated.",
            ),
        ),
        prompts=(
            "What specific comments, actions, or decisions made you believe this was based on your protected characteristic?",
            "Were there other employees in a similar situation who were treated differently? How?",
            "Did you report this to HR or a supervisor? What was their response?",
            "Has there been a pattern of similar treatment, or was this a single incident?",
        ),
        evidence_checklist=(
            EvidenceItem(
                description="Written communications (emails, texts, memos) showing discriminatory language or decisions",
                importance=Importance.critical,
                tip="Screenshot and save emails before they can be deleted.",
            ),
            EvidenceItem(
                description="Performance reviews or evaluations (yours and comparators if available)",
                importance=Importance.critical,
                tip="Keep copies of all reviews, especially positive ones before the adverse action.",
            ),
            EvidenceItem(
                description="Company policies on the relevant decision (promotion, hiring, etc.)",
                importance=Importance.recommended,
                tip="Check your employee handbook or intranet.",
            ),
            EvidenceItem(
                description="Witness statements or names of people who observed the treatment",
                importance=Importance.recommended,
            ),
            EvidenceItem(
                description="Timeline of events showing pattern of differential treatment",
                importance=Importance.recommended,
            ),
            EvidenceItem(
                description="Notes from any meetings with HR or management about the issue",
                importance=Importance.optional,
            ),
        ),
        related_claim_types=("feha_discrimination",),
        legal_tips=(
            "Under FEHA, California protects more characteristics than federal law. You have 3 years to file a complaint with the Civil Rights Department (CRD).",
            "Document how similarly-situated employees outside your protected group were treated differently — this 'comparator evidence' is often key to proving discrimination.",
        ),
    ),
    IncidentType.harassment: IncidentTypeGuide(
        incident_type=IncidentType.harassment,
        label="Harassment / Hostile Work Environment",
        description="Document incidents of unwelcome conduct based on a protected characteristic that is severe or pervasive enough to create a hostile work environment.",
        common_fields=COMMON_FIELDS,
        specific_fields=(
            DocumentationField(
                name="harassment_type",
                label="Type of Harassment",
                field_type=FieldType.select,
                required=True,
                help_text="What type of harassment did you experience?",
                options=(
                    "Sexual harassment",
                    "Racial harassment",
                    "Age-based harassment",
                    "Disability-based harassment",
                    "Religious harassment",
                    "Gender identity harassment",
                    "Other protected characteristic",
                ),
            ),
            DocumentationField(
                name="frequency",
                label="Frequency",
                field_type=FieldType.select,
                help_text="How often does this occur?",
                options=(
                    "Single incident",
                    "Weekly",
                    "Daily",
                    "Multiple times per day",
                    "Ongoing/continuous",
                ),
            ),
            DocumentationField(
                name="reported_to_hr",
                label="Reported to HR",
                field_type=FieldType.boolean,
                help_text="Have you reported this to HR or management?",
            ),
            DocumentationField(
                name="hr_response",
                label="HR/Management Response",
                field_type=FieldType.textarea,
                placeholder="What action did HR or management take after your report?",
                help_text="Document the response, including if no action was taken.",
            ),
        ),
        prompts=(
            "Describe the specific words, gestures, or actions that constitute the harassment.",
            "How often does this happen, and has the behavior escalated over time?",
            "Did you report the behavior to anyone? What happened after you reported it?",
            "Have other employees experienced similar behavior from this person?",
        ),
        evidence_checklist=(
            EvidenceItem(
                description="Dated log of each incident with specific details (who, what, when, where)",
                importance=Importance.critical,
                tip="A contemporaneous log — written at or near the time of each incident — carries significant weight.",
            ),
            EvidenceItem(
                description="Written complaints to HR or management and their responses",
                importance=Importance.critical,
                tip="Always submit complaints in writing (email) so you have a record.",
            ),
            EvidenceItem(
                description="Offensive emails, texts, messages, or images",
                importance=Importance.critical,
                tip="Take screenshots with visible timestamps.",
            ),
            EvidenceItem(
                description="Names of witnesses who can corroborate incidents",
                importance=Importance.recommended,
            ),
            EvidenceItem(
                description="Company anti-harassment policy",
                importance=Importance.recommended,
                tip="Document whether the company followed its own policy.",
            ),
            EvidenceItem(
                description="Medical or therapy records showing emotional/physical impact",
                importance=Importance.optional,
                tip="If the harassment has affected your health, records from your doctor or therapist can support your claim.",
            ),
        ),
        related_claim_types=("feha_discrimination",),
        legal_tips=(
            "Under California law, a single severe incident can constitute harassment — it does not always need to be a pattern of behavior.",
            "Your employer can be liable if they knew or should have known about the harassment and failed to take prompt corrective action.",
        ),
    ),
    IncidentType.wrongful_termination: IncidentTypeGuide(
        incident_type=IncidentType.wrongful_termination,
        label="Wrongful Termination",
        description="Document circumstances surrounding your firing that you believe was illegal — whether due to discrimination, retaliation, or violation of public policy.",
        common_fields=COMMON_FIELDS,
        specific_fields=(
            DocumentationField(
                name="stated_reason",
                label="Reason Given for Termination",
                field_type=FieldType.textarea,
                placeholder="What reason did your employer give for firing you?",
                required=True,
                help_text="Record the exact reason stated at the time of termination.",
            ),
            DocumentationField(
                name="actual_reason",
                label="Actual Reason (Your Belief)",
                field_type=FieldType.textarea,
                placeholder="What do you believe is the real reason you were fired?",
                help_text="Explain why you believe the stated reason is pretextual.",
            ),
            DocumentationField(
                name="tenure_length",
                label="Length of Employment",
                field_type=FieldType.text,
                placeholder="e.g., 3 years, 6 months",
                help_text="How long did you work for this employer?",
            ),
            DocumentationField(
                name="received_warnings",
                label="Received Prior Warnings",
                field_type=FieldType.boolean,
                help_text="Did you receive any written warnings or performance improvement plans before termination?",
            ),
        ),
        prompts=(
            "What reason did your employer give for firing you? Do you believe this is the real reason?",
            "Were there any recent events (complaints, protected activity, leave requests) that preceded the termination?",
            "Were other employees who did similar things treated differently?",
            "Did you have positive performance reviews before the termination?",
        ),
        evidence_checklist=(
            EvidenceItem(
                description="Termination letter or written notice",
                importance=Importance.critical,
                tip="If you were terminated verbally, send an email confirming the conversation to create a written record.",
            ),
            EvidenceItem(
                description="Performance reviews, especially positive ones before termination",
                importance=Importance.critical,
                tip="A history of good reviews undermines a claim that you were fired for performance reasons.",
            ),
            EvidenceItem(
                description="Any written warnings or performance improvement plans",
                importance=Importance.recommended,
            ),
            EvidenceItem(
                description="Communications around the time of termination (emails, texts)",
                importance=Importance.recommended,
                tip="Save any messages that show the timeline of events.",
            ),
            EvidenceItem(
                description="Evidence of protected activity before termination (complaints, leave requests)",
                importance=Importance.recommended,
            ),
            EvidenceItem(
                description="Final paycheck and documentation of benefits owed",
                importance=Importance.optional,
            ),
        ),
        related_claim_types=("wrongful_termination",),
        legal_tips=(
            "California is an at-will employment state, but firing someone for an illegal reason (discrimination, retaliation, public policy violation) is wrongful termination.",
            "The timing between a protected activity (filing a complaint, taking leave) and termination can be strong evidence of pretext.",
        ),
    ),
    IncidentType.unpaid_wages: IncidentTypeGuide(
        incident_type=IncidentType.unpaid_wages,
        label="Unpaid Wages",
        description="Document instances where you were not paid for work performed, including overtime, commissions, or other earned compensation.",
        common_fields=COMMON_FIELDS,
        specific_fields=(
            DocumentationField(
                name="hours_worked",
                label="Hours Worked (Unpaid)",
                field_type=FieldType.number,
                placeholder="Number of hours",
                required=True,
                help_text="How many hours did you work that were not properly compensated?",
            ),
            DocumentationField(
                name="hours_paid",
                label="Hours Paid",
                field_type=FieldType.number,
                placeholder="Number of hours",
                help_text="How many hours were you actually paid for during this period?",
            ),
            DocumentationField(
                name="pay_period",
                label="Pay Period",
                field_type=FieldType.text,
                placeholder="e.g., Jan 1-15, 2026",
                help_text="Which pay period(s) are affected?",
            ),
            DocumentationField(
                name="wage_type",
                label="Type of Unpaid Wages",
                field_type=FieldType.select,
                help_text="What type of compensation was not paid?",
                options=(
                    "Regular wages",
                    "Overtime",
                    "Double time",
                    "Commissions",
                    "Bonuses",
                    "Vacation/PTO payout",
                    "Other",
                ),
            ),
        ),
        prompts=(
            "How many hours did you work that were not paid? What period does this cover?",
            "Were you asked to work off the clock, before clocking in, or after clocking out?",
            "Do you have your own records of hours worked (notes, personal calendar, GPS data)?",
            "Have you raised this issue with your employer? What was their response?",
        ),
        evidence_checklist=(
            EvidenceItem(
                description="Pay stubs showing hours paid vs. hours actually worked",
                importance=Importance.critical,
                tip="California employers must provide itemized pay stubs. Request copies if you don't have them.",
            ),
            EvidenceItem(
                description="Personal records of hours worked (notes, calendar, app, GPS data)",
                importance=Importance.critical,
                tip="Start tracking your hours independently using a personal app or notebook.",
            ),
            EvidenceItem(
                description="Time clock records or employer's timekeeping system records",
                importance=Importance.recommended,
                tip="Request a copy of your timekeeping records from your employer.",
            ),
            EvidenceItem(
                description="Employment agreement or offer letter showing agreed pay rate",
                importance=Importance.recommended,
            ),
            EvidenceItem(
                description="Communications about work assignments (emails, texts requesting off-clock work)",
                importance=Importance.recommended,
            ),
            EvidenceItem(
                description="Coworker statements about similar pay practices",
                importance=Importance.optional,
            ),
        ),
        related_claim_types=("wage_theft",),
        legal_tips=(
            "California requires employers to pay all wages earned within specific timeframes. You can file a wage claim with the DLSE even while still employed.",
            "Keep your own independent record of hours worked — if your employer's records are inaccurate, your personal records can serve as evidence.",
        ),
    ),
    IncidentType.retaliation: IncidentTypeGuide(
        incident_type=IncidentType.retaliation,
        label="Retaliation",
        description="Document incidents where your employer took negative action against you for exercising a legal right, such as filing a complaint, reporting a violation, or participating in an investigation.",
        common_fields=COMMON_FIELDS,
        specific_fields=(
            DocumentationField(
                name="protected_activity",
                label="Protected Activity",
                field_type=FieldType.textarea,
                placeholder="What did you do that you believe triggered the retaliation?",
                required=True,
                help_text="Describe the complaint, report, or activity you engaged in.",
            ),
            DocumentationField(
                name="adverse_action",
                label="Retaliatory Action",
                field_type=FieldType.textarea,
                placeholder="e.g., demotion, schedule change, termination, reduced hours",
                help_text="What negative action was taken against you?",
            ),
            DocumentationField(
                name="timeline_gap",
                label="Time Between Activity and Retaliation",
                field_type=FieldType.text,
                placeholder="e.g., 2 weeks, 3 days",
                help_text="How soon after your protected activity did the retaliation occur?",
            ),
        ),
        prompts=(
            "What protected activity did you engage in before the retaliation occurred?",
            "How soon after your protected activity did the adverse action happen?",
            "Did your employer's attitude or behavior toward you change after the protected activity?",
            "Were others who engaged in similar protected activities also retaliated against?",
        ),
        evidence_checklist=(
            EvidenceItem(
                description="Documentation of the protected activity (complaint, report, etc.)",
                importance=Importance.critical,
                tip="Always keep copies of any complaints or reports you file.",
            ),
            EvidenceItem(
                description="Timeline showing close proximity between protected activity and adverse action",
                importance=Importance.critical,
                tip="The shorter the gap, the stronger the inference of retaliation.",
            ),
            EvidenceItem(
                description="Evidence of change in treatment after protected activity",
                importance=Importance.recommended,
                tip="Compare your treatment before and after the protected activity.",
            ),
            EvidenceItem(
                description="Written notice of the adverse action (demotion letter, schedule change, etc.)",
                importance=Importance.recommended,
            ),
            EvidenceItem(
                description="Performance evaluations before and after the protected activity",
                importance=Importance.recommended,
            ),
        ),
        related_claim_types=("retaliation_whistleblower",),
        legal_tips=(
            "California Labor Code section 98.6 protects employees from retaliation for filing wage claims, complaints about working conditions, and other protected activities. The filing deadline is 6 months.",
            "Close timing between your protected activity and the adverse action is often the strongest evidence of retaliation.",
        ),
    ),
    IncidentType.family_medical_leave: IncidentTypeGuide(
        incident_type=IncidentType.family_medical_leave,
        label="Family / Medical Leave Violation",
        description="Document incidents where your employer denied, interfered with, or retaliated against you for requesting or taking family or medical leave.",
        common_fields=COMMON_FIELDS,
        specific_fields=(
            DocumentationField(
                name="leave_type",
                label="Type of Leave",
                field_type=FieldType.select,
                required=True,
                help_text="What type of leave were you seeking?",
                options=(
                    "CFRA/FMLA family leave",
                    "Pregnancy disability leave",
                    "Bonding leave (new child)",
                    "Caring for ill family member",
                    "Own serious health condition",
                    "Other",
                ),
            ),
            DocumentationField(
                name="leave_requested",
                label="Leave Was Requested",
                field_type=FieldType.boolean,
                help_text="Did you formally request the leave?",
            ),
            DocumentationField(
                name="leave_denied",
                label="Leave Was Denied",
                field_type=FieldType.boolean,
                help_text="Was your leave request denied?",
            ),
            DocumentationField(
                name="adverse_action_on_return",
                label="Adverse Action Upon Return",
                field_type=FieldType.textarea,
                placeholder="Were you demoted, had your position eliminated, or faced other negative consequences?",
                help_text="Describe any negative treatment when you returned from leave.",
            ),
        ),
        prompts=(
            "What type of leave did you request or take, and when?",
            "Was your leave request denied, delayed, or discouraged? What reason was given?",
            "Were you able to return to the same or equivalent position after leave?",
            "Did your employer make negative comments about your leave or discourage you from taking it?",
        ),
        evidence_checklist=(
            EvidenceItem(
                description="Leave request documentation (written request, email, HR forms)",
                importance=Importance.critical,
                tip="Always request leave in writing and keep a copy.",
            ),
            EvidenceItem(
                description="Employer's response to leave request (approval, denial, or silence)",
                importance=Importance.critical,
                tip="If denied verbally, send a follow-up email confirming what was said.",
            ),
            EvidenceItem(
                description="Medical certification or documentation supporting the need for leave",
                importance=Importance.recommended,
            ),
            EvidenceItem(
                description="Evidence of position changes upon return (new title, duties, schedule)",
                importance=Importance.recommended,
            ),
            EvidenceItem(
                description="Company leave policy from employee handbook",
                importance=Importance.optional,
                tip="Compare your employer's actions to their stated policy.",
            ),
        ),
        related_claim_types=("cfra_family_leave",),
        legal_tips=(
            "Under CFRA, eligible employees can take up to 12 weeks of unpaid, job-protected leave per year. Your employer must restore you to the same or comparable position.",
            "Your employer cannot count protected leave against you in attendance policies, performance reviews, or employment decisions.",
        ),
    ),
    IncidentType.workplace_safety: IncidentTypeGuide(
        incident_type=IncidentType.workplace_safety,
        label="Workplace Safety / Health Hazard",
        description="Document unsafe working conditions, health hazards, or safety violations in your workplace.",
        common_fields=COMMON_FIELDS,
        specific_fields=(
            DocumentationField(
                name="hazard_type",
                label="Type of Hazard",
                field_type=FieldType.select,
                required=True,
                help_text="What type of safety hazard or violation did you observe?",
                options=(
                    "Chemical exposure",
                    "Fall hazard",
                    "Electrical hazard",
                    "Fire hazard",
                    "Ergonomic hazard",
                    "Machine/equipment hazard",
                    "Violence/threat",
                    "Extreme temperature",
                    "Inadequate training",
                    "Missing safety equipment",
                    "Other",
                ),
            ),
            DocumentationField(
                name="injury_occurred",
                label="Injury Occurred",
                field_type=FieldType.boolean,
                help_text="Did anyone get injured as a result of this hazard?",
            ),
            DocumentationField(
                name="injury_description",
                label="Injury Description",
                field_type=FieldType.textarea,
                placeholder="Describe any injuries that resulted",
                help_text="If an injury occurred, describe what happened and who was affected.",
            ),
            DocumentationField(
                name="reported_to_employer",
                label="Reported to Employer",
                field_type=FieldType.boolean,
                help_text="Did you report the hazard to your employer?",
            ),
        ),
        prompts=(
            "Describe the specific hazard or unsafe condition you observed.",
            "Has anyone been injured or become ill because of this hazard?",
            "Did you report the hazard to your employer? How did they respond?",
            "Is this an ongoing hazard, or was it a one-time occurrence?",
        ),
        evidence_checklist=(
            EvidenceItem(
                description="Photos or videos of the hazardous condition",
                importance=Importance.critical,
                tip="Take photos with timestamps if you can do so safely.",
            ),
            EvidenceItem(
                description="Written report to employer about the hazard",
                importance=Importance.critical,
                tip="Report safety concerns in writing (email) for documentation.",
            ),
            EvidenceItem(
                description="Medical records if injury occurred",
                importance=Importance.recommended,
                tip="Report workplace injuries to your doctor and note the cause.",
            ),
            EvidenceItem(
                description="OSHA or Cal/OSHA standards that apply to the hazard",
                importance=Importance.recommended,
            ),
            EvidenceItem(
                description="Names of coworkers exposed to the same hazard",
                importance=Importance.optional,
            ),
        ),
        related_claim_types=(),
        legal_tips=(
            "You can file a Cal/OSHA complaint anonymously. Your employer cannot legally retaliate against you for reporting safety concerns.",
            "If there is an imminent danger, Cal/OSHA is required to respond within 3 days. For other hazards, the response time is typically 14 days.",
        ),
    ),
    IncidentType.misclassification: IncidentTypeGuide(
        incident_type=IncidentType.misclassification,
        label="Worker Misclassification",
        description="Document evidence that you have been misclassified as an independent contractor when you should be an employee, or misclassified in your job duties or overtime eligibility.",
        common_fields=COMMON_FIELDS,
        specific_fields=(
            DocumentationField(
                name="classification",
                label="Current Classification",
                field_type=FieldType.select,
                required=True,
                help_text="How are you currently classified by your employer?",
                options=(
                    "Independent contractor (1099)",
                    "Exempt employee (no overtime)",
                    "Part-time (should be full-time)",
                    "Other",
                ),
            ),
            DocumentationField(
                name="control_level",
                label="Level of Control by Employer",
                field_type=FieldType.textarea,
                placeholder="Describe how much your employer controls when, where, and how you work",
                help_text="The more control your employer exercises, the more likely you should be an employee.",
            ),
            DocumentationField(
                name="benefits_denied",
                label="Benefits Denied",
                field_type=FieldType.textarea,
                placeholder="e.g., health insurance, overtime pay, meal breaks, workers' comp",
                help_text="What employee benefits have you been denied due to your classification?",
            ),
        ),
        prompts=(
            "How much control does your employer exercise over when, where, and how you perform your work?",
            "Do you use your own tools/equipment, or does the employer provide them?",
            "Can you work for other clients/companies, or does this employer require exclusivity?",
            "What employee benefits (insurance, overtime, breaks, etc.) have you been denied?",
        ),
        evidence_checklist=(
            EvidenceItem(
                description="Contract or agreement showing your classification",
                importance=Importance.critical,
                tip="Keep a copy of any agreement that labels you as an independent contractor.",
            ),
            EvidenceItem(
                description="Evidence of employer control (set schedule, required location, provided equipment)",
                importance=Importance.critical,
                tip="Under California's ABC test, a worker is presumed to be an employee unless the employer proves otherwise.",
            ),
            EvidenceItem(
                description="Pay records (1099 forms, invoices, pay stubs)",
                importance=Importance.recommended,
            ),
            EvidenceItem(
                description="Communications showing employer direction and control",
                importance=Importance.recommended,
                tip="Emails or messages where your employer tells you how to do your job are strong evidence.",
            ),
            EvidenceItem(
                description="List of benefits you've been denied",
                importance=Importance.optional,
            ),
        ),
        related_claim_types=("misclassification",),
        legal_tips=(
            "California uses the ABC test (AB 5) to determine worker classification. Under this test, a worker is presumed to be an employee unless the employer can prove all three prongs.",
            "Misclassified workers can recover unpaid overtime, meal/rest break premiums, business expense reimbursement, and other benefits they were denied.",
        ),
    ),
    IncidentType.meal_rest_breaks: IncidentTypeGuide(
        incident_type=IncidentType.meal_rest_breaks,
        label="Meal / Rest Break Violations",
        description="Document instances where your employer failed to provide required meal periods or rest breaks, or pressured you to skip or work through them.",
        common_fields=COMMON_FIELDS,
        specific_fields=(
            DocumentationField(
                name="break_type",
                label="Type of Break Missed",
                field_type=FieldType.select,
                required=True,
                help_text="What type of break was missed or denied?",
                options=(
                    "Meal break (30 min)",
                    "Rest break (10 min)",
                    "Both meal and rest breaks",
                ),
            ),
            DocumentationField(
                name="breaks_missed_count",
                label="Number of Breaks Missed",
                field_type=FieldType.number,
                placeholder="Total number",
                help_text="How many breaks have you missed in the relevant period?",
            ),
            DocumentationField(
                name="reason_missed",
                label="Reason Breaks Were Missed",
                field_type=FieldType.textarea,
                placeholder="e.g., told to keep working, understaffed, pressure from supervisor",
                help_text="Why were the breaks missed — employer pressure, staffing, workload?",
            ),
            DocumentationField(
                name="break_policy_exists",
                label="Company Has a Break Policy",
                field_type=FieldType.boolean,
                help_text="Does your employer have a written meal/rest break policy?",
            ),
        ),
        prompts=(
            "Were you told to skip breaks, or were working conditions such that taking breaks was impractical?",
            "How many breaks have you missed over what time period?",
            "Were you compensated with premium pay for missed breaks?",
            "Do other employees also miss breaks, or is it primarily affecting you?",
        ),
        evidence_checklist=(
            EvidenceItem(
                description="Time records showing work through meal periods",
                importance=Importance.critical,
                tip="If your employer auto-deducts meal breaks from your time, note when you actually worked through them.",
            ),
            EvidenceItem(
                description="Personal log of missed breaks with dates and reasons",
                importance=Importance.critical,
                tip="Start keeping a daily log of every missed break.",
            ),
            EvidenceItem(
                description="Company break policy from employee handbook",
                importance=Importance.recommended,
            ),
            EvidenceItem(
                description="Communications from supervisor directing you to skip breaks or keep working",
                importance=Importance.recommended,
                tip="Save any texts or emails where a supervisor tells you to skip a break.",
            ),
            EvidenceItem(
                description="Pay stubs showing whether premium pay was included",
                importance=Importance.optional,
                tip="Under California law, you're owed one hour of premium pay for each missed break.",
            ),
        ),
        related_claim_types=("wage_theft",),
        legal_tips=(
            "California requires a 30-minute meal break before the 5th hour of work and a 10-minute rest break for every 4 hours worked. Employers who fail to provide these owe one hour of premium pay per missed break per day.",
            "Your employer must relieve you of all duties during meal breaks. If you must remain on call or available, the break may be considered 'on duty' and compensable.",
        ),
    ),
    IncidentType.whistleblower: IncidentTypeGuide(
        incident_type=IncidentType.whistleblower,
        label="Whistleblower",
        description="Document situations where you reported illegal activity, regulatory violations, or unsafe practices by your employer, and any retaliation you faced as a result.",
        common_fields=COMMON_FIELDS,
        specific_fields=(
            DocumentationField(
                name="violation_reported",
                label="Violation or Illegal Activity Reported",
                field_type=FieldType.textarea,
                placeholder="Describe the violation, illegal activity, or unsafe practice you reported",
                required=True,
                help_text="What specific violation or illegal activity did you report?",
            ),
            DocumentationField(
                name="reported_to",
                label="Who You Reported To",
                field_type=FieldType.textarea,
                placeholder="e.g., supervisor, HR, government agency, law enforcement",
                help_text="To whom did you report the violation?",
            ),
            DocumentationField(
                name="adverse_action",
                label="Retaliation Experienced",
                field_type=FieldType.textarea,
                placeholder="What negative action was taken against you after reporting?",
                help_text="Describe any retaliation you faced after making your report.",
            ),
        ),
        prompts=(
            "What specific violation or illegal activity did you observe or discover?",
            "Who did you report it to, and when? What was their response?",
            "What negative consequences have you faced since making the report?",
            "Do you have documentation of the underlying violation you reported?",
        ),
        evidence_checklist=(
            EvidenceItem(
                description="Written report or complaint about the violation (email, form, letter)",
                importance=Importance.critical,
                tip="Always report violations in writing and keep copies.",
            ),
            EvidenceItem(
                description="Evidence of the underlying violation (documents, photos, records)",
                importance=Importance.critical,
                tip="Secure copies of evidence before reporting if possible — access may be restricted afterward.",
            ),
            EvidenceItem(
                description="Timeline showing connection between report and retaliation",
                importance=Importance.recommended,
            ),
            EvidenceItem(
                description="Communications showing employer's reaction to your report",
                importance=Importance.recommended,
                tip="Save all communications related to your report and any subsequent treatment changes.",
            ),
            EvidenceItem(
                description="Government agency filings or responses (if reported externally)",
                importance=Importance.optional,
            ),
        ),
        related_claim_types=("retaliation_whistleblower",),
        legal_tips=(
            "California Labor Code section 1102.5 protects employees who report violations of law to a government or law enforcement agency, or to a supervisor or employee with authority to investigate.",
            "Whistleblower protections apply even if the violation you reported turns out not to be a violation — as long as you had a reasonable belief that it was.",
        ),
    ),
}


DISCLAIMER = (
    "This tool helps you create a personal record of workplace incidents. "
    "It is NOT a legal document and does not constitute legal advice. "
    "Your data is stored only in your browser and is never sent to our servers. "
    "Consult a licensed California employment attorney for advice about your specific situation."
)


def get_incident_guide(incident_type: IncidentType) -> IncidentTypeGuide:
    """Get documentation guidance for an incident type.

    Args:
        incident_type: The type of workplace incident.

    Returns:
        IncidentTypeGuide with fields, prompts, evidence checklist, and tips.
    """
    return INCIDENT_GUIDES[incident_type]
