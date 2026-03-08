"""Tests for auth middleware (A1.4) and dual-mode rate limiting (A2.4)."""

from __future__ import annotations

import sqlite3
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from employee_help.api.main import (
    _budget_exceeded_response,
    _check_daily_budget,
    _check_rate_limit,
    _daily_budget_store,
    _get_rate_limit_key,
    _increment_daily_budget,
    _is_authenticated,
    _rate_limit_response,
    _requires_auth,
    auth_middleware,
    rate_limit_middleware,
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


# ── _is_authenticated tests ──────────────────────────────────


class TestIsAuthenticated:
    """Test the _is_authenticated helper."""

    def test_anonymous_returns_false(self):
        request = MagicMock()
        request.state.user = None
        assert _is_authenticated(request) is False

    def test_authenticated_returns_true(self):
        request = MagicMock()
        request.state.user = AccessTokenClaims(
            sub="user-1", org="org-1", role="owner", email="a@b.com", iat=0, exp=0
        )
        assert _is_authenticated(request) is True

    def test_no_state_attribute_returns_false(self):
        request = MagicMock()
        request.state = SimpleNamespace()
        assert _is_authenticated(request) is False


# ── _check_rate_limit unit tests ─────────────────────────────


class TestCheckRateLimit:
    """Test the _check_rate_limit helper."""

    def test_first_request_allowed(self):
        store: dict[str, list[float]] = defaultdict(list)
        allowed, remaining, _ = _check_rate_limit(store, "ip:1.2.3.4", 5, 60, 1000.0)
        assert allowed is True
        assert remaining == 4

    def test_at_limit_denied(self):
        store: dict[str, list[float]] = defaultdict(list)
        # Fill to limit
        for i in range(5):
            _check_rate_limit(store, "ip:1.2.3.4", 5, 60, 1000.0 + i)
        allowed, remaining, _ = _check_rate_limit(store, "ip:1.2.3.4", 5, 60, 1004.5)
        assert allowed is False
        assert remaining == 0

    def test_window_expiry_resets(self):
        store: dict[str, list[float]] = defaultdict(list)
        for i in range(5):
            _check_rate_limit(store, "ip:1.2.3.4", 5, 60, 1000.0 + i)
        # After window expires for all entries (latest at 1004 + 60 = 1064)
        allowed, remaining, _ = _check_rate_limit(store, "ip:1.2.3.4", 5, 60, 1065.0)
        assert allowed is True
        assert remaining == 4

    def test_different_keys_independent(self):
        store: dict[str, list[float]] = defaultdict(list)
        for i in range(5):
            _check_rate_limit(store, "user:alice", 5, 60, 1000.0 + i)
        # Alice is at limit, Bob is not
        allowed_alice, _, _ = _check_rate_limit(store, "user:alice", 5, 60, 1004.5)
        allowed_bob, remaining_bob, _ = _check_rate_limit(store, "user:bob", 5, 60, 1004.5)
        assert allowed_alice is False
        assert allowed_bob is True
        assert remaining_bob == 4

    def test_higher_limit_allows_more(self):
        store: dict[str, list[float]] = defaultdict(list)
        for i in range(5):
            _check_rate_limit(store, "user:auth", 20, 60, 1000.0 + i)
        # At 5 requests with limit=20, still allowed
        allowed, remaining, _ = _check_rate_limit(store, "user:auth", 20, 60, 1005.0)
        assert allowed is True
        assert remaining == 14


# ── _check_daily_budget unit tests ───────────────────────────


class TestCheckDailyBudget:
    """Test per-key daily budget."""

    def setup_method(self):
        _daily_budget_store.clear()

    def test_fresh_budget_allowed(self):
        allowed, remaining = _check_daily_budget("global", 500)
        assert allowed is True
        assert remaining == 500

    def test_increment_reduces_remaining(self):
        _check_daily_budget("global", 500)
        _increment_daily_budget("global")
        _increment_daily_budget("global")
        allowed, remaining = _check_daily_budget("global", 500)
        assert allowed is True
        assert remaining == 498

    def test_budget_exceeded(self):
        _check_daily_budget("global", 2)
        _increment_daily_budget("global")
        _increment_daily_budget("global")
        allowed, remaining = _check_daily_budget("global", 2)
        assert allowed is False
        assert remaining == 0

    def test_per_user_budgets_independent(self):
        """Two users have independent daily budgets."""
        _check_daily_budget("user:alice", 3)
        _increment_daily_budget("user:alice")
        _increment_daily_budget("user:alice")
        _increment_daily_budget("user:alice")
        # Alice exhausted, Bob fresh
        allowed_alice, _ = _check_daily_budget("user:alice", 3)
        allowed_bob, remaining_bob = _check_daily_budget("user:bob", 3)
        assert allowed_alice is False
        assert allowed_bob is True
        assert remaining_bob == 3

    def test_authenticated_higher_limit(self):
        """Authenticated users get higher daily budget than global."""
        # Global budget: 2
        _check_daily_budget("global", 2)
        _increment_daily_budget("global")
        _increment_daily_budget("global")
        # Auth budget: 5
        _check_daily_budget("user:alice", 5)
        _increment_daily_budget("user:alice")
        _increment_daily_budget("user:alice")
        # Global exhausted, auth still has room
        allowed_global, _ = _check_daily_budget("global", 2)
        allowed_auth, remaining_auth = _check_daily_budget("user:alice", 5)
        assert allowed_global is False
        assert allowed_auth is True
        assert remaining_auth == 3


# ── Response helper tests ────────────────────────────────────


class TestResponseHelpers:
    """Test rate limit response builders."""

    def test_rate_limit_response_status(self):
        resp = _rate_limit_response("Wait.", 5, 1000.0)
        assert resp.status_code == 429
        assert b"Rate limit exceeded" in resp.body

    def test_rate_limit_response_headers(self):
        resp = _rate_limit_response("Wait.", 10, 1060.0)
        assert resp.headers["X-RateLimit-Limit"] == "10"
        assert resp.headers["X-RateLimit-Remaining"] == "0"

    def test_budget_exceeded_response(self):
        resp = _budget_exceeded_response()
        assert resp.status_code == 429
        assert b"Daily query budget exceeded" in resp.body
        assert resp.headers["Retry-After"] == "3600"


# ── Dual-mode rate limiting integration tests (A2.4) ─────────


def _make_rate_limit_test_app() -> FastAPI:
    """Create a test app with both auth + rate limit middleware."""

    @asynccontextmanager
    async def noop_lifespan(app):
        yield

    test_app = FastAPI(lifespan=noop_lifespan)
    # Order matters: rate_limit first (innermost), auth second (outermost on request)
    test_app.middleware("http")(rate_limit_middleware)
    test_app.middleware("http")(auth_middleware)

    @test_app.post("/api/ask")
    async def ask(request: Request):
        return JSONResponse(content={"answer": "test"})

    @test_app.post("/api/discovery/suggest")
    async def discovery_suggest(request: Request):
        return JSONResponse(content={"ok": True})

    @test_app.post("/api/objections/parse")
    async def objections_parse(request: Request):
        return JSONResponse(content={"ok": True})

    @test_app.get("/api/health")
    async def health():
        return JSONResponse(content={"status": "ok"})

    return test_app


@pytest.fixture
def rate_client(session_manager: SessionManager) -> TestClient:
    """Client with both auth and rate limit middleware."""
    import employee_help.api.deps as deps
    from employee_help.api.main import (
        _daily_budget_store,
        _discovery_rate_store,
        _objection_parse_rate_store,
        _rate_limit_store,
    )

    old_sm = deps._session_manager
    _rate_limit_store.clear()
    _discovery_rate_store.clear()
    _objection_parse_rate_store.clear()
    _daily_budget_store.clear()
    try:
        deps._session_manager = session_manager
        with TestClient(
            _make_rate_limit_test_app(), raise_server_exceptions=False
        ) as tc:
            yield tc
    finally:
        deps._session_manager = old_sm
        _rate_limit_store.clear()
        _discovery_rate_store.clear()
        _objection_parse_rate_store.clear()
        _daily_budget_store.clear()


class TestDualModeRateLimiting:
    """A2.4: Authenticated users get higher rate limits."""

    def test_anonymous_rate_limited_at_5(self, rate_client: TestClient):
        """Anonymous /api/ask limited to 5/min (RATE_LIMIT_MAX default)."""
        for i in range(5):
            resp = rate_client.post("/api/ask", json={"query": f"q{i}"})
            assert resp.status_code == 200, f"Request {i+1} should succeed"

        resp = rate_client.post("/api/ask", json={"query": "over limit"})
        assert resp.status_code == 429

    def test_authenticated_rate_limited_at_20(
        self, rate_client: TestClient, auth_token: str
    ):
        """Authenticated /api/ask limited to 20/min (AUTH_RATE_LIMIT_MAX default)."""
        rate_client.cookies.set("access_token", auth_token)
        for i in range(20):
            resp = rate_client.post("/api/ask", json={"query": f"q{i}"})
            assert resp.status_code == 200, f"Request {i+1} should succeed"

        resp = rate_client.post("/api/ask", json={"query": "over limit"})
        assert resp.status_code == 429

    def test_authenticated_exceeds_anonymous_limit_still_ok(
        self, rate_client: TestClient, auth_token: str
    ):
        """Authenticated user can make >5 requests (anon limit), proving higher tier."""
        rate_client.cookies.set("access_token", auth_token)
        for i in range(10):
            resp = rate_client.post("/api/ask", json={"query": f"q{i}"})
            assert resp.status_code == 200

    def test_two_users_behind_same_ip_independent(
        self, rate_client: TestClient, session_manager: SessionManager, auth_storage: AuthStorage
    ):
        """Two authenticated users behind the same IP get independent limits."""
        # Create User A
        user_a = User(
            id=str(uuid.uuid4()), provider="google",
            provider_user_id="rl-user-a", email="a@firm.com", display_name="A",
        )
        auth_storage.create_user(user_a)
        org_a = Organization(id=str(uuid.uuid4()), name="Firm A", slug="firm-a")
        auth_storage.create_organization(org_a)
        auth_storage.create_membership(Membership(
            id=str(uuid.uuid4()), user_id=user_a.id,
            organization_id=org_a.id, role="owner",
        ))
        token_a, _ = session_manager.create_session(user=user_a, org_id=org_a.id, role="owner")

        # Create User B
        user_b = User(
            id=str(uuid.uuid4()), provider="google",
            provider_user_id="rl-user-b", email="b@firm.com", display_name="B",
        )
        auth_storage.create_user(user_b)
        org_b = Organization(id=str(uuid.uuid4()), name="Firm B", slug="firm-b")
        auth_storage.create_organization(org_b)
        auth_storage.create_membership(Membership(
            id=str(uuid.uuid4()), user_id=user_b.id,
            organization_id=org_b.id, role="owner",
        ))
        token_b, _ = session_manager.create_session(user=user_b, org_id=org_b.id, role="owner")

        # User A makes 15 requests
        rate_client.cookies.set("access_token", token_a)
        for i in range(15):
            resp = rate_client.post("/api/ask", json={"query": f"a-q{i}"})
            assert resp.status_code == 200

        # User B still has full quota
        rate_client.cookies.set("access_token", token_b)
        for i in range(15):
            resp = rate_client.post("/api/ask", json={"query": f"b-q{i}"})
            assert resp.status_code == 200

    def test_rate_limit_headers_reflect_auth_limit(
        self, rate_client: TestClient, auth_token: str
    ):
        """Rate limit headers show authenticated limit (20), not anonymous (5)."""
        rate_client.cookies.set("access_token", auth_token)
        resp = rate_client.post("/api/ask", json={"query": "test"})
        assert resp.status_code == 200
        assert resp.headers["X-RateLimit-Limit"] == "20"


class TestDualModePerUserBudget:
    """A2.4: Daily budget is per-user for authenticated, global for anonymous."""

    def test_anonymous_uses_global_budget(self, rate_client: TestClient):
        """Anonymous requests share a global daily budget."""
        import employee_help.api.main as main_mod

        old_budget = main_mod.DAILY_QUERY_BUDGET
        try:
            main_mod.DAILY_QUERY_BUDGET = 3
            for i in range(3):
                resp = rate_client.post("/api/ask", json={"query": f"q{i}"})
                assert resp.status_code == 200
            resp = rate_client.post("/api/ask", json={"query": "over"})
            assert resp.status_code == 429
            assert "budget" in resp.json()["detail"].lower()
        finally:
            main_mod.DAILY_QUERY_BUDGET = old_budget

    def test_authenticated_uses_per_user_budget(
        self, rate_client: TestClient, auth_token: str
    ):
        """Authenticated user has own daily budget, separate from global."""
        import employee_help.api.main as main_mod

        old_budget = main_mod.DAILY_QUERY_BUDGET
        old_auth_budget = main_mod.AUTH_DAILY_QUERY_BUDGET
        try:
            main_mod.DAILY_QUERY_BUDGET = 2
            main_mod.AUTH_DAILY_QUERY_BUDGET = 5
            # Exhaust global budget as anonymous
            for i in range(2):
                resp = rate_client.post("/api/ask", json={"query": f"anon-{i}"})
                assert resp.status_code == 200
            resp = rate_client.post("/api/ask", json={"query": "anon-over"})
            assert resp.status_code == 429

            # Authenticated user still has their own budget
            rate_client.cookies.set("access_token", auth_token)
            for i in range(5):
                resp = rate_client.post("/api/ask", json={"query": f"auth-{i}"})
                assert resp.status_code == 200
            resp = rate_client.post("/api/ask", json={"query": "auth-over"})
            assert resp.status_code == 429
        finally:
            main_mod.DAILY_QUERY_BUDGET = old_budget
            main_mod.AUTH_DAILY_QUERY_BUDGET = old_auth_budget


# ── Gate A2.4 ────────────────────────────────────────────────


class TestGateA24:
    """A2.4 gate: authenticated gets higher limits, two users behind same IP independent."""

    def test_gate(
        self,
        rate_client: TestClient,
        auth_token: str,
        session_manager: SessionManager,
        auth_storage: AuthStorage,
    ):
        # 1. Anonymous limited at 5
        for i in range(5):
            resp = rate_client.post("/api/ask", json={"query": f"q{i}"})
            assert resp.status_code == 200
        resp = rate_client.post("/api/ask", json={"query": "over"})
        assert resp.status_code == 429

        # 2. Authenticated user gets higher limit (can do >5)
        rate_client.cookies.set("access_token", auth_token)
        for i in range(10):
            resp = rate_client.post("/api/ask", json={"query": f"auth-{i}"})
            assert resp.status_code == 200

        # 3. Second authenticated user has independent limits
        user_b = User(
            id=str(uuid.uuid4()), provider="google",
            provider_user_id="gate-user-b", email="gate-b@firm.com",
            display_name="Gate B",
        )
        auth_storage.create_user(user_b)
        org_b = Organization(id=str(uuid.uuid4()), name="Gate B Org", slug="gate-b")
        auth_storage.create_organization(org_b)
        auth_storage.create_membership(Membership(
            id=str(uuid.uuid4()), user_id=user_b.id,
            organization_id=org_b.id, role="owner",
        ))
        token_b, _ = session_manager.create_session(
            user=user_b, org_id=org_b.id, role="owner"
        )
        rate_client.cookies.set("access_token", token_b)
        for i in range(10):
            resp = rate_client.post("/api/ask", json={"query": f"b-{i}"})
            assert resp.status_code == 200
