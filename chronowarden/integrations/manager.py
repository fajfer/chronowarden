# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Vault connection manager for multiple Vault instances."""

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Any, Optional

from chronowarden.config import AppConfig, VaultConfig
from chronowarden.integrations.vault import VaultIntegration
from chronowarden.metrics import INTEGRATION_HEALTH, VAULT_CONNECTIONS_TOTAL

logger = logging.getLogger("uvicorn.error")

_DEFAULT_RECONNECT_INTERVAL_SECONDS = 120
_DEFAULT_RECONNECT_MAX_ATTEMPTS = 5


class VaultManager:
    """Manages connections to multiple Vault instances defined by configuration."""

    def __init__(self) -> None:
        """Initialize the Vault manager with empty connections."""
        self._vaults: dict[str, VaultIntegration] = {}
        self._ca_bundle_path: Optional[str] = None
        self._pending_configs: dict[str, VaultConfig] = {}
        self._reconnect_task: Optional[asyncio.Task[None]] = None
        self._reconnect_interval: int = _DEFAULT_RECONNECT_INTERVAL_SECONDS
        self._reconnect_max_attempts: int = _DEFAULT_RECONNECT_MAX_ATTEMPTS
        self._reconnect_attempts: int = 0

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
        # Create global CA bundle if directory is configured
        if config.ca_certs_dir:
            self._ca_bundle_path = self._create_ca_bundle(config.ca_certs_dir)

        self._reconnect_interval = config.vault_reconnect_interval
        self._reconnect_max_attempts = config.vault_reconnect_max_attempts

        for vault_config in config.vaults:
            self._connect_vault(vault_config)

    def disconnect_all(self) -> None:
        """Disconnect from all vault instances and stop reconnection loop."""
        self.stop_reconnect_loop()
        for name in list(self._vaults.keys()):
            self._disconnect_vault(name)
        self._pending_configs.clear()

    def health(self) -> dict[str, dict[str, Any]]:
        """
        Check health of all connected vault instances.

        Returns:
            Dictionary mapping vault names to their health status.
        """
        result: dict[str, dict[str, Any]] = {}
        for name, vault in self._vaults.items():
            health = vault.check_health()
            logger.debug(health)
            connected = vault.is_connected()
            health["connected"] = connected
            if not connected and vault.last_error is not None:
                health["error"] = vault.last_error
            result[name] = health
        return result

    def _create_ca_bundle(self, certs_dir: str) -> Optional[str]:
        """
        Create a CA bundle from all certificates in the specified directory.

        Args:
            certs_dir: Path to directory containing certificate files.

        Returns:
            Path to the created CA bundle file, or None if no valid certs found.
        """
        cert_dir = Path(certs_dir)
        if not cert_dir.is_dir():
            logger.warning("CA certs directory does not exist: %s", certs_dir)
            return None

        # Find all certificate files
        cert_files = []
        for pattern in ["*.pem", "*.crt", "*.cert"]:
            cert_files.extend(cert_dir.glob(pattern))

        if not cert_files:
            logger.warning("No certificate files found in %s", certs_dir)
            return None

        # Load all certificates
        bundle_content = []
        for cert_file in cert_files:
            try:
                content = cert_file.read_text()
                bundle_content.append(content)
                logger.info("Loaded CA certificate: %s", cert_file.name)
            except OSError:
                logger.exception("Failed to read certificate file: %s", cert_file)

        if not bundle_content:
            logger.warning("No valid certificates loaded from %s", certs_dir)
            return None

        # Create temporary bundle file
        try:
            fd, bundle_path = tempfile.mkstemp(suffix=".pem", prefix="chronowarden-ca-")
            with open(fd, "w") as f:
                f.write("\n\n".join(bundle_content))
            logger.info(
                "Created global CA bundle with %d certificate(s) from %s: %s",
                len(bundle_content),
                certs_dir,
                bundle_path,
            )
            return bundle_path
        except OSError:
            logger.exception("Failed to create CA bundle file")
            return None

    def _connect_vault(self, vault_config: VaultConfig) -> None:
        """
        Connect to a single vault instance from config.

        Args:
            vault_config: Configuration for the vault instance.
        """
        if vault_config.auth_method == "approle":
            role_id = vault_config.resolve_role_id()
            secret_id = vault_config.resolve_secret_id()
            if role_id is None:
                logger.error("Cannot resolve role_id for vault '%s', skipping", vault_config.name)
                VAULT_CONNECTIONS_TOTAL.labels(status="failure").inc()
                INTEGRATION_HEALTH.labels(integration=f"vault:{vault_config.name}").set(0)
                return
            if secret_id is None:
                logger.error("Cannot resolve secret_id for vault '%s', skipping", vault_config.name)
                VAULT_CONNECTIONS_TOTAL.labels(status="failure").inc()
                INTEGRATION_HEALTH.labels(integration=f"vault:{vault_config.name}").set(0)
                return

            integration = VaultIntegration(
                address=vault_config.address,
                namespace=vault_config.namespace,
                mount_path=vault_config.mount_path,
                verify_ssl=vault_config.verify_ssl,
                ca_bundle=self._ca_bundle_path,
                auth_method="approle",
                role_id=role_id,
                secret_id=secret_id,
                approle_mount_point=vault_config.approle_mount_point,
            )
        else:
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
                ca_bundle=self._ca_bundle_path,
            )

        if integration.connect():
            self._vaults[vault_config.name] = integration
            self._pending_configs.pop(vault_config.name, None)
            VAULT_CONNECTIONS_TOTAL.labels(status="success").inc()
            INTEGRATION_HEALTH.labels(integration=f"vault:{vault_config.name}").set(1)
            logger.info("Connected to vault '%s' at %s", vault_config.name, vault_config.address)
        else:
            self._vaults[vault_config.name] = integration
            VAULT_CONNECTIONS_TOTAL.labels(status="failure").inc()
            INTEGRATION_HEALTH.labels(integration=f"vault:{vault_config.name}").set(0)
            reason = integration.last_error or "unknown connection failure"
            if integration.last_error_kind == "auth":
                self._pending_configs.pop(vault_config.name, None)
                logger.error(
                    "Vault '%s' at %s authentication failed and will not be retried automatically: %s",
                    vault_config.name,
                    vault_config.address,
                    reason,
                )
            elif integration.last_error_kind == "offline":
                self._pending_configs[vault_config.name] = vault_config
                logger.warning(
                    "Vault '%s' at %s appears to be offline, will retry every %d seconds",
                    vault_config.name,
                    vault_config.address,
                    self._reconnect_interval,
                )
            else:
                self._pending_configs[vault_config.name] = vault_config
                logger.warning(
                    "Vault '%s' at %s connection failed, will retry every %d seconds: %s",
                    vault_config.name,
                    vault_config.address,
                    self._reconnect_interval,
                    reason,
                )

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

    def start_reconnect_loop(self) -> None:
        """Start an async background task that retries offline and disconnected vaults."""
        if self._reconnect_task is not None:
            if self._reconnect_task.done():
                self._reconnect_task = None
            else:
                return

        self._reconnect_attempts = 0
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())
        logger.info(
            "Vault reconnection loop started (interval=%ds, max_attempts=%d)",
            self._reconnect_interval,
            self._reconnect_max_attempts,
        )

    def restart_reconnect_loop(self) -> None:
        """Restart the reconnect background loop and reset retry attempts."""
        self.stop_reconnect_loop()
        self.start_reconnect_loop()

    def stop_reconnect_loop(self) -> None:
        """Cancel the reconnection background task."""
        if self._reconnect_task is not None:
            self._reconnect_task.cancel()
            self._reconnect_task = None
            logger.info("Vault reconnection loop stopped")
        self._reconnect_attempts = 0

    def _retry_pending_vaults(self) -> None:
        """Retry vaults that failed initial connection and were queued for reconnect."""
        if not self._pending_configs:
            return

        pending_names = list(self._pending_configs.keys())
        logger.info("Attempting to reconnect %d offline vault(s): %s", len(pending_names), pending_names)

        for name in pending_names:
            vault_config = self._pending_configs.get(name)
            if vault_config is None:
                continue
            integration = self._vaults.get(name)
            if integration is None:
                continue

            if integration.connect():
                self._pending_configs.pop(name, None)
                VAULT_CONNECTIONS_TOTAL.labels(status="success").inc()
                INTEGRATION_HEALTH.labels(integration=f"vault:{name}").set(1)
                logger.info("Reconnected to vault '%s' at %s", name, vault_config.address)
                continue

            reason = integration.last_error or "unknown connection failure"
            if integration.last_error_kind == "auth":
                self._pending_configs.pop(name, None)
                logger.error(
                    "Vault '%s' at %s authentication failed during reconnect and retries were stopped: %s",
                    name,
                    vault_config.address,
                    reason,
                )
            elif integration.last_error_kind == "offline":
                logger.warning("Vault '%s' at %s is still offline", name, vault_config.address)
            else:
                logger.warning(
                    "Vault '%s' at %s is still unavailable: %s",
                    name,
                    vault_config.address,
                    reason,
                )

    def _reconnect_disconnected_vaults(self) -> None:
        """Reconnect vaults that were connected previously but later lost authentication."""
        for name, integration in self._vaults.items():
            if name in self._pending_configs:
                continue
            if integration.is_connected():
                continue

            reason = integration.last_error or "unknown disconnection"
            logger.warning(
                "Vault '%s' is disconnected, attempting re-authentication (reason: %s)",
                name,
                reason,
            )

            if integration.connect():
                VAULT_CONNECTIONS_TOTAL.labels(status="success").inc()
                INTEGRATION_HEALTH.labels(integration=f"vault:{name}").set(1)
                logger.info("Re-authenticated vault '%s'", name)
                continue

            INTEGRATION_HEALTH.labels(integration=f"vault:{name}").set(0)
            reason = integration.last_error or "unknown connection failure"
            if integration.last_error_kind == "offline":
                logger.warning("Vault '%s' appears offline during re-authentication", name)
            elif integration.last_error_kind == "auth":
                logger.error("Vault '%s' re-authentication failed: %s", name, reason)
            else:
                logger.warning("Vault '%s' re-authentication failed: %s", name, reason)

    async def _reconnect_loop(self) -> None:
        """Retry offline/disconnected vaults until max attempts are exhausted or loop is cancelled."""
        try:
            while self._reconnect_attempts < self._reconnect_max_attempts:
                await asyncio.sleep(self._reconnect_interval)
                self._retry_pending_vaults()
                self._reconnect_disconnected_vaults()
                self._reconnect_attempts += 1
        finally:
            self._reconnect_task = None

        logger.warning(
            "Vault reconnection loop exhausted %d attempt(s) and stopped; trigger sync to restart",
            self._reconnect_max_attempts,
        )
