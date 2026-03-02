"""API integration tests for the agency routing endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from employee_help.tools.routing import IssueType


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
        main_mod._routing_rate_store.clear()

        yield TestClient(main_mod.app)


# ── Validation: missing / invalid fields ─────────────────────────────


def test_missing_issue_type(client):
    resp = client.post("/api/agency-routing", json={})
    assert resp.status_code == 422


def test_invalid_issue_type(client):
    resp = client.post(
        "/api/agency-routing",
        json={"issue_type": "not_a_real_type"},
    )
    assert resp.status_code == 422


# ── Happy path: all issue types ──────────────────────────────────────


@pytest.mark.parametrize("issue_type", [it.value for it in IssueType])
def test_all_issue_types_accepted(client, issue_type):
    resp = client.post(
        "/api/agency-routing",
        json={"issue_type": issue_type},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["issue_type"] == issue_type
    assert len(data["recommendations"]) > 0


# ── Response structure ───────────────────────────────────────────────


def test_response_structure(client):
    resp = client.post(
        "/api/agency-routing",
        json={"issue_type": "discrimination"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["issue_type"] == "discrimination"
    assert data["issue_type_label"] == "Discrimination (Race, Gender, Age, Disability, etc.)"
    assert data["is_government_employee"] is False
    assert isinstance(data["recommendations"], list)
    assert "disclaimer" in data
    assert len(data["disclaimer"]) > 0

    # Check first recommendation has all fields
    rec = data["recommendations"][0]
    assert "agency_name" in rec
    assert "agency_acronym" in rec
    assert "agency_description" in rec
    assert "agency_handles" in rec
    assert "portal_url" in rec
    assert "phone" in rec
    assert "filing_methods" in rec
    assert isinstance(rec["filing_methods"], list)
    assert "process_overview" in rec
    assert "typical_timeline" in rec
    assert "priority" in rec
    assert "reason" in rec
    assert "what_to_file" in rec
    assert "notes" in rec
    assert "related_claim_type" in rec


# ── Government employee modifies response ────────────────────────────


def test_gov_employee_adds_prerequisite(client):
    resp = client.post(
        "/api/agency-routing",
        json={"issue_type": "discrimination", "is_government_employee": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_government_employee"] is True

    # Should have a prerequisite recommendation
    prereqs = [r for r in data["recommendations"] if r["priority"] == "prerequisite"]
    assert len(prereqs) == 1
    assert prereqs[0]["agency_acronym"] == "CalHR"


def test_gov_employee_no_change_for_safety(client):
    normal = client.post(
        "/api/agency-routing",
        json={"issue_type": "workplace_safety", "is_government_employee": False},
    ).json()
    gov = client.post(
        "/api/agency-routing",
        json={"issue_type": "workplace_safety", "is_government_employee": True},
    ).json()
    assert len(normal["recommendations"]) == len(gov["recommendations"])


# ── Defaults ─────────────────────────────────────────────────────────


def test_defaults_to_non_government(client):
    resp = client.post(
        "/api/agency-routing",
        json={"issue_type": "unpaid_wages"},
    )
    data = resp.json()
    assert data["is_government_employee"] is False
    # No prerequisite recommendations
    prereqs = [r for r in data["recommendations"] if r["priority"] == "prerequisite"]
    assert len(prereqs) == 0


# ── Disclaimer present ───────────────────────────────────────────────


def test_disclaimer_present(client):
    resp = client.post(
        "/api/agency-routing",
        json={"issue_type": "unpaid_wages"},
    )
    data = resp.json()
    assert "general information" in data["disclaimer"]
    assert "attorney" in data["disclaimer"].lower()


# ── Priority ordering ────────────────────────────────────────────────


def test_prerequisite_comes_first(client):
    resp = client.post(
        "/api/agency-routing",
        json={"issue_type": "discrimination", "is_government_employee": True},
    )
    data = resp.json()
    recs = data["recommendations"]
    assert recs[0]["priority"] == "prerequisite"
    # Primary before alternatives
    priorities = [r["priority"] for r in recs]
    order = {"prerequisite": 0, "primary": 1, "alternative": 2}
    values = [order[p] for p in priorities]
    assert values == sorted(values)
