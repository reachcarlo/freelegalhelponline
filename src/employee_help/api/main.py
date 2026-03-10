"""FastAPI application entry point.

Start with:
    uv run uvicorn employee_help.api.main:app --reload --port 8000
"""

from __future__ import annotations

# Load .env BEFORE any app imports so module-level os.environ reads pick up values.
import os
from pathlib import Path

from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(_env_path)

import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import sentry_sdk
import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from employee_help.logging import redact_pii

# Configure structlog with PII redaction processor (A3.4)
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        redact_pii,
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

from employee_help.api.auth_routes import auth_router
from employee_help.api.casefile_routes import casefile_router
from employee_help.api.deps import init_services, shutdown_services
from employee_help.api.discovery_routes import discovery_router
from employee_help.api.objection_routes import objection_router
from employee_help.api.routes import router

logger = structlog.get_logger(__name__)

# --- Configuration from environment ---

# --- Sentry error tracking ---

_sentry_dsn = os.environ.get("SENTRY_DSN")
if _sentry_dsn:
    sentry_sdk.init(
        dsn=_sentry_dsn,
        environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        enable_tracing=True,
    )
    logger.info("sentry_initialized", environment=os.environ.get("SENTRY_ENVIRONMENT", "production"))

CORS_ORIGINS = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
).split(",")

# Anonymous (IP-based) rate limits
RATE_LIMIT_MAX = int(os.environ.get("RATE_LIMIT_MAX", "5"))
RATE_LIMIT_WINDOW = int(os.environ.get("RATE_LIMIT_WINDOW", "60"))
FEEDBACK_RATE_LIMIT_MAX = int(os.environ.get("FEEDBACK_RATE_LIMIT_MAX", "10"))
DEADLINE_RATE_LIMIT_MAX = int(os.environ.get("DEADLINE_RATE_LIMIT_MAX", "20"))
ROUTING_RATE_LIMIT_MAX = int(os.environ.get("ROUTING_RATE_LIMIT_MAX", "20"))
WAGES_RATE_LIMIT_MAX = int(os.environ.get("WAGES_RATE_LIMIT_MAX", "20"))
INCIDENT_GUIDE_RATE_LIMIT_MAX = int(os.environ.get("INCIDENT_GUIDE_RATE_LIMIT_MAX", "20"))
INTAKE_RATE_LIMIT_MAX = int(os.environ.get("INTAKE_RATE_LIMIT_MAX", "20"))
INTAKE_SUMMARY_RATE_LIMIT_MAX = int(os.environ.get("INTAKE_SUMMARY_RATE_LIMIT_MAX", "5"))
DISCOVERY_RATE_LIMIT_MAX = int(os.environ.get("DISCOVERY_RATE_LIMIT_MAX", "20"))
OBJECTION_PARSE_RATE_LIMIT_MAX = int(os.environ.get("OBJECTION_PARSE_RATE_LIMIT_MAX", "10"))
OBJECTION_GENERATE_RATE_LIMIT_MAX = int(os.environ.get("OBJECTION_GENERATE_RATE_LIMIT_MAX", "5"))
CASEFILE_UPLOAD_RATE_LIMIT_MAX = int(os.environ.get("CASEFILE_UPLOAD_RATE_LIMIT_MAX", "20"))
CASEFILE_CHAT_RATE_LIMIT_MAX = int(os.environ.get("CASEFILE_CHAT_RATE_LIMIT_MAX", "10"))
DAILY_QUERY_BUDGET = int(os.environ.get("DAILY_QUERY_BUDGET", "500"))

