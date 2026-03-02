"""Statute of limitations deadline calculator.

Pure computation — no DB, no ML, no external services.
Users provide a claim type and incident date; the calculator returns
all relevant filing deadlines with urgency warnings.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum


class ClaimType(str, Enum):
    """California employment claim types."""

    feha_discrimination = "feha_discrimination"
    wage_theft = "wage_theft"
    wrongful_termination = "wrongful_termination"
    retaliation_whistleblower = "retaliation_whistleblower"
    paga = "paga"
    cfra_family_leave = "cfra_family_leave"
    government_employee = "government_employee"
    misclassification = "misclassification"


# Human-readable labels
CLAIM_TYPE_LABELS: dict[ClaimType, str] = {
    ClaimType.feha_discrimination: "FEHA Discrimination / Harassment",
    ClaimType.wage_theft: "Wage Theft / Unpaid Wages",
    ClaimType.wrongful_termination: "Wrongful Termination",
    ClaimType.retaliation_whistleblower: "Retaliation / Whistleblower",
    ClaimType.paga: "PAGA (Private Attorneys General Act)",
    ClaimType.cfra_family_leave: "CFRA / Family Leave Violations",
    ClaimType.government_employee: "Government Employee Claims",
    ClaimType.misclassification: "Worker Misclassification",
}


class UrgencyLevel(str, Enum):
    """Urgency classification for a deadline."""

    expired = "expired"
    critical = "critical"  # <30 days
    urgent = "urgent"  # <90 days
    normal = "normal"


@dataclass(frozen=True)
class DeadlineRule:
    """A single filing deadline rule for a claim type."""

    name: str
    description: str
    filing_entity: str
    legal_citation: str
    portal_url: str
    notes: str = ""
    # Exactly one offset type should be set
    days: int | None = None
    months: int | None = None
    years: int | None = None


@dataclass(frozen=True)
class DeadlineResult:
    """A computed deadline with urgency classification."""

    name: str
    description: str
    filing_entity: str
    legal_citation: str
    portal_url: str
    notes: str
    deadline_date: date
    days_remaining: int
    urgency: UrgencyLevel


# ── Date arithmetic helpers ──────────────────────────────────────────


def _add_years(d: date, years: int) -> date:
    """Add years, handling Feb 29 → Feb 28 in non-leap years."""
    target_year = d.year + years
    if d.month == 2 and d.day == 29:
        if not calendar.isleap(target_year):
            return date(target_year, 2, 28)
    return d.replace(year=target_year)


def _add_months(d: date, months: int) -> date:
    """Add months, clamping day to month-end on overflow."""
    total_months = (d.year * 12 + d.month - 1) + months
    target_year = total_months // 12
    target_month = total_months % 12 + 1
    max_day = calendar.monthrange(target_year, target_month)[1]
    return date(target_year, target_month, min(d.day, max_day))


def _apply_offset(d: date, rule: DeadlineRule) -> date:
    """Apply the rule's offset to the incident date."""
    if rule.years is not None:
        return _add_years(d, rule.years)
    if rule.months is not None:
        return _add_months(d, rule.months)
    if rule.days is not None:
        return d + timedelta(days=rule.days)
    raise ValueError(f"DeadlineRule '{rule.name}' has no offset set")


def _classify_urgency(days_remaining: int) -> UrgencyLevel:
    if days_remaining < 0:
        return UrgencyLevel.expired
    if days_remaining < 30:
        return UrgencyLevel.critical
    if days_remaining < 90:
        return UrgencyLevel.urgent
    return UrgencyLevel.normal


# ── Deadline rules per claim type ────────────────────────────────────

