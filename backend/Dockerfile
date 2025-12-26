# SPDX-FileCopyrightText: 2025 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

# =============================================================================
# Multi-stage Dockerfile for Chronowarden Backend
# =============================================================================
# Build targets:
#   - production: Distroless image for minimal attack surface (default)
#   - development: Full Python image with shell and debugging tools
#
# Usage:
#   Production:  docker build -t chronowarden-backend .
#   Development: docker build --target development -t chronowarden-backend:dev .
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Builder - Install dependencies and build the application
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first for better layer caching
COPY pyproject.toml ./

# Copy source code
COPY src/ ./src/

# Install the application and its dependencies
RUN pip install --no-cache-dir .

# -----------------------------------------------------------------------------
# Stage 2: Production - Distroless image for minimal footprint
# -----------------------------------------------------------------------------
FROM gcr.io/distroless/python3-debian12 AS production

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Copy application source
COPY --from=builder /build/src/chronowarden /app/chronowarden

# Set Python path to include our packages
ENV PYTHONPATH="/usr/local/lib/python3.11/site-packages:/app"

# Run as non-root user (distroless provides a nonroot user)
USER nonroot

# Expose the application port
EXPOSE 8000

# Health check
# Note: distroless doesn't have curl, health checks are done via Kubernetes probes
LABEL org.opencontainers.image.title="Chronowarden Backend" \
      org.opencontainers.image.description="Secret management service with expiration tracking" \
      org.opencontainers.image.version="0.1.0" \
      org.opencontainers.image.vendor="Damian Fajfer" \
      org.opencontainers.image.licenses="EUPL-1.2"

# Run the application
ENTRYPOINT ["python", "-m", "uvicorn", "chronowarden.app:app", "--host", "0.0.0.0", "--port", "8000"]

# -----------------------------------------------------------------------------
# Stage 3: Development - Full image with debugging tools
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS development

WORKDIR /app

# Install runtime and debugging tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    vim \
    procps \
    net-tools \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Copy application source
COPY --from=builder /build/src/chronowarden /app/chronowarden

# Install development dependencies
RUN pip install --no-cache-dir \
    pytest>=8.3.0 \
    pytest-asyncio>=0.24.0 \
    httpx>=0.28.0 \
    ruff>=0.8.0 \
    black>=24.10.0

# Set Python path
ENV PYTHONPATH="/usr/local/lib/python3.11/site-packages:/app"

# Create non-root user for development
RUN useradd --create-home --shell /bin/bash appuser
USER appuser

# Expose the application port
EXPOSE 8000

# Health check with curl available
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

LABEL org.opencontainers.image.title="Chronowarden Backend (Development)" \
      org.opencontainers.image.description="Secret management service - Development image with debugging tools" \
      org.opencontainers.image.version="0.1.0-dev" \
      org.opencontainers.image.vendor="Damian Fajfer" \
      org.opencontainers.image.licenses="EUPL-1.2"

# Run the application with auto-reload for development
CMD ["python", "-m", "uvicorn", "chronowarden.app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# -----------------------------------------------------------------------------
# Stage 4: Test - Image for running tests in CI/CD pipelines
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS test

WORKDIR /app

# Install runtime and test dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Copy application source
COPY --from=builder /build/src/chronowarden /app/chronowarden

# Copy test files
COPY tests/ /app/tests/
COPY pyproject.toml /app/

# Install test dependencies including coverage
RUN pip install --no-cache-dir \
    pytest>=8.3.0 \
    pytest-asyncio>=0.24.0 \
    pytest-cov>=4.1.0 \
    httpx>=0.28.0 \
    ruff>=0.8.0 \
    black>=24.10.0 \
    syft \
    azure-identity>=1.15.0 \
    azure-keyvault-secrets>=4.8.0 \
    azure-keyvault-certificates>=4.8.0

# Set Python path
ENV PYTHONPATH="/usr/local/lib/python3.11/site-packages:/app"

# Create test results directory
RUN mkdir -p /app/test-results

# Create non-root user for testing
RUN useradd --create-home --shell /bin/bash testuser && \
    chown -R testuser:testuser /app
USER testuser

# Expose the application port
EXPOSE 8000

LABEL org.opencontainers.image.title="Chronowarden Backend (Test)" \
      org.opencontainers.image.description="Secret management service - Test image for CI/CD" \
      org.opencontainers.image.version="0.1.0-test" \
      org.opencontainers.image.vendor="Damian Fajfer" \
      org.opencontainers.image.licenses="EUPL-1.2"

# Default command runs the test suite
CMD ["pytest", "tests/", "-v", "--tb=short"]
