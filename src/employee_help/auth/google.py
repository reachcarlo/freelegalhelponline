"""Google OIDC provider implementation."""

from __future__ import annotations

from urllib.parse import urlencode

import httpx
import jwt

from employee_help.auth.provider import AuthError, AuthResult, JWKSClient

_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
_ISSUERS = ("https://accounts.google.com", "accounts.google.com")
_SCOPES = "openid email profile"


class GoogleOIDCProvider:
    """Google OIDC authentication via direct token exchange.

    Uses the standard OAuth 2.0 authorization code flow:
    1. Redirect user to Google's consent screen
    2. Exchange authorization code for tokens
    3. Validate ID token JWT (RS256 signature, claims)
    4. Extract identity (sub, email, name, picture)
    """

    def __init__(self, client_id: str, client_secret: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._jwks = JWKSClient(_JWKS_URL)

    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        """Build the Google OAuth consent screen URL."""
        params = {
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": _SCOPES,
            "state": state,
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
        """Validate ID token signature and claims."""
        try:
            header = jwt.get_unverified_header(id_token)
        except jwt.DecodeError as e:
            raise AuthError(f"Malformed ID token: {e}") from e

        kid = header.get("kid")
        if not kid:
            raise AuthError("ID token missing kid header")

        public_key = await self._jwks.get_signing_key(kid)

        try:
            return jwt.decode(
                id_token,
                public_key,
                algorithms=["RS256"],
                audience=self._client_id,
                issuer=list(_ISSUERS),
            )
        except jwt.InvalidTokenError as e:
            raise AuthError(f"ID token validation failed: {e}") from e

    def _extract_identity(self, claims: dict) -> AuthResult:
        """Extract user identity from validated ID token claims."""
        if not claims.get("email_verified", False):
            raise AuthError("Email not verified by Google")

        email = claims.get("email")
        if not email:
            raise AuthError("No email claim in ID token")

        return AuthResult(
            provider="google",
            provider_user_id=claims["sub"],
            email=email,
            display_name=claims.get("name"),
            avatar_url=claims.get("picture"),
            raw_claims=claims,
        )
