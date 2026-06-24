# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for application lifespan startup and shutdown cleanup."""

from unittest.mock import patch

import pytest
from fastapi import FastAPI

from chronowarden.config import AppConfig
from chronowarden.app import lifespan


@pytest.mark.asyncio
async def test_lifespan_runs_cleanup_on_normal_shutdown() -> None:
    """Lifespan should close DB and disconnect vaults on normal shutdown."""
    with (
        patch("chronowarden.app.load_config", return_value=AppConfig()),
        patch("chronowarden.app._configure_sentry"),
        patch("chronowarden.app.vault_manager.connect_all"),
        patch("chronowarden.app.vault_manager.start_reconnect_loop"),
        patch("chronowarden.app.vault_manager.disconnect_all") as mock_disconnect_all,
        patch("chronowarden.app.db.connect"),
        patch("chronowarden.app.db.close") as mock_db_close,
    ):
        async with lifespan(FastAPI()):
            pass

    mock_db_close.assert_called_once_with()
    mock_disconnect_all.assert_called_once_with()


@pytest.mark.asyncio
async def test_lifespan_runs_cleanup_when_startup_fails() -> None:
    """Lifespan should still run cleanup when startup fails before yield."""
    with (
        patch("chronowarden.app.load_config", return_value=AppConfig()),
        patch("chronowarden.app._configure_sentry"),
        patch("chronowarden.app.vault_manager.connect_all"),
        patch("chronowarden.app.vault_manager.start_reconnect_loop"),
        patch("chronowarden.app.vault_manager.disconnect_all") as mock_disconnect_all,
        patch("chronowarden.app.db.connect", side_effect=RuntimeError("db connect failed")),
        patch("chronowarden.app.db.close") as mock_db_close,
    ):
        with pytest.raises(RuntimeError, match="db connect failed"):
            async with lifespan(FastAPI()):
                pass

    mock_db_close.assert_called_once_with()
    mock_disconnect_all.assert_called_once_with()
