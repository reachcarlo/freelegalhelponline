"""Tests for security headers middleware (A3.3)."""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from employee_help.api.main import security_headers


# ── Fixtures ───────────────────────────────────────────────────


@pytest.fixture
def app() -> FastAPI:
    """Minimal FastAPI app with only the security headers middleware."""

    @asynccontextmanager
    async def noop_lifespan(app: FastAPI):
        yield

    test_app = FastAPI(lifespan=noop_lifespan)

    test_app.middleware("http")(security_headers)

    @test_app.get("/api/test")
    async def test_endpoint():
        return {"ok": True}

    @test_app.post("/api/ask")
    async def ask_endpoint():
        return {"answer": "test"}

    @test_app.get("/health")
    async def health():
        return {"status": "healthy"}

    return test_app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


# ── Security Headers Present ──────────────────────────────────


class TestSecurityHeadersPresent:
    """All API responses must include security headers."""

    def test_x_content_type_options(self, client: TestClient):
        resp = client.get("/api/test")
        assert resp.headers["X-Content-Type-Options"] == "nosniff"

    def test_x_frame_options(self, client: TestClient):
        resp = client.get("/api/test")
        assert resp.headers["X-Frame-Options"] == "DENY"

    def test_referrer_policy(self, client: TestClient):
        resp = client.get("/api/test")
        assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    def test_permissions_policy(self, client: TestClient):
        resp = client.get("/api/test")
        assert resp.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"

    def test_headers_on_post(self, client: TestClient):
        resp = client.post("/api/ask", json={"question": "test"})
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["X-Frame-Options"] == "DENY"

    def test_headers_on_non_api_route(self, client: TestClient):
        resp = client.get("/health")
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert resp.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"

    def test_headers_on_404(self, client: TestClient):
        resp = client.get("/nonexistent")
        assert resp.status_code == 404
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["X-Frame-Options"] == "DENY"


# ── Integration: Headers on actual app ────────────────────────


class TestSecurityHeadersIntegration:
    """Verify headers are present on the real app (imported fresh)."""

    def test_real_app_has_security_headers(self):
        """The real app should respond with security headers."""
        from employee_help.api.main import app as real_app

        with TestClient(real_app) as c:
            resp = c.get("/api/health")
            assert resp.headers.get("X-Content-Type-Options") == "nosniff"
            assert resp.headers.get("X-Frame-Options") == "DENY"
            assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
            assert (
                resp.headers.get("Permissions-Policy")
                == "camera=(), microphone=(), geolocation=()"
            )
