"""Tests for AuthStorage CRUD operations (A1.1)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from employee_help.auth.models import AuthSession, Membership, Organization, User
from employee_help.auth.storage import AuthStorage
from employee_help.storage.storage import Storage


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
def sample_user() -> User:
    return User(
        id=str(uuid.uuid4()),
        provider="google",
        provider_user_id="google-123",
        email="attorney@lawfirm.com",
        display_name="Jane Attorney",
        avatar_url="https://lh3.googleusercontent.com/photo.jpg",
    )


@pytest.fixture
def saved_user(auth_storage: AuthStorage, sample_user: User) -> User:
    return auth_storage.create_user(sample_user)


@pytest.fixture
def sample_org() -> Organization:
    return Organization(
        id=str(uuid.uuid4()),
        name="Jane's Workspace",
        slug=f"user-{uuid.uuid4().hex[:8]}",
    )


@pytest.fixture
def saved_org(auth_storage: AuthStorage, sample_org: Organization) -> Organization:
    return auth_storage.create_organization(sample_org)


# ── User Tests ───────────────────────────────────────────────


class TestUserCRUD:
    def test_create_user(self, auth_storage: AuthStorage, sample_user: User):
        user = auth_storage.create_user(sample_user)
        assert user.id == sample_user.id
        assert user.provider == "google"
        assert user.email == "attorney@lawfirm.com"

    def test_get_user(self, auth_storage: AuthStorage, saved_user: User):
        user = auth_storage.get_user(saved_user.id)
        assert user is not None
        assert user.id == saved_user.id
        assert user.email == saved_user.email

    def test_get_user_not_found(self, auth_storage: AuthStorage):
        assert auth_storage.get_user("nonexistent-id") is None

    def test_find_by_provider(self, auth_storage: AuthStorage, saved_user: User):
        user = auth_storage.find_user_by_provider("google", "google-123")
        assert user is not None
        assert user.id == saved_user.id

    def test_find_by_provider_not_found(self, auth_storage: AuthStorage, saved_user: User):
        assert auth_storage.find_user_by_provider("microsoft", "google-123") is None
        assert auth_storage.find_user_by_provider("google", "wrong-id") is None

    def test_find_by_email(self, auth_storage: AuthStorage, saved_user: User):
        users = auth_storage.find_users_by_email("attorney@lawfirm.com")
        assert len(users) == 1
        assert users[0].id == saved_user.id

    def test_find_by_email_multiple_providers(self, auth_storage: AuthStorage, saved_user: User):
        """Same email can exist across different providers."""
        ms_user = User(
            id=str(uuid.uuid4()),
            provider="microsoft",
            provider_user_id="ms-oid-456",
            email="attorney@lawfirm.com",
            display_name="Jane Attorney",
        )
        auth_storage.create_user(ms_user)
        users = auth_storage.find_users_by_email("attorney@lawfirm.com")
        assert len(users) == 2

    def test_update_last_login(self, auth_storage: AuthStorage, saved_user: User):
        original_login = saved_user.last_login_at
        auth_storage.update_last_login(saved_user.id)
        user = auth_storage.get_user(saved_user.id)
        assert user.last_login_at >= original_login

    def test_update_user_profile(self, auth_storage: AuthStorage, saved_user: User):
        auth_storage.update_user_profile(
            saved_user.id,
            display_name="Jane Q. Attorney, Esq.",
            email="jane@newdomain.com",
        )
        user = auth_storage.get_user(saved_user.id)
        assert user.display_name == "Jane Q. Attorney, Esq."
        assert user.email == "jane@newdomain.com"
        # Avatar unchanged
        assert user.avatar_url == saved_user.avatar_url

    def test_update_user_profile_noop(self, auth_storage: AuthStorage, saved_user: User):
        """No-op when no fields provided."""
        auth_storage.update_user_profile(saved_user.id)
        user = auth_storage.get_user(saved_user.id)
        assert user.display_name == saved_user.display_name

    def test_deactivate_user(self, auth_storage: AuthStorage, saved_user: User):
        assert saved_user.is_active is True
        auth_storage.deactivate_user(saved_user.id)
        user = auth_storage.get_user(saved_user.id)
        assert user.is_active is False

    def test_unique_provider_constraint(self, auth_storage: AuthStorage, saved_user: User):
        """Cannot create two users with same provider + provider_user_id."""
        duplicate = User(
            id=str(uuid.uuid4()),
            provider="google",
            provider_user_id="google-123",
            email="different@email.com",
        )
        with pytest.raises(Exception):  # IntegrityError
            auth_storage.create_user(duplicate)


# ── Organization Tests ───────────────────────────────────────


class TestOrganizationCRUD:
    def test_create_organization(self, auth_storage: AuthStorage, sample_org: Organization):
        org = auth_storage.create_organization(sample_org)
        assert org.id == sample_org.id
        assert org.plan_tier == "individual"

    def test_get_organization(self, auth_storage: AuthStorage, saved_org: Organization):
        org = auth_storage.get_organization(saved_org.id)
        assert org is not None
        assert org.name == saved_org.name
        assert org.slug == saved_org.slug

    def test_get_organization_not_found(self, auth_storage: AuthStorage):
        assert auth_storage.get_organization("nonexistent") is None

    def test_unique_slug_constraint(self, auth_storage: AuthStorage, saved_org: Organization):
        duplicate = Organization(
            id=str(uuid.uuid4()),
            name="Different Name",
            slug=saved_org.slug,  # Same slug
        )
        with pytest.raises(Exception):  # IntegrityError
            auth_storage.create_organization(duplicate)


# ── Membership Tests ─────────────────────────────────────────


class TestMembershipCRUD:
    def test_create_membership(
        self, auth_storage: AuthStorage, saved_user: User, saved_org: Organization
    ):
        membership = Membership(
            id=str(uuid.uuid4()),
            user_id=saved_user.id,
            organization_id=saved_org.id,
            role="owner",
        )
        result = auth_storage.create_membership(membership)
        assert result.role == "owner"

    def test_get_user_memberships(
        self, auth_storage: AuthStorage, saved_user: User, saved_org: Organization
    ):
        membership = Membership(
            id=str(uuid.uuid4()),
            user_id=saved_user.id,
            organization_id=saved_org.id,
            role="owner",
        )
        auth_storage.create_membership(membership)

        memberships = auth_storage.get_user_memberships(saved_user.id)
        assert len(memberships) == 1
        assert memberships[0].organization_id == saved_org.id

    def test_get_org_members(
        self, auth_storage: AuthStorage, saved_user: User, saved_org: Organization
    ):
        membership = Membership(
            id=str(uuid.uuid4()),
            user_id=saved_user.id,
            organization_id=saved_org.id,
            role="member",
        )
        auth_storage.create_membership(membership)

        members = auth_storage.get_org_members(saved_org.id)
        assert len(members) == 1
        assert members[0].user_id == saved_user.id

    def test_unique_user_org_constraint(
        self, auth_storage: AuthStorage, saved_user: User, saved_org: Organization
    ):
        """One membership per user per org."""
        membership = Membership(
            id=str(uuid.uuid4()),
            user_id=saved_user.id,
            organization_id=saved_org.id,
        )
        auth_storage.create_membership(membership)

        duplicate = Membership(
            id=str(uuid.uuid4()),
            user_id=saved_user.id,
            organization_id=saved_org.id,
        )
        with pytest.raises(Exception):  # IntegrityError
            auth_storage.create_membership(duplicate)

    def test_cascade_delete_user(
        self, auth_storage: AuthStorage, saved_user: User, saved_org: Organization
    ):
        """Deleting a user cascades to memberships."""
        membership = Membership(
            id=str(uuid.uuid4()),
            user_id=saved_user.id,
            organization_id=saved_org.id,
        )
        auth_storage.create_membership(membership)

        auth_storage._conn.execute(
            "DELETE FROM users WHERE id = ?", (saved_user.id,)
        )
        auth_storage._conn.commit()

        memberships = auth_storage.get_user_memberships(saved_user.id)
        assert len(memberships) == 0


# ── Session Tests ────────────────────────────────────────────


class TestSessionCRUD:
    def _make_session(self, user_id: str) -> AuthSession:
        return AuthSession(
            id=str(uuid.uuid4()),
            user_id=user_id,
            refresh_token_hash="sha256-hash-of-refresh-token",
            expires_at=datetime.now(tz=UTC) + timedelta(days=7),
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )

    def test_create_session(self, auth_storage: AuthStorage, saved_user: User):
        session = self._make_session(saved_user.id)
        result = auth_storage.create_session(session)
        assert result.id == session.id
        assert result.is_revoked is False

    def test_get_session(self, auth_storage: AuthStorage, saved_user: User):
        session = self._make_session(saved_user.id)
        auth_storage.create_session(session)

        found = auth_storage.get_session(session.id)
        assert found is not None
        assert found.user_id == saved_user.id
        assert found.refresh_token_hash == "sha256-hash-of-refresh-token"
        assert found.ip_address == "192.168.1.1"
        assert found.is_revoked is False

    def test_get_session_not_found(self, auth_storage: AuthStorage):
        assert auth_storage.get_session("nonexistent") is None

    def test_update_session_last_used(self, auth_storage: AuthStorage, saved_user: User):
        session = self._make_session(saved_user.id)
        auth_storage.create_session(session)

        auth_storage.update_session_last_used(session.id)
        found = auth_storage.get_session(session.id)
        assert found.last_used_at >= session.last_used_at

    def test_revoke_session(self, auth_storage: AuthStorage, saved_user: User):
        session = self._make_session(saved_user.id)
        auth_storage.create_session(session)

        auth_storage.revoke_session(session.id)
        found = auth_storage.get_session(session.id)
        assert found.is_revoked is True

    def test_revoke_all_user_sessions(self, auth_storage: AuthStorage, saved_user: User):
        s1 = self._make_session(saved_user.id)
        s2 = self._make_session(saved_user.id)
        auth_storage.create_session(s1)
        auth_storage.create_session(s2)

        count = auth_storage.revoke_all_user_sessions(saved_user.id)
        assert count == 2

        assert auth_storage.get_session(s1.id).is_revoked is True
        assert auth_storage.get_session(s2.id).is_revoked is True

    def test_revoke_all_skips_already_revoked(
        self, auth_storage: AuthStorage, saved_user: User
    ):
        s1 = self._make_session(saved_user.id)
        auth_storage.create_session(s1)
        auth_storage.revoke_session(s1.id)

        s2 = self._make_session(saved_user.id)
        auth_storage.create_session(s2)

        count = auth_storage.revoke_all_user_sessions(saved_user.id)
        assert count == 1  # Only s2 was active

    def test_cleanup_expired_sessions(self, auth_storage: AuthStorage, saved_user: User):
        # Expired session
        expired = AuthSession(
            id=str(uuid.uuid4()),
            user_id=saved_user.id,
            refresh_token_hash="hash-1",
            expires_at=datetime.now(tz=UTC) - timedelta(hours=1),
        )
        auth_storage.create_session(expired)

        # Revoked session
        revoked = self._make_session(saved_user.id)
        auth_storage.create_session(revoked)
        auth_storage.revoke_session(revoked.id)

        # Active session (should survive)
        active = self._make_session(saved_user.id)
        auth_storage.create_session(active)

        deleted = auth_storage.cleanup_expired_sessions()
        assert deleted == 2  # expired + revoked

        assert auth_storage.get_session(expired.id) is None
        assert auth_storage.get_session(revoked.id) is None
        assert auth_storage.get_session(active.id) is not None

    def test_cascade_delete_user_sessions(
        self, auth_storage: AuthStorage, saved_user: User
    ):
        """Deleting a user cascades to sessions."""
        session = self._make_session(saved_user.id)
        auth_storage.create_session(session)

        auth_storage._conn.execute(
            "DELETE FROM users WHERE id = ?", (saved_user.id,)
        )
        auth_storage._conn.commit()

        assert auth_storage.get_session(session.id) is None


# ── Standalone Connection Tests ──────────────────────────────


class TestStandaloneConnection:
    def test_create_with_db_path(self, tmp_path: Path):
        db_path = tmp_path / "standalone.db"
        # Need to create the schema first via Storage
        s = Storage(db_path=db_path)
        s.close()

        auth = AuthStorage(db_path=db_path)
        user = User(
            id=str(uuid.uuid4()),
            provider="google",
            provider_user_id="standalone-test",
            email="standalone@test.com",
        )
        auth.create_user(user)
        found = auth.get_user(user.id)
        assert found is not None
        auth.close()

    def test_requires_conn_or_path(self):
        with pytest.raises(ValueError, match="Either conn or db_path"):
            AuthStorage()
