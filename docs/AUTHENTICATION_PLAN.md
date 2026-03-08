# Authentication & User Accounts: Implementation Plan

> **Status**: In Progress (A1.1 complete)
> **Created**: 2026-03-07
> **GTM Strategy**: Bottom-up PLG (individual attorneys) → enterprise upsell (their firms)
> **Auth Providers**: Google OIDC + Microsoft OIDC (no email/password, no local credentials)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architectural Decisions & Rationale](#architectural-decisions--rationale)
3. [Security Architecture](#security-architecture)
4. [Data Model](#data-model)
5. [Phase A1: Authentication Foundation](#phase-a1-authentication-foundation)
6. [Phase A2: Data Ownership & Tenant Isolation](#phase-a2-data-ownership--tenant-isolation)
7. [Phase A3: Security Hardening & Audit](#phase-a3-security-hardening--audit)
8. [Phase A4: Organization & Team Support](#phase-a4-organization--team-support)
9. [Phase A5: Enterprise SSO & SCIM](#phase-a5-enterprise-sso--scim)
10. [Migration Plan for Existing Features](#migration-plan-for-existing-features)
11. [Cost Analysis](#cost-analysis)
12. [Appendix: Provider Comparison & Research Notes](#appendix-provider-comparison--research-notes)

---

## Executive Summary

### The Problem

Employee Help has reached a critical inflection point. Users are uploading private case files (LITIGAGENT), generating discovery documents with confidential party information, and building workflows around sensitive legal matters. Every one of these features currently operates without authentication — no user accounts, no access control, no data isolation. Any user who knows a case UUID can access any other user's files.

This is not a feature gap. It is a security liability that blocks the entire attorney market.

### The Solution

Google and Microsoft OAuth exclusively. No email/password. No magic links. No local credential storage. Two buttons on a login page: "Sign in with Google" and "Sign in with Microsoft."

**Why this is the right constraint:**

1. **Zero credential liability.** We never see, store, hash, or transmit a password. There is no password reset flow to build, no brute-force attack surface, no credential stuffing risk. When a data breach hits the news, we can truthfully say: "We do not store passwords. Period."

2. **Inherited security infrastructure.** Google and Microsoft spend billions annually on authentication security — anomalous login detection, device fingerprinting, phishing-resistant MFA (passkeys, FIDO2), impossible travel detection, compromised credential monitoring. By delegating authentication to them, we inherit all of it. We cannot build this. We should not try.

3. **100% market coverage.** Every attorney in the United States has either a Google account (Workspace or personal) or a Microsoft account (M365 or personal). 90% of AmLaw 200 firms run Microsoft 365. The remainder use Google Workspace. There is no attorney who cannot sign in.

4. **PLG → Enterprise alignment.** Individual attorneys sign in with their work Google/Microsoft accounts. When their firm buys an enterprise plan, those same accounts become SSO-managed through the firm's identity provider. The transition is seamless — same email, same identity, upgraded authentication method. No account migration required.

### The GTM Motion

```
Individual attorney signs up (Google/Microsoft OAuth)
    → Uses product, uploads case files, generates documents
    → Mentions product to colleagues
    → Colleagues sign up with same-domain work emails
    → We detect organic clusters: 5 attorneys at @smithlaw.com
    → Sales reaches out to firm IT/managing partner
    → Firm signs enterprise deal
    → IT configures SSO via Entra ID or Google Workspace
    → Existing individual accounts seamlessly linked to firm org
    → SCIM auto-provisions remaining attorneys
```

This is the Slack/Notion/Figma playbook adapted for legal. The authentication system must be designed from day one to support this full arc without a rewrite.

---

## Architectural Decisions & Rationale

### AD-1: No Email/Password Authentication

**Decision**: Only Google OIDC and Microsoft OIDC. No email/password, no magic links, no SMS OTP.

**Rationale (DIP, ISP — reduce surface area):**
- Every authentication method we support is attack surface we maintain. Email/password requires: password hashing (argon2/bcrypt), reset flow, email infrastructure, rate limiting on login attempts, credential stuffing detection, breach monitoring. Google/Microsoft OAuth requires: validating a signed JWT. The complexity difference is 10:1.
- ABA Model Rule 1.6(c) requires "reasonable efforts to prevent unauthorized disclosure." Eliminating local credential storage is the most reasonable effort possible — it removes the most common breach vector entirely.
- Support cost: zero "forgot password" tickets. Zero account lockout tickets. Zero "was my password in a breach?" tickets.

**Tradeoff acknowledged**: A tiny percentage of attorneys may not have Google or Microsoft accounts. In practice, this percentage is effectively zero for our target market (California employment law practitioners). If an edge case surfaces, we revisit — but we do not design for it today (YAGNI).

### AD-2: Direct OAuth First, Auth Provider Later

**Decision**: Phase A1 uses Google and Microsoft OIDC directly (their official Python SDKs). Phase A5 introduces WorkOS for enterprise SSO/SCIM only when the first enterprise deal demands it.

**Rationale (YAGNI, ISP — don't depend on things you don't need):**
- WorkOS is free for user management up to 1M MAUs, but introduces a dependency on a third-party service for every authentication request. If WorkOS has an outage, no one can log in. Direct OIDC against Google/Microsoft means authentication depends only on the identity providers themselves — services with 99.99%+ uptime SLAs.
- WorkOS adds value when you need SAML SSO connections, SCIM directory sync, and the Admin Portal. We need none of these for Phase A1-A3 (individual users). Paying the complexity cost now for Phase A5 capabilities violates SDP (Stable Dependencies Principle) — we'd be depending on a less stable component for features we don't use.
- The architecture protects against this being a hard swap. We define an `AuthProvider` interface (Strategy pattern). Phase A1 implements `GoogleOIDCProvider` and `MicrosoftOIDCProvider`. Phase A5 implements `WorkOSProvider`. The swap is a configuration change, not a rewrite.

**Exit strategy**: If we need to swap providers, only the `auth/providers/` module changes. No route handlers, no middleware, no frontend logic changes. This is the Dependency Rule in action — business logic never imports from the auth provider layer.

### AD-3: Organization as First-Class Entity from Day One

**Decision**: Every user gets an implicit single-member organization at signup. `organization_id` is a foreign key on the `cases` table from day one, even if we don't expose organization features in the UI until Phase A4.

**Rationale (research-validated, CCP — Common Closure):**
- The market research is unequivocal: "Retrofitting multi-tenancy costs 3-5x more than building it correctly from the start." We agree.
- By making organization_id present from day one, the transition from individual → team → enterprise requires zero schema migrations on the core data tables. The only changes are: creating new organizations, adding memberships, and enabling org-level settings.
- The user never sees or interacts with "organization" in Phase A1-A3. Their implicit org is invisible. But the data model is ready.

### AD-4: HttpOnly Cookie Sessions, Not Bearer Tokens

**Decision**: Authentication state stored in HttpOnly, Secure, SameSite=Lax cookies. No `Authorization: Bearer` header. No localStorage tokens.

**Rationale (OWASP best practice, reduce XSS blast radius):**
- Bearer tokens stored in localStorage are accessible to any JavaScript running on the page. A single XSS vulnerability (in our code, in a dependency, in a browser extension) can exfiltrate the token and impersonate the user indefinitely.
- HttpOnly cookies are invisible to JavaScript. Even if XSS is achieved, the attacker cannot read the session token. Combined with SameSite=Lax, CSRF is mitigated without additional tokens.
- SameSite=Lax (not Strict) because Strict blocks the OAuth redirect callback — the browser won't send cookies when navigating from Google/Microsoft back to our site.
- The session cookie contains a signed, short-lived (15-minute) access claim. A separate HttpOnly refresh cookie (7-day expiry) handles token rotation. On expiry, the frontend receives a 401 and transparently refreshes via a `/api/auth/refresh` endpoint.

### AD-5: SQLite for User Data (Same Database)

**Decision**: User, organization, and membership tables live in the same `employee_help.db` SQLite database as knowledge base and case data.

**Rationale (Orthogonality — minimize moving parts):**
- The product currently runs on a single SQLite database in WAL mode. Adding a second database for user data introduces connection management complexity, transaction coordination across databases, and deployment complexity — all for zero benefit at current scale.
- User data volume is trivially small. Even at 10,000 users with 100 organizations, the user tables add < 1MB to the database. SQLite handles this without breaking a sweat.
- When the product outgrows SQLite (>100K concurrent users, multi-server deployment), the migration to PostgreSQL moves all tables together. Same schema, same relationships, same queries. The `Storage` class abstraction already isolates SQL from business logic.

**Tradeoff**: Single-server deployment. SQLite cannot be shared across multiple application instances. This is acceptable for the current scale and for at least the next 12-18 months. When horizontal scaling is needed, migrate to PostgreSQL — the auth interface abstraction means this is a storage swap, not an architecture rewrite.

---

## Security Architecture

### Threat Model

| Threat | Mitigation | Phase |
|--------|-----------|-------|
| Credential theft | No credentials stored. OAuth only. | A1 |
| Session hijacking | HttpOnly + Secure + SameSite cookies. Short-lived access tokens (15 min). | A1 |
| XSS token exfiltration | No tokens in JavaScript-accessible storage. CSP headers. | A1, A3 |
| Cross-user data access | `user_id` FK on cases. Ownership check in every query. | A2 |
| CSRF | SameSite=Lax cookies + Origin header validation. | A1 |
| Unauthorized file access | Files served through authenticated API endpoint, never as static files. | A2 |
| Account takeover | Delegated to Google/Microsoft (MFA, anomalous login detection). | A1 |
| Token replay | Short-lived access tokens (15 min). Refresh token rotation. | A1 |
| Privilege escalation | RBAC checked in middleware, not in route handlers. | A2, A4 |
| Data leakage in logs | PIIs (email, name) redacted from structlog output. Structured logging with allow-listed fields only. | A3 |
| Insider threat (compromised server) | File data encrypted at rest (infrastructure-level). Audit logs for all data access. | A3 |

### Security Guarantees We Can Make to Attorneys

1. **"We never see your password."** — True. We never receive, store, or transmit passwords. Authentication is handled entirely by Google or Microsoft.
2. **"Your files are isolated."** — True. Every case belongs to one user (Phase A1) or one organization (Phase A4). Database queries enforce ownership. There is no API endpoint that can return another user's data.
3. **"Your login is protected by your provider's security."** — True. If a user has MFA enabled on their Google/Microsoft account, that MFA protects access to Employee Help. If their IT admin enforces Conditional Access policies, those policies apply. We inherit the full security posture of the identity provider.
4. **"We audit every access."** — True from Phase A3. Every file download, case access, and document generation is logged with user ID, timestamp, and action.
5. **"Your data is encrypted."** — True. In transit: TLS 1.3 (HTTPS). At rest: infrastructure-level encryption (cloud provider encrypted volumes for production deployments; for development, macOS FileVault). We do not implement application-level encryption because it adds complexity without meaningful security benefit when the server process must decrypt data to serve it — the real protection is the authentication and authorization layer.

### What We Explicitly Do NOT Build

- **Password hashing or storage** — eliminated by design.
- **Email verification flows** — Google/Microsoft have already verified the email.
- **MFA implementation** — delegated to identity provider. We respect their MFA decisions.
- **Anomalous login detection** — delegated to identity provider.
- **Account recovery** — delegated to identity provider. "Reset your Google password" or "Reset your Microsoft password."
- **CAPTCHA / bot detection on login** — no login form to protect. OAuth redirect flow is inherently bot-resistant.

This is the core insight: **by refusing to build authentication ourselves, we achieve better security than we could ever build**. Google and Microsoft employ dedicated security teams larger than our entire company will ever be. Leveraging their infrastructure is not laziness — it is the architecturally correct decision.

---

## Data Model

### Entity Relationship Diagram

```
┌──────────────┐       ┌──────────────────┐       ┌──────────────┐
│    users      │──────▶│   memberships    │◀──────│organizations │
│              │  1:N  │                  │  N:1  │              │
│ id (UUID PK) │       │ user_id (FK)     │       │ id (UUID PK) │
│ provider     │       │ organization_id  │       │ name         │
│ provider_uid │       │ role             │       │ slug         │
│ email        │       │ created_at       │       │ plan_tier    │
│ display_name │       └──────────────────┘       │ sso_provider │
│ avatar_url   │                                  │ sso_config   │
│ created_at   │       ┌──────────────────┐       │ created_at   │
│ last_login   │       │     cases        │       └──────────────┘
│ is_active    │       │                  │              │
└──────┬───────┘       │ id (UUID PK)    │              │
       │               │ user_id (FK) ◀──┘──────────────┘
       │               │ organization_id (FK)
       │               │ name            │
       │               │ ...existing...  │
       │               └────────┬────────┘
       │                        │
       │               ┌────────┴────────┐
       │               │   case_files    │
       │               │   case_notes    │
       │               │   case_chunks   │
       │               │  (unchanged —   │
       │               │   access via    │
       │               │   case ownership│
       │               └─────────────────┘
       │
       ▼
┌──────────────────┐
│  sessions        │
│                  │
│ id (UUID PK)     │
│ user_id (FK)     │
│ refresh_token    │
│ expires_at       │
│ created_at       │
│ last_used_at     │
│ ip_address       │
│ user_agent       │
│ is_revoked       │
└──────────────────┘
```

### Table Definitions

```sql
-- Users: identity established by Google/Microsoft OAuth
-- No password column. No email_verified column (provider guarantees it).
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,                    -- UUID
    provider TEXT NOT NULL,                 -- 'google' | 'microsoft'
    provider_user_id TEXT NOT NULL,         -- Provider's stable user ID
    email TEXT NOT NULL,                    -- Email from OAuth profile
    display_name TEXT,                      -- Name from OAuth profile
    avatar_url TEXT,                        -- Profile picture URL
    is_active INTEGER NOT NULL DEFAULT 1,   -- Soft-delete / suspension
    created_at TEXT NOT NULL,               -- ISO 8601 UTC
    last_login_at TEXT NOT NULL,            -- Updated on each login
    UNIQUE(provider, provider_user_id)      -- One account per provider identity
);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_provider ON users(provider, provider_user_id);

-- Organizations: implicit for individuals, explicit for teams/enterprise
-- Every user gets one at signup. Invisible until Phase A4.
CREATE TABLE IF NOT EXISTS organizations (
    id TEXT PRIMARY KEY,                    -- UUID
    name TEXT NOT NULL,                     -- Firm name or user's display name
    slug TEXT UNIQUE NOT NULL,              -- URL-safe identifier
    plan_tier TEXT NOT NULL DEFAULT 'individual',  -- individual|team|enterprise
    sso_provider TEXT,                      -- NULL | 'google_workspace' | 'entra_id' | 'saml'
    sso_config TEXT,                        -- JSON blob for SSO settings (Phase A5)
    max_seats INTEGER,                      -- NULL = unlimited (individual), N = team/enterprise
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Memberships: users ↔ organizations join table
-- One user can belong to multiple orgs (of-counsel, outside counsel).
CREATE TABLE IF NOT EXISTS memberships (
    id TEXT PRIMARY KEY,                    -- UUID
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'member',    -- 'owner' | 'admin' | 'member'
    created_at TEXT NOT NULL,
    UNIQUE(user_id, organization_id)        -- One membership per user per org
);
CREATE INDEX IF NOT EXISTS idx_memberships_user ON memberships(user_id);
CREATE INDEX IF NOT EXISTS idx_memberships_org ON memberships(organization_id);

-- Sessions: server-side session tracking for refresh token rotation
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,                    -- UUID (this is the refresh token ID)
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    refresh_token_hash TEXT NOT NULL,       -- SHA-256 of the refresh token value
    expires_at TEXT NOT NULL,               -- Refresh token expiry (7 days)
    created_at TEXT NOT NULL,
    last_used_at TEXT NOT NULL,
    ip_address TEXT,                        -- For audit trail
    user_agent TEXT,                        -- For "active sessions" display
    is_revoked INTEGER NOT NULL DEFAULT 0   -- Soft-revoke without delete
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);

-- Audit log: immutable append-only table for security events
-- Phase A3 implementation, schema defined now.
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    organization_id TEXT REFERENCES organizations(id) ON DELETE SET NULL,
    action TEXT NOT NULL,                   -- 'login' | 'logout' | 'case.create' | 'file.upload' | 'file.download' | ...
    resource_type TEXT,                     -- 'case' | 'file' | 'note' | 'session'
    resource_id TEXT,                       -- UUID of the affected resource
    ip_address TEXT,
    user_agent TEXT,
    metadata TEXT,                          -- JSON: additional context
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);
```

### Modifications to Existing Tables

```sql
-- Add user_id and organization_id to cases table
ALTER TABLE cases ADD COLUMN user_id TEXT REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE cases ADD COLUMN organization_id TEXT REFERENCES organizations(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_cases_user ON cases(user_id);
CREATE INDEX IF NOT EXISTS idx_cases_org ON cases(organization_id);
```

Case files, case notes, and case chunks inherit access control through the `cases` table — no additional columns needed. Access check: `SELECT ... FROM cases WHERE id = ? AND (user_id = ? OR organization_id IN (SELECT organization_id FROM memberships WHERE user_id = ?))`.

---

## Phase A1: Authentication Foundation

**Goal**: Users can sign in with Google or Microsoft. Sessions are managed. Authenticated users access a basic account. All new feature work requires login.

**Prerequisites**: None. This is the first phase.

### A1.1 — Auth Provider Interface & OIDC Implementations ✅ COMPLETE (2026-03-07)

**Files to create:**
- `src/employee_help/auth/__init__.py`
- `src/employee_help/auth/provider.py` — `AuthProvider` protocol + `AuthResult` dataclass
- `src/employee_help/auth/google.py` — `GoogleOIDCProvider` implementation
- `src/employee_help/auth/microsoft.py` — `MicrosoftOIDCProvider` implementation
- `src/employee_help/auth/session.py` — `SessionManager` (create, validate, refresh, revoke)
- `src/employee_help/auth/models.py` — `User`, `Organization`, `Membership`, `Session` dataclasses
- `src/employee_help/auth/storage.py` — `AuthStorage` (user/org/membership/session CRUD against SQLite)

**Architecture:**

```python
# provider.py — the interface (Strategy pattern)
from dataclasses import dataclass
from typing import Protocol

@dataclass
class AuthResult:
    provider: str           # 'google' | 'microsoft'
    provider_user_id: str   # Stable ID from the provider
    email: str              # Verified email
    display_name: str | None
    avatar_url: str | None
    raw_claims: dict        # Full token claims for audit

class AuthProvider(Protocol):
    """Validates an OAuth callback and returns identity claims."""
    def get_authorization_url(self, state: str, redirect_uri: str) -> str: ...
    async def handle_callback(self, code: str, redirect_uri: str) -> AuthResult: ...
```

```python
# google.py — concrete implementation
class GoogleOIDCProvider:
    """Google OIDC via https://accounts.google.com/.well-known/openid-configuration"""

    def __init__(self, client_id: str, client_secret: str):
        self._client_id = client_id
        self._client_secret = client_secret

    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        # Build URL to https://accounts.google.com/o/oauth2/v2/auth
        # Scopes: openid email profile
        # response_type: code
        # access_type: offline (for refresh token on first consent)
        ...

    async def handle_callback(self, code: str, redirect_uri: str) -> AuthResult:
        # 1. Exchange code for tokens at https://oauth2.googleapis.com/token
        # 2. Validate ID token (signature, iss, aud, exp)
        # 3. Extract: sub (stable user ID), email, name, picture
        # 4. Verify email_verified == true
        # 5. Return AuthResult
        ...
```

```python
# microsoft.py — concrete implementation
class MicrosoftOIDCProvider:
    """Microsoft OIDC via Entra ID /common endpoint (personal + organizational)."""

    # CRITICAL: Use 'oid' claim (not 'sub') for stable user identification.
    # 'sub' is pair-wise per application in Microsoft's implementation.
    # Use /common endpoint to accept both personal and organizational accounts.
    ...
```

**Key implementation details:**

- **Google**: Use `sub` claim as `provider_user_id`. Validate `email_verified` is true. Check for `hd` (hosted domain) claim — present for Workspace, absent for consumer Gmail. Store `hd` in user metadata for future enterprise domain-claiming.
- **Microsoft**: Use `oid` claim (NOT `sub`) as `provider_user_id` — `sub` is pair-wise per app in Entra ID. Use the `/common` endpoint to accept both personal (@outlook.com) and organizational (company M365) accounts. Store `tid` (tenant ID) for future enterprise association.
- **Token validation**: Validate JWT signature against provider's JWKS endpoint. Cache JWKS keys with 24h TTL. Validate `iss`, `aud`, `exp`, `iat` claims. Reject tokens older than 5 minutes.
- **httpx for token exchange**: We already depend on httpx. No new dependency needed.

**Dependencies to add:**
- `PyJWT>=2.8` — JWT decoding and validation (already available as `pyjwt`)
- `cryptography>=42.0` — Required by PyJWT for RS256 signature verification (likely already installed as transitive dep)

No Google SDK, no Microsoft SDK, no MSAL. Pure OIDC. The protocol is standardized — we don't need provider-specific SDKs for token exchange and JWT validation. Two providers, same flow, different endpoints.

**Tasks:**
1. Create `auth/provider.py` with `AuthProvider` protocol and `AuthResult` dataclass
2. Create `auth/google.py` implementing `GoogleOIDCProvider`
3. Create `auth/microsoft.py` implementing `MicrosoftOIDCProvider`
4. Create `auth/models.py` with `User`, `Organization`, `Membership`, `Session` dataclasses
5. Create `auth/storage.py` with `AuthStorage` class (user CRUD, org CRUD, session CRUD)
6. Add schema migration in `storage/storage.py` for `users`, `organizations`, `memberships`, `sessions`, `audit_log` tables
7. Write tests: mock OIDC token exchange, validate claim extraction, test storage CRUD
8. Register Google OAuth app in Google Cloud Console, get `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET`
9. Register Microsoft app in Azure Portal (App Registrations), get `MICROSOFT_CLIENT_ID` + `MICROSOFT_CLIENT_SECRET`
10. Add env vars to `.env.example`

**Gate**: Unit tests pass for both providers (mocked). `AuthStorage` CRUD tests pass against test SQLite.

### A1.2 — Session Management

**Files to create/modify:**
- `src/employee_help/auth/session.py` — `SessionManager` class
- `src/employee_help/auth/tokens.py` — JWT access token creation/validation

**Session flow:**

```
User clicks "Sign in with Google"
    → Frontend redirects to /api/auth/google/login
    → Backend generates state token, stores in cookie, redirects to Google
    → Google authenticates user, redirects to /api/auth/google/callback?code=...&state=...
    → Backend validates state, exchanges code for tokens, validates ID token
    → Backend creates/updates User record in DB
    → Backend creates Session record, generates refresh token
    → Backend signs short-lived access JWT (15 min) with user_id + org_id
    → Backend sets two HttpOnly cookies:
        - `access_token` (15 min, HttpOnly, Secure, SameSite=Lax, Path=/)
        - `refresh_token` (7 days, HttpOnly, Secure, SameSite=Lax, Path=/api/auth/refresh)
    → Backend redirects to frontend (e.g., /tools/litigagent or / )
```

**Access token (JWT) claims:**
```json
{
  "sub": "user-uuid",
  "org": "org-uuid",
  "role": "owner",
  "email": "user@example.com",
  "iat": 1709827200,
  "exp": 1709828100
}
```

**Signing**: HS256 with a server-side secret (`AUTH_JWT_SECRET` env var, 256-bit random). Not RS256 — we don't need asymmetric signing because the same server issues and validates. Simpler is better.

**Refresh token rotation**: Each refresh request issues a new refresh token and invalidates the old one. If a revoked refresh token is presented (replay attack), all sessions for that user are revoked (breach detected).

**Tasks:**
1. Implement `SessionManager` with create, validate, refresh, revoke, revoke_all methods
2. Implement `create_access_token()` and `validate_access_token()` in `tokens.py`
3. Generate `AUTH_JWT_SECRET` documentation (instruction to generate via `python -c "import secrets; print(secrets.token_hex(32))"`)
4. Write tests for token lifecycle: create, validate, expire, refresh, revoke, replay detection

**Gate**: Full session lifecycle test passes — create session, validate access token, expire access token, refresh, validate new access token, revoke session.

### A1.3 — Auth API Routes

**Files to create/modify:**
- `src/employee_help/api/auth_routes.py` — Auth router with login/callback/refresh/logout/me endpoints
- `src/employee_help/api/main.py` — Register auth router
- `src/employee_help/api/deps.py` — Add auth service initialization

**Endpoints:**

| Method | Path | Auth Required | Purpose |
|--------|------|--------------|---------|
| GET | `/api/auth/google/login` | No | Initiate Google OAuth flow |
| GET | `/api/auth/google/callback` | No | Handle Google OAuth callback |
| GET | `/api/auth/microsoft/login` | No | Initiate Microsoft OAuth flow |
| GET | `/api/auth/microsoft/callback` | No | Handle Microsoft OAuth callback |
| POST | `/api/auth/refresh` | Refresh cookie | Rotate access + refresh tokens |
| POST | `/api/auth/logout` | Yes | Revoke current session |
| GET | `/api/auth/me` | Yes | Return current user profile |
| GET | `/api/auth/sessions` | Yes | List active sessions (Phase A3) |
| DELETE | `/api/auth/sessions/{id}` | Yes | Revoke a specific session (Phase A3) |

**OAuth state parameter**: Generated per login attempt, stored in a short-lived HttpOnly cookie (5 min TTL). Validated on callback to prevent CSRF during OAuth flow. This replaces the need for server-side state storage.

**Tasks:**
1. Create `auth_routes.py` with all endpoints
2. Implement `get_current_user()` dependency (reads access token cookie, validates JWT, returns `User`)
3. Register `auth_router` in `main.py`
4. Initialize `AuthStorage` and providers in `deps.py`
5. Add `AUTH_JWT_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET` to env config
6. Write API tests for full OAuth flow (mocked provider responses)

**Gate**: Can complete full login flow with mocked Google/Microsoft responses. `/api/auth/me` returns user profile. Logout clears cookies and revokes session.

### A1.4 — Auth Middleware

**Files to modify:**
- `src/employee_help/api/main.py` — Add authentication middleware

**Middleware behavior:**

```python
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Extract and validate user identity from access token cookie."""

    # Public paths that don't require authentication:
    PUBLIC_PATHS = {
        "/api/auth/",       # Auth endpoints themselves
        "/api/health",      # Health check
        "/health",          # Health check alias
        "/api/ask",         # Public RAG Q&A (consumer mode) — rate limited by IP
        "/api/deadlines",   # Public tool
        "/api/agency-routing",  # Public tool
        "/api/unpaid-wages",    # Public tool
        "/api/incident-guide",  # Public tool
        "/api/intake",          # Public tool
    }

    # Check if path is public
    if any(request.url.path.startswith(p) for p in PUBLIC_PATHS):
        return await call_next(request)

    # Extract access token from cookie
    access_token = request.cookies.get("access_token")
    if not access_token:
        return JSONResponse(status_code=401, content={"detail": "Authentication required"})

    # Validate JWT and extract user
    user = validate_access_token(access_token)
    if not user:
        return JSONResponse(status_code=401, content={"detail": "Invalid or expired token"})

    # Attach user to request state for downstream handlers
    request.state.user = user
    return await call_next(request)
```

**Key decision: Public vs. authenticated endpoints.** Consumer-facing tools (RAG Q&A, calculators, intake) remain publicly accessible with IP-based rate limiting. This preserves the PLG funnel — a potential user can try the product without signing up. Attorney tools (LITIGAGENT, discovery, objections) require authentication because they involve private case data.

| Feature | Auth Required | Rationale |
|---------|:---:|-----------|
| RAG Q&A (consumer mode) | No | PLG funnel — try before you sign up |
| RAG Q&A (attorney mode) | Yes | Attorney work product = private |
| Calculators (deadlines, wages) | No | Public tools, no private data |
| Intake questionnaire | No | Lead generation, no private data |
| Discovery tools | Yes | Private case data, document generation |
| Objection drafter | Yes | Private case data |
| LITIGAGENT (cases/files) | Yes | Private case files |
| Feedback | No | Anonymous product feedback |

**Tasks:**
1. Implement auth middleware in `main.py`
2. Define `PUBLIC_PATHS` configuration (should be config-driven, not hardcoded)
3. Add `request.state.user` pattern for accessing current user in route handlers
4. Update rate limiting: authenticated users get per-user limits (higher), unauthenticated get per-IP limits (lower)
5. Write middleware tests: public paths pass through, authenticated paths require valid token, expired tokens return 401

**Gate**: Unauthenticated request to `/api/cases` returns 401. Authenticated request to `/api/cases` succeeds. Unauthenticated request to `/api/ask` succeeds (public).

### A1.5 — Frontend Auth Flow

**Files to create/modify:**
- `frontend/app/login/page.tsx` — Login page with Google/Microsoft buttons
- `frontend/lib/auth.ts` — Auth utility functions
- `frontend/components/auth-guard.tsx` — Client-side auth check wrapper
- `frontend/components/user-menu.tsx` — User avatar + dropdown (logout, account)
- `frontend/app/layout.tsx` — Add auth provider context
- `frontend/middleware.ts` — Next.js middleware for route protection

**Login page design (minimal):**

```
┌─────────────────────────────────────┐
│                                     │
│         Employee Help               │
│         [logo]                      │
│                                     │
│   California Employment Law         │
│   AI-Powered Legal Guidance         │
│                                     │
│  ┌─────────────────────────────┐    │
│  │  ☐ Sign in with Google      │    │
│  └─────────────────────────────┘    │
│                                     │
│  ┌─────────────────────────────┐    │
│  │  ☐ Sign in with Microsoft   │    │
│  └─────────────────────────────┘    │
│                                     │
│   By signing in, you agree to our   │
│   Terms of Service and Privacy      │
│   Policy.                           │
│                                     │
│   Your files are encrypted and      │
│   private. We never store your      │
│   password.                         │
│                                     │
└─────────────────────────────────────┘
```

**Auth state management:**
- `GET /api/auth/me` on app load to check if session is valid
- If 401, show login page (for protected routes) or continue anonymously (for public routes)
- Store user info in React context (`AuthContext`) — NOT in localStorage
- On logout, `POST /api/auth/logout` + clear context + redirect to home

**Next.js middleware** (runs on edge, before page render):
```typescript
// middleware.ts
const PROTECTED_ROUTES = ['/tools/litigagent', '/tools/discovery', '/tools/objections'];

export function middleware(request: NextRequest) {
    const accessToken = request.cookies.get('access_token');
    const isProtectedRoute = PROTECTED_ROUTES.some(r => request.nextUrl.pathname.startsWith(r));

    if (isProtectedRoute && !accessToken) {
        return NextResponse.redirect(new URL('/login', request.url));
    }
}
```

Note: The Next.js middleware only checks cookie presence (fast, no JWT validation). The actual JWT validation happens server-side when the API is called. This is defense-in-depth, not security-through-obscurity.

**Tasks:**
1. Create login page with Google and Microsoft buttons
2. Create `AuthContext` provider and `useAuth()` hook
3. Create `AuthGuard` component for protected pages
4. Create `UserMenu` component (avatar, name, logout)
5. Add Next.js middleware for route protection
6. Update header/layout to show user menu when authenticated
7. Handle 401 responses globally (redirect to login, preserve intended destination)
8. Write Playwright E2E tests for login flow (mocked OAuth)

**Gate**: Full E2E flow — visit protected page → redirected to login → click Google → OAuth flow → redirected back to original page → user menu shows name/avatar → logout → redirected to home.

### A1.6 — Environment & Configuration

**New environment variables:**

```bash
# Auth configuration
AUTH_JWT_SECRET=           # 256-bit random hex string (required)
AUTH_ACCESS_TOKEN_TTL=900  # 15 minutes in seconds (default)
AUTH_REFRESH_TOKEN_TTL=604800  # 7 days in seconds (default)

# Google OAuth
GOOGLE_CLIENT_ID=          # From Google Cloud Console
GOOGLE_CLIENT_SECRET=      # From Google Cloud Console
GOOGLE_REDIRECT_URI=http://localhost:3000/api/auth/google/callback

# Microsoft OAuth
MICROSOFT_CLIENT_ID=       # From Azure Portal → App Registrations
MICROSOFT_CLIENT_SECRET=   # From Azure Portal → App Registrations
MICROSOFT_REDIRECT_URI=http://localhost:3000/api/auth/microsoft/callback
```

**Tasks:**
1. Update `.env.example` with all new variables
2. Add validation in `deps.py` — fail fast at startup if auth env vars are missing
3. Document OAuth app registration steps for Google and Microsoft in this file (Appendix)

**Gate**: Application starts with all env vars set. Application fails fast with clear error message if `AUTH_JWT_SECRET` is missing.

---

## Phase A2: Data Ownership & Tenant Isolation

**Goal**: Every case, file, and note belongs to a user. No user can access another user's data. Rate limiting transitions from IP-based to user-based for authenticated endpoints.

**Prerequisites**: Phase A1 complete.

### A2.1 — Schema Migration: Add user_id to Cases

**Files to modify:**
- `src/employee_help/storage/storage.py` — Add migration for `user_id` and `organization_id` columns on `cases`
- `src/employee_help/storage/case_storage.py` — Add `user_id` parameter to all CRUD methods

**Migration strategy:**
- New columns added as nullable (existing rows have no user yet)
- After auth is enforced on case endpoints, all new cases will have `user_id` set
- Existing anonymous cases can be claimed via a one-time migration endpoint or simply abandoned (they're development data)

**Tasks:**
1. Add `ALTER TABLE` migration for `cases` table (user_id, organization_id)
2. Update `CaseStorage.create()` to require `user_id` and `organization_id`
3. Update `CaseStorage.list()` to filter by `user_id` (or `organization_id` for team access)
4. Update `CaseStorage.get()` to verify ownership
5. Write tests: user A cannot read user B's case

**Gate**: `CaseStorage.list(user_id="A")` returns only A's cases. `CaseStorage.get(case_id, user_id="B")` returns None for A's case.

### A2.2 — Ownership Enforcement on API Routes

**Files to modify:**
- `src/employee_help/api/casefile_routes.py` — Inject `request.state.user` into all case operations
- `src/employee_help/api/discovery_routes.py` — Associate discovery sessions with user
- `src/employee_help/api/objection_routes.py` — Associate objection drafts with user

**Pattern for ownership enforcement:**

```python
@router.get("/api/cases")
async def list_cases(request: Request):
    user = request.state.user  # Set by auth middleware
    cases = case_storage.list(user_id=user.id)
    return cases

@router.get("/api/cases/{case_id}")
async def get_case(case_id: str, request: Request):
    user = request.state.user
    case = case_storage.get(case_id)
    if not case or case.user_id != user.id:
        raise HTTPException(status_code=404)  # 404, not 403 — don't leak existence
    return case
```

**Critical security decision**: Return 404 (not 403) when a user tries to access another user's resource. A 403 reveals that the resource exists; a 404 reveals nothing. This prevents enumeration attacks.

**Tasks:**
1. Update all case CRUD routes to enforce ownership
2. Update file upload/download routes to verify case ownership
3. Update notes routes to verify case ownership
4. Update discovery routes to associate sessions with user
5. Update objection routes to associate sessions with user
6. Write E2E tests: User A creates case, User B gets 404 trying to access it

**Gate**: Full cross-user isolation test passes. No API endpoint leaks data across users.

### A2.3 — File Download Security

**Files to modify:**
- `src/employee_help/api/casefile_routes.py` — File download endpoint

**Current state**: Files stored at `data/cases/{case_id}/files/{file_id}_{filename}`. If served as static files (via a web server), anyone with the path can access them.

**Fix**: Files MUST be served through the authenticated API endpoint, never as static files. The download endpoint reads the file from disk and streams it through the authenticated response.

```python
@router.get("/api/cases/{case_id}/files/{file_id}/download")
async def download_file(case_id: str, file_id: str, request: Request):
    user = request.state.user
    case = case_storage.get(case_id)
    if not case or case.user_id != user.id:
        raise HTTPException(status_code=404)

    file = case_storage.get_file(file_id)
    if not file or file.case_id != case_id:
        raise HTTPException(status_code=404)

    # Stream file from disk — never expose storage_path to client
    return FileResponse(
        path=file.storage_path,
        filename=file.original_filename,
        media_type=file.mime_type,
    )
```

**Deployment note**: In production, ensure the `data/cases/` directory is NOT served by nginx/Caddy/etc. as a static directory. Only the FastAPI application should read from it.

**Tasks:**
1. Verify download endpoint enforces ownership
2. Add nginx/Caddy configuration documentation to block direct file access
3. Write test: unauthenticated request to file download returns 401

**Gate**: Direct HTTP request to file path returns 401/404. Authenticated request through API returns file.

### A2.4 — Rate Limiting Upgrade

**Files to modify:**
- `src/employee_help/api/main.py` — Dual-mode rate limiting

**Current state**: All rate limiting is IP-based. This is problematic because:
- Multiple users behind a corporate NAT share an IP (unfair throttling)
- A single user can evade limits by changing IP

**New approach**: Hybrid rate limiting.
- **Authenticated requests**: Rate limit by `user_id` (from JWT). Higher limits.
- **Unauthenticated requests**: Rate limit by `client_ip` (current behavior). Lower limits.

```python
def _get_rate_limit_key(request: Request) -> str:
    """User ID for authenticated requests, IP for anonymous."""
    user = getattr(request.state, 'user', None)
    if user:
        return f"user:{user.id}"
    return f"ip:{_get_client_ip(request)}"
```

**Authenticated user limits** (higher — they're paying customers):
- `/api/ask`: 20/min (up from 5)
- LLM endpoints: 15/min (up from 5)
- Discovery/upload: 50/min (up from 20)

**Tasks:**
1. Refactor rate limiting to use `_get_rate_limit_key()`
2. Define authenticated vs. unauthenticated limit tiers
3. Update daily budget to be per-user for authenticated users (no shared global budget)
4. Write tests for dual-mode rate limiting

**Gate**: Authenticated user gets higher limits. Two authenticated users behind same IP have independent limits.

---

## Phase A3: Security Hardening & Audit

**Goal**: Production-grade security posture. Audit logging. Session management UI. CSP headers. Prepare for SOC 2 readiness.

**Prerequisites**: Phase A2 complete.

### A3.1 — Audit Logging

**Files to create:**
- `src/employee_help/auth/audit.py` — `AuditLogger` class

**Events to log:**

| Action | Trigger |
|--------|---------|
| `auth.login` | Successful OAuth callback |
| `auth.login_failed` | Failed OAuth callback (invalid state, provider error) |
| `auth.logout` | User logout |
| `auth.session_refresh` | Access token refreshed |
| `auth.session_revoked` | Session manually revoked |
| `case.create` | New case created |
| `case.delete` | Case deleted |
| `case.archive` | Case archived |
| `file.upload` | File uploaded |
| `file.download` | File downloaded |
| `file.delete` | File deleted |
| `file.reprocess` | File reprocessed |
| `note.create` | Note created |
| `note.update` | Note updated |
| `note.delete` | Note deleted |
| `discovery.generate` | Discovery document generated |
| `objection.generate` | Objection analysis generated |

**Implementation**: Append-only writes to `audit_log` table. No updates, no deletes. AuditLogger is injected as a dependency into route handlers, not called from middleware (middleware doesn't know the business action).

**Tasks:**
1. Implement `AuditLogger` with `log()` method
2. Add audit logging calls to all case/file/note routes
3. Add audit logging to auth routes (login, logout, refresh)
4. Add `/api/auth/audit-log` endpoint (user can view their own audit log)
5. Write tests for audit log integrity

**Gate**: Every case/file operation creates an audit log entry. Audit log entries cannot be modified or deleted through the API.

### A3.2 — Session Management UI

**Files to create/modify:**
- `frontend/app/account/page.tsx` — Account page with active sessions
- `frontend/components/active-sessions.tsx` — List sessions with revoke button

**Features:**
- List all active sessions: device/browser (from user_agent), IP address, last used, created at
- Highlight current session
- "Revoke" button on each non-current session
- "Revoke all other sessions" button

This gives attorneys visible control over their access — a concrete security feature they can point to.

**Tasks:**
1. Implement `GET /api/auth/sessions` endpoint
2. Implement `DELETE /api/auth/sessions/{id}` endpoint
3. Build account page with sessions list
4. Write E2E tests for session revocation

**Gate**: User can see active sessions. Revoking a session invalidates that session's refresh token.

### A3.3 — Security Headers

**Files to modify:**
- `src/employee_help/api/main.py` — Add security headers middleware

**Headers to add:**

```python
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    # CSP configured in Next.js for frontend; backend API responses don't need it
    return response
```

**Tasks:**
1. Add security headers middleware
2. Configure CSP in Next.js `next.config.ts` (restrict script sources, block inline scripts)
3. HSTS header: set in reverse proxy (nginx/Caddy), not in application

**Gate**: Response headers present on all API responses. CSP blocks inline script execution.

### A3.4 — PII Handling in Logs

**Files to modify:**
- Logging configuration throughout the application

**Rules:**
- Never log email addresses, display names, or file names in application logs (structlog output)
- Log `user_id` (UUID) — it's not PII, it's an opaque identifier
- The audit log (database) stores user_id + action — the user's profile info is joined at query time, never duplicated into logs
- Redact IP addresses in application logs (keep in audit log for security, but not in general logs)

**Tasks:**
1. Review all `logger.info()` / `logger.warning()` / `logger.error()` calls for PII
2. Add structlog processor to redact known PII patterns (emails)
3. Document PII handling policy

**Gate**: Grep through application logs — no emails, no names, no file names present.

---

## Phase A4: Organization & Team Support

**Goal**: Users can create organizations, invite team members, and share cases within an organization. This enables the "sell into the company" motion.

**Prerequisites**: Phase A3 complete. Product has organic user clusters (multiple users from same email domain).

### A4.1 — Organization Management

**Files to create:**
- `src/employee_help/api/org_routes.py` — Organization CRUD
- `frontend/app/account/organization/page.tsx` — Org settings page

**Endpoints:**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/orgs` | List user's organizations |
| POST | `/api/orgs` | Create new organization |
| PATCH | `/api/orgs/{id}` | Update org name/settings |
| GET | `/api/orgs/{id}/members` | List members |
| POST | `/api/orgs/{id}/invites` | Invite member by email |
| DELETE | `/api/orgs/{id}/members/{user_id}` | Remove member |
| PATCH | `/api/orgs/{id}/members/{user_id}` | Change member role |

**Invite flow:**
1. Admin enters colleague's email
2. System sends invite (email via SendGrid/Postmark — first email dependency)
3. Invitee signs in with Google/Microsoft (using that email)
4. On login, system checks for pending invites matching the email
5. User is added to the organization

**No invite link tokens** — the invite is validated by the email address match on OAuth login. This eliminates link-sharing vulnerabilities.

**Tasks:**
1. Create org CRUD endpoints
2. Create invite system (pending_invites table)
3. Update login flow to check for pending invites
4. Build org settings UI (member list, invite form, role management)
5. Write tests for invite flow, role enforcement

**Gate**: User A invites user B by email. User B logs in via Google. User B is auto-added to A's org. Both can see shared cases.

### A4.2 — Shared Case Access

**Files to modify:**
- `src/employee_help/storage/case_storage.py` — Add organization-scoped queries

**Access model:**
- Case has `user_id` (creator) AND `organization_id` (team)
- Creator can always access their case
- Members of the same org can access cases created within that org
- Role-based: `owner`/`admin` can manage org settings; `member` can access shared cases

**Query change:**
```sql
-- Before: only user's own cases
SELECT * FROM cases WHERE user_id = ?

-- After: user's own cases + org cases
SELECT * FROM cases
WHERE user_id = ?
   OR organization_id IN (
       SELECT organization_id FROM memberships WHERE user_id = ?
   )
```

**Tasks:**
1. Update case listing to include org-shared cases
2. Add case-level sharing controls (private to user vs. shared with org)
3. Update file access checks for org membership
4. Write tests: org member can access shared case, non-member cannot

**Gate**: Two users in the same org can both access a shared case. A user in a different org cannot.

### A4.3 — Domain-Based Clustering (Analytics Only)

**Purpose**: Detect organic clusters for sales outreach. Not user-facing.

**Implementation:**
- Extract email domain from user profile on login
- Store in `users` table (new column: `email_domain`)
- Admin/internal query: `SELECT email_domain, COUNT(*) FROM users GROUP BY email_domain HAVING COUNT(*) > 1`
- This identifies firms where multiple attorneys are already using the product individually

**No auto-join by domain** in this phase — that's a Phase A5 enterprise feature. Here we're just collecting the signal for sales.

**Tasks:**
1. Add `email_domain` column to users table
2. Extract domain on user creation/update
3. Create internal analytics query (CLI or admin endpoint)

**Gate**: After 5 users from @smithlaw.com sign up individually, admin query shows "smithlaw.com: 5 users."

---

## Phase A5: Enterprise SSO & SCIM

**Goal**: Enterprise law firms can configure SAML SSO and SCIM provisioning. Individual accounts transition seamlessly to enterprise-managed accounts.

**Prerequisites**: Phase A4 complete. At least one enterprise deal in pipeline that requires SSO.

**Provider decision**: Introduce WorkOS at this phase. The `AuthProvider` interface designed in A1.1 enables this without touching business logic.

### A5.1 — WorkOS Integration

**Files to create/modify:**
- `src/employee_help/auth/workos.py` — `WorkOSProvider` implementing `AuthProvider`
- `src/employee_help/auth/provider.py` — Provider routing logic

**Architecture:**
- WorkOS handles SAML/OIDC negotiation with the firm's IdP (Entra ID, Okta, Google Workspace)
- Our `WorkOSProvider` replaces `GoogleOIDCProvider`/`MicrosoftOIDCProvider` for enterprise users
- Non-enterprise users continue using direct OAuth providers
- Provider routing: check user's email domain → if domain has SSO configured → route through WorkOS → otherwise → direct OAuth

**Dependencies to add:**
- `workos>=5.0` — WorkOS Python SDK

**Tasks:**
1. Implement `WorkOSProvider`
2. Add provider routing logic (domain → SSO config lookup)
3. Configure WorkOS dashboard with SSO connections
4. Test with Entra ID test tenant
5. Test with Google Workspace test org

**Gate**: Enterprise user from SSO-configured domain logs in via SAML through WorkOS. Non-enterprise user continues using direct Google/Microsoft OAuth.

### A5.2 — Domain Claiming & Account Linking

**Implementation:**
1. Enterprise IT admin claims their domain (e.g., `kirkland.com`) via WorkOS Admin Portal
2. System identifies existing users with `@kirkland.com` emails
3. Existing users' next login is routed through SSO instead of direct OAuth
4. User's data (cases, files, notes) is preserved — only the auth method changes
5. User is added to the enterprise organization, removed from their individual org

**This is the critical PLG → Enterprise bridge.** Individual attorney's work product survives the transition. No data loss, no re-upload, no disruption.

**Tasks:**
1. Implement domain claim flow via WorkOS Admin Portal
2. Build account linking logic (existing user → enterprise org)
3. Handle data migration: cases move from individual org to enterprise org
4. Test: user with 10 cases transitions to enterprise SSO, all cases preserved
5. Handle edge case: user belongs to multiple orgs, only one claims the domain

**Gate**: User with 5 existing cases and 20 uploaded files transitions from Google OAuth to firm SSO. Zero data loss. Can access all existing work product immediately after SSO login.

### A5.3 — SCIM Directory Sync

**Implementation via WorkOS Directory Sync:**
- Firm's Entra ID / Okta pushes user create/update/delete events to WorkOS
- WorkOS forwards events to our webhook endpoint
- Our system auto-creates/deactivates user accounts based on directory events

**Deprovisioning is critical for legal**: When an attorney leaves the firm, their access must be revoked immediately (ABA Model Rule 1.6(c) confidentiality). SCIM deprovisioning handles this automatically — when IT removes the user from their directory, our system deactivates the account within minutes.

**Tasks:**
1. Implement WorkOS Directory Sync webhook endpoint
2. Handle user.created → auto-provision account + add to org
3. Handle user.updated → sync profile changes
4. Handle user.deleted → deactivate account, revoke all sessions
5. Handle group sync → map to roles (optional)
6. Write tests for all SCIM lifecycle events

**Gate**: User added in Entra ID → auto-provisioned in Employee Help within 40 minutes. User removed from Entra ID → account deactivated, all sessions revoked, cannot access any data.

### A5.4 — Admin Portal

**Implementation via WorkOS Admin Portal:**
- Embeddable portal where firm IT admins configure SSO and SCIM without our help
- Reduces our support burden to near-zero for enterprise onboarding
- IT admin configures: SSO provider (Entra ID, Okta, Google Workspace), SCIM connection, MFA policy

This is not something we build — WorkOS provides it. We embed it.

**Tasks:**
1. Generate Admin Portal link via WorkOS API
2. Add "SSO Settings" section to org settings page (visible to org admins)
3. Embed Admin Portal in iframe or redirect
4. Document enterprise onboarding flow

**Gate**: Firm IT admin can self-configure SSO via Admin Portal without any support tickets.

---

## Migration Plan for Existing Features

### Features Requiring Auth Integration

| Feature | Current Auth | Target Auth | Migration Effort |
|---------|-------------|-------------|-----------------|
| RAG Q&A (consumer) | None (public) | None (stays public) | None |
| RAG Q&A (attorney) | None | Required | Add auth check in route |
| Calculators | None (public) | None (stays public) | None |
| Intake questionnaire | None (public) | None (stays public) | None |
| Discovery tools | None | Required | Add auth + user_id to sessions |
| Objection drafter | None | Required | Add auth + user_id to sessions |
| LITIGAGENT | None | Required | Add user_id to cases, auth to all routes |
| Feedback | None (public) | Optional (enhance with user_id) | Add optional user_id |
| Dashboard | None | Required (admin only) | Add auth + admin check |

### Conversation Sessions

Current `conversation_session` and `discovery_sessions` tables have no `user_id`. Options:

1. **Add `user_id` column (nullable)** — anonymous sessions continue to work, authenticated sessions are linked to users
2. This enables: "Your recent conversations" for logged-in users
3. No migration of existing sessions needed — they remain anonymous

### Data Directory Structure

Current: `data/cases/{case_id}/files/{file_id}_{filename}`

No change needed. The `case_id` is the access boundary, and ownership is enforced at the database level. The file path is opaque — no user information is encoded in it, which is correct (if we ever need to transfer case ownership between users, the files don't need to move on disk).

---

## Cost Analysis

### Phase A1-A3: Zero Incremental Cost

| Item | Cost | Notes |
|------|------|-------|
| Google OAuth app registration | Free | Google Cloud Console |
| Microsoft app registration | Free | Azure Portal |
| PyJWT dependency | Free | MIT license, pure Python |
| Auth infrastructure | Free | OAuth + JWT + SQLite |
| Email sending (for invites, Phase A4) | ~$0.001/email | SendGrid free tier: 100 emails/day |

**Total Phase A1-A3 cost: $0/month**

We are leveraging billions of dollars of Google and Microsoft security infrastructure for free. This is the entire point.

### Phase A5: Enterprise Auth Provider

| Item | Cost | Notes |
|------|------|-------|
| WorkOS user management | Free | Up to 1M MAUs |
| WorkOS SSO connection | $125/month/connection | Per enterprise org |
| WorkOS SCIM connection | $125/month/connection | Per enterprise org |
| Volume discount | ~$50/connection at 100+ | Scale pricing |

**Per enterprise customer cost**: $250/month (SSO + SCIM). This is easily absorbed by enterprise contract pricing ($2,000-$10,000/month per firm). The cost-to-revenue ratio is < 5%.

### SOC 2 Type II (Future)

| Item | Cost | Notes |
|------|------|-------|
| SOC 2 Type II audit (Year 1) | $20K-50K | Dependent on scope |
| Compliance platform (Vanta/Drata) | $10K-25K/year | Automates evidence collection |
| ISO 27001 (optional) | $15K-30K | If targeting international firms |

These costs are justified by enterprise deal sizes and will be pursued when the first enterprise deal is in active procurement. Not before.

---

## Appendix: Provider Comparison & Research Notes

### Identity Provider Coverage in Legal

| IdP | Market Share (AmLaw 200) | Protocol | Account Types |
|-----|-------------------------|----------|---------------|
| Microsoft Entra ID | ~90% | OIDC + SAML 2.0 | Organizational (M365) + Personal (@outlook.com) |
| Google Workspace | ~10-15% | OIDC + SAML 2.0 | Workspace (verified domain) + Consumer (@gmail.com) |

### Key Implementation Details from Research

**Microsoft Entra ID:**
- Use `oid` + `tid` claims for stable user identification (NOT `sub`, which is pair-wise per app)
- `/common` endpoint accepts both personal and organizational accounts
- 200-group limit in JWT tokens (triggers overage claim → Graph API fallback)
- SCIM provisioning requires Entra ID Premium P1 ($6/user/month), included in M365 E3/E5
- Gallery app submissions suspended (March 2025) — use non-gallery configuration initially

**Google Workspace:**
- `hd` (hosted domain) claim present for Workspace accounts, absent for consumer Gmail
- Always validate `hd` server-side to distinguish organizational from personal users
- SCIM sync every few hours (slower than Entra ID's ~40 minutes)
- No native SCIM UI for custom endpoints — use Admin SDK or WorkOS

### Auth Provider Decision Matrix

| Criteria | Direct OAuth | WorkOS | Stytch |
|----------|:--:|:--:|:--:|
| Phase A1-A3 (individual users) | Best | Acceptable | Acceptable |
| Phase A5 (enterprise SSO) | Cannot | Best | Good |
| Dependencies | 1 (PyJWT) | 1 (workos SDK) | 1 (stytch SDK) |
| Outage blast radius | Provider-only | Provider + WorkOS | Provider + Stytch |
| Cost (0-1000 users) | $0 | $0 | $0 |
| Cost (enterprise) | N/A | $250/connection/mo | $250/connection/mo |
| SCIM maturity | N/A | Battle-tested | Newer |
| Admin Portal | N/A | Self-serve | Embeddable |
| Used by | Direct | OpenAI, Cursor, Vercel | Newer startups |

**Decision**: Direct OAuth for Phase A1-A3 (zero cost, zero dependency, zero outage risk). WorkOS for Phase A5 (enterprise-grade SSO/SCIM, proven at scale, self-serve Admin Portal).

### Competitor Authentication Stack (from research)

| Company | SAML 2.0 | OIDC | SCIM | Certifications |
|---------|:--:|:--:|:--:|----------------|
| Harvey AI | Yes | Not documented | Not documented | SOC 2 II, ISO 27001 |
| Clio | Yes | Yes | Yes (Operate tier) | SOC 2 II, ISO 27001, HIPAA |
| Relativity | Yes | Yes | Not documented | SOC 2 II, ISO 27001, FedRAMP |
| Westlaw | Yes | Via integrations | Partial (Okta) | SOC 2, ISO 27001 |
| Legora | Yes | Likely | Not documented | ISO 27001, ISO 42001, SOC 2 |
| **Employee Help (target)** | **Phase A5** | **Phase A1** | **Phase A5** | **SOC 2 II (12-18 months)** |

### OAuth App Registration Steps

**Google Cloud Console:**
1. Go to console.cloud.google.com → APIs & Services → Credentials
2. Create OAuth 2.0 Client ID (Web application)
3. Add authorized redirect URI: `https://yourdomain.com/api/auth/google/callback`
4. Copy Client ID and Client Secret to `.env`
5. Configure OAuth consent screen (External, production → requires Google review)

**Azure Portal (Microsoft):**
1. Go to portal.azure.com → Microsoft Entra ID → App Registrations → New Registration
2. Supported account types: "Accounts in any organizational directory and personal Microsoft accounts"
3. Redirect URI: `https://yourdomain.com/api/auth/microsoft/callback` (Web)
4. Certificates & Secrets → New Client Secret → Copy value to `.env`
5. API Permissions: `openid`, `email`, `profile` (default, no admin consent needed)
6. Copy Application (client) ID to `.env`

---

## Phase Summary & Dependencies

```
Phase A1: Authentication Foundation
├── A1.1  Auth Provider Interface + OIDC Implementations
├── A1.2  Session Management
├── A1.3  Auth API Routes
├── A1.4  Auth Middleware
├── A1.5  Frontend Auth Flow
└── A1.6  Environment & Configuration

Phase A2: Data Ownership & Tenant Isolation (requires A1)
├── A2.1  Schema Migration (user_id on cases)
├── A2.2  Ownership Enforcement on API Routes
├── A2.3  File Download Security
└── A2.4  Rate Limiting Upgrade

Phase A3: Security Hardening & Audit (requires A2)
├── A3.1  Audit Logging
├── A3.2  Session Management UI
├── A3.3  Security Headers
└── A3.4  PII Handling in Logs

Phase A4: Organization & Team Support (requires A3)
├── A4.1  Organization Management (invites, roles)
├── A4.2  Shared Case Access
└── A4.3  Domain-Based Clustering (analytics)

Phase A5: Enterprise SSO & SCIM (requires A4 + enterprise deal)
├── A5.1  WorkOS Integration
├── A5.2  Domain Claiming & Account Linking
├── A5.3  SCIM Directory Sync
└── A5.4  Admin Portal
```

### Non-Negotiable Principles

1. **No local credentials. Ever.** Google and Microsoft OAuth only. No email/password. No magic links. No SMS OTP. If we don't store it, it can't be breached.

2. **Ownership enforcement is not optional.** Every query that touches user data MUST include a user/org ownership check. No exceptions. This is the Dependency Rule applied to data access — the authorization check is part of the domain logic, not an afterthought bolted on at the API layer.

3. **Organization_id from day one.** Even if invisible to users in Phase A1-A3, the data model is multi-tenant from the start. Retrofitting costs 3-5x more.

4. **404, not 403.** Never reveal the existence of resources the user cannot access. Unauthorized access returns 404 as if the resource doesn't exist.

5. **Files through API, never static.** Case files are served through authenticated API endpoints. No static file serving. No direct URL access. The file path on disk is an implementation detail that never reaches the client.
