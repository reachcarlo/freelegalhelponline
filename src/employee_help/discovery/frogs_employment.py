"""DISC-002 Form Interrogatories (Employment Law) — section registry with directional filtering.

DISC-002 sections are directional — some are "directed to employer"
(e.g., 201.x about adverse actions taken) and some are "directed to
employee" (e.g., 210.x about employee's income loss). The suggestion
function filters based on the propounding party's role.

Pure data — no DB, no ML, no external services.
"""

from __future__ import annotations

from dataclasses import dataclass

from .claim_mapping import get_suggestions_for_claims
from .models import ClaimType, PartyRole


@dataclass(frozen=True)
class Disc002Section:
    """Metadata for a DISC-002 section group."""

    number: str          # Section group number (e.g. "200", "201", "204")
    title: str
    subsections: tuple[str, ...]
    directed_to: str     # "both", "employer", "employee"
    description: str


# ---------------------------------------------------------------------------
# Section registry
# ---------------------------------------------------------------------------

DISC002_SECTIONS: dict[str, Disc002Section] = {
    "200": Disc002Section(
        number="200",
        title="Employment Relationship",
        subsections=("200.1", "200.2", "200.3", "200.4", "200.5", "200.6"),
        directed_to="both",
        description="Nature of the employment relationship, agreements, policies.",
    ),
    "201": Disc002Section(
        number="201",
        title="Adverse Employment Actions / Termination",
        subsections=("201.1", "201.2", "201.3", "201.4", "201.5", "201.6", "201.7"),
        directed_to="employer",
        description="Termination details, post-termination facts, replacements.",
    ),
    "202": Disc002Section(
        number="202",
        title="Discrimination",
        subsections=("202.1", "202.2"),
        directed_to="employee",
        description="Contentions regarding discriminatory adverse employment actions.",
    ),
    "203": Disc002Section(
        number="203",
        title="Harassment",
        subsections=("203.1",),
        directed_to="employee",
        description="Contentions regarding unlawful workplace harassment.",
    ),
    "204": Disc002Section(
        number="204",
        title="Disability Discrimination",
        subsections=("204.1", "204.2", "204.4", "204.5", "204.6", "204.7"),
        directed_to="both",
        description="Disability allegations, accommodation requests, interactive process.",
    ),
    "205": Disc002Section(
        number="205",
        title="Wrongful Discharge in Violation of Public Policy",
        subsections=("205.1",),
        directed_to="both",
        description="Contentions that adverse action violated public policy.",
    ),
    "206": Disc002Section(
        number="206",
        title="Defamation",
        subsections=("206.1", "206.2", "206.3"),
        directed_to="both",
        description="Defamatory statements published by employer agents.",
    ),
    "207": Disc002Section(
        number="207",
        title="Internal / External Complaints",
        subsections=("207.1", "207.2"),
        directed_to="both",
        description="Internal complaint policies and employee complaints.",
    ),
    "208": Disc002Section(
        number="208",
        title="Government Agency Complaints",
        subsections=("208.1", "208.2"),
        directed_to="both",
        description="Claims filed with CRD/EEOC/DLSE and employer responses.",
    ),
    "209": Disc002Section(
        number="209",
        title="Other Claims / Previous Actions",
        subsections=("209.1", "209.2"),
        directed_to="both",
        description="Prior employment lawsuits filed by employee or against employer.",
    ),
    "210": Disc002Section(
        number="210",
        title="Loss of Income / Benefits (Employee)",
        subsections=("210.1", "210.2", "210.3", "210.4", "210.5", "210.6"),
        directed_to="employee",
        description="Employee's income loss, mitigation efforts, subsequent employment.",
    ),
    "211": Disc002Section(
        number="211",
        title="Loss of Income / Benefits (Employer Contentions)",
        subsections=("211.1", "211.2", "211.3"),
        directed_to="employer",
        description="Employer's contentions about benefits, mitigation, and lost income.",
    ),
    "212": Disc002Section(
        number="212",
        title="Physical, Mental, or Emotional Injuries",
        subsections=("212.1", "212.2", "212.3", "212.4", "212.5", "212.6", "212.7"),
        directed_to="employee",
        description="Injuries attributed to adverse employment action, treatment, medications.",
    ),
    "213": Disc002Section(
        number="213",
        title="Other Damages",
        subsections=("213.1", "213.2"),
        directed_to="employee",
        description="Other damages and supporting documents.",
    ),
    "214": Disc002Section(
        number="214",
        title="Insurance",
        subsections=("214.1", "214.2"),
        directed_to="both",
        description="Insurance policies covering the adverse employment action.",
    ),
    "215": Disc002Section(
        number="215",
        title="Investigation",
        subsections=("215.1", "215.2"),
        directed_to="both",
        description="Interviews and statements obtained concerning the action.",
    ),
    "216": Disc002Section(
        number="216",
        title="Affirmative Defenses",
        subsections=("216.1",),
        directed_to="both",
        description="Identification of denials and affirmative defenses.",
    ),
    "217": Disc002Section(
        number="217",
        title="Responses to Requests for Admission",
        subsections=("217.1",),
        directed_to="both",
        description="Explanation of non-admissions in response to RFAs.",
    ),
}


