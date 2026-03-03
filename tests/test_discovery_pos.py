"""Tests for Proof of Service DOCX generation.

Tests cover POS generation using docxtpl on California pleading paper,
including all service methods and the API endpoint.
"""

from __future__ import annotations

import io
import zipfile
from datetime import date

import pytest

from employee_help.discovery.generator.pos_builder import (
    SERVICE_METHOD_DESCRIPTIONS,
    build_proof_of_service,
)
from employee_help.discovery.models import (
    AttorneyInfo,
    CaseInfo,
    PartyInfo,
    PartyRole,
    ServiceMethod,
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
        set_number=1,
    )


@pytest.fixture
def sample_pos_kwargs() -> dict:
    return {
        "server_name": "John Process Server",
        "server_address": "456 Service Blvd, Los Angeles, CA 90015",
        "served_party_name": "Acme Corp (through its agent for service of process)",
        "served_party_address": "789 Corporate Ave, Los Angeles, CA 90071",
        "service_method": ServiceMethod.MAIL_IN_STATE,
        "service_date": date(2026, 3, 1),
        "documents_served": [
            "Special Interrogatories, Set One",
            "Requests for Production of Documents, Set One",
        ],
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_valid_docx(data: bytes) -> bool:
    """Verify bytes are a valid DOCX file (which is a ZIP)."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            return "[Content_Types].xml" in zf.namelist()
    except zipfile.BadZipFile:
        return False


def _get_doc_xml(data: bytes) -> str:
    """Extract word/document.xml text from a DOCX."""
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        return zf.read("word/document.xml").decode("utf-8")


# ---------------------------------------------------------------------------
# POS generation tests
# ---------------------------------------------------------------------------


class TestBuildProofOfService:
    def test_returns_valid_docx(
        self,
        sample_case_info: CaseInfo,
        sample_pos_kwargs: dict,
    ):
        result = build_proof_of_service(sample_case_info, **sample_pos_kwargs)
        assert isinstance(result, bytes)
        assert _is_valid_docx(result)

    def test_contains_proof_of_service_heading(
        self,
        sample_case_info: CaseInfo,
        sample_pos_kwargs: dict,
    ):
        result = build_proof_of_service(sample_case_info, **sample_pos_kwargs)
        doc_xml = _get_doc_xml(result)
        assert "PROOF OF SERVICE" in doc_xml

    def test_contains_server_name(
        self,
        sample_case_info: CaseInfo,
        sample_pos_kwargs: dict,
    ):
        result = build_proof_of_service(sample_case_info, **sample_pos_kwargs)
        doc_xml = _get_doc_xml(result)
        assert "John Process Server" in doc_xml

    def test_contains_served_party(
        self,
        sample_case_info: CaseInfo,
        sample_pos_kwargs: dict,
    ):
        result = build_proof_of_service(sample_case_info, **sample_pos_kwargs)
        doc_xml = _get_doc_xml(result)
        assert "Acme Corp" in doc_xml
        assert "789 Corporate Ave" in doc_xml

    def test_contains_documents_served(
        self,
        sample_case_info: CaseInfo,
        sample_pos_kwargs: dict,
    ):
        result = build_proof_of_service(sample_case_info, **sample_pos_kwargs)
        doc_xml = _get_doc_xml(result)
        assert "Special Interrogatories, Set One" in doc_xml
        assert "Requests for Production of Documents, Set One" in doc_xml

    def test_contains_service_date(
        self,
        sample_case_info: CaseInfo,
        sample_pos_kwargs: dict,
    ):
        result = build_proof_of_service(sample_case_info, **sample_pos_kwargs)
        doc_xml = _get_doc_xml(result)
        assert "March 01, 2026" in doc_xml

    def test_contains_case_number(
        self,
        sample_case_info: CaseInfo,
        sample_pos_kwargs: dict,
    ):
        result = build_proof_of_service(sample_case_info, **sample_pos_kwargs)
        doc_xml = _get_doc_xml(result)
        assert "23STCV12345" in doc_xml

    def test_contains_penalty_of_perjury(
        self,
        sample_case_info: CaseInfo,
        sample_pos_kwargs: dict,
    ):
        result = build_proof_of_service(sample_case_info, **sample_pos_kwargs)
        doc_xml = _get_doc_xml(result)
        assert "penalty of perjury" in doc_xml

    def test_contains_server_address(
        self,
        sample_case_info: CaseInfo,
        sample_pos_kwargs: dict,
    ):
        result = build_proof_of_service(sample_case_info, **sample_pos_kwargs)
        doc_xml = _get_doc_xml(result)
        assert "456 Service Blvd" in doc_xml


class TestServiceMethods:
    @pytest.mark.parametrize("method", list(ServiceMethod))
    def test_all_service_methods_produce_valid_docx(
        self,
        sample_case_info: CaseInfo,
        sample_pos_kwargs: dict,
        method: ServiceMethod,
    ):
        sample_pos_kwargs["service_method"] = method
        result = build_proof_of_service(sample_case_info, **sample_pos_kwargs)
        assert _is_valid_docx(result)

    def test_personal_service_description(
        self,
        sample_case_info: CaseInfo,
        sample_pos_kwargs: dict,
    ):
        sample_pos_kwargs["service_method"] = ServiceMethod.PERSONAL
        result = build_proof_of_service(sample_case_info, **sample_pos_kwargs)
        doc_xml = _get_doc_xml(result)
        assert "personally delivering" in doc_xml

    def test_electronic_service_description(
        self,
        sample_case_info: CaseInfo,
        sample_pos_kwargs: dict,
    ):
        sample_pos_kwargs["service_method"] = ServiceMethod.ELECTRONIC
        result = build_proof_of_service(sample_case_info, **sample_pos_kwargs)
        doc_xml = _get_doc_xml(result)
        assert "electronic service" in doc_xml
        assert "1010.6" in doc_xml

    def test_mail_in_state_description(
        self,
        sample_case_info: CaseInfo,
        sample_pos_kwargs: dict,
    ):
        sample_pos_kwargs["service_method"] = ServiceMethod.MAIL_IN_STATE
        result = build_proof_of_service(sample_case_info, **sample_pos_kwargs)
        doc_xml = _get_doc_xml(result)
        assert "United States mail" in doc_xml
        assert "1013" in doc_xml


class TestServiceMethodDescriptions:
    def test_all_methods_have_descriptions(self):
        for method in ServiceMethod:
            assert method in SERVICE_METHOD_DESCRIPTIONS
            assert len(SERVICE_METHOD_DESCRIPTIONS[method]) > 20


class TestPOSSingleDocument:
    def test_single_document_served(
        self,
        sample_case_info: CaseInfo,
        sample_pos_kwargs: dict,
    ):
        sample_pos_kwargs["documents_served"] = [
            "Request for Admissions, Set One"
        ]
        result = build_proof_of_service(sample_case_info, **sample_pos_kwargs)
        assert _is_valid_docx(result)
        doc_xml = _get_doc_xml(result)
        assert "Request for Admissions, Set One" in doc_xml
