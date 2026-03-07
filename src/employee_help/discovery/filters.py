"""Role and claim filtering for discovery request banks.

Pure functions that filter DiscoveryRequest lists by party role
and claim types. No side effects.
"""

from __future__ import annotations

from .models import ClaimType, DiscoveryRequest, PartyRole


def filter_by_role(
    requests: list[DiscoveryRequest],
    party_role: PartyRole,
) -> list[DiscoveryRequest]:
    """Return only requests applicable to the given party role."""
    role_value = party_role.value
    return [r for r in requests if role_value in r.applicable_roles]


def filter_by_claims(
    requests: list[DiscoveryRequest],
    claim_types: tuple[ClaimType, ...],
) -> list[DiscoveryRequest]:
    """Return requests applicable to any of the given claim types.

    Requests with empty applicable_claims pass through (universal).
    """
    claim_values = {ct.value for ct in claim_types}
    return [
        r for r in requests
        if not r.applicable_claims
        or bool(set(r.applicable_claims) & claim_values)
    ]
