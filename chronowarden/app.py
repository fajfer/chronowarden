# SPDX-FileCopyrightText: 2025 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Main FastAPI application for Chronowarden."""

from contextlib import asynccontextmanager
from importlib.metadata import metadata, version
from typing import AsyncIterator

from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler for startup and shutdown events."""
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title=metadata("chronowarden")["Name"],
    description=metadata("chronowarden")["Description"],
    version=version("chronowarden"),
    lifespan=lifespan,
)

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
