"""Authentication data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


@dataclass
class User:
    """A user authenticated via Google or Microsoft OAuth."""

    id: str
    provider: str  # 'google' | 'microsoft'
    provider_user_id: str
    email: str
    display_name: str | None = None
    avatar_url: str | None = None
    is_active: bool = True
    created_at: datetime = field(default_factory=_utcnow)
    last_login_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        if not self.id:
            import uuid

            self.id = str(uuid.uuid4())


@dataclass
class Organization:
    """An organization (implicit for individuals, explicit for teams)."""

    id: str
    name: str
    slug: str
    plan_tier: str = "individual"
    sso_provider: str | None = None
    sso_config: str | None = None
    max_seats: int | None = None
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        if not self.id:
            import uuid

            self.id = str(uuid.uuid4())


@dataclass
class Membership:
    """A user's membership in an organization."""

    id: str
    user_id: str
    organization_id: str
    role: str = "member"  # 'owner' | 'admin' | 'member'
    created_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        if not self.id:
            import uuid

            self.id = str(uuid.uuid4())


@dataclass
class AuthSession:
    """A server-side session for refresh token tracking."""

    id: str
    user_id: str
    refresh_token_hash: str
    expires_at: datetime
    created_at: datetime = field(default_factory=_utcnow)
    last_used_at: datetime = field(default_factory=_utcnow)
    ip_address: str | None = None
    user_agent: str | None = None
    is_revoked: bool = False

    def __post_init__(self) -> None:
        if not self.id:
            import uuid

            self.id = str(uuid.uuid4())
