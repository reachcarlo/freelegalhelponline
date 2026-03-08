"""Tests for SessionManager (A1.2)."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from employee_help.auth.models import AuthSession, Membership, Organization, User
from employee_help.auth.provider import AuthError
from employee_help.auth.session import SessionManager, _hash_token
from employee_help.auth.storage import AuthStorage
from employee_help.auth.tokens import validate_access_token
from employee_help.storage.storage import Storage

SECRET = "test-jwt-secret-for-session-manager-tests"


@pytest.fixture
def storage(tmp_path: Path) -> Storage:
    db_path = tmp_path / "test.db"
    s = Storage(db_path=db_path)
    yield s
    s.close()


@pytest.fixture
def auth_storage(storage: Storage) -> AuthStorage:
    return AuthStorage(conn=storage._conn)


@pytest.fixture
def manager(auth_storage: AuthStorage) -> SessionManager:
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


# ── Hash function ─────────────────────────────────────────


class TestHashToken:
    def test_sha256_hash(self):
        result = _hash_token("test-token")
        expected = hashlib.sha256(b"test-token").hexdigest()
        assert result == expected

    def test_deterministic(self):
        assert _hash_token("same") == _hash_token("same")

    def test_different_tokens_different_hashes(self):
        assert _hash_token("token-a") != _hash_token("token-b")


# ── Create session ────────────────────────────────────────


class TestCreateSession:
    def test_returns_access_and_refresh_tokens(
        self, manager: SessionManager, user_with_org: tuple
    ):
        user, org, membership = user_with_org
        access_token, refresh_token = manager.create_session(
            user=user, org_id=org.id, role="owner",
        )
        assert isinstance(access_token, str)
        assert isinstance(refresh_token, str)
        assert len(access_token) > 0
        assert len(refresh_token) > 0

    def test_access_token_contains_correct_claims(
        self, manager: SessionManager, user_with_org: tuple
    ):
        user, org, _ = user_with_org
        access_token, _ = manager.create_session(
            user=user, org_id=org.id, role="owner",
        )
        claims = validate_access_token(access_token, SECRET)
        assert claims is not None
        assert claims.sub == user.id
        assert claims.org == org.id
        assert claims.role == "owner"
        assert claims.email == user.email

    def test_session_stored_in_db(
        self, manager: SessionManager, auth_storage: AuthStorage,
        user_with_org: tuple,
    ):
        user, org, _ = user_with_org
        _, refresh_token = manager.create_session(
            user=user, org_id=org.id, role="owner",
            ip_address="10.0.0.1", user_agent="TestBrowser/1.0",
        )
        token_hash = _hash_token(refresh_token)
        session = auth_storage.find_session_by_refresh_hash(token_hash)
        assert session is not None
        assert session.user_id == user.id
        assert session.ip_address == "10.0.0.1"
        assert session.user_agent == "TestBrowser/1.0"
        assert session.is_revoked is False

    def test_refresh_token_is_random(
        self, manager: SessionManager, user_with_org: tuple
    ):
        user, org, _ = user_with_org
        _, rt1 = manager.create_session(user=user, org_id=org.id, role="owner")
        _, rt2 = manager.create_session(user=user, org_id=org.id, role="owner")
        assert rt1 != rt2


# ── Validate access token ────────────────────────────────


class TestValidate:
    def test_valid_token(self, manager: SessionManager, user_with_org: tuple):
        user, org, _ = user_with_org
        access_token, _ = manager.create_session(
            user=user, org_id=org.id, role="owner",
        )
        claims = manager.validate(access_token)
        assert claims is not None
        assert claims.sub == user.id

    def test_invalid_token(self, manager: SessionManager):
        assert manager.validate("garbage") is None


# ── Refresh session ───────────────────────────────────────


class TestRefreshSession:
    def test_returns_new_tokens(
        self, manager: SessionManager, user_with_org: tuple
    ):
        user, org, _ = user_with_org
        _, refresh_token = manager.create_session(
            user=user, org_id=org.id, role="owner",
        )
        new_access, new_refresh = manager.refresh_session(refresh_token)
        assert isinstance(new_access, str)
        assert isinstance(new_refresh, str)
        assert new_refresh != refresh_token

    def test_new_access_token_valid(
        self, manager: SessionManager, user_with_org: tuple
    ):
        user, org, _ = user_with_org
        _, refresh_token = manager.create_session(
            user=user, org_id=org.id, role="owner",
        )
        new_access, _ = manager.refresh_session(refresh_token)
        claims = manager.validate(new_access)
        assert claims is not None
        assert claims.sub == user.id
        assert claims.org == org.id

    def test_old_refresh_token_revoked(
        self, manager: SessionManager, auth_storage: AuthStorage,
        user_with_org: tuple,
    ):
        user, org, _ = user_with_org
        _, refresh_token = manager.create_session(
            user=user, org_id=org.id, role="owner",
        )
        old_hash = _hash_token(refresh_token)
        manager.refresh_session(refresh_token)

        old_session = auth_storage.find_session_by_refresh_hash(old_hash)
        assert old_session is not None
        assert old_session.is_revoked is True

    def test_new_session_created(
        self, manager: SessionManager, auth_storage: AuthStorage,
        user_with_org: tuple,
    ):
        user, org, _ = user_with_org
        _, refresh_token = manager.create_session(
            user=user, org_id=org.id, role="owner",
        )
        _, new_refresh = manager.refresh_session(refresh_token)
        new_hash = _hash_token(new_refresh)
        new_session = auth_storage.find_session_by_refresh_hash(new_hash)
        assert new_session is not None
        assert new_session.is_revoked is False
        assert new_session.user_id == user.id

    def test_invalid_refresh_token(self, manager: SessionManager):
        with pytest.raises(AuthError, match="Invalid refresh token"):
            manager.refresh_session("nonexistent-token")

    def test_expired_refresh_token(
        self, manager: SessionManager, auth_storage: AuthStorage,
        user_with_org: tuple,
    ):
        user, org, _ = user_with_org
        # Create a session that's already expired
        refresh_token = "expired-test-token"
        session = AuthSession(
            id=str(uuid.uuid4()),
            user_id=user.id,
            refresh_token_hash=_hash_token(refresh_token),
            expires_at=datetime.now(tz=UTC) - timedelta(hours=1),
        )
        auth_storage.create_session(session)

        with pytest.raises(AuthError, match="expired"):
            manager.refresh_session(refresh_token)

    def test_replay_detection_revokes_all_sessions(
        self, manager: SessionManager, auth_storage: AuthStorage,
        user_with_org: tuple,
    ):
        """If a revoked refresh token is reused, all user sessions are revoked."""
        user, org, _ = user_with_org

        # Create two sessions
        _, rt1 = manager.create_session(user=user, org_id=org.id, role="owner")
        _, rt2 = manager.create_session(user=user, org_id=org.id, role="owner")

        # Refresh rt1 (this revokes the old session and creates a new one)
        _, new_rt1 = manager.refresh_session(rt1)

        # Replay: reuse the OLD rt1 (which is now revoked)
        with pytest.raises(AuthError, match="reuse detected"):
            manager.refresh_session(rt1)

        # All sessions should be revoked, including the one from rt2
        rt2_session = auth_storage.find_session_by_refresh_hash(_hash_token(rt2))
        assert rt2_session is not None
        assert rt2_session.is_revoked is True

    def test_inactive_user_rejected(
        self, manager: SessionManager, auth_storage: AuthStorage,
        user_with_org: tuple,
    ):
        user, org, _ = user_with_org
        _, refresh_token = manager.create_session(
            user=user, org_id=org.id, role="owner",
        )
        auth_storage.deactivate_user(user.id)

        with pytest.raises(AuthError, match="inactive"):
            manager.refresh_session(refresh_token)

    def test_preserves_ip_and_ua_from_request(
        self, manager: SessionManager, auth_storage: AuthStorage,
        user_with_org: tuple,
    ):
        user, org, _ = user_with_org
        _, refresh_token = manager.create_session(
            user=user, org_id=org.id, role="owner",
            ip_address="10.0.0.1", user_agent="OldBrowser/1.0",
        )
        _, new_refresh = manager.refresh_session(
            refresh_token,
            ip_address="10.0.0.2",
            user_agent="NewBrowser/2.0",
        )
        new_session = auth_storage.find_session_by_refresh_hash(
            _hash_token(new_refresh)
        )
        assert new_session.ip_address == "10.0.0.2"
        assert new_session.user_agent == "NewBrowser/2.0"

    def test_inherits_ip_ua_when_not_provided(
        self, manager: SessionManager, auth_storage: AuthStorage,
        user_with_org: tuple,
    ):
        user, org, _ = user_with_org
        _, refresh_token = manager.create_session(
            user=user, org_id=org.id, role="owner",
            ip_address="10.0.0.1", user_agent="Browser/1.0",
        )
        _, new_refresh = manager.refresh_session(refresh_token)
        new_session = auth_storage.find_session_by_refresh_hash(
            _hash_token(new_refresh)
        )
        assert new_session.ip_address == "10.0.0.1"
        assert new_session.user_agent == "Browser/1.0"


# ── Revoke ────────────────────────────────────────────────


class TestRevokeSession:
    def test_revoke_single_session(
        self, manager: SessionManager, auth_storage: AuthStorage,
        user_with_org: tuple,
    ):
        user, org, _ = user_with_org
        _, refresh_token = manager.create_session(
            user=user, org_id=org.id, role="owner",
        )
        session = auth_storage.find_session_by_refresh_hash(
            _hash_token(refresh_token)
        )
        manager.revoke_session(session.id)

        found = auth_storage.get_session(session.id)
        assert found.is_revoked is True


class TestRevokeAllSessions:
    def test_revoke_all(
        self, manager: SessionManager, user_with_org: tuple
    ):
        user, org, _ = user_with_org
        manager.create_session(user=user, org_id=org.id, role="owner")
        manager.create_session(user=user, org_id=org.id, role="owner")
        manager.create_session(user=user, org_id=org.id, role="owner")

        count = manager.revoke_all_sessions(user.id)
        assert count == 3

    def test_revoke_all_returns_zero_for_no_sessions(
        self, manager: SessionManager, user_with_org: tuple
    ):
        user, _, _ = user_with_org
        assert manager.revoke_all_sessions(user.id) == 0


# ── Full lifecycle ────────────────────────────────────────


class TestFullLifecycle:
    def test_login_validate_expire_refresh_validate_logout(
        self, manager: SessionManager, auth_storage: AuthStorage,
        user_with_org: tuple,
    ):
        """Gate test: full session lifecycle."""
        user, org, _ = user_with_org

        # 1. Login — create session
        access_token, refresh_token = manager.create_session(
            user=user, org_id=org.id, role="owner",
        )

        # 2. Validate access token
        claims = manager.validate(access_token)
        assert claims is not None
        assert claims.sub == user.id

        # 3. Simulate expired access token — create one with ttl=-1
        from employee_help.auth.tokens import create_access_token
        expired = create_access_token(
            user_id=user.id, org_id=org.id, role="owner",
            email=user.email, secret=SECRET, ttl=-1,
        )
        assert manager.validate(expired) is None

        # 4. Refresh — get new tokens
        new_access, new_refresh = manager.refresh_session(refresh_token)
        assert new_refresh != refresh_token

        # 5. Validate new access token
        new_claims = manager.validate(new_access)
        assert new_claims is not None
        assert new_claims.sub == user.id

        # 6. Old refresh token should fail (already revoked)
        with pytest.raises(AuthError):
            manager.refresh_session(refresh_token)

        # 7. Logout — revoke current session
        session = auth_storage.find_session_by_refresh_hash(
            _hash_token(new_refresh)
        )
        manager.revoke_session(session.id)

        # 8. Refresh with revoked token fails
        with pytest.raises(AuthError):
            manager.refresh_session(new_refresh)