DEADLINE_RULES: dict[ClaimType, list[DeadlineRule]] = {
    ClaimType.feha_discrimination: [
        DeadlineRule(
            name="CRD Complaint",
            description="File a complaint with the California Civil Rights Department (formerly DFEH).",
            filing_entity="Civil Rights Department (CRD)",
            legal_citation="Gov. Code \u00a712960(d)",
            portal_url="https://calcivilrights.ca.gov/complaintprocess/",
            years=3,
        ),
        DeadlineRule(
            name="EEOC Charge",
            description="File a charge with the Equal Employment Opportunity Commission (federal cross-file).",
            filing_entity="EEOC",
            legal_citation="42 U.S.C. \u00a72000e-5(e)",
            portal_url="https://www.eeoc.gov/filing-charge-discrimination",
            notes="300-day deadline applies because California has a state agency (CRD) with a work-sharing agreement.",
            days=300,
        ),
        DeadlineRule(
            name="Civil Suit (Right-to-Sue)",
            description="File a civil lawsuit after obtaining a right-to-sue notice from CRD.",
            filing_entity="Superior Court",
            legal_citation="Gov. Code \u00a712965(b)",
            portal_url="https://www.courts.ca.gov/selfhelp-employmentlaw.htm",
            notes="Must first file with CRD and obtain right-to-sue letter. Statute runs from the discriminatory act, not the letter.",
            years=4,
        ),
    ],
    ClaimType.wage_theft: [
        DeadlineRule(
            name="DLSE / Labor Commissioner Claim",
            description="File a wage claim with the Division of Labor Standards Enforcement.",
            filing_entity="Labor Commissioner (DLSE)",
            legal_citation="Lab. Code \u00a798; CCP \u00a7338(a)",
            portal_url="https://www.dir.ca.gov/dlse/howtofilewageclaim.htm",
            years=3,
        ),
        DeadlineRule(
            name="Court Action \u2014 Oral Agreement",
            description="Sue for unpaid wages based on an oral employment agreement.",
            filing_entity="Superior Court",
            legal_citation="CCP \u00a7339(1)",
            portal_url="https://www.courts.ca.gov/selfhelp-smallclaims.htm",
            notes="Applies to verbal promises of pay, bonuses, or commissions.",
            years=2,
        ),
        DeadlineRule(
            name="Court Action \u2014 Written Agreement",
            description="Sue for unpaid wages based on a written employment agreement.",
            filing_entity="Superior Court",
            legal_citation="CCP \u00a7337(a)",
            portal_url="https://www.courts.ca.gov/selfhelp-smallclaims.htm",
            years=4,
        ),
        DeadlineRule(
            name="UCL (Unfair Business Practices)",
            description="Sue under California's Unfair Competition Law for unlawful wage practices.",
            filing_entity="Superior Court",
            legal_citation="Bus. & Prof. Code \u00a717208",
            portal_url="https://www.courts.ca.gov/selfhelp-employmentlaw.htm",
            notes="Allows recovery of wages as restitution; no punitive damages.",
            years=4,
        ),
        DeadlineRule(
            name="PAGA Notice (Wage Violations)",
            description="Send notice to LWDA before filing a PAGA action for wage violations.",
            filing_entity="LWDA",
            legal_citation="Lab. Code \u00a72699.3(a)",
            portal_url="https://www.dir.ca.gov/Private-Attorneys-General-Act/Private-Attorneys-General-Act.html",
            notes="Must send LWDA notice before filing suit. Court action within 65 days after notice.",
            years=1,
        ),
    ],
    ClaimType.wrongful_termination: [
        DeadlineRule(
            name="Tort Claim (Public Policy)",
            description="File a wrongful termination in violation of public policy lawsuit.",
            filing_entity="Superior Court",
            legal_citation="CCP \u00a7335.1",
            portal_url="https://www.courts.ca.gov/selfhelp-employmentlaw.htm",
            years=2,
        ),
        DeadlineRule(
            name="Breach of Oral Contract",
            description="Sue for wrongful termination based on an oral employment agreement.",
            filing_entity="Superior Court",
            legal_citation="CCP \u00a7339(1)",
            portal_url="https://www.courts.ca.gov/selfhelp-employmentlaw.htm",
            years=2,
        ),
        DeadlineRule(
            name="Breach of Written Contract",
            description="Sue for wrongful termination based on a written employment agreement.",
            filing_entity="Superior Court",
            legal_citation="CCP \u00a7337(a)",
            portal_url="https://www.courts.ca.gov/selfhelp-employmentlaw.htm",
            years=4,
        ),
    ],
    ClaimType.retaliation_whistleblower: [
        DeadlineRule(
            name="Court Action (Lab. Code \u00a71102.5)",
            description="File a whistleblower retaliation lawsuit in court.",
            filing_entity="Superior Court",
            legal_citation="Lab. Code \u00a71102.5; CCP \u00a7338",
            portal_url="https://www.courts.ca.gov/selfhelp-employmentlaw.htm",
            years=3,
        ),
        DeadlineRule(
            name="DLSE Retaliation Complaint",
            description="File a retaliation complaint with the Labor Commissioner.",
            filing_entity="Labor Commissioner (DLSE)",
            legal_citation="Lab. Code \u00a798.6",
            portal_url="https://www.dir.ca.gov/dlse/howtofileretaliation.htm",
            notes="Shorter deadline than court action. DLSE investigates and may hold a hearing.",
            months=6,
        ),
    ],
    ClaimType.paga: [
        DeadlineRule(
            name="LWDA Notice",
            description="Send written notice to the Labor and Workforce Development Agency and employer.",
            filing_entity="LWDA",
            legal_citation="Lab. Code \u00a72699.3(a)(2)",
            portal_url="https://www.dir.ca.gov/Private-Attorneys-General-Act/Private-Attorneys-General-Act.html",
            notes="Required before filing suit. LWDA has 65 days to respond.",
            years=1,
        ),
        DeadlineRule(
            name="Court Filing After LWDA Notice",
            description="File PAGA action in court after the 65-day LWDA notice period.",
            filing_entity="Superior Court",
            legal_citation="Lab. Code \u00a72699.3(a)(2)(A)",
            portal_url="https://www.courts.ca.gov/selfhelp-employmentlaw.htm",
            notes="65 calendar days after LWDA notice, if LWDA does not investigate. Starts from incident date + 65 days for calculation purposes.",
            days=430,  # ~1yr + 65d
        ),
    ],
    ClaimType.cfra_family_leave: [
        DeadlineRule(
            name="CRD Complaint",
            description="File a CFRA violation complaint with the Civil Rights Department.",
            filing_entity="Civil Rights Department (CRD)",
            legal_citation="Gov. Code \u00a712945.2; Gov. Code \u00a712960",
            portal_url="https://calcivilrights.ca.gov/complaintprocess/",
            years=3,
        ),
        DeadlineRule(
            name="EEOC Charge (FMLA Cross-File)",
            description="File a charge with the EEOC for related federal FMLA violations.",
            filing_entity="EEOC",
            legal_citation="29 U.S.C. \u00a72617",
            portal_url="https://www.eeoc.gov/filing-charge-discrimination",
            notes="For federal FMLA claims. California CFRA claims go through CRD.",
            days=300,
        ),
    ],
    ClaimType.government_employee: [
        DeadlineRule(
            name="Government Tort Claim",
            description="File a tort claim with the employing government agency before suing.",
            filing_entity="Government Agency",
            legal_citation="Gov. Code \u00a7911.2",
            portal_url="https://www.courts.ca.gov/documents/govt-tort-claim.pdf",
            notes="Must file tort claim BEFORE filing a lawsuit. Deadline runs from the date of the incident.",
            months=6,
        ),
        DeadlineRule(
            name="Court Action After Claim Denial",
            description="File a lawsuit after the government denies your tort claim (or fails to respond in 45 days).",
            filing_entity="Superior Court",
            legal_citation="Gov. Code \u00a7945.6",
            portal_url="https://www.courts.ca.gov/selfhelp-employmentlaw.htm",
            notes="6 months to file tort claim + 6 months after denial. This is the outer limit from the incident date.",
            months=12,
        ),
    ],
    ClaimType.misclassification: [
        DeadlineRule(
            name="DLSE Misclassification Complaint",
            description="File a misclassification complaint with the Labor Commissioner.",
            filing_entity="Labor Commissioner (DLSE)",
            legal_citation="Lab. Code \u00a7226.8",
            portal_url="https://www.dir.ca.gov/dlse/howtofilewageclaim.htm",
            years=3,
        ),
        DeadlineRule(
            name="Court Action \u2014 Unpaid Wages",
            description="Sue for unpaid wages and benefits resulting from misclassification.",
            filing_entity="Superior Court",
            legal_citation="CCP \u00a7338(a)",
            portal_url="https://www.courts.ca.gov/selfhelp-smallclaims.htm",
            years=3,
        ),
        DeadlineRule(
            name="UCL (Unfair Business Practices)",
            description="Sue under the UCL for misclassification as an unfair business practice.",
            filing_entity="Superior Court",
            legal_citation="Bus. & Prof. Code \u00a717208",
            portal_url="https://www.courts.ca.gov/selfhelp-employmentlaw.htm",
            notes="Allows recovery of wages as restitution.",
            years=4,
        ),
    ],
}

