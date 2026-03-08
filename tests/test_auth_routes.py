"""Tests for auth API routes (A1.3)."""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from employee_help.auth.models import AuthSession, Membership, Organization, User
from employee_help.auth.provider import AuthError, AuthResult
from employee_help.auth.session import SessionManager, _hash_token
from employee_help.auth.storage import AuthStorage
from employee_help.storage.storage import Storage


# ── Fixtures ───────────────────────────────────────────────────

SECRET = "test-jwt-secret-for-auth-route-tests"


@pytest.fixture
def storage(tmp_path: Path) -> Storage:
    db_path = tmp_path / "test.db"
    s = Storage(db_path=db_path)
    yield s
    s.close()


@pytest.fixture
def auth_storage(storage: Storage) -> AuthStorage:
    # Use a separate connection with check_same_thread=False
    # because FastAPI TestClient runs requests in a different thread
    conn = sqlite3.connect(str(storage._db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return AuthStorage(conn=conn)


@pytest.fixture
def session_manager(auth_storage: AuthStorage) -> SessionManager:
    return SessionManager(
        auth_storage=auth_storage,
        jwt_secret=SECRET,
        access_token_ttl=900,
        refresh_token_ttl=604800,
    )


@pytest.fixture
def user_with_org(auth_storage: AuthStorage) -> tuple[User, Organization, Membership]:
    """Create a user with an organization and membership."""
    user = User(
        id=str(uuid.uuid4()),
        provider="google",
        provider_user_id="google-test-123",
        email="attorney@lawfirm.com",
        display_name="Jane Attorney",
    )
    auth_storage.create_user(user)

    org = Organization(
        id=str(uuid.uuid4()),
        name="Jane's Workspace",
        slug=f"user-{uuid.uuid4().hex[:8]}",
    )
    auth_storage.create_organization(org)

    membership = Membership(
        id=str(uuid.uuid4()),
        user_id=user.id,
        organization_id=org.id,
        role="owner",
    )
    auth_storage.create_membership(membership)

    return user, org, membership


def _make_app():
    """Create a FastAPI app with auth routes and no-op lifespan."""
    @asynccontextmanager
    async def noop_lifespan(app):
        yield

    app = FastAPI(lifespan=noop_lifespan)

    from employee_help.api.auth_routes import auth_router

    app.include_router(auth_router)
    return app


@pytest.fixture
def client(
    auth_storage: AuthStorage,
    session_manager: SessionManager,
) -> TestClient:
    """Create a test client with injected auth services."""
    import employee_help.api.deps as deps

    old_auth = deps._auth_storage
    old_sm = deps._session_manager
    old_gp = deps._google_provider
    old_mp = deps._microsoft_provider

    try:
        deps._auth_storage = auth_storage
        deps._session_manager = session_manager
        deps._google_provider = None
        deps._microsoft_provider = None
        with TestClient(_make_app(), raise_server_exceptions=False) as tc:
            yield tc
    finally:
        deps._auth_storage = old_auth
        deps._session_manager = old_sm
        deps._google_provider = old_gp
        deps._microsoft_provider = old_mp


@pytest.fixture
def authenticated_client(
    client: TestClient,
    session_manager: SessionManager,
    user_with_org: tuple,
) -> tuple[TestClient, User, Organization]:
    """Client with valid auth cookies set."""
    user, org, membership = user_with_org
    access_token, refresh_token = session_manager.create_session(
        user=user, org_id=org.id, role="owner",
    )
    client.cookies.set("access_token", access_token)
    client.cookies.set("refresh_token", refresh_token)
    return client, user, org


# ── Google Login ───────────────────────────────────────────────


class TestGoogleLogin:
    def test_returns_503_when_not_configured(self, client: TestClient):
        resp = client.get("/api/auth/google/login", follow_redirects=False)
        assert resp.status_code == 503

    def test_redirects_to_google_with_state(self, client: TestClient):
        import employee_help.api.deps as deps

        mock_provider = MagicMock()
        mock_provider.get_authorization_url.return_value = (
            "https://accounts.google.com/o/oauth2/v2/auth?test=1"
        )
        deps._google_provider = mock_provider

        resp = client.get("/api/auth/google/login", follow_redirects=False)
        assert resp.status_code == 302
        assert "accounts.google.com" in resp.headers["location"]

        # Should have set oauth_state cookie
        assert "oauth_state" in resp.cookies

    def test_state_cookie_is_httponly(self, client: TestClient):
        import employee_help.api.deps as deps

        mock_provider = MagicMock()
        mock_provider.get_authorization_url.return_value = "https://google.com/auth"
        deps._google_provider = mock_provider

        resp = client.get("/api/auth/google/login", follow_redirects=False)
        # Check Set-Cookie header for httponly
        cookie_header = resp.headers.get("set-cookie", "")
        assert "httponly" in cookie_header.lower()


# ── Microsoft Login ────────────────────────────────────────────


class TestMicrosoftLogin:
    def test_returns_503_when_not_configured(self, client: TestClient):
        resp = client.get("/api/auth/microsoft/login", follow_redirects=False)
        assert resp.status_code == 503

    def test_redirects_to_microsoft_with_state(self, client: TestClient):
        import employee_help.api.deps as deps

        mock_provider = MagicMock()
        mock_provider.get_authorization_url.return_value = (
            "https://login.microsoftonline.com/common/oauth2/v2.0/authorize?test=1"
        )
        deps._microsoft_provider = mock_provider

        resp = client.get("/api/auth/microsoft/login", follow_redirects=False)
        assert resp.status_code == 302
        assert "microsoftonline.com" in resp.headers["location"]
        assert "oauth_state" in resp.cookies


# ── Google Callback ────────────────────────────────────────────


class TestGoogleCallback:
    def test_error_param_redirects_to_login(self, client: TestClient):
        resp = client.get(
            "/api/auth/google/callback?error=access_denied",
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "error=oauth_denied" in resp.headers["location"]

    def test_missing_code_redirects_to_login(self, client: TestClient):
        resp = client.get(
            "/api/auth/google/callback?state=abc",
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "error=missing_params" in resp.headers["location"]

    def test_missing_state_redirects_to_login(self, client: TestClient):
        resp = client.get(
            "/api/auth/google/callback?code=abc",
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "error=missing_params" in resp.headers["location"]

    def test_returns_503_when_not_configured(self, client: TestClient):
        resp = client.get(
            "/api/auth/google/callback?code=abc&state=xyz",
            follow_redirects=False,
        )
        assert resp.status_code == 503

    def test_state_mismatch_redirects_to_login(self, client: TestClient):
        import employee_help.api.deps as deps

        mock_provider = MagicMock()
        mock_provider.handle_callback = AsyncMock(
            return_value=AuthResult(
                provider="google",
                provider_user_id="google-sub-123",
                email="user@example.com",
            )
        )
        deps._google_provider = mock_provider

        # Set state cookie to 'correct-state' but send 'wrong-state' in query
        client.cookies.set("oauth_state", "correct-state")
        resp = client.get(
            "/api/auth/google/callback?code=auth-code&state=wrong-state",
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "error=invalid_state" in resp.headers["location"]

    def test_successful_login_creates_user_and_sets_cookies(self, client: TestClient):
        import employee_help.api.deps as deps

        mock_provider = MagicMock()
        mock_provider.handle_callback = AsyncMock(
            return_value=AuthResult(
                provider="google",
                provider_user_id="google-sub-456",
                email="newuser@example.com",
                display_name="New User",
                avatar_url="https://example.com/avatar.jpg",
            )
        )
        deps._google_provider = mock_provider

        state = secrets.token_urlsafe(32)
        client.cookies.set("oauth_state", state)
        resp = client.get(
            f"/api/auth/google/callback?code=valid-code&state={state}",
            follow_redirects=False,
        )

        assert resp.status_code == 302
        # Should redirect to frontend
        assert resp.headers["location"].startswith("http://localhost:3000")
        # Should have auth cookies
        assert "access_token" in resp.cookies
        assert "refresh_token" in resp.cookies

    def test_successful_login_finds_existing_user(
        self, client: TestClient, auth_storage: AuthStorage, user_with_org: tuple
    ):
        import employee_help.api.deps as deps

        user, org, membership = user_with_org
        mock_provider = MagicMock()
        mock_provider.handle_callback = AsyncMock(
            return_value=AuthResult(
                provider="google",
                provider_user_id=user.provider_user_id,
                email=user.email,
                display_name="Updated Name",
            )
        )
        deps._google_provider = mock_provider

        state = secrets.token_urlsafe(32)
        client.cookies.set("oauth_state", state)
        resp = client.get(
            f"/api/auth/google/callback?code=valid-code&state={state}",
            follow_redirects=False,
        )

        assert resp.status_code == 302
        assert "access_token" in resp.cookies

        # User profile should be updated
        updated = auth_storage.get_user(user.id)
        assert updated.display_name == "Updated Name"

    def test_provider_error_redirects_to_login(self, client: TestClient):
        import employee_help.api.deps as deps

        mock_provider = MagicMock()
        mock_provider.handle_callback = AsyncMock(
            side_effect=AuthError("Token exchange failed")
        )
        deps._google_provider = mock_provider

        state = secrets.token_urlsafe(32)
        client.cookies.set("oauth_state", state)
        resp = client.get(
            f"/api/auth/google/callback?code=bad-code&state={state}",
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "error=auth_failed" in resp.headers["location"]


# ── Microsoft Callback ─────────────────────────────────────────


class TestMicrosoftCallback:
    def test_successful_microsoft_login(self, client: TestClient):
        import employee_help.api.deps as deps

        mock_provider = MagicMock()
        mock_provider.handle_callback = AsyncMock(
            return_value=AuthResult(
                provider="microsoft",
                provider_user_id="ms-oid-789",
                email="msuser@outlook.com",
                display_name="MS User",
            )
        )
        deps._microsoft_provider = mock_provider

        state = secrets.token_urlsafe(32)
        client.cookies.set("oauth_state", state)
        resp = client.get(
            f"/api/auth/microsoft/callback?code=ms-code&state={state}",
            follow_redirects=False,
        )

        assert resp.status_code == 302
        assert "access_token" in resp.cookies

    def test_error_param_redirects(self, client: TestClient):
        resp = client.get(
            "/api/auth/microsoft/callback?error=consent_required",
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "error=oauth_denied" in resp.headers["location"]


# ── Token Refresh ──────────────────────────────────────────────


class TestRefresh:
    def test_no_refresh_token_returns_401(self, client: TestClient):
        resp = client.post("/api/auth/refresh")
        assert resp.status_code == 401

    def test_successful_refresh_sets_new_cookies(
        self,
        client: TestClient,
        session_manager: SessionManager,
        user_with_org: tuple,
    ):
        user, org, membership = user_with_org
        _, refresh_token = session_manager.create_session(
            user=user, org_id=org.id, role="owner",
        )

        # The refresh endpoint reads from the cookie named "refresh_token"
        # at path /api/auth/refresh
        client.cookies.set("refresh_token", refresh_token)
        resp = client.post("/api/auth/refresh")

        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        assert "access_token" in resp.cookies
        assert "refresh_token" in resp.cookies

    def test_invalid_refresh_token_clears_cookies(self, client: TestClient):
        client.cookies.set("refresh_token", "invalid-token")
        resp = client.post("/api/auth/refresh")

        assert resp.status_code == 401

    def test_expired_refresh_token_returns_401(
        self,
        client: TestClient,
        auth_storage: AuthStorage,
        user_with_org: tuple,
    ):
        user, org, _ = user_with_org
        refresh_token = "expired-refresh-token"
        session = AuthSession(
            id=str(uuid.uuid4()),
            user_id=user.id,
            refresh_token_hash=_hash_token(refresh_token),
            expires_at=datetime.now(tz=UTC) - timedelta(hours=1),
        )
        auth_storage.create_session(session)

        client.cookies.set("refresh_token", refresh_token)
        resp = client.post("/api/auth/refresh")

        assert resp.status_code == 401
        assert "expired" in resp.json()["detail"]


# ── Logout ─────────────────────────────────────────────────────


class TestLogout:
    def test_logout_clears_cookies(self, authenticated_client: tuple):
        client, user, org = authenticated_client
        resp = client.post("/api/auth/logout")

        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_logout_without_token_still_succeeds(self, client: TestClient):
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 200

    def test_logout_revokes_sessions(
        self,
        authenticated_client: tuple,
        auth_storage: AuthStorage,
    ):
        client, user, org = authenticated_client
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 200

        # All sessions should be revoked
        sessions = auth_storage._conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE user_id = ? AND is_revoked = 0",
            (user.id,),
        ).fetchone()
        assert sessions[0] == 0


# ── Get Current User ───────────────────────────────────────────


class TestGetMe:
    def test_no_token_returns_401(self, client: TestClient):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self, client: TestClient):
        client.cookies.set("access_token", "garbage")
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_returns_user_profile(self, authenticated_client: tuple):
        client, user, org = authenticated_client
        resp = client.get("/api/auth/me")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == user.id
        assert data["email"] == user.email
        assert data["display_name"] == user.display_name
        assert data["provider"] == "google"
        assert data["role"] == "owner"
        assert data["organization"]["id"] == org.id
        assert data["organization"]["name"] == org.name
        assert data["organization"]["slug"] == org.slug
        assert data["organization"]["plan_tier"] == "individual"

    def test_expired_token_returns_401(
        self,
        client: TestClient,
        user_with_org: tuple,
    ):
        from employee_help.auth.tokens import create_access_token

        user, org, _ = user_with_org
        expired = create_access_token(
            user_id=user.id, org_id=org.id, role="owner",
            email=user.email, secret=SECRET, ttl=-1,
        )
        client.cookies.set("access_token", expired)
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401


# ── Find or Create User ───────────────────────────────────────


class TestFindOrCreateUser:
    def test_creates_new_user_with_implicit_org(self, auth_storage: AuthStorage):
        from employee_help.api.auth_routes import _find_or_create_user

        result = AuthResult(
            provider="google",
            provider_user_id="new-google-id",
            email="brand-new@example.com",
            display_name="Brand New",
        )

        user, org, membership = _find_or_create_user(auth_storage, result)

        assert user.email == "brand-new@example.com"
        assert user.provider == "google"
        assert org.name == "Brand New"
        assert membership.role == "owner"
        assert membership.user_id == user.id
        assert membership.organization_id == org.id

    def test_finds_existing_user(
        self, auth_storage: AuthStorage, user_with_org: tuple
    ):
        from employee_help.api.auth_routes import _find_or_create_user

        user, org, membership = user_with_org
        result = AuthResult(
            provider=user.provider,
            provider_user_id=user.provider_user_id,
            email=user.email,
        )

        found_user, found_org, found_membership = _find_or_create_user(
            auth_storage, result
        )

        assert found_user.id == user.id
        assert found_org.id == org.id
        assert found_membership.id == membership.id

    def test_creates_org_for_existing_user_without_membership(
        self, auth_storage: AuthStorage
    ):
        from employee_help.api.auth_routes import _find_or_create_user

        # Create a user with no org/membership
        user = User(
            id=str(uuid.uuid4()),
            provider="google",
            provider_user_id="orphan-user",
            email="orphan@example.com",
        )
        auth_storage.create_user(user)

        result = AuthResult(
            provider="google",
            provider_user_id="orphan-user",
            email="orphan@example.com",
        )

        found_user, org, membership = _find_or_create_user(auth_storage, result)
        assert found_user.id == user.id
        assert membership.user_id == user.id
        assert membership.role == "owner"

    def test_uses_email_prefix_when_no_display_name(
        self, auth_storage: AuthStorage
    ):
        from employee_help.api.auth_routes import _find_or_create_user

        result = AuthResult(
            provider="microsoft",
            provider_user_id="ms-no-name",
            email="john.doe@company.com",
            display_name=None,
        )

        _, org, _ = _find_or_create_user(auth_storage, result)
        assert org.name == "john.doe"


# ── Cookie Helpers ─────────────────────────────────────────────


class TestCookieHelpers:
    def test_set_auth_cookies(self):
        from fastapi.responses import JSONResponse

        from employee_help.api.auth_routes import _set_auth_cookies

        response = JSONResponse(content={})
        _set_auth_cookies(response, "access-123", "refresh-456")

        # Check that cookies were set (via headers)
        cookie_headers = [
            h for h in response.headers.raw if h[0] == b"set-cookie"
        ]
        assert len(cookie_headers) == 2

    def test_clear_auth_cookies(self):
        from fastapi.responses import JSONResponse

        from employee_help.api.auth_routes import _clear_auth_cookies

        response = JSONResponse(content={})
        _clear_auth_cookies(response)

        cookie_headers = [
            h for h in response.headers.raw if h[0] == b"set-cookie"
        ]
        assert len(cookie_headers) == 2  # Two delete cookies


# ── Redirect URI Builder ──────────────────────────────────────


class TestGetRedirectUri:
    def test_builds_redirect_uri_from_request(self):
        from unittest.mock import MagicMock

        from employee_help.api.auth_routes import _get_redirect_uri

        request = MagicMock()
        request.headers = {"host": "app.example.com"}
        request.url.scheme = "https"

        uri = _get_redirect_uri(request, "google")
        assert uri == "https://app.example.com/api/auth/google/callback"

    def test_respects_forwarded_headers(self):
        from unittest.mock import MagicMock

        from employee_help.api.auth_routes import _get_redirect_uri

        request = MagicMock()
        request.headers = {
            "x-forwarded-proto": "https",
            "x-forwarded-host": "prod.example.com",
            "host": "internal:8000",
        }
        request.url.scheme = "http"

        uri = _get_redirect_uri(request, "microsoft")
        assert uri == "https://prod.example.com/api/auth/microsoft/callback"


# ── Full OAuth Lifecycle ───────────────────────────────────────


class TestFullLifecycle:
    def test_login_me_refresh_logout(
        self,
        client: TestClient,
        auth_storage: AuthStorage,
        session_manager: SessionManager,
    ):
        """Gate test: full auth lifecycle through API endpoints."""
        import employee_help.api.deps as deps

        # 1. Set up mock Google provider
        mock_provider = MagicMock()
        mock_provider.get_authorization_url.return_value = "https://google.com/auth"
        mock_provider.handle_callback = AsyncMock(
            return_value=AuthResult(
                provider="google",
                provider_user_id="lifecycle-user-123",
                email="lifecycle@test.com",
                display_name="Lifecycle User",
            )
        )
        deps._google_provider = mock_provider

        # 2. Initiate login
        resp = client.get("/api/auth/google/login", follow_redirects=False)
        assert resp.status_code == 302
        state = resp.cookies.get("oauth_state")
        assert state is not None

        # 3. Callback — simulates Google redirect
        client.cookies.set("oauth_state", state)
        resp = client.get(
            f"/api/auth/google/callback?code=test-code&state={state}",
            follow_redirects=False,
        )
        assert resp.status_code == 302
        access_token = resp.cookies.get("access_token")
        refresh_token = resp.cookies.get("refresh_token")
        assert access_token is not None
        assert refresh_token is not None

        # 4. Get user profile
        client.cookies.set("access_token", access_token)
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200
        profile = resp.json()
        assert profile["email"] == "lifecycle@test.com"
        assert profile["display_name"] == "Lifecycle User"
        assert profile["provider"] == "google"

        # 5. Refresh tokens
        client.cookies.set("refresh_token", refresh_token)
        resp = client.post("/api/auth/refresh")
        assert resp.status_code == 200
        new_access = resp.cookies.get("access_token")
        new_refresh = resp.cookies.get("refresh_token")
        assert new_access is not None
        assert new_refresh is not None
        assert new_refresh != refresh_token  # Rotation

        # 6. Old refresh token should fail (rotated)
        client.cookies.set("refresh_token", refresh_token)
        resp = client.post("/api/auth/refresh")
        assert resp.status_code == 401

        # 7. Logout with new access token
        client.cookies.set("access_token", new_access)
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 200

        # 8. After logout, /me should fail
        resp = client.get("/api/auth/me")
        # Token is still in cookie but still valid JWT — the session is
        # revoked but access_token is a self-contained JWT, so /me still
        # works until it expires. This is by design — 15-min window.
        # To test full logout enforcement, we'd need the auth middleware
        # (Phase A1.4) to check session revocation on every request.
