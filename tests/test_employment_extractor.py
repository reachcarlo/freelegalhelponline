"""Tests for EmploymentExtractor (V2.1b.5)."""

from employee_help.casefile.extractors.employment import (
    EmploymentExtractor,
    EmploymentResult,
)


class TestEmploymentResult:
    def test_frozen(self):
        import pytest

        r = EmploymentResult(field="employer", value="Acme Corp")
        with pytest.raises(AttributeError):
            r.field = "changed"  # type: ignore[misc]


class TestEmployerExtraction:
    def setup_method(self):
        self.ext = EmploymentExtractor()

    def test_employer_labeled(self):
        text = "Employer: Acme Corp"
        results = self.ext.extract(text)
        assert any(
            r.field == "employer" and r.value == "Acme Corp" for r in results
        )

    def test_company_name_labeled(self):
        text = "Company Name: Global Industries Inc."
        results = self.ext.extract(text)
        assert any(
            r.field == "employer" and r.value == "Global Industries Inc."
            for r in results
        )

    def test_employed_by(self):
        text = "Plaintiff was employed by Acme Corp as an Analyst."
        results = self.ext.extract(text)
        assert any(
            r.field == "employer" and r.value == "Acme Corp" for r in results
        )

    def test_worked_for(self):
        text = "Plaintiff worked for ACME CORPORATION from 2019 to 2025."
        results = self.ext.extract(text)
        assert any(
            r.field == "employer" and r.value == "ACME CORPORATION"
            for r in results
        )

    def test_hired_by(self):
        text = "Plaintiff was hired by Tech Solutions Inc on June 15, 2020."
        results = self.ext.extract(text)
        assert any(
            r.field == "employer" and r.value == "Tech Solutions Inc"
            for r in results
        )

    def test_employment_with(self):
        text = "Her employment with Acme Corp began in 2019."
        results = self.ext.extract(text)
        assert any(
            r.field == "employer" and r.value == "Acme Corp" for r in results
        )


class TestPositionExtraction:
    def setup_method(self):
        self.ext = EmploymentExtractor()

    def test_position_labeled(self):
        text = "Position: Senior Analyst"
        results = self.ext.extract(text)
        assert any(
            r.field == "position" and r.value == "Senior Analyst"
            for r in results
        )

    def test_job_title_labeled(self):
        text = "Job Title: VP of Engineering"
        results = self.ext.extract(text)
        assert any(
            r.field == "position" and r.value == "VP of Engineering"
            for r in results
        )

    def test_position_of(self):
        text = "We offer you the position of Senior Analyst in our firm."
        results = self.ext.extract(text)
        assert any(
            r.field == "position" and r.value == "Senior Analyst"
            for r in results
        )

    def test_employed_as(self):
        text = "Plaintiff was employed as an Analyst in the Finance department."
        results = self.ext.extract(text)
        assert any(
            r.field == "position" and r.value == "Analyst" for r in results
        )

    def test_hired_as(self):
        text = "She was hired as a Project Manager on March 1, 2019."
        results = self.ext.extract(text)
        assert any(
            r.field == "position" and r.value == "Project Manager"
            for r in results
        )

    def test_worked_as(self):
        text = "Plaintiff worked as a Staff Attorney for 3 years."
        results = self.ext.extract(text)
        assert any(
            r.field == "position" and r.value == "Staff Attorney"
            for r in results
        )


class TestDepartmentExtraction:
    def setup_method(self):
        self.ext = EmploymentExtractor()

    def test_department_labeled(self):
        text = "Department: Finance"
        results = self.ext.extract(text)
        assert any(
            r.field == "department" and r.value == "Finance" for r in results
        )

    def test_dept_abbreviated(self):
        text = "Dept: Human Resources"
        results = self.ext.extract(text)
        assert any(
            r.field == "department" and r.value == "Human Resources"
            for r in results
        )

    def test_department_contextual(self):
        text = "Plaintiff worked in the Marketing department."
        results = self.ext.extract(text)
        assert any(
            r.field == "department" and r.value == "Marketing" for r in results
        )


