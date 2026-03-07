"""Bank integrity tests for discovery request banks (Phase D.2.5).

Verifies structural integrity across all three banks:
- No duplicate IDs
- Valid category references
- Every category has at least one request
- Role annotations present and valid
- Claim annotations reference valid ClaimType values
- Template variables are from the known registry
- Request counts match expected totals
"""

from __future__ import annotations

import re

import pytest

from employee_help.discovery.models import ClaimType, DiscoveryRequest
from employee_help.discovery.resolver import VARIABLE_NAMES
from employee_help.discovery.srogs import SROG_BANK, SROG_CATEGORIES
from employee_help.discovery.rfpds import RFPD_BANK, RFPD_CATEGORIES
from employee_help.discovery.rfas import RFA_BANK, RFA_CATEGORIES, RFARequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_ROLES = {"plaintiff", "defendant"}
VALID_CLAIM_VALUES = {ct.value for ct in ClaimType}
TEMPLATE_VAR_RE = re.compile(r"\{([A-Z_]+)\}")

ALL_BANKS = [
    ("SROG", SROG_BANK, SROG_CATEGORIES),
    ("RFPD", RFPD_BANK, RFPD_CATEGORIES),
    ("RFA", RFA_BANK, RFA_CATEGORIES),
]


# ---------------------------------------------------------------------------
# No duplicate IDs
# ---------------------------------------------------------------------------

class TestNoDuplicateIDs:
    @pytest.mark.parametrize("name,bank,_cats", ALL_BANKS, ids=["SROG", "RFPD", "RFA"])
    def test_unique_ids(self, name, bank, _cats):
        ids = [r.id for r in bank]
        assert len(ids) == len(set(ids)), (
            f"{name} bank has duplicate IDs: "
            f"{[x for x in ids if ids.count(x) > 1]}"
        )


# ---------------------------------------------------------------------------
# Valid category references
# ---------------------------------------------------------------------------

class TestValidCategories:
    @pytest.mark.parametrize("name,bank,cats", ALL_BANKS, ids=["SROG", "RFPD", "RFA"])
    def test_all_requests_reference_valid_category(self, name, bank, cats):
        for req in bank:
            assert req.category in cats, (
                f"{name} request {req.id} references unknown category "
                f"'{req.category}'"
            )

    @pytest.mark.parametrize("name,bank,cats", ALL_BANKS, ids=["SROG", "RFPD", "RFA"])
    def test_every_category_has_requests(self, name, bank, cats):
        used_cats = {r.category for r in bank}
        for cat_key in cats:
            assert cat_key in used_cats, (
                f"{name} category '{cat_key}' has no requests"
            )


# ---------------------------------------------------------------------------
# Role annotations
# ---------------------------------------------------------------------------

class TestRoleAnnotations:
    @pytest.mark.parametrize("name,bank,_cats", ALL_BANKS, ids=["SROG", "RFPD", "RFA"])
    def test_non_empty_roles(self, name, bank, _cats):
        for req in bank:
            assert len(req.applicable_roles) > 0, (
                f"{name} request {req.id} has empty applicable_roles"
            )

    @pytest.mark.parametrize("name,bank,_cats", ALL_BANKS, ids=["SROG", "RFPD", "RFA"])
    def test_valid_role_values(self, name, bank, _cats):
        for req in bank:
            for role in req.applicable_roles:
                assert role in VALID_ROLES, (
                    f"{name} request {req.id} has invalid role '{role}'"
                )

    @pytest.mark.parametrize("name,bank,_cats", ALL_BANKS, ids=["SROG", "RFPD", "RFA"])
    def test_explicit_roles_on_all(self, name, bank, _cats):
        """Every request has an explicit applicable_roles annotation
        (not relying on the default)."""
        for req in bank:
            assert req.applicable_roles in (
                ("plaintiff",),
                ("defendant",),
                ("plaintiff", "defendant"),
            ), f"{name} request {req.id} has unexpected roles {req.applicable_roles}"


# ---------------------------------------------------------------------------
# Claim annotations
# ---------------------------------------------------------------------------

class TestClaimAnnotations:
    @pytest.mark.parametrize("name,bank,_cats", ALL_BANKS, ids=["SROG", "RFPD", "RFA"])
    def test_valid_claim_values(self, name, bank, _cats):
        for req in bank:
            for claim in req.applicable_claims:
                assert claim in VALID_CLAIM_VALUES, (
                    f"{name} request {req.id} has invalid claim "
                    f"'{claim}', valid values: {VALID_CLAIM_VALUES}"
                )


# ---------------------------------------------------------------------------
# Template variables
# ---------------------------------------------------------------------------

# Variables that are allowed in templates: the 6 known ones plus
# user-fillable placeholders like [DATE], [AMOUNT], etc.
ALLOWED_TEMPLATE_VARS = VARIABLE_NAMES


class TestTemplateVariables:
    @pytest.mark.parametrize("name,bank,_cats", ALL_BANKS, ids=["SROG", "RFPD", "RFA"])
    def test_known_variables_only(self, name, bank, _cats):
        for req in bank:
            variables = TEMPLATE_VAR_RE.findall(req.text)
            for var in variables:
                assert var in ALLOWED_TEMPLATE_VARS, (
                    f"{name} request {req.id} uses unknown template "
                    f"variable '{{{var}}}'"
                )


# ---------------------------------------------------------------------------
# Request count totals
# ---------------------------------------------------------------------------

