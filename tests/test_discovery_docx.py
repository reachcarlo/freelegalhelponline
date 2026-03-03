"""Tests for discovery DOCX pleading paper generation.

Tests cover SROGs, RFPDs, and RFAs generation using docxtpl
on California 28-line pleading paper.
"""

from __future__ import annotations

import io
import zipfile
from datetime import date
from pathlib import Path

import pytest

from employee_help.discovery.models import (
    AttorneyInfo,
    CaseInfo,
    DiscoveryRequest,
    DiscoveryToolType,
    PartyInfo,
    PartyRole,
)
from employee_help.discovery.generator.docx_builder import (
    _build_declaration_context,
    build_discovery_docx,
    build_rfas,
    build_rfpds,
    build_srogs,
    _format_rfa_requests,
    _format_rfpd_requests,
    _format_srog_requests,
)
from employee_help.discovery.generator.pleading_template import (
    create_pleading_template,
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
def sample_srog_requests() -> list[DiscoveryRequest]:
    return [
        DiscoveryRequest(
            id="srog_001",
            text=(
                "State the name, job title, and job duties of each PERSON who "
                "participated in the decision to take any ADVERSE EMPLOYMENT "
                "ACTION against EMPLOYEE."
            ),
            category="adverse_action",
            order=1,
        ),
        DiscoveryRequest(
            id="srog_002",
            text=(
                "IDENTIFY all DOCUMENTS that YOU reviewed, considered, or relied "
                "upon in making the decision to take any ADVERSE EMPLOYMENT "
                "ACTION against EMPLOYEE."
            ),
            category="adverse_action",
            order=2,
        ),
        DiscoveryRequest(
            id="srog_003",
            text=(
                "State the specific reason(s) for each ADVERSE EMPLOYMENT "
                "ACTION taken against EMPLOYEE."
            ),
            category="adverse_action",
            order=3,
        ),
    ]


@pytest.fixture
def sample_rfpd_requests() -> list[DiscoveryRequest]:
    return [
        DiscoveryRequest(
            id="rfpd_001",
            text=(
                "All DOCUMENTS constituting, evidencing, or RELATING TO the "
                "EMPLOYEE's personnel file, including but not limited to performance "
                "evaluations, disciplinary records, and commendations."
            ),
            category="personnel_file",
            order=1,
        ),
        DiscoveryRequest(
            id="rfpd_002",
            text=(
                "All DOCUMENTS RELATING TO any investigation of any complaint "
                "made by EMPLOYEE during the course of EMPLOYMENT."
            ),
            category="complaints",
            order=2,
        ),
    ]


@pytest.fixture
def sample_rfa_requests() -> list[DiscoveryRequest]:
    return [
        DiscoveryRequest(
            id="rfa_001",
            text=(
                "Admit that EMPLOYEE was employed by EMPLOYER from "
                "January 15, 2020 through January 15, 2025."
            ),
            category="employment_dates",
            order=1,
        ),
        DiscoveryRequest(
            id="rfa_002",
            text=(
                "Admit that EMPLOYEE's TERMINATION was not based on "
                "poor job performance."
            ),
            category="termination",
            order=2,
        ),
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_valid_docx(data: bytes) -> bool:
    """Verify bytes are a valid DOCX file (which is a ZIP)."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            # DOCX must contain [Content_Types].xml
            return "[Content_Types].xml" in zf.namelist()
    except zipfile.BadZipFile:
        return False


# ---------------------------------------------------------------------------
# Template creation tests
# ---------------------------------------------------------------------------


class TestPleadingTemplate:
    def test_creates_valid_docx(self, tmp_path: Path):
        output = tmp_path / "test_template.docx"
        result = create_pleading_template(output)
        assert result == output
        assert output.exists()
        assert _is_valid_docx(output.read_bytes())

    def test_creates_without_caption(self, tmp_path: Path):
        output = tmp_path / "no_caption.docx"
        result = create_pleading_template(output, include_caption=False)
        assert result == output
        assert output.exists()
        assert _is_valid_docx(output.read_bytes())

    def test_template_has_content(self, tmp_path: Path):
        output = tmp_path / "template.docx"
        create_pleading_template(output)
        data = output.read_bytes()
        # Check that Jinja2 tags are present in the document
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            doc_xml = zf.read("word/document.xml").decode("utf-8")
            assert "document_title" in doc_xml
            assert "requests" in doc_xml


# ---------------------------------------------------------------------------
# Request formatting tests
# ---------------------------------------------------------------------------


class TestFormatRequests:
    def test_srog_labels(self, sample_srog_requests: list[DiscoveryRequest]):
        formatted = _format_srog_requests(sample_srog_requests)
        assert len(formatted) == 3
        assert formatted[0]["label"] == "SPECIAL INTERROGATORY NO. 1:"
        assert formatted[2]["label"] == "SPECIAL INTERROGATORY NO. 3:"
        assert "ADVERSE EMPLOYMENT" in formatted[0]["text"]

    def test_rfpd_labels(self, sample_rfpd_requests: list[DiscoveryRequest]):
        formatted = _format_rfpd_requests(sample_rfpd_requests)
        assert len(formatted) == 2
        assert formatted[0]["label"] == "REQUEST FOR PRODUCTION NO. 1:"
        assert "personnel file" in formatted[0]["text"]

    def test_rfa_labels(self, sample_rfa_requests: list[DiscoveryRequest]):
        formatted = _format_rfa_requests(sample_rfa_requests)
        assert len(formatted) == 2
        assert formatted[0]["label"] == "REQUEST FOR ADMISSION NO. 1:"

    def test_empty_requests(self):
        assert _format_srog_requests([]) == []
        assert _format_rfpd_requests([]) == []
        assert _format_rfa_requests([]) == []


# ---------------------------------------------------------------------------
# SROG tests
# ---------------------------------------------------------------------------


class TestBuildSrogs:
    def test_returns_valid_docx(
        self,
        sample_case_info: CaseInfo,
        sample_srog_requests: list[DiscoveryRequest],
    ):
        result = build_srogs(sample_case_info, sample_srog_requests)
        assert isinstance(result, bytes)
        assert _is_valid_docx(result)

    def test_contains_interrogatory_text(
        self,
        sample_case_info: CaseInfo,
        sample_srog_requests: list[DiscoveryRequest],
    ):
        result = build_srogs(sample_case_info, sample_srog_requests)
        with zipfile.ZipFile(io.BytesIO(result)) as zf:
            doc_xml = zf.read("word/document.xml").decode("utf-8")
            assert "SPECIAL INTERROGATORY NO. 1" in doc_xml
            assert "ADVERSE EMPLOYMENT" in doc_xml

    def test_includes_definitions_by_default(
        self,
        sample_case_info: CaseInfo,
        sample_srog_requests: list[DiscoveryRequest],
    ):
        result = build_srogs(sample_case_info, sample_srog_requests)
        with zipfile.ZipFile(io.BytesIO(result)) as zf:
            doc_xml = zf.read("word/document.xml").decode("utf-8")
            assert "DOCUMENT" in doc_xml
            assert "COMMUNICATION" in doc_xml

    def test_no_definitions(
        self,
        sample_case_info: CaseInfo,
        sample_srog_requests: list[DiscoveryRequest],
    ):
        result = build_srogs(
            sample_case_info,
            sample_srog_requests,
            include_definitions=False,
        )
        assert _is_valid_docx(result)

    def test_contains_case_number(
        self,
        sample_case_info: CaseInfo,
        sample_srog_requests: list[DiscoveryRequest],
    ):
        result = build_srogs(sample_case_info, sample_srog_requests)
        with zipfile.ZipFile(io.BytesIO(result)) as zf:
            doc_xml = zf.read("word/document.xml").decode("utf-8")
            assert "23STCV12345" in doc_xml

    def test_empty_requests(self, sample_case_info: CaseInfo):
        result = build_srogs(sample_case_info, [])
        assert _is_valid_docx(result)


# ---------------------------------------------------------------------------
# RFPD tests
# ---------------------------------------------------------------------------


class TestBuildRfpds:
    def test_returns_valid_docx(
        self,
        sample_case_info: CaseInfo,
        sample_rfpd_requests: list[DiscoveryRequest],
    ):
        result = build_rfpds(sample_case_info, sample_rfpd_requests)
        assert isinstance(result, bytes)
        assert _is_valid_docx(result)

    def test_includes_production_instructions(
        self,
        sample_case_info: CaseInfo,
        sample_rfpd_requests: list[DiscoveryRequest],
    ):
        result = build_rfpds(sample_case_info, sample_rfpd_requests)
        with zipfile.ZipFile(io.BytesIO(result)) as zf:
            doc_xml = zf.read("word/document.xml").decode("utf-8")
            # Production instructions should be included by default for RFPDs
            assert "possession, custody, or control" in doc_xml

    def test_no_production_instructions(
        self,
        sample_case_info: CaseInfo,
        sample_rfpd_requests: list[DiscoveryRequest],
    ):
        result = build_rfpds(
            sample_case_info,
            sample_rfpd_requests,
            include_production_instructions=False,
        )
        assert _is_valid_docx(result)

    def test_contains_request_text(
        self,
        sample_case_info: CaseInfo,
        sample_rfpd_requests: list[DiscoveryRequest],
    ):
        result = build_rfpds(sample_case_info, sample_rfpd_requests)
        with zipfile.ZipFile(io.BytesIO(result)) as zf:
            doc_xml = zf.read("word/document.xml").decode("utf-8")
            assert "REQUEST FOR PRODUCTION NO. 1" in doc_xml
            assert "personnel file" in doc_xml


# ---------------------------------------------------------------------------
# RFA tests
# ---------------------------------------------------------------------------


class TestBuildRfas:
    def test_returns_valid_docx(
        self,
        sample_case_info: CaseInfo,
        sample_rfa_requests: list[DiscoveryRequest],
    ):
        result = build_rfas(sample_case_info, sample_rfa_requests)
        assert isinstance(result, bytes)
        assert _is_valid_docx(result)

    def test_contains_rfa_text(
        self,
        sample_case_info: CaseInfo,
        sample_rfa_requests: list[DiscoveryRequest],
    ):
        result = build_rfas(sample_case_info, sample_rfa_requests)
        with zipfile.ZipFile(io.BytesIO(result)) as zf:
            doc_xml = zf.read("word/document.xml").decode("utf-8")
            assert "REQUEST FOR ADMISSION NO. 1" in doc_xml


# ---------------------------------------------------------------------------
# Dispatcher tests
# ---------------------------------------------------------------------------


class TestBuildDiscoveryDocx:
    def test_dispatch_srogs(
        self,
        sample_case_info: CaseInfo,
        sample_srog_requests: list[DiscoveryRequest],
    ):
        result = build_discovery_docx(
            DiscoveryToolType.SROGS,
            sample_case_info,
            sample_srog_requests,
        )
        assert _is_valid_docx(result)

    def test_dispatch_rfpds(
        self,
        sample_case_info: CaseInfo,
        sample_rfpd_requests: list[DiscoveryRequest],
    ):
        result = build_discovery_docx(
            DiscoveryToolType.RFPDS,
            sample_case_info,
            sample_rfpd_requests,
        )
        assert _is_valid_docx(result)

    def test_dispatch_rfas(
        self,
        sample_case_info: CaseInfo,
        sample_rfa_requests: list[DiscoveryRequest],
    ):
        result = build_discovery_docx(
            DiscoveryToolType.RFAS,
            sample_case_info,
            sample_rfa_requests,
        )
        assert _is_valid_docx(result)

    def test_dispatch_frogs_raises(self, sample_case_info: CaseInfo):
        with pytest.raises(ValueError, match="does not use DOCX"):
            build_discovery_docx(
                DiscoveryToolType.FROGS_GENERAL,
                sample_case_info,
                [],
            )

    def test_dispatch_frogs_employment_raises(self, sample_case_info: CaseInfo):
        with pytest.raises(ValueError, match="does not use DOCX"):
            build_discovery_docx(
                DiscoveryToolType.FROGS_EMPLOYMENT,
                sample_case_info,
                [],
            )

    def test_custom_definitions(
        self,
        sample_case_info: CaseInfo,
        sample_srog_requests: list[DiscoveryRequest],
    ):
        custom_defs = {
            "DOCUMENT": "A custom definition of document.",
            "INCIDENT": "The events of January 15, 2025.",
        }
        result = build_discovery_docx(
            DiscoveryToolType.SROGS,
            sample_case_info,
            sample_srog_requests,
            custom_definitions=custom_defs,
        )
        assert _is_valid_docx(result)
        with zipfile.ZipFile(io.BytesIO(result)) as zf:
            doc_xml = zf.read("word/document.xml").decode("utf-8")
            assert "custom definition of document" in doc_xml

    def test_defendant_generates_correctly(
        self,
        sample_srog_requests: list[DiscoveryRequest],
    ):
        """Defendant side produces correct party designations."""
        def_attorney = AttorneyInfo(
            name="Robert Chen",
            sbn="654321",
            address="200 Corporate Plaza",
            city_state_zip="Los Angeles, CA 90071",
            phone="(213) 555-9999",
            email="rchen@defense.com",
            firm_name="Chen & Associates",
            attorney_for="Defendant BigCo Inc",
        )
        def_case = CaseInfo(
            case_number="23STCV12345",
            court_county="Los Angeles",
            party_role=PartyRole.DEFENDANT,
            plaintiffs=(PartyInfo(name="John Smith"),),
            defendants=(PartyInfo(name="BigCo Inc", is_entity=True),),
            attorney=def_attorney,
            set_number=1,
        )
        result = build_discovery_docx(
            DiscoveryToolType.SROGS,
            def_case,
            sample_srog_requests,
        )
        assert _is_valid_docx(result)
        with zipfile.ZipFile(io.BytesIO(result)) as zf:
            doc_xml = zf.read("word/document.xml").decode("utf-8")
            # Defendant is the propounding party
            assert "DEFENDANT BIGCO INC" in doc_xml


# ---------------------------------------------------------------------------
# Declaration of Necessity tests
# ---------------------------------------------------------------------------


def _make_requests(n: int, prefix: str = "srog") -> list[DiscoveryRequest]:
    """Create n selected DiscoveryRequest objects."""
    return [
        DiscoveryRequest(
            id=f"{prefix}_{i:03d}",
            text=f"Request number {i} text.",
            category="test",
            is_selected=True,
            order=i,
        )
        for i in range(1, n + 1)
    ]


class TestDeclarationContext:
    def test_srogs_under_limit_no_declaration(
        self, sample_case_info: CaseInfo,
    ):
        requests = _make_requests(35)
        result = _build_declaration_context(
            DiscoveryToolType.SROGS, sample_case_info, requests,
        )
        assert result is None

    def test_srogs_over_limit_has_declaration(
        self, sample_case_info: CaseInfo,
    ):
        requests = _make_requests(36)
        result = _build_declaration_context(
            DiscoveryToolType.SROGS, sample_case_info, requests,
        )
        assert result is not None
        assert result["ccp_section"] == "2030.050"
        assert result["limit_section"] == "2030.030"
        assert result["request_count"] == 36
        assert result["request_type_plural"] == "specially prepared interrogatories"
        assert result["declarant_name"] == "Maria Garcia"

    def test_rfas_under_limit_no_declaration(
        self, sample_case_info: CaseInfo,
    ):
        requests = _make_requests(35, prefix="rfa")
        result = _build_declaration_context(
            DiscoveryToolType.RFAS, sample_case_info, requests,
        )
        assert result is None

    def test_rfas_over_limit_has_declaration(
        self, sample_case_info: CaseInfo,
    ):
        requests = _make_requests(36, prefix="rfa")
        result = _build_declaration_context(
            DiscoveryToolType.RFAS, sample_case_info, requests,
        )
        assert result is not None
        assert result["ccp_section"] == "2033.050"
        assert result["request_count"] == 36
        assert result["request_type_plural"] == "requests for admission"

    def test_rfpds_never_have_declaration(
        self, sample_case_info: CaseInfo,
    ):
        requests = _make_requests(100, prefix="rfpd")
        result = _build_declaration_context(
            DiscoveryToolType.RFPDS, sample_case_info, requests,
        )
        assert result is None


class TestDeclarationInDocx:
    def test_srogs_over_limit_includes_declaration_page(
        self, sample_case_info: CaseInfo,
    ):
        requests = _make_requests(36)
        result = build_srogs(sample_case_info, requests)
        assert _is_valid_docx(result)
        with zipfile.ZipFile(io.BytesIO(result)) as zf:
            doc_xml = zf.read("word/document.xml").decode("utf-8")
            assert "DECLARATION FOR ADDITIONAL DISCOVERY" in doc_xml
            assert "2030.050" in doc_xml
            assert "2030.030" in doc_xml
            assert "36" in doc_xml
            assert "specially prepared interrogatories" in doc_xml
            assert "penalty of perjury" in doc_xml

    def test_srogs_under_limit_no_declaration_page(
        self, sample_case_info: CaseInfo,
    ):
        requests = _make_requests(10)
        result = build_srogs(sample_case_info, requests)
        assert _is_valid_docx(result)
        with zipfile.ZipFile(io.BytesIO(result)) as zf:
            doc_xml = zf.read("word/document.xml").decode("utf-8")
            assert "DECLARATION FOR ADDITIONAL DISCOVERY" not in doc_xml

    def test_rfas_over_limit_includes_declaration_page(
        self, sample_case_info: CaseInfo,
    ):
        requests = _make_requests(40, prefix="rfa")
        result = build_rfas(sample_case_info, requests)
        assert _is_valid_docx(result)
        with zipfile.ZipFile(io.BytesIO(result)) as zf:
            doc_xml = zf.read("word/document.xml").decode("utf-8")
            assert "DECLARATION FOR ADDITIONAL DISCOVERY" in doc_xml
            assert "2033.050" in doc_xml

    def test_rfpds_no_declaration_regardless_of_count(
        self, sample_case_info: CaseInfo,
    ):
        requests = _make_requests(100, prefix="rfpd")
        result = build_rfpds(sample_case_info, requests)
        assert _is_valid_docx(result)
        with zipfile.ZipFile(io.BytesIO(result)) as zf:
            doc_xml = zf.read("word/document.xml").decode("utf-8")
            assert "DECLARATION FOR ADDITIONAL DISCOVERY" not in doc_xml

    def test_declaration_includes_attorney_name(
        self, sample_case_info: CaseInfo,
    ):
        requests = _make_requests(36)
        result = build_srogs(sample_case_info, requests)
        with zipfile.ZipFile(io.BytesIO(result)) as zf:
            doc_xml = zf.read("word/document.xml").decode("utf-8")
            # Attorney name should appear in declaration section
            assert "Maria Garcia" in doc_xml
