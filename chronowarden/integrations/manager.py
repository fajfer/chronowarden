# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Vault connection manager for multiple Vault instances."""

import logging
from typing import Any, Optional

from chronowarden.config import AppConfig, VaultConfig
from chronowarden.integrations.vault import VaultIntegration
from chronowarden.metrics import INTEGRATION_HEALTH, VAULT_CONNECTIONS_TOTAL

logger = logging.getLogger(__name__)


class VaultManager:
    """Manages connections to multiple Vault instances defined by configuration."""

    def __init__(self) -> None:
        """Initialize the Vault manager with empty connections."""
        self._vaults: dict[str, VaultIntegration] = {}

    @property
    def vault_names(self) -> list[str]:
        """Return names of all registered vault instances."""
        return list(self._vaults.keys())

    def get(self, name: str) -> Optional[VaultIntegration]:
        """
        Get a vault integration by name.

        Args:
            name: The configured vault name.

        Returns:
            The VaultIntegration instance, or None if not found.
        """
        return self._vaults.get(name)

    def connect_all(self, config: AppConfig) -> None:
        """
        Connect to all vault instances defined in the configuration.

        Args:
            config: Application configuration containing vault definitions.
        """
        for vault_config in config.vaults:
            self._connect_vault(vault_config)

    def disconnect_all(self) -> None:
        """Disconnect from all vault instances."""
        for name in list(self._vaults.keys()):
            self._disconnect_vault(name)

    def health(self) -> dict[str, dict[str, Any]]:
        """
        Check health of all connected vault instances.

        Returns:
            Dictionary mapping vault names to their health status.
        """
        result: dict[str, dict[str, Any]] = {}
        for name, vault in self._vaults.items():
            health = vault.check_health()
            health["connected"] = vault.is_connected()
            result[name] = health
        return result

    def _connect_vault(self, vault_config: VaultConfig) -> None:
        """
        Connect to a single vault instance from config.

        Args:
            vault_config: Configuration for the vault instance.
        """
        token = vault_config.resolve_token()
        if token is None:
            logger.error("Cannot resolve token for vault '%s', skipping", vault_config.name)
            VAULT_CONNECTIONS_TOTAL.labels(status="failure").inc()
            INTEGRATION_HEALTH.labels(integration=f"vault:{vault_config.name}").set(0)
            return

        integration = VaultIntegration(
            address=vault_config.address,
            token=token,
            namespace=vault_config.namespace,
            mount_path=vault_config.mount_path,
            verify_ssl=vault_config.verify_ssl,
        )

        if integration.connect():
            self._vaults[vault_config.name] = integration
            VAULT_CONNECTIONS_TOTAL.labels(status="success").inc()
            INTEGRATION_HEALTH.labels(integration=f"vault:{vault_config.name}").set(1)
            logger.info("Connected to vault '%s' at %s", vault_config.name, vault_config.address)
        else:
            VAULT_CONNECTIONS_TOTAL.labels(status="failure").inc()
            INTEGRATION_HEALTH.labels(integration=f"vault:{vault_config.name}").set(0)
            logger.error("Failed to connect to vault '%s' at %s", vault_config.name, vault_config.address)

    def _disconnect_vault(self, name: str) -> None:
        """
        Disconnect a single vault instance by name.

        Args:
            name: The vault instance name.
        """
        vault = self._vaults.pop(name, None)
        if vault:
            vault.disconnect()
            INTEGRATION_HEALTH.labels(integration=f"vault:{name}").set(0)
            logger.info("Disconnected from vault '%s'", name)