DISCLAIMER = (
    "These deadlines are general estimates based on California law. "
    "Actual deadlines may vary depending on tolling, discovery rules, "
    "continuing violations, or other legal doctrines. Weekend/holiday "
    "adjustments are not applied (CCP \u00a712a applies only to specific "
    "court filing deadlines). Consult a licensed California employment "
    "attorney for advice about your specific situation."
)


def calculate_deadlines(
    claim_type: ClaimType,
    incident_date: date,
    *,
    as_of: date | None = None,
) -> list[DeadlineResult]:
    """Calculate all filing deadlines for a claim type.

    Args:
        claim_type: The type of employment claim.
        incident_date: The date of the incident / last violation.
        as_of: Reference date for days_remaining (defaults to today).

    Returns:
        List of DeadlineResult sorted by deadline_date ascending.
    """
    reference = as_of or date.today()
    rules = DEADLINE_RULES.get(claim_type, [])

    results: list[DeadlineResult] = []
    for rule in rules:
        deadline_date = _apply_offset(incident_date, rule)
        days_remaining = (deadline_date - reference).days
        urgency = _classify_urgency(days_remaining)

        results.append(
            DeadlineResult(
                name=rule.name,
                description=rule.description,
                filing_entity=rule.filing_entity,
                legal_citation=rule.legal_citation,
                portal_url=rule.portal_url,
                notes=rule.notes,
                deadline_date=deadline_date,
                days_remaining=days_remaining,
                urgency=urgency,
            )
        )

    results.sort(key=lambda r: r.deadline_date)
    return results
