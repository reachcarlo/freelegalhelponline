"""Tests for CaptionExtractor (V2.1b.2)."""

from employee_help.casefile.extractors.caption import (
    CaptionAttorney,
    CaptionExtractor,
    CaptionParty,
    CaptionResult,
)


class TestCaptionResult:
    def test_empty_result(self):
        r = CaptionResult()
        assert r.parties == []
        assert r.case_number is None
        assert r.court is None
        assert r.county is None
        assert r.department is None
        assert r.judge is None
        assert r.attorneys == []

    def test_frozen(self):
        import pytest

        r = CaptionResult()
        with pytest.raises(AttributeError):
            r.court = "Changed"  # type: ignore[misc]


class TestExtractCourt:
    def setup_method(self):
        self.ext = CaptionExtractor()

    def test_standard_court_header(self):
        text = """
        SUPERIOR COURT OF THE STATE OF CALIFORNIA
        COUNTY OF LOS ANGELES
        """
        result = self.ext.extract(text)
        assert result.court == "SUPERIOR COURT OF THE STATE OF CALIFORNIA"
        assert result.county == "LOS ANGELES"

    def test_court_without_state_of(self):
        text = """
        SUPERIOR COURT OF CALIFORNIA
        COUNTY OF SAN FRANCISCO
        """
        result = self.ext.extract(text)
        assert result.court == "SUPERIOR COURT OF CALIFORNIA"
        assert result.county == "SAN FRANCISCO"

    def test_court_with_comma_separator(self):
        text = """
        SUPERIOR COURT OF CALIFORNIA, COUNTY OF ORANGE
        """
        result = self.ext.extract(text)
        assert result.court == "SUPERIOR COURT OF CALIFORNIA"
        assert result.county == "ORANGE"

    def test_multi_word_county(self):
        text = """
        SUPERIOR COURT OF CALIFORNIA
        COUNTY OF SAN BERNARDINO
        """
        result = self.ext.extract(text)
        assert result.county == "SAN BERNARDINO"


class TestExtractCaseNumber:
    def setup_method(self):
        self.ext = CaptionExtractor()

    def test_standard_case_number(self):
        text = "Case No. 24STCV12345"
        result = self.ext.extract(text)
        assert result.case_number == "24STCV12345"

    def test_case_number_with_colon(self):
        text = "Case Number: BC-2025-67890"
        result = self.ext.extract(text)
        assert result.case_number == "BC-2025-67890"

    def test_no_prefix(self):
        text = "No. 24STCV99999"
        result = self.ext.extract(text)
        assert result.case_number == "24STCV99999"


class TestExtractDepartment:
    def setup_method(self):
        self.ext = CaptionExtractor()

    def test_department_number(self):
        text = "Dept. 7"
        result = self.ext.extract(text)
        assert result.department == "7"

    def test_department_spelled_out(self):
        text = "Department: 14"
        result = self.ext.extract(text)
        assert result.department == "14"


class TestExtractJudge:
    def setup_method(self):
        self.ext = CaptionExtractor()

    def test_honorable_judge(self):
        text = "Hon. Sarah Chen"
        result = self.ext.extract(text)
        assert result.judge == "Sarah Chen"

    def test_judge_with_middle_initial(self):
        text = "Judge Robert M. Garcia"
        result = self.ext.extract(text)
        assert result.judge == "Robert M. Garcia"


class TestExtractParties:
    def setup_method(self):
        self.ext = CaptionExtractor()

    def test_single_plaintiff_single_defendant(self):
        text = """
MARIA MARTINEZ,
    Plaintiff,
vs.
ACME CORPORATION, a California corporation,
    Defendant.
"""
        result = self.ext.extract(text)
        assert len(result.parties) == 2

        plaintiffs = [p for p in result.parties if p.role == "plaintiff"]
        assert len(plaintiffs) == 1
        assert plaintiffs[0].name == "MARIA MARTINEZ"
        assert plaintiffs[0].party_type == "individual"

        defendants = [p for p in result.parties if p.role == "defendant"]
        assert len(defendants) == 1
        assert "ACME CORPORATION" in defendants[0].name
        assert defendants[0].party_type == "entity"

    def test_doe_defendants(self):
        text = """
JOHN DOE,
    Plaintiff,
v.
BIG CORP INC. and DOES 1 through 50,
    Defendants.
"""
        result = self.ext.extract(text)
        does = [p for p in result.parties if p.party_type == "doe"]
        assert len(does) == 1
        assert does[0].count == 50
        assert does[0].role == "defendant"

    def test_multiple_defendants(self):
        text = """
ALICE JONES,
    Plaintiff,
vs.
WIDGET CO LLC; JOHN SMITH,
    Defendants.
"""
        result = self.ext.extract(text)
        defendants = [p for p in result.parties if p.role == "defendant"]
        assert len(defendants) == 2
        assert any("WIDGET CO LLC" in d.name for d in defendants)
        assert any("JOHN SMITH" in d.name for d in defendants)

    def test_entity_classification(self):
        """Entity indicators like Corp, LLC, Inc. should classify as entity."""
        text = """
JANE WORKER,
    Plaintiff,
vs.
MEGACORP HOLDINGS LLC,
    Defendant.
"""
        result = self.ext.extract(text)
        defendants = [p for p in result.parties if p.role == "defendant"]
        assert defendants[0].party_type == "entity"

    def test_no_caption_returns_empty(self):
        text = "This is just a regular paragraph of text with no caption."
        result = self.ext.extract(text)
        assert result.parties == []


