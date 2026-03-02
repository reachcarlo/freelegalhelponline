"""API integration tests for the unpaid wages calculator endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from employee_help.tools.unpaid_wages import EmploymentStatus


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
        main_mod._wages_rate_store.clear()

        yield TestClient(main_mod.app)


# ── Validation: missing / invalid fields ─────────────────────────────


def test_missing_hourly_rate(client):
    resp = client.post("/api/unpaid-wages", json={"unpaid_hours": 8})
    assert resp.status_code == 422


def test_negative_hourly_rate(client):
    resp = client.post(
        "/api/unpaid-wages",
        json={"hourly_rate": -5, "unpaid_hours": 8},
    )
    assert resp.status_code == 422


def test_zero_hourly_rate(client):
    resp = client.post(
        "/api/unpaid-wages",
        json={"hourly_rate": 0, "unpaid_hours": 8},
    )
    assert resp.status_code == 422


def test_hourly_rate_over_1000(client):
    resp = client.post(
        "/api/unpaid-wages",
        json={"hourly_rate": 1001, "unpaid_hours": 8},
    )
    assert resp.status_code == 422


def test_invalid_employment_status(client):
    resp = client.post(
        "/api/unpaid-wages",
        json={
            "hourly_rate": 25,
            "unpaid_hours": 8,
            "employment_status": "not_a_status",
        },
    )
    assert resp.status_code == 422


def test_terminated_without_termination_date(client):
    resp = client.post(
        "/api/unpaid-wages",
        json={
            "hourly_rate": 25,
            "unpaid_hours": 8,
            "employment_status": "terminated",
        },
    )
    assert resp.status_code == 422


def test_future_termination_date(client):
    resp = client.post(
        "/api/unpaid-wages",
        json={
            "hourly_rate": 25,
            "unpaid_hours": 8,
            "employment_status": "terminated",
            "termination_date": "2099-01-01",
        },
    )
    assert resp.status_code == 422


# ── Happy path ──────────────────────────────────────────────────────


def test_valid_basic_request(client):
    resp = client.post(
        "/api/unpaid-wages",
        json={"hourly_rate": 25, "unpaid_hours": 40},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) > 0
    assert data["total"] == "1000.00"


def test_response_structure(client):
    resp = client.post(
        "/api/unpaid-wages",
        json={"hourly_rate": 20, "unpaid_hours": 10, "missed_meal_breaks": 1},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert "items" in data
    assert "total" in data
    assert "hourly_rate" in data
    assert "unpaid_hours" in data
    assert "disclaimer" in data

    item = data["items"][0]
    assert "category" in item
    assert "label" in item
    assert "amount" in item
    assert "legal_citation" in item
    assert "description" in item
    assert "notes" in item


@pytest.mark.parametrize("status", [s.value for s in EmploymentStatus])
def test_all_employment_statuses_accepted(client, status):
    payload = {"hourly_rate": 25, "unpaid_hours": 8, "employment_status": status}
    if status != "still_employed":
        payload["termination_date"] = "2025-01-15"
    resp = client.post("/api/unpaid-wages", json=payload)
    assert resp.status_code == 200


def test_waiting_penalty_for_terminated(client):
    resp = client.post(
        "/api/unpaid-wages",
        json={
            "hourly_rate": 25,
            "unpaid_hours": 8,
            "employment_status": "terminated",
            "termination_date": "2025-01-01",
        },
    )
    data = resp.json()
    categories = [item["category"] for item in data["items"]]
    assert "waiting_time_penalty" in categories


def test_no_penalty_for_still_employed(client):
    resp = client.post(
        "/api/unpaid-wages",
        json={"hourly_rate": 25, "unpaid_hours": 8},
    )
    data = resp.json()
    categories = [item["category"] for item in data["items"]]
    assert "waiting_time_penalty" not in categories


def test_disclaimer_present(client):
    resp = client.post(
        "/api/unpaid-wages",
        json={"hourly_rate": 25, "unpaid_hours": 8},
    )
    data = resp.json()
    assert "general estimates" in data["disclaimer"]
    assert "attorney" in data["disclaimer"].lower()


def test_total_is_valid_number(client):
    resp = client.post(
        "/api/unpaid-wages",
        json={"hourly_rate": 25, "unpaid_hours": 40, "missed_meal_breaks": 3},
    )
    data = resp.json()
    total = float(data["total"])
    assert total > 0


def test_defaults_work(client):
    """Minimal request with just rate and hours uses sensible defaults."""
    resp = client.post(
        "/api/unpaid-wages",
        json={"hourly_rate": 15, "unpaid_hours": 0},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == "0.00"