class TestRequestCounts:
    def test_srog_count(self):
        assert len(SROG_BANK) == 58

    def test_rfpd_count(self):
        assert len(RFPD_BANK) == 52

    def test_rfa_count(self):
        assert len(RFA_BANK) == 67

    def test_total_count(self):
        total = len(SROG_BANK) + len(RFPD_BANK) + len(RFA_BANK)
        assert total == 177

    def test_srog_category_count(self):
        assert len(SROG_CATEGORIES) == 16

    def test_rfpd_category_count(self):
        assert len(RFPD_CATEGORIES) == 24

    def test_rfa_category_count(self):
        assert len(RFA_CATEGORIES) == 17


# ---------------------------------------------------------------------------
# Role/side consistency
# ---------------------------------------------------------------------------

class TestRoleSideConsistency:
    def test_srog_plaintiff_count(self):
        plaintiff = [r for r in SROG_BANK if "plaintiff" in r.applicable_roles]
        assert len(plaintiff) >= 35  # existing 35 + new plaintiff

    def test_srog_defendant_count(self):
        defendant = [r for r in SROG_BANK if "defendant" in r.applicable_roles]
        assert len(defendant) >= 15  # new defendant categories

    def test_srog_shared_count(self):
        shared = [
            r for r in SROG_BANK
            if r.applicable_roles == ("plaintiff", "defendant")
        ]
        assert len(shared) == 4  # employment_relationship

    def test_rfpd_plaintiff_count(self):
        plaintiff = [r for r in RFPD_BANK if "plaintiff" in r.applicable_roles]
        assert len(plaintiff) >= 28  # existing 28 + new plaintiff

    def test_rfpd_defendant_count(self):
        defendant = [r for r in RFPD_BANK if "defendant" in r.applicable_roles]
        assert len(defendant) >= 15  # new defendant categories

    def test_rfa_shared_count(self):
        shared = [
            r for r in RFA_BANK
            if r.applicable_roles == ("plaintiff", "defendant")
        ]
        assert len(shared) >= 4  # employment_facts + document_genuineness

    def test_rfa_fact_vs_genuineness(self):
        facts = [r for r in RFA_BANK if r.rfa_type == "fact"]
        genuineness = [r for r in RFA_BANK if r.rfa_type == "genuineness"]
        assert len(facts) == 60
        assert len(genuineness) == 7
        assert len(facts) + len(genuineness) == len(RFA_BANK)


# ---------------------------------------------------------------------------
# Claim-gated requests
# ---------------------------------------------------------------------------

class TestClaimGating:
    def test_wage_srogs_gated(self):
        wage_srogs = [r for r in SROG_BANK if r.category == "wages_hours"]
        for r in wage_srogs:
            assert len(r.applicable_claims) > 0, (
                f"Wage SROG {r.id} should be claim-gated"
            )

    def test_accommodation_srogs_gated(self):
        accom_srogs = [r for r in SROG_BANK if r.category == "accommodation"]
        for r in accom_srogs:
            assert "feha_failure_to_accommodate" in r.applicable_claims, (
                f"Accommodation SROG {r.id} should be FEHA-gated"
            )

    def test_wage_rfas_gated(self):
        wage_rfas = [r for r in RFA_BANK if r.category == "wage_facts"]
        for r in wage_rfas:
            assert len(r.applicable_claims) > 0, (
                f"Wage RFA {r.id} should be claim-gated"
            )

    def test_accommodation_rfas_gated(self):
        accom_rfas = [r for r in RFA_BANK if r.category == "accommodation_facts"]
        for r in accom_rfas:
            assert "feha_failure_to_accommodate" in r.applicable_claims, (
                f"Accommodation RFA {r.id} should be FEHA-gated"
            )

    def test_accommodation_rfpds_gated(self):
        accom_rfpds = [r for r in RFPD_BANK if r.category == "accommodation_docs"]
        for r in accom_rfpds:
            assert "feha_failure_to_accommodate" in r.applicable_claims, (
                f"Accommodation RFPD {r.id} should be FEHA-gated"
            )

    def test_timekeeping_rfpd_gated(self):
        time_rfpds = [r for r in RFPD_BANK if r.category == "timekeeping"]
        for r in time_rfpds:
            assert len(r.applicable_claims) > 0, (
                f"Timekeeping RFPD {r.id} should be claim-gated"
            )

    def test_universal_requests_have_no_gate(self):
        """Requests without claim gates should have empty applicable_claims."""
        ungated_srog_cats = {
            "employment_relationship", "adverse_action",
            "comparator_treatment", "decision_makers", "investigation",
            "policies", "damages", "contention_interrogatories",
            "communications", "factual_basis", "emotional_distress",
            "mitigation", "prior_employment", "social_media_recordings",
        }
        for r in SROG_BANK:
            if r.category in ungated_srog_cats:
                assert r.applicable_claims == (), (
                    f"SROG {r.id} in ungated category has claims: "
                    f"{r.applicable_claims}"
                )


# ---------------------------------------------------------------------------
# Order uniqueness within banks
# ---------------------------------------------------------------------------

class TestOrdering:
    @pytest.mark.parametrize("name,bank,_cats", ALL_BANKS, ids=["SROG", "RFPD", "RFA"])
    def test_unique_orders(self, name, bank, _cats):
        orders = [r.order for r in bank]
        assert len(orders) == len(set(orders)), (
            f"{name} bank has duplicate order values"
        )

    @pytest.mark.parametrize("name,bank,_cats", ALL_BANKS, ids=["SROG", "RFPD", "RFA"])
    def test_sequential_orders(self, name, bank, _cats):
        orders = sorted(r.order for r in bank)
        assert orders == list(range(1, len(bank) + 1)), (
            f"{name} bank orders are not sequential 1..{len(bank)}"
        )
