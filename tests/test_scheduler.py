# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for the scheduled sync (#74, ADR-013)."""

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI

from chronowarden.app import lifespan
from chronowarden.config import AppConfig, AuthConfig
from chronowarden.scheduler import SyncScheduler, sync_connected


class FakeManager:
    """Vaults by name: True = connected, False = disconnected."""

    def __init__(self, **connected: bool) -> None:
        self._vaults = {name: SimpleNamespace(is_connected=lambda c=c: c) for name, c in connected.items()}

    @property
    def vault_names(self) -> list[str]:
        return list(self._vaults)

    def get(self, name: str) -> Any:
        return self._vaults.get(name)


@pytest.mark.asyncio
async def test_sync_connected_skips_disconnected_and_survives_a_failure() -> None:
    manager = FakeManager(prod=True, dev=False, broken=True)

    async def fake_sync(_manager: Any, name: str, _config: Any, _db: Any) -> list[int]:
        if name == "broken":
            raise RuntimeError("backend exploded")
        return [1, 2, 3]

    with patch("chronowarden.scheduler.sync_vault_now", side_effect=fake_sync) as sync:
        results = await sync_connected(manager, AppConfig(), MagicMock())
    assert results == {"prod": 3, "dev": None, "broken": None}
    assert [call.args[1] for call in sync.call_args_list] == ["prod", "broken"]


@pytest.mark.asyncio
async def test_scheduler_syncs_after_startup_then_stops() -> None:
    config = AppConfig(polling_interval="1h")
    with patch("chronowarden.scheduler.sync_connected", new=AsyncMock(return_value={"prod": 2})) as sync:
        scheduler = SyncScheduler(MagicMock(), config, MagicMock(), startup_delay=0)
        scheduler.start()
        for _ in range(5):
            await asyncio.sleep(0)
        assert sync.await_count == 1, "the first sync runs right after the startup delay, the next one in an hour"
        task = scheduler._task
        scheduler.stop()
        await asyncio.sleep(0)
    assert task is not None and task.cancelled()


@pytest.mark.asyncio
async def test_off_starts_nothing() -> None:
    scheduler = SyncScheduler(MagicMock(), AppConfig(polling_interval="off"), MagicMock())
    scheduler.start()
    assert scheduler._task is None
    scheduler.stop()


@pytest.mark.asyncio
async def test_lifespan_starts_and_stops_the_scheduler() -> None:
    with (
        patch("chronowarden.app.load_config", return_value=AppConfig(auth=AuthConfig(mode="none"))),
        patch("chronowarden.app._configure_sentry"),
        patch("chronowarden.app.vault_manager.connect_all"),
        patch("chronowarden.app.vault_manager.start_reconnect_loop"),
        patch("chronowarden.app.vault_manager.disconnect_all"),
        patch("chronowarden.app.db.connect"),
        patch("chronowarden.app.db.close"),
        patch("chronowarden.app.record_config_change"),
        patch("chronowarden.app.SyncScheduler") as scheduler_class,
    ):
        async with lifespan(FastAPI()):
            scheduler_class.return_value.start.assert_called_once_with()
    scheduler_class.return_value.stop.assert_called_once_with()
