"""Variable substitution for discovery request templates.

Resolves {PLACEHOLDER} variables in request text using case context.
Pure functions — no side effects, no imports outside discovery package.
"""

from __future__ import annotations

from dataclasses import replace

from .models import CaseInfo, DiscoveryRequest, PartyRole


# Known template variables
VARIABLE_NAMES = frozenset({
    "PROPOUNDING_PARTY",
    "RESPONDING_PARTY",
    "PROPOUNDING_DESIGNATION",
    "RESPONDING_DESIGNATION",
    "EMPLOYEE",
    "EMPLOYER",
})


class _PassthroughDict(dict):
    """Dict that returns unknown keys wrapped in braces."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def build_variable_map(case_info: CaseInfo) -> dict[str, str]:
    """Build the variable substitution map from case context.

    Maps each template variable to its resolved value based on
    party_role and party names.
    """
    plaintiff_name = (
        case_info.plaintiffs[0].name if case_info.plaintiffs else ""
    )
    defendant_name = (
        case_info.defendants[0].name if case_info.defendants else ""
    )

    if case_info.party_role == PartyRole.PLAINTIFF:
        return {
            "PROPOUNDING_PARTY": plaintiff_name,
            "RESPONDING_PARTY": defendant_name,
            "PROPOUNDING_DESIGNATION": "Plaintiff",
            "RESPONDING_DESIGNATION": "Defendant",
            "EMPLOYEE": plaintiff_name,
            "EMPLOYER": defendant_name,
        }
    else:
        return {
            "PROPOUNDING_PARTY": defendant_name,
            "RESPONDING_PARTY": plaintiff_name,
            "PROPOUNDING_DESIGNATION": "Defendant",
            "RESPONDING_DESIGNATION": "Plaintiff",
            "EMPLOYEE": plaintiff_name,
            "EMPLOYER": defendant_name,
        }


def resolve_text(template: str, variables: dict[str, str]) -> str:
    """Replace {PLACEHOLDER} variables in template text.

    Unknown variables pass through unchanged as {UNKNOWN}.
    """
    return template.format_map(_PassthroughDict(variables))


def resolve_request(
    request: DiscoveryRequest,
    case_info: CaseInfo,
) -> DiscoveryRequest:
    """Return a new DiscoveryRequest with resolved text."""
    variables = build_variable_map(case_info)
    resolved = resolve_text(request.text, variables)
    return replace(request, text=resolved)
