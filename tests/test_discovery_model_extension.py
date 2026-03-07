"""Tests for DiscoveryRequest model extension (Phase D.1.1).

Covers:
- New field defaults on DiscoveryRequest
- New field defaults on RFARequest (inheritance)
- Frozen dataclass immutability preserved
- Existing bank items get default values
"""

from __future__ import annotations

import pytest

from employee_help.discovery.models import DiscoveryRequest
from employee_help.discovery.rfas import RFA_BANK, RFARequest
from employee_help.discovery.srogs import SROG_BANK
from employee_help.discovery.rfpds import RFPD_BANK


class TestDiscoveryRequestDefaults:
    def test_applicable_roles_default(self):
        req = DiscoveryRequest(id="x", text="t", category="c")
        assert req.applicable_roles == ("plaintiff", "defendant")

    def test_applicable_claims_default(self):
        req = DiscoveryRequest(id="x", text="t", category="c")
        assert req.applicable_claims == ()

    def test_explicit_roles(self):
        req = DiscoveryRequest(
            id="x", text="t", category="c",
            applicable_roles=("plaintiff",),
        )
        assert req.applicable_roles == ("plaintiff",)

    def test_explicit_claims(self):
        req = DiscoveryRequest(
            id="x", text="t", category="c",
            applicable_claims=("wage_theft", "overtime"),
        )
        assert req.applicable_claims == ("wage_theft", "overtime")

    def test_frozen_immutability(self):
        req = DiscoveryRequest(id="x", text="t", category="c")
        with pytest.raises(AttributeError):
            req.applicable_roles = ("plaintiff",)  # type: ignore[misc]
        with pytest.raises(AttributeError):
            req.applicable_claims = ("wage_theft",)  # type: ignore[misc]


class TestRFARequestInheritance:
    def test_inherits_applicable_roles(self):
        rfa = RFARequest(id="x", text="t", category="c")
        assert rfa.applicable_roles == ("plaintiff", "defendant")

    def test_inherits_applicable_claims(self):
        rfa = RFARequest(id="x", text="t", category="c")
        assert rfa.applicable_claims == ()

    def test_explicit_roles_on_rfa(self):
        rfa = RFARequest(
            id="x", text="t", category="c",
            applicable_roles=("defendant",),
        )
        assert rfa.applicable_roles == ("defendant",)

    def test_rfa_type_still_works(self):
        rfa = RFARequest(
            id="x", text="t", category="c",
            rfa_type="genuineness",
            applicable_roles=("plaintiff",),
        )
        assert rfa.rfa_type == "genuineness"
        assert rfa.applicable_roles == ("plaintiff",)

    def test_frozen_immutability(self):
        rfa = RFARequest(id="x", text="t", category="c")
        with pytest.raises(AttributeError):
            rfa.applicable_roles = ("plaintiff",)  # type: ignore[misc]


class TestExistingBankDefaults:
    def test_all_srogs_have_default_roles(self):
        for req in SROG_BANK:
            assert req.applicable_roles == ("plaintiff", "defendant"), (
                f"{req.id} missing default applicable_roles"
            )

    def test_all_srogs_have_default_claims(self):
        for req in SROG_BANK:
            assert req.applicable_claims == (), (
                f"{req.id} missing default applicable_claims"
            )

    def test_all_rfpds_have_default_roles(self):
        for req in RFPD_BANK:
            assert req.applicable_roles == ("plaintiff", "defendant")

    def test_all_rfas_have_default_roles(self):
        for req in RFA_BANK:
            assert req.applicable_roles == ("plaintiff", "defendant")

    def test_all_rfas_have_default_claims(self):
        for req in RFA_BANK:
            assert req.applicable_claims == ()

    def test_bank_counts_unchanged(self):
        assert len(SROG_BANK) == 35
        assert len(RFPD_BANK) == 28
        assert len(RFA_BANK) == 26
