"""Tests for the feedback API endpoints (POST /api/feedback, query_id in /api/ask)."""

from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from employee_help.feedback.models import QueryLogEntry
from employee_help.feedback.store import FeedbackStore
from employee_help.generation.llm import LLMClient, StreamChunk
from employee_help.generation.prompts import PromptBuilder, PromptBundle
from employee_help.generation.service import AnswerService
from employee_help.retrieval.service import RetrievalResult, RetrievalService


# ── Helpers ──────────────────────────────────────────────────────


def _make_result(chunk_id: int, **kwargs) -> RetrievalResult:
    defaults = {
        "chunk_id": chunk_id,
        "document_id": chunk_id * 10,
        "source_id": 1,
        "content": f"Content for chunk {chunk_id}",
        "heading_path": f"Test > Chunk {chunk_id}",
        "content_category": "agency_guidance",
        "citation": None,
        "relevance_score": 0.9 - (chunk_id * 0.1),
        "source_url": f"https://example.com/{chunk_id}",
    }
    defaults.update(kwargs)
    return RetrievalResult(**defaults)


def _make_noop_app():
    """Create a FastAPI app with no-op lifespan but real middleware/routes."""
    from contextlib import asynccontextmanager

    from fastapi import FastAPI

    from employee_help.api.main import log_requests, rate_limit_middleware
    from employee_help.api.routes import router

    @asynccontextmanager
    async def noop_lifespan(app):
        yield

    app = FastAPI(lifespan=noop_lifespan)
    app.middleware("http")(rate_limit_middleware)
    app.middleware("http")(log_requests)
    app.include_router(router)
    return app


def parse_sse(text: str) -> list[tuple[str, dict]]:
    """Parse SSE text into (event_type, data) tuples."""
    events = []
    event_type = ""
    data_lines = []

    for line in text.split("\n"):
        if line.startswith("event: "):
            event_type = line[7:].strip()
        elif line.startswith("data: "):
            data_lines.append(line[6:])
        elif line == "" and event_type and data_lines:
            data_str = "\n".join(data_lines)
            events.append((event_type, json.loads(data_str)))
            event_type = ""
            data_lines = []

    if event_type and data_lines:
        data_str = "\n".join(data_lines)
        events.append((event_type, json.loads(data_str)))

    return events


# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def feedback_store(tmp_path):
    """Create a FeedbackStore with a temp database."""
    db_path = tmp_path / "feedback.db"
    return FeedbackStore(db_path)


@pytest.fixture
def mock_services():
    """Create mock retrieval and answer services."""
    retrieval_svc = MagicMock(spec=RetrievalService)
    retrieval_svc.embedding_service = MagicMock()
    retrieval_svc.vector_store = MagicMock()

    llm_client = MagicMock(spec=LLMClient)
    prompt_builder = MagicMock(spec=PromptBuilder)
    prompt_builder.build_prompt.return_value = PromptBundle(
        system_prompt="You are helpful.",
        user_message="test question",
        document_blocks=[],
        context_chunks=[_make_result(1)],
    )

    answer_svc = AnswerService(
        retrieval_service=retrieval_svc,
        llm_client=llm_client,
        prompt_builder=prompt_builder,
        citation_validation="strict",
    )
    answer_svc.generate_stream = MagicMock(
        return_value=(
            iter(["test answer"]),
            [_make_result(1)],
            [{"model": "test-model", "input_tokens": 10, "output_tokens": 5, "citations": []}],
        )
    )

    return retrieval_svc, answer_svc


@pytest.fixture
def client(mock_services, feedback_store):
    """Create a test client with mocked services and real feedback store."""
    import employee_help.api.deps as deps
    from employee_help.api.main import _rate_limit_store

    retrieval_svc, answer_svc = mock_services
    old_ret = deps._retrieval_service
    old_ans = deps._answer_service
    old_fb = deps._feedback_store
    _rate_limit_store.clear()

    try:
        deps._retrieval_service = retrieval_svc
        deps._answer_service = answer_svc
        deps._feedback_store = feedback_store
        with TestClient(_make_noop_app(), raise_server_exceptions=False) as tc:
            yield tc
    finally:
        deps._retrieval_service = old_ret
        deps._answer_service = old_ans
        deps._feedback_store = old_fb
        _rate_limit_store.clear()
        feedback_store.close()


# ── POST /api/feedback tests ─────────────────────────────────────


class TestFeedbackEndpoint:
    def test_valid_feedback_returns_200(self, client, feedback_store):
        # First create a query log entry
        entry = QueryLogEntry(
            query_id="test-id-123",
            query_hash="abc",
            mode="consumer",
        )
        feedback_store.log_query(entry)

        resp = client.post(
            "/api/feedback",
            json={"query_id": "test-id-123", "rating": 1},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_unknown_query_id_returns_404(self, client):
        resp = client.post(
            "/api/feedback",
            json={"query_id": "nonexistent-id", "rating": 1},
        )
        assert resp.status_code == 404
        assert "Unknown query_id" in resp.json()["detail"]

    def test_invalid_rating_returns_422(self, client):
        resp = client.post(
            "/api/feedback",
            json={"query_id": "some-id", "rating": 0},
        )
        assert resp.status_code == 422

    def test_missing_query_id_returns_422(self, client):
        resp = client.post(
            "/api/feedback",
            json={"rating": 1},
        )
        assert resp.status_code == 422

    def test_thumbs_down_stored(self, client, feedback_store):
        entry = QueryLogEntry(
            query_id="test-down",
            query_hash="abc",
            mode="attorney",
        )
        feedback_store.log_query(entry)

        resp = client.post(
            "/api/feedback",
            json={"query_id": "test-down", "rating": -1},
        )
        assert resp.status_code == 200

        fb = feedback_store.get_feedback("test-down")
        assert fb is not None
        assert fb.rating == -1


# ── query_id in /api/ask SSE done event ──────────────────────────


class TestQueryIdInAsk:
    def test_done_event_contains_query_id(self, client, mock_services):
        resp = client.post(
            "/api/ask", json={"query": "test question", "mode": "consumer"}
        )
        assert resp.status_code == 200

        events = parse_sse(resp.text)
        done_events = [e for e in events if e[0] == "done"]
        assert len(done_events) == 1

        done_data = done_events[0][1]
        assert "query_id" in done_data
        assert len(done_data["query_id"]) == 36  # UUID4 format

    def test_query_logged_after_ask(self, client, feedback_store, mock_services):
        resp = client.post(
            "/api/ask", json={"query": "test question", "mode": "consumer"}
        )
        assert resp.status_code == 200

        events = parse_sse(resp.text)
        done_data = [e for e in events if e[0] == "done"][0][1]
        query_id = done_data["query_id"]

        # Verify the query was logged in the feedback store
        stats = feedback_store.get_mode_distribution(days=1)
        assert stats.get("consumer", 0) >= 1