# Authenticated (user-based) rate limits — higher tiers
AUTH_RATE_LIMIT_MAX = int(os.environ.get("AUTH_RATE_LIMIT_MAX", "20"))
AUTH_INTAKE_SUMMARY_RATE_LIMIT_MAX = int(os.environ.get("AUTH_INTAKE_SUMMARY_RATE_LIMIT_MAX", "15"))
AUTH_OBJECTION_GENERATE_RATE_LIMIT_MAX = int(os.environ.get("AUTH_OBJECTION_GENERATE_RATE_LIMIT_MAX", "15"))
AUTH_OBJECTION_PARSE_RATE_LIMIT_MAX = int(os.environ.get("AUTH_OBJECTION_PARSE_RATE_LIMIT_MAX", "30"))
AUTH_DISCOVERY_RATE_LIMIT_MAX = int(os.environ.get("AUTH_DISCOVERY_RATE_LIMIT_MAX", "50"))
AUTH_CASEFILE_UPLOAD_RATE_LIMIT_MAX = int(os.environ.get("AUTH_CASEFILE_UPLOAD_RATE_LIMIT_MAX", "50"))
AUTH_CASEFILE_CHAT_RATE_LIMIT_MAX = int(os.environ.get("AUTH_CASEFILE_CHAT_RATE_LIMIT_MAX", "20"))
AUTH_DAILY_QUERY_BUDGET = int(os.environ.get("AUTH_DAILY_QUERY_BUDGET", "2000"))

# --- In-memory rate limit state ---

_rate_limit_store: dict[str, list[float]] = defaultdict(list)
_feedback_rate_store: dict[str, list[float]] = defaultdict(list)
_deadline_rate_store: dict[str, list[float]] = defaultdict(list)
_routing_rate_store: dict[str, list[float]] = defaultdict(list)
_wages_rate_store: dict[str, list[float]] = defaultdict(list)
_incident_guide_rate_store: dict[str, list[float]] = defaultdict(list)
_intake_rate_store: dict[str, list[float]] = defaultdict(list)
_intake_summary_rate_store: dict[str, list[float]] = defaultdict(list)
_discovery_rate_store: dict[str, list[float]] = defaultdict(list)
_objection_parse_rate_store: dict[str, list[float]] = defaultdict(list)
_objection_generate_rate_store: dict[str, list[float]] = defaultdict(list)
_casefile_upload_rate_store: dict[str, list[float]] = defaultdict(list)
_casefile_chat_rate_store: dict[str, list[float]] = defaultdict(list)
_daily_budget_store: dict[str, dict] = defaultdict(
    lambda: {"date": "", "count": 0}
)


def _get_client_ip(request: Request) -> str:
    """Extract real client IP from X-Forwarded-For or fall back to direct IP."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # X-Forwarded-For: client, proxy1, proxy2 — first is the real client
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _prune_stale_entries(store: dict[str, list[float]], window: int) -> None:
    """Remove IPs with no recent activity (older than 2x window)."""
    cutoff = time.time() - (window * 2)
    stale_keys = [ip for ip, ts in store.items() if not ts or ts[-1] < cutoff]
    for key in stale_keys:
        del store[key]


def _check_daily_budget(budget_key: str, limit: int) -> tuple[bool, int]:
    """Check if daily query budget is exceeded. Returns (allowed, remaining)."""
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    bucket = _daily_budget_store[budget_key]
    if bucket["date"] != today:
        bucket["date"] = today
        bucket["count"] = 0
    remaining = limit - int(bucket["count"])
    return remaining > 0, max(remaining, 0)


def _increment_daily_budget(budget_key: str) -> None:
    """Increment today's query count for the given budget key."""
    _daily_budget_store[budget_key]["count"] = (
        int(_daily_budget_store[budget_key]["count"]) + 1
    )


def _check_rate_limit(
    store: dict[str, list[float]],
    key: str,
    limit: int,
    window: int,
    now: float,
) -> tuple[bool, int, float]:
    """Check and record a rate limit hit.

    Returns (allowed, remaining, reset_at).
    """
    store[key] = [t for t in store[key] if now - t < window]
    count = len(store[key])
    reset_at = now + window

    if count >= limit:
        return False, 0, store[key][0] + window

    store[key].append(now)
    if len(store) > 100:
        _prune_stale_entries(store, window)

    return True, limit - count - 1, reset_at


