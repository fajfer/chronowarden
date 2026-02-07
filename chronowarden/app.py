# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Main FastAPI application for Chronowarden."""

import logging
from contextlib import asynccontextmanager
from importlib.metadata import metadata, version
from typing import AsyncIterator

from fastapi import FastAPI

from chronowarden.api import health_router, secrets_router, vault_router
from chronowarden.config import load_config
from chronowarden.integrations import VaultManager

logger = logging.getLogger(__name__)

vault_manager = VaultManager()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler for startup and shutdown events."""
    config = load_config()
    vault_manager.connect_all(config)
    logger.info("Chronowarden started with %d vault(s) configured", len(config.vaults))
    yield
    vault_manager.disconnect_all()
    logger.info("Chronowarden shutdown complete")


app = FastAPI(
    title=metadata("chronowarden")["Name"],
    description=metadata("chronowarden")["Description"],
    version=version("chronowarden"),
    lifespan=lifespan,
    openapi_tags=[
        {"name": "health", "description": "Health and metrics endpoints"},
        {"name": "secrets", "description": "Secret management operations"},
        {"name": "vault", "description": "HashiCorp Vault integration"},
    ],
)

# Include routers
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
        "name": metadata("chronowarden")["Name"] + " API",
        "version": version("chronowarden"),
        "docs": "/docs",
    }
