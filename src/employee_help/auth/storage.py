"""SQLite storage for authentication entities."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from employee_help.auth.models import AuthSession, Membership, Organization, User


class AuthStorage:
    """CRUD operations for users, organizations, memberships, and sessions.

    Operates on the same SQLite database as the knowledge-base Storage class.
    Accepts either a raw sqlite3.Connection or a db_path.
    """

    def __init__(
        self,
        conn: sqlite3.Connection | None = None,
        db_path: str | Path | None = None,
    ) -> None:
        if conn is not None:
            self._conn = conn
            self._owns_conn = False
        elif db_path is not None:
            p = Path(db_path)
            if str(p) != ":memory:":
                p.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(p))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._owns_conn = True
        else:
            raise ValueError("Either conn or db_path must be provided")

    def close(self) -> None:
        if self._owns_conn:
            self._conn.close()

    # ── Users ────────────────────────────────────────────────────

    def find_user_by_provider(
        self, provider: str, provider_user_id: str
    ) -> User | None:
        """Find a user by their OAuth provider identity."""
        row = self._conn.execute(
            "SELECT * FROM users WHERE provider = ? AND provider_user_id = ?",
            (provider, provider_user_id),
        ).fetchone()
        return self._row_to_user(row) if row else None

    def find_users_by_email(self, email: str) -> list[User]:
        """Find all users with a given email (may span providers)."""
        rows = self._conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchall()
        return [self._row_to_user(r) for r in rows]

    def get_user(self, user_id: str) -> User | None:
        """Get a user by their internal UUID."""
        row = self._conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return self._row_to_user(row) if row else None

    def create_user(self, user: User) -> User:
        """Insert a new user record."""
        self._conn.execute(
            """INSERT INTO users (id, provider, provider_user_id, email,
               display_name, avatar_url, is_active, created_at, last_login_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user.id,
                user.provider,
                user.provider_user_id,
                user.email,
                user.display_name,
                user.avatar_url,
                1 if user.is_active else 0,
                user.created_at.isoformat(),
                user.last_login_at.isoformat(),
            ),
        )
        self._conn.commit()
        return user

    def update_last_login(self, user_id: str) -> None:
        """Update the last_login_at timestamp for a user."""
        now = datetime.now(tz=UTC).isoformat()
        self._conn.execute(
            "UPDATE users SET last_login_at = ? WHERE id = ?",
            (now, user_id),
        )
        self._conn.commit()

    def update_user_profile(
        self,
        user_id: str,
        display_name: str | None = None,
        avatar_url: str | None = None,
        email: str | None = None,
    ) -> None:
        """Update user profile fields from latest OAuth claims."""
        updates = []
        values: list = []
        if display_name is not None:
            updates.append("display_name = ?")
            values.append(display_name)
        if avatar_url is not None:
            updates.append("avatar_url = ?")
            values.append(avatar_url)
        if email is not None:
            updates.append("email = ?")
            values.append(email)
        if not updates:
            return
        values.append(user_id)
        self._conn.execute(
            f"UPDATE users SET {', '.join(updates)} WHERE id = ?",
            values,
        )
        self._conn.commit()

    def deactivate_user(self, user_id: str) -> None:
        """Soft-delete a user by setting is_active to false."""
        self._conn.execute(
            "UPDATE users SET is_active = 0 WHERE id = ?", (user_id,)
        )
        self._conn.commit()

    # ── Organizations ────────────────────────────────────────────

    def create_organization(self, org: Organization) -> Organization:
        """Insert a new organization record."""
        self._conn.execute(
            """INSERT INTO organizations (id, name, slug, plan_tier,
               sso_provider, sso_config, max_seats, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                org.id,
                org.name,
                org.slug,
                org.plan_tier,
                org.sso_provider,
                org.sso_config,
                org.max_seats,
                org.created_at.isoformat(),
                org.updated_at.isoformat(),
            ),
        )
        self._conn.commit()
        return org

    def get_organization(self, org_id: str) -> Organization | None:
        """Get an organization by its UUID."""
        row = self._conn.execute(
            "SELECT * FROM organizations WHERE id = ?", (org_id,)
        ).fetchone()
        return self._row_to_organization(row) if row else None

    # ── Memberships ──────────────────────────────────────────────

    def create_membership(self, membership: Membership) -> Membership:
        """Insert a new membership record."""
        self._conn.execute(
            """INSERT INTO memberships (id, user_id, organization_id, role, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                membership.id,
                membership.user_id,
                membership.organization_id,
                membership.role,
                membership.created_at.isoformat(),
            ),
        )
        self._conn.commit()
        return membership

    def get_user_memberships(self, user_id: str) -> list[Membership]:
        """Get all organizations a user belongs to."""
        rows = self._conn.execute(
            "SELECT * FROM memberships WHERE user_id = ?", (user_id,)
        ).fetchall()
        return [self._row_to_membership(r) for r in rows]

    def get_org_members(self, org_id: str) -> list[Membership]:
        """Get all members of an organization."""
        rows = self._conn.execute(
            "SELECT * FROM memberships WHERE organization_id = ?", (org_id,)
        ).fetchall()
        return [self._row_to_membership(r) for r in rows]

    # ── Sessions ─────────────────────────────────────────────────

    def create_session(self, session: AuthSession) -> AuthSession:
        """Insert a new session record."""
        self._conn.execute(
            """INSERT INTO sessions (id, user_id, refresh_token_hash,
               expires_at, created_at, last_used_at, ip_address, user_agent, is_revoked)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session.id,
                session.user_id,
                session.refresh_token_hash,
                session.expires_at.isoformat(),
                session.created_at.isoformat(),
                session.last_used_at.isoformat(),
                session.ip_address,
                session.user_agent,
                0,
            ),
        )
        self._conn.commit()
        return session

    def get_session(self, session_id: str) -> AuthSession | None:
        """Get a session by its UUID."""
        row = self._conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return self._row_to_session(row) if row else None

    def find_session_by_refresh_hash(self, token_hash: str) -> AuthSession | None:
        """Find a session by its refresh token hash."""
        row = self._conn.execute(
            "SELECT * FROM sessions WHERE refresh_token_hash = ?",
            (token_hash,),
        ).fetchone()
        return self._row_to_session(row) if row else None

    def update_session_last_used(self, session_id: str) -> None:
        """Update the last_used_at timestamp for a session."""
        now = datetime.now(tz=UTC).isoformat()
        self._conn.execute(
            "UPDATE sessions SET last_used_at = ? WHERE id = ?",
            (now, session_id),
        )
        self._conn.commit()

    def revoke_session(self, session_id: str) -> None:
        """Revoke a single session."""
        self._conn.execute(
            "UPDATE sessions SET is_revoked = 1 WHERE id = ?", (session_id,)
        )
        self._conn.commit()

    def revoke_all_user_sessions(self, user_id: str) -> int:
        """Revoke all active sessions for a user. Returns count revoked."""
        cur = self._conn.execute(
            "UPDATE sessions SET is_revoked = 1 WHERE user_id = ? AND is_revoked = 0",
            (user_id,),
        )
        self._conn.commit()
        return cur.rowcount

    def cleanup_expired_sessions(self) -> int:
        """Delete expired and revoked sessions. Returns count deleted."""
        now = datetime.now(tz=UTC).isoformat()
        cur = self._conn.execute(
            "DELETE FROM sessions WHERE expires_at < ? OR is_revoked = 1",
            (now,),
        )
        self._conn.commit()
        return cur.rowcount

    # ── Row mappers ──────────────────────────────────────────────

    def _row_to_user(self, row: sqlite3.Row) -> User:
        return User(
            id=row["id"],
            provider=row["provider"],
            provider_user_id=row["provider_user_id"],
            email=row["email"],
            display_name=row["display_name"],
            avatar_url=row["avatar_url"],
            is_active=bool(row["is_active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            last_login_at=datetime.fromisoformat(row["last_login_at"]),
        )

    def _row_to_organization(self, row: sqlite3.Row) -> Organization:
        return Organization(
            id=row["id"],
            name=row["name"],
            slug=row["slug"],
            plan_tier=row["plan_tier"],
            sso_provider=row["sso_provider"],
            sso_config=row["sso_config"],
            max_seats=row["max_seats"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _row_to_membership(self, row: sqlite3.Row) -> Membership:
        return Membership(
            id=row["id"],
            user_id=row["user_id"],
            organization_id=row["organization_id"],
            role=row["role"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def _row_to_session(self, row: sqlite3.Row) -> AuthSession:
        return AuthSession(
            id=row["id"],
            user_id=row["user_id"],
            refresh_token_hash=row["refresh_token_hash"],
            expires_at=datetime.fromisoformat(row["expires_at"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            last_used_at=datetime.fromisoformat(row["last_used_at"]),
            ip_address=row["ip_address"],
            user_agent=row["user_agent"],
            is_revoked=bool(row["is_revoked"]),
        )
