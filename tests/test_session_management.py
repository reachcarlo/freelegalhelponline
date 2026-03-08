"""Tests for session management UI endpoints (A3.2)."""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from employee_help.auth.models import AuthSession, Membership, Organization, User
from employee_help.auth.session import SessionManager, _hash_token
from employee_help.auth.storage import AuthStorage
from employee_help.auth.tokens import create_access_token, validate_access_token
from employee_help.storage.storage import Storage


# ── Fixtures ───────────────────────────────────────────────────

SECRET = "test-jwt-secret-for-session-mgmt-tests"


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
    return SessionManager(
        auth_storage=auth_storage,
        jwt_secret=SECRET,
        access_token_ttl=900,
        refresh_token_ttl=604800,
    )


@pytest.fixture
def user_with_org(auth_storage: AuthStorage) -> tuple[User, Organization, Membership]:
    user = User(
        id=str(uuid.uuid4()),
        provider="google",
        provider_user_id="google-session-123",
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
    @asynccontextmanager
    async def noop_lifespan(app):
        yield

    app = FastAPI(lifespan=noop_lifespan)
    from employee_help.api.auth_routes import auth_router

    app.include_router(auth_router)
    return app


@pytest.fixture
def client(auth_storage: AuthStorage, session_manager: SessionManager) -> TestClient:
    import employee_help.api.deps as deps

    old_auth = deps._auth_storage
    old_sm = deps._session_manager
    old_gp = deps._google_provider
    old_mp = deps._microsoft_provider
    old_al = deps._audit_logger

    try:
        deps._auth_storage = auth_storage
        deps._session_manager = session_manager
        deps._google_provider = None
        deps._microsoft_provider = None
        deps._audit_logger = None
        with TestClient(_make_app(), raise_server_exceptions=False) as tc:
            yield tc
    finally:
        deps._auth_storage = old_auth
        deps._session_manager = old_sm
        deps._google_provider = old_gp
        deps._microsoft_provider = old_mp
        deps._audit_logger = old_al


@pytest.fixture
def auth_client(
    client: TestClient,
    session_manager: SessionManager,
    user_with_org: tuple,
) -> tuple[TestClient, User, Organization]:
    user, org, membership = user_with_org
    access_token, refresh_token = session_manager.create_session(
        user=user,
        org_id=org.id,
        role="owner",
        ip_address="10.0.0.1",
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120",
    )
    client.cookies.set("access_token", access_token)
    client.cookies.set("refresh_token", refresh_token)
    return client, user, org


# ── Token sid claim tests ──────────────────────────────────────


class TestAccessTokenSid:
    def test_create_token_with_session_id(self):
        token = create_access_token(
            user_id="u1", org_id="o1", role="owner",
            email="t@t.com", secret=SECRET, session_id="sess-123",
        )
        claims = validate_access_token(token, SECRET)
        assert claims is not None
        assert claims.sid == "sess-123"

    def test_create_token_without_session_id(self):
        token = create_access_token(
            user_id="u1", org_id="o1", role="owner",
            email="t@t.com", secret=SECRET,
        )
        claims = validate_access_token(token, SECRET)
        assert claims is not None
        assert claims.sid == ""

    def test_session_manager_includes_sid(self, session_manager, user_with_org):
        user, org, _ = user_with_org
        access_token, _ = session_manager.create_session(
            user=user, org_id=org.id, role="owner",
        )
        claims = validate_access_token(access_token, SECRET)
        assert claims is not None
        assert claims.sid != ""
        # Verify it's a valid UUID
        uuid.UUID(claims.sid)

    def test_refresh_rotates_sid(self, session_manager, user_with_org):
        user, org, _ = user_with_org
        access1, refresh1 = session_manager.create_session(
            user=user, org_id=org.id, role="owner",
        )
        claims1 = validate_access_token(access1, SECRET)

        access2, refresh2 = session_manager.refresh_session(refresh1)
        claims2 = validate_access_token(access2, SECRET)

        assert claims1.sid != claims2.sid


# ── AuthStorage.get_user_sessions tests ────────────────────────


class TestGetUserSessions:
    def test_returns_active_sessions(self, auth_storage, user_with_org):
        user, _, _ = user_with_org
        s1 = AuthSession(
            id=str(uuid.uuid4()), user_id=user.id,
            refresh_token_hash="hash1",
            expires_at=datetime.now(tz=UTC) + timedelta(days=7),
            user_agent="Chrome",
        )
        s2 = AuthSession(
            id=str(uuid.uuid4()), user_id=user.id,
            refresh_token_hash="hash2",
            expires_at=datetime.now(tz=UTC) + timedelta(days=7),
            user_agent="Firefox",
        )
        auth_storage.create_session(s1)
        auth_storage.create_session(s2)

        sessions = auth_storage.get_user_sessions(user.id)
        assert len(sessions) == 2

    def test_excludes_revoked(self, auth_storage, user_with_org):
        user, _, _ = user_with_org
        s = AuthSession(
            id=str(uuid.uuid4()), user_id=user.id,
            refresh_token_hash="hash-revoked",
            expires_at=datetime.now(tz=UTC) + timedelta(days=7),
        )
        auth_storage.create_session(s)
        auth_storage.revoke_session(s.id)

        sessions = auth_storage.get_user_sessions(user.id)
        assert len(sessions) == 0

    def test_excludes_expired(self, auth_storage, user_with_org):
        user, _, _ = user_with_org
        s = AuthSession(
            id=str(uuid.uuid4()), user_id=user.id,
            refresh_token_hash="hash-expired",
            expires_at=datetime.now(tz=UTC) - timedelta(hours=1),
        )
        auth_storage.create_session(s)

        sessions = auth_storage.get_user_sessions(user.id)
        assert len(sessions) == 0

    def test_excludes_other_users(self, auth_storage, user_with_org):
        user, _, _ = user_with_org
        other_user = User(
            id=str(uuid.uuid4()), provider="google",
            provider_user_id="google-other-456", email="other@firm.com",
        )
        auth_storage.create_user(other_user)

        s = AuthSession(
            id=str(uuid.uuid4()), user_id=other_user.id,
            refresh_token_hash="hash-other",
            expires_at=datetime.now(tz=UTC) + timedelta(days=7),
        )
        auth_storage.create_session(s)

        sessions = auth_storage.get_user_sessions(user.id)
        assert len(sessions) == 0

    def test_ordered_by_last_used_desc(self, auth_storage, user_with_org):
        user, _, _ = user_with_org
        old = AuthSession(
            id=str(uuid.uuid4()), user_id=user.id,
            refresh_token_hash="hash-old",
            expires_at=datetime.now(tz=UTC) + timedelta(days=7),
            last_used_at=datetime.now(tz=UTC) - timedelta(hours=2),
        )
        new = AuthSession(
            id=str(uuid.uuid4()), user_id=user.id,
            refresh_token_hash="hash-new",
            expires_at=datetime.now(tz=UTC) + timedelta(days=7),
            last_used_at=datetime.now(tz=UTC),
        )
        auth_storage.create_session(old)
        auth_storage.create_session(new)

        sessions = auth_storage.get_user_sessions(user.id)
        assert sessions[0].id == new.id
        assert sessions[1].id == old.id


# ── GET /api/auth/sessions tests ───────────────────────────────


class TestListSessions:
    def test_requires_auth(self, client: TestClient):
        resp = client.get("/api/auth/sessions")
        assert resp.status_code == 401

    def test_returns_sessions(self, auth_client):
        tc, user, org = auth_client
        resp = tc.get("/api/auth/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert "sessions" in data
        # At least the current session
        assert len(data["sessions"]) >= 1

    def test_marks_current_session(self, auth_client):
        tc, user, org = auth_client
        resp = tc.get("/api/auth/sessions")
        data = resp.json()
        current = [s for s in data["sessions"] if s["is_current"]]
        assert len(current) == 1

    def test_includes_device_info(self, auth_client):
        tc, _, _ = auth_client
        resp = tc.get("/api/auth/sessions")
        session = resp.json()["sessions"][0]
        assert "browser" in session
        assert "os" in session
        assert "device" in session
        assert "ip_address" in session
        assert "created_at" in session
        assert "last_used_at" in session

    def test_parses_chrome_user_agent(self, auth_client):
        tc, _, _ = auth_client
        resp = tc.get("/api/auth/sessions")
        session = resp.json()["sessions"][0]
        assert session["browser"] == "Chrome"
        assert session["os"] == "macOS"
        assert session["device"] == "Desktop"


# ── DELETE /api/auth/sessions/{id} tests ───────────────────────


class TestRevokeSession:
    def test_requires_auth(self, client: TestClient):
        resp = client.delete("/api/auth/sessions/some-id")
        assert resp.status_code == 401

    def test_revokes_other_session(
        self, auth_client, session_manager, user_with_org,
    ):
        tc, user, org = auth_client
        # Create a second session
        access2, _ = session_manager.create_session(
            user=user, org_id=org.id, role="owner",
            user_agent="Firefox/100",
        )
        claims2 = validate_access_token(access2, SECRET)

        resp = tc.delete(f"/api/auth/sessions/{claims2.sid}")
        assert resp.status_code == 200

        # Verify it's gone from the list
        resp2 = tc.get("/api/auth/sessions")
        ids = [s["id"] for s in resp2.json()["sessions"]]
        assert claims2.sid not in ids

    def test_cannot_revoke_current_session(self, auth_client):
        tc, _, _ = auth_client
        # Get current session ID
        resp = tc.get("/api/auth/sessions")
        current = [s for s in resp.json()["sessions"] if s["is_current"]][0]

        resp2 = tc.delete(f"/api/auth/sessions/{current['id']}")
        assert resp2.status_code == 400
        assert "current session" in resp2.json()["detail"].lower()

    def test_cannot_revoke_other_users_session(
        self, auth_client, auth_storage, session_manager,
    ):
        tc, _, _ = auth_client
        # Create another user with a session
        other_user = User(
            id=str(uuid.uuid4()), provider="microsoft",
            provider_user_id="ms-other-789", email="other@firm.com",
        )
        auth_storage.create_user(other_user)
        other_org = Organization(
            id=str(uuid.uuid4()), name="Other", slug="other-org",
        )
        auth_storage.create_organization(other_org)
        auth_storage.create_membership(Membership(
            id=str(uuid.uuid4()), user_id=other_user.id,
            organization_id=other_org.id, role="owner",
        ))
        access_other, _ = session_manager.create_session(
            user=other_user, org_id=other_org.id, role="owner",
        )
        claims_other = validate_access_token(access_other, SECRET)

        resp = tc.delete(f"/api/auth/sessions/{claims_other.sid}")
        assert resp.status_code == 404

    def test_returns_404_for_nonexistent_session(self, auth_client):
        tc, _, _ = auth_client
        resp = tc.delete(f"/api/auth/sessions/{uuid.uuid4()}")
        assert resp.status_code == 404


# ── DELETE /api/auth/sessions tests (revoke all others) ────────


class TestRevokeAllOtherSessions:
    def test_requires_auth(self, client: TestClient):
        resp = client.delete("/api/auth/sessions")
        assert resp.status_code == 401

    def test_revokes_all_other_sessions(
        self, auth_client, session_manager, user_with_org,
    ):
        tc, user, org = auth_client
        # Create 2 more sessions
        session_manager.create_session(
            user=user, org_id=org.id, role="owner",
            user_agent="Firefox/100",
        )
        session_manager.create_session(
            user=user, org_id=org.id, role="owner",
            user_agent="Safari/17",
        )

        # Verify 3 sessions exist
        resp = tc.get("/api/auth/sessions")
        assert len(resp.json()["sessions"]) == 3

        # Revoke all others
        resp2 = tc.delete("/api/auth/sessions")
        assert resp2.status_code == 200
        assert resp2.json()["revoked_count"] == 2

        # Only current session remains
        resp3 = tc.get("/api/auth/sessions")
        sessions = resp3.json()["sessions"]
        assert len(sessions) == 1
        assert sessions[0]["is_current"] is True

    def test_returns_zero_when_no_other_sessions(self, auth_client):
        tc, _, _ = auth_client
        resp = tc.delete("/api/auth/sessions")
        assert resp.status_code == 200
        assert resp.json()["revoked_count"] == 0


# ── Logout with sid tests ──────────────────────────────────────


class TestLogoutWithSid:
    def test_logout_revokes_only_current_session(
        self, auth_client, session_manager, user_with_org, auth_storage,
    ):
        tc, user, org = auth_client
        # Create a second session
        access2, refresh2 = session_manager.create_session(
            user=user, org_id=org.id, role="owner",
        )
        claims2 = validate_access_token(access2, SECRET)

        # Logout (should only revoke current session, not the second one)
        resp = tc.post("/api/auth/logout")
        assert resp.status_code == 200

        # The second session should still be active
        session2 = auth_storage.get_session(claims2.sid)
        assert session2 is not None
        assert not session2.is_revoked


# ── User agent parser tests ───────────────────────────────────


class TestParseUserAgent:
    def test_chrome_macos(self):
        from employee_help.api.auth_routes import _parse_user_agent

        result = _parse_user_agent(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        )
        assert result == {"browser": "Chrome", "os": "macOS", "device": "Desktop"}

    def test_firefox_windows(self):
        from employee_help.api.auth_routes import _parse_user_agent

        result = _parse_user_agent(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) "
            "Gecko/20100101 Firefox/120.0"
        )
        assert result == {"browser": "Firefox", "os": "Windows", "device": "Desktop"}

    def test_safari_iphone(self):
        from employee_help.api.auth_routes import _parse_user_agent

        result = _parse_user_agent(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1"
        )
        assert result == {"browser": "Safari", "os": "iOS", "device": "Mobile"}

    def test_edge_windows(self):
        from employee_help.api.auth_routes import _parse_user_agent

        result = _parse_user_agent(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
        )
        assert result == {"browser": "Edge", "os": "Windows", "device": "Desktop"}

    def test_none_user_agent(self):
        from employee_help.api.auth_routes import _parse_user_agent

        result = _parse_user_agent(None)
        assert result == {"browser": "Unknown", "os": "Unknown", "device": "Unknown"}

    def test_android_mobile(self):
        from employee_help.api.auth_routes import _parse_user_agent

        result = _parse_user_agent(
            "Mozilla/5.0 (Linux; Android 14) Chrome/120.0.0.0 Mobile Safari/537.36"
        )
        assert result == {"browser": "Chrome", "os": "Android", "device": "Mobile"}
