"""Case information helpers.

Pure computation — no DB, no ML, no external services.
Derives party names, discovery cutoffs, and response deadlines
from CaseInfo and service-method rules.
"""

from __future__ import annotations

from datetime import date, timedelta

from .models import (
    DISCOVERY_CUTOFF_DAYS_BEFORE_TRIAL,
    MOTION_CUTOFF_DAYS_BEFORE_TRIAL,
    RESPONSE_DEADLINE_DAYS,
    SERVICE_METHOD_EXTENSIONS,
    CaseInfo,
    PartyRole,
    ServiceMethod,
)


def propounding_party_name(case_info: CaseInfo) -> str:
    """Return the display name of the propounding (asking) party."""
    if case_info.party_role == PartyRole.PLAINTIFF:
        return case_info.plaintiffs[0].name if case_info.plaintiffs else "Plaintiff"
    return case_info.defendants[0].name if case_info.defendants else "Defendant"


def responding_party_name(case_info: CaseInfo) -> str:
    """Return the display name of the responding (answering) party."""
    if case_info.party_role == PartyRole.PLAINTIFF:
        return case_info.defendants[0].name if case_info.defendants else "Defendant"
    return case_info.plaintiffs[0].name if case_info.plaintiffs else "Plaintiff"


def propounding_party_designation(case_info: CaseInfo) -> str:
    """Return e.g. 'Plaintiff' or 'Defendant'."""
    return "Plaintiff" if case_info.party_role == PartyRole.PLAINTIFF else "Defendant"


def responding_party_designation(case_info: CaseInfo) -> str:
    """Return e.g. 'Plaintiff' or 'Defendant' for the opposing side."""
    return "Defendant" if case_info.party_role == PartyRole.PLAINTIFF else "Plaintiff"


def plaintiff_block(case_info: CaseInfo) -> str:
    """Format plaintiff(s) for the case caption."""
    names = [p.name for p in case_info.plaintiffs]
    block = ",\n".join(names)
    if case_info.does_included:
        block += ";\nDoes 1 through 50, inclusive"
    return block


def defendant_block(case_info: CaseInfo) -> str:
    """Format defendant(s) for the case caption."""
    return ",\n".join(d.name for d in case_info.defendants)


def discovery_cutoff_date(case_info: CaseInfo) -> date | None:
    """Calculate the last day to complete discovery (CCP 2024.020).

    Returns None if no trial date is set.
    """
    if case_info.trial_date is None:
        return None
    return case_info.trial_date - timedelta(days=DISCOVERY_CUTOFF_DAYS_BEFORE_TRIAL)


def motion_cutoff_date(case_info: CaseInfo) -> date | None:
    """Calculate the last day to hear discovery motions (CCP 2024.020).

    Returns None if no trial date is set.
    """
    if case_info.trial_date is None:
        return None
    return case_info.trial_date - timedelta(days=MOTION_CUTOFF_DAYS_BEFORE_TRIAL)


def response_deadline(
    service_date: date,
    method: ServiceMethod = ServiceMethod.MAIL_IN_STATE,
) -> date:
    """Calculate when responses are due given service date and method.

    CCP 2030.260: 30 days base + service-method extension.
    Note: electronic/overnight extensions are in *court days* (excluding
    weekends and court holidays). This calculation uses calendar days as
    an approximation. For exact court-day calculations, consult a
    court-day calendar.
    """
    extension = SERVICE_METHOD_EXTENSIONS[method]
    return service_date + timedelta(days=RESPONSE_DEADLINE_DAYS + extension)


def days_until_discovery_cutoff(
    case_info: CaseInfo,
    as_of: date | None = None,
) -> int | None:
    """Return days remaining until discovery cutoff, or None if no trial date."""
    cutoff = discovery_cutoff_date(case_info)
    if cutoff is None:
        return None
    ref = as_of or date.today()
    return (cutoff - ref).days


def set_number_label(n: int) -> str:
    """Convert set number to word form for pleading paper (1 → 'One')."""
    words = {
        1: "One",
        2: "Two",
        3: "Three",
        4: "Four",
        5: "Five",
        6: "Six",
        7: "Seven",
        8: "Eight",
        9: "Nine",
        10: "Ten",
    }
    return words.get(n, str(n))


def document_title(
    case_info: CaseInfo,
    tool_label: str,
) -> str:
    """Build the document title line for pleading paper.

    Example: "PLAINTIFF JANE SMITH'S SPECIAL INTERROGATORIES TO
              DEFENDANT ACME CORP, Set One"
    """
    prop_desig = propounding_party_designation(case_info).upper()
    prop_name = propounding_party_name(case_info).upper()
    resp_desig = responding_party_designation(case_info).upper()
    resp_name = responding_party_name(case_info).upper()
    set_label = set_number_label(case_info.set_number)
    return (
        f"{prop_desig} {prop_name}'S {tool_label} TO "
        f"{resp_desig} {resp_name}, Set {set_label}"
    )
