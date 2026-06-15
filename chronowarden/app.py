# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

import logging
from contextlib import asynccontextmanager
from importlib.metadata import metadata, version
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

from chronowarden.api import health_router, owners_router, secrets_router, sync_router, vault_router
from chronowarden.config import AppConfig, load_config
from chronowarden.database import Database
from chronowarden.integrations import VaultManager

logger = logging.getLogger(__name__)

vault_manager = VaultManager()
db = Database()
app_config = AppConfig()


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
    vault_manager.start_reconnect_loop()
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
        {"name": "root", "description": "Root endpoint with API information"},
        {"name": "health", "description": "Health and metrics endpoints"},
        {"name": "secrets", "description": "Secret management operations"},
        {"name": "vault", "description": "HashiCorp Vault integration"},
        {"name": "sync", "description": "Metadata synchronization"},
        {"name": "owners", "description": "Owner profile management"},
    ],
)

# Include routers
app.include_router(health_router, prefix="/api/v1")
app.include_router(secrets_router, prefix="/api/v1")
app.include_router(vault_router, prefix="/api/v1")
app.include_router(sync_router, prefix="/api/v1")
app.include_router(owners_router, prefix="/api/v1")


@app.get("/api/v1", tags=["root"], summary="API endpoint")
async def root() -> dict[str, str]:
    """
    Root endpoint returning API information.

    Returns:
        API name and version.
    """
    return {
        "name": metadata("chronowarden")["Name"],
        "version": version("chronowarden"),
        "docs": "/docs",
    }


# Serve SvelteKit static frontend in production.
# The build directory is created by `npm run build` with adapter-static.
_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "build"

if _FRONTEND_DIR.is_dir():

    @app.get("/", include_in_schema=False)
    async def serve_index() -> FileResponse:
        """Serve the index.html file for the root path."""
        return FileResponse(_FRONTEND_DIR / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str) -> FileResponse:
        """Serve SvelteKit SPA with fallback to index.html for client-side routing."""
        file_path = _FRONTEND_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(_FRONTEND_DIR / "index.html")

    app.mount("/_app", StaticFiles(directory=_FRONTEND_DIR / "_app"), name="frontend-assets")
    logger.info("Frontend served from %s", _FRONTEND_DIR)
else:
    logger.warning("Frontend build not found at %s — UI will not be served", _FRONTEND_DIR)
