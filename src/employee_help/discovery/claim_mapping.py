"""Claim-to-discovery mapping for California employment law.

Maps each ClaimType to the discovery tools and sections that are
typically relevant. This is the core intelligence layer that drives
the guided workflow's pre-selection of interrogatories and requests.

Mappings reflect prevailing California employment litigation practice.

Pure data — no DB, no ML, no external services.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import ClaimType


@dataclass(frozen=True)
class DiscoverySuggestions:
    """Suggested discovery for a specific claim type.

    Each field contains identifiers that map to specific tools:
    - disc001_sections: DISC-001 section numbers (e.g. "1.1", "6.1")
    - disc002_sections: DISC-002 section numbers (e.g. "200.1", "201.1")
    - srog_categories: Category slugs for the SROG request bank
    - rfpd_categories: Category slugs for the RFPD request bank
    - rfa_categories: Category slugs for the RFA request bank
    """

    disc001_sections: tuple[str, ...]
    disc002_sections: tuple[str, ...]
    srog_categories: tuple[str, ...]
    rfpd_categories: tuple[str, ...]
    rfa_categories: tuple[str, ...]


def merge_suggestions(suggestions: list[DiscoverySuggestions]) -> DiscoverySuggestions:
    """Merge multiple DiscoverySuggestions into a single de-duped set.

    Used when a case has multiple claim types — each claim's suggestions
    are unioned together.
    """
    disc001: set[str] = set()
    disc002: set[str] = set()
    srog: set[str] = set()
    rfpd: set[str] = set()
    rfa: set[str] = set()

    for s in suggestions:
        disc001.update(s.disc001_sections)
        disc002.update(s.disc002_sections)
        srog.update(s.srog_categories)
        rfpd.update(s.rfpd_categories)
        rfa.update(s.rfa_categories)

    return DiscoverySuggestions(
        disc001_sections=tuple(sorted(disc001)),
        disc002_sections=tuple(sorted(disc002)),
        srog_categories=tuple(sorted(srog)),
        rfpd_categories=tuple(sorted(rfpd)),
        rfa_categories=tuple(sorted(rfa)),
    )


# ---------------------------------------------------------------------------
# Common section sets (reused across claim types)
# ---------------------------------------------------------------------------

# DISC-001 sections that apply to virtually every employment case
_DISC001_ALWAYS = (
    "1.1",   # Identity
    "2.1",   # General background
    "2.5",   # Contact info
    "2.6",   # Occupation
    "2.7",   # Education
    "4.1",   # Insurance
    "11.1",  # Other claims
    "12.1",  # Witnesses
    "12.2",  # Interviews
    "12.3",  # Statements
    "12.6",  # Reports
    "15.1",  # Denials and defenses
)

_DISC001_INJURIES = (
    "6.1", "6.2", "6.3", "6.4", "6.5", "6.6", "6.7",
)

_DISC001_INCOME_LOSS = (
    "8.1", "8.2", "8.3", "8.4", "8.5", "8.6", "8.7", "8.8",
)

_DISC001_DAMAGES = (
    "9.1", "9.2",
)

_DISC001_MEDICAL_HISTORY = (
    "10.1", "10.2", "10.3",
)

_DISC001_INVESTIGATION = (
    "12.1", "12.2", "12.3", "12.4", "12.5", "12.6", "12.7",
    "13.1", "13.2",
)

# DISC-002 sections common to most employment claims
_DISC002_EMPLOYMENT_REL = (
    "200.1", "200.2", "200.3", "200.4",
)

_DISC002_ADVERSE_ACTION = (
    "201.1", "201.2", "201.3", "201.4", "201.5", "201.6", "201.7",
)

_DISC002_INCOME_EMPLOYEE = (
    "210.1", "210.2", "210.3", "210.4", "210.5", "210.6",
)

_DISC002_INCOME_EMPLOYER = (
    "211.1", "211.2", "211.3",
)

_DISC002_INJURIES = (
    "212.1", "212.2", "212.3", "212.4", "212.5", "212.6", "212.7",
)

_DISC002_DAMAGES = (
    "213.1", "213.2",
)

_DISC002_STANDARD_TAIL = (
    "214.1", "214.2",  # Insurance
    "215.1", "215.2",  # Investigation
    "216.1",            # Defenses
)

# Standard SROG/RFPD/RFA categories for most employment claims
_SROG_STANDARD = (
    "employment_relationship",
    "adverse_action",
    "decision_makers",
    "investigation",
    "policies",
    "damages",
)

_RFPD_STANDARD = (
    "personnel_file",
    "policies_handbooks",
    "communications",
    "investigation_docs",
    "organizational",
)

_RFA_STANDARD = (
    "employment_facts",
    "adverse_action_facts",
    "document_genuineness",
)


# ---------------------------------------------------------------------------
# The master mapping
# ---------------------------------------------------------------------------

CLAIM_DISCOVERY_MAP: dict[ClaimType, DiscoverySuggestions] = {
    # ----- FEHA Claims -----
    ClaimType.FEHA_DISCRIMINATION: DiscoverySuggestions(
        disc001_sections=(
            *_DISC001_ALWAYS,
            *_DISC001_INJURIES,
            *_DISC001_INCOME_LOSS,
            *_DISC001_DAMAGES,
            *_DISC001_MEDICAL_HISTORY,
            *_DISC001_INVESTIGATION,
            "14.1",  # Statutory violations
        ),
        disc002_sections=(
            *_DISC002_EMPLOYMENT_REL,
            "200.5", "200.6",
            *_DISC002_ADVERSE_ACTION,
            "202.1", "202.2",  # Discrimination
            "207.1", "207.2",  # Internal complaints
            "208.1", "208.2",  # Government complaints
            "209.1", "209.2",  # Other claims
            *_DISC002_INCOME_EMPLOYEE,
            *_DISC002_INCOME_EMPLOYER,
            *_DISC002_INJURIES,
            *_DISC002_DAMAGES,
            *_DISC002_STANDARD_TAIL,
        ),
        srog_categories=(
            *_SROG_STANDARD,
            "comparator_treatment",
        ),
        rfpd_categories=(
            *_RFPD_STANDARD,
            "performance_reviews",
            "discipline_records",
            "comparator_docs",
            "training_records",
            "job_descriptions",
        ),
        rfa_categories=(
            *_RFA_STANDARD,
            "policy_facts",
        ),
    ),

    ClaimType.FEHA_HARASSMENT: DiscoverySuggestions(
        disc001_sections=(
            *_DISC001_ALWAYS,
            *_DISC001_INJURIES,
            *_DISC001_INCOME_LOSS,
            *_DISC001_DAMAGES,
            *_DISC001_MEDICAL_HISTORY,
            *_DISC001_INVESTIGATION,
        ),
        disc002_sections=(
            *_DISC002_EMPLOYMENT_REL,
            *_DISC002_ADVERSE_ACTION,
            "203.1",           # Harassment
            "207.1", "207.2",  # Internal complaints
            "208.1", "208.2",  # Government complaints
            "209.1", "209.2",
            *_DISC002_INCOME_EMPLOYEE,
            *_DISC002_INJURIES,
            *_DISC002_DAMAGES,
            *_DISC002_STANDARD_TAIL,
        ),
        srog_categories=(
            *_SROG_STANDARD,
            "comparator_treatment",
        ),
        rfpd_categories=(
            *_RFPD_STANDARD,
            "discipline_records",
            "training_records",
            "comparator_docs",
        ),
        rfa_categories=(
            *_RFA_STANDARD,
            "complaint_facts",
            "policy_facts",
        ),
    ),

    ClaimType.FEHA_RETALIATION: DiscoverySuggestions(
        disc001_sections=(
            *_DISC001_ALWAYS,
            *_DISC001_INJURIES,
            *_DISC001_INCOME_LOSS,
            *_DISC001_DAMAGES,
            *_DISC001_MEDICAL_HISTORY,
            *_DISC001_INVESTIGATION,
            "14.1",
        ),
        disc002_sections=(
            *_DISC002_EMPLOYMENT_REL,
            *_DISC002_ADVERSE_ACTION,
            "202.1", "202.2",
            "205.1",           # Public policy
            "207.1", "207.2",  # Internal complaints
            "208.1", "208.2",  # Government complaints
            "209.1", "209.2",
            *_DISC002_INCOME_EMPLOYEE,
            *_DISC002_INCOME_EMPLOYER,
            *_DISC002_INJURIES,
            *_DISC002_DAMAGES,
            *_DISC002_STANDARD_TAIL,
        ),
        srog_categories=(
            *_SROG_STANDARD,
            "comparator_treatment",
        ),
        rfpd_categories=(
            *_RFPD_STANDARD,
            "performance_reviews",
            "discipline_records",
            "comparator_docs",
        ),
        rfa_categories=(
            *_RFA_STANDARD,
            "complaint_facts",
            "policy_facts",
        ),
    ),

    ClaimType.FEHA_FAILURE_TO_PREVENT: DiscoverySuggestions(
        disc001_sections=(
            *_DISC001_ALWAYS,
            *_DISC001_INJURIES,
            *_DISC001_INCOME_LOSS,
            *_DISC001_DAMAGES,
            *_DISC001_INVESTIGATION,
        ),
        disc002_sections=(
            *_DISC002_EMPLOYMENT_REL,
            *_DISC002_ADVERSE_ACTION,
            "202.1", "202.2",
            "203.1",
            "207.1", "207.2",
            "208.1", "208.2",
            "209.1", "209.2",
            *_DISC002_INCOME_EMPLOYEE,
            *_DISC002_INJURIES,
            *_DISC002_DAMAGES,
            *_DISC002_STANDARD_TAIL,
        ),
        srog_categories=(
            *_SROG_STANDARD,
            "comparator_treatment",
        ),
        rfpd_categories=(
            *_RFPD_STANDARD,
            "training_records",
            "discipline_records",
        ),
        rfa_categories=(
            *_RFA_STANDARD,
            "complaint_facts",
            "policy_facts",
        ),
    ),

    ClaimType.FEHA_FAILURE_TO_ACCOMMODATE: DiscoverySuggestions(
        disc001_sections=(
            *_DISC001_ALWAYS,
            *_DISC001_INJURIES,
            *_DISC001_INCOME_LOSS,
            *_DISC001_DAMAGES,
            *_DISC001_MEDICAL_HISTORY,
            *_DISC001_INVESTIGATION,
        ),
        disc002_sections=(
            *_DISC002_EMPLOYMENT_REL,
            *_DISC002_ADVERSE_ACTION,
            "204.1", "204.2", "204.4", "204.5", "204.6", "204.7",  # Disability
            "207.1", "207.2",
            "208.1", "208.2",
            "209.1", "209.2",
            *_DISC002_INCOME_EMPLOYEE,
            *_DISC002_INJURIES,
            *_DISC002_DAMAGES,
            *_DISC002_STANDARD_TAIL,
        ),
        srog_categories=(
            "employment_relationship",
            "adverse_action",
            "decision_makers",
            "investigation",
            "policies",
            "damages",
        ),
        rfpd_categories=(
            *_RFPD_STANDARD,
            "performance_reviews",
            "job_descriptions",
        ),
        rfa_categories=(
            *_RFA_STANDARD,
            "policy_facts",
        ),
    ),

    ClaimType.FEHA_FAILURE_INTERACTIVE_PROCESS: DiscoverySuggestions(
        disc001_sections=(
            *_DISC001_ALWAYS,
            *_DISC001_INJURIES,
            *_DISC001_INCOME_LOSS,
            *_DISC001_DAMAGES,
            *_DISC001_MEDICAL_HISTORY,
            *_DISC001_INVESTIGATION,
        ),
        disc002_sections=(
            *_DISC002_EMPLOYMENT_REL,
            *_DISC002_ADVERSE_ACTION,
            "204.1", "204.2", "204.4", "204.5", "204.6", "204.7",
            "207.1", "207.2",
            "208.1", "208.2",
            "209.1", "209.2",
            *_DISC002_INCOME_EMPLOYEE,
            *_DISC002_INJURIES,
            *_DISC002_DAMAGES,
            *_DISC002_STANDARD_TAIL,
        ),
        srog_categories=(
            "employment_relationship",
            "adverse_action",
            "decision_makers",
            "investigation",
            "policies",
            "damages",
        ),
        rfpd_categories=(
            *_RFPD_STANDARD,
            "performance_reviews",
            "job_descriptions",
        ),
        rfa_categories=(
            *_RFA_STANDARD,
            "policy_facts",
        ),
    ),

    # ----- Wrongful Termination / Contract -----
    ClaimType.WRONGFUL_TERMINATION_PUBLIC_POLICY: DiscoverySuggestions(
        disc001_sections=(
            *_DISC001_ALWAYS,
            *_DISC001_INJURIES,
            *_DISC001_INCOME_LOSS,
            *_DISC001_DAMAGES,
            *_DISC001_MEDICAL_HISTORY,
            *_DISC001_INVESTIGATION,
            "14.1",
        ),
        disc002_sections=(
            *_DISC002_EMPLOYMENT_REL,
            *_DISC002_ADVERSE_ACTION,
            "205.1",           # Discharge / public policy
            "207.1", "207.2",
            "208.1", "208.2",
            "209.1", "209.2",
            *_DISC002_INCOME_EMPLOYEE,
            *_DISC002_INCOME_EMPLOYER,
            *_DISC002_INJURIES,
            *_DISC002_DAMAGES,
            *_DISC002_STANDARD_TAIL,
        ),
        srog_categories=(*_SROG_STANDARD,),
        rfpd_categories=(
            *_RFPD_STANDARD,
            "performance_reviews",
            "discipline_records",
            "termination_docs",
        ),
        rfa_categories=(
            *_RFA_STANDARD,
            "complaint_facts",
        ),
    ),

    ClaimType.BREACH_IMPLIED_CONTRACT: DiscoverySuggestions(
        disc001_sections=(
            *_DISC001_ALWAYS,
            *_DISC001_INCOME_LOSS,
            *_DISC001_DAMAGES,
            *_DISC001_INVESTIGATION,
        ),
        disc002_sections=(
            *_DISC002_EMPLOYMENT_REL,
            "200.5", "200.6",
            *_DISC002_ADVERSE_ACTION,
            "209.1", "209.2",
            *_DISC002_INCOME_EMPLOYEE,
            *_DISC002_INCOME_EMPLOYER,
            *_DISC002_DAMAGES,
            *_DISC002_STANDARD_TAIL,
        ),
        srog_categories=(
            "employment_relationship",
            "adverse_action",
            "decision_makers",
            "policies",
            "damages",
        ),
        rfpd_categories=(
            *_RFPD_STANDARD,
            "performance_reviews",
            "termination_docs",
        ),
        rfa_categories=(
            *_RFA_STANDARD,
            "policy_facts",
        ),
    ),

    ClaimType.BREACH_COVENANT_GOOD_FAITH: DiscoverySuggestions(
        disc001_sections=(
            *_DISC001_ALWAYS,
            *_DISC001_INCOME_LOSS,
            *_DISC001_DAMAGES,
            *_DISC001_INVESTIGATION,
        ),
        disc002_sections=(
            *_DISC002_EMPLOYMENT_REL,
            "200.5", "200.6",
            *_DISC002_ADVERSE_ACTION,
            "209.1", "209.2",
            *_DISC002_INCOME_EMPLOYEE,
            *_DISC002_INCOME_EMPLOYER,
            *_DISC002_DAMAGES,
            *_DISC002_STANDARD_TAIL,
        ),
        srog_categories=(
            "employment_relationship",
            "adverse_action",
            "decision_makers",
            "policies",
            "damages",
        ),
        rfpd_categories=(
            *_RFPD_STANDARD,
            "performance_reviews",
            "termination_docs",
        ),
        rfa_categories=(
            *_RFA_STANDARD,
            "policy_facts",
        ),
    ),

    # ----- Wage & Hour Claims -----
    ClaimType.WAGE_THEFT: DiscoverySuggestions(
        disc001_sections=(
            *_DISC001_ALWAYS,
            *_DISC001_INCOME_LOSS,
            *_DISC001_DAMAGES,
            *_DISC001_INVESTIGATION,
            "14.1",
        ),
        disc002_sections=(
            *_DISC002_EMPLOYMENT_REL,
            "200.5",
            "209.1", "209.2",
            *_DISC002_INCOME_EMPLOYEE,
            *_DISC002_INCOME_EMPLOYER,
            *_DISC002_DAMAGES,
            *_DISC002_STANDARD_TAIL,
        ),
        srog_categories=(
            "employment_relationship",
            "policies",
            "damages",
            "wages_hours",
        ),
        rfpd_categories=(
            "personnel_file",
            "policies_handbooks",
            "communications",
            "compensation_records",
            "timekeeping",
        ),
        rfa_categories=(
            "employment_facts",
            "wage_facts",
            "document_genuineness",
        ),
    ),

    ClaimType.MEAL_REST_BREAK: DiscoverySuggestions(
        disc001_sections=(
            *_DISC001_ALWAYS,
            *_DISC001_INCOME_LOSS,
            *_DISC001_DAMAGES,
            *_DISC001_INVESTIGATION,
            "14.1",
        ),
        disc002_sections=(
            *_DISC002_EMPLOYMENT_REL,
            "200.5",
            "209.1", "209.2",
            *_DISC002_INCOME_EMPLOYEE,
            *_DISC002_DAMAGES,
            *_DISC002_STANDARD_TAIL,
        ),
        srog_categories=(
            "employment_relationship",
            "policies",
            "damages",
            "wages_hours",
        ),
        rfpd_categories=(
            "personnel_file",
            "policies_handbooks",
            "compensation_records",
            "timekeeping",
        ),
        rfa_categories=(
            "employment_facts",
            "wage_facts",
            "policy_facts",
            "document_genuineness",
        ),
    ),

    ClaimType.OVERTIME: DiscoverySuggestions(
        disc001_sections=(
            *_DISC001_ALWAYS,
            *_DISC001_INCOME_LOSS,
            *_DISC001_DAMAGES,
            *_DISC001_INVESTIGATION,
            "14.1",
        ),
        disc002_sections=(
            *_DISC002_EMPLOYMENT_REL,
            "200.5",
            "209.1", "209.2",
            *_DISC002_INCOME_EMPLOYEE,
            *_DISC002_DAMAGES,
            *_DISC002_STANDARD_TAIL,
        ),
        srog_categories=(
            "employment_relationship",
            "policies",
            "damages",
            "wages_hours",
        ),
        rfpd_categories=(
            "personnel_file",
            "policies_handbooks",
            "compensation_records",
            "timekeeping",
            "job_descriptions",
        ),
        rfa_categories=(
            "employment_facts",
            "wage_facts",
            "document_genuineness",
        ),
    ),

    ClaimType.MISCLASSIFICATION: DiscoverySuggestions(
        disc001_sections=(
            *_DISC001_ALWAYS,
            *_DISC001_INCOME_LOSS,
            *_DISC001_DAMAGES,
            *_DISC001_INVESTIGATION,
            "14.1",
        ),
        disc002_sections=(
            *_DISC002_EMPLOYMENT_REL,
            "200.5", "200.6",
            "209.1", "209.2",
            *_DISC002_INCOME_EMPLOYEE,
            *_DISC002_DAMAGES,
            *_DISC002_STANDARD_TAIL,
        ),
        srog_categories=(
            "employment_relationship",
            "policies",
            "damages",
            "wages_hours",
        ),
        rfpd_categories=(
            "personnel_file",
            "policies_handbooks",
            "compensation_records",
            "timekeeping",
            "job_descriptions",
            "organizational",
        ),
        rfa_categories=(
            "employment_facts",
            "wage_facts",
            "document_genuineness",
        ),
    ),

    # ----- Retaliation Claims -----
    ClaimType.WHISTLEBLOWER_RETALIATION: DiscoverySuggestions(
        disc001_sections=(
            *_DISC001_ALWAYS,
            *_DISC001_INJURIES,
            *_DISC001_INCOME_LOSS,
            *_DISC001_DAMAGES,
            *_DISC001_MEDICAL_HISTORY,
            *_DISC001_INVESTIGATION,
            "14.1",
        ),
        disc002_sections=(
            *_DISC002_EMPLOYMENT_REL,
            *_DISC002_ADVERSE_ACTION,
            "205.1",
            "207.1", "207.2",
            "208.1", "208.2",
            "209.1", "209.2",
            *_DISC002_INCOME_EMPLOYEE,
            *_DISC002_INCOME_EMPLOYER,
            *_DISC002_INJURIES,
            *_DISC002_DAMAGES,
            *_DISC002_STANDARD_TAIL,
        ),
        srog_categories=(
            *_SROG_STANDARD,
            "comparator_treatment",
        ),
        rfpd_categories=(
            *_RFPD_STANDARD,
            "performance_reviews",
            "discipline_records",
            "comparator_docs",
            "termination_docs",
        ),
        rfa_categories=(
            *_RFA_STANDARD,
            "complaint_facts",
            "policy_facts",
        ),
    ),

    ClaimType.LABOR_CODE_RETALIATION: DiscoverySuggestions(
        disc001_sections=(
            *_DISC001_ALWAYS,
            *_DISC001_INJURIES,
            *_DISC001_INCOME_LOSS,
            *_DISC001_DAMAGES,
            *_DISC001_INVESTIGATION,
            "14.1",
        ),
        disc002_sections=(
            *_DISC002_EMPLOYMENT_REL,
            *_DISC002_ADVERSE_ACTION,
            "205.1",
            "207.1", "207.2",
            "208.1", "208.2",
            "209.1", "209.2",
            *_DISC002_INCOME_EMPLOYEE,
            *_DISC002_INCOME_EMPLOYER,
            *_DISC002_INJURIES,
            *_DISC002_DAMAGES,
            *_DISC002_STANDARD_TAIL,
        ),
        srog_categories=(
            *_SROG_STANDARD,
            "comparator_treatment",
        ),
        rfpd_categories=(
            *_RFPD_STANDARD,
            "performance_reviews",
            "discipline_records",
            "comparator_docs",
        ),
        rfa_categories=(
            *_RFA_STANDARD,
            "complaint_facts",
        ),
    ),

    # ----- CFRA / FMLA -----
    ClaimType.CFRA_FMLA: DiscoverySuggestions(
        disc001_sections=(
            *_DISC001_ALWAYS,
            *_DISC001_INJURIES,
            *_DISC001_INCOME_LOSS,
            *_DISC001_DAMAGES,
            *_DISC001_MEDICAL_HISTORY,
            *_DISC001_INVESTIGATION,
        ),
        disc002_sections=(
            *_DISC002_EMPLOYMENT_REL,
            *_DISC002_ADVERSE_ACTION,
            "204.1", "204.2", "204.5", "204.6", "204.7",
            "207.1", "207.2",
            "208.1", "208.2",
            "209.1", "209.2",
            *_DISC002_INCOME_EMPLOYEE,
            *_DISC002_INCOME_EMPLOYER,
            *_DISC002_INJURIES,
            *_DISC002_DAMAGES,
            *_DISC002_STANDARD_TAIL,
        ),
        srog_categories=(
            *_SROG_STANDARD,
        ),
        rfpd_categories=(
            *_RFPD_STANDARD,
            "performance_reviews",
        ),
        rfa_categories=(
            *_RFA_STANDARD,
            "policy_facts",
        ),
    ),

    # ----- Tort Claims -----
    ClaimType.DEFAMATION: DiscoverySuggestions(
        disc001_sections=(
            *_DISC001_ALWAYS,
            *_DISC001_INJURIES,
            *_DISC001_INCOME_LOSS,
            *_DISC001_DAMAGES,
            *_DISC001_INVESTIGATION,
        ),
        disc002_sections=(
            *_DISC002_EMPLOYMENT_REL,
            *_DISC002_ADVERSE_ACTION,
            "206.1", "206.2", "206.3",  # Defamation
            "209.1", "209.2",
            *_DISC002_INCOME_EMPLOYEE,
            *_DISC002_INJURIES,
            *_DISC002_DAMAGES,
            *_DISC002_STANDARD_TAIL,
        ),
        srog_categories=(
            "employment_relationship",
            "adverse_action",
            "investigation",
            "damages",
        ),
        rfpd_categories=(
            *_RFPD_STANDARD,
            "performance_reviews",
            "termination_docs",
        ),
        rfa_categories=(
            *_RFA_STANDARD,
        ),
    ),

    ClaimType.IIED: DiscoverySuggestions(
        disc001_sections=(
            *_DISC001_ALWAYS,
            *_DISC001_INJURIES,
            *_DISC001_INCOME_LOSS,
            *_DISC001_DAMAGES,
            *_DISC001_MEDICAL_HISTORY,
            *_DISC001_INVESTIGATION,
        ),
        disc002_sections=(
            *_DISC002_EMPLOYMENT_REL,
            *_DISC002_ADVERSE_ACTION,
            "207.1", "207.2",
            "209.1", "209.2",
            *_DISC002_INCOME_EMPLOYEE,
            *_DISC002_INJURIES,
            *_DISC002_DAMAGES,
            *_DISC002_STANDARD_TAIL,
        ),
        srog_categories=(
            *_SROG_STANDARD,
        ),
        rfpd_categories=(
            *_RFPD_STANDARD,
            "discipline_records",
        ),
        rfa_categories=(
            *_RFA_STANDARD,
            "complaint_facts",
        ),
    ),

    ClaimType.NIED: DiscoverySuggestions(
        disc001_sections=(
            *_DISC001_ALWAYS,
            *_DISC001_INJURIES,
            *_DISC001_INCOME_LOSS,
            *_DISC001_DAMAGES,
            *_DISC001_MEDICAL_HISTORY,
            *_DISC001_INVESTIGATION,
        ),
        disc002_sections=(
            *_DISC002_EMPLOYMENT_REL,
            *_DISC002_ADVERSE_ACTION,
            "207.1", "207.2",
            "209.1", "209.2",
            *_DISC002_INCOME_EMPLOYEE,
            *_DISC002_INJURIES,
            *_DISC002_DAMAGES,
            *_DISC002_STANDARD_TAIL,
        ),
        srog_categories=(
            *_SROG_STANDARD,
        ),
        rfpd_categories=(
            *_RFPD_STANDARD,
        ),
        rfa_categories=(
            *_RFA_STANDARD,
        ),
    ),

    # ----- PAGA / UCL -----
    ClaimType.PAGA: DiscoverySuggestions(
        disc001_sections=(
            *_DISC001_ALWAYS,
            *_DISC001_INCOME_LOSS,
            *_DISC001_DAMAGES,
            *_DISC001_INVESTIGATION,
            "14.1",
        ),
        disc002_sections=(
            *_DISC002_EMPLOYMENT_REL,
            "200.5",
            "208.1", "208.2",
            "209.1", "209.2",
            *_DISC002_INCOME_EMPLOYEE,
            *_DISC002_DAMAGES,
            *_DISC002_STANDARD_TAIL,
        ),
        srog_categories=(
            "employment_relationship",
            "policies",
            "damages",
            "wages_hours",
        ),
        rfpd_categories=(
            "personnel_file",
            "policies_handbooks",
            "compensation_records",
            "timekeeping",
            "organizational",
        ),
        rfa_categories=(
            "employment_facts",
            "wage_facts",
            "policy_facts",
            "document_genuineness",
        ),
    ),

    ClaimType.UNFAIR_BUSINESS_PRACTICES: DiscoverySuggestions(
        disc001_sections=(
            *_DISC001_ALWAYS,
            *_DISC001_INCOME_LOSS,
            *_DISC001_DAMAGES,
            *_DISC001_INVESTIGATION,
            "14.1",
        ),
        disc002_sections=(
            *_DISC002_EMPLOYMENT_REL,
            "200.5",
            "209.1", "209.2",
            *_DISC002_INCOME_EMPLOYEE,
            *_DISC002_DAMAGES,
            *_DISC002_STANDARD_TAIL,
        ),
        srog_categories=(
            "employment_relationship",
            "policies",
            "damages",
            "wages_hours",
        ),
        rfpd_categories=(
            "personnel_file",
            "policies_handbooks",
            "compensation_records",
            "timekeeping",
            "organizational",
        ),
        rfa_categories=(
            "employment_facts",
            "wage_facts",
            "document_genuineness",
        ),
    ),
}


def get_suggestions_for_claims(
    claim_types: list[ClaimType] | tuple[ClaimType, ...],
) -> DiscoverySuggestions:
    """Get merged discovery suggestions for one or more claim types.

    Args:
        claim_types: The claim types to get suggestions for.

    Returns:
        Merged DiscoverySuggestions with all relevant sections/categories.
    """
    suggestions = [
        CLAIM_DISCOVERY_MAP[ct]
        for ct in claim_types
        if ct in CLAIM_DISCOVERY_MAP
    ]
    if not suggestions:
        return DiscoverySuggestions(
            disc001_sections=(),
            disc002_sections=(),
            srog_categories=(),
            rfpd_categories=(),
            rfa_categories=(),
        )
    return merge_suggestions(suggestions)
