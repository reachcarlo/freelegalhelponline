"""Tests for discovery PDF form filling.

Tests cover DISC-001, DISC-002, and DISC-020 generation
using PyPDFForm on real Judicial Council PDF templates.
"""

from __future__ import annotations

from datetime import date

import pytest
from pypdf import PdfReader
import io

from employee_help.discovery.models import (
    AttorneyInfo,
    CaseInfo,
    DiscoveryToolType,
    PartyInfo,
    PartyRole,
)
from employee_help.discovery.generator.pdf_filler import (
    fill_disc001,
    fill_disc002,
    fill_disc020,
    fill_discovery_pdf,
    _format_date,
    _format_attorney_block,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_attorney() -> AttorneyInfo:
    return AttorneyInfo(
        name="Maria Garcia",
        sbn="123456",
        address="100 Main Street, Suite 200",
        city_state_zip="Los Angeles, CA 90012",
        phone="(213) 555-1234",
        email="mgarcia@lawfirm.com",
        firm_name="Garcia Employment Law",
        fax="(213) 555-1235",
        attorney_for="Plaintiff Jane Doe",
    )


@pytest.fixture
def sample_case_info(sample_attorney: AttorneyInfo) -> CaseInfo:
    return CaseInfo(
        case_number="23STCV12345",
        court_county="Los Angeles",
        party_role=PartyRole.PLAINTIFF,
        plaintiffs=(PartyInfo(name="Jane Doe"),),
        defendants=(
            PartyInfo(name="Acme Corp", is_entity=True, entity_type="corporation"),
        ),
        attorney=sample_attorney,
        trial_date=date(2026, 9, 15),
        set_number=1,
    )


@pytest.fixture
def defendant_case_info(sample_attorney: AttorneyInfo) -> CaseInfo:
    """Case where the user is the defendant."""
    return CaseInfo(
        case_number="23STCV12345",
        court_county="Los Angeles",
        party_role=PartyRole.DEFENDANT,
        plaintiffs=(PartyInfo(name="John Smith"),),
        defendants=(
            PartyInfo(name="BigCo Inc", is_entity=True, entity_type="corporation"),
        ),
        attorney=AttorneyInfo(
            name="Robert Chen",
            sbn="654321",
            address="200 Corporate Plaza",
            city_state_zip="Los Angeles, CA 90071",
            phone="(213) 555-9999",
            email="rchen@defense.com",
            firm_name="Chen & Associates",
            attorney_for="Defendant BigCo Inc",
        ),
        set_number=2,
    )


# ---------------------------------------------------------------------------
# Helper tests
# ---------------------------------------------------------------------------


class TestFormatDate:
    def test_valid_date(self):
        assert _format_date(date(2026, 3, 15)) == "03/15/2026"

    def test_none_date(self):
        assert _format_date(None) == ""


class TestFormatAttorneyBlock:
    def test_attorney_block(self, sample_case_info: CaseInfo):
        block = _format_attorney_block(sample_case_info)
        assert "Maria Garcia (SBN 123456)" in block
        assert "Garcia Employment Law" in block
        assert "100 Main Street, Suite 200" in block
        assert "Los Angeles, CA 90012" in block

    def test_pro_per_block(self, sample_case_info: CaseInfo):
        pro_per_atty = AttorneyInfo(
            name="Jane Doe",
            sbn="",
            address="456 Oak Ave",
            city_state_zip="San Diego, CA 92101",
            phone="(619) 555-0000",
            email="jane@email.com",
            is_pro_per=True,
        )
        case_info = CaseInfo(
            case_number="23STCV99999",
            court_county="San Diego",
            party_role=PartyRole.PLAINTIFF,
            plaintiffs=(PartyInfo(name="Jane Doe"),),
            defendants=(PartyInfo(name="BadCo LLC"),),
            attorney=pro_per_atty,
        )
        block = _format_attorney_block(case_info)
        assert "Jane Doe, In Pro Per" in block
        assert "SBN" not in block


# ---------------------------------------------------------------------------
# DISC-001 tests
# ---------------------------------------------------------------------------


class TestFillDisc001:
    def test_returns_valid_pdf_bytes(self, sample_case_info: CaseInfo):
        result = fill_disc001(sample_case_info, ["1.1", "2.1"])
        assert isinstance(result, bytes)
        assert len(result) > 0
        # Verify it's a valid PDF
        assert result[:5] == b"%PDF-"

    def test_case_number_filled(self, sample_case_info: CaseInfo):
        result = fill_disc001(sample_case_info, ["1.1"])
        reader = PdfReader(io.BytesIO(result))
        fields = reader.get_fields()
        # Find the case number field by its full path
        case_number_val = None
        for name, field in fields.items():
            if "CaseNumber" in name and field.get("/V"):
                case_number_val = str(field["/V"])
                break
        assert case_number_val == "23STCV12345"

    def test_multiple_sections_checked(self, sample_case_info: CaseInfo):
        sections = ["1.1", "2.1", "6.1", "6.2", "8.1", "15.1"]
        result = fill_disc001(sample_case_info, sections)
        assert isinstance(result, bytes)
        assert len(result) > 200_000  # DISC-001 is ~270KB

    def test_no_sections_selected(self, sample_case_info: CaseInfo):
        """Even with no sections, header is still filled."""
        result = fill_disc001(sample_case_info, [])
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_all_employment_sections(self, sample_case_info: CaseInfo):
        """Selecting all employment-relevant sections produces valid PDF."""
        from employee_help.discovery.generator.field_mapping import DISC001_EMPLOYMENT_SECTIONS
        result = fill_disc001(
            sample_case_info,
            sorted(DISC001_EMPLOYMENT_SECTIONS),
        )
        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"

    def test_custom_definitions(self, sample_case_info: CaseInfo):
        result = fill_disc001(
            sample_case_info,
            ["1.1"],
            custom_definitions="INCIDENT means the wrongful termination of Plaintiff on or about January 15, 2025.",
        )
        assert isinstance(result, bytes)

    def test_defendant_side(self, defendant_case_info: CaseInfo):
        """Defendant generating FROGs — asking/answering parties swap."""
        result = fill_disc001(defendant_case_info, ["1.1", "15.1"])
        reader = PdfReader(io.BytesIO(result))
        fields = reader.get_fields()
        # The asking party should be the defendant (BigCo Inc)
        asking_val = None
        for name, field in fields.items():
            if "TextField5" in name and field.get("/V"):
                asking_val = str(field["/V"])
                break
        assert asking_val == "BigCo Inc"

    def test_invalid_section_ignored(self, sample_case_info: CaseInfo):
        """Unknown section numbers are silently ignored."""
        result = fill_disc001(sample_case_info, ["1.1", "99.99"])
        assert isinstance(result, bytes)


# ---------------------------------------------------------------------------
# DISC-002 tests
# ---------------------------------------------------------------------------


class TestFillDisc002:
    def test_returns_valid_pdf_bytes(self, sample_case_info: CaseInfo):
        result = fill_disc002(sample_case_info, ["200.1", "201.1"])
        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"

    def test_employment_sections(self, sample_case_info: CaseInfo):
        sections = [
            "200.1", "200.3", "200.4",
            "201.1", "201.3", "201.4",
            "202.1", "202.2",
            "210.1", "210.2", "210.3", "210.4",
            "212.1", "212.2", "212.3",
            "216.1",
        ]
        result = fill_disc002(sample_case_info, sections)
        assert isinstance(result, bytes)
        assert len(result) > 100_000

    def test_adverse_actions_text(self, sample_case_info: CaseInfo):
        result = fill_disc002(
            sample_case_info,
            ["201.3"],
            adverse_actions=["termination", "demotion", "pay reduction"],
        )
        assert isinstance(result, bytes)

    def test_all_sections(self, sample_case_info: CaseInfo):
        """Selecting every section produces valid PDF."""
        from employee_help.discovery.generator.field_mapping import DISC002_SECTION_FIELDS
        result = fill_disc002(
            sample_case_info,
            list(DISC002_SECTION_FIELDS.keys()),
        )
        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"

    def test_no_sections_selected(self, sample_case_info: CaseInfo):
        result = fill_disc002(sample_case_info, [])
        assert isinstance(result, bytes)

    def test_defendant_filling(self, defendant_case_info: CaseInfo):
        result = fill_disc002(defendant_case_info, ["200.1"])
        assert isinstance(result, bytes)


# ---------------------------------------------------------------------------
# DISC-020 tests
# ---------------------------------------------------------------------------


class TestFillDisc020:
    def test_returns_valid_pdf_bytes(self, sample_case_info: CaseInfo):
        result = fill_disc020(sample_case_info)
        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"

    def test_truth_of_facts(self, sample_case_info: CaseInfo):
        result = fill_disc020(
            sample_case_info,
            truth_of_facts=True,
            facts_text="1. Plaintiff was employed by Defendant from January 2020 to January 2025.",
        )
        assert isinstance(result, bytes)

    def test_genuineness_of_documents(self, sample_case_info: CaseInfo):
        result = fill_disc020(
            sample_case_info,
            truth_of_facts=False,
            genuineness_of_documents=True,
            docs_text="1. Plaintiff's employment agreement dated January 15, 2020.",
        )
        assert isinstance(result, bytes)

    def test_both_types(self, sample_case_info: CaseInfo):
        result = fill_disc020(
            sample_case_info,
            truth_of_facts=True,
            genuineness_of_documents=True,
            facts_text="1. Plaintiff was employed by Defendant.",
            docs_text="1. Termination letter dated January 15, 2025.",
        )
        assert isinstance(result, bytes)

    def test_continued_on_attachment(self, sample_case_info: CaseInfo):
        result = fill_disc020(
            sample_case_info,
            truth_of_facts=True,
            facts_continued=True,
        )
        assert isinstance(result, bytes)

    def test_court_info_filled(self, sample_case_info: CaseInfo):
        case_with_court = CaseInfo(
            case_number="23STCV12345",
            court_county="Los Angeles",
            party_role=PartyRole.PLAINTIFF,
            plaintiffs=(PartyInfo(name="Jane Doe"),),
            defendants=(PartyInfo(name="Acme Corp"),),
            attorney=sample_case_info.attorney,
            court_branch="Stanley Mosk Courthouse",
            court_address="111 N. Hill Street",
            court_city_zip="Los Angeles, CA 90012",
        )
        result = fill_disc020(case_with_court)
        assert isinstance(result, bytes)


# ---------------------------------------------------------------------------
# Dispatcher tests
# ---------------------------------------------------------------------------


class TestFillDiscoveryPdf:
    def test_dispatch_frogs_general(self, sample_case_info: CaseInfo):
        result = fill_discovery_pdf(
            DiscoveryToolType.FROGS_GENERAL,
            sample_case_info,
            ["1.1", "2.1"],
        )
        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"

    def test_dispatch_frogs_employment(self, sample_case_info: CaseInfo):
        result = fill_discovery_pdf(
            DiscoveryToolType.FROGS_EMPLOYMENT,
            sample_case_info,
            ["200.1", "201.1"],
        )
        assert isinstance(result, bytes)

    def test_dispatch_rfas(self, sample_case_info: CaseInfo):
        result = fill_discovery_pdf(
            DiscoveryToolType.RFAS,
            sample_case_info,
            [],
            truth_of_facts=True,
        )
        assert isinstance(result, bytes)

    def test_dispatch_srogs_raises(self, sample_case_info: CaseInfo):
        with pytest.raises(ValueError, match="does not use PDF"):
            fill_discovery_pdf(
                DiscoveryToolType.SROGS,
                sample_case_info,
                [],
            )

    def test_dispatch_rfpds_raises(self, sample_case_info: CaseInfo):
        with pytest.raises(ValueError, match="does not use PDF"):
            fill_discovery_pdf(
                DiscoveryToolType.RFPDS,
                sample_case_info,
                [],
            )
