"""DISC-001 Form Interrogatories (General) — section registry and suggestion logic.

Provides section metadata (titles, subsection counts, employment relevance)
and a suggestion function that pre-selects sections based on claim types
and party role.

Pure data — no DB, no ML, no external services.
"""

from __future__ import annotations

from dataclasses import dataclass

from .claim_mapping import get_suggestions_for_claims
from .models import ClaimType, PartyRole


@dataclass(frozen=True)
class Disc001Section:
    """Metadata for a DISC-001 section group."""

    number: str          # Section group number (e.g. "1", "2", "6")
    title: str
    subsections: tuple[str, ...]  # Individual interrogatory numbers
    employment_relevance: str     # "always", "common", "conditional", "rare"
    description: str


# ---------------------------------------------------------------------------
# Section registry
# ---------------------------------------------------------------------------

DISC001_SECTIONS: dict[str, Disc001Section] = {
    "1": Disc001Section(
        number="1",
        title="Identity of Persons Answering",
        subsections=("1.1",),
        employment_relevance="always",
        description="Identifies who prepared the responses.",
    ),
    "2": Disc001Section(
        number="2",
        title="General Background — Individual",
        subsections=(
            "2.1", "2.2", "2.3", "2.4", "2.5",
            "2.6", "2.7", "2.8", "2.9", "2.10",
            "2.11", "2.12", "2.13",
        ),
        employment_relevance="always",
        description="Background information about the individual party.",
    ),
    "3": Disc001Section(
        number="3",
        title="General Background — Business Entity",
        subsections=("3.1", "3.2", "3.3", "3.4", "3.5", "3.6", "3.7"),
        employment_relevance="always",
        description="Background information about entity parties.",
    ),
    "4": Disc001Section(
        number="4",
        title="Insurance",
        subsections=("4.1", "4.2"),
        employment_relevance="always",
        description="Insurance coverage for claims and damages.",
    ),
    "6": Disc001Section(
        number="6",
        title="Physical, Mental, or Emotional Injuries",
        subsections=("6.1", "6.2", "6.3", "6.4", "6.5", "6.6", "6.7"),
        employment_relevance="common",
        description="Injuries attributed to the incident, medical treatment, medications.",
    ),
    "7": Disc001Section(
        number="7",
        title="Property Damage",
        subsections=("7.1", "7.2", "7.3"),
        employment_relevance="rare",
        description="Loss of or damage to property. Rarely relevant in employment cases.",
    ),
    "8": Disc001Section(
        number="8",
        title="Loss of Income or Earning Capacity",
        subsections=("8.1", "8.2", "8.3", "8.4", "8.5", "8.6", "8.7", "8.8"),
        employment_relevance="always",
        description="Income loss, employment history, and earning capacity.",
    ),
    "9": Disc001Section(
        number="9",
        title="Other Damages",
        subsections=("9.1", "9.2"),
        employment_relevance="common",
        description="Any damages not covered by other sections.",
    ),
    "10": Disc001Section(
        number="10",
        title="Medical History",
        subsections=("10.1", "10.2", "10.3"),
        employment_relevance="conditional",
        description="Prior medical conditions. Relevant when emotional distress is claimed.",
    ),
    "11": Disc001Section(
        number="11",
        title="Other Claims and Previous Claims",
        subsections=("11.1", "11.2"),
        employment_relevance="always",
        description="Prior personal injury actions and workers' comp claims (10-year lookback).",
    ),
    "12": Disc001Section(
        number="12",
        title="Investigation — General",
        subsections=("12.1", "12.2", "12.3", "12.4", "12.5", "12.6", "12.7"),
        employment_relevance="always",
        description="Witnesses, statements, photographs, reports, inspections.",
    ),
    "13": Disc001Section(
        number="13",
        title="Investigation — Surveillance",
        subsections=("13.1", "13.2"),
        employment_relevance="common",
        description="Surveillance conducted on any individual or party.",
    ),
    "14": Disc001Section(
        number="14",
        title="Statutory or Regulatory Violations",
        subsections=("14.1", "14.2"),
        employment_relevance="common",
        description="Violations of statutes, ordinances, or regulations.",
    ),
    "15": Disc001Section(
        number="15",
        title="Denials and Special/Affirmative Defenses",
        subsections=("15.1",),
        employment_relevance="always",
        description="Each denial and affirmative defense in pleadings.",
    ),
    "16": Disc001Section(
        number="16",
        title="Defendant's Contentions — Personal Injury",
        subsections=(
            "16.1", "16.2", "16.3", "16.4", "16.5",
            "16.6", "16.7", "16.8", "16.9", "16.10",
        ),
        employment_relevance="conditional",
        description="Defendant's contentions about plaintiff's injuries and damages. "
                    "Typically propounded by plaintiff to defendant.",
    ),
    "17": Disc001Section(
        number="17",
        title="Response to Request for Admissions",
        subsections=("17.1",),
        employment_relevance="conditional",
        description="Served alongside RFAs to require explanation of non-admissions.",
    ),
    "20": Disc001Section(
        number="20",
        title="How the Incident Occurred — Motor Vehicle",
        subsections=(
            "20.1", "20.2", "20.3", "20.4", "20.5",
            "20.6", "20.7", "20.8", "20.9", "20.10", "20.11",
        ),
        employment_relevance="rare",
        description="Motor vehicle incident details. Not relevant in most employment cases.",
    ),
    "50": Disc001Section(
        number="50",
        title="Contract",
        subsections=("50.1", "50.2", "50.3", "50.4", "50.5", "50.6"),
        employment_relevance="conditional",
        description="Contract formation, breach, performance, and enforceability. "
                    "Relevant for breach of contract / implied contract claims.",
    ),
}


