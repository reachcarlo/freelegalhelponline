"""FastAPI application entry point.

Start with:
    uv run uvicorn employee_help.api.main:app --reload --port 8000
"""

from __future__ import annotations

import os
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import sentry_sdk
import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from employee_help.api.deps import init_services, shutdown_services
from employee_help.api.discovery_routes import discovery_router
from employee_help.api.objection_routes import objection_router
from employee_help.api.routes import router

logger = structlog.get_logger(__name__)

# Load .env file if present (for ANTHROPIC_API_KEY and other config)
_env_path = Path(__file__).resolve().parents[3] / ".env"
if _env_path.exists():
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _, _val = _line.partition("=")
                os.environ.setdefault(_key.strip(), _val.strip())

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
DAILY_QUERY_BUDGET = int(os.environ.get("DAILY_QUERY_BUDGET", "500"))

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
_daily_budget: dict[str, int] = {"date": "", "count": 0}  # type: ignore[dict-item]


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


def _check_daily_budget() -> tuple[bool, int]:
    """Check if daily query budget is exceeded. Returns (allowed, remaining)."""
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    if _daily_budget["date"] != today:
        _daily_budget["date"] = today
        _daily_budget["count"] = 0
    remaining = DAILY_QUERY_BUDGET - int(_daily_budget["count"])
    return remaining > 0, max(remaining, 0)


def _increment_daily_budget() -> None:
    """Increment today's query count."""
    _daily_budget["count"] = int(_daily_budget["count"]) + 1


