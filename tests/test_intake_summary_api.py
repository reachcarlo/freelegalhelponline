"""API integration tests for POST /api/intake-summary.

Mirrors the patterns in test_api.py — mocked AnswerService, no ML models.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from employee_help.generation.llm import LLMClient
from employee_help.generation.prompts import PromptBuilder, PromptBundle
from employee_help.generation.service import AnswerService
from employee_help.retrieval.service import RetrievalResult, RetrievalService


# ── Helpers ──────────────────────────────────────────────────────────


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
    events = []
    event_type = ""
    data_lines: list[str] = []

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


# Valid answers that trigger unpaid_wages (high confidence)
VALID_ANSWERS = [
    "not_paid", "pay_not_received",
    "retaliation_no", "status_still_employed",
    "employer_private", "need_none",
]


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def mock_services():
    retrieval_svc = MagicMock(spec=RetrievalService)
    retrieval_svc.embedding_service = MagicMock()
    retrieval_svc.vector_store = MagicMock()
    retrieval_svc.retrieve.return_value = [_make_result(1), _make_result(2)]

    llm_client = MagicMock(spec=LLMClient)
    prompt_builder = MagicMock(spec=PromptBuilder)
    prompt_builder.build_prompt.return_value = PromptBundle(
        system_prompt="You are helpful.",
        user_message="test",
        document_blocks=[],
        context_chunks=[_make_result(1), _make_result(2)],
    )

    answer_svc = AnswerService(
        retrieval_service=retrieval_svc,
        llm_client=llm_client,
        prompt_builder=prompt_builder,
        citation_validation="strict",
    )

    return retrieval_svc, answer_svc


@pytest.fixture
def client(mock_services):
    import employee_help.api.deps as deps
    from employee_help.api.main import _intake_summary_rate_store, _rate_limit_store

    retrieval_svc, answer_svc = mock_services
    old_ret, old_ans = deps._retrieval_service, deps._answer_service
    _rate_limit_store.clear()
    _intake_summary_rate_store.clear()
    try:
        deps._retrieval_service = retrieval_svc
        deps._answer_service = answer_svc
        with TestClient(_make_noop_app(), raise_server_exceptions=False) as tc:
            yield tc
    finally:
        deps._retrieval_service = old_ret
        deps._answer_service = old_ans
        _rate_limit_store.clear()
        _intake_summary_rate_store.clear()


# ── Tests ────────────────────────────────────────────────────────────


class TestIntakeSummaryEndpoint:
    def test_valid_request_returns_sse_stream(self, client, mock_services):
        """POST /api/intake-summary with valid answers returns 200 SSE stream."""
        _, answer_svc = mock_services
        answer_svc.generate_stream = MagicMock(return_value=(
            iter(["You have ", "rights."]),
            [_make_result(1), _make_result(2)],
            [{"model": "claude-haiku-4-5-20251001", "input_tokens": 50, "output_tokens": 10, "citations": []}],
        ))

        resp = client.post("/api/intake-summary", json={"answers": VALID_ANSWERS})
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/event-stream; charset=utf-8"

    def test_invalid_answer_key_returns_422(self, client):
        """Invalid answer key should return 422."""
        resp = client.post(
            "/api/intake-summary", json={"answers": ["not_a_real_key"]}
        )
        assert resp.status_code == 422

    def test_empty_answers_returns_422(self, client):
        """Empty answers list should return 422."""
        resp = client.post("/api/intake-summary", json={"answers": []})
        assert resp.status_code == 422

    def test_sse_events_structure(self, client, mock_services):
        """Response contains sources, token, and done SSE events."""
        _, answer_svc = mock_services
        answer_svc.generate_stream = MagicMock(return_value=(
            iter(["Your rights ", "include..."]),
            [_make_result(1)],
            [{"model": "claude-haiku-4-5-20251001", "input_tokens": 80, "output_tokens": 15, "citations": []}],
        ))

        resp = client.post("/api/intake-summary", json={"answers": VALID_ANSWERS})
        events = parse_sse(resp.text)
        event_types = [e[0] for e in events]

        assert event_types[0] == "sources"
        assert event_types[-1] == "done"
        token_events = [e for e in events if e[0] == "token"]
        assert len(token_events) == 2

        # Check sources
        sources_data = events[0][1]
        assert len(sources_data["sources"]) == 1
        assert sources_data["sources"][0]["chunk_id"] == 1

        # Check token text
        full_text = "".join(e[1]["text"] for e in token_events)
        assert full_text == "Your rights include..."

    def test_done_event_contains_metadata(self, client, mock_services):
        """Done event contains model, duration, cost_estimate."""
        _, answer_svc = mock_services
        answer_svc.generate_stream = MagicMock(return_value=(
            iter(["answer"]),
            [_make_result(1)],
            [{"model": "claude-haiku-4-5-20251001", "input_tokens": 100, "output_tokens": 20, "citations": []}],
        ))

        resp = client.post("/api/intake-summary", json={"answers": VALID_ANSWERS})
        events = parse_sse(resp.text)
        done_event = next(e for e in events if e[0] == "done")
        done_data = done_event[1]

        assert done_data["model"] == "claude-haiku-4-5-20251001"
        assert "duration_ms" in done_data
        assert "cost_estimate" in done_data
        assert "query_id" in done_data

    def test_no_issues_returns_done_with_warning(self, client):
        """When intake finds no issues, returns done event with warning."""
        # Answers that produce no issues above threshold
        no_issue_answers = [
            "pay_na", "unfair_na", "retaliation_no",
            "status_still_employed", "employer_private", "need_none",
        ]
        resp = client.post("/api/intake-summary", json={"answers": no_issue_answers})
        assert resp.status_code == 200

        events = parse_sse(resp.text)
        done_event = next(e for e in events if e[0] == "done")
        assert len(done_event[1]["warnings"]) > 0

    def test_consumer_mode_is_used(self, client, mock_services):
        """Endpoint always calls generate_stream with mode='consumer'."""
        _, answer_svc = mock_services
        answer_svc.generate_stream = MagicMock(return_value=(
            iter(["ok"]),
            [_make_result(1)],
            [{"model": "test", "input_tokens": 10, "output_tokens": 5, "citations": []}],
        ))

        client.post("/api/intake-summary", json={"answers": VALID_ANSWERS})
        answer_svc.generate_stream.assert_called_once()
        call_kwargs = answer_svc.generate_stream.call_args
        assert call_kwargs.kwargs.get("mode") == "consumer" or call_kwargs[1].get("mode") == "consumer"
