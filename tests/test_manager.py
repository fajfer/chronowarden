# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for Vault manager behavior."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chronowarden.config import VaultConfig
from chronowarden.integrations import BaseIntegration, VaultIntegration, provider_types, register_provider
from chronowarden.integrations.manager import ProviderManager


class TestProviderManagerHealth:
    """Tests for ProviderManager.health()."""

    def test_health_includes_last_error_when_disconnected(self) -> None:
        """Disconnected vaults include the latest connection error in health output."""
        manager = ProviderManager()
        vault = MagicMock()
        vault.check_health.return_value = {"healthy": True, "version": "1.16.0"}
        vault.is_connected.return_value = False
        vault.last_error = "AppRole authentication failed: invalid role_id or secret_id " "(mount point 'chronowarden')"

        manager._vaults["dev-vault"] = vault

        health = manager.health()

        assert health["dev-vault"]["connected"] is False
        assert health["dev-vault"]["error"] == vault.last_error


class TestProviderManagerConnectionRetry:
    """Tests for ProviderManager retry decisions after failed connects."""

    def test_auth_failure_is_not_added_to_pending_retries(self) -> None:
        """Auth failures should require config fix and not auto-retry indefinitely."""
        manager = ProviderManager()
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

        with patch("chronowarden.integrations.manager.build_provider", return_value=integration):
            manager._connect_vault(vault_config)

        assert manager.get("dev-vault") is integration
        assert "dev-vault" not in manager._pending_configs

    def test_offline_failure_is_added_to_pending_retries(self) -> None:
        """Offline failures should stay queued for reconnect attempts."""
        manager = ProviderManager()
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

        with patch("chronowarden.integrations.manager.build_provider", return_value=integration):
            manager._connect_vault(vault_config)

        assert manager.get("dev-vault") is integration
        assert manager._pending_configs["dev-vault"] == vault_config


class TestProviderManagerDisconnectedReconnect:
    """Tests for reconnecting vaults that lose authentication after startup."""

    def test_disconnected_vault_is_reauthenticated(self) -> None:
        """A disconnected vault outside pending queue is re-authenticated."""
        manager = ProviderManager()
        integration = MagicMock()
        integration.is_connected.return_value = False
        integration.connect.return_value = True

        manager._vaults["dev-vault"] = integration

        manager._reconnect_disconnected_vaults()

        integration.connect.assert_called_once_with()

    def test_connected_vault_is_not_reauthenticated(self) -> None:
        """A healthy vault is skipped by disconnected reconnect pass."""
        manager = ProviderManager()
        integration = MagicMock()
        integration.is_connected.return_value = True

        manager._vaults["dev-vault"] = integration

        manager._reconnect_disconnected_vaults()

        integration.connect.assert_not_called()

    def test_pending_vault_is_handled_by_pending_retry_path(self) -> None:
        """Vaults already queued as pending are skipped by disconnected pass."""
        manager = ProviderManager()
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


class TestProviderManagerReconnectLoop:
    """Tests for bounded reconnect loop behavior."""

    def test_reconnect_loop_stops_after_configured_attempts(self) -> None:
        """Reconnect loop exits after reaching configured max attempts."""
        manager = ProviderManager()
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
        manager = ProviderManager()
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


class TestProviderManagerReconnect:
    """Tests for single reconnect attempts, sync locks and the reconnect callback (#59)."""

    def _manager_with(self, connect_ok: bool, error_kind: str = "offline") -> tuple[ProviderManager, MagicMock]:
        """Build a manager with one pending vault whose connect() succeeds or fails."""
        manager = ProviderManager()
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
        assert ProviderManager().reconnect("missing") is False

    def test_sync_lock_is_per_vault(self) -> None:
        """Each vault has exactly one lock, distinct from other vaults."""
        manager = ProviderManager()
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


class TestProviderManagerBuildIntegration:
    """Tests for building an integration from a vault's credentials (the `vault` provider builder, ADR-011)."""

    def test_token_and_approle_credentials_are_passed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CW_TEST_TOKEN", "t")
        token = VaultIntegration.from_config(
            VaultConfig(name="a", address="http://v:8200", token_env="CW_TEST_TOKEN"), "/ca.pem"
        )
        assert token is not None and (token._token, token._auth_method, token._ca_bundle) == ("t", "token", "/ca.pem")
        approle = VaultIntegration.from_config(
            VaultConfig(name="b", address="http://v:8200", auth_method="approle", role_id="r", secret_id="s"), None
        )
        assert approle is not None and (approle._auth_method, approle._role_id, approle._secret_id) == (
            "approle",
            "r",
            "s",
        )

    def test_the_manager_builds_by_type(self) -> None:
        assert "vault" in provider_types()
        with patch("chronowarden.integrations.manager.build_provider", return_value=None) as build:
            manager = ProviderManager()
            manager._connect_vault(VaultConfig(name="a", address="http://v:8200", token="t"))
        assert build.call_args.args[0].type == "vault" and manager.get("a") is None

    def test_unresolved_credential_skips_the_vault(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CW_TEST_SECRET_ID", raising=False)
        manager = ProviderManager()
        config = VaultConfig(
            name="c", address="http://v:8200", auth_method="approle", role_id="r", secret_id_env="CW_TEST_SECRET_ID"
        )
        with patch.object(VaultIntegration, "connect") as connect:
            manager._connect_vault(config)
        connect.assert_not_called()
        assert manager.get("c") is None and "c" not in manager._pending_configs


class TestRegistry:
    """The provider interface and registry (ADR-011)."""

    def test_an_incomplete_provider_cannot_be_instantiated(self) -> None:
        class Incomplete(BaseIntegration):
            def connect(self) -> bool:
                return True

        with pytest.raises(TypeError, match="abstract"):
            Incomplete()  # type: ignore[abstract]

    def test_types_register_once(self) -> None:
        with pytest.raises(ValueError, match="registered already"):
            register_provider("vault", lambda config, ca: None)
