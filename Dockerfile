# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

# ============================================================================
# Stage 1: Frontend builder
#   Runs on the build machine's native platform: the output is static HTML/JS,
#   identical for every target, and npm under QEMU emulation can hang.
# ============================================================================
# Base images are pinned by digest (tag kept for readers); Dependabot updates both.
FROM --platform=$BUILDPLATFORM node:22-alpine@sha256:0a7108bf6c7bf5de370ffb1a3ed6be93d405b43ff159f681a8d18c0e2bc2e402 AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ============================================================================
# Stage 2: Backend builder
# ============================================================================
FROM ghcr.io/astral-sh/uv:0.13.0@sha256:cdc6093146eb3ff6a40107b38f008b789e050e77ad87865e381d9917da55a168 AS uv

FROM python:3.13.15-slim@sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b AS backend-builder

COPY --from=uv /uv /usr/local/bin/uv

# Use the image's Python, copy files instead of hard-linking from the cache
ENV UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

COPY pyproject.toml uv.lock README.md /app/
COPY chronowarden/ /app/chronowarden/

# Exactly the versions in uv.lock, runtime dependencies only
RUN uv sync --locked --no-dev --no-editable --no-cache

# ============================================================================
# Stage 3a: Development image  (--target dev)
#   Includes shell, dev tools, editable source mounts expected
# ============================================================================
FROM python:3.13.15-slim@sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b AS dev

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
FROM gcr.io/distroless/python3-debian13:nonroot@sha256:83aa8d4f74a4d7f7cf2d472054139bef71a927b76c680c0f2e1021d6b1d6d732 AS production

WORKDIR /app

COPY --from=backend-builder /app/.venv/lib/python3.13/site-packages /app/.venv/lib/python3.13/site-packages
COPY chronowarden/ /app/chronowarden/
COPY --from=frontend-builder /app/frontend/build /app/frontend/build

ENV PYTHONPATH="/app/.venv/lib/python3.13/site-packages:/app" \
    PYTHONUNBUFFERED=1 \
    CHRONOWARDEN_CONFIG=/data/config.yaml

EXPOSE 8000

ENTRYPOINT ["python", "-m", "uvicorn", "chronowarden:app", "--host", "0.0.0.0", "--port", "8000"]
