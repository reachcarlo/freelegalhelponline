"""Session management: create, refresh (with rotation), revoke."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from employee_help.auth.models import AuthSession, User
from employee_help.auth.provider import AuthError
from employee_help.auth.storage import AuthStorage
from employee_help.auth.tokens import AccessTokenClaims, create_access_token, validate_access_token


def _hash_token(token: str) -> str:
    """SHA-256 hash a raw refresh token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


class SessionManager:
    """Manages authentication sessions and token lifecycle.

    Responsibilities:
    - Create new sessions (on login) — issues access + refresh tokens
    - Validate access tokens
    - Refresh sessions — rotates refresh token, issues new access token
    - Revoke sessions (on logout)
    - Detect replay attacks — if a revoked refresh token is reused,
      all sessions for that user are revoked (breach assumed)
    """

    def __init__(
        self,
        auth_storage: AuthStorage,
        jwt_secret: str,
        access_token_ttl: int = 900,
        refresh_token_ttl: int = 604800,
    ) -> None:
        self._storage = auth_storage
        self._secret = jwt_secret
        self._access_ttl = access_token_ttl
        self._refresh_ttl = refresh_token_ttl

    def create_session(
        self,
        user: User,
        org_id: str,
        role: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[str, str]:
        """Create a new session after successful OAuth login.

        Returns:
            (access_token, refresh_token) tuple.
        """
        refresh_token = secrets.token_urlsafe(32)
        session = AuthSession(
            id=str(uuid.uuid4()),
            user_id=user.id,
            refresh_token_hash=_hash_token(refresh_token),
            expires_at=datetime.now(tz=UTC) + timedelta(seconds=self._refresh_ttl),
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self._storage.create_session(session)

        access_token = create_access_token(
            user_id=user.id,
            org_id=org_id,
            role=role,
            email=user.email,
            secret=self._secret,
            ttl=self._access_ttl,
        )
        return access_token, refresh_token

    def validate(self, token: str) -> AccessTokenClaims | None:
        """Validate an access token and return its claims."""
        return validate_access_token(token, self._secret)

    def refresh_session(
        self,
        refresh_token: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[str, str]:
        """Rotate refresh token and issue a new access token.

        Args:
            refresh_token: The current raw refresh token.
            ip_address: Client IP for audit.
            user_agent: Client user-agent for audit.

        Returns:
            (new_access_token, new_refresh_token) tuple.

        Raises:
            AuthError: If the refresh token is invalid, expired, or revoked.
                If a revoked token is presented (replay attack), all sessions
                for that user are revoked as a security measure.
        """
        token_hash = _hash_token(refresh_token)
        session = self._storage.find_session_by_refresh_hash(token_hash)

        if session is None:
            raise AuthError("Invalid refresh token")

        # Replay detection: revoked token reused → breach assumed
        if session.is_revoked:
            self._storage.revoke_all_user_sessions(session.user_id)
            raise AuthError("Refresh token reuse detected — all sessions revoked")

        # Check expiry
        if session.expires_at <= datetime.now(tz=UTC):
            raise AuthError("Refresh token expired")

        # Look up user for access token claims
        user = self._storage.get_user(session.user_id)
        if user is None or not user.is_active:
            self._storage.revoke_session(session.id)
            raise AuthError("User not found or inactive")

        # Get user's org and role for access token
        memberships = self._storage.get_user_memberships(user.id)
        if not memberships:
            raise AuthError("User has no organization membership")
        membership = memberships[0]  # Primary org

        # Rotate: revoke old, create new
        self._storage.revoke_session(session.id)

        new_refresh_token = secrets.token_urlsafe(32)
        new_session = AuthSession(
            id=str(uuid.uuid4()),
            user_id=user.id,
            refresh_token_hash=_hash_token(new_refresh_token),
            expires_at=datetime.now(tz=UTC) + timedelta(seconds=self._refresh_ttl),
            ip_address=ip_address or session.ip_address,
            user_agent=user_agent or session.user_agent,
        )
        self._storage.create_session(new_session)

        access_token = create_access_token(
            user_id=user.id,
            org_id=membership.organization_id,
            role=membership.role,
            email=user.email,
            secret=self._secret,
            ttl=self._access_ttl,
        )
        return access_token, new_refresh_token

    def revoke_session(self, session_id: str) -> None:
        """Revoke a specific session (logout)."""
        self._storage.revoke_session(session_id)

    def revoke_all_sessions(self, user_id: str) -> int:
        """Revoke all sessions for a user. Returns count revoked."""
        return self._storage.revoke_all_user_sessions(user_id)
