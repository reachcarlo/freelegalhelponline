"""API integration tests for discovery endpoints.

Covers:
- POST /api/discovery/suggest (validation, happy path, all tool types)
- POST /api/discovery/generate (PDF, DOCX, validation, headers)
- GET /api/discovery/banks/{tool} (all 5 tools, 404 for invalid)
- GET /api/discovery/definitions
"""

from __future__ import annotations

import zipfile
from io import BytesIO

import pytest
from fastapi.testclient import TestClient


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

        # Reset discovery rate limit store to avoid 429s
        main_mod._discovery_rate_store.clear()

        yield TestClient(main_mod.app)


SAMPLE_CASE_INFO = {
    "case_number": "23STCV12345",
    "court_county": "Los Angeles",
    "party_role": "plaintiff",
    "plaintiffs": [{"name": "Jane Smith", "is_entity": False}],
    "defendants": [{"name": "Acme Corp", "is_entity": True, "entity_type": "corporation"}],
    "attorney": {
        "name": "John Doe",
        "sbn": "123456",
        "address": "123 Main St, Suite 100",
        "city_state_zip": "Los Angeles, CA 90012",
        "phone": "(213) 555-1234",
        "email": "john@example.com",
        "firm_name": "Doe Law Firm",
        "attorney_for": "Plaintiff Jane Smith",
    },
    "set_number": 1,
}


# ---------------------------------------------------------------------------
# POST /api/discovery/suggest
# ---------------------------------------------------------------------------


