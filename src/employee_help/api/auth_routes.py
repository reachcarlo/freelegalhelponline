"""Auth API routes: OAuth login/callback, refresh, logout, user profile.

Endpoints:
    GET  /api/auth/google/login       — Initiate Google OAuth flow
    GET  /api/auth/google/callback    — Handle Google OAuth callback
    GET  /api/auth/microsoft/login    — Initiate Microsoft OAuth flow
    GET  /api/auth/microsoft/callback — Handle Microsoft OAuth callback
    POST /api/auth/refresh            — Rotate access + refresh tokens
    POST /api/auth/logout             — Revoke current session
    GET  /api/auth/me                 — Return current user profile
"""

from __future__ import annotations

import os
import secrets

import structlog
from fastapi import APIRouter, Cookie, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

from employee_help.auth.models import Membership, Organization, User
from employee_help.auth.provider import AuthError, AuthResult
from employee_help.auth.session import SessionManager, _hash_token

auth_router = APIRouter(prefix="/api/auth", tags=["auth"])

logger = structlog.get_logger(__name__)

# Cookie settings — configurable via env vars
_SECURE_COOKIES = os.environ.get("AUTH_COOKIE_SECURE", "true").lower() == "true"
_COOKIE_DOMAIN = os.environ.get("AUTH_COOKIE_DOMAIN")  # None = current domain
_FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")


def _set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    access_max_age: int = 900,
    refresh_max_age: int = 604800,
) -> None:
    """Set HttpOnly auth cookies on a response."""
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=_SECURE_COOKIES,
        samesite="lax",
        path="/",
        max_age=access_max_age,
        domain=_COOKIE_DOMAIN,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=_SECURE_COOKIES,
        samesite="lax",
        path="/api/auth/refresh",
        max_age=refresh_max_age,
        domain=_COOKIE_DOMAIN,
    )


def _clear_auth_cookies(response: Response) -> None:
    """Clear auth cookies from a response."""
    response.delete_cookie(
        key="access_token",
        path="/",
        domain=_COOKIE_DOMAIN,
    )
    response.delete_cookie(
        key="refresh_token",
        path="/api/auth/refresh",
        domain=_COOKIE_DOMAIN,
    )


def _get_redirect_uri(request: Request, provider: str) -> str:
    """Build the OAuth callback redirect URI from the current request."""
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", "localhost:8000"))
    return f"{scheme}://{host}/api/auth/{provider}/callback"


# ── OAuth Login Initiation ─────────────────────────────────────


@auth_router.get("/google/login")
async def google_login(request: Request) -> RedirectResponse:
    """Initiate Google OAuth flow."""
    from employee_help.api.deps import get_google_provider

    provider = get_google_provider()
    if provider is None:
        raise HTTPException(status_code=503, detail="Google OAuth not configured")

    state = secrets.token_urlsafe(32)
    redirect_uri = _get_redirect_uri(request, "google")
    auth_url = provider.get_authorization_url(state, redirect_uri)

    response = RedirectResponse(url=auth_url, status_code=302)
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        secure=_SECURE_COOKIES,
        samesite="lax",
        max_age=300,  # 5 minute TTL
        path="/api/auth/",
        domain=_COOKIE_DOMAIN,
    )
    return response


@auth_router.get("/microsoft/login")
async def microsoft_login(request: Request) -> RedirectResponse:
    """Initiate Microsoft OAuth flow."""
    from employee_help.api.deps import get_microsoft_provider

    provider = get_microsoft_provider()
    if provider is None:
        raise HTTPException(status_code=503, detail="Microsoft OAuth not configured")

    state = secrets.token_urlsafe(32)
    redirect_uri = _get_redirect_uri(request, "microsoft")
    auth_url = provider.get_authorization_url(state, redirect_uri)

    response = RedirectResponse(url=auth_url, status_code=302)
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        secure=_SECURE_COOKIES,
        samesite="lax",
        max_age=300,
        path="/api/auth/",
        domain=_COOKIE_DOMAIN,
    )
    return response


# ── OAuth Callbacks ─────────────────────────────────────────────


