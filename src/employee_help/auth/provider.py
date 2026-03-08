"""Auth provider protocol and shared utilities."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx
import jwt


class AuthError(Exception):
    """Raised when authentication fails."""


@dataclass
class AuthResult:
    """Identity claims returned by an OAuth provider after successful login."""

    provider: str  # 'google' | 'microsoft'
    provider_user_id: str  # Stable ID from the provider
    email: str  # Verified email address
    display_name: str | None = None
    avatar_url: str | None = None
    raw_claims: dict[str, Any] = field(default_factory=dict)


class AuthProvider(Protocol):
    """Strategy interface for OAuth/OIDC providers."""

    def get_authorization_url(self, state: str, redirect_uri: str) -> str: ...

    async def handle_callback(
        self, code: str, redirect_uri: str
    ) -> AuthResult: ...


class JWKSClient:
    """Fetches and caches JWKS keys from an OIDC provider.

    Each provider instance holds its own JWKSClient with a 24-hour
    cache TTL to avoid repeated network calls on every token validation.
    """

    def __init__(self, jwks_url: str, cache_ttl: int = 86400) -> None:
        self._url = jwks_url
        self._ttl = cache_ttl
        self._keys: dict[str, Any] | None = None
        self._fetched_at: float = 0

    async def get_signing_key(self, kid: str) -> Any:
        """Get the RSA public key matching the given kid."""
        jwks = await self._fetch()
        for key_data in jwks.get("keys", []):
            if key_data.get("kid") == kid:
                return jwt.algorithms.RSAAlgorithm.from_jwk(key_data)
        raise AuthError(f"No matching key found for kid={kid}")

    async def _fetch(self) -> dict[str, Any]:
        now = time.monotonic()
        if self._keys is not None and now - self._fetched_at < self._ttl:
            return self._keys
        async with httpx.AsyncClient() as client:
            resp = await client.get(self._url)
            resp.raise_for_status()
            self._keys = resp.json()
            self._fetched_at = now
            return self._keys