class TestSuggestEndpoint:
    def test_suggest_frogs_general(self, client):
        resp = client.post("/api/discovery/suggest", json={
            "claim_types": ["feha_discrimination"],
            "party_role": "plaintiff",
            "tool_type": "frogs_general",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["tool_type"] == "frogs_general"
        assert data["total_suggested"] > 0
        assert len(data["suggested_sections"]) > 0
        # 1.1 should always be suggested
        section_nums = [s["section_number"] for s in data["suggested_sections"]]
        assert "1.1" in section_nums

    def test_suggest_frogs_employment(self, client):
        resp = client.post("/api/discovery/suggest", json={
            "claim_types": ["feha_discrimination"],
            "party_role": "plaintiff",
            "tool_type": "frogs_employment",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["tool_type"] == "frogs_employment"
        assert data["total_suggested"] > 0
        # 200.1 is always included
        section_nums = [s["section_number"] for s in data["suggested_sections"]]
        assert "200.1" in section_nums

    def test_suggest_srogs(self, client):
        resp = client.post("/api/discovery/suggest", json={
            "claim_types": ["feha_discrimination"],
            "party_role": "plaintiff",
            "tool_type": "srogs",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["tool_type"] == "srogs"
        assert data["total_suggested"] > 0
        assert len(data["suggested_categories"]) > 0

    def test_suggest_rfpds(self, client):
        resp = client.post("/api/discovery/suggest", json={
            "claim_types": ["wage_theft"],
            "party_role": "plaintiff",
            "tool_type": "rfpds",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["suggested_categories"]) > 0
        cat_keys = [c["category"] for c in data["suggested_categories"]]
        assert "compensation_records" in cat_keys

    def test_suggest_rfas(self, client):
        resp = client.post("/api/discovery/suggest", json={
            "claim_types": ["feha_harassment"],
            "party_role": "defendant",
            "tool_type": "rfas",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["party_role"] == "defendant"
        assert data["total_suggested"] > 0

    def test_suggest_multiple_claims(self, client):
        resp = client.post("/api/discovery/suggest", json={
            "claim_types": ["feha_discrimination", "wage_theft"],
            "party_role": "plaintiff",
            "tool_type": "srogs",
        })
        assert resp.status_code == 200
        data = resp.json()
        # Multiple claims should produce more suggestions
        assert data["total_suggested"] > 0

    def test_suggest_invalid_tool_type(self, client):
        resp = client.post("/api/discovery/suggest", json={
            "claim_types": ["feha_discrimination"],
            "party_role": "plaintiff",
            "tool_type": "invalid_tool",
        })
        assert resp.status_code == 422

    def test_suggest_invalid_claim_type(self, client):
        resp = client.post("/api/discovery/suggest", json={
            "claim_types": ["not_a_claim"],
            "party_role": "plaintiff",
            "tool_type": "srogs",
        })
        assert resp.status_code == 422

    def test_suggest_invalid_party_role(self, client):
        resp = client.post("/api/discovery/suggest", json={
            "claim_types": ["feha_discrimination"],
            "party_role": "judge",
            "tool_type": "srogs",
        })
        assert resp.status_code == 422

    def test_suggest_empty_claims(self, client):
        resp = client.post("/api/discovery/suggest", json={
            "claim_types": [],
            "party_role": "plaintiff",
            "tool_type": "srogs",
        })
        assert resp.status_code == 422

    def test_suggest_with_rfas_flag(self, client):
        resp = client.post("/api/discovery/suggest", json={
            "claim_types": ["feha_discrimination"],
            "party_role": "plaintiff",
            "tool_type": "frogs_general",
            "has_rfas": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        section_nums = [s["section_number"] for s in data["suggested_sections"]]
        assert "17.1" in section_nums


# ---------------------------------------------------------------------------
# POST /api/discovery/generate
# ---------------------------------------------------------------------------


class TestGenerateEndpoint:
    def test_generate_disc001_pdf(self, client):
        resp = client.post("/api/discovery/generate", json={
            "tool_type": "frogs_general",
            "case_info": SAMPLE_CASE_INFO,
            "selected_sections": ["1.1", "2.1", "4.1", "6.1", "15.1"],
        })
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert "DISC-001" in resp.headers["content-disposition"]
        assert "23STCV12345" in resp.headers["content-disposition"]
        assert int(resp.headers["content-length"]) > 0
        # PDF magic bytes
        assert resp.content[:5] == b"%PDF-"

    def test_generate_disc002_pdf(self, client):
        resp = client.post("/api/discovery/generate", json={
            "tool_type": "frogs_employment",
            "case_info": SAMPLE_CASE_INFO,
            "selected_sections": ["200.1", "201.1", "202.1"],
            "adverse_actions": ["Termination", "Demotion"],
        })
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert "DISC-002" in resp.headers["content-disposition"]
        assert resp.content[:5] == b"%PDF-"

    def test_generate_srogs_docx(self, client):
        resp = client.post("/api/discovery/generate", json={
            "tool_type": "srogs",
            "case_info": SAMPLE_CASE_INFO,
            "selected_requests": [
                {"id": "srog_1", "text": "State the date of hire.", "category": "employment_relationship", "is_selected": True, "order": 1},
                {"id": "srog_2", "text": "Identify all supervisors.", "category": "employment_relationship", "is_selected": True, "order": 2},
            ],
        })
        assert resp.status_code == 200
        docx_ct = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert resp.headers["content-type"] == docx_ct
        assert "SROGs" in resp.headers["content-disposition"]
        # DOCX is a ZIP
        assert zipfile.is_zipfile(BytesIO(resp.content))

    def test_generate_rfpds_docx(self, client):
        resp = client.post("/api/discovery/generate", json={
            "tool_type": "rfpds",
            "case_info": SAMPLE_CASE_INFO,
            "selected_requests": [
                {"id": "rfpd_1", "text": "All personnel file documents.", "category": "personnel_file", "is_selected": True, "order": 1},
            ],
        })
        assert resp.status_code == 200
        assert "RFPDs" in resp.headers["content-disposition"]
        assert zipfile.is_zipfile(BytesIO(resp.content))

    def test_generate_rfas_docx(self, client):
        resp = client.post("/api/discovery/generate", json={
            "tool_type": "rfas",
            "case_info": SAMPLE_CASE_INFO,
            "selected_requests": [
                {"id": "rfa_1", "text": "Admit employee was employed.", "category": "employment_facts", "is_selected": True, "order": 1, "rfa_type": "fact"},
            ],
        })
        assert resp.status_code == 200
        assert "RFAs" in resp.headers["content-disposition"]

    def test_generate_invalid_tool_type(self, client):
        resp = client.post("/api/discovery/generate", json={
            "tool_type": "invalid",
            "case_info": SAMPLE_CASE_INFO,
            "selected_sections": ["1.1"],
        })
        assert resp.status_code == 422

    def test_generate_missing_sections_for_frogs(self, client):
        resp = client.post("/api/discovery/generate", json={
            "tool_type": "frogs_general",
            "case_info": SAMPLE_CASE_INFO,
            "selected_sections": [],
        })
        assert resp.status_code == 422

    def test_generate_missing_requests_for_srogs(self, client):
        resp = client.post("/api/discovery/generate", json={
            "tool_type": "srogs",
            "case_info": SAMPLE_CASE_INFO,
            "selected_requests": [],
        })
        assert resp.status_code == 422

    def test_generate_missing_case_info(self, client):
        resp = client.post("/api/discovery/generate", json={
            "tool_type": "srogs",
            "selected_requests": [
                {"id": "s1", "text": "Test", "category": "test", "is_selected": True, "order": 1},
            ],
        })
        assert resp.status_code == 422

    def test_generate_deselected_requests_filtered(self, client):
        resp = client.post("/api/discovery/generate", json={
            "tool_type": "srogs",
            "case_info": SAMPLE_CASE_INFO,
            "selected_requests": [
                {"id": "s1", "text": "Keep this.", "category": "test", "is_selected": True, "order": 1},
                {"id": "s2", "text": "Drop this.", "category": "test", "is_selected": False, "order": 2},
            ],
        })
        assert resp.status_code == 200

    def test_generate_all_deselected_returns_422(self, client):
        resp = client.post("/api/discovery/generate", json={
            "tool_type": "srogs",
            "case_info": SAMPLE_CASE_INFO,
            "selected_requests": [
                {"id": "s1", "text": "Dropped.", "category": "test", "is_selected": False, "order": 1},
            ],
        })
        assert resp.status_code == 422

    def test_generate_defendant_side(self, client):
        case = {**SAMPLE_CASE_INFO, "party_role": "defendant"}
        resp = client.post("/api/discovery/generate", json={
            "tool_type": "frogs_general",
            "case_info": case,
            "selected_sections": ["1.1", "2.1"],
        })
        assert resp.status_code == 200
        assert resp.content[:5] == b"%PDF-"

    def test_generate_has_generation_id_header(self, client):
        resp = client.post("/api/discovery/generate", json={
            "tool_type": "frogs_general",
            "case_info": SAMPLE_CASE_INFO,
            "selected_sections": ["1.1"],
        })
        assert resp.status_code == 200
        assert "x-generation-id" in resp.headers

    def test_generate_with_custom_definitions(self, client):
        resp = client.post("/api/discovery/generate", json={
            "tool_type": "srogs",
            "case_info": SAMPLE_CASE_INFO,
            "selected_requests": [
                {"id": "s1", "text": "State facts.", "category": "test", "is_selected": True, "order": 1},
            ],
            "custom_definitions": {"TERM1": "Definition one.", "TERM2": "Definition two."},
        })
        assert resp.status_code == 200

    def test_generate_without_definitions(self, client):
        resp = client.post("/api/discovery/generate", json={
            "tool_type": "srogs",
            "case_info": SAMPLE_CASE_INFO,
            "selected_requests": [
                {"id": "s1", "text": "State facts.", "category": "test", "is_selected": True, "order": 1},
            ],
            "include_definitions": False,
        })
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/discovery/banks/{tool}
# ---------------------------------------------------------------------------


class TestBanksEndpoint:
    @pytest.mark.parametrize("tool", [
        "frogs_general", "frogs_employment", "srogs", "rfpds", "rfas",
    ])
    def test_get_bank_all_tools(self, client, tool):
        resp = client.get(f"/api/discovery/banks/{tool}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tool_type"] == tool
        assert data["total_items"] > 0
        assert len(data["categories"]) > 0
        assert len(data["items"]) == data["total_items"]

    def test_bank_invalid_tool(self, client):
        resp = client.get("/api/discovery/banks/invalid_tool")
        assert resp.status_code == 404

    def test_srogs_bank_has_limit(self, client):
        resp = client.get("/api/discovery/banks/srogs")
        data = resp.json()
        assert data["limit"] == 35
        assert data["total_items"] == 58

    def test_rfas_bank_has_limit(self, client):
        resp = client.get("/api/discovery/banks/rfas")
        data = resp.json()
        assert data["limit"] == 35
        assert data["total_items"] == 67

    def test_rfpds_bank_no_limit(self, client):
        resp = client.get("/api/discovery/banks/rfpds")
        data = resp.json()
        assert data["limit"] is None
        assert data["total_items"] == 52

    def test_rfas_bank_has_rfa_type(self, client):
        resp = client.get("/api/discovery/banks/rfas")
        data = resp.json()
        rfa_types = {item["rfa_type"] for item in data["items"]}
        assert "fact" in rfa_types
        assert "genuineness" in rfa_types

    def test_bank_categories_have_counts(self, client):
        resp = client.get("/api/discovery/banks/srogs")
        data = resp.json()
        for cat in data["categories"]:
            assert "key" in cat
            assert "label" in cat
            assert cat["count"] > 0

    def test_frogs_general_bank_items(self, client):
        resp = client.get("/api/discovery/banks/frogs_general")
        data = resp.json()
        # Should have many subsections across 17 groups
        assert data["total_items"] > 50

    def test_frogs_employment_bank_items(self, client):
        resp = client.get("/api/discovery/banks/frogs_employment")
        data = resp.json()
        assert data["total_items"] > 40


# ---------------------------------------------------------------------------
# GET /api/discovery/definitions
# ---------------------------------------------------------------------------


class TestDefinitionsEndpoint:
    def test_get_definitions(self, client):
        resp = client.get("/api/discovery/definitions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["definitions"]) > 0
        assert len(data["production_instructions"]) > 0

    def test_definitions_have_terms(self, client):
        resp = client.get("/api/discovery/definitions")
        data = resp.json()
        terms = {d["term"] for d in data["definitions"]}
        assert "DOCUMENT" in terms
        assert "EMPLOYEE" in terms
        assert "EMPLOYER" in terms
        assert "ADVERSE EMPLOYMENT ACTION" in terms

    def test_definitions_have_content(self, client):
        resp = client.get("/api/discovery/definitions")
        data = resp.json()
        for defn in data["definitions"]:
            assert len(defn["term"]) > 0
            assert len(defn["definition"]) > 0

    def test_production_instructions_nonempty(self, client):
        resp = client.get("/api/discovery/definitions")
        data = resp.json()
        assert "Code of Civil Procedure" in data["production_instructions"]


# ---------------------------------------------------------------------------
# Schema validation edge cases
# ---------------------------------------------------------------------------


class TestSchemaValidation:
    def test_case_info_missing_plaintiffs(self, client):
        case = {**SAMPLE_CASE_INFO, "plaintiffs": []}
        resp = client.post("/api/discovery/generate", json={
            "tool_type": "frogs_general",
            "case_info": case,
            "selected_sections": ["1.1"],
        })
        assert resp.status_code == 422

    def test_case_info_invalid_party_role(self, client):
        case = {**SAMPLE_CASE_INFO, "party_role": "judge"}
        resp = client.post("/api/discovery/generate", json={
            "tool_type": "frogs_general",
            "case_info": case,
            "selected_sections": ["1.1"],
        })
        assert resp.status_code == 422

    def test_case_info_missing_case_number(self, client):
        case = {**SAMPLE_CASE_INFO}
        del case["case_number"]
        resp = client.post("/api/discovery/generate", json={
            "tool_type": "frogs_general",
            "case_info": case,
            "selected_sections": ["1.1"],
        })
        assert resp.status_code == 422

    def test_case_info_empty_attorney_name(self, client):
        case = {**SAMPLE_CASE_INFO}
        case["attorney"] = {**case["attorney"], "name": ""}
        resp = client.post("/api/discovery/generate", json={
            "tool_type": "frogs_general",
            "case_info": case,
            "selected_sections": ["1.1"],
        })
        assert resp.status_code == 422