@auth_router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """Handle Google OAuth callback."""
    if error:
        logger.warning("google_oauth_error", error=error)
        return RedirectResponse(url=f"{_FRONTEND_URL}/login?error=oauth_denied", status_code=302)

    if not code or not state:
        return RedirectResponse(url=f"{_FRONTEND_URL}/login?error=missing_params", status_code=302)

    from employee_help.api.deps import get_google_provider

    provider = get_google_provider()
    if provider is None:
        raise HTTPException(status_code=503, detail="Google OAuth not configured")

    return await _handle_oauth_callback(request, provider, code, state, "google")


@auth_router.get("/microsoft/callback")
async def microsoft_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """Handle Microsoft OAuth callback."""
    if error:
        logger.warning("microsoft_oauth_error", error=error)
        return RedirectResponse(url=f"{_FRONTEND_URL}/login?error=oauth_denied", status_code=302)

    if not code or not state:
        return RedirectResponse(url=f"{_FRONTEND_URL}/login?error=missing_params", status_code=302)

    from employee_help.api.deps import get_microsoft_provider

    provider = get_microsoft_provider()
    if provider is None:
        raise HTTPException(status_code=503, detail="Microsoft OAuth not configured")

    return await _handle_oauth_callback(request, provider, code, state, "microsoft")


async def _handle_oauth_callback(
    request: Request,
    provider,
    code: str,
    state: str,
    provider_name: str,
) -> RedirectResponse:
    """Shared callback logic for both OAuth providers."""
    from employee_help.api.deps import get_auth_storage, get_session_manager

    # Validate state against cookie
    stored_state = request.cookies.get("oauth_state")
    if not stored_state or not secrets.compare_digest(stored_state, state):
        logger.warning("oauth_state_mismatch", provider=provider_name)
        return RedirectResponse(url=f"{_FRONTEND_URL}/login?error=invalid_state", status_code=302)

    # Exchange code for identity
    redirect_uri = _get_redirect_uri(request, provider_name)
    try:
        auth_result: AuthResult = await provider.handle_callback(code, redirect_uri)
    except AuthError as e:
        logger.warning("oauth_callback_failed", provider=provider_name, error=str(e))
        return RedirectResponse(url=f"{_FRONTEND_URL}/login?error=auth_failed", status_code=302)

    auth_storage = get_auth_storage()
    session_manager = get_session_manager()

    # Find or create user + org
    user, org, membership = _find_or_create_user(auth_storage, auth_result)

    # Update last login
    auth_storage.update_last_login(user.id)

    # Update profile from latest OAuth claims
    auth_storage.update_user_profile(
        user.id,
        display_name=auth_result.display_name,
        avatar_url=auth_result.avatar_url,
        email=auth_result.email,
    )

    # Create session
    client_ip = _get_client_ip(request)
    user_agent = request.headers.get("user-agent")

    access_token, refresh_token = session_manager.create_session(
        user=user,
        org_id=org.id,
        role=membership.role,
        ip_address=client_ip,
        user_agent=user_agent,
    )

    logger.info(
        "user_logged_in",
        user_id=user.id,
        provider=provider_name,
        email=auth_result.email,
    )

    # Set cookies and redirect to frontend
    response = RedirectResponse(url=_FRONTEND_URL, status_code=302)
    _set_auth_cookies(response, access_token, refresh_token)
    # Clear the state cookie
    response.delete_cookie(key="oauth_state", path="/api/auth/", domain=_COOKIE_DOMAIN)
    return response


