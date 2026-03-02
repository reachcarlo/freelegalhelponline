"""Guided intake questionnaire.

Pure computation — no DB, no ML, no external services.
Users answer plain-language questions about their workplace situation;
the module scores answers against IssueType values and returns
personalized tool recommendations with pre-filled parameters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from employee_help.tools.deadlines import ClaimType
from employee_help.tools.routing import ISSUE_TYPE_LABELS, IssueType

# ── Issue → natural-language clause for RAG query ────────────────────

ISSUE_QUERY_CLAUSES: dict[IssueType, str] = {
    IssueType.unpaid_wages: "my employer has not paid me wages that I am owed",
    IssueType.discrimination: "I have been discriminated against based on a protected characteristic",
    IssueType.harassment: "I have experienced workplace harassment",
    IssueType.wrongful_termination: "I believe my termination was wrongful or illegal",
    IssueType.retaliation: "I was retaliated against after reporting a problem or exercising a legal right",
    IssueType.meal_rest_breaks: "my employer has denied me required meal or rest breaks",
    IssueType.misclassification: "I may have been misclassified as an independent contractor",
    IssueType.family_medical_leave: "I was denied family or medical leave that I am entitled to",
    IssueType.workplace_safety: "my workplace has unsafe conditions",
    IssueType.whistleblower: "I reported illegal activity and faced consequences",
    IssueType.unemployment_benefits: "I need to apply for unemployment benefits",
    IssueType.disability_insurance: "I need to apply for disability insurance benefits",
    IssueType.paid_family_leave: "I need to apply for paid family leave benefits",
}


# ── Answer keys ─────────────────────────────────────────────────────


class AnswerKey(str, Enum):
    """All possible answer values across the questionnaire."""

    # Q1: situation
    not_paid = "not_paid"
    treated_unfairly = "treated_unfairly"
    fired_laid_off = "fired_laid_off"
    unsafe_conditions = "unsafe_conditions"
    benefits_issue = "benefits_issue"
    reported_problem = "reported_problem"

    # Q2: pay_details
    pay_not_received = "pay_not_received"
    pay_misclassified = "pay_misclassified"
    pay_breaks_denied = "pay_breaks_denied"
    pay_na = "pay_na"

    # Q3: unfair_details
    unfair_protected_class = "unfair_protected_class"
    unfair_hostile_env = "unfair_hostile_env"
    unfair_leave_denied = "unfair_leave_denied"
    unfair_na = "unfair_na"

    # Q4: retaliation
    retaliation_yes = "retaliation_yes"
    retaliation_no = "retaliation_no"

    # Q5: reported_what
    reported_safety = "reported_safety"
    reported_pay_violation = "reported_pay_violation"
    reported_discrimination = "reported_discrimination"
    reported_legal_violation = "reported_legal_violation"
    reported_na = "reported_na"

    # Q6: employment_status
    status_still_employed = "status_still_employed"
    status_terminated = "status_terminated"
    status_quit = "status_quit"

    # Q7: employer_type
    employer_private = "employer_private"
    employer_government = "employer_government"
    employer_unsure = "employer_unsure"

    # Q8: benefits_needed
    need_unemployment = "need_unemployment"
    need_disability = "need_disability"
    need_family_leave = "need_family_leave"
    need_none = "need_none"


# ── Data models ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class AnswerOption:
    """A single selectable answer within a question."""

    key: AnswerKey
    label: str
    help_text: str = ""


@dataclass(frozen=True)
class IntakeQuestion:
    """A single intake question with its options."""

    question_id: str
    question_text: str
    help_text: str
    options: tuple[AnswerOption, ...]
    allow_multiple: bool = False
    show_if: tuple[AnswerKey, ...] | None = None


@dataclass(frozen=True)
class ToolRecommendation:
    """A recommended tool with pre-filled parameters."""

    tool_name: str
    tool_label: str
    tool_path: str
    description: str
    prefill_params: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class IdentifiedIssue:
    """A scored employment issue with tool recommendations."""

    issue_type: IssueType
    issue_label: str
    confidence: str  # "high" or "medium"
    description: str
    related_claim_types: tuple[str, ...]
    tools: tuple[ToolRecommendation, ...]
    has_deadline_urgency: bool


@dataclass(frozen=True)
class IntakeResult:
    """Complete intake evaluation result."""

    identified_issues: list[IdentifiedIssue]
    is_government_employee: bool
    employment_status: str
    summary: str


# ── Question registry ───────────────────────────────────────────────

QUESTIONS: tuple[IntakeQuestion, ...] = (
    IntakeQuestion(
        question_id="situation",
        question_text="Which of these best describes your situation?",
        help_text="Choose the option that most closely matches what happened.",
        options=(
            AnswerOption(AnswerKey.not_paid, "I wasn't paid correctly", "Missing wages, overtime, or final paycheck issues"),
            AnswerOption(AnswerKey.treated_unfairly, "I was treated unfairly", "Discrimination, harassment, or denied leave"),
            AnswerOption(AnswerKey.fired_laid_off, "I was fired or laid off", "Termination you believe was unjust or illegal"),
            AnswerOption(AnswerKey.unsafe_conditions, "My workplace is unsafe", "Health hazards, safety violations, or dangerous conditions"),
            AnswerOption(AnswerKey.benefits_issue, "I need help with benefits", "Unemployment, disability, or family leave benefits"),
            AnswerOption(AnswerKey.reported_problem, "I reported a problem and faced consequences", "Retaliation for whistleblowing or complaints"),
        ),
    ),
    IntakeQuestion(
        question_id="pay_details",
        question_text="What is the pay issue?",
        help_text="Select the option that best describes your pay problem.",
        options=(
            AnswerOption(AnswerKey.pay_not_received, "I didn't receive wages I earned", "Missing regular pay, overtime, or final paycheck"),
            AnswerOption(AnswerKey.pay_misclassified, "I'm classified as an independent contractor but should be an employee", "Your employer treats you as 1099 instead of W-2"),
            AnswerOption(AnswerKey.pay_breaks_denied, "I'm not getting my meal or rest breaks", "Denied or interrupted required break periods"),
            AnswerOption(AnswerKey.pay_na, "Not sure / other pay issue", ""),
        ),
        show_if=(AnswerKey.not_paid,),
    ),
    IntakeQuestion(
        question_id="unfair_details",
        question_text="How were you treated unfairly?",
        help_text="Select the option that best describes what happened.",
        options=(
            AnswerOption(AnswerKey.unfair_protected_class, "Because of my race, gender, age, disability, or other protected characteristic", "Treatment based on who you are"),
            AnswerOption(AnswerKey.unfair_hostile_env, "Ongoing harassment or hostile work environment", "Repeated unwelcome conduct that is severe or pervasive"),
            AnswerOption(AnswerKey.unfair_leave_denied, "I was denied family or medical leave", "FMLA/CFRA leave request was denied or punished"),
            AnswerOption(AnswerKey.unfair_na, "Not sure / other unfair treatment", ""),
        ),
        show_if=(AnswerKey.treated_unfairly,),
    ),
    IntakeQuestion(
        question_id="retaliation",
        question_text="Did any of these problems happen after you complained, reported a violation, or exercised a legal right?",
        help_text="Retaliation is when an employer punishes you for protected activity.",
        options=(
            AnswerOption(AnswerKey.retaliation_yes, "Yes, I think it was retaliation", "The problem started or got worse after you spoke up"),
            AnswerOption(AnswerKey.retaliation_no, "No, or I'm not sure", ""),
        ),
    ),
    IntakeQuestion(
        question_id="reported_what",
        question_text="What did you complain about or report?",
        help_text="Select the option closest to what you reported.",
        options=(
            AnswerOption(AnswerKey.reported_safety, "Unsafe working conditions", "Health or safety violations"),
            AnswerOption(AnswerKey.reported_pay_violation, "Pay or wage violations", "Unpaid wages, missing breaks, etc."),
            AnswerOption(AnswerKey.reported_discrimination, "Discrimination or harassment", "Unfair treatment based on protected characteristics"),
            AnswerOption(AnswerKey.reported_legal_violation, "Other illegal activity", "Fraud, law violations, or other misconduct"),
            AnswerOption(AnswerKey.reported_na, "Not sure / other", ""),
        ),
        show_if=(AnswerKey.retaliation_yes,),
    ),
    IntakeQuestion(
        question_id="employment_status",
        question_text="What is your current employment status?",
        help_text="This affects which remedies and deadlines apply.",
        options=(
            AnswerOption(AnswerKey.status_still_employed, "I still work there", "You are currently employed at this job"),
            AnswerOption(AnswerKey.status_terminated, "I was fired or laid off", "Your employer ended your employment"),
            AnswerOption(AnswerKey.status_quit, "I quit", "You left the job voluntarily"),
        ),
    ),
    IntakeQuestion(
        question_id="employer_type",
        question_text="What type of employer do you work for?",
        help_text="Government employees have different filing requirements.",
        options=(
            AnswerOption(AnswerKey.employer_private, "Private company", "Most businesses, non-profits, etc."),
            AnswerOption(AnswerKey.employer_government, "Government agency", "City, county, state, or federal government"),
            AnswerOption(AnswerKey.employer_unsure, "Not sure", ""),
        ),
    ),
    IntakeQuestion(
        question_id="benefits_needed",
        question_text="Do you need to apply for any of these benefits right now?",
        help_text="Select all that apply. These are separate from your employment claim.",
        options=(
            AnswerOption(AnswerKey.need_unemployment, "Unemployment insurance", "If you lost your job and need income"),
            AnswerOption(AnswerKey.need_disability, "State disability insurance (SDI)", "If you can't work due to illness or injury"),
            AnswerOption(AnswerKey.need_family_leave, "Paid family leave", "To bond with a new child or care for a family member"),
            AnswerOption(AnswerKey.need_none, "None of these", ""),
        ),
        allow_multiple=True,
    ),
)


# ── Signal map (AnswerKey → {IssueType: weight}) ───────────────────

SIGNAL_MAP: dict[AnswerKey, dict[IssueType, float]] = {
    # Q1: situation
    AnswerKey.not_paid: {
        IssueType.unpaid_wages: 1.0,
        IssueType.meal_rest_breaks: 0.3,
        IssueType.misclassification: 0.3,
    },
    AnswerKey.treated_unfairly: {
        IssueType.discrimination: 0.5,
        IssueType.harassment: 0.5,
    },
    AnswerKey.fired_laid_off: {
        IssueType.wrongful_termination: 1.0,
    },
    AnswerKey.unsafe_conditions: {
        IssueType.workplace_safety: 1.0,
    },
    AnswerKey.benefits_issue: {
        IssueType.unemployment_benefits: 0.5,
        IssueType.disability_insurance: 0.5,
        IssueType.paid_family_leave: 0.5,
    },
    AnswerKey.reported_problem: {
        IssueType.retaliation: 1.0,
        IssueType.whistleblower: 0.5,
    },

    # Q2: pay_details
    AnswerKey.pay_not_received: {
        IssueType.unpaid_wages: 1.0,
    },
    AnswerKey.pay_misclassified: {
        IssueType.misclassification: 1.0,
        IssueType.unpaid_wages: 0.5,
    },
    AnswerKey.pay_breaks_denied: {
        IssueType.meal_rest_breaks: 1.0,
    },
    AnswerKey.pay_na: {},

    # Q3: unfair_details
    AnswerKey.unfair_protected_class: {
        IssueType.discrimination: 1.0,
    },
    AnswerKey.unfair_hostile_env: {
        IssueType.harassment: 1.0,
    },
    AnswerKey.unfair_leave_denied: {
        IssueType.family_medical_leave: 1.0,
    },
    AnswerKey.unfair_na: {},

    # Q4: retaliation
    AnswerKey.retaliation_yes: {
        IssueType.retaliation: 1.0,
    },
    AnswerKey.retaliation_no: {},

    # Q5: reported_what
    AnswerKey.reported_safety: {
        IssueType.workplace_safety: 0.5,
        IssueType.whistleblower: 1.0,
    },
    AnswerKey.reported_pay_violation: {
        IssueType.unpaid_wages: 0.3,
        IssueType.whistleblower: 0.5,
    },
    AnswerKey.reported_discrimination: {
        IssueType.discrimination: 0.3,
        IssueType.whistleblower: 0.5,
    },
    AnswerKey.reported_legal_violation: {
        IssueType.whistleblower: 1.0,
    },
    AnswerKey.reported_na: {},

    # Q6: employment_status
    AnswerKey.status_still_employed: {},
    AnswerKey.status_terminated: {
        IssueType.wrongful_termination: 0.3,
    },
    AnswerKey.status_quit: {},

    # Q7: employer_type (no scoring — handled separately)
    AnswerKey.employer_private: {},
    AnswerKey.employer_government: {},
    AnswerKey.employer_unsure: {},

    # Q8: benefits_needed
    AnswerKey.need_unemployment: {
        IssueType.unemployment_benefits: 1.0,
    },
    AnswerKey.need_disability: {
        IssueType.disability_insurance: 1.0,
    },
    AnswerKey.need_family_leave: {
        IssueType.paid_family_leave: 1.0,
        IssueType.family_medical_leave: 0.5,
    },
    AnswerKey.need_none: {},
}


# ── Cross-reference: IssueType → ClaimType values ──────────────────

ISSUE_TO_CLAIM: dict[IssueType, list[str]] = {
    IssueType.unpaid_wages: [ClaimType.wage_theft.value],
    IssueType.discrimination: [ClaimType.feha_discrimination.value],
    IssueType.harassment: [ClaimType.feha_discrimination.value],
    IssueType.wrongful_termination: [ClaimType.wrongful_termination.value],
    IssueType.retaliation: [ClaimType.retaliation_whistleblower.value],
    IssueType.family_medical_leave: [ClaimType.cfra_family_leave.value],
    IssueType.workplace_safety: [],
    IssueType.misclassification: [ClaimType.misclassification.value],
    IssueType.unemployment_benefits: [],
    IssueType.disability_insurance: [],
    IssueType.paid_family_leave: [],
    IssueType.meal_rest_breaks: [ClaimType.wage_theft.value],
    IssueType.whistleblower: [ClaimType.retaliation_whistleblower.value],
}

# IssueType → IncidentType mapping (subset that has incident docs)
_ISSUE_TO_INCIDENT: dict[IssueType, str] = {
    IssueType.unpaid_wages: "unpaid_wages",
    IssueType.discrimination: "discrimination",
    IssueType.harassment: "harassment",
    IssueType.wrongful_termination: "wrongful_termination",
    IssueType.retaliation: "retaliation",
    IssueType.family_medical_leave: "family_medical_leave",
    IssueType.workplace_safety: "workplace_safety",
    IssueType.misclassification: "misclassification",
    IssueType.meal_rest_breaks: "meal_rest_breaks",
    IssueType.whistleblower: "whistleblower",
}

# Wage-related issue types that benefit from the unpaid wages calculator
_WAGE_ISSUES: set[IssueType] = {
    IssueType.unpaid_wages,
    IssueType.meal_rest_breaks,
    IssueType.misclassification,
}

# Short descriptions per IssueType for the result cards
_ISSUE_DESCRIPTIONS: dict[IssueType, str] = {
    IssueType.unpaid_wages: "Your employer may owe you unpaid wages. California law requires timely payment of all earned wages.",
    IssueType.discrimination: "You may have experienced illegal workplace discrimination based on a protected characteristic under California's FEHA.",
    IssueType.harassment: "You may have a claim for workplace harassment or hostile work environment under California law.",
    IssueType.wrongful_termination: "Your termination may have violated California law or public policy.",
    IssueType.retaliation: "You may have been retaliated against for exercising a protected legal right.",
    IssueType.family_medical_leave: "You may have been denied family or medical leave rights under CFRA/FMLA.",
    IssueType.workplace_safety: "Your workplace may have unsafe conditions that violate Cal/OSHA standards.",
    IssueType.misclassification: "You may be misclassified as an independent contractor when you should be treated as an employee.",
    IssueType.unemployment_benefits: "You may be eligible for unemployment insurance benefits through EDD.",
    IssueType.disability_insurance: "You may be eligible for State Disability Insurance (SDI) benefits through EDD.",
    IssueType.paid_family_leave: "You may be eligible for Paid Family Leave (PFL) benefits through EDD.",
    IssueType.meal_rest_breaks: "Your employer may owe you premium pay for missed meal or rest breaks.",
    IssueType.whistleblower: "You may have whistleblower protections for reporting illegal activity at your workplace.",
}


# ── Scoring ─────────────────────────────────────────────────────────

SCORE_THRESHOLD = 0.8


def _build_tool_recommendations(issue_type: IssueType) -> tuple[ToolRecommendation, ...]:
    """Build tool recommendations for a given issue type."""
    tools: list[ToolRecommendation] = []

    # Agency routing (always)
    tools.append(
        ToolRecommendation(
            tool_name="agency_routing",
            tool_label="Agency Routing Guide",
            tool_path="/tools/agency-routing",
            description="Find which government agency handles your complaint and how to file.",
            prefill_params={"issue_type": issue_type.value},
        )
    )

    # Deadline calculator (if claim types exist)
    claim_types = ISSUE_TO_CLAIM[issue_type]
    if claim_types:
        tools.append(
            ToolRecommendation(
                tool_name="deadline_calculator",
                tool_label="Deadline Calculator",
                tool_path="/tools/deadline-calculator",
                description="Check your filing deadlines to make sure you don't miss any cutoff dates.",
                prefill_params={"claim_type": claim_types[0]},
            )
        )

    # Incident documentation (if incident type exists)
    if issue_type in _ISSUE_TO_INCIDENT:
        tools.append(
            ToolRecommendation(
                tool_name="incident_docs",
                tool_label="Incident Documentation Helper",
                tool_path="/tools/incident-docs",
                description="Document what happened while details are fresh. All data stays in your browser.",
                prefill_params={"incident_type": _ISSUE_TO_INCIDENT[issue_type]},
            )
        )

    # Unpaid wages calculator (if wage-related)
    if issue_type in _WAGE_ISSUES:
        tools.append(
            ToolRecommendation(
                tool_name="unpaid_wages_calculator",
                tool_label="Unpaid Wages Calculator",
                tool_path="/tools/unpaid-wages-calculator",
                description="Estimate how much you may be owed including penalties and interest.",
            )
        )

    return tuple(tools)


DISCLAIMER = (
    "This questionnaire provides general guidance to help you identify "
    "potential employment law issues based on your answers. It is not "
    "legal advice, and it does not create an attorney-client relationship. "
    "Employment law is complex, and your specific facts may lead to "
    "different conclusions. Consult a licensed California employment "
    "attorney for advice about your specific situation."
)


# ── Public API ──────────────────────────────────────────────────────


def get_questions() -> list[IntakeQuestion]:
    """Return the full questionnaire."""
    return list(QUESTIONS)


def build_intake_query(result: IntakeResult) -> str:
    """Convert IntakeResult into a natural-language query for RAG retrieval.

    Produces a first-person query describing the user's situation, employment
    status, and identified issues — optimised for the consumer RAG pipeline.
    """
    parts: list[str] = ["I am a California employee"]

    # Employment status
    if result.employment_status == "terminated":
        parts.append("who was recently terminated")
    elif result.employment_status == "quit":
        parts.append("who recently quit")
    else:
        parts.append("who is still employed")

    # Government employer
    if result.is_government_employee:
        parts.append("working for a government employer")

    # Issue clauses (sorted by confidence desc — high before medium)
    confidence_order = {"high": 0, "medium": 1}
    sorted_issues = sorted(
        result.identified_issues,
        key=lambda i: confidence_order.get(i.confidence, 2),
    )
    clauses = [
        ISSUE_QUERY_CLAUSES[issue.issue_type]
        for issue in sorted_issues
        if issue.issue_type in ISSUE_QUERY_CLAUSES
    ]

    if clauses:
        parts.append(". Specifically, " + "; ".join(clauses))

    query = " ".join(parts)
    query += ". What are my rights under California law and what steps should I take?"
    return query


def evaluate_intake(answers: list[str]) -> IntakeResult:
    """Score answers, identify issues, and return tool recommendations.

    Args:
        answers: List of AnswerKey value strings selected by the user.

    Returns:
        IntakeResult with identified issues and recommendations.

    Raises:
        ValueError: If any answer is not a valid AnswerKey.
    """
    # Validate all answers
    answer_keys: list[AnswerKey] = []
    for raw in answers:
        try:
            answer_keys.append(AnswerKey(raw))
        except ValueError:
            raise ValueError(f"Invalid answer key: {raw!r}")

    answer_set = set(answer_keys)

    # Score each IssueType
    scores: dict[IssueType, float] = {it: 0.0 for it in IssueType}
    for key in answer_keys:
        signals = SIGNAL_MAP.get(key, {})
        for issue_type, weight in signals.items():
            scores[issue_type] += weight

    # Detect government employee
    is_government_employee = AnswerKey.employer_government in answer_set

    # Detect employment status
    if AnswerKey.status_terminated in answer_set:
        employment_status = "terminated"
    elif AnswerKey.status_quit in answer_set:
        employment_status = "quit"
    else:
        employment_status = "still_employed"

    # Build identified issues (above threshold, sorted by score desc)
    identified_issues: list[IdentifiedIssue] = []
    for issue_type, score in sorted(scores.items(), key=lambda x: -x[1]):
        if score < SCORE_THRESHOLD:
            continue

        confidence = "high" if score >= 1.5 else "medium"
        claim_types = list(ISSUE_TO_CLAIM[issue_type])

        # Government employees get an additional claim type
        if is_government_employee and claim_types:
            claim_types.append(ClaimType.government_employee.value)

        has_deadline_urgency = len(ISSUE_TO_CLAIM[issue_type]) > 0

        identified_issues.append(
            IdentifiedIssue(
                issue_type=issue_type,
                issue_label=ISSUE_TYPE_LABELS[issue_type],
                confidence=confidence,
                description=_ISSUE_DESCRIPTIONS[issue_type],
                related_claim_types=tuple(claim_types),
                tools=_build_tool_recommendations(issue_type),
                has_deadline_urgency=has_deadline_urgency,
            )
        )

    # Build summary
    if not identified_issues:
        summary = (
            "Based on your answers, we couldn't identify a specific employment "
            "law issue. Consider speaking with a California employment attorney "
            "for personalized guidance."
        )
    elif len(identified_issues) == 1:
        summary = (
            f"Based on your answers, your situation most closely matches: "
            f"{identified_issues[0].issue_label}. "
            f"Review the recommended tools below to take the next step."
        )
    else:
        labels = ", ".join(i.issue_label for i in identified_issues[:3])
        summary = (
            f"Based on your answers, your situation may involve multiple issues: "
            f"{labels}. Review the recommended tools below for each issue."
        )

    return IntakeResult(
        identified_issues=identified_issues,
        is_government_employee=is_government_employee,
        employment_status=employment_status,
        summary=summary,
    )
