# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""HashiCorp Vault integration for Chronowarden."""

import logging
from typing import Any, Optional

import hvac
from hvac.exceptions import InvalidPath, VaultError

from chronowarden.integrations.base import BaseIntegration

logger = logging.getLogger(__name__)


class VaultIntegration(BaseIntegration):
    """Integration with HashiCorp Vault for secret management."""

    def __init__(
        self,
        address: str,
        token: Optional[str] = None,
        namespace: Optional[str] = None,
        mount_path: str = "secret",
        verify_ssl: bool = True,
        ca_bundle: Optional[str] = None,
        auth_method: str = "token",
        role_id: Optional[str] = None,
        secret_id: Optional[str] = None,
        approle_mount_point: str = "approle",
    ) -> None:
        """
        Initialize Vault integration.

        Args:
            address: Vault server address (e.g., https://vault.example.com:8200).
            token: Vault authentication token.
            namespace: Vault namespace (enterprise feature).
            mount_path: KV secrets engine mount path.
            verify_ssl: Whether to verify SSL certificates.
            ca_bundle: Path to CA certificate bundle file (if global certs configured).
            auth_method: Authentication method ('token' or 'approle').
            role_id: AppRole role ID (when auth_method='approle').
            secret_id: AppRole secret ID (when auth_method='approle').
            approle_mount_point: AppRole auth method mount point (when auth_method='approle').
        """
        self._address = address
        self._token = token
        self._namespace = namespace
        self._mount_path = mount_path
        self._verify_ssl = verify_ssl
        self._ca_bundle = ca_bundle
        self._auth_method = auth_method
        self._role_id = role_id
        self._secret_id = secret_id
        self._approle_mount_point = approle_mount_point
        self._client: Optional[hvac.Client] = None

    def connect(self) -> bool:
        """
        Establish connection to Vault.

        Returns:
            bool: True if connection and authentication successful.
        """
        try:
            verify: bool | str = self._verify_ssl

            # Use global CA bundle if provided
            if self._verify_ssl and self._ca_bundle:
                verify = self._ca_bundle

            if self._auth_method == "approle":
                # Create unauthenticated client for AppRole login
                self._client = hvac.Client(
                    url=self._address,
                    namespace=self._namespace,
                    verify=verify,
                )

                response = self._client.auth.approle.login(
                    role_id=self._role_id,
                    secret_id=self._secret_id,
                    mount_point=self._approle_mount_point,
                )
                self._client.token = response["auth"]["client_token"]
                logger.info("Authenticated to Vault at %s using AppRole", self._address)
            else:
                # Token-based authentication
                self._client = hvac.Client(
                    url=self._address,
                    token=self._token,
                    namespace=self._namespace,
                    verify=verify,
                )

            if self._client.is_authenticated():
                logger.info("Successfully connected to Vault at %s", self._address)
                return True

            logger.warning("Vault connection established but authentication failed")
            return False
        except VaultError:
            logger.exception("Failed to connect to Vault")
            return False

    def disconnect(self) -> None:
        """Close connection to Vault."""
        if self._client is not None:
            self._client.adapter.close()
            self._client = None
            logger.info("Disconnected from Vault")

    def is_connected(self) -> bool:
        """
        Check if connected and authenticated to Vault.

        Returns:
            bool: True if connected and authenticated.
        """
        if self._client is None:
            return False
        try:
            return self._client.is_authenticated()
        except VaultError:
            logger.exception("Error checking Vault connection")
            return False

    def get_secret(
        self, path: str, key: Optional[str] = None, mount_point: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        """
        Retrieve a secret from Vault KV v2 engine.

        Args:
            path: Path to the secret within the mount point.
            key: Optional specific key to retrieve from the secret.
            mount_point: Override the default mount point for this request.

        Returns:
            The secret data dictionary or None if not found.
        """
        if not self._client:
            logger.error("Not connected to Vault")
            return None

        mount = mount_point if mount_point is not None else self._mount_path

        try:
            response = self._client.secrets.kv.v2.read_secret_version(
                path=path,
                mount_point=mount,
            )

            if response and "data" in response and "data" in response["data"]:
                data = response["data"]["data"]
                if key:
                    return {key: data.get(key)} if key in data else None
                return data

            return None
        except InvalidPath:
            logger.warning("Secret not found at path: %s", path)
            return None
        except VaultError:
            logger.exception("Error retrieving secret from Vault")
            return None

    def list_secrets(self, path: str, mount_point: Optional[str] = None) -> list[str]:
        """
        List secrets at the given path in Vault.

        Args:
            path: Path to list secrets from.
            mount_point: Override the default mount point for this request.

        Returns:
            List of secret names at the path.
        """
        if not self._client:
            logger.error("Not connected to Vault")
            return []

        mount = mount_point if mount_point is not None else self._mount_path

        try:
            response = self._client.secrets.kv.v2.list_secrets(
                path=path,
                mount_point=mount,
            )

            if response and "data" in response and "keys" in response["data"]:
                return response["data"]["keys"]

            return []
        except InvalidPath:
            if path == "":
                logger.warning("Secrets not found under mount_point %s", mount)
            else:
                logger.warning("Path not found: %s", path)
            return []
        except VaultError:
            logger.exception("Error listing secrets from Vault")
            return []

    def get_secret_metadata(self, path: str, mount_point: Optional[str] = None) -> Optional[dict[str, Any]]:
        """
        Get metadata about a secret from Vault.

        Args:
            path: Path to the secret.
            mount_point: Override the default mount point for this request.

        Returns:
            Metadata dictionary including creation_time, updated_time, version, etc.
        """
        if not self._client:
            logger.error("Not connected to Vault")
            return None

        mount = mount_point if mount_point is not None else self._mount_path

        try:
            response = self._client.secrets.kv.v2.read_secret_metadata(
                path=path,
                mount_point=mount,
            )

            if response and "data" in response:
                return response["data"]

            return None
        except InvalidPath:
            logger.warning("Secret metadata not found at path: %s", path)
            return None
        except VaultError:
            logger.exception("Error retrieving secret metadata from Vault")
            return None

    def check_health(self) -> dict[str, Any]:
        """
        Check Vault health status.

        Returns:
            Health status dictionary.
        """
        if not self._client:
            return {"healthy": False, "error": "Not connected"}

        try:
            health = self._client.sys.read_health_status(method="GET")
            return {
                "healthy": True,
                "initialized": health.get("initialized", False),
                "sealed": health.get("sealed", True),
                "version": health.get("version", "unknown"),
            }
        except VaultError:
            logger.exception("Error checking Vault health")
            return {"healthy": False, "error": "Health check failed"}

    def write_secret_metadata(
        self,
        path: str,
        custom_metadata: dict[str, str],
        mount_point: Optional[str] = None,
    ) -> bool:
        """
        Write custom metadata fields to a Vault secret.

        Args:
            path: Path to the secret.
            custom_metadata: Dictionary of custom metadata key-value pairs to write.
            mount_point: Override the default mount point for this request.

        Returns:
            True if metadata was written successfully, False otherwise.
        """
        if not self._client:
            logger.error("Not connected to Vault")
            return False

        mount = mount_point if mount_point is not None else self._mount_path

        try:
            self._client.secrets.kv.v2.update_metadata(
                path=path,
                mount_point=mount,
                custom_metadata=custom_metadata,
            )
            logger.debug("Updated custom metadata for %s/%s", mount, path)
            return True
        except VaultError:
            logger.exception("Error writing metadata to Vault")
            return False

    def discover_engines(self) -> list[dict[str, Any]]:
        """
        Auto-discover KV v2 secret engines from Vault.

        Returns:
            List of discovered engine dictionaries with 'path' and 'type' keys.
        """
        if not self._client:
            logger.error("Not connected to Vault")
            return []

        try:
            mounts = self._client.sys.list_mounted_secrets_engines()
            engines: list[dict[str, Any]] = []
            if mounts and "data" in mounts:
                mount_data = mounts["data"]
            elif isinstance(mounts, dict):
                mount_data = mounts
            else:
                return []

            for mount_path, details in mount_data.items():
                if not isinstance(details, dict):
                    continue
                engine_type = details.get("type", "")
                options = details.get("options", {}) or {}
                version = options.get("version", "")
                if engine_type == "kv" and version == "2":
                    engines.append(
                        {
                            "path": mount_path.rstrip("/"),
                            "type": "kv",
                            "version": "2",
                            "description": details.get("description", ""),
                        }
                    )
            return engines
        except VaultError:
            logger.exception("Error discovering secret engines")
            return []