def _rate_limit_headers(
    limit: int, remaining: int, reset_at: float
) -> dict[str, str]:
    """Build rate limit response headers."""
    return {
        "X-RateLimit-Limit": str(limit),
        "X-RateLimit-Remaining": str(max(remaining, 0)),
        "X-RateLimit-Reset": str(int(reset_at)),
    }


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
    """Rate limiting for /api/ask and /api/feedback."""
    now = time.time()
    client_ip = _get_client_ip(request)

    # --- /api/ask rate limiting ---
    if request.url.path == "/api/ask" and request.method == "POST":
        # Check daily budget first
        budget_ok, budget_remaining = _check_daily_budget()
        if not budget_ok:
            return Response(
                content='{"detail":"Daily query budget exceeded. Please try again tomorrow."}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": "3600"},
            )

        # Per-IP rate limiting
        _rate_limit_store[client_ip] = [
            t for t in _rate_limit_store[client_ip] if now - t < RATE_LIMIT_WINDOW
        ]
        count = len(_rate_limit_store[client_ip])
        remaining = RATE_LIMIT_MAX - count
        reset_at = now + RATE_LIMIT_WINDOW

        if count >= RATE_LIMIT_MAX:
            oldest = _rate_limit_store[client_ip][0]
            reset_at = oldest + RATE_LIMIT_WINDOW
            return Response(
                content='{"detail":"Rate limit exceeded. Please wait before asking another question."}',
                status_code=429,
                media_type="application/json",
                headers=_rate_limit_headers(RATE_LIMIT_MAX, 0, reset_at),
            )

        _rate_limit_store[client_ip].append(now)
        _increment_daily_budget()
        remaining -= 1

        # Periodically prune stale entries
        if len(_rate_limit_store) > 100:
            _prune_stale_entries(_rate_limit_store, RATE_LIMIT_WINDOW)

        response = await call_next(request)
        for k, v in _rate_limit_headers(RATE_LIMIT_MAX, remaining, reset_at).items():
            response.headers[k] = v
        return response

    # --- /api/deadlines rate limiting ---
    if request.url.path == "/api/deadlines" and request.method == "POST":
        _deadline_rate_store[client_ip] = [
            t for t in _deadline_rate_store[client_ip] if now - t < 60
        ]
        count = len(_deadline_rate_store[client_ip])

        if count >= DEADLINE_RATE_LIMIT_MAX:
            oldest = _deadline_rate_store[client_ip][0]
            return Response(
                content='{"detail":"Rate limit exceeded. Please wait before making another calculation."}',
                status_code=429,
                media_type="application/json",
                headers=_rate_limit_headers(DEADLINE_RATE_LIMIT_MAX, 0, oldest + 60),
            )

        _deadline_rate_store[client_ip].append(now)

        if len(_deadline_rate_store) > 100:
            _prune_stale_entries(_deadline_rate_store, 60)

    # --- /api/agency-routing rate limiting ---
    if request.url.path == "/api/agency-routing" and request.method == "POST":
        _routing_rate_store[client_ip] = [
            t for t in _routing_rate_store[client_ip] if now - t < 60
        ]
        count = len(_routing_rate_store[client_ip])

        if count >= ROUTING_RATE_LIMIT_MAX:
            oldest = _routing_rate_store[client_ip][0]
            return Response(
                content='{"detail":"Rate limit exceeded. Please wait before making another request."}',
                status_code=429,
                media_type="application/json",
                headers=_rate_limit_headers(ROUTING_RATE_LIMIT_MAX, 0, oldest + 60),
            )

        _routing_rate_store[client_ip].append(now)

        if len(_routing_rate_store) > 100:
            _prune_stale_entries(_routing_rate_store, 60)

    # --- /api/unpaid-wages rate limiting ---
    if request.url.path == "/api/unpaid-wages" and request.method == "POST":
        _wages_rate_store[client_ip] = [
            t for t in _wages_rate_store[client_ip] if now - t < 60
        ]
        count = len(_wages_rate_store[client_ip])

        if count >= WAGES_RATE_LIMIT_MAX:
            oldest = _wages_rate_store[client_ip][0]
            return Response(
                content='{"detail":"Rate limit exceeded. Please wait before making another calculation."}',
                status_code=429,
                media_type="application/json",
                headers=_rate_limit_headers(WAGES_RATE_LIMIT_MAX, 0, oldest + 60),
            )

        _wages_rate_store[client_ip].append(now)

        if len(_wages_rate_store) > 100:
            _prune_stale_entries(_wages_rate_store, 60)

    # --- /api/incident-guide rate limiting ---
    if request.url.path == "/api/incident-guide" and request.method == "POST":
        _incident_guide_rate_store[client_ip] = [
            t for t in _incident_guide_rate_store[client_ip] if now - t < 60
        ]
        count = len(_incident_guide_rate_store[client_ip])

        if count >= INCIDENT_GUIDE_RATE_LIMIT_MAX:
            oldest = _incident_guide_rate_store[client_ip][0]
            return Response(
                content='{"detail":"Rate limit exceeded. Please wait before making another request."}',
                status_code=429,
                media_type="application/json",
                headers=_rate_limit_headers(INCIDENT_GUIDE_RATE_LIMIT_MAX, 0, oldest + 60),
            )

        _incident_guide_rate_store[client_ip].append(now)

        if len(_incident_guide_rate_store) > 100:
            _prune_stale_entries(_incident_guide_rate_store, 60)

    # --- /api/intake rate limiting ---
    if request.url.path == "/api/intake" and request.method == "POST":
        _intake_rate_store[client_ip] = [
            t for t in _intake_rate_store[client_ip] if now - t < 60
        ]
        count = len(_intake_rate_store[client_ip])

        if count >= INTAKE_RATE_LIMIT_MAX:
            oldest = _intake_rate_store[client_ip][0]
            return Response(
                content='{"detail":"Rate limit exceeded. Please wait before submitting another questionnaire."}',
                status_code=429,
                media_type="application/json",
                headers=_rate_limit_headers(INTAKE_RATE_LIMIT_MAX, 0, oldest + 60),
            )

        _intake_rate_store[client_ip].append(now)

        if len(_intake_rate_store) > 100:
            _prune_stale_entries(_intake_rate_store, 60)

    # --- /api/intake-summary rate limiting (LLM endpoint) ---
    if request.url.path == "/api/intake-summary" and request.method == "POST":
        # Check daily budget first
        budget_ok, budget_remaining = _check_daily_budget()
        if not budget_ok:
            return Response(
                content='{"detail":"Daily query budget exceeded. Please try again tomorrow."}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": "3600"},
            )

        _intake_summary_rate_store[client_ip] = [
            t for t in _intake_summary_rate_store[client_ip] if now - t < RATE_LIMIT_WINDOW
        ]
        count = len(_intake_summary_rate_store[client_ip])
        remaining = INTAKE_SUMMARY_RATE_LIMIT_MAX - count
        reset_at = now + RATE_LIMIT_WINDOW

        if count >= INTAKE_SUMMARY_RATE_LIMIT_MAX:
            oldest = _intake_summary_rate_store[client_ip][0]
            reset_at = oldest + RATE_LIMIT_WINDOW
            return Response(
                content='{"detail":"Rate limit exceeded. Please wait before requesting another summary."}',
                status_code=429,
                media_type="application/json",
                headers=_rate_limit_headers(INTAKE_SUMMARY_RATE_LIMIT_MAX, 0, reset_at),
            )

        _intake_summary_rate_store[client_ip].append(now)
        _increment_daily_budget()
        remaining -= 1

        if len(_intake_summary_rate_store) > 100:
            _prune_stale_entries(_intake_summary_rate_store, RATE_LIMIT_WINDOW)

        response = await call_next(request)
        for k, v in _rate_limit_headers(INTAKE_SUMMARY_RATE_LIMIT_MAX, remaining, reset_at).items():
            response.headers[k] = v
        return response

    # --- /api/objections/generate rate limiting (LLM endpoint) ---
    if request.url.path == "/api/objections/generate" and request.method == "POST":
        budget_ok, budget_remaining = _check_daily_budget()
        if not budget_ok:
            return Response(
                content='{"detail":"Daily query budget exceeded. Please try again tomorrow."}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": "3600"},
            )

        _objection_generate_rate_store[client_ip] = [
            t for t in _objection_generate_rate_store[client_ip] if now - t < RATE_LIMIT_WINDOW
        ]
        count = len(_objection_generate_rate_store[client_ip])
        remaining = OBJECTION_GENERATE_RATE_LIMIT_MAX - count
        reset_at = now + RATE_LIMIT_WINDOW

        if count >= OBJECTION_GENERATE_RATE_LIMIT_MAX:
            oldest = _objection_generate_rate_store[client_ip][0]
            reset_at = oldest + RATE_LIMIT_WINDOW
            return Response(
                content='{"detail":"Rate limit exceeded. Please wait before generating more objections."}',
                status_code=429,
                media_type="application/json",
                headers=_rate_limit_headers(OBJECTION_GENERATE_RATE_LIMIT_MAX, 0, reset_at),
            )

        _objection_generate_rate_store[client_ip].append(now)
        _increment_daily_budget()
        remaining -= 1

        if len(_objection_generate_rate_store) > 100:
            _prune_stale_entries(_objection_generate_rate_store, RATE_LIMIT_WINDOW)

        response = await call_next(request)
        for k, v in _rate_limit_headers(OBJECTION_GENERATE_RATE_LIMIT_MAX, remaining, reset_at).items():
            response.headers[k] = v
        return response

    # --- /api/objections/parse rate limiting ---
    if request.url.path == "/api/objections/parse" and request.method == "POST":
        _objection_parse_rate_store[client_ip] = [
            t for t in _objection_parse_rate_store[client_ip] if now - t < 60
        ]
        count = len(_objection_parse_rate_store[client_ip])

        if count >= OBJECTION_PARSE_RATE_LIMIT_MAX:
            oldest = _objection_parse_rate_store[client_ip][0]
            return Response(
                content='{"detail":"Rate limit exceeded. Please wait before parsing again."}',
                status_code=429,
                media_type="application/json",
                headers=_rate_limit_headers(OBJECTION_PARSE_RATE_LIMIT_MAX, 0, oldest + 60),
            )

        _objection_parse_rate_store[client_ip].append(now)

        if len(_objection_parse_rate_store) > 100:
            _prune_stale_entries(_objection_parse_rate_store, 60)

    # --- /api/discovery/* rate limiting ---
    if request.url.path.startswith("/api/discovery/") and request.method == "POST":
        _discovery_rate_store[client_ip] = [
            t for t in _discovery_rate_store[client_ip] if now - t < 60
        ]
        count = len(_discovery_rate_store[client_ip])

        if count >= DISCOVERY_RATE_LIMIT_MAX:
            oldest = _discovery_rate_store[client_ip][0]
            return Response(
                content='{"detail":"Rate limit exceeded. Please wait before generating another document."}',
                status_code=429,
                media_type="application/json",
                headers=_rate_limit_headers(DISCOVERY_RATE_LIMIT_MAX, 0, oldest + 60),
            )

        _discovery_rate_store[client_ip].append(now)

        if len(_discovery_rate_store) > 100:
            _prune_stale_entries(_discovery_rate_store, 60)

    # --- /api/feedback rate limiting ---
    if request.url.path == "/api/feedback" and request.method == "POST":
        _feedback_rate_store[client_ip] = [
            t for t in _feedback_rate_store[client_ip] if now - t < 60
        ]
        count = len(_feedback_rate_store[client_ip])

        if count >= FEEDBACK_RATE_LIMIT_MAX:
            oldest = _feedback_rate_store[client_ip][0]
            return Response(
                content='{"detail":"Feedback rate limit exceeded. Please wait a moment."}',
                status_code=429,
                media_type="application/json",
                headers=_rate_limit_headers(FEEDBACK_RATE_LIMIT_MAX, 0, oldest + 60),
            )

        _feedback_rate_store[client_ip].append(now)

        if len(_feedback_rate_store) > 100:
            _prune_stale_entries(_feedback_rate_store, 60)

    return await call_next(request)


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
app.include_router(discovery_router)
app.include_router(objection_router)
