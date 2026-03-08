"""Tests for JWT access token creation and validation (A1.2)."""

from __future__ import annotations

import time

import jwt
import pytest

from employee_help.auth.tokens import AccessTokenClaims, create_access_token, validate_access_token

SECRET = "test-secret-key-256-bits-long-enough"


class TestCreateAccessToken:
    def test_creates_valid_jwt(self):
        token = create_access_token(
            user_id="user-1",
            org_id="org-1",
            role="owner",
            email="test@example.com",
            secret=SECRET,
        )
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        assert payload["sub"] == "user-1"
        assert payload["org"] == "org-1"
        assert payload["role"] == "owner"
        assert payload["email"] == "test@example.com"
        assert "iat" in payload
        assert "exp" in payload

    def test_default_ttl_15_minutes(self):
        token = create_access_token(
            user_id="u", org_id="o", role="member", email="a@b.com", secret=SECRET,
        )
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        assert payload["exp"] - payload["iat"] == 900

    def test_custom_ttl(self):
        token = create_access_token(
            user_id="u", org_id="o", role="member", email="a@b.com",
            secret=SECRET, ttl=300,
        )
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        assert payload["exp"] - payload["iat"] == 300

    def test_hs256_algorithm(self):
        token = create_access_token(
            user_id="u", org_id="o", role="member", email="a@b.com", secret=SECRET,
        )
        header = jwt.get_unverified_header(token)
        assert header["alg"] == "HS256"


class TestValidateAccessToken:
    def test_valid_token(self):
        token = create_access_token(
            user_id="user-1", org_id="org-1", role="owner",
            email="test@example.com", secret=SECRET,
        )
        claims = validate_access_token(token, SECRET)
        assert isinstance(claims, AccessTokenClaims)
        assert claims.sub == "user-1"
        assert claims.org == "org-1"
        assert claims.role == "owner"
        assert claims.email == "test@example.com"

    def test_expired_token(self):
        token = create_access_token(
            user_id="u", org_id="o", role="member", email="a@b.com",
            secret=SECRET, ttl=-1,
        )
        assert validate_access_token(token, SECRET) is None

    def test_wrong_secret(self):
        token = create_access_token(
            user_id="u", org_id="o", role="member", email="a@b.com", secret=SECRET,
        )
        assert validate_access_token(token, "wrong-secret") is None

    def test_malformed_token(self):
        assert validate_access_token("not-a-jwt", SECRET) is None

    def test_missing_claims(self):
        """Token with missing required claims returns None."""
        payload = {"sub": "u", "iat": int(time.time()), "exp": int(time.time()) + 300}
        token = jwt.encode(payload, SECRET, algorithm="HS256")
        assert validate_access_token(token, SECRET) is None

    def test_tampered_payload(self):
        """Token with tampered payload fails validation."""
        token = create_access_token(
            user_id="u", org_id="o", role="member", email="a@b.com", secret=SECRET,
        )
        # Corrupt the payload section
        parts = token.split(".")
        parts[1] = parts[1][:-2] + "XX"
        tampered = ".".join(parts)
        assert validate_access_token(tampered, SECRET) is None
