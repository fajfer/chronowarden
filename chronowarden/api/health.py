# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""API routes for health and metrics."""

from importlib.metadata import metadata, version
from typing import Any

from fastapi import APIRouter, HTTPException, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from chronowarden.compliance.report import reports_available

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
async def api_info() -> dict[str, Any]:
    """
    Return API name, version, documentation link, the instance default UI theme and the features of this image.

    Returns:
        API information dictionary; `features` says whether the UI and PDF reports are there (ADR-024).
    """
    from chronowarden.app import _FRONTEND_DIR, app_config

    return {
        "name": metadata("chronowarden")["Name"] + " API",
        "version": version("chronowarden"),
        "docs": "/docs",
        "default_theme": app_config.resolve_default_theme(),
        "features": {"ui": _FRONTEND_DIR.is_dir(), "pdf_reports": reports_available()},
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
    Expose Prometheus-compatible metrics when `metrics.enabled` is set (off by default, ADR-022).

    Returns:
        Prometheus metrics in OpenMetrics format.

    Raises:
        HTTPException: 404 while metrics are disabled.
    """
    from chronowarden.app import app_config

    if not app_config.metrics.enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Metrics are disabled; set metrics.enabled: true in config.yaml to serve them",
        )
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
