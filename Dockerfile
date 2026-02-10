# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

# ============================================================================
# Stage 1: Frontend builder
# ============================================================================
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ============================================================================
# Stage 2: Backend builder
# ============================================================================
FROM python:3.12-slim AS backend-builder

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY chronowarden/ /app/chronowarden/

RUN python -m venv /app/.venv \
  && /app/.venv/bin/pip install --no-cache-dir --upgrade pip \
  && /app/.venv/bin/pip install --no-cache-dir .

# ============================================================================
# Stage 3a: Development image  (--target dev)
#   Includes shell, dev tools, editable source mounts expected
# ============================================================================
FROM python:3.12-slim AS dev

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 chronowarden

WORKDIR /app

COPY --from=backend-builder /app/.venv /app/.venv
COPY chronowarden/ /app/chronowarden/
COPY --from=frontend-builder /app/frontend/build /app/frontend/build

RUN mkdir -p /data && chown -R chronowarden:chronowarden /app /data

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    CHRONOWARDEN_CONFIG=/data/config.yaml

EXPOSE 8000

USER chronowarden

CMD ["uvicorn", "chronowarden:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ============================================================================
# Stage 3b: Production image  (default target)
# ============================================================================
FROM python:3.12-slim AS production

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 chronowarden

WORKDIR /app

COPY --from=backend-builder /app/.venv /app/.venv
COPY chronowarden/ /app/chronowarden/
COPY --from=frontend-builder /app/frontend/build /app/frontend/build

RUN mkdir -p /data && chown -R chronowarden:chronowarden /app /data

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    CHRONOWARDEN_CONFIG=/data/config.yaml

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["curl", "-f", "http://localhost:8000/api/v1/health"]

USER chronowarden

ENTRYPOINT ["uvicorn", "chronowarden:app", "--host", "0.0.0.0", "--port", "8000"]
