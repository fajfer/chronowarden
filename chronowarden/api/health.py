# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""API routes for health and metrics."""

from importlib.metadata import metadata, version

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

router = APIRouter(tags=["health"])


@router.get("/health", summary="Health check endpoint")
async def health_check() -> dict[str, str]:
    """
    Basic health check endpoint.

    Returns:
        Health status.
    """
    return {"status": "healthy"}


@router.get("/info", summary="API information endpoint")
async def api_info() -> dict[str, str]:
    """
    Return API name, version and documentation link.

    Returns:
        API information dictionary.
    """
    return {
        "name": metadata("chronowarden")["Name"] + " API",
        "version": version("chronowarden"),
        "docs": "/docs",
    }


@router.get("/ready", summary="Readiness check endpoint")
async def readiness_check() -> dict[str, str]:
    """
    Readiness check endpoint for Kubernetes.

    Returns:
        Readiness status.
    """
    return {"status": "ready"}


@router.get("/metrics", summary="Prometheus metrics endpoint")
async def metrics() -> Response:
    """
    Expose Prometheus-compatible metrics.

    Returns:
        Prometheus metrics in OpenMetrics format.
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
