"""Tests for DateExtractor (V2.1b.3)."""

from employee_help.casefile.extractors.dates import DateExtractor, DateResult


class TestDateResult:
    def test_frozen(self):
        import pytest

        r = DateResult(label="Filed", date="2026-01-15", date_type="filing")
        with pytest.raises(AttributeError):
            r.label = "Changed"  # type: ignore[misc]


class TestFilingDates:
    def setup_method(self):
        self.ext = DateExtractor()

    def test_filed_with_month_name(self):
        text = "Filed: January 15, 2026"
        results = self.ext.extract(text)
        assert any(
            r.date == "2026-01-15" and r.date_type == "filing" for r in results
        )

    def test_filed_abbreviated_month(self):
        text = "Filed: Jan. 15, 2026"
        results = self.ext.extract(text)
        assert any(
            r.date == "2026-01-15" and r.date_type == "filing" for r in results
        )

    def test_filing_date_with_slash(self):
        text = "Filing Date: 03/10/2025"
        results = self.ext.extract(text)
        assert any(
            r.date == "2025-03-10" and r.date_type == "filing" for r in results
        )


class TestTrialDates:
    def setup_method(self):
        self.ext = DateExtractor()

    def test_trial_date(self):
        text = "Trial date: March 10, 2027"
        results = self.ext.extract(text)
        assert any(
            r.date == "2027-03-10" and r.date_type == "trial" for r in results
        )

    def test_trial_set_for(self):
        text = "Trial set for June 5, 2027"
        results = self.ext.extract(text)
        assert any(
            r.date == "2027-06-05" and r.date_type == "trial" for r in results
        )


class TestDiscoveryCutoff:
    def setup_method(self):
        self.ext = DateExtractor()

    def test_discovery_cutoff(self):
        text = "Discovery cutoff: January 10, 2027"
        results = self.ext.extract(text)
        assert any(
            r.date == "2027-01-10" and r.date_type == "discovery_cutoff"
            for r in results
        )

    def test_discovery_deadline(self):
        text = "Discovery deadline: 02/28/2027"
        results = self.ext.extract(text)
        assert any(
            r.date == "2027-02-28" and r.date_type == "discovery_cutoff"
            for r in results
        )


class TestEmploymentDates:
    def setup_method(self):
        self.ext = DateExtractor()

    def test_start_date(self):
        text = "Your start date will be March 1, 2019."
        results = self.ext.extract(text)
        assert any(
            r.date == "2019-03-01" and r.date_type == "employment"
            and r.label == "Employment start"
            for r in results
        )

    def test_hired_on(self):
        text = "Plaintiff was hired on June 15, 2020."
        results = self.ext.extract(text)
        assert any(
            r.date == "2020-06-15" and r.date_type == "employment"
            for r in results
        )

    def test_terminated_effective(self):
        text = "your employment is hereby terminated effective November 15, 2025."
        results = self.ext.extract(text)
        assert any(
            r.date == "2025-11-15" and r.date_type == "employment"
            and r.label == "Employment end"
            for r in results
        )

    def test_last_day_of_employment(self):
        text = "Your last day of employment will be December 31, 2025."
        results = self.ext.extract(text)
        assert any(
            r.date == "2025-12-31" and r.date_type == "employment"
            and r.label == "Employment end"
            for r in results
        )


class TestDeadlines:
    def setup_method(self):
        self.ext = DateExtractor()

    def test_deadline(self):
        text = "Response deadline: April 20, 2026"
        results = self.ext.extract(text)
        assert any(
            r.date == "2026-04-20" and r.date_type == "deadline" for r in results
        )

    def test_due_by(self):
        text = "Response is due by May 1, 2026."
        results = self.ext.extract(text)
        assert any(
            r.date == "2026-05-01" and r.date_type == "deadline" for r in results
        )


class TestPayStubDates:
    def setup_method(self):
        self.ext = DateExtractor()

    def test_pay_period_range(self):
        text = "Pay Period: 01/01/2025 - 01/15/2025"
        results = self.ext.extract(text)
        assert any(
            r.date == "2025-01-01" and r.label == "Pay period start" for r in results
        )
        assert any(
            r.date == "2025-01-15" and r.label == "Pay period end" for r in results
        )

    def test_check_date(self):
        text = "Check Date: 01/20/2025"
        results = self.ext.extract(text)
        assert any(
            r.date == "2025-01-20" and r.date_type == "event" for r in results
        )


class TestReviewPeriod:
    def setup_method(self):
        self.ext = DateExtractor()

    def test_review_period(self):
        text = "Review Period: January 2024 - December 2024"
        results = self.ext.extract(text)
        assert any(
            r.date == "2024-01-01" and r.label == "Review period start"
            for r in results
        )
        assert any(
            r.date == "2024-12-28" and r.label == "Review period end"
            for r in results
        )


class TestFullDocument:
    def setup_method(self):
        self.ext = DateExtractor()

    def test_complaint_with_multiple_dates(self):
        text = """
COMPLAINT FOR DAMAGES

Filed: January 15, 2026

1. Plaintiff was hired on March 1, 2019 as an Analyst.

2. Plaintiff's employment was terminated effective November 15, 2025.

Trial date: March 10, 2027
Discovery cutoff: January 10, 2027
"""
        results = self.ext.extract(text)
        dates = {r.date for r in results}
        assert "2026-01-15" in dates  # filing
        assert "2019-03-01" in dates  # employment start
        assert "2025-11-15" in dates  # employment end
        assert "2027-03-10" in dates  # trial
        assert "2027-01-10" in dates  # discovery cutoff

    def test_pay_stub_with_dates(self):
        text = """
EARNINGS STATEMENT

Employee: Maria Martinez
Pay Period: 01/01/2025 - 01/15/2025
Check Date: 01/20/2025
"""
        results = self.ext.extract(text)
        assert len(results) >= 3
        dates = {r.date for r in results}
        assert "2025-01-01" in dates
        assert "2025-01-15" in dates
        assert "2025-01-20" in dates


class TestEdgeCases:
    def setup_method(self):
        self.ext = DateExtractor()

    def test_empty_text(self):
        assert self.ext.extract("") == []

    def test_whitespace_only(self):
        assert self.ext.extract("   \n\t  ") == []

    def test_no_dates(self):
        assert self.ext.extract("This paragraph has no dates at all.") == []

    def test_deduplication(self):
        """Same date+type appearing twice should be deduplicated."""
        text = "Filed: January 15, 2026. The complaint was filed January 15, 2026."
        results = self.ext.extract(text)
        filing_dates = [r for r in results if r.date_type == "filing"]
        assert len(filing_dates) == 1

    def test_iso_date_format(self):
        text = "Filing Date: 2026-01-15"
        results = self.ext.extract(text)
        assert any(
            r.date == "2026-01-15" and r.date_type == "filing" for r in results
        )

    def test_separation_date(self):
        text = "Separation date: October 31, 2025"
        results = self.ext.extract(text)
        assert any(
            r.date == "2025-10-31" and r.date_type == "employment"
            and r.label == "Employment end"
            for r in results
        )
