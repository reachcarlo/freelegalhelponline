"""Tests for discovery request limit tracking.

CCP 2030.030: 35 specially prepared interrogatories without declaration.
CCP 2033.030: 35 fact-based RFAs without declaration.
Genuineness-of-document RFAs (CCP 2033.060) are unlimited.
RFPDs have no numeric limit.

Covers:
- SROG 35-item limit tracking
- RFA fact vs genuineness counting
- RFA 35-fact limit tracking
- Declaration of Necessity detection
- Edge cases (exactly at limit, custom requests, deselected items)
"""

from __future__ import annotations

import pytest

from employee_help.discovery.models import (
    DiscoveryRequest,
    SROG_LIMIT,
    RFA_FACT_LIMIT,
)
from employee_help.discovery.srogs import (
    SROG_BANK,
    count_selected,
    exceeds_limit as srog_exceeds_limit,
    needs_declaration as srog_needs_declaration,
)
from employee_help.discovery.rfas import (
    RFA_BANK,
    RFARequest,
    count_fact_rfas,
    count_genuineness_rfas,
    exceeds_fact_limit,
    needs_declaration as rfa_needs_declaration,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_srog(id: str, selected: bool = True) -> DiscoveryRequest:
    return DiscoveryRequest(
        id=id,
        text=f"Test SROG {id}",
        category="test",
        is_selected=selected,
        order=0,
    )


def _make_rfa(
    id: str,
    rfa_type: str = "fact",
    selected: bool = True,
) -> RFARequest:
    return RFARequest(
        id=id,
        text=f"Test RFA {id}",
        category="test",
        rfa_type=rfa_type,
        is_selected=selected,
        order=0,
    )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestLimitConstants:
    def test_srog_limit_is_35(self):
        assert SROG_LIMIT == 35

    def test_rfa_fact_limit_is_35(self):
        assert RFA_FACT_LIMIT == 35


# ---------------------------------------------------------------------------
# SROG limit tracking
# ---------------------------------------------------------------------------


class TestSrogLimits:
    def test_count_all_selected(self):
        requests = [_make_srog(f"s{i}") for i in range(10)]
        assert count_selected(requests) == 10

    def test_count_none_selected(self):
        requests = [_make_srog(f"s{i}", selected=False) for i in range(10)]
        assert count_selected(requests) == 0

    def test_count_mixed_selection(self):
        requests = [
            _make_srog("s1", selected=True),
            _make_srog("s2", selected=False),
            _make_srog("s3", selected=True),
            _make_srog("s4", selected=False),
            _make_srog("s5", selected=True),
        ]
        assert count_selected(requests) == 3

    def test_bank_exactly_at_limit(self):
        """The default bank has exactly 35 items, all selected."""
        assert count_selected(SROG_BANK) == 35
        assert not srog_exceeds_limit(SROG_BANK)

    def test_exceeds_at_36(self):
        requests = [_make_srog(f"s{i}") for i in range(36)]
        assert srog_exceeds_limit(requests)

    def test_not_exceeds_at_35(self):
        requests = [_make_srog(f"s{i}") for i in range(35)]
        assert not srog_exceeds_limit(requests)

    def test_not_exceeds_at_34(self):
        requests = [_make_srog(f"s{i}") for i in range(34)]
        assert not srog_exceeds_limit(requests)

    def test_needs_declaration_matches_exceeds(self):
        under = [_make_srog(f"s{i}") for i in range(35)]
        over = [_make_srog(f"s{i}") for i in range(36)]
        assert not srog_needs_declaration(under)
        assert srog_needs_declaration(over)

    def test_empty_list(self):
        assert count_selected([]) == 0
        assert not srog_exceeds_limit([])

    def test_deselected_dont_count(self):
        """Adding deselected items should not trigger the limit."""
        requests = [_make_srog(f"s{i}") for i in range(35)]
        # Add 10 deselected
        for i in range(10):
            requests.append(_make_srog(f"extra{i}", selected=False))
        assert count_selected(requests) == 35
        assert not srog_exceeds_limit(requests)

    def test_custom_requests_count_toward_limit(self):
        """Custom (user-added) requests count the same as bank requests."""
        requests = [_make_srog(f"s{i}") for i in range(34)]
        custom = DiscoveryRequest(
            id="custom_1",
            text="Custom interrogatory",
            category="test",
            is_selected=True,
            is_custom=True,
            order=35,
        )
        requests.append(custom)
        assert count_selected(requests) == 35
        assert not srog_exceeds_limit(requests)

        # Add one more custom → exceeds
        custom2 = DiscoveryRequest(
            id="custom_2",
            text="Another custom interrogatory",
            category="test",
            is_selected=True,
            is_custom=True,
            order=36,
        )
        requests.append(custom2)
        assert count_selected(requests) == 36
        assert srog_exceeds_limit(requests)


# ---------------------------------------------------------------------------
# RFA limit tracking (fact vs genuineness)
# ---------------------------------------------------------------------------


class TestRfaLimits:
    def test_count_fact_rfas_all_facts(self):
        requests = [_make_rfa(f"r{i}", rfa_type="fact") for i in range(10)]
        assert count_fact_rfas(requests) == 10

    def test_count_genuineness_rfas(self):
        requests = [_make_rfa(f"r{i}", rfa_type="genuineness") for i in range(5)]
        assert count_genuineness_rfas(requests) == 5
        assert count_fact_rfas(requests) == 0

    def test_mixed_fact_and_genuineness(self):
        requests = [
            _make_rfa("f1", rfa_type="fact"),
            _make_rfa("f2", rfa_type="fact"),
            _make_rfa("g1", rfa_type="genuineness"),
            _make_rfa("f3", rfa_type="fact"),
            _make_rfa("g2", rfa_type="genuineness"),
        ]
        assert count_fact_rfas(requests) == 3
        assert count_genuineness_rfas(requests) == 2

    def test_genuineness_dont_count_toward_limit(self):
        """Even with 100 genuineness RFAs, the limit should not be exceeded."""
        fact_requests = [_make_rfa(f"f{i}", rfa_type="fact") for i in range(35)]
        gen_requests = [_make_rfa(f"g{i}", rfa_type="genuineness") for i in range(100)]
        all_requests = fact_requests + gen_requests
        assert count_fact_rfas(all_requests) == 35
        assert not exceeds_fact_limit(all_requests)

    def test_exceeds_at_36_facts(self):
        requests = [_make_rfa(f"f{i}", rfa_type="fact") for i in range(36)]
        assert exceeds_fact_limit(requests)

    def test_not_exceeds_at_35_facts(self):
        requests = [_make_rfa(f"f{i}", rfa_type="fact") for i in range(35)]
        assert not exceeds_fact_limit(requests)

    def test_deselected_facts_dont_count(self):
        requests = [_make_rfa(f"f{i}", rfa_type="fact") for i in range(35)]
        # Add deselected facts
        for i in range(10):
            requests.append(_make_rfa(f"extra{i}", rfa_type="fact", selected=False))
        assert count_fact_rfas(requests) == 35
        assert not exceeds_fact_limit(requests)

    def test_deselected_genuineness_dont_count(self):
        requests = [_make_rfa(f"g{i}", rfa_type="genuineness", selected=False) for i in range(5)]
        assert count_genuineness_rfas(requests) == 0

    def test_needs_declaration_matches_exceeds(self):
        under = [_make_rfa(f"f{i}", rfa_type="fact") for i in range(35)]
        over = [_make_rfa(f"f{i}", rfa_type="fact") for i in range(36)]
        assert not rfa_needs_declaration(under)
        assert rfa_needs_declaration(over)

    def test_empty_list(self):
        assert count_fact_rfas([]) == 0
        assert count_genuineness_rfas([]) == 0
        assert not exceeds_fact_limit([])

    def test_bank_default_counts(self):
        """Default bank should have 21 fact + 5 genuineness, well under limit."""
        assert count_fact_rfas(RFA_BANK) == 21
        assert count_genuineness_rfas(RFA_BANK) == 5
        assert not exceeds_fact_limit(RFA_BANK)

    def test_bank_genuineness_unlimited_scenario(self):
        """Adding many genuineness RFAs to the bank should never trigger limit."""
        extended = list(RFA_BANK)
        for i in range(50):
            extended.append(_make_rfa(f"extra_gen_{i}", rfa_type="genuineness"))
        assert count_fact_rfas(extended) == 21
        assert count_genuineness_rfas(extended) == 55  # 5 original + 50 extra
        assert not exceeds_fact_limit(extended)

    def test_custom_fact_rfas_count_toward_limit(self):
        """Custom fact-based RFAs count toward the 35 limit."""
        requests = [_make_rfa(f"f{i}", rfa_type="fact") for i in range(34)]
        custom = RFARequest(
            id="custom_1",
            text="Custom admission request",
            category="test",
            rfa_type="fact",
            is_selected=True,
            is_custom=True,
            order=35,
        )
        requests.append(custom)
        assert count_fact_rfas(requests) == 35
        assert not exceeds_fact_limit(requests)

        custom2 = RFARequest(
            id="custom_2",
            text="Another custom",
            category="test",
            rfa_type="fact",
            is_selected=True,
            is_custom=True,
            order=36,
        )
        requests.append(custom2)
        assert count_fact_rfas(requests) == 36
        assert exceeds_fact_limit(requests)
