"""API integration tests for the guided intake questionnaire endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


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
        main_mod._intake_rate_store.clear()

        yield TestClient(main_mod.app)


# ── GET /api/intake-questions ────────────────────────────────────────


def test_get_questions_returns_200(client):
    resp = client.get("/api/intake-questions")
    assert resp.status_code == 200


def test_get_questions_has_questions(client):
    data = client.get("/api/intake-questions").json()
    assert "questions" in data
    assert len(data["questions"]) >= 5


def test_get_questions_structure(client):
    data = client.get("/api/intake-questions").json()
    q = data["questions"][0]
    assert "question_id" in q
    assert "question_text" in q
    assert "help_text" in q
    assert "options" in q
    assert "allow_multiple" in q
    assert len(q["options"]) >= 2

    opt = q["options"][0]
    assert "key" in opt
    assert "label" in opt
    assert "help_text" in opt


# ── POST /api/intake — happy path ───────────────────────────────────


def test_intake_valid_answers(client):
    resp = client.post(
        "/api/intake",
        json={"answers": [
            "not_paid", "pay_not_received",
            "retaliation_no", "status_still_employed",
            "employer_private", "need_none",
        ]},
    )
    assert resp.status_code == 200


def test_intake_response_structure(client):
    data = client.post(
        "/api/intake",
        json={"answers": [
            "not_paid", "pay_not_received",
            "retaliation_no", "status_still_employed",
            "employer_private", "need_none",
        ]},
    ).json()

    assert "identified_issues" in data
    assert "is_government_employee" in data
    assert "employment_status" in data
    assert "summary" in data
    assert "disclaimer" in data
    assert len(data["identified_issues"]) > 0


def test_intake_identified_issue_structure(client):
    data = client.post(
        "/api/intake",
        json={"answers": [
            "not_paid", "pay_not_received",
            "retaliation_no", "status_still_employed",
            "employer_private", "need_none",
        ]},
    ).json()

    issue = data["identified_issues"][0]
    assert "issue_type" in issue
    assert "issue_label" in issue
    assert "confidence" in issue
    assert "description" in issue
    assert "related_claim_types" in issue
    assert "tools" in issue
    assert "has_deadline_urgency" in issue
    assert len(issue["tools"]) >= 1

    tool = issue["tools"][0]
    assert "tool_name" in tool
    assert "tool_label" in tool
    assert "tool_path" in tool
    assert "description" in tool
    assert "prefill_params" in tool


# ── POST /api/intake — validation ───────────────────────────────────


def test_intake_invalid_answer_key(client):
    resp = client.post(
        "/api/intake",
        json={"answers": ["not_a_real_key"]},
    )
    assert resp.status_code == 422


def test_intake_empty_answers(client):
    resp = client.post(
        "/api/intake",
        json={"answers": []},
    )
    assert resp.status_code == 422


# ── Government employee ──────────────────────────────────────────────


def test_intake_detects_government_employee(client):
    data = client.post(
        "/api/intake",
        json={"answers": [
            "not_paid", "pay_not_received",
            "retaliation_no", "status_still_employed",
            "employer_government", "need_none",
        ]},
    ).json()

    assert data["is_government_employee"] is True


# ── Disclaimer ───────────────────────────────────────────────────────


def test_intake_disclaimer_present(client):
    data = client.post(
        "/api/intake",
        json={"answers": [
            "not_paid", "pay_not_received",
            "retaliation_no", "status_still_employed",
            "employer_private", "need_none",
        ]},
    ).json()

    assert "not legal advice" in data["disclaimer"].lower()
    assert "attorney" in data["disclaimer"].lower()
