"""JWT access token creation and validation (HS256)."""

from __future__ import annotations

import time
from dataclasses import dataclass

import jwt


@dataclass
class AccessTokenClaims:
    """Decoded claims from a validated access token."""

    sub: str  # user_id
    org: str  # organization_id
    role: str  # 'owner' | 'admin' | 'member'
    email: str
    iat: int
    exp: int


def create_access_token(
    *,
    user_id: str,
    org_id: str,
    role: str,
    email: str,
    secret: str,
    ttl: int = 900,
) -> str:
    """Create a signed HS256 JWT access token.

    Args:
        user_id: Internal UUID of the user.
        org_id: Organization UUID.
        role: User's role in the organization.
        email: User's email address.
        secret: HS256 signing secret (AUTH_JWT_SECRET).
        ttl: Token time-to-live in seconds (default: 15 minutes).

    Returns:
        Encoded JWT string.
    """
    now = int(time.time())
    payload = {
        "sub": user_id,
        "org": org_id,
        "role": role,
        "email": email,
        "iat": now,
        "exp": now + ttl,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def validate_access_token(token: str, secret: str) -> AccessTokenClaims | None:
    """Validate and decode an access token.

    Returns:
        AccessTokenClaims on success, None on any validation failure
        (expired, bad signature, missing claims, etc.).
    """
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return AccessTokenClaims(
            sub=payload["sub"],
            org=payload["org"],
            role=payload["role"],
            email=payload["email"],
            iat=payload["iat"],
            exp=payload["exp"],
        )
    except (jwt.InvalidTokenError, KeyError):
        return None