# ---------------------------------------------------------------------------
# Sections appropriate for each party role (when propounding)
# ---------------------------------------------------------------------------

# Sections that only make sense when propounded by plaintiff to defendant
_PLAINTIFF_PROPOUNDING_SECTIONS = {
    "16.1", "16.2", "16.3", "16.4", "16.5",
    "16.6", "16.7", "16.8", "16.9", "16.10",
}

# Sections that only make sense when propounded by defendant to plaintiff
_DEFENDANT_PROPOUNDING_SECTIONS: set[str] = set()
# (Most DISC-001 sections are bidirectional; defendant has no exclusive ones)


def suggest_disc001_sections(
    claim_types: list[ClaimType] | tuple[ClaimType, ...],
    party_role: PartyRole,
    *,
    has_rfas: bool = False,
    responding_is_entity: bool = False,
) -> list[str]:
    """Return suggested DISC-001 section numbers to pre-check.

    Args:
        claim_types: Claim types in the case.
        party_role: Who is propounding (plaintiff or defendant).
        has_rfas: Whether RFAs are also being propounded (adds 17.1).
        responding_is_entity: Whether responding party is a business entity.

    Returns:
        Sorted list of section numbers (e.g. ["1.1", "2.1", "4.1", ...]).
    """
    merged = get_suggestions_for_claims(claim_types)
    sections = set(merged.disc001_sections)

    # Always include identity and defenses
    sections.add("1.1")
    sections.add("15.1")

    # Party-role filtering
    if party_role == PartyRole.PLAINTIFF:
        # Plaintiff propounds to defendant — include section 16 contentions
        # (already in mapping if relevant), remove defendant-only
        sections -= _DEFENDANT_PROPOUNDING_SECTIONS
    else:
        # Defendant propounds to plaintiff — remove plaintiff-only sections
        sections -= _PLAINTIFF_PROPOUNDING_SECTIONS

    # Entity-specific sections
    if responding_is_entity:
        # Add entity background (section 3) if the responding party is a business
        for sub in DISC001_SECTIONS["3"].subsections:
            sections.add(sub)
    else:
        # Individual: ensure section 2 is present
        sections.add("2.1")

    # Conditional additions
    if has_rfas:
        sections.add("17.1")

    # Remove motor vehicle (section 20) unless explicitly in mapping
    # (no employment claim should map to motor vehicle)
    for sub in DISC001_SECTIONS["20"].subsections:
        sections.discard(sub)

    return sorted(sections)


def get_all_employment_sections() -> list[str]:
    """Return all DISC-001 sections commonly used in employment cases.

    Excludes motor vehicle (20) and property damage (7).
    """
    sections = []
    for group in DISC001_SECTIONS.values():
        if group.employment_relevance in ("always", "common", "conditional"):
            sections.extend(group.subsections)
    return sorted(sections)
