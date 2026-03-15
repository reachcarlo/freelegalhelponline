"""Tests for LITIGAGENTv2 CaseContext + *View value objects (V2.1a.4)."""

from employee_help.casefile.context import (
    AttorneyView,
    CaseContext,
    ClaimView,
    CourtView,
    DateView,
    EmploymentPeriodView,
    FinancialView,
    PartyView,
)


class TestViewDataclasses:
    def test_party_view(self):
        p = PartyView(name="Alice", role="plaintiff", party_type="individual")
        assert p.name == "Alice"
        assert p.role == "plaintiff"
        assert p.party_type == "individual"
        assert p.count is None

    def test_party_view_doe(self):
        p = PartyView(name="Does 1-50", role="defendant", party_type="doe", count=50)
        assert p.count == 50

    def test_employment_period_view(self):
        e = EmploymentPeriodView(
            employer="Acme Corp",
            position="Analyst",
            start_date="2019-03-01",
            end_date="2021-06-15",
            change_reason="hired",
        )
        assert e.employer == "Acme Corp"
        assert e.position == "Analyst"
        assert e.department is None
        assert e.compensation_rate is None

    def test_claim_view_defaults(self):
        c = ClaimView(claim_type="feha_discrimination")
        assert c.status == "active"
        assert c.protected_class is None

    def test_financial_view(self):
        f = FinancialView(label="Initial demand", amount=450000, date="2025-12-01")
        assert f.amount == 450000

    def test_court_view(self):
        c = CourtView(court="Superior Court of California", county="Los Angeles")
        assert c.county == "Los Angeles"
        assert c.department is None

    def test_attorney_view(self):
        a = AttorneyView(name="David Kim", side="plaintiff", firm="Kim & Associates")
        assert a.firm == "Kim & Associates"
        assert a.bar_number is None

    def test_date_view(self):
        d = DateView(label="Trial date", date="2027-03-10", date_type="trial")
        assert d.date_type == "trial"


class TestCaseContext:
    def _make_context(self, **overrides) -> CaseContext:
        defaults = {"case_id": "c1", "case_name": "Test Case"}
        defaults.update(overrides)
        return CaseContext(**defaults)

    def test_empty_context(self):
        ctx = self._make_context()
        assert ctx.case_id == "c1"
        assert ctx.parties == []
        assert ctx.court is None
        assert ctx.fact_count == 0
        assert ctx.confirmed_count == 0
        assert ctx.extraction_sources == {}

    def test_frozen(self):
        ctx = self._make_context()
        import pytest

        with pytest.raises(AttributeError):
            ctx.case_name = "Changed"  # type: ignore[misc]

    def test_plaintiff_names(self):
        ctx = self._make_context(
            parties=[
                PartyView(name="Alice", role="plaintiff", party_type="individual"),
                PartyView(name="Acme Corp", role="defendant", party_type="entity"),
                PartyView(name="Bob", role="plaintiff", party_type="individual"),
            ]
        )
        assert ctx.plaintiff_names == ["Alice", "Bob"]

    def test_defendant_names(self):
        ctx = self._make_context(
            parties=[
                PartyView(name="Alice", role="plaintiff", party_type="individual"),
                PartyView(name="Acme Corp", role="defendant", party_type="entity"),
            ]
        )
        assert ctx.defendant_names == ["Acme Corp"]

    def test_active_claims(self):
        ctx = self._make_context(
            claims=[
                ClaimView(claim_type="feha_discrimination", status="active"),
                ClaimView(claim_type="wage_theft", status="dropped"),
                ClaimView(claim_type="retaliation", status="active"),
            ]
        )
        active = ctx.active_claims
        assert len(active) == 2
        assert all(c.status == "active" for c in active)

    def test_current_demand(self):
        ctx = self._make_context(
            financials=[
                FinancialView(label="Initial demand", amount=450000),
                FinancialView(label="Counter-offer", amount=125000),
                FinancialView(label="Revised demand", amount=350000),
            ]
        )
        assert ctx.current_demand is not None
        assert ctx.current_demand.amount == 350000

    def test_current_demand_none(self):
        ctx = self._make_context(financials=[])
        assert ctx.current_demand is None

    def test_current_demand_ignores_non_demand(self):
        ctx = self._make_context(
            financials=[
                FinancialView(label="Settlement payment", amount=200000),
            ]
        )
        assert ctx.current_demand is None

    def test_all_person_names(self):
        ctx = self._make_context(
            parties=[
                PartyView(name="Alice", role="plaintiff", party_type="individual"),
                PartyView(name="Acme Corp", role="defendant", party_type="entity"),
            ],
            attorneys=[
                AttorneyView(name="David Kim", side="plaintiff"),
            ],
        )
        assert ctx.all_person_names == ["Alice", "David Kim"]

    def test_all_entity_names(self):
        ctx = self._make_context(
            parties=[
                PartyView(name="Acme Corp", role="defendant", party_type="entity"),
                PartyView(name="Alice", role="plaintiff", party_type="individual"),
            ],
            attorneys=[
                AttorneyView(name="David Kim", side="plaintiff", firm="Kim & Associates"),
            ],
            employment_history=[
                EmploymentPeriodView(employer="Acme Corp"),
            ],
        )
        names = ctx.all_entity_names
        assert "Acme Corp" in names
        assert "Kim & Associates" in names
        # deduplicated
        assert names.count("Acme Corp") == 1
