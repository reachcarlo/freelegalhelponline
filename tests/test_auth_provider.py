"""Tests for auth provider implementations (A1.1).

Tests Google and Microsoft OIDC providers with mocked token exchange
and JWKS endpoints. Uses real RSA key pairs for JWT signing/verification.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta

import httpx
import jwt as pyjwt
import pytest
import respx
from cryptography.hazmat.primitives.asymmetric import rsa

from employee_help.auth.google import (
    GoogleOIDCProvider,
    _JWKS_URL as GOOGLE_JWKS_URL,
    _TOKEN_URL as GOOGLE_TOKEN_URL,
)
from employee_help.auth.microsoft import (
    MicrosoftOIDCProvider,
    _JWKS_URL as MS_JWKS_URL,
    _TOKEN_URL as MS_TOKEN_URL,
)
from employee_help.auth.provider import AuthError, AuthResult, JWKSClient

# ── Test RSA key pair ────────────────────────────────────────

_TEST_PRIVATE_KEY = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
)
_TEST_PUBLIC_KEY = _TEST_PRIVATE_KEY.public_key()
_TEST_KID = "test-key-1"


def _make_jwks() -> dict:
    """Build a JWKS containing the test public key."""
    jwk_str = pyjwt.algorithms.RSAAlgorithm.to_jwk(_TEST_PUBLIC_KEY)
    jwk = json.loads(jwk_str)
    jwk["kid"] = _TEST_KID
    jwk["use"] = "sig"
    jwk["alg"] = "RS256"
    return {"keys": [jwk]}


_TEST_JWKS = _make_jwks()


def _sign_jwt(claims: dict, kid: str = _TEST_KID) -> str:
    """Sign a JWT with the test private key."""
    return pyjwt.encode(
        claims,
        _TEST_PRIVATE_KEY,
        algorithm="RS256",
        headers={"kid": kid},
    )


# ── AuthResult Tests ────────────────────────────────────────


class TestAuthResult:
    def test_create(self):
        result = AuthResult(
            provider="google",
            provider_user_id="123",
            email="test@example.com",
        )
        assert result.provider == "google"
        assert result.email == "test@example.com"
        assert result.display_name is None
        assert result.raw_claims == {}

    def test_with_all_fields(self):
        result = AuthResult(
            provider="microsoft",
            provider_user_id="abc",
            email="user@firm.com",
            display_name="Jane Doe",
            avatar_url="https://example.com/avatar.jpg",
            raw_claims={"tid": "tenant-1"},
        )
        assert result.display_name == "Jane Doe"
        assert result.raw_claims["tid"] == "tenant-1"


# ── JWKSClient Tests ────────────────────────────────────────


class TestJWKSClient:
    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_and_cache(self):
        url = "https://example.com/.well-known/jwks"
        respx.get(url).mock(
            return_value=httpx.Response(200, json=_TEST_JWKS)
        )

        client = JWKSClient(url, cache_ttl=300)
        key = await client.get_signing_key(_TEST_KID)
        assert key is not None

        # Second call should use cache (no new HTTP request)
        key2 = await client.get_signing_key(_TEST_KID)
        assert key2 is not None
        assert respx.calls.call_count == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_no_matching_kid(self):
        url = "https://example.com/.well-known/jwks"
        respx.get(url).mock(
            return_value=httpx.Response(200, json=_TEST_JWKS)
        )

        client = JWKSClient(url)
        with pytest.raises(AuthError, match="No matching key"):
            await client.get_signing_key("nonexistent-kid")

    @pytest.mark.asyncio
    @respx.mock
    async def test_cache_expiry(self):
        url = "https://example.com/.well-known/jwks"
        respx.get(url).mock(
            return_value=httpx.Response(200, json=_TEST_JWKS)
        )

        client = JWKSClient(url, cache_ttl=0)  # Immediately expired
        await client.get_signing_key(_TEST_KID)
        # Force cache expiry by setting fetched_at to the past
        client._fetched_at = time.monotonic() - 1
        await client.get_signing_key(_TEST_KID)
        assert respx.calls.call_count == 2


# ── Google OIDC Provider Tests ──────────────────────────────


class TestGoogleOIDCProvider:
    CLIENT_ID = "google-client-id"
    CLIENT_SECRET = "google-client-secret"
    REDIRECT_URI = "http://localhost:3000/api/auth/google/callback"

    def _make_google_claims(self, **overrides) -> dict:
        now = int(datetime.now(tz=UTC).timestamp())
        claims = {
            "iss": "https://accounts.google.com",
            "sub": "google-user-123",
            "aud": self.CLIENT_ID,
            "email": "attorney@lawfirm.com",
            "email_verified": True,
            "name": "Jane Attorney",
            "picture": "https://lh3.googleusercontent.com/photo.jpg",
            "hd": "lawfirm.com",
            "iat": now,
            "exp": now + 3600,
        }
        claims.update(overrides)
        return claims

    def test_authorization_url(self):
        provider = GoogleOIDCProvider(self.CLIENT_ID, self.CLIENT_SECRET)
        url = provider.get_authorization_url("state-abc", self.REDIRECT_URI)

        assert "accounts.google.com" in url
        assert f"client_id={self.CLIENT_ID}" in url
        assert "state=state-abc" in url
        assert "response_type=code" in url
        assert "scope=openid+email+profile" in url

    @pytest.mark.asyncio
    @respx.mock
    async def test_successful_callback(self):
        claims = self._make_google_claims()
        id_token = _sign_jwt(claims)

        respx.post(GOOGLE_TOKEN_URL).mock(
            return_value=httpx.Response(200, json={"id_token": id_token})
        )
        respx.get(GOOGLE_JWKS_URL).mock(
            return_value=httpx.Response(200, json=_TEST_JWKS)
        )

        provider = GoogleOIDCProvider(self.CLIENT_ID, self.CLIENT_SECRET)
        result = await provider.handle_callback("auth-code", self.REDIRECT_URI)

        assert result.provider == "google"
        assert result.provider_user_id == "google-user-123"
        assert result.email == "attorney@lawfirm.com"
        assert result.display_name == "Jane Attorney"
        assert result.avatar_url == "https://lh3.googleusercontent.com/photo.jpg"
        assert result.raw_claims["hd"] == "lawfirm.com"

    @pytest.mark.asyncio
    @respx.mock
    async def test_token_exchange_failure(self):
        respx.post(GOOGLE_TOKEN_URL).mock(
            return_value=httpx.Response(400, json={"error": "invalid_grant"})
        )

        provider = GoogleOIDCProvider(self.CLIENT_ID, self.CLIENT_SECRET)
        with pytest.raises(AuthError, match="Token exchange failed: 400"):
            await provider.handle_callback("bad-code", self.REDIRECT_URI)

    @pytest.mark.asyncio
    @respx.mock
    async def test_missing_id_token(self):
        respx.post(GOOGLE_TOKEN_URL).mock(
            return_value=httpx.Response(200, json={"access_token": "at"})
        )

        provider = GoogleOIDCProvider(self.CLIENT_ID, self.CLIENT_SECRET)
        with pytest.raises(AuthError, match="No id_token"):
            await provider.handle_callback("code", self.REDIRECT_URI)

    @pytest.mark.asyncio
    @respx.mock
    async def test_unverified_email(self):
        claims = self._make_google_claims(email_verified=False)
        id_token = _sign_jwt(claims)

        respx.post(GOOGLE_TOKEN_URL).mock(
            return_value=httpx.Response(200, json={"id_token": id_token})
        )
        respx.get(GOOGLE_JWKS_URL).mock(
            return_value=httpx.Response(200, json=_TEST_JWKS)
        )

        provider = GoogleOIDCProvider(self.CLIENT_ID, self.CLIENT_SECRET)
        with pytest.raises(AuthError, match="Email not verified"):
            await provider.handle_callback("code", self.REDIRECT_URI)

    @pytest.mark.asyncio
    @respx.mock
    async def test_missing_email_claim(self):
        claims = self._make_google_claims(email_verified=True)
        del claims["email"]
        id_token = _sign_jwt(claims)

        respx.post(GOOGLE_TOKEN_URL).mock(
            return_value=httpx.Response(200, json={"id_token": id_token})
        )
        respx.get(GOOGLE_JWKS_URL).mock(
            return_value=httpx.Response(200, json=_TEST_JWKS)
        )

        provider = GoogleOIDCProvider(self.CLIENT_ID, self.CLIENT_SECRET)
        with pytest.raises(AuthError, match="No email claim"):
            await provider.handle_callback("code", self.REDIRECT_URI)

    @pytest.mark.asyncio
    @respx.mock
    async def test_expired_token(self):
        past = int(datetime.now(tz=UTC).timestamp()) - 7200
        claims = self._make_google_claims(iat=past, exp=past + 3600)
        id_token = _sign_jwt(claims)

        respx.post(GOOGLE_TOKEN_URL).mock(
            return_value=httpx.Response(200, json={"id_token": id_token})
        )
        respx.get(GOOGLE_JWKS_URL).mock(
            return_value=httpx.Response(200, json=_TEST_JWKS)
        )

        provider = GoogleOIDCProvider(self.CLIENT_ID, self.CLIENT_SECRET)
        with pytest.raises(AuthError, match="ID token validation failed"):
            await provider.handle_callback("code", self.REDIRECT_URI)

    @pytest.mark.asyncio
    @respx.mock
    async def test_wrong_audience(self):
        claims = self._make_google_claims(aud="wrong-client-id")
        id_token = _sign_jwt(claims)

        respx.post(GOOGLE_TOKEN_URL).mock(
            return_value=httpx.Response(200, json={"id_token": id_token})
        )
        respx.get(GOOGLE_JWKS_URL).mock(
            return_value=httpx.Response(200, json=_TEST_JWKS)
        )

        provider = GoogleOIDCProvider(self.CLIENT_ID, self.CLIENT_SECRET)
        with pytest.raises(AuthError, match="ID token validation failed"):
            await provider.handle_callback("code", self.REDIRECT_URI)

    @pytest.mark.asyncio
    @respx.mock
    async def test_no_kid_in_header(self):
        claims = self._make_google_claims()
        # Sign without kid header
        id_token = pyjwt.encode(
            claims, _TEST_PRIVATE_KEY, algorithm="RS256"
        )

        respx.post(GOOGLE_TOKEN_URL).mock(
            return_value=httpx.Response(200, json={"id_token": id_token})
        )

        provider = GoogleOIDCProvider(self.CLIENT_ID, self.CLIENT_SECRET)
        with pytest.raises(AuthError, match="missing kid"):
            await provider.handle_callback("code", self.REDIRECT_URI)

    @pytest.mark.asyncio
    @respx.mock
    async def test_consumer_gmail_no_hd(self):
        """Consumer Gmail accounts don't have hd claim."""
        claims = self._make_google_claims(email="user@gmail.com")
        del claims["hd"]
        id_token = _sign_jwt(claims)

        respx.post(GOOGLE_TOKEN_URL).mock(
            return_value=httpx.Response(200, json={"id_token": id_token})
        )
        respx.get(GOOGLE_JWKS_URL).mock(
            return_value=httpx.Response(200, json=_TEST_JWKS)
        )

        provider = GoogleOIDCProvider(self.CLIENT_ID, self.CLIENT_SECRET)
        result = await provider.handle_callback("code", self.REDIRECT_URI)
        assert result.email == "user@gmail.com"
        assert "hd" not in result.raw_claims


