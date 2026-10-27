# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for application lifespan startup and shutdown cleanup."""

from unittest.mock import patch

import pytest
from fastapi import FastAPI

from chronowarden.app import lifespan
from chronowarden.config import AppConfig, AuthConfig, ConfigError

_TRUSTED = AppConfig(auth=AuthConfig(mode="none"))


@pytest.mark.asyncio
async def test_lifespan_runs_cleanup_on_normal_shutdown() -> None:
    """Lifespan should close DB and disconnect vaults on normal shutdown."""
    with (
        patch("chronowarden.app.load_config", return_value=_TRUSTED),
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
        patch("chronowarden.app.load_config", return_value=_TRUSTED),
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


@pytest.mark.asyncio
async def test_lifespan_registers_sync_after_reconnect() -> None:
    """Startup registers the callback that syncs a vault after a background reconnect (#59)."""
    from chronowarden.app import _sync_after_reconnect

    with (
        patch("chronowarden.app.load_config", return_value=_TRUSTED),
        patch("chronowarden.app._configure_sentry"),
        patch("chronowarden.app.vault_manager.connect_all"),
        patch("chronowarden.app.vault_manager.start_reconnect_loop"),
        patch("chronowarden.app.vault_manager.set_reconnect_callback") as mock_set_callback,
        patch("chronowarden.app.vault_manager.disconnect_all"),
        patch("chronowarden.app.db.connect"),
        patch("chronowarden.app.db.close"),
    ):
        async with lifespan(FastAPI()):
            pass

    mock_set_callback.assert_called_once_with(_sync_after_reconnect)


@pytest.mark.asyncio
async def test_lifespan_refuses_to_start_without_auth() -> None:
    """Without an auth section the server stops before it connects to anything (ADR-015)."""
    with (
        patch("chronowarden.app.load_config", return_value=AppConfig()),
        patch("chronowarden.app._configure_sentry"),
        patch("chronowarden.app.vault_manager.connect_all") as mock_connect_all,
        patch("chronowarden.app.vault_manager.disconnect_all"),
        patch("chronowarden.app.db.connect"),
        patch("chronowarden.app.db.close"),
    ):
        with pytest.raises(ConfigError, match="auth.mode"):
            async with lifespan(FastAPI()):
                pass

    mock_connect_all.assert_not_called()
