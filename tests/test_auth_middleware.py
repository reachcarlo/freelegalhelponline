"""Tests for auth middleware (A1.4)."""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from employee_help.api.main import (
    _get_rate_limit_key,
    _requires_auth,
    auth_middleware,
)
from employee_help.auth.models import Membership, Organization, User
from employee_help.auth.session import SessionManager
from employee_help.auth.storage import AuthStorage
from employee_help.auth.tokens import AccessTokenClaims, create_access_token
from employee_help.storage.storage import Storage


SECRET = "test-jwt-secret-middleware"


# ── Fixtures ───────────────────────────────────────────────────


@pytest.fixture
def storage(tmp_path: Path) -> Storage:
    db_path = tmp_path / "test.db"
    s = Storage(db_path=db_path)
    yield s
    s.close()


@pytest.fixture
def auth_storage(storage: Storage) -> AuthStorage:
    conn = sqlite3.connect(str(storage._db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return AuthStorage(conn=conn)


@pytest.fixture
def session_manager(auth_storage: AuthStorage) -> SessionManager:
    return SessionManager(auth_storage=auth_storage, jwt_secret=SECRET)


@pytest.fixture
def user_with_org(auth_storage: AuthStorage) -> tuple[User, Organization, Membership]:
    user = User(
        id=str(uuid.uuid4()),
        provider="google",
        provider_user_id="mw-test-123",
        email="test@lawfirm.com",
        display_name="Test Attorney",
    )
    auth_storage.create_user(user)
    org = Organization(id=str(uuid.uuid4()), name="Test Org", slug="test-org")
    auth_storage.create_organization(org)
    membership = Membership(
        id=str(uuid.uuid4()),
        user_id=user.id,
        organization_id=org.id,
        role="owner",
    )
    auth_storage.create_membership(membership)
    return user, org, membership


def _make_test_app() -> FastAPI:
    """Create a test app with auth middleware and dummy routes."""

    @asynccontextmanager
    async def noop_lifespan(app):
        yield

    test_app = FastAPI(lifespan=noop_lifespan)
    test_app.middleware("http")(auth_middleware)

    # Protected routes
    @test_app.get("/api/cases")
    async def list_cases(request: Request):
        return JSONResponse(
            content={
                "user_id": request.state.user.sub,
                "org_id": request.state.user.org,
                "role": request.state.user.role,
            }
        )

    @test_app.get("/api/cases/{case_id}")
    async def get_case(request: Request, case_id: str):
        return JSONResponse(
            content={"case_id": case_id, "user_id": request.state.user.sub}
        )

    @test_app.post("/api/discovery/suggest")
    async def discovery_suggest(request: Request):
        return JSONResponse(content={"user_id": request.state.user.sub})

    @test_app.post("/api/objections/parse")
    async def objections_parse(request: Request):
        return JSONResponse(content={"user_id": request.state.user.sub})

    # Public routes
    @test_app.get("/api/health")
    async def health():
        return JSONResponse(content={"status": "ok"})

    @test_app.post("/api/ask")
    async def ask(request: Request):
        user = request.state.user
        return JSONResponse(
            content={"answer": "test", "authenticated": user is not None}
        )

    @test_app.post("/api/deadlines")
    async def deadlines():
        return JSONResponse(content={"ok": True})

    @test_app.post("/api/feedback")
    async def feedback():
        return JSONResponse(content={"ok": True})

    return test_app


@pytest.fixture
def client(session_manager: SessionManager) -> TestClient:
    import employee_help.api.deps as deps

    old_sm = deps._session_manager
    try:
        deps._session_manager = session_manager
        with TestClient(_make_test_app(), raise_server_exceptions=False) as tc:
            yield tc
    finally:
        deps._session_manager = old_sm


@pytest.fixture
def auth_token(session_manager: SessionManager, user_with_org: tuple) -> str:
    user, org, membership = user_with_org
    access_token, _ = session_manager.create_session(
        user=user,
        org_id=org.id,
        role="owner",
    )
    return access_token


# ── _requires_auth tests ──────────────────────────────────────


class TestRequiresAuth:
    """Test the _requires_auth path checker."""

    def test_cases_path(self):
        assert _requires_auth("/api/cases") is True

    def test_cases_subpath(self):
        assert _requires_auth("/api/cases/123/files") is True

    def test_discovery_path(self):
        assert _requires_auth("/api/discovery/suggest") is True

    def test_discovery_banks(self):
        assert _requires_auth("/api/discovery/banks/srogs") is True

    def test_objections_path(self):
        assert _requires_auth("/api/objections/parse") is True

    def test_objections_grounds(self):
        assert _requires_auth("/api/objections/grounds") is True

    def test_health_is_public(self):
        assert _requires_auth("/api/health") is False

    def test_ask_is_public(self):
        assert _requires_auth("/api/ask") is False

    def test_auth_is_public(self):
        assert _requires_auth("/api/auth/google/login") is False

    def test_deadlines_is_public(self):
        assert _requires_auth("/api/deadlines") is False

    def test_feedback_is_public(self):
        assert _requires_auth("/api/feedback") is False

    def test_intake_is_public(self):
        assert _requires_auth("/api/intake") is False

    def test_intake_summary_is_public(self):
        assert _requires_auth("/api/intake-summary") is False

    def test_agency_routing_is_public(self):
        assert _requires_auth("/api/agency-routing") is False

    def test_unpaid_wages_is_public(self):
        assert _requires_auth("/api/unpaid-wages") is False

    def test_incident_guide_is_public(self):
        assert _requires_auth("/api/incident-guide") is False

    def test_root_is_public(self):
        assert _requires_auth("/") is False

    def test_docs_is_public(self):
        assert _requires_auth("/docs") is False


# ── Auth middleware tests ─────────────────────────────────────


class TestAuthMiddleware:
    """Test auth middleware behavior with test app."""

    def test_protected_path_without_auth_returns_401(self, client: TestClient):
        resp = client.get("/api/cases")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Authentication required"

    def test_protected_subpath_without_auth_returns_401(self, client: TestClient):
        resp = client.get("/api/cases/some-uuid")
        assert resp.status_code == 401

    def test_discovery_without_auth_returns_401(self, client: TestClient):
        resp = client.post("/api/discovery/suggest")
        assert resp.status_code == 401

    def test_objections_without_auth_returns_401(self, client: TestClient):
        resp = client.post("/api/objections/parse")
        assert resp.status_code == 401

    def test_protected_path_with_valid_token_succeeds(
        self, client: TestClient, auth_token: str, user_with_org: tuple
    ):
        user, org, _ = user_with_org
        client.cookies.set("access_token", auth_token)
        resp = client.get("/api/cases")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == user.id
        assert data["org_id"] == org.id
        assert data["role"] == "owner"

    def test_protected_subpath_with_valid_token_succeeds(
        self, client: TestClient, auth_token: str, user_with_org: tuple
    ):
        user, _, _ = user_with_org
        client.cookies.set("access_token", auth_token)
        resp = client.get("/api/cases/test-case-id")
        assert resp.status_code == 200
        data = resp.json()
        assert data["case_id"] == "test-case-id"
        assert data["user_id"] == user.id

    def test_public_health_without_auth_succeeds(self, client: TestClient):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_public_ask_without_auth_succeeds(self, client: TestClient):
        resp = client.post("/api/ask")
        assert resp.status_code == 200
        assert resp.json()["authenticated"] is False

    def test_public_ask_with_auth_sets_user(
        self, client: TestClient, auth_token: str
    ):
        client.cookies.set("access_token", auth_token)
        resp = client.post("/api/ask")
        assert resp.status_code == 200
        assert resp.json()["authenticated"] is True

    def test_public_deadlines_without_auth_succeeds(self, client: TestClient):
        resp = client.post("/api/deadlines")
        assert resp.status_code == 200

    def test_public_feedback_without_auth_succeeds(self, client: TestClient):
        resp = client.post("/api/feedback")
        assert resp.status_code == 200

    def test_expired_token_on_protected_path_returns_401(
        self, client: TestClient, user_with_org: tuple
    ):
        user, org, _ = user_with_org
        expired = create_access_token(
            user_id=user.id,
            org_id=org.id,
            role="owner",
            email=user.email,
            secret=SECRET,
            ttl=-1,
        )
        client.cookies.set("access_token", expired)
        resp = client.get("/api/cases")
        assert resp.status_code == 401

    def test_invalid_token_on_protected_path_returns_401(self, client: TestClient):
        client.cookies.set("access_token", "garbage-token")
        resp = client.get("/api/cases")
        assert resp.status_code == 401

    def test_expired_token_on_public_path_passes(
        self, client: TestClient, user_with_org: tuple
    ):
        user, org, _ = user_with_org
        expired = create_access_token(
            user_id=user.id,
            org_id=org.id,
            role="owner",
            email=user.email,
            secret=SECRET,
            ttl=-1,
        )
        client.cookies.set("access_token", expired)
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_no_session_manager_on_protected_path_returns_401(self):
        """When auth services are not initialized, protected paths return 401."""
        import employee_help.api.deps as deps

        old_sm = deps._session_manager
        try:
            deps._session_manager = None
            with TestClient(_make_test_app(), raise_server_exceptions=False) as tc:
                resp = tc.get("/api/cases")
                assert resp.status_code == 401
        finally:
            deps._session_manager = old_sm

    def test_no_session_manager_on_public_path_passes(self):
        """When auth services are not initialized, public paths still work."""
        import employee_help.api.deps as deps

        old_sm = deps._session_manager
        try:
            deps._session_manager = None
            with TestClient(_make_test_app(), raise_server_exceptions=False) as tc:
                resp = tc.get("/api/health")
                assert resp.status_code == 200
        finally:
            deps._session_manager = old_sm


# ── Rate limit key tests ──────────────────────────────────────


class TestRateLimitKey:
    """Test rate limit key selection."""

    def test_anonymous_uses_ip(self):
        request = MagicMock()
        request.state.user = None
        request.headers = {}
        request.client.host = "192.168.1.1"

        key = _get_rate_limit_key(request)
        assert key == "192.168.1.1"

    def test_authenticated_uses_user_id(self):
        request = MagicMock()
        request.state.user = AccessTokenClaims(
            sub="user-123",
            org="org-456",
            role="owner",
            email="test@example.com",
            iat=0,
            exp=0,
        )

        key = _get_rate_limit_key(request)
        assert key == "user:user-123"

    def test_no_state_attribute_uses_ip(self):
        """When request.state has no user attribute, fall back to IP."""
        request = MagicMock()
        request.state = SimpleNamespace()  # No 'user' attribute
        request.headers = {}
        request.client.host = "10.0.0.1"

        key = _get_rate_limit_key(request)
        assert key == "10.0.0.1"

    def test_forwarded_ip_used_for_anonymous(self):
        request = MagicMock()
        request.state.user = None
        request.headers = {"x-forwarded-for": "203.0.113.1, 10.0.0.1"}
        request.client.host = "10.0.0.1"

        key = _get_rate_limit_key(request)
        assert key == "203.0.113.1"


# ── Gate Test ─────────────────────────────────────────────────


class TestGateA14:
    """A1.4 gate: unauthenticated /api/cases -> 401, authenticated -> 200, /api/ask -> 200."""

    def test_gate(
        self, client: TestClient, auth_token: str, user_with_org: tuple
    ):
        user, org, _ = user_with_org

        # 1. Unauthenticated request to /api/cases -> 401
        resp = client.get("/api/cases")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Authentication required"

        # 2. Authenticated request to /api/cases -> 200
        client.cookies.set("access_token", auth_token)
        resp = client.get("/api/cases")
        assert resp.status_code == 200
        assert resp.json()["user_id"] == user.id

        # 3. Unauthenticated request to /api/ask -> 200 (public)
        client.cookies.clear()
        resp = client.post("/api/ask")
        assert resp.status_code == 200
        assert resp.json()["answer"] == "test"