class TestExtractAttorneys:
    def setup_method(self):
        self.ext = CaptionExtractor()

    def test_plaintiff_attorney_block(self):
        text = """
David Kim (SBN 298451)
Kim & Associates LLP
david@kimlaw.com
Attorneys for Plaintiff
"""
        result = self.ext.extract(text)
        assert len(result.attorneys) == 1
        atty = result.attorneys[0]
        assert atty.name == "David Kim"
        assert atty.side == "plaintiff"
        assert atty.bar_number == "298451"
        assert atty.firm == "Kim & Associates LLP"
        assert atty.email == "david@kimlaw.com"

    def test_defendant_attorney(self):
        text = """
Sarah Chen (State Bar No. 345678)
BigLaw Attorneys
Attorney for Defendant
"""
        result = self.ext.extract(text)
        assert len(result.attorneys) == 1
        atty = result.attorneys[0]
        assert atty.name == "Sarah Chen"
        assert atty.side == "defendant"
        assert atty.bar_number == "345678"

    def test_no_attorney_block(self):
        text = "Some text without any attorney information."
        result = self.ext.extract(text)
        assert result.attorneys == []


class TestFullCaption:
    def setup_method(self):
        self.ext = CaptionExtractor()

    def test_complete_california_complaint_caption(self):
        text = """
David Kim (SBN 298451)
Kim & Associates LLP
123 Main Street, Suite 400
Los Angeles, CA 90012
david@kimlaw.com
Attorneys for Plaintiff

SUPERIOR COURT OF THE STATE OF CALIFORNIA
COUNTY OF LOS ANGELES

MARIA MARTINEZ,
    Plaintiff,
vs.
ACME CORPORATION, a California corporation; and DOES 1 through 50, inclusive,
    Defendants.

Case No. 24STCV12345
Dept. 7
Hon. Sarah Chen

COMPLAINT FOR DAMAGES

GENERAL ALLEGATIONS

1. Plaintiff alleges that at all times relevant herein, Plaintiff
was employed by Defendant ACME CORPORATION as an Analyst.
"""
        result = self.ext.extract(text)

        # Court info
        assert result.court == "SUPERIOR COURT OF THE STATE OF CALIFORNIA"
        assert result.county == "LOS ANGELES"
        assert result.case_number == "24STCV12345"
        assert result.department == "7"
        assert result.judge == "Sarah Chen"

        # Parties
        plaintiffs = [p for p in result.parties if p.role == "plaintiff"]
        assert len(plaintiffs) == 1
        assert plaintiffs[0].name == "MARIA MARTINEZ"

        defendants = [p for p in result.parties if p.role == "defendant"]
        assert len(defendants) >= 2
        corp = [d for d in defendants if d.party_type == "entity"]
        assert len(corp) >= 1
        does = [d for d in defendants if d.party_type == "doe"]
        assert len(does) == 1
        assert does[0].count == 50

        # Attorney
        assert len(result.attorneys) >= 1
        atty = result.attorneys[0]
        assert atty.name == "David Kim"
        assert atty.side == "plaintiff"
        assert atty.bar_number == "298451"


class TestEdgeCases:
    def setup_method(self):
        self.ext = CaptionExtractor()

    def test_empty_text(self):
        result = self.ext.extract("")
        assert result == CaptionResult()

    def test_whitespace_only(self):
        result = self.ext.extract("   \n\t  ")
        assert result == CaptionResult()

    def test_petitioner_respondent(self):
        """Should handle petition-style captions (petitioner/respondent)."""
        text = """
JOHN WORKER,
    Petitioner,
vs.
UNEMPLOYMENT INSURANCE APPEALS BOARD,
    Respondent.
"""
        result = self.ext.extract(text)
        plaintiffs = [p for p in result.parties if p.role == "plaintiff"]
        defendants = [p for p in result.parties if p.role == "defendant"]
        assert len(plaintiffs) == 1
        assert len(defendants) == 1

    def test_v_without_s(self):
        """Should handle 'v.' as well as 'vs.'."""
        text = """
ALICE SMITH,
    Plaintiff,
v.
BOB JONES,
    Defendant.
"""
        result = self.ext.extract(text)
        assert len(result.parties) == 2