# ---------------------------------------------------------------------------
# Directional filter sets
# ---------------------------------------------------------------------------

# Sections appropriate when propounding TO the employer (i.e., plaintiff propounds)
EMPLOYER_DIRECTED_SECTIONS: set[str] = set()
for _sec in DISC002_SECTIONS.values():
    if _sec.directed_to in ("both", "employer"):
        EMPLOYER_DIRECTED_SECTIONS.update(_sec.subsections)

# Sections appropriate when propounding TO the employee (i.e., defendant propounds)
EMPLOYEE_DIRECTED_SECTIONS: set[str] = set()
for _sec in DISC002_SECTIONS.values():
    if _sec.directed_to in ("both", "employee"):
        EMPLOYEE_DIRECTED_SECTIONS.update(_sec.subsections)


def suggest_disc002_sections(
    claim_types: list[ClaimType] | tuple[ClaimType, ...],
    party_role: PartyRole,
    *,
    has_rfas: bool = False,
) -> list[str]:
    """Return suggested DISC-002 section numbers, filtered by party role.

    The key insight: if plaintiff is propounding, the interrogatories
    are directed TO the defendant (employer). So we filter to sections
    that are "directed to employer" or "both".

    If defendant is propounding, interrogatories are directed TO the
    plaintiff (employee). So we filter to "directed to employee" or "both".

    Args:
        claim_types: Claim types in the case.
        party_role: Who is propounding (plaintiff or defendant).
        has_rfas: Whether RFAs are also being propounded (adds 217.1).

    Returns:
        Sorted list of section numbers (e.g. ["200.1", "201.1", ...]).
    """
    merged = get_suggestions_for_claims(claim_types)
    sections = set(merged.disc002_sections)

    # Directional filtering
    if party_role == PartyRole.PLAINTIFF:
        # Plaintiff propounds → directed to employer
        sections &= EMPLOYER_DIRECTED_SECTIONS
    else:
        # Defendant propounds → directed to employee
        sections &= EMPLOYEE_DIRECTED_SECTIONS

    # Always include employment relationship (bidirectional)
    sections.add("200.1")

    # Add defenses
    sections.add("216.1")

    # Conditional
    if has_rfas:
        sections.add("217.1")

    return sorted(sections)


def get_sections_for_direction(directed_to: str) -> list[str]:
    """Return all section numbers directed to a specific target.

    Args:
        directed_to: "employer", "employee", or "both".

    Returns:
        Sorted list of matching section numbers.
    """
    result: set[str] = set()
    for sec in DISC002_SECTIONS.values():
        if sec.directed_to == directed_to or sec.directed_to == "both":
            result.update(sec.subsections)
    return sorted(result)
