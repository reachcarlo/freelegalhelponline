"""End-to-end tests for the FastAPI web API.

Tests the full request/response cycle through the API endpoints with mocked
RAG services to avoid loading ML models.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from employee_help.generation.llm import LLMClient, StreamChunk
from employee_help.generation.models import TokenUsage
from employee_help.generation.prompts import PromptBuilder, PromptBundle
from employee_help.generation.service import AnswerService
from employee_help.retrieval.service import RetrievalResult, RetrievalService


# ── Fixtures ──────────────────────────────────────────────────────────


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


def _make_statutory_result(chunk_id: int, section: str) -> RetrievalResult:
    return _make_result(
        chunk_id,
        content_category="statutory_code",
        citation=f"Cal. Lab. Code § {section}",
        source_url=f"https://leginfo.legislature.ca.gov/faces/codes_displaySection?sectionNum={section}&lawCode=LAB",
    )


@pytest.fixture
def mock_services():
    """Create mock retrieval and answer services."""
    retrieval_svc = MagicMock(spec=RetrievalService)
    retrieval_svc.embedding_service = MagicMock()
    retrieval_svc.vector_store = MagicMock()
    retrieval_svc.retrieve.return_value = [
        _make_result(1),
        _make_result(2),
        _make_result(3, content_category="faq"),
    ]

    # Build a real-ish AnswerService with mocked internals
    llm_client = MagicMock(spec=LLMClient)
    prompt_builder = MagicMock(spec=PromptBuilder)
    prompt_builder.build_prompt.return_value = PromptBundle(
        system_prompt="You are helpful.",
        user_message="test question",
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
    """Create a test client with mocked services, bypassing lifespan."""
    import employee_help.api.deps as deps
    from employee_help.api.main import _rate_limit_store

    retrieval_svc, answer_svc = mock_services
    old_ret, old_ans = deps._retrieval_service, deps._answer_service
    _rate_limit_store.clear()
    try:
        deps._retrieval_service = retrieval_svc
        deps._answer_service = answer_svc
        with TestClient(_make_noop_app(), raise_server_exceptions=False) as tc:
            yield tc
    finally:
        deps._retrieval_service = old_ret
        deps._answer_service = old_ans
        _rate_limit_store.clear()


# ── Helpers ───────────────────────────────────────────────────────────


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


# ── Helper to parse SSE events ────────────────────────────────────────


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

    # Handle final event without trailing newline
    if event_type and data_lines:
        data_str = "\n".join(data_lines)
        events.append((event_type, json.loads(data_str)))

    return events


# ── Health endpoint ───────────────────────────────────────────────────


class TestHealthEndpoint:
    def test_health_returns_ok(self, client, mock_services):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["embedding_model_loaded"] is True
        assert data["vector_store_connected"] is True

    def test_health_before_init(self):
        """Health returns 'starting' when services aren't initialized."""
        import employee_help.api.deps as deps
        old_ret, old_ans = deps._retrieval_service, deps._answer_service
        try:
            deps._retrieval_service = None
            deps._answer_service = None
            resp = TestClient(
                _make_noop_app(), raise_server_exceptions=False
            ).get("/api/health")
            assert resp.status_code == 200
            assert resp.json()["status"] == "starting"
        finally:
            deps._retrieval_service = old_ret
            deps._answer_service = old_ans


# ── Ask endpoint: validation ──────────────────────────────────────────


class TestAskValidation:
    def test_empty_query_rejected(self, client):
        resp = client.post("/api/ask", json={"query": "", "mode": "consumer"})
        assert resp.status_code == 422

    def test_missing_query_rejected(self, client):
        resp = client.post("/api/ask", json={"mode": "consumer"})
        assert resp.status_code == 422

    def test_invalid_mode_rejected(self, client):
        resp = client.post("/api/ask", json={"query": "test", "mode": "invalid"})
        assert resp.status_code == 422

    def test_query_too_long_rejected(self, client):
        resp = client.post(
            "/api/ask", json={"query": "x" * 2001, "mode": "consumer"}
        )
        assert resp.status_code == 422

    def test_default_mode_is_consumer(self, client, mock_services):
        """When mode is omitted, defaults to consumer."""
        retrieval_svc, answer_svc = mock_services
        # Set up streaming mock
        answer_svc.generate_stream = MagicMock(return_value=(
            iter(["test"]),
            [_make_result(1)],
            [{"model": "test", "input_tokens": 10, "output_tokens": 5, "citations": []}],
        ))
        resp = client.post("/api/ask", json={"query": "test question"})
        assert resp.status_code == 200
        # Verify generate_stream was called with mode="consumer"
        answer_svc.generate_stream.assert_called_once_with(
            query="test question", mode="consumer"
        )


# ── Ask endpoint: SSE streaming ───────────────────────────────────────