def _find_or_create_user(
    auth_storage,
    auth_result: AuthResult,
) -> tuple[User, Organization, Membership]:
    """Find existing user or create new user + implicit org + membership."""
    import uuid

    user = auth_storage.find_user_by_provider(
        auth_result.provider, auth_result.provider_user_id
    )

    if user is not None:
        # Existing user — get their org and membership
        memberships = auth_storage.get_user_memberships(user.id)
        if memberships:
            org = auth_storage.get_organization(memberships[0].organization_id)
            return user, org, memberships[0]
        # Edge case: user exists but no membership (shouldn't happen, but handle it)
        org, membership = _create_implicit_org(auth_storage, user)
        return user, org, membership

    # New user — create user + implicit org + membership
    user = User(
        id=str(uuid.uuid4()),
        provider=auth_result.provider,
        provider_user_id=auth_result.provider_user_id,
        email=auth_result.email,
        display_name=auth_result.display_name,
        avatar_url=auth_result.avatar_url,
    )
    auth_storage.create_user(user)

    org, membership = _create_implicit_org(auth_storage, user)
    return user, org, membership


def _create_implicit_org(auth_storage, user: User) -> tuple[Organization, Membership]:
    """Create an implicit single-member organization for a new user."""
    import uuid

    org = Organization(
        id=str(uuid.uuid4()),
        name=user.display_name or user.email.split("@")[0],
        slug=f"user-{uuid.uuid4().hex[:8]}",
    )
    auth_storage.create_organization(org)

    membership = Membership(
        id=str(uuid.uuid4()),
        user_id=user.id,
        organization_id=org.id,
        role="owner",
    )
    auth_storage.create_membership(membership)

    return org, membership


# ── Token Refresh ───────────────────────────────────────────────


@auth_router.post("/refresh")
async def refresh_tokens(
    request: Request,
    refresh_token: str | None = Cookie(default=None),
) -> JSONResponse:
    """Rotate refresh token and issue a new access token."""
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")

    from employee_help.api.deps import get_session_manager

    session_manager = get_session_manager()
    client_ip = _get_client_ip(request)
    user_agent = request.headers.get("user-agent")

    try:
        new_access, new_refresh = session_manager.refresh_session(
            refresh_token,
            ip_address=client_ip,
            user_agent=user_agent,
        )
    except AuthError as e:
        logger.warning("refresh_failed", error=str(e))
        response = JSONResponse(
            status_code=401,
            content={"detail": str(e)},
        )
        _clear_auth_cookies(response)
        return response

    response = JSONResponse(content={"status": "ok"})
    _set_auth_cookies(response, new_access, new_refresh)
    return response


# ── Logout ──────────────────────────────────────────────────────


@auth_router.post("/logout")
async def logout(
    request: Request,
    access_token: str | None = Cookie(default=None),
) -> JSONResponse:
    """Revoke current session and clear cookies."""
    from employee_help.api.deps import get_auth_storage, get_session_manager

    session_manager = get_session_manager()

    if access_token:
        claims = session_manager.validate(access_token)
        if claims:
            # Find the session by the refresh token and revoke it
            # Since we don't have the refresh token here, revoke all sessions
            # for this user to be safe. A more targeted approach would require
            # storing session_id in the access token claims.
            # For now, just revoke all sessions — logout means logout.
            session_manager.revoke_all_sessions(claims.sub)
            logger.info("user_logged_out", user_id=claims.sub)

    response = JSONResponse(content={"status": "ok"})
    _clear_auth_cookies(response)
    return response


# ── User Profile ────────────────────────────────────────────────


@auth_router.get("/me")
async def get_current_user(
    request: Request,
    access_token: str | None = Cookie(default=None),
) -> JSONResponse:
    """Return the current authenticated user's profile."""
    if not access_token:
        raise HTTPException(status_code=401, detail="Authentication required")

    from employee_help.api.deps import get_auth_storage, get_session_manager

    session_manager = get_session_manager()
    claims = session_manager.validate(access_token)
    if claims is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    auth_storage = get_auth_storage()
    user = auth_storage.get_user(claims.sub)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    org = auth_storage.get_organization(claims.org)

    return JSONResponse(content={
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "provider": user.provider,
        "organization": {
            "id": org.id,
            "name": org.name,
            "slug": org.slug,
            "plan_tier": org.plan_tier,
        } if org else None,
        "role": claims.role,
    })


# ── Helpers ─────────────────────────────────────────────────────


def _get_client_ip(request: Request) -> str:
    """Extract real client IP from X-Forwarded-For or fall back to direct IP."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
