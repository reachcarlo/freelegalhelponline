"""API integration tests for the deadline calculator endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from employee_help.tools.deadlines import ClaimType


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
        from employee_help.api.main import app

        yield TestClient(app)


# ── Validation: missing fields ──────────────────────────────────────


def test_missing_claim_type(client):
    resp = client.post("/api/deadlines", json={"incident_date": "2025-06-01"})
    assert resp.status_code == 422


def test_missing_incident_date(client):
    resp = client.post("/api/deadlines", json={"claim_type": "feha_discrimination"})
    assert resp.status_code == 422


# ── Validation: invalid values ──────────────────────────────────────


def test_invalid_claim_type(client):
    resp = client.post(
        "/api/deadlines",
        json={"claim_type": "not_a_real_type", "incident_date": "2025-06-01"},
    )
    assert resp.status_code == 422


def test_invalid_date_format(client):
    resp = client.post(
        "/api/deadlines",
        json={"claim_type": "feha_discrimination", "incident_date": "not-a-date"},
    )
    assert resp.status_code == 422


def test_future_date_rejected(client):
    resp = client.post(
        "/api/deadlines",
        json={"claim_type": "feha_discrimination", "incident_date": "2099-01-01"},
    )
    assert resp.status_code == 422


def test_pre_1970_date_rejected(client):
    resp = client.post(
        "/api/deadlines",
        json={"claim_type": "feha_discrimination", "incident_date": "1960-01-01"},
    )
    assert resp.status_code == 422


# ── Happy path: all claim types ─────────────────────────────────────


@pytest.mark.parametrize("claim_type", [ct.value for ct in ClaimType])
def test_all_claim_types_accepted(client, claim_type):
    resp = client.post(
        "/api/deadlines",
        json={"claim_type": claim_type, "incident_date": "2025-06-01"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["claim_type"] == claim_type
    assert len(data["deadlines"]) > 0


# ── Response structure ──────────────────────────────────────────────


def test_response_structure(client):
    resp = client.post(
        "/api/deadlines",
        json={"claim_type": "wage_theft", "incident_date": "2025-01-15"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["claim_type"] == "wage_theft"
    assert data["claim_type_label"] == "Wage Theft / Unpaid Wages"
    assert data["incident_date"] == "2025-01-15"
    assert isinstance(data["deadlines"], list)
    assert "disclaimer" in data
    assert len(data["disclaimer"]) > 0

    # Check first deadline has all fields
    dl = data["deadlines"][0]
    assert "name" in dl
    assert "description" in dl
    assert "deadline_date" in dl
    assert "days_remaining" in dl
    assert "urgency" in dl
    assert "filing_entity" in dl
    assert "portal_url" in dl
    assert "legal_citation" in dl
    assert "notes" in dl


def test_disclaimer_present(client):
    resp = client.post(
        "/api/deadlines",
        json={"claim_type": "feha_discrimination", "incident_date": "2025-01-01"},
    )
    data = resp.json()
    assert "general estimates" in data["disclaimer"]
    assert "attorney" in data["disclaimer"].lower()
