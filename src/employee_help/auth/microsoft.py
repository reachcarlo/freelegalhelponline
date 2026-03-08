"""Microsoft OIDC provider implementation (Entra ID)."""

from __future__ import annotations

from urllib.parse import urlencode

import httpx
import jwt

from employee_help.auth.provider import AuthError, AuthResult, JWKSClient

_AUTH_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
_JWKS_URL = "https://login.microsoftonline.com/common/discovery/v2.0/keys"
_ISSUER_TEMPLATE = "https://login.microsoftonline.com/{tid}/v2.0"
_SCOPES = "openid email profile"


class MicrosoftOIDCProvider:
    """Microsoft OIDC via Entra ID /common endpoint.

    Accepts both personal (Outlook/Hotmail) and organizational (M365) accounts.

    CRITICAL: Uses 'oid' claim (not 'sub') as stable user identifier.
    Microsoft's 'sub' is pair-wise per application — different apps get
    different 'sub' values for the same user. 'oid' is stable across apps
    within the same tenant.

    The /common endpoint allows sign-in from any Microsoft tenant (personal
    or organizational), which means the issuer varies per token. We validate
    the issuer pattern manually after decoding.
    """

    def __init__(self, client_id: str, client_secret: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._jwks = JWKSClient(_JWKS_URL)

    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        """Build the Microsoft OAuth consent screen URL."""
        params = {
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": _SCOPES,
            "state": state,
            "response_mode": "query",
        }
        return f"{_AUTH_URL}?{urlencode(params)}"

    async def handle_callback(
        self, code: str, redirect_uri: str
    ) -> AuthResult:
        """Exchange authorization code for tokens and extract identity."""
        token_data = await self._exchange_code(code, redirect_uri)
        id_token_str = token_data.get("id_token")
        if not id_token_str:
            raise AuthError("No id_token in token response")
        claims = await self._validate_id_token(id_token_str)
        return self._extract_identity(claims)

    async def _exchange_code(self, code: str, redirect_uri: str) -> dict:
        """Exchange authorization code for token response."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                _TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
            )
            if resp.status_code != 200:
                raise AuthError(f"Token exchange failed: {resp.status_code}")
            return resp.json()

    async def _validate_id_token(self, id_token: str) -> dict:
        """Validate ID token signature and claims.

        Microsoft issuer varies per tenant, so we skip automatic issuer
        validation and check it manually against the token's tid claim.
        """
        try:
            header = jwt.get_unverified_header(id_token)
        except jwt.DecodeError as e:
            raise AuthError(f"Malformed ID token: {e}") from e

        kid = header.get("kid")
        if not kid:
            raise AuthError("ID token missing kid header")

        public_key = await self._jwks.get_signing_key(kid)

        try:
            claims = jwt.decode(
                id_token,
                public_key,
                algorithms=["RS256"],
                audience=self._client_id,
                options={"verify_iss": False},
            )
        except jwt.InvalidTokenError as e:
            raise AuthError(f"ID token validation failed: {e}") from e

        # Manual issuer validation against tenant ID
        tid = claims.get("tid")
        if not tid:
            raise AuthError("No tid claim in ID token")

        expected_issuer = _ISSUER_TEMPLATE.format(tid=tid)
        if claims.get("iss") != expected_issuer:
            raise AuthError(
                f"Invalid issuer: expected {expected_issuer}, "
                f"got {claims.get('iss')}"
            )

        return claims

    def _extract_identity(self, claims: dict) -> AuthResult:
        """Extract user identity from validated ID token claims.

        Uses 'oid' (not 'sub') for stable identification.
        Falls back from 'email' to 'preferred_username' since personal
        Microsoft accounts may not include the 'email' claim.
        """
        oid = claims.get("oid")
        if not oid:
            raise AuthError("No oid claim in ID token")

        email = claims.get("email") or claims.get("preferred_username")
        if not email:
            raise AuthError("No email or preferred_username in ID token")

        return AuthResult(
            provider="microsoft",
            provider_user_id=oid,
            email=email,
            display_name=claims.get("name"),
            avatar_url=None,  # Microsoft doesn't include avatar in ID token
            raw_claims=claims,
        )
