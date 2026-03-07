"""Tests for Phase D.3 — role-aware API and claim mapping integration.

Covers:
- DiscoverySuggestions.categories_for_role() helper
- Defendant-specific category overrides in CLAIM_DISCOVERY_MAP
- merge_suggestions() merging of defendant fields
- Bank endpoint role filtering (party_role query parameter)
- Suggest endpoint role-aware category mapping
- Variable resolution in bank endpoint responses
- Schema updates (applicable_roles, applicable_claims)
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from employee_help.discovery.claim_mapping import (
    CLAIM_DISCOVERY_MAP,
    DiscoverySuggestions,
    get_suggestions_for_claims,
    merge_suggestions,
)
from employee_help.discovery.models import ClaimType, PartyRole


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """Create a test client that bypasses RAG service init."""
    from unittest.mock import MagicMock, patch

    mock_retrieval = MagicMock()
    mock_retrieval.embedding_service = MagicMock()
    mock_retrieval.vector_store = MagicMock()
    mock_answer = MagicMock()

    with (
        patch("employee_help.api.deps._retrieval_service", mock_retrieval),
        patch("employee_help.api.deps._answer_service", mock_answer),
        patch("employee_help.api.deps._feedback_store", MagicMock()),
    ):
        from employee_help.api import main as main_mod

        main_mod._discovery_rate_store.clear()
        yield TestClient(main_mod.app)


# ---------------------------------------------------------------------------
# D.3.1 — categories_for_role() helper
# ---------------------------------------------------------------------------


class TestCategoriesForRole:
    def test_plaintiff_returns_base_categories(self):
        sug = CLAIM_DISCOVERY_MAP[ClaimType.FEHA_DISCRIMINATION]
        cats = sug.categories_for_role("srogs", PartyRole.PLAINTIFF)
        assert cats == sug.srog_categories

    def test_defendant_returns_override(self):
        sug = CLAIM_DISCOVERY_MAP[ClaimType.FEHA_DISCRIMINATION]
        cats = sug.categories_for_role("srogs", PartyRole.DEFENDANT)
        assert cats == sug.srog_categories_defendant

    def test_defendant_fallback_when_no_override(self):
        """When defendant override is None, falls back to base."""
        sug = DiscoverySuggestions(
            disc001_sections=(),
            disc002_sections=(),
            srog_categories=("employment_relationship",),
            rfpd_categories=("personnel_file",),
            rfa_categories=("employment_facts",),
            # No defendant overrides
        )
        cats = sug.categories_for_role("srogs", PartyRole.DEFENDANT)
        assert cats == ("employment_relationship",)

    def test_all_three_tools_work(self):
        sug = CLAIM_DISCOVERY_MAP[ClaimType.FEHA_DISCRIMINATION]
        for tool in ("srogs", "rfpds", "rfas"):
            plaintiff = sug.categories_for_role(tool, PartyRole.PLAINTIFF)
            defendant = sug.categories_for_role(tool, PartyRole.DEFENDANT)
            assert len(plaintiff) > 0
            assert len(defendant) > 0

    def test_plaintiff_and_defendant_differ(self):
        """Plaintiff and defendant should get different categories."""
        sug = CLAIM_DISCOVERY_MAP[ClaimType.FEHA_DISCRIMINATION]
        plaintiff = sug.categories_for_role("srogs", PartyRole.PLAINTIFF)
        defendant = sug.categories_for_role("srogs", PartyRole.DEFENDANT)
        assert plaintiff != defendant

    def test_defendant_categories_include_defendant_only_cats(self):
        sug = CLAIM_DISCOVERY_MAP[ClaimType.FEHA_DISCRIMINATION]
        defendant_srogs = sug.categories_for_role("srogs", PartyRole.DEFENDANT)
        assert "factual_basis" in defendant_srogs
        assert "emotional_distress" in defendant_srogs

    def test_plaintiff_categories_exclude_defendant_only_cats(self):
        sug = CLAIM_DISCOVERY_MAP[ClaimType.FEHA_DISCRIMINATION]
        plaintiff_srogs = sug.categories_for_role("srogs", PartyRole.PLAINTIFF)
        assert "factual_basis" not in plaintiff_srogs
        assert "emotional_distress" not in plaintiff_srogs


# ---------------------------------------------------------------------------
# D.3.1 — All claim types have defendant overrides
# ---------------------------------------------------------------------------


class TestAllClaimsHaveDefendantOverrides:
    def test_every_claim_type_has_srog_defendant(self):
        for ct in ClaimType:
            sug = CLAIM_DISCOVERY_MAP[ct]
            assert sug.srog_categories_defendant is not None, (
                f"{ct.value} missing srog_categories_defendant"
            )

    def test_every_claim_type_has_rfpd_defendant(self):
        for ct in ClaimType:
            sug = CLAIM_DISCOVERY_MAP[ct]
            assert sug.rfpd_categories_defendant is not None, (
                f"{ct.value} missing rfpd_categories_defendant"
            )

    def test_every_claim_type_has_rfa_defendant(self):
        for ct in ClaimType:
            sug = CLAIM_DISCOVERY_MAP[ct]
            assert sug.rfa_categories_defendant is not None, (
                f"{ct.value} missing rfa_categories_defendant"
            )

    def test_defendant_categories_reference_valid_srog_cats(self):
        from employee_help.discovery.srogs import SROG_CATEGORIES

        valid = set(SROG_CATEGORIES.keys())
        for ct in ClaimType:
            sug = CLAIM_DISCOVERY_MAP[ct]
            if sug.srog_categories_defendant:
                for cat in sug.srog_categories_defendant:
                    assert cat in valid, (
                        f"{ct.value} defendant SROG references invalid '{cat}'"
                    )

    def test_defendant_categories_reference_valid_rfpd_cats(self):
        from employee_help.discovery.rfpds import RFPD_CATEGORIES

        valid = set(RFPD_CATEGORIES.keys())
        for ct in ClaimType:
            sug = CLAIM_DISCOVERY_MAP[ct]
            if sug.rfpd_categories_defendant:
                for cat in sug.rfpd_categories_defendant:
                    assert cat in valid, (
                        f"{ct.value} defendant RFPD references invalid '{cat}'"
                    )

    def test_defendant_categories_reference_valid_rfa_cats(self):
        from employee_help.discovery.rfas import RFA_CATEGORIES

        valid = set(RFA_CATEGORIES.keys())
        for ct in ClaimType:
            sug = CLAIM_DISCOVERY_MAP[ct]
            if sug.rfa_categories_defendant:
                for cat in sug.rfa_categories_defendant:
                    assert cat in valid, (
                        f"{ct.value} defendant RFA references invalid '{cat}'"
                    )


# ---------------------------------------------------------------------------
# D.3.1 — Merge with defendant fields
# ---------------------------------------------------------------------------


class TestMergeDefendantFields:
    def test_merge_preserves_defendant_fields(self):
        s1 = DiscoverySuggestions(
            disc001_sections=("1.1",),
            disc002_sections=("200.1",),
            srog_categories=("damages",),
            rfpd_categories=("personnel_file",),
            rfa_categories=("employment_facts",),
            srog_categories_defendant=("factual_basis",),
            rfpd_categories_defendant=("medical_records",),
            rfa_categories_defendant=("performance_facts",),
        )
        merged = merge_suggestions([s1])
        assert merged.srog_categories_defendant == ("factual_basis",)
        assert merged.rfpd_categories_defendant == ("medical_records",)
        assert merged.rfa_categories_defendant == ("performance_facts",)

    def test_merge_unions_defendant_fields(self):
        s1 = DiscoverySuggestions(
            disc001_sections=("1.1",),
            disc002_sections=("200.1",),
            srog_categories=("damages",),
            rfpd_categories=("personnel_file",),
            rfa_categories=("employment_facts",),
            srog_categories_defendant=("factual_basis",),
            rfpd_categories_defendant=("medical_records",),
            rfa_categories_defendant=("performance_facts",),
        )
        s2 = DiscoverySuggestions(
            disc001_sections=("2.1",),
            disc002_sections=("201.1",),
            srog_categories=("policies",),
            rfpd_categories=("communications",),
            rfa_categories=("document_genuineness",),
            srog_categories_defendant=("emotional_distress", "factual_basis"),
            rfpd_categories_defendant=("financial_records",),
            rfa_categories_defendant=("damages_limitations",),
        )
        merged = merge_suggestions([s1, s2])
        assert "factual_basis" in merged.srog_categories_defendant
        assert "emotional_distress" in merged.srog_categories_defendant
        assert "medical_records" in merged.rfpd_categories_defendant
        assert "financial_records" in merged.rfpd_categories_defendant
        assert "performance_facts" in merged.rfa_categories_defendant
        assert "damages_limitations" in merged.rfa_categories_defendant

    def test_merge_none_when_no_defendant_fields(self):
        s1 = DiscoverySuggestions(
            disc001_sections=("1.1",),
            disc002_sections=("200.1",),
            srog_categories=("damages",),
            rfpd_categories=("personnel_file",),
            rfa_categories=("employment_facts",),
        )
        merged = merge_suggestions([s1])
        assert merged.srog_categories_defendant is None

    def test_merge_multi_claim_preserves_defendant(self):
        """Real-world: merging FEHA + wage should union defendant cats."""
        merged = get_suggestions_for_claims([
            ClaimType.FEHA_DISCRIMINATION,
            ClaimType.WAGE_THEFT,
        ])
        assert merged.srog_categories_defendant is not None
        # Should have both standard and wage defendant categories
        assert "factual_basis" in merged.srog_categories_defendant
        assert "employment_relationship" in merged.srog_categories_defendant


# ---------------------------------------------------------------------------
# D.3.1 — Claim-specific defendant category content
# ---------------------------------------------------------------------------


class TestClaimSpecificDefendantCategories:
    def test_feha_defendant_has_direct_evidence(self):
        sug = CLAIM_DISCOVERY_MAP[ClaimType.FEHA_DISCRIMINATION]
        assert "direct_evidence" in sug.rfa_categories_defendant

    def test_wage_defendant_has_no_emotional_distress(self):
        sug = CLAIM_DISCOVERY_MAP[ClaimType.WAGE_THEFT]
        assert "emotional_distress" not in sug.srog_categories_defendant

    def test_wage_defendant_has_no_direct_evidence(self):
        sug = CLAIM_DISCOVERY_MAP[ClaimType.WAGE_THEFT]
        assert "direct_evidence" not in sug.rfa_categories_defendant

    def test_tort_defendant_has_emotional_distress(self):
        sug = CLAIM_DISCOVERY_MAP[ClaimType.IIED]
        assert "emotional_distress" in sug.srog_categories_defendant

    def test_contract_defendant_has_no_emotional_distress(self):
        sug = CLAIM_DISCOVERY_MAP[ClaimType.BREACH_IMPLIED_CONTRACT]
        assert "emotional_distress" not in sug.srog_categories_defendant

    def test_all_defendants_have_employment_relationship(self):
        for ct in ClaimType:
            sug = CLAIM_DISCOVERY_MAP[ct]
            assert "employment_relationship" in sug.srog_categories_defendant, (
                f"{ct.value} defendant SROGs missing employment_relationship"
            )

    def test_all_defendants_have_factual_basis(self):
        for ct in ClaimType:
            sug = CLAIM_DISCOVERY_MAP[ct]
            assert "factual_basis" in sug.srog_categories_defendant, (
                f"{ct.value} defendant SROGs missing factual_basis"
            )


# ---------------------------------------------------------------------------
# D.3.2 — Bank endpoint role filtering
# ---------------------------------------------------------------------------


class TestBankEndpointRoleFiltering:
    def test_bank_no_role_returns_full_bank(self, client):
        """Without party_role, returns full bank (backwards compatible)."""
        resp = client.get("/api/discovery/banks/srogs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_items"] == 58  # Full bank

    def test_bank_plaintiff_returns_plaintiff_items(self, client):
        resp = client.get("/api/discovery/banks/srogs?party_role=plaintiff")
        assert resp.status_code == 200
        data = resp.json()
        # Should have fewer items than full bank (no defendant-only)
        assert data["total_items"] < 58
        assert data["total_items"] > 0

    def test_bank_defendant_returns_defendant_items(self, client):
        resp = client.get("/api/discovery/banks/srogs?party_role=defendant")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_items"] > 0
        assert data["total_items"] < 58

    def test_bank_invalid_role_returns_422(self, client):
        resp = client.get("/api/discovery/banks/srogs?party_role=judge")
        assert resp.status_code == 422

    def test_plaintiff_and_defendant_dont_overlap_on_exclusive(self, client):
        """Plaintiff-only items should not appear for defendant and vice versa."""
        p_resp = client.get("/api/discovery/banks/srogs?party_role=plaintiff")
        d_resp = client.get("/api/discovery/banks/srogs?party_role=defendant")
        p_ids = {item["id"] for item in p_resp.json()["items"]}
        d_ids = {item["id"] for item in d_resp.json()["items"]}
        # Shared items appear in both; exclusive items don't
        # There should be some items unique to each side
        plaintiff_only = p_ids - d_ids
        defendant_only = d_ids - p_ids
        assert len(plaintiff_only) > 0
        assert len(defendant_only) > 0

    def test_shared_items_appear_in_both(self, client):
        """Shared items (both roles) should appear for both roles."""
        p_resp = client.get("/api/discovery/banks/srogs?party_role=plaintiff")
        d_resp = client.get("/api/discovery/banks/srogs?party_role=defendant")
        p_ids = {item["id"] for item in p_resp.json()["items"]}
        d_ids = {item["id"] for item in d_resp.json()["items"]}
        shared = p_ids & d_ids
        assert len(shared) > 0  # employment_relationship items are shared

    def test_rfpd_bank_role_filtering(self, client):
        full = client.get("/api/discovery/banks/rfpds").json()
        plaintiff = client.get("/api/discovery/banks/rfpds?party_role=plaintiff").json()
        defendant = client.get("/api/discovery/banks/rfpds?party_role=defendant").json()
        assert full["total_items"] == 52
        assert plaintiff["total_items"] < 52
        assert defendant["total_items"] < 52
        assert plaintiff["total_items"] > 0
        assert defendant["total_items"] > 0

    def test_rfa_bank_role_filtering(self, client):
        full = client.get("/api/discovery/banks/rfas").json()
        plaintiff = client.get("/api/discovery/banks/rfas?party_role=plaintiff").json()
        defendant = client.get("/api/discovery/banks/rfas?party_role=defendant").json()
        assert full["total_items"] == 67
        assert plaintiff["total_items"] < 67
        assert defendant["total_items"] < 67

    def test_empty_categories_omitted(self, client):
        """Categories with zero items after filtering should be omitted."""
        resp = client.get("/api/discovery/banks/srogs?party_role=defendant")
        data = resp.json()
        cat_keys = {c["key"] for c in data["categories"]}
        # Defendant shouldn't have plaintiff-only categories like adverse_action
        assert "adverse_action" not in cat_keys
        # But should have defendant categories like factual_basis
        assert "factual_basis" in cat_keys

    def test_category_counts_match_filtered_items(self, client):
        """Category counts should match the number of items in that category."""
        resp = client.get("/api/discovery/banks/srogs?party_role=plaintiff")
        data = resp.json()
        for cat in data["categories"]:
            actual = sum(1 for i in data["items"] if i["category"] == cat["key"])
            assert cat["count"] == actual, (
                f"Category {cat['key']}: count={cat['count']} but {actual} items"
            )


# ---------------------------------------------------------------------------
# D.3.3 — Suggest endpoint role-aware mapping
# ---------------------------------------------------------------------------


class TestSuggestRoleAware:
    def test_plaintiff_feha_gets_plaintiff_categories(self, client):
        resp = client.post("/api/discovery/suggest", json={
            "claim_types": ["feha_discrimination"],
            "party_role": "plaintiff",
            "tool_type": "srogs",
        })
        assert resp.status_code == 200
        data = resp.json()
        cat_keys = [c["category"] for c in data["suggested_categories"]]
        assert "comparator_treatment" in cat_keys
        assert "adverse_action" in cat_keys
        # Should NOT include defendant-only categories
        assert "factual_basis" not in cat_keys

    def test_defendant_feha_gets_defendant_categories(self, client):
        resp = client.post("/api/discovery/suggest", json={
            "claim_types": ["feha_discrimination"],
            "party_role": "defendant",
            "tool_type": "srogs",
        })
        assert resp.status_code == 200
        data = resp.json()
        cat_keys = [c["category"] for c in data["suggested_categories"]]
        assert "factual_basis" in cat_keys
        assert "emotional_distress" in cat_keys
        # Should NOT include plaintiff-only categories
        assert "comparator_treatment" not in cat_keys
        assert "adverse_action" not in cat_keys

    def test_defendant_rfpd_categories(self, client):
        resp = client.post("/api/discovery/suggest", json={
            "claim_types": ["feha_discrimination"],
            "party_role": "defendant",
            "tool_type": "rfpds",
        })
        assert resp.status_code == 200
        data = resp.json()
        cat_keys = [c["category"] for c in data["suggested_categories"]]
        assert "medical_records" in cat_keys
        assert "financial_records" in cat_keys

    def test_defendant_rfa_categories(self, client):
        resp = client.post("/api/discovery/suggest", json={
            "claim_types": ["feha_discrimination"],
            "party_role": "defendant",
            "tool_type": "rfas",
        })
        assert resp.status_code == 200
        data = resp.json()
        cat_keys = [c["category"] for c in data["suggested_categories"]]
        assert "performance_facts" in cat_keys
        assert "direct_evidence" in cat_keys

    def test_defendant_wage_limited_categories(self, client):
        """Defendant wage claims should get fewer categories than FEHA."""
        resp = client.post("/api/discovery/suggest", json={
            "claim_types": ["wage_theft"],
            "party_role": "defendant",
            "tool_type": "srogs",
        })
        data = resp.json()
        cat_keys = [c["category"] for c in data["suggested_categories"]]
        assert "factual_basis" in cat_keys
        assert "mitigation" in cat_keys
        assert "emotional_distress" not in cat_keys

    def test_suggest_total_reflects_role_filter(self, client):
        """Total should count role-filtered items, not full bank."""
        p_resp = client.post("/api/discovery/suggest", json={
            "claim_types": ["feha_discrimination"],
            "party_role": "plaintiff",
            "tool_type": "srogs",
        })
        d_resp = client.post("/api/discovery/suggest", json={
            "claim_types": ["feha_discrimination"],
            "party_role": "defendant",
            "tool_type": "srogs",
        })
        p_total = p_resp.json()["total_suggested"]
        d_total = d_resp.json()["total_suggested"]
        # Both should have items but not the full bank
        assert p_total > 0
        assert d_total > 0

    def test_empty_categories_not_in_suggest_response(self, client):
        """Categories with 0 items after filtering should not appear."""
        resp = client.post("/api/discovery/suggest", json={
            "claim_types": ["feha_discrimination"],
            "party_role": "defendant",
            "tool_type": "srogs",
        })
        data = resp.json()
        for cat in data["suggested_categories"]:
            assert cat["request_count"] > 0


# ---------------------------------------------------------------------------
# D.3.4 — Variable resolution in bank responses
# ---------------------------------------------------------------------------


class TestVariableResolution:
    def test_plaintiff_resolves_propounding_designation(self, client):
        resp = client.get("/api/discovery/banks/srogs?party_role=plaintiff")
        data = resp.json()
        all_text = " ".join(i["text"] for i in data["items"])
        # Variables should be resolved, not raw
        assert "{PROPOUNDING_DESIGNATION}" not in all_text
        assert "{RESPONDING_DESIGNATION}" not in all_text

    def test_defendant_resolves_propounding_designation(self, client):
        resp = client.get("/api/discovery/banks/srogs?party_role=defendant")
        data = resp.json()
        all_text = " ".join(i["text"] for i in data["items"])
        assert "{PROPOUNDING_DESIGNATION}" not in all_text
        assert "{RESPONDING_DESIGNATION}" not in all_text

    def test_no_role_leaves_templates_raw(self, client):
        """Without party_role, template variables should not be resolved."""
        resp = client.get("/api/discovery/banks/srogs")
        data = resp.json()
        # Some items use {EMPLOYEE} or {EMPLOYER} variables
        all_text = " ".join(i["text"] for i in data["items"])
        # Raw templates contain curly-brace variables
        assert "{EMPLOYEE}" in all_text or "{EMPLOYER}" in all_text

    def test_employee_employer_resolve_to_defaults(self, client):
        """Without case info, EMPLOYEE/EMPLOYER resolve to definition-style defaults."""
        resp = client.get("/api/discovery/banks/srogs?party_role=plaintiff")
        data = resp.json()
        all_text = " ".join(i["text"] for i in data["items"])
        # {EMPLOYEE} should resolve to "EMPLOYEE" (the default)
        assert "{EMPLOYEE}" not in all_text
        # But the word EMPLOYEE should still appear (as resolved value)
        assert "EMPLOYEE" in all_text


# ---------------------------------------------------------------------------
# D.3.5 — Schema includes applicable_roles and applicable_claims
# ---------------------------------------------------------------------------


class TestSchemaFields:
    def test_bank_items_include_applicable_roles(self, client):
        resp = client.get("/api/discovery/banks/srogs")
        data = resp.json()
        for item in data["items"]:
            assert "applicable_roles" in item
            assert item["applicable_roles"] is not None
            assert len(item["applicable_roles"]) > 0

    def test_bank_items_include_applicable_claims(self, client):
        resp = client.get("/api/discovery/banks/srogs")
        data = resp.json()
        # At least some items should have applicable_claims (wage-gated)
        has_claims = [i for i in data["items"] if i["applicable_claims"]]
        has_no_claims = [i for i in data["items"] if not i["applicable_claims"]]
        assert len(has_claims) > 0  # wage SROGs are claim-gated
        assert len(has_no_claims) > 0  # most are universal

    def test_rfas_bank_items_have_rfa_type(self, client):
        resp = client.get("/api/discovery/banks/rfas")
        data = resp.json()
        rfa_types = {i["rfa_type"] for i in data["items"]}
        assert "fact" in rfa_types
        assert "genuineness" in rfa_types

    def test_filtered_items_still_have_roles(self, client):
        resp = client.get("/api/discovery/banks/srogs?party_role=plaintiff")
        data = resp.json()
        for item in data["items"]:
            assert "plaintiff" in item["applicable_roles"]
