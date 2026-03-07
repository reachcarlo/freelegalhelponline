"""Tests for discovery role and claim filtering (Phase D.1.3).

Covers:
- filter_by_role for plaintiff, defendant, and shared requests
- filter_by_claims for gated and universal requests
- Edge cases: empty inputs, multiple claims, mixed lists
"""

from __future__ import annotations

import pytest

from employee_help.discovery.filters import filter_by_claims, filter_by_role
from employee_help.discovery.models import ClaimType, DiscoveryRequest, PartyRole


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _req(
    id: str,
    roles: tuple[str, ...] = ("plaintiff", "defendant"),
    claims: tuple[str, ...] = (),
) -> DiscoveryRequest:
    return DiscoveryRequest(
        id=id,
        text=f"Text for {id}",
        category="test",
        applicable_roles=roles,
        applicable_claims=claims,
    )


# ---------------------------------------------------------------------------
# filter_by_role
# ---------------------------------------------------------------------------


class TestFilterByRole:
    def test_shared_passes_both(self):
        req = _req("shared")
        assert filter_by_role([req], PartyRole.PLAINTIFF) == [req]
        assert filter_by_role([req], PartyRole.DEFENDANT) == [req]

    def test_plaintiff_only(self):
        req = _req("p_only", roles=("plaintiff",))
        assert filter_by_role([req], PartyRole.PLAINTIFF) == [req]
        assert filter_by_role([req], PartyRole.DEFENDANT) == []

    def test_defendant_only(self):
        req = _req("d_only", roles=("defendant",))
        assert filter_by_role([req], PartyRole.PLAINTIFF) == []
        assert filter_by_role([req], PartyRole.DEFENDANT) == [req]

    def test_mixed_list(self):
        reqs = [
            _req("shared"),
            _req("p_only", roles=("plaintiff",)),
            _req("d_only", roles=("defendant",)),
        ]
        plaintiff_result = filter_by_role(reqs, PartyRole.PLAINTIFF)
        assert [r.id for r in plaintiff_result] == ["shared", "p_only"]

        defendant_result = filter_by_role(reqs, PartyRole.DEFENDANT)
        assert [r.id for r in defendant_result] == ["shared", "d_only"]

    def test_empty_input(self):
        assert filter_by_role([], PartyRole.PLAINTIFF) == []

    def test_preserves_order(self):
        reqs = [_req(f"r{i}") for i in range(5)]
        result = filter_by_role(reqs, PartyRole.PLAINTIFF)
        assert [r.id for r in result] == [f"r{i}" for i in range(5)]


# ---------------------------------------------------------------------------
# filter_by_claims
# ---------------------------------------------------------------------------


class TestFilterByClaims:
    def test_universal_always_passes(self):
        req = _req("universal", claims=())
        result = filter_by_claims(
            [req], (ClaimType.FEHA_DISCRIMINATION,)
        )
        assert result == [req]

    def test_matching_claim(self):
        req = _req("feha", claims=("feha_discrimination",))
        result = filter_by_claims(
            [req], (ClaimType.FEHA_DISCRIMINATION,)
        )
        assert result == [req]

    def test_non_matching_claim(self):
        req = _req("feha", claims=("feha_discrimination",))
        result = filter_by_claims([req], (ClaimType.WAGE_THEFT,))
        assert result == []

    def test_any_claim_match(self):
        """Request passes if ANY of its claims matches ANY of the filter."""
        req = _req("multi", claims=("wage_theft", "overtime"))
        result = filter_by_claims(
            [req], (ClaimType.OVERTIME, ClaimType.DEFAMATION)
        )
        assert result == [req]

    def test_multiple_claims_no_overlap(self):
        req = _req("gated", claims=("feha_discrimination",))
        result = filter_by_claims(
            [req], (ClaimType.WAGE_THEFT, ClaimType.OVERTIME)
        )
        assert result == []

    def test_mixed_universal_and_gated(self):
        reqs = [
            _req("universal", claims=()),
            _req("gated_match", claims=("wage_theft",)),
            _req("gated_miss", claims=("feha_discrimination",)),
        ]
        result = filter_by_claims(reqs, (ClaimType.WAGE_THEFT,))
        assert [r.id for r in result] == ["universal", "gated_match"]

    def test_empty_requests(self):
        assert filter_by_claims([], (ClaimType.WAGE_THEFT,)) == []

    def test_empty_claim_types_filter(self):
        """With no claims to filter by, only universal requests pass."""
        reqs = [
            _req("universal", claims=()),
            _req("gated", claims=("wage_theft",)),
        ]
        result = filter_by_claims(reqs, ())
        assert [r.id for r in result] == ["universal"]

    def test_feha_accommodation_gate(self):
        req = _req(
            "accommodation",
            claims=(
                "feha_failure_to_accommodate",
                "feha_failure_interactive_process",
            ),
        )
        assert filter_by_claims(
            [req], (ClaimType.FEHA_FAILURE_TO_ACCOMMODATE,)
        ) == [req]
        assert filter_by_claims(
            [req], (ClaimType.FEHA_FAILURE_INTERACTIVE_PROCESS,)
        ) == [req]
        assert filter_by_claims(
            [req], (ClaimType.FEHA_DISCRIMINATION,)
        ) == []


# ---------------------------------------------------------------------------
# Combined filter_by_role + filter_by_claims
# ---------------------------------------------------------------------------


class TestCombinedFilters:
    def test_plaintiff_with_matching_claim(self):
        reqs = [
            _req("shared_universal"),
            _req("plaintiff_gated", roles=("plaintiff",), claims=("wage_theft",)),
            _req("defendant_universal", roles=("defendant",)),
        ]
        result = filter_by_role(reqs, PartyRole.PLAINTIFF)
        result = filter_by_claims(result, (ClaimType.WAGE_THEFT,))
        assert [r.id for r in result] == ["shared_universal", "plaintiff_gated"]

    def test_defendant_with_no_matching_claim(self):
        reqs = [
            _req("shared_universal"),
            _req("plaintiff_gated", roles=("plaintiff",), claims=("wage_theft",)),
            _req("defendant_gated", roles=("defendant",), claims=("feha_discrimination",)),
        ]
        result = filter_by_role(reqs, PartyRole.DEFENDANT)
        result = filter_by_claims(result, (ClaimType.WAGE_THEFT,))
        assert [r.id for r in result] == ["shared_universal"]
