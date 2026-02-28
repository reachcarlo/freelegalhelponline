# ============================================================
# Employee Help — Production Docker Image (Railway)
# ============================================================
# Multi-stage build: builder installs deps, runtime copies them.
# Data (LanceDB, SQLite) lives on a persistent volume at /app/data.
# ============================================================

# --- Stage 1: Builder ---
FROM python:3.12-slim AS builder

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first (layer caching)
COPY pyproject.toml uv.lock ./

# Install production dependencies (rag + web groups)
RUN uv sync --frozen --no-dev --extra rag --extra web

# Copy source code and config
COPY src/ src/
COPY config/ config/

# Install the project itself
RUN uv sync --frozen --no-dev --extra rag --extra web

# --- Stage 2: Runtime ---
FROM python:3.12-slim

# curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed virtualenv from builder
COPY --from=builder /app/.venv /app/.venv

# Copy source and config
COPY --from=builder /app/src src/
COPY --from=builder /app/config config/
COPY --from=builder /app/pyproject.toml pyproject.toml

# Put venv on PATH
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/api/health || exit 1

CMD ["sh", "-c", "uvicorn employee_help.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
