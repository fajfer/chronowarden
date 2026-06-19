# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for Vault manager behavior."""

from unittest.mock import MagicMock
from unittest.mock import patch

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
        vault.last_error = (
            "AppRole authentication failed: invalid role_id or secret_id "
            "(mount point 'chronowarden')"
        )

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
            "AppRole authentication failed: invalid role_id or secret_id "
            "(mount point 'chronowarden')"
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