def _rate_limit_headers(
    limit: int, remaining: int, reset_at: float
) -> dict[str, str]:
    """Build rate limit response headers."""
    return {
        "X-RateLimit-Limit": str(limit),
        "X-RateLimit-Remaining": str(max(remaining, 0)),
        "X-RateLimit-Reset": str(int(reset_at)),
    }


def _rate_limit_response(message: str, limit: int, reset_at: float) -> Response:
    """Build a 429 rate limit response."""
    return Response(
        content=f'{{"detail":"Rate limit exceeded. {message}"}}',
        status_code=429,
        media_type="application/json",
        headers=_rate_limit_headers(limit, 0, reset_at),
    )


def _budget_exceeded_response() -> Response:
    """Build a 429 daily budget exceeded response."""
    return Response(
        content='{"detail":"Daily query budget exceeded. Please try again tomorrow."}',
        status_code=429,
        media_type="application/json",
        headers={"Retry-After": "3600"},
    )


# ── Auth middleware configuration ─────────────────────────────

# Paths requiring authentication — all others are public.
_PROTECTED_PATH_PREFIXES = (
    "/api/cases",       # LITIGAGENT — private case files
    "/api/discovery",   # Discovery tools — private case data
    "/api/objections",  # Objection drafter — private case data
)


def _requires_auth(path: str) -> bool:
    """Check if a request path requires authentication."""
    return any(path.startswith(prefix) for prefix in _PROTECTED_PATH_PREFIXES)


def _get_rate_limit_key(request: Request) -> str:
    """Rate limit key: user_id for authenticated users, client IP for anonymous."""
    user = getattr(request.state, "user", None)
    if user is not None:
        return f"user:{user.sub}"
    return _get_client_ip(request)


