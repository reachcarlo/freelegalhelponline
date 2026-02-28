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

# Copy readme referenced by pyproject.toml
COPY docs/requirements/PHASE_1_KNOWLEDGE_ACQUISITION.md docs/requirements/

# Install dependencies only (no project install yet)
RUN uv sync --frozen --no-dev --extra rag --extra web --no-install-project

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

# Bootstrap data (baked into image, reassembled from splits)
COPY data/lancedb/ /app/_bootstrap/lancedb/
COPY data/splits/large_lance.part_* /tmp/lance_parts/
RUN cat /tmp/lance_parts/large_lance.part_* > /app/_bootstrap/lancedb/chunk_embeddings.lance/data/0000001000110111110001105ab58d465ea9b138c06c4baa3b.lance \
    && rm -rf /tmp/lance_parts
COPY data/splits/employee_help.db.part_* /tmp/db_parts/
RUN cat /tmp/db_parts/employee_help.db.part_* > /app/_bootstrap/employee_help.db \
    && rm -rf /tmp/db_parts

# Startup script: copy bootstrap data to volume if empty, then start server
RUN echo '#!/bin/sh\n\
set -e\n\
echo "Data dir contents:"\n\
mkdir -p /app/data\n\
ls -la /app/data/ || true\n\
DB_SIZE=$(stat -c%s /app/data/employee_help.db 2>/dev/null || echo 0)\n\
if [ "$DB_SIZE" -lt 1000000 ]; then\n\
  echo "Bootstrapping data to volume (db size: $DB_SIZE)..."\n\
  cp -r /app/_bootstrap/* /app/data/\n\
  echo "Bootstrap complete. New db size: $(stat -c%s /app/data/employee_help.db)"\n\
else\n\
  echo "Data already present ($DB_SIZE bytes), skipping bootstrap."\n\
fi\n\
echo "Starting server on port ${PORT:-8000}..."\n\
exec uvicorn employee_help.api.main:app --host 0.0.0.0 --port ${PORT:-8000}\n\
' > /app/start.sh && chmod +x /app/start.sh

EXPOSE 8000

CMD ["/app/start.sh"]
