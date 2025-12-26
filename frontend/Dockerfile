# SPDX-FileCopyrightText: 2025 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

# =============================================================================
# Multi-stage Dockerfile for Chronowarden Frontend
# =============================================================================
# Build targets:
#   - production: Distroless nginx image serving static files (default)
#   - development: Node.js image with hot-reload for development
#
# Usage:
#   Production:  docker build -t chronowarden-frontend .
#   Development: docker build --target development -t chronowarden-frontend:dev .
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Dependencies - Install npm dependencies
# -----------------------------------------------------------------------------
FROM node:22-slim AS dependencies

WORKDIR /build

# Copy package files for dependency installation
COPY package.json package-lock.json ./

# Install dependencies
RUN npm ci

# -----------------------------------------------------------------------------
# Stage 2: Builder - Build the production application
# -----------------------------------------------------------------------------
FROM dependencies AS builder

# Copy source code
COPY . .

# Build the application
RUN npm run build

# -----------------------------------------------------------------------------
# Stage 3: Production - Distroless nginx serving static files
# -----------------------------------------------------------------------------
FROM nginx:alpine AS production

# Remove default nginx config and html
RUN rm -rf /usr/share/nginx/html/* /etc/nginx/conf.d/default.conf

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built static files
COPY --from=builder /build/dist /usr/share/nginx/html

# Run as non-root user
RUN addgroup -g 1001 -S appgroup && \
    adduser -u 1001 -S appuser -G appgroup && \
    chown -R appuser:appgroup /usr/share/nginx/html && \
    chown -R appuser:appgroup /var/cache/nginx && \
    chown -R appuser:appgroup /var/log/nginx && \
    touch /var/run/nginx.pid && \
    chown -R appuser:appgroup /var/run/nginx.pid

USER appuser

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080/ || exit 1

LABEL org.opencontainers.image.title="Chronowarden Frontend" \
      org.opencontainers.image.description="Secret management service - Web UI" \
      org.opencontainers.image.version="0.1.0" \
      org.opencontainers.image.vendor="Damian Fajfer" \
      org.opencontainers.image.licenses="EUPL-1.2"

CMD ["nginx", "-g", "daemon off;"]

# -----------------------------------------------------------------------------
# Stage 4: Development - Node.js with hot-reload
# -----------------------------------------------------------------------------
FROM node:22-slim AS development

WORKDIR /app

# Install additional tools for development
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies from dependencies stage
COPY --from=dependencies /build/node_modules ./node_modules

# Copy source code
COPY . .

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose development server port
EXPOSE 5173

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5173/ || exit 1

LABEL org.opencontainers.image.title="Chronowarden Frontend (Development)" \
      org.opencontainers.image.description="Secret management service - Development image with hot-reload" \
      org.opencontainers.image.version="0.1.0-dev" \
      org.opencontainers.image.vendor="Damian Fajfer" \
      org.opencontainers.image.licenses="EUPL-1.2"

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
