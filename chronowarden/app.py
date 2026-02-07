# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Main FastAPI application for Chronowarden."""

import logging
import re
from contextlib import asynccontextmanager
from importlib.metadata import metadata, version
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI

from chronowarden.api import health_router, owners_router, secrets_router, sync_router, vault_router
from chronowarden.config import AppConfig, load_config
from chronowarden.database import Database
from chronowarden.integrations import VaultManager

logger = logging.getLogger(__name__)

vault_manager = VaultManager()
db = Database()
app_config = AppConfig()

_POLLING_INTERVAL_PATTERN = re.compile(r"^(\d+)([hms])$")


def _parse_polling_interval_seconds(interval: str) -> int:
    """
    Parse a polling interval string to seconds.

    Args:
        interval: Interval string (e.g. '6h', '30m', '60s').

    Returns:
        Interval in seconds.
    """
    match = _POLLING_INTERVAL_PATTERN.match(interval.strip().lower())
    if not match:
        logger.warning("Invalid polling interval '%s', defaulting to 6h", interval)
        return 21600

    value = int(match.group(1))
    unit = match.group(2)

    if unit == "h":
        return value * 3600
    elif unit == "m":
        return value * 60
    else:
        return value


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler for startup and shutdown events."""
    global app_config
    app_config = load_config()
    vault_manager.connect_all(app_config)

    db_path = Path("chronowarden.db")
    db._db_path = db_path
    db.connect()

    logger.info("Chronowarden started with %d vault(s) configured", len(app_config.vaults))
    yield
    db.close()
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
        {"name": "sync", "description": "Metadata synchronization"},
        {"name": "owners", "description": "Owner profile management"},
    ],
)

# Include routers
app.include_router(secrets_router, prefix="/api/v1")
app.include_router(vault_router, prefix="/api/v1")
app.include_router(sync_router, prefix="/api/v1")
app.include_router(owners_router, prefix="/api/v1")


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