# ── Microsoft OIDC Provider Tests ────────────────────────────


class TestMicrosoftOIDCProvider:
    CLIENT_ID = "ms-client-id"
    CLIENT_SECRET = "ms-client-secret"
    REDIRECT_URI = "http://localhost:3000/api/auth/microsoft/callback"
    TEST_TID = "tenant-uuid-123"

    def _make_ms_claims(self, **overrides) -> dict:
        now = int(datetime.now(tz=UTC).timestamp())
        claims = {
            "iss": f"https://login.microsoftonline.com/{self.TEST_TID}/v2.0",
            "sub": "pairwise-sub-456",  # NOT used for identification
            "oid": "ms-user-oid-789",  # Stable user ID
            "aud": self.CLIENT_ID,
            "email": "attorney@smithlaw.com",
            "name": "John Attorney",
            "preferred_username": "jattorney@smithlaw.com",
            "tid": self.TEST_TID,
            "iat": now,
            "exp": now + 3600,
        }
        claims.update(overrides)
        return claims

    def test_authorization_url(self):
        provider = MicrosoftOIDCProvider(self.CLIENT_ID, self.CLIENT_SECRET)
        url = provider.get_authorization_url("state-xyz", self.REDIRECT_URI)

        assert "login.microsoftonline.com/common" in url
        assert f"client_id={self.CLIENT_ID}" in url
        assert "state=state-xyz" in url
        assert "response_type=code" in url
        assert "response_mode=query" in url

    @pytest.mark.asyncio
    @respx.mock
    async def test_successful_callback(self):
        claims = self._make_ms_claims()
        id_token = _sign_jwt(claims)

        respx.post(MS_TOKEN_URL).mock(
            return_value=httpx.Response(200, json={"id_token": id_token})
        )
        respx.get(MS_JWKS_URL).mock(
            return_value=httpx.Response(200, json=_TEST_JWKS)
        )

        provider = MicrosoftOIDCProvider(self.CLIENT_ID, self.CLIENT_SECRET)
        result = await provider.handle_callback("auth-code", self.REDIRECT_URI)

        assert result.provider == "microsoft"
        assert result.provider_user_id == "ms-user-oid-789"
        assert result.email == "attorney@smithlaw.com"
        assert result.display_name == "John Attorney"
        assert result.avatar_url is None  # MS doesn't include in ID token
        assert result.raw_claims["tid"] == self.TEST_TID

    @pytest.mark.asyncio
    @respx.mock
    async def test_uses_oid_not_sub(self):
        """Verify we use oid (stable) not sub (pairwise) for identification."""
        claims = self._make_ms_claims()
        id_token = _sign_jwt(claims)

        respx.post(MS_TOKEN_URL).mock(
            return_value=httpx.Response(200, json={"id_token": id_token})
        )
        respx.get(MS_JWKS_URL).mock(
            return_value=httpx.Response(200, json=_TEST_JWKS)
        )

        provider = MicrosoftOIDCProvider(self.CLIENT_ID, self.CLIENT_SECRET)
        result = await provider.handle_callback("code", self.REDIRECT_URI)

        assert result.provider_user_id == "ms-user-oid-789"
        assert result.provider_user_id != "pairwise-sub-456"

    @pytest.mark.asyncio
    @respx.mock
    async def test_email_fallback_to_preferred_username(self):
        """Personal MS accounts may not have email, use preferred_username."""
        claims = self._make_ms_claims()
        del claims["email"]
        id_token = _sign_jwt(claims)

        respx.post(MS_TOKEN_URL).mock(
            return_value=httpx.Response(200, json={"id_token": id_token})
        )
        respx.get(MS_JWKS_URL).mock(
            return_value=httpx.Response(200, json=_TEST_JWKS)
        )

        provider = MicrosoftOIDCProvider(self.CLIENT_ID, self.CLIENT_SECRET)
        result = await provider.handle_callback("code", self.REDIRECT_URI)
        assert result.email == "jattorney@smithlaw.com"

    @pytest.mark.asyncio
    @respx.mock
    async def test_no_email_or_preferred_username(self):
        claims = self._make_ms_claims()
        del claims["email"]
        del claims["preferred_username"]
        id_token = _sign_jwt(claims)

        respx.post(MS_TOKEN_URL).mock(
            return_value=httpx.Response(200, json={"id_token": id_token})
        )
        respx.get(MS_JWKS_URL).mock(
            return_value=httpx.Response(200, json=_TEST_JWKS)
        )

        provider = MicrosoftOIDCProvider(self.CLIENT_ID, self.CLIENT_SECRET)
        with pytest.raises(AuthError, match="No email or preferred_username"):
            await provider.handle_callback("code", self.REDIRECT_URI)

    @pytest.mark.asyncio
    @respx.mock
    async def test_missing_oid_claim(self):
        claims = self._make_ms_claims()
        del claims["oid"]
        id_token = _sign_jwt(claims)

        respx.post(MS_TOKEN_URL).mock(
            return_value=httpx.Response(200, json={"id_token": id_token})
        )
        respx.get(MS_JWKS_URL).mock(
            return_value=httpx.Response(200, json=_TEST_JWKS)
        )

        provider = MicrosoftOIDCProvider(self.CLIENT_ID, self.CLIENT_SECRET)
        with pytest.raises(AuthError, match="No oid claim"):
            await provider.handle_callback("code", self.REDIRECT_URI)

    @pytest.mark.asyncio
    @respx.mock
    async def test_missing_tid_claim(self):
        claims = self._make_ms_claims()
        del claims["tid"]
        id_token = _sign_jwt(claims)

        respx.post(MS_TOKEN_URL).mock(
            return_value=httpx.Response(200, json={"id_token": id_token})
        )
        respx.get(MS_JWKS_URL).mock(
            return_value=httpx.Response(200, json=_TEST_JWKS)
        )

        provider = MicrosoftOIDCProvider(self.CLIENT_ID, self.CLIENT_SECRET)
        with pytest.raises(AuthError, match="No tid claim"):
            await provider.handle_callback("code", self.REDIRECT_URI)

    @pytest.mark.asyncio
    @respx.mock
    async def test_invalid_issuer(self):
        claims = self._make_ms_claims(
            iss="https://login.microsoftonline.com/wrong-tenant/v2.0"
        )
        id_token = _sign_jwt(claims)

        respx.post(MS_TOKEN_URL).mock(
            return_value=httpx.Response(200, json={"id_token": id_token})
        )
        respx.get(MS_JWKS_URL).mock(
            return_value=httpx.Response(200, json=_TEST_JWKS)
        )

        provider = MicrosoftOIDCProvider(self.CLIENT_ID, self.CLIENT_SECRET)
        with pytest.raises(AuthError, match="Invalid issuer"):
            await provider.handle_callback("code", self.REDIRECT_URI)

    @pytest.mark.asyncio
    @respx.mock
    async def test_token_exchange_failure(self):
        respx.post(MS_TOKEN_URL).mock(
            return_value=httpx.Response(401, json={"error": "invalid_client"})
        )

        provider = MicrosoftOIDCProvider(self.CLIENT_ID, self.CLIENT_SECRET)
        with pytest.raises(AuthError, match="Token exchange failed: 401"):
            await provider.handle_callback("bad-code", self.REDIRECT_URI)

    @pytest.mark.asyncio
    @respx.mock
    async def test_personal_account(self):
        """Personal Microsoft accounts (Outlook/Hotmail) should work."""
        personal_tid = "9188040d-6c67-4c5b-b112-36a304b66dad"
        claims = self._make_ms_claims(
            tid=personal_tid,
            iss=f"https://login.microsoftonline.com/{personal_tid}/v2.0",
            email="user@outlook.com",
        )
        id_token = _sign_jwt(claims)

        respx.post(MS_TOKEN_URL).mock(
            return_value=httpx.Response(200, json={"id_token": id_token})
        )
        respx.get(MS_JWKS_URL).mock(
            return_value=httpx.Response(200, json=_TEST_JWKS)
        )

        provider = MicrosoftOIDCProvider(self.CLIENT_ID, self.CLIENT_SECRET)
        result = await provider.handle_callback("code", self.REDIRECT_URI)
        assert result.email == "user@outlook.com"
        assert result.raw_claims["tid"] == personal_tid