def _is_authenticated(request: Request) -> bool:
    """Check if the request has a valid authenticated user."""
    return getattr(request.state, "user", None) is not None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load services at startup, clean up at shutdown."""
    logger.info("server_starting")
    init_services()
    logger.info("server_ready")
    yield
    shutdown_services()
    logger.info("server_stopped")


app = FastAPI(
    title="Employee Help API",
    description="AI-powered California employment rights guidance",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — configurable via CORS_ORIGINS env var
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Dual-mode rate limiting: authenticated users get higher limits."""
    now = time.time()
    key = _get_rate_limit_key(request)
    is_auth = _is_authenticated(request)

    # --- /api/ask rate limiting (LLM endpoint) ---
    if request.url.path == "/api/ask" and request.method == "POST":
        budget_key = key if is_auth else "global"
        daily_limit = AUTH_DAILY_QUERY_BUDGET if is_auth else DAILY_QUERY_BUDGET
        budget_ok, _ = _check_daily_budget(budget_key, daily_limit)
        if not budget_ok:
            return _budget_exceeded_response()

        limit = AUTH_RATE_LIMIT_MAX if is_auth else RATE_LIMIT_MAX
        allowed, remaining, reset_at = _check_rate_limit(
            _rate_limit_store, key, limit, RATE_LIMIT_WINDOW, now
        )
        if not allowed:
            return _rate_limit_response(
                "Please wait before asking another question.", limit, reset_at
            )

        _increment_daily_budget(budget_key)

        response = await call_next(request)
        for k, v in _rate_limit_headers(limit, remaining, reset_at).items():
            response.headers[k] = v
        return response

    # --- /api/deadlines rate limiting (public calculator) ---
    if request.url.path == "/api/deadlines" and request.method == "POST":
        allowed, _, reset_at = _check_rate_limit(
            _deadline_rate_store, key, DEADLINE_RATE_LIMIT_MAX, 60, now
        )
        if not allowed:
            return _rate_limit_response(
                "Please wait before making another calculation.",
                DEADLINE_RATE_LIMIT_MAX,
                reset_at,
            )

    # --- /api/agency-routing rate limiting (public calculator) ---
    if request.url.path == "/api/agency-routing" and request.method == "POST":
        allowed, _, reset_at = _check_rate_limit(
            _routing_rate_store, key, ROUTING_RATE_LIMIT_MAX, 60, now
        )
        if not allowed:
            return _rate_limit_response(
                "Please wait before making another request.",
                ROUTING_RATE_LIMIT_MAX,
                reset_at,
            )

    # --- /api/unpaid-wages rate limiting (public calculator) ---
    if request.url.path == "/api/unpaid-wages" and request.method == "POST":
        allowed, _, reset_at = _check_rate_limit(
            _wages_rate_store, key, WAGES_RATE_LIMIT_MAX, 60, now
        )
        if not allowed:
            return _rate_limit_response(
                "Please wait before making another calculation.",
                WAGES_RATE_LIMIT_MAX,
                reset_at,
            )

    # --- /api/incident-guide rate limiting (public calculator) ---
    if request.url.path == "/api/incident-guide" and request.method == "POST":
        allowed, _, reset_at = _check_rate_limit(
            _incident_guide_rate_store, key, INCIDENT_GUIDE_RATE_LIMIT_MAX, 60, now
        )
        if not allowed:
            return _rate_limit_response(
                "Please wait before making another request.",
                INCIDENT_GUIDE_RATE_LIMIT_MAX,
                reset_at,
            )

    # --- /api/intake rate limiting (public) ---
    if request.url.path == "/api/intake" and request.method == "POST":
        allowed, _, reset_at = _check_rate_limit(
            _intake_rate_store, key, INTAKE_RATE_LIMIT_MAX, 60, now
        )
        if not allowed:
            return _rate_limit_response(
                "Please wait before submitting another questionnaire.",
                INTAKE_RATE_LIMIT_MAX,
                reset_at,
            )

    # --- /api/intake-summary rate limiting (LLM endpoint) ---
    if request.url.path == "/api/intake-summary" and request.method == "POST":
        budget_key = key if is_auth else "global"
        daily_limit = AUTH_DAILY_QUERY_BUDGET if is_auth else DAILY_QUERY_BUDGET
        budget_ok, _ = _check_daily_budget(budget_key, daily_limit)
        if not budget_ok:
            return _budget_exceeded_response()

        limit = AUTH_INTAKE_SUMMARY_RATE_LIMIT_MAX if is_auth else INTAKE_SUMMARY_RATE_LIMIT_MAX
        allowed, remaining, reset_at = _check_rate_limit(
            _intake_summary_rate_store, key, limit, RATE_LIMIT_WINDOW, now
        )
        if not allowed:
            return _rate_limit_response(
                "Please wait before requesting another summary.", limit, reset_at
            )

        _increment_daily_budget(budget_key)

        response = await call_next(request)
        for k, v in _rate_limit_headers(limit, remaining, reset_at).items():
            response.headers[k] = v
        return response

    # --- /api/objections/generate rate limiting (LLM endpoint) ---
    if request.url.path == "/api/objections/generate" and request.method == "POST":
        budget_key = key if is_auth else "global"
        daily_limit = AUTH_DAILY_QUERY_BUDGET if is_auth else DAILY_QUERY_BUDGET
        budget_ok, _ = _check_daily_budget(budget_key, daily_limit)
        if not budget_ok:
            return _budget_exceeded_response()

        limit = AUTH_OBJECTION_GENERATE_RATE_LIMIT_MAX if is_auth else OBJECTION_GENERATE_RATE_LIMIT_MAX
        allowed, remaining, reset_at = _check_rate_limit(
            _objection_generate_rate_store, key, limit, RATE_LIMIT_WINDOW, now
        )
        if not allowed:
            return _rate_limit_response(
                "Please wait before generating more objections.", limit, reset_at
            )

        _increment_daily_budget(budget_key)

        response = await call_next(request)
        for k, v in _rate_limit_headers(limit, remaining, reset_at).items():
            response.headers[k] = v
        return response

    # --- /api/objections/parse rate limiting ---
    if request.url.path == "/api/objections/parse" and request.method == "POST":
        limit = AUTH_OBJECTION_PARSE_RATE_LIMIT_MAX if is_auth else OBJECTION_PARSE_RATE_LIMIT_MAX
        allowed, _, reset_at = _check_rate_limit(
            _objection_parse_rate_store, key, limit, 60, now
        )
        if not allowed:
            return _rate_limit_response(
                "Please wait before parsing again.", limit, reset_at
            )

    # --- /api/discovery/* rate limiting ---
    if request.url.path.startswith("/api/discovery/") and request.method == "POST":
        limit = AUTH_DISCOVERY_RATE_LIMIT_MAX if is_auth else DISCOVERY_RATE_LIMIT_MAX
        allowed, _, reset_at = _check_rate_limit(
            _discovery_rate_store, key, limit, 60, now
        )
        if not allowed:
            return _rate_limit_response(
                "Please wait before generating another document.", limit, reset_at
            )

    # --- /api/cases/*/files upload rate limiting ---
    if (
        request.method == "POST"
        and request.url.path.startswith("/api/cases/")
        and request.url.path.endswith("/files")
    ):
        limit = AUTH_CASEFILE_UPLOAD_RATE_LIMIT_MAX if is_auth else CASEFILE_UPLOAD_RATE_LIMIT_MAX
        allowed, _, reset_at = _check_rate_limit(
            _casefile_upload_rate_store, key, limit, 60, now
        )
        if not allowed:
            return _rate_limit_response(
                "Please wait before uploading more files.", limit, reset_at
            )

    # --- /api/cases/*/chat rate limiting ---
    if (
        request.method == "POST"
        and request.url.path.startswith("/api/cases/")
        and request.url.path.endswith("/chat")
    ):
        limit = AUTH_CASEFILE_CHAT_RATE_LIMIT_MAX if is_auth else CASEFILE_CHAT_RATE_LIMIT_MAX
        allowed, _, reset_at = _check_rate_limit(
            _casefile_chat_rate_store, key, limit, 60, now
        )
        if not allowed:
            return _rate_limit_response(
                "Please wait before sending another question.", limit, reset_at
            )

    # --- /api/feedback rate limiting (public) ---
    if request.url.path == "/api/feedback" and request.method == "POST":
        allowed, _, reset_at = _check_rate_limit(
            _feedback_rate_store, key, FEEDBACK_RATE_LIMIT_MAX, 60, now
        )
        if not allowed:
            return _rate_limit_response(
                "Please wait a moment.", FEEDBACK_RATE_LIMIT_MAX, reset_at
            )

    return await call_next(request)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Validate access token for protected paths, set request.state.user."""
    # Always initialize user state for downstream handlers and rate limiting
    request.state.user = None

    # Try to extract user from access token cookie
    access_token = request.cookies.get("access_token")
    if access_token:
        try:
            from employee_help.api.deps import get_session_manager

            session_manager = get_session_manager()
            request.state.user = session_manager.validate(access_token)
        except RuntimeError:
            pass  # Auth services not initialized

    # Protected paths require a valid access token
    if _requires_auth(request.url.path) and request.state.user is None:
        return Response(
            content='{"detail":"Authentication required"}',
            status_code=401,
            media_type="application/json",
        )

    return await call_next(request)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all API requests."""
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = int((time.monotonic() - start) * 1000)

    logger.info(
        "http_request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=duration_ms,
    )
    return response


app.include_router(router)
app.include_router(auth_router)
app.include_router(discovery_router)
app.include_router(objection_router)
app.include_router(casefile_router)
