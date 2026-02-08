# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

# ============================================================================
# Stage 1: Build Frontend
# ============================================================================
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci --omit=dev

COPY frontend/ ./
RUN npm run build

# ============================================================================
# Stage 2: Build Backend Dependencies
# ============================================================================
FROM python:3.12-slim AS backend-builder

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
RUN uv sync --no-dev

# ============================================================================
# Stage 3: Runtime Image
# ============================================================================
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 chronowarden

WORKDIR /app

# Copy Python virtual environment from builder
COPY --from=backend-builder /app/.venv /app/.venv

# Copy backend source
COPY chronowarden/ /app/chronowarden/

# Copy built frontend
COPY --from=frontend-builder /app/frontend/.svelte-kit /app/frontend/.svelte-kit
COPY --from=frontend-builder /app/frontend/static /app/frontend/static

# Create data directory
RUN mkdir -p /data && chown -R chronowarden:chronowarden /app /data

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    CHRONOWARDEN_CONFIG=/data/config.yaml

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8000/api/v1/health || exit 1

EXPOSE 8000

USER chronowarden

CMD ["uvicorn", "chronowarden:app", "--host", "0.0.0.0", "--port", "8000"]
