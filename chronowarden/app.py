# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

import logging
import os
from contextlib import asynccontextmanager
from importlib.metadata import metadata, version
from pathlib import Path
from typing import AsyncIterator, Optional

import sentry_sdk
from fastapi import FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

from chronowarden.api import health_router, owners_router, secrets_router, sync_router, vault_router
from chronowarden.api.sync import sync_vault_now
from chronowarden.config import AppConfig, load_config
from chronowarden.database import Database
from chronowarden.integrations import VaultManager
from chronowarden.logging_config import configure_logging

logger = logging.getLogger("uvicorn.error")

# Runs when uvicorn imports the app, after it set up its log handlers
configure_logging()

vault_manager = VaultManager()
db = Database()
app_config = AppConfig()


def _configure_sentry(config: AppConfig) -> None:
    """Initialize Sentry SDK if a DSN is configured."""
    if not config.sentry_dsn:
        logger.info("Sentry DSN is not configured; Sentry integration disabled")
        return

    sentry_sdk.init(
        dsn=config.sentry_dsn,
        # Add data like request headers and IP for users,
        # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
        send_default_pii=True,
        # Enable sending logs to Sentry
        enable_logs=True,
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for tracing.
        traces_sample_rate=1.0,
        # Set profile_session_sample_rate to 1.0 to profile 100%
        # of profile sessions.
        profile_session_sample_rate=1.0,
        # Set profile_lifecycle to "trace" to automatically
        # run the profiler on when there is an active transaction
        profile_lifecycle="trace",
    )


async def _sync_after_reconnect(vault_name: str) -> None:
    """Sync a vault right after the background loop reconnected it (#59)."""
    updated = await sync_vault_now(vault_manager, vault_name, app_config, db)
    logger.info("Synced vault '%s' after reconnect: %d secret(s)", vault_name, len(updated))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler for startup and shutdown events."""
    global app_config
    try:
        app_config = load_config()
        _configure_sentry(app_config)
        vault_manager.connect_all(app_config)

        db_path = Path("chronowarden.db")
        db._db_path = db_path
        db.connect()

        logger.info("Chronowarden started with %d vault(s) configured", len(app_config.vaults))
        vault_manager.set_reconnect_callback(_sync_after_reconnect)
        vault_manager.start_reconnect_loop()
        yield
    except Exception:
        logger.exception("Chronowarden startup failed")
        raise
    finally:
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
def _resolve_frontend_dir() -> Path:
    """Return the first existing frontend build directory."""
    override = os.environ.get("CHRONOWARDEN_FRONTEND_DIR")
    candidates = [
        Path(override) if override else None,
        Path(__file__).resolve().parent.parent / "frontend" / "build",
        Path("/app/frontend/build"),
    ]
    for candidate in candidates:
        if candidate is not None and candidate.is_dir():
            return candidate
    return Path("/app/frontend/build")


_API_PREFIX = "api"


def _frontend_file(frontend_dir: Path, full_path: str) -> Optional[Path]:
    """
    Return the requested file if it exists inside the frontend build directory.

    The path is resolved first, so `..` segments (also URL-encoded ones) can't escape the directory.

    Args:
        frontend_dir: The frontend build directory.
        full_path: The request path without the leading slash.

    Returns:
        The file to serve, or None if it doesn't exist or lies outside frontend_dir.
    """
    root = frontend_dir.resolve()
    candidate = (root / full_path).resolve()
    if candidate.is_relative_to(root) and candidate.is_file():
        return candidate
    return None


def register_frontend(target: FastAPI, frontend_dir: Path) -> None:
    """
    Serve the SvelteKit SPA from frontend_dir, falling back to index.html for client-side routes.

    Must be called after all API routers are included: the catch-all route matches every other path.
    Unknown `/api/...` paths get a 404 instead of the SPA page.

    Args:
        target: The application to register the routes on.
        frontend_dir: The frontend build directory (output of `npm run build`).
    """

    @target.get("/", include_in_schema=False)
    async def serve_index() -> FileResponse:
        """Serve the index.html file for the root path."""
        return FileResponse(frontend_dir / "index.html")

    @target.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str) -> FileResponse:
        """Serve a file from the build directory, or index.html for client-side routes."""
        if full_path == _API_PREFIX or full_path.startswith(f"{_API_PREFIX}/"):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
        file_path = _frontend_file(frontend_dir, full_path)
        return FileResponse(file_path if file_path is not None else frontend_dir / "index.html")

    target.mount("/_app", StaticFiles(directory=frontend_dir / "_app"), name="frontend-assets")


_FRONTEND_DIR = _resolve_frontend_dir()

if _FRONTEND_DIR.is_dir():
    register_frontend(app, _FRONTEND_DIR)
    logger.info("Frontend served from %s", _FRONTEND_DIR)
else:
    logger.warning("Frontend build not found at %s — UI will not be served", _FRONTEND_DIR)
