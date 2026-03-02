"""API integration tests for the incident documentation guide endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from employee_help.tools.incident_docs import IncidentType


# ── Fixture ──────────────────────────────────────────────────────────


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

        # Reset rate limit store between tests to avoid 429s
        main_mod._incident_guide_rate_store.clear()

        yield TestClient(main_mod.app)


# ── Validation: missing / invalid fields ─────────────────────────────


def test_missing_incident_type(client):
    resp = client.post("/api/incident-guide", json={})
    assert resp.status_code == 422


def test_invalid_incident_type(client):
    resp = client.post(
        "/api/incident-guide",
        json={"incident_type": "not_a_real_type"},
    )
    assert resp.status_code == 422


# ── Happy path: all incident types ───────────────────────────────────


@pytest.mark.parametrize("incident_type", [it.value for it in IncidentType])
def test_all_incident_types_accepted(client, incident_type):
    resp = client.post(
        "/api/incident-guide",
        json={"incident_type": incident_type},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["incident_type"] == incident_type
    assert len(data["incident_type_label"]) > 0


# ── Response structure ───────────────────────────────────────────────


def test_response_structure(client):
    resp = client.post(
        "/api/incident-guide",
        json={"incident_type": "discrimination"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["incident_type"] == "discrimination"
    assert data["incident_type_label"] == "Discrimination"
    assert isinstance(data["description"], str)
    assert isinstance(data["common_fields"], list)
    assert isinstance(data["specific_fields"], list)
    assert isinstance(data["prompts"], list)
    assert isinstance(data["evidence_checklist"], list)
    assert isinstance(data["related_claim_types"], list)
    assert isinstance(data["legal_tips"], list)
    assert "disclaimer" in data


def test_common_fields_count_and_names(client):
    resp = client.post(
        "/api/incident-guide",
        json={"incident_type": "harassment"},
    )
    data = resp.json()
    common_names = [f["name"] for f in data["common_fields"]]
    assert len(common_names) == 8
    assert "incident_date" in common_names
    assert "narrative" in common_names
    assert "location" in common_names


def test_specific_fields_non_empty(client):
    resp = client.post(
        "/api/incident-guide",
        json={"incident_type": "wrongful_termination"},
    )
    data = resp.json()
    assert len(data["specific_fields"]) > 0


def test_prompts_non_empty(client):
    resp = client.post(
        "/api/incident-guide",
        json={"incident_type": "retaliation"},
    )
    data = resp.json()
    assert len(data["prompts"]) >= 3


def test_evidence_checklist_non_empty(client):
    resp = client.post(
        "/api/incident-guide",
        json={"incident_type": "unpaid_wages"},
    )
    data = resp.json()
    assert len(data["evidence_checklist"]) >= 4


def test_related_claim_types_is_list(client):
    resp = client.post(
        "/api/incident-guide",
        json={"incident_type": "meal_rest_breaks"},
    )
    data = resp.json()
    assert isinstance(data["related_claim_types"], list)


def test_disclaimer_present(client):
    resp = client.post(
        "/api/incident-guide",
        json={"incident_type": "whistleblower"},
    )
    data = resp.json()
    assert "personal record" in data["disclaimer"].lower()
    assert "attorney" in data["disclaimer"].lower()


def test_field_info_structure(client):
    resp = client.post(
        "/api/incident-guide",
        json={"incident_type": "discrimination"},
    )
    data = resp.json()
    field = data["common_fields"][0]
    assert "name" in field
    assert "label" in field
    assert "field_type" in field
    assert "placeholder" in field
    assert "required" in field
    assert "help_text" in field
    assert "options" in field


def test_evidence_item_structure(client):
    resp = client.post(
        "/api/incident-guide",
        json={"incident_type": "workplace_safety"},
    )
    data = resp.json()
    item = data["evidence_checklist"][0]
    assert "description" in item
    assert "importance" in item
    assert item["importance"] in ("critical", "recommended", "optional")
    assert "tip" in item