class TestCompensationExtraction:
    def setup_method(self):
        self.ext = EmploymentExtractor()

    def test_base_salary(self):
        text = "Your base salary will be $95,000 annually."
        results = self.ext.extract(text)
        comp = [r for r in results if r.field == "compensation"]
        assert len(comp) >= 1
        assert comp[0].compensation_rate == 95000.0
        assert comp[0].compensation_type == "salary"
        assert comp[0].pay_period == "annual"

    def test_annual_compensation(self):
        text = "Annual compensation: $120,000"
        results = self.ext.extract(text)
        comp = [r for r in results if r.field == "compensation"]
        assert len(comp) >= 1
        assert comp[0].compensation_rate == 120000.0
        assert comp[0].compensation_type == "salary"

    def test_hourly_rate_pre_context(self):
        text = "Plaintiff's hourly rate of $36.06 was below market."
        results = self.ext.extract(text)
        comp = [r for r in results if r.field == "compensation"]
        assert len(comp) >= 1
        assert comp[0].compensation_rate == 36.06
        assert comp[0].compensation_type == "hourly"

    def test_hourly_rate_post_context(self):
        text = "Plaintiff was paid $36.06 per hour."
        results = self.ext.extract(text)
        comp = [r for r in results if r.field == "compensation"]
        assert len(comp) >= 1
        assert comp[0].compensation_rate == 36.06
        assert comp[0].compensation_type == "hourly"

    def test_hourly_rate_slash(self):
        text = "Rate: $54.09/hr"
        results = self.ext.extract(text)
        comp = [r for r in results if r.field == "compensation"]
        assert len(comp) >= 1
        assert comp[0].compensation_rate == 54.09
        assert comp[0].compensation_type == "hourly"

    def test_pay_rate_hourly_inference(self):
        text = "Pay Rate: $42.50"
        results = self.ext.extract(text)
        comp = [r for r in results if r.field == "compensation"]
        assert len(comp) >= 1
        assert comp[0].compensation_rate == 42.50
        assert comp[0].compensation_type == "hourly"

    def test_pay_rate_salary_inference(self):
        text = "Pay Rate: $85,000"
        results = self.ext.extract(text)
        comp = [r for r in results if r.field == "compensation"]
        assert len(comp) >= 1
        assert comp[0].compensation_rate == 85000.0
        assert comp[0].compensation_type == "salary"


class TestFullDocument:
    def setup_method(self):
        self.ext = EmploymentExtractor()

    def test_complaint_with_employment_details(self):
        text = """
COMPLAINT FOR DAMAGES

1. Plaintiff was employed by ACME CORP as an Analyst.

2. Plaintiff worked in the Finance department.

3. Plaintiff's annual salary was $95,000.

4. Plaintiff was hired by ACME CORP on March 1, 2019.
"""
        results = self.ext.extract(text)
        fields = {r.field for r in results}
        assert "employer" in fields
        assert "position" in fields
        assert "department" in fields
        assert "compensation" in fields
        assert any(r.value == "ACME CORP" and r.field == "employer" for r in results)
        assert any(r.value == "Analyst" and r.field == "position" for r in results)
        assert any(r.value == "Finance" and r.field == "department" for r in results)

    def test_pay_stub(self):
        text = """
EARNINGS STATEMENT

Employer: Acme Corp
Employee: Maria Martinez
Position: Senior Analyst
Department: Finance
Pay Rate: $36.06

Pay Period: 01/01/2025 - 01/15/2025
Gross Pay:    $3,533.70
Net Pay:      $2,558.37
"""
        results = self.ext.extract(text)
        assert any(
            r.field == "employer" and r.value == "Acme Corp" for r in results
        )
        assert any(
            r.field == "position" and r.value == "Senior Analyst" for r in results
        )
        assert any(
            r.field == "department" and r.value == "Finance" for r in results
        )
        assert any(
            r.field == "compensation" and r.compensation_rate == 36.06
            for r in results
        )

    def test_offer_letter(self):
        text = """
Dear Ms. Martinez,

We are pleased to offer you the position of Senior Analyst at Acme Corp.

Your base salary will be $95,000 annually.

Your start date will be March 1, 2019.
"""
        results = self.ext.extract(text)
        assert any(
            r.field == "position" and r.value == "Senior Analyst" for r in results
        )
        assert any(
            r.field == "compensation" and r.compensation_rate == 95000.0
            for r in results
        )


class TestEdgeCases:
    def setup_method(self):
        self.ext = EmploymentExtractor()

    def test_empty_text(self):
        assert self.ext.extract("") == []

    def test_whitespace_only(self):
        assert self.ext.extract("   \n\t  ") == []

    def test_no_employment_info(self):
        assert self.ext.extract("This paragraph has no employment details.") == []

    def test_deduplication(self):
        """Same employer mentioned twice should be deduplicated."""
        text = "Employer: Acme Corp\nThe employer is Acme Corp."
        results = self.ext.extract(text)
        employers = [r for r in results if r.field == "employer" and r.value == "Acme Corp"]
        assert len(employers) == 1

    def test_compensation_dedup_hourly(self):
        """Hourly rate from pre and post context should be deduplicated."""
        text = "Hourly rate of $36.06. She was paid $36.06 per hour."
        results = self.ext.extract(text)
        comp = [r for r in results if r.field == "compensation" and r.compensation_rate == 36.06]
        assert len(comp) == 1
