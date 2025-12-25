# SPDX-FileCopyrightText: 2025 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Main FastAPI application for Chronowarden."""

import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from chronowarden.api import health_router, secrets_router, vault_router
from chronowarden.metrics import API_REQUEST_DURATION_SECONDS, API_REQUESTS_TOTAL


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler for startup and shutdown events."""
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title="Chronowarden",
    description="Secret management service with expiration tracking",
    version="0.1.0",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "health", "description": "Health and metrics endpoints"},
        {"name": "secrets", "description": "Secret management operations"},
        {"name": "vault", "description": "HashiCorp Vault integration"},
    ],
)

# CORS middleware for frontend access
# NOTE: In production, replace "*" with specific allowed origins (e.g., ["https://chronowarden.example.com"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Middleware to track API request metrics."""
    start_time = time.time()

    response = await call_next(request)

    duration = time.time() - start_time
    endpoint = request.url.path
    method = request.method

    API_REQUESTS_TOTAL.labels(
        method=method,
        endpoint=endpoint,
        status=response.status_code,
    ).inc()

    API_REQUEST_DURATION_SECONDS.labels(
        method=method,
        endpoint=endpoint,
    ).observe(duration)

    return response


# Include routers
app.include_router(health_router)
app.include_router(secrets_router, prefix="/api/v1")
app.include_router(vault_router, prefix="/api/v1")


@app.get("/", summary="Root endpoint")
async def root() -> dict[str, str]:
    """
    Root endpoint returning API information.

    Returns:
        API name and version.
    """
    return {
        "name": "Chronowarden API",
        "version": "0.1.0",
        "docs": "/docs",
    }
