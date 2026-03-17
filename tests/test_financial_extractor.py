"""Tests for FinancialExtractor (V2.1b.4)."""

from employee_help.casefile.extractors.financial import (
    FinancialExtractor,
    FinancialResult,
)


class TestFinancialResult:
    def test_frozen(self):
        import pytest

        r = FinancialResult(label="Demand", amount=450000.0, amount_type="demand")
        with pytest.raises(AttributeError):
            r.label = "Changed"  # type: ignore[misc]


class TestDemandAmounts:
    def setup_method(self):
        self.ext = FinancialExtractor()

    def test_settlement_demand(self):
        text = "Settlement Demand: $450,000.00"
        results = self.ext.extract(text)
        assert any(
            r.amount == 450000.0 and r.amount_type == "demand" for r in results
        )

    def test_demand_for_payment(self):
        text = "We demand payment of $25,000 in unpaid overtime."
        results = self.ext.extract(text)
        assert any(
            r.amount == 25000.0 and r.amount_type == "demand" for r in results
        )

    def test_demand_in_the_amount_of(self):
        text = "We hereby demand in the amount of $350,000 for damages."
        results = self.ext.extract(text)
        assert any(
            r.amount == 350000.0 and r.amount_type == "demand" for r in results
        )


class TestSettlement:
    def setup_method(self):
        self.ext = FinancialExtractor()

    def test_settled_for(self):
        text = "The parties settled for $125,000."
        results = self.ext.extract(text)
        assert any(
            r.amount == 125000.0 and r.amount_type == "settlement" for r in results
        )

    def test_settlement_amount(self):
        text = "Settlement amount: $200,000.00"
        results = self.ext.extract(text)
        assert any(
            r.amount == 200000.0 and r.amount_type == "settlement" for r in results
        )


class TestCompensation:
    def setup_method(self):
        self.ext = FinancialExtractor()

    def test_base_salary(self):
        text = "Your base salary will be $95,000 annually."
        results = self.ext.extract(text)
        assert any(
            r.amount == 95000.0 and r.amount_type == "compensation" for r in results
        )

    def test_annual_compensation(self):
        text = "Annual compensation: $95,000"
        results = self.ext.extract(text)
        assert any(
            r.amount == 95000.0 and r.amount_type == "compensation" for r in results
        )

    def test_hourly_rate_pre_context(self):
        text = "Plaintiff's hourly rate of $36.06 was below market."
        results = self.ext.extract(text)
        assert any(
            r.amount == 36.06 and r.amount_type == "hourly_rate" for r in results
        )

    def test_hourly_rate_post_context(self):
        text = "Plaintiff was paid $36.06 per hour."
        results = self.ext.extract(text)
        assert any(
            r.amount == 36.06 and r.amount_type == "hourly_rate" for r in results
        )

    def test_hourly_rate_slash_hr(self):
        text = "Rate: $54.09/hr"
        results = self.ext.extract(text)
        assert any(
            r.amount == 54.09 and r.amount_type == "hourly_rate" for r in results
        )


class TestPayAmounts:
    def setup_method(self):
        self.ext = FinancialExtractor()

    def test_gross_and_net_pay(self):
        text = """
        Gross Pay:    $3,533.70
        Net Pay:      $2,558.37
        """
        results = self.ext.extract(text)
        assert any(
            r.amount == 3533.70 and r.label == "Gross pay" for r in results
        )
        assert any(
            r.amount == 2558.37 and r.label == "Net pay" for r in results
        )

    def test_unpaid_wages(self):
        text = "Plaintiff is owed unpaid wages of $12,500."
        results = self.ext.extract(text)
        assert any(
            r.amount == 12500.0 and r.amount_type == "pay" and r.label == "Unpaid wages"
            for r in results
        )

    def test_unpaid_overtime(self):
        text = "unpaid overtime totaling $8,750"
        results = self.ext.extract(text)
        assert any(
            r.amount == 8750.0 and r.amount_type == "pay" for r in results
        )


class TestDamages:
    def setup_method(self):
        self.ext = FinancialExtractor()

    def test_general_damages(self):
        text = "Plaintiff seeks general damages of $100,000."
        results = self.ext.extract(text)
        assert any(
            r.amount == 100000.0 and r.amount_type == "damages"
            and r.label == "General damages"
            for r in results
        )

    def test_punitive_damages(self):
        text = "Plaintiff seeks punitive damages in the amount of $500,000."
        results = self.ext.extract(text)
        assert any(
            r.amount == 500000.0 and r.amount_type == "damages"
            and r.label == "Punitive damages"
            for r in results
        )

    def test_unqualified_damages(self):
        text = "Plaintiff seeks damages of $250,000."
        results = self.ext.extract(text)
        assert any(
            r.amount == 250000.0 and r.amount_type == "damages"
            and r.label == "Damages"
            for r in results
        )


class TestPenalties:
    def setup_method(self):
        self.ext = FinancialExtractor()

    def test_penalty(self):
        text = "waiting time penalty of $5,000"
        results = self.ext.extract(text)
        assert any(
            r.amount == 5000.0 and r.amount_type == "penalty" for r in results
        )


class TestFullDocument:
    def setup_method(self):
        self.ext = FinancialExtractor()

    def test_demand_letter_with_multiple_amounts(self):
        text = """
SETTLEMENT DEMAND

Dear Counsel,

This letter constitutes a demand on behalf of our client against Acme Corp.

Our client was hired at an annual salary of $75,000. She was paid $36.06 per hour.

We hereby demand settlement in the amount of $450,000 for damages arising from
the wrongful termination.

Settlement Demand: $450,000.00
"""
        results = self.ext.extract(text)
        amounts = {r.amount for r in results}
        assert 75000.0 in amounts  # salary
        assert 36.06 in amounts  # hourly rate
        assert 450000.0 in amounts  # demand

    def test_pay_stub_with_amounts(self):
        text = """
EARNINGS STATEMENT

Employee: Maria Martinez
Pay Period: 01/01/2025 - 01/15/2025

Gross Pay:    $3,533.70
Net Pay:      $2,558.37
YTD Gross:    $3,533.70
"""
        results = self.ext.extract(text)
        assert any(r.amount == 3533.70 and r.label == "Gross pay" for r in results)
        assert any(r.amount == 2558.37 and r.label == "Net pay" for r in results)


class TestEdgeCases:
    def setup_method(self):
        self.ext = FinancialExtractor()

    def test_empty_text(self):
        assert self.ext.extract("") == []

    def test_whitespace_only(self):
        assert self.ext.extract("   \n\t  ") == []

    def test_no_amounts(self):
        assert self.ext.extract("This paragraph has no dollar amounts.") == []

    def test_deduplication(self):
        """Same amount+type appearing twice should be deduplicated."""
        text = "Settlement Demand: $450,000. We demand $450,000."
        results = self.ext.extract(text)
        demands = [r for r in results if r.amount_type == "demand"]
        assert len(demands) == 1

    def test_dollar_with_comma_thousands(self):
        text = "Settlement Demand: $1,234,567.89"
        results = self.ext.extract(text)
        assert any(r.amount == 1234567.89 for r in results)
