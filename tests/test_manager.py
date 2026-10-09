# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for Vault manager behavior."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from chronowarden.config import VaultConfig
from chronowarden.integrations.manager import VaultManager


class TestVaultManagerHealth:
    """Tests for VaultManager.health()."""

    def test_health_includes_last_error_when_disconnected(self) -> None:
        """Disconnected vaults include the latest connection error in health output."""
        manager = VaultManager()
        vault = MagicMock()
        vault.check_health.return_value = {"healthy": True, "version": "1.16.0"}
        vault.is_connected.return_value = False
        vault.last_error = "AppRole authentication failed: invalid role_id or secret_id " "(mount point 'chronowarden')"

        manager._vaults["dev-vault"] = vault

        health = manager.health()

        assert health["dev-vault"]["connected"] is False
        assert health["dev-vault"]["error"] == vault.last_error


class TestVaultManagerConnectionRetry:
    """Tests for VaultManager retry decisions after failed connects."""

    def test_auth_failure_is_not_added_to_pending_retries(self) -> None:
        """Auth failures should require config fix and not auto-retry indefinitely."""
        manager = VaultManager()
        vault_config = VaultConfig(
            name="dev-vault",
            address="http://localhost:8202",
            auth_method="approle",
            role_id="rid",
            secret_id="sid",
        )

        integration = MagicMock()
        integration.connect.return_value = False
        integration.last_error_kind = "auth"
        integration.last_error = (
            "AppRole authentication failed: invalid role_id or secret_id " "(mount point 'chronowarden')"
        )

        with patch("chronowarden.integrations.manager.VaultIntegration", return_value=integration):
            manager._connect_vault(vault_config)

        assert manager.get("dev-vault") is integration
        assert "dev-vault" not in manager._pending_configs

    def test_offline_failure_is_added_to_pending_retries(self) -> None:
        """Offline failures should stay queued for reconnect attempts."""
        manager = VaultManager()
        vault_config = VaultConfig(
            name="dev-vault",
            address="http://localhost:8202",
            auth_method="approle",
            role_id="rid",
            secret_id="sid",
        )

        integration = MagicMock()
        integration.connect.return_value = False
        integration.last_error_kind = "offline"
        integration.last_error = "Vault at http://localhost:8202 appears to be offline"

        with patch("chronowarden.integrations.manager.VaultIntegration", return_value=integration):
            manager._connect_vault(vault_config)

        assert manager.get("dev-vault") is integration
        assert manager._pending_configs["dev-vault"] == vault_config


class TestVaultManagerDisconnectedReconnect:
    """Tests for reconnecting vaults that lose authentication after startup."""

    def test_disconnected_vault_is_reauthenticated(self) -> None:
        """A disconnected vault outside pending queue is re-authenticated."""
        manager = VaultManager()
        integration = MagicMock()
        integration.is_connected.return_value = False
        integration.connect.return_value = True

        manager._vaults["dev-vault"] = integration

        manager._reconnect_disconnected_vaults()

        integration.connect.assert_called_once_with()

    def test_connected_vault_is_not_reauthenticated(self) -> None:
        """A healthy vault is skipped by disconnected reconnect pass."""
        manager = VaultManager()
        integration = MagicMock()
        integration.is_connected.return_value = True

        manager._vaults["dev-vault"] = integration

        manager._reconnect_disconnected_vaults()

        integration.connect.assert_not_called()

    def test_pending_vault_is_handled_by_pending_retry_path(self) -> None:
        """Vaults already queued as pending are skipped by disconnected pass."""
        manager = VaultManager()
        integration = MagicMock()
        integration.is_connected.return_value = False
        integration.connect.return_value = True
        vault_config = VaultConfig(
            name="dev-vault",
            address="http://localhost:8202",
            auth_method="approle",
            role_id="rid",
            secret_id="sid",
        )

        manager._vaults["dev-vault"] = integration
        manager._pending_configs["dev-vault"] = vault_config

        manager._reconnect_disconnected_vaults()

        integration.connect.assert_not_called()


