"""Agency routing guide.

Pure computation — no DB, no ML, no external services.
Users provide an issue type and optionally indicate government employment;
the router returns an ordered list of recommended agencies with filing info.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class IssueType(str, Enum):
    """California employment issue types for agency routing."""

    unpaid_wages = "unpaid_wages"
    discrimination = "discrimination"
    harassment = "harassment"
    wrongful_termination = "wrongful_termination"
    retaliation = "retaliation"
    family_medical_leave = "family_medical_leave"
    workplace_safety = "workplace_safety"
    misclassification = "misclassification"
    unemployment_benefits = "unemployment_benefits"
    disability_insurance = "disability_insurance"
    paid_family_leave = "paid_family_leave"
    meal_rest_breaks = "meal_rest_breaks"
    whistleblower = "whistleblower"


ISSUE_TYPE_LABELS: dict[IssueType, str] = {
    IssueType.unpaid_wages: "Unpaid Wages / Wage Theft",
    IssueType.discrimination: "Discrimination (Race, Gender, Age, Disability, etc.)",
    IssueType.harassment: "Harassment / Hostile Work Environment",
    IssueType.wrongful_termination: "Wrongful Termination",
    IssueType.retaliation: "Retaliation for Exercising Rights",
    IssueType.family_medical_leave: "Family / Medical Leave Violations",
    IssueType.workplace_safety: "Workplace Safety / Health Hazards",
    IssueType.misclassification: "Worker Misclassification (1099 vs W-2)",
    IssueType.unemployment_benefits: "Unemployment Insurance Benefits",
    IssueType.disability_insurance: "State Disability Insurance (SDI)",
    IssueType.paid_family_leave: "Paid Family Leave (PFL)",
    IssueType.meal_rest_breaks: "Meal / Rest Break Violations",
    IssueType.whistleblower: "Whistleblower Protections",
}


class Priority(str, Enum):
    """Recommendation priority level."""

    prerequisite = "prerequisite"
    primary = "primary"
    alternative = "alternative"


@dataclass(frozen=True)
class AgencyInfo:
    """Static information about a California government agency."""

    name: str
    acronym: str
    description: str
    handles: str
    portal_url: str
    phone: str
    filing_methods: list[str] = field(default_factory=list)
    process_overview: str = ""
    typical_timeline: str = ""


@dataclass(frozen=True)
class AgencyRecommendation:
    """A single agency recommendation with context."""

    agency: AgencyInfo
    priority: Priority
    reason: str
    what_to_file: str
    notes: str = ""
    related_claim_type: str | None = None


# ── Agency registry ──────────────────────────────────────────────────

AGENCIES: dict[str, AgencyInfo] = {
    "dlse": AgencyInfo(
        name="Division of Labor Standards Enforcement",
        acronym="DLSE",
        description="The Labor Commissioner's Office enforces California wage and hour laws, investigates retaliation complaints, and resolves wage disputes.",
        handles="Wage claims, meal/rest break violations, retaliation, misclassification",
        portal_url="https://www.dir.ca.gov/dlse/",
        phone="(844) 522-6734",
        filing_methods=["Online", "Mail", "In person at local office"],
        process_overview="File a wage claim or retaliation complaint. DLSE investigates, schedules a settlement conference, and may hold a formal hearing.",
        typical_timeline="3-6 months for investigation; hearing within 12 months",
    ),
    "crd": AgencyInfo(
        name="Civil Rights Department",
        acronym="CRD",
        description="California's primary agency for enforcing civil rights laws including FEHA. Handles discrimination, harassment, and family/medical leave complaints.",
        handles="Discrimination, harassment, FEHA violations, CFRA/family leave",
        portal_url="https://calcivilrights.ca.gov/complaintprocess/",
        phone="(800) 884-1684",
        filing_methods=["Online portal", "Mail", "Phone intake"],
        process_overview="File a complaint online or by mail. CRD investigates, may attempt mediation, and issues a right-to-sue notice if unresolved.",
        typical_timeline="1-3 months for initial review; 12-18 months for full investigation",
    ),
    "edd": AgencyInfo(
        name="Employment Development Department",
        acronym="EDD",
        description="Administers unemployment insurance, state disability insurance, and paid family leave benefits for California workers.",
        handles="Unemployment insurance, SDI, paid family leave",
        portal_url="https://edd.ca.gov/",
        phone="(800) 300-5616",
        filing_methods=["Online (UI Online / SDI Online)", "Phone", "Mail"],
        process_overview="File a claim online or by phone. EDD reviews eligibility, may schedule a phone interview, and issues a determination.",
        typical_timeline="2-4 weeks for initial determination; appeals take 4-8 weeks",
    ),
    "cal_osha": AgencyInfo(
        name="Division of Occupational Safety and Health",
        acronym="Cal/OSHA",
        description="Enforces workplace health and safety standards. Investigates complaints about unsafe working conditions and workplace hazards.",
        handles="Workplace safety violations, health hazards, unsafe conditions",
        portal_url="https://www.dir.ca.gov/dosh/",
        phone="(844) 522-6734",
        filing_methods=["Online", "Phone", "Mail", "In person"],
        process_overview="File a safety complaint (can be anonymous). Cal/OSHA inspects the workplace, issues citations for violations, and requires corrective action.",
        typical_timeline="1-5 days for imminent hazards; 14-30 days for standard complaints",
    ),
    "lwda": AgencyInfo(
        name="Labor & Workforce Development Agency",
        acronym="LWDA",
        description="Oversees California labor enforcement agencies. Receives PAGA (Private Attorneys General Act) notices before employees can file representative actions.",
        handles="PAGA notices for labor code violations",
        portal_url="https://www.dir.ca.gov/Private-Attorneys-General-Act/Private-Attorneys-General-Act.html",
        phone="",
        filing_methods=["Online PAGA notice submission"],
        process_overview="Submit a PAGA notice to LWDA and your employer. After 65 days, if LWDA does not investigate, you may file a civil action.",
        typical_timeline="65-day waiting period after PAGA notice",
    ),
    "eeoc": AgencyInfo(
        name="Equal Employment Opportunity Commission",
        acronym="EEOC",
        description="Federal agency enforcing Title VII, ADA, ADEA, and other federal anti-discrimination laws. Has a work-sharing agreement with California CRD.",
        handles="Federal discrimination claims (Title VII, ADA, ADEA, Equal Pay Act)",
        portal_url="https://www.eeoc.gov/filing-charge-discrimination",
        phone="(800) 669-4000",
        filing_methods=["Online portal", "In person at local office", "Mail"],
        process_overview="File a charge of discrimination. EEOC investigates, may attempt conciliation, and issues a right-to-sue letter if unresolved.",
        typical_timeline="6-10 months for investigation; 180 days for right-to-sue",
    ),
    "calhr": AgencyInfo(
        name="California Department of Human Resources",
        acronym="CalHR",
        description="Manages the state's workforce. State government employees must file internal complaints with CalHR before pursuing external remedies.",
        handles="State government employee complaints, internal grievances",
        portal_url="https://www.calhr.ca.gov/",
        phone="(866) 225-4728",
        filing_methods=["Internal grievance process", "Written complaint"],
        process_overview="File an internal complaint through your department's EEO office or CalHR. Must exhaust administrative remedies before filing with external agencies.",
        typical_timeline="30-90 days for internal review",
    ),
    "superior_court": AgencyInfo(
        name="California Superior Court",
        acronym="Court",
        description="File a civil lawsuit for employment claims. May require exhaustion of administrative remedies (CRD, DLSE) before filing.",
        handles="Civil lawsuits for employment violations, wrongful termination, breach of contract",
        portal_url="https://www.courts.ca.gov/selfhelp-employmentlaw.htm",
        phone="",
        filing_methods=["In person at courthouse", "E-filing (select counties)"],
        process_overview="File a civil complaint in the appropriate Superior Court. Case proceeds through discovery, possible settlement, and trial.",
        typical_timeline="12-24 months to trial; small claims heard within 30-70 days",
    ),
}


# ── Routing rules ────────────────────────────────────────────────────

# Maps IssueType → list of (agency_key, priority, reason, what_to_file, notes, related_claim_type)
_RoutingTuple = tuple[str, Priority, str, str, str, str | None]

_ROUTING_RULES: dict[IssueType, list[_RoutingTuple]] = {
    IssueType.unpaid_wages: [
        ("dlse", Priority.primary, "DLSE is the primary agency for wage claims in California.", "Wage claim (DLSE Form 1)", "", "wage_theft"),
        ("superior_court", Priority.alternative, "You can file a civil lawsuit instead of or after a DLSE claim.", "Civil complaint for unpaid wages", "Consider small claims court for amounts under $12,500.", "wage_theft"),
        ("lwda", Priority.alternative, "File a PAGA notice to pursue penalties on behalf of yourself and coworkers.", "PAGA notice to LWDA", "Requires 65-day waiting period before filing suit.", "wage_theft"),
    ],
    IssueType.discrimination: [
        ("crd", Priority.primary, "CRD enforces California's Fair Employment and Housing Act (FEHA), the primary state anti-discrimination law.", "Pre-complaint inquiry or formal complaint", "", "feha_discrimination"),
        ("eeoc", Priority.alternative, "The EEOC handles federal discrimination claims. CRD and EEOC have a work-sharing agreement, so filing with one can cross-file with the other.", "Charge of discrimination", "300-day filing deadline from the discriminatory act.", "feha_discrimination"),
        ("superior_court", Priority.alternative, "File a civil lawsuit after obtaining a right-to-sue notice from CRD.", "Civil complaint for discrimination", "Must first file with CRD and obtain a right-to-sue letter.", "feha_discrimination"),
    ],
    IssueType.harassment: [
        ("crd", Priority.primary, "CRD handles harassment complaints under FEHA, including sexual harassment and hostile work environment.", "Pre-complaint inquiry or formal complaint", "", "feha_discrimination"),
        ("eeoc", Priority.alternative, "The EEOC handles federal harassment claims under Title VII.", "Charge of discrimination (harassment)", "300-day filing deadline.", "feha_discrimination"),
        ("superior_court", Priority.alternative, "File a civil lawsuit after obtaining a right-to-sue notice.", "Civil complaint for harassment", "Must first file with CRD and obtain a right-to-sue letter.", "feha_discrimination"),
    ],
    IssueType.wrongful_termination: [
        ("superior_court", Priority.primary, "Wrongful termination lawsuits are typically filed directly in court.", "Civil complaint for wrongful termination", "May be based on public policy, breach of contract, or discrimination.", "wrongful_termination"),
        ("crd", Priority.alternative, "If termination was discriminatory, file with CRD first.", "Pre-complaint inquiry or formal complaint", "Only applies if termination was based on a protected characteristic.", "wrongful_termination"),
    ],
    IssueType.retaliation: [
        ("dlse", Priority.primary, "DLSE investigates retaliation complaints for exercising labor rights.", "Retaliation complaint (Labor Code \u00a798.6)", "6-month deadline from the retaliatory act.", "retaliation_whistleblower"),
        ("superior_court", Priority.alternative, "File a civil lawsuit for retaliation.", "Civil complaint for retaliation", "", "retaliation_whistleblower"),
        ("crd", Priority.alternative, "If retaliation is related to a FEHA-protected activity, file with CRD.", "Pre-complaint inquiry or formal complaint", "Applies when retaliation is for opposing discrimination or harassment.", "retaliation_whistleblower"),
    ],
    IssueType.family_medical_leave: [
        ("crd", Priority.primary, "CRD enforces CFRA (California Family Rights Act) and handles family/medical leave violations.", "Pre-complaint inquiry or formal complaint", "", "cfra_family_leave"),
        ("eeoc", Priority.alternative, "The EEOC handles federal FMLA violations.", "Charge of discrimination (FMLA interference)", "For federal FMLA claims; California CFRA claims go through CRD.", "cfra_family_leave"),
    ],
    IssueType.workplace_safety: [
        ("cal_osha", Priority.primary, "Cal/OSHA enforces workplace health and safety standards.", "Safety complaint (can be filed anonymously)", "Complaints can be anonymous. Cal/OSHA must inspect within set timeframes.", None),
        ("dlse", Priority.alternative, "If you were retaliated against for reporting safety concerns, file with DLSE.", "Retaliation complaint", "Separate from the safety complaint itself.", None),
    ],
    IssueType.misclassification: [
        ("dlse", Priority.primary, "DLSE investigates worker misclassification and can recover unpaid wages and benefits.", "Wage claim or misclassification complaint", "", "misclassification"),
        ("superior_court", Priority.alternative, "File a civil lawsuit for damages from misclassification.", "Civil complaint for misclassification", "", "misclassification"),
        ("lwda", Priority.alternative, "File a PAGA notice for misclassification violations.", "PAGA notice to LWDA", "Requires 65-day waiting period before filing suit.", "misclassification"),
    ],
    IssueType.unemployment_benefits: [
        ("edd", Priority.primary, "EDD administers unemployment insurance benefits in California.", "Unemployment insurance claim", "File online at UI Online for fastest processing.", None),
    ],
    IssueType.disability_insurance: [
        ("edd", Priority.primary, "EDD administers State Disability Insurance (SDI) for workers unable to work due to non-work-related illness or injury.", "SDI claim", "File online at SDI Online. Requires medical certification.", None),
    ],
    IssueType.paid_family_leave: [
        ("edd", Priority.primary, "EDD administers Paid Family Leave (PFL) for bonding with a new child or caring for a seriously ill family member.", "PFL claim", "File online at SDI Online. Provides up to 8 weeks of partial wage replacement.", None),
    ],
    IssueType.meal_rest_breaks: [
        ("dlse", Priority.primary, "DLSE enforces meal and rest break requirements under California labor law.", "Wage claim for meal/rest break violations", "Employees are entitled to premium pay for missed breaks.", "wage_theft"),
        ("lwda", Priority.alternative, "File a PAGA notice for meal/rest break violations on behalf of coworkers.", "PAGA notice to LWDA", "Requires 65-day waiting period before filing suit.", "wage_theft"),
        ("superior_court", Priority.alternative, "File a civil lawsuit for meal/rest break violations.", "Civil complaint for meal/rest break violations", "", "wage_theft"),
    ],
    IssueType.whistleblower: [
        ("dlse", Priority.primary, "DLSE handles whistleblower retaliation complaints under Labor Code \u00a71102.5.", "Retaliation/whistleblower complaint", "", "retaliation_whistleblower"),
        ("superior_court", Priority.alternative, "File a whistleblower retaliation lawsuit in court.", "Civil complaint for whistleblower retaliation", "", "retaliation_whistleblower"),
        ("cal_osha", Priority.alternative, "If you reported workplace safety issues, Cal/OSHA also investigates whistleblower retaliation.", "Safety retaliation complaint", "Applies specifically to health and safety whistleblowing.", "retaliation_whistleblower"),
    ],
}

# Issue types where government employees get a CalHR prerequisite
_GOV_CALHR_PREREQUISITE: set[IssueType] = {
    IssueType.unpaid_wages,
    IssueType.discrimination,
    IssueType.harassment,
    IssueType.retaliation,
    IssueType.family_medical_leave,
    IssueType.meal_rest_breaks,
}

# Issue types where government employees get a tort claim prerequisite
_GOV_TORT_PREREQUISITE: set[IssueType] = {
    IssueType.wrongful_termination,
    IssueType.whistleblower,
}


DISCLAIMER = (
    "This routing guide provides general information about California "
    "government agencies that handle employment complaints. It is not "
    "legal advice. Filing requirements, deadlines, and procedures may "
    "vary depending on your specific situation, employer type, and the "
    "nature of your claim. Consult a licensed California employment "
    "attorney for advice about your specific situation."
)


def get_agency_routing(
    issue_type: IssueType,
    *,
    is_government_employee: bool = False,
) -> list[AgencyRecommendation]:
    """Get agency recommendations for an employment issue.

    Args:
        issue_type: The type of employment issue.
        is_government_employee: Whether the user works for a government agency.

    Returns:
        List of AgencyRecommendation sorted: prerequisite -> primary -> alternative.
    """
    rules = _ROUTING_RULES.get(issue_type, [])

    recommendations: list[AgencyRecommendation] = []

    # Add government employee prerequisites
    if is_government_employee:
        if issue_type in _GOV_CALHR_PREREQUISITE:
            recommendations.append(
                AgencyRecommendation(
                    agency=AGENCIES["calhr"],
                    priority=Priority.prerequisite,
                    reason="As a government employee, you must first file an internal complaint through your department's EEO office or CalHR before pursuing external remedies.",
                    what_to_file="Internal grievance or EEO complaint",
                    notes="Exhaust internal administrative remedies before filing with external agencies.",
                )
            )
        elif issue_type in _GOV_TORT_PREREQUISITE:
            recommendations.append(
                AgencyRecommendation(
                    agency=AGENCIES["superior_court"],
                    priority=Priority.prerequisite,
                    reason="As a government employee, you must file a government tort claim with your employing agency before filing a lawsuit.",
                    what_to_file="Government tort claim (Gov. Code \u00a7911.2)",
                    notes="Must be filed within 6 months of the incident. If denied, you have 6 months to file suit.",
                    related_claim_type="government_employee",
                )
            )

    # Add standard recommendations
    for agency_key, priority, reason, what_to_file, notes, related_claim_type in rules:
        recommendations.append(
            AgencyRecommendation(
                agency=AGENCIES[agency_key],
                priority=priority,
                reason=reason,
                what_to_file=what_to_file,
                notes=notes,
                related_claim_type=related_claim_type,
            )
        )

    # Sort: prerequisite first, then primary, then alternative
    priority_order = {Priority.prerequisite: 0, Priority.primary: 1, Priority.alternative: 2}
    recommendations.sort(key=lambda r: priority_order[r.priority])

    return recommendations