class TestAskStreaming:
    def test_consumer_mode_streams_response(self, client, mock_services):
        retrieval_svc, answer_svc = mock_services
        answer_svc.generate_stream = MagicMock(return_value=(
            iter(["The minimum ", "wage is ", "$16.90."]),
            [_make_result(1), _make_result(2)],
            [{"model": "claude-haiku-4-5-20251001", "input_tokens": 100, "output_tokens": 20, "citations": []}],
        ))

        resp = client.post(
            "/api/ask", json={"query": "What is minimum wage?", "mode": "consumer"}
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/event-stream; charset=utf-8"

        events = parse_sse(resp.text)
        event_types = [e[0] for e in events]

        # Must have sources first, then tokens, then done
        assert event_types[0] == "sources"
        assert event_types[-1] == "done"
        token_events = [e for e in events if e[0] == "token"]
        assert len(token_events) == 3

        # Verify sources event
        sources_data = events[0][1]
        assert len(sources_data["sources"]) == 2
        assert sources_data["sources"][0]["chunk_id"] == 1

        # Verify token content
        full_text = "".join(e[1]["text"] for e in token_events)
        assert full_text == "The minimum wage is $16.90."

        # Verify done metadata
        done_data = events[-1][1]
        assert done_data["model"] == "claude-haiku-4-5-20251001"
        assert done_data["input_tokens"] == 100
        assert done_data["output_tokens"] == 20
        assert done_data["duration_ms"] > 0
        assert "query_id" in done_data
        assert len(done_data["query_id"]) == 36  # UUID4 format

    def test_attorney_mode_streams_response(self, client, mock_services):
        retrieval_svc, answer_svc = mock_services
        statutory_results = [
            _make_statutory_result(1, "1102.5"),
            _make_statutory_result(2, "1102.6"),
        ]
        answer_svc.generate_stream = MagicMock(return_value=(
            iter(["Under Cal. Lab. Code § 1102.5, ", "protections apply."]),
            statutory_results,
            [{"model": "claude-sonnet-4-6", "input_tokens": 500, "output_tokens": 100, "citations": []}],
        ))

        resp = client.post(
            "/api/ask",
            json={"query": "Whistleblower protections?", "mode": "attorney"},
        )
        assert resp.status_code == 200
        events = parse_sse(resp.text)

        sources_data = events[0][1]
        assert sources_data["sources"][0]["citation"] == "Cal. Lab. Code § 1102.5"
        assert sources_data["sources"][0]["content_category"] == "statutory_code"

        done_data = [e for e in events if e[0] == "done"][0][1]
        assert done_data["model"] == "claude-sonnet-4-6"

    def test_empty_retrieval_streams_fallback(self, client, mock_services):
        """When retrieval returns nothing, stream still completes."""
        retrieval_svc, answer_svc = mock_services
        answer_svc.generate_stream = MagicMock(return_value=(
            iter(["I wasn't able to find relevant information."]),
            [],  # no retrieval results
            [],  # no metadata (empty stream)
        ))

        resp = client.post(
            "/api/ask", json={"query": "quantum physics?", "mode": "consumer"}
        )
        assert resp.status_code == 200
        events = parse_sse(resp.text)

        # Sources event should have empty list
        sources_data = events[0][1]
        assert sources_data["sources"] == []

        # Should still have token and done events
        token_events = [e for e in events if e[0] == "token"]
        assert len(token_events) >= 1

    def test_source_fields_serialized(self, client, mock_services):
        """Verify all SourceInfo fields are present in the SSE sources event."""
        retrieval_svc, answer_svc = mock_services
        answer_svc.generate_stream = MagicMock(return_value=(
            iter(["answer"]),
            [_make_result(
                42,
                content_category="faq",
                citation=None,
                source_url="https://www.dir.ca.gov/faq.htm",
                heading_path="FAQ > Minimum Wage",
                relevance_score=0.85,
            )],
            [{"model": "test", "input_tokens": 1, "output_tokens": 1, "citations": []}],
        ))

        resp = client.post(
            "/api/ask", json={"query": "test", "mode": "consumer"}
        )
        events = parse_sse(resp.text)
        source = events[0][1]["sources"][0]

        assert source["chunk_id"] == 42
        assert source["content_category"] == "faq"
        assert source["citation"] is None
        assert source["source_url"] == "https://www.dir.ca.gov/faq.htm"
        assert source["heading_path"] == "FAQ > Minimum Wage"
        assert source["relevance_score"] == pytest.approx(0.85)

    def test_cost_estimate_in_metadata(self, client, mock_services):
        retrieval_svc, answer_svc = mock_services
        answer_svc.generate_stream = MagicMock(return_value=(
            iter(["ok"]),
            [_make_result(1)],
            [{"model": "claude-haiku-4-5-20251001", "input_tokens": 1000, "output_tokens": 200, "citations": []}],
        ))

        resp = client.post(
            "/api/ask", json={"query": "test", "mode": "consumer"}
        )
        events = parse_sse(resp.text)
        done_data = [e for e in events if e[0] == "done"][0][1]

        # Haiku: $0.80/M input, $4.00/M output
        # 1000 * 0.80/1M + 200 * 4.00/1M = 0.0008 + 0.0008 = 0.0016
        assert done_data["cost_estimate"] > 0


# ── Ask endpoint: error handling ──────────────────────────────────────


class TestAskErrors:
    def test_service_error_returns_sse_error_event(self, client, mock_services):
        retrieval_svc, answer_svc = mock_services
        answer_svc.generate_stream = MagicMock(
            side_effect=RuntimeError("Model failed to load")
        )

        resp = client.post(
            "/api/ask", json={"query": "test", "mode": "consumer"}
        )
        assert resp.status_code == 200  # SSE always returns 200, errors are in-stream
        events = parse_sse(resp.text)

        error_events = [e for e in events if e[0] == "error"]
        assert len(error_events) == 1
        assert "Model failed to load" in error_events[0][1]["message"]

    def test_service_unavailable(self):
        """503 when services haven't been initialized."""
        import employee_help.api.deps as deps
        old_ret, old_ans = deps._retrieval_service, deps._answer_service
        try:
            deps._retrieval_service = None
            deps._answer_service = None
            app = _make_noop_app()
            resp = TestClient(app, raise_server_exceptions=False).post(
                "/api/ask", json={"query": "test", "mode": "consumer"}
            )
            assert resp.status_code == 503
        finally:
            deps._retrieval_service = old_ret
            deps._answer_service = old_ans


# ── Rate limiting ─────────────────────────────────────────────────────


class TestRateLimiting:
    def test_rate_limit_enforced(self, client, mock_services):
        retrieval_svc, answer_svc = mock_services
        answer_svc.generate_stream = MagicMock(return_value=(
            iter(["ok"]),
            [_make_result(1)],
            [{"model": "test", "input_tokens": 1, "output_tokens": 1, "citations": []}],
        ))

        # Clear rate limit store
        from employee_help.api.main import _rate_limit_store
        _rate_limit_store.clear()

        # First 5 should succeed
        for i in range(5):
            resp = client.post(
                "/api/ask", json={"query": f"question {i}", "mode": "consumer"}
            )
            assert resp.status_code == 200, f"Request {i+1} should succeed"

        # 6th should be rate limited
        resp = client.post(
            "/api/ask", json={"query": "one too many", "mode": "consumer"}
        )
        assert resp.status_code == 429
        assert "Rate limit" in resp.json()["detail"]

    def test_rate_limit_does_not_affect_health(self, client, mock_services):
        """Health endpoint should not be rate limited."""
        from employee_help.api.main import _rate_limit_store
        _rate_limit_store.clear()

        for _ in range(10):
            resp = client.get("/api/health")
            assert resp.status_code == 200


# ── Schema validation ─────────────────────────────────────────────────


class TestSchemas:
    def test_ask_request_valid(self):
        from employee_help.api.schemas import AskRequest
        req = AskRequest(query="test question", mode="consumer")
        assert req.query == "test question"
        assert req.mode == "consumer"

    def test_ask_request_default_mode(self):
        from employee_help.api.schemas import AskRequest
        req = AskRequest(query="test question")
        assert req.mode == "consumer"

    def test_ask_request_attorney_mode(self):
        from employee_help.api.schemas import AskRequest
        req = AskRequest(query="test question", mode="attorney")
        assert req.mode == "attorney"

    def test_ask_request_rejects_empty(self):
        from employee_help.api.schemas import AskRequest
        with pytest.raises(Exception):
            AskRequest(query="", mode="consumer")

    def test_ask_request_rejects_too_long(self):
        from employee_help.api.schemas import AskRequest
        with pytest.raises(Exception):
            AskRequest(query="x" * 2001, mode="consumer")

    def test_source_info_serialization(self):
        from employee_help.api.schemas import SourceInfo
        src = SourceInfo(
            chunk_id=1,
            content_category="statute",
            citation="Cal. Lab. Code § 1102.5",
            source_url="https://example.com",
            heading_path="LAB > Div 2",
            relevance_score=0.95,
        )
        data = src.model_dump()
        assert data["chunk_id"] == 1
        assert data["citation"] == "Cal. Lab. Code § 1102.5"

    def test_health_response_defaults(self):
        from employee_help.api.schemas import HealthResponse
        hr = HealthResponse()
        assert hr.status == "ok"
        assert hr.embedding_model_loaded is False
        assert hr.vector_store_connected is False