class TestVaultManagerReconnectLoop:
    """Tests for bounded reconnect loop behavior."""

    def test_reconnect_loop_stops_after_configured_attempts(self) -> None:
        """Reconnect loop exits after reaching configured max attempts."""
        manager = VaultManager()
        manager._reconnect_interval = 1
        manager._reconnect_max_attempts = 3
        manager._retry_pending_vaults = MagicMock()
        manager._reconnect_disconnected_vaults = MagicMock()

        async def _run_loop() -> None:
            with patch("chronowarden.integrations.manager.asyncio.sleep", new=AsyncMock()):
                await manager._reconnect_loop()

        asyncio.run(_run_loop())

        assert manager._reconnect_attempts == 3
        assert manager._retry_pending_vaults.call_count == 3
        assert manager._reconnect_disconnected_vaults.call_count == 3
        assert manager._reconnect_task is None

    def test_start_reconnect_loop_can_restart_after_exhaustion(self) -> None:
        """A new loop can be started after a previous one exhausted max attempts."""
        manager = VaultManager()
        manager._reconnect_interval = 1
        manager._reconnect_max_attempts = 1
        manager._retry_pending_vaults = MagicMock()
        manager._reconnect_disconnected_vaults = MagicMock()

        async def _run_restart() -> None:
            with patch("chronowarden.integrations.manager.asyncio.sleep", new=AsyncMock()):
                manager.start_reconnect_loop()
                first_task = manager._reconnect_task
                assert first_task is not None
                await first_task

                assert manager._reconnect_task is None

                manager.start_reconnect_loop()
                second_task = manager._reconnect_task
                assert second_task is not None
                assert second_task is not first_task
                await second_task

        asyncio.run(_run_restart())

        assert manager._retry_pending_vaults.call_count == 2
        assert manager._reconnect_disconnected_vaults.call_count == 2


class TestVaultManagerReconnect:
    """Tests for single reconnect attempts, sync locks and the reconnect callback (#59)."""

    def _manager_with(self, connect_ok: bool, error_kind: str = "offline") -> tuple[VaultManager, MagicMock]:
        """Build a manager with one pending vault whose connect() succeeds or fails."""
        manager = VaultManager()
        integration = MagicMock()
        integration.connect.return_value = connect_ok
        integration.last_error_kind = None if connect_ok else error_kind
        manager._vaults["v"] = integration
        manager._pending_configs["v"] = VaultConfig(name="v", address="http://x", token="t")
        return manager, integration

    def test_reconnect_success_clears_pending(self) -> None:
        """A successful reconnect removes the vault from the retry queue."""
        manager, _ = self._manager_with(connect_ok=True)
        assert manager.reconnect("v") is True
        assert "v" not in manager._pending_configs

    def test_reconnect_offline_keeps_pending(self) -> None:
        """An offline vault stays queued for background retries."""
        manager, _ = self._manager_with(connect_ok=False, error_kind="offline")
        assert manager.reconnect("v") is False
        assert "v" in manager._pending_configs

    def test_reconnect_auth_failure_stops_retries(self) -> None:
        """An auth failure removes the vault from background retries."""
        manager, _ = self._manager_with(connect_ok=False, error_kind="auth")
        assert manager.reconnect("v") is False
        assert "v" not in manager._pending_configs

    def test_reconnect_unknown_vault(self) -> None:
        """An unknown vault can't be reconnected."""
        assert VaultManager().reconnect("missing") is False

    def test_sync_lock_is_per_vault(self) -> None:
        """Each vault has exactly one lock, distinct from other vaults."""
        manager = VaultManager()
        assert manager.sync_lock("a") is manager.sync_lock("a")
        assert manager.sync_lock("a") is not manager.sync_lock("b")

    def test_loop_calls_callback_once_per_reconnected_vault(self) -> None:
        """After a reconnect the loop calls the callback for exactly that vault."""
        manager, _ = self._manager_with(connect_ok=True)
        manager._reconnect_max_attempts = 1
        manager._reconnect_interval = 0
        callback = AsyncMock()
        manager.set_reconnect_callback(callback)

        with patch("chronowarden.integrations.manager.asyncio.sleep", new=AsyncMock()):
            asyncio.run(manager._reconnect_loop())

        callback.assert_awaited_once_with("v")

    def test_callback_failure_does_not_stop_the_loop(self) -> None:
        """An exception in the callback is logged and the loop completes."""
        manager, _ = self._manager_with(connect_ok=True)
        manager._reconnect_max_attempts = 1
        manager.set_reconnect_callback(AsyncMock(side_effect=RuntimeError("sync failed")))

        with patch("chronowarden.integrations.manager.asyncio.sleep", new=AsyncMock()):
            asyncio.run(manager._reconnect_loop())

        assert manager._reconnect_task is None
