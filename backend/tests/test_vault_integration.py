# SPDX-FileCopyrightText: 2025 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Integration tests for HashiCorp Vault.

These tests require a running Vault instance. They are designed to run
in the docker-compose.test.yml environment which provides:
- A Vault server in dev mode
- Pre-seeded test secrets
- Network connectivity between services

Environment variables:
- VAULT_ADDR: Vault server address (default: http://vault:8200)
- VAULT_TOKEN: Vault authentication token (default: test-root-token)
- VAULT_MOUNT_PATH: KV secrets engine mount path (default: chronowarden)
"""

import os

import pytest

from chronowarden.integrations.vault import VaultIntegration

# Skip all tests in this module if VAULT_ADDR is not set
pytestmark = pytest.mark.skipif(
    os.environ.get("VAULT_ADDR") is None,
    reason="VAULT_ADDR environment variable not set - skipping Vault integration tests",
)


@pytest.fixture
def vault_config():
    """Get Vault configuration from environment."""
    return {
        "address": os.environ.get("VAULT_ADDR", "http://vault:8200"),
        "token": os.environ.get("VAULT_TOKEN", "test-root-token"),
        "mount_path": os.environ.get("VAULT_MOUNT_PATH", "chronowarden"),
    }


@pytest.fixture
def vault_integration(vault_config):
    """Create and connect a Vault integration instance."""
    integration = VaultIntegration(
        address=vault_config["address"],
        token=vault_config["token"],
        mount_path=vault_config["mount_path"],
        verify_ssl=False,  # Dev mode doesn't use SSL
    )
    yield integration
    integration.disconnect()


class TestVaultIntegrationConnection:
    """Tests for Vault connection handling."""

    def test_connect_success(self, vault_integration: VaultIntegration) -> None:
        """Test successful connection to Vault."""
        result = vault_integration.connect()
        assert result is True
        assert vault_integration.is_connected() is True

    def test_disconnect(self, vault_integration: VaultIntegration) -> None:
        """Test disconnection from Vault."""
        vault_integration.connect()
        vault_integration.disconnect()
        assert vault_integration.is_connected() is False

    def test_connect_with_invalid_token(self, vault_config) -> None:
        """Test connection failure with invalid token."""
        integration = VaultIntegration(
            address=vault_config["address"],
            token="invalid-token",
            mount_path=vault_config["mount_path"],
            verify_ssl=False,
        )
        result = integration.connect()
        # Connection may succeed but authentication will fail
        assert result is False or not integration.is_connected()


class TestVaultIntegrationSecrets:
    """Tests for Vault secret operations."""

    def test_get_secret(self, vault_integration: VaultIntegration) -> None:
        """Test retrieving a secret from Vault."""
        vault_integration.connect()

        # Get the test API key secret seeded by vault-init
        secret = vault_integration.get_secret("test/api-key")

        assert secret is not None
        assert "value" in secret
        assert secret["value"] == "test-api-key-12345"

    def test_get_secret_with_key(self, vault_integration: VaultIntegration) -> None:
        """Test retrieving a specific key from a secret."""
        vault_integration.connect()

        # Get only the username from database credentials
        secret = vault_integration.get_secret("test/database-credentials", key="username")

        assert secret is not None
        assert "username" in secret
        assert secret["username"] == "testuser"

    def test_get_nonexistent_secret(self, vault_integration: VaultIntegration) -> None:
        """Test retrieving a secret that doesn't exist."""
        vault_integration.connect()

        secret = vault_integration.get_secret("nonexistent/path")
        assert secret is None

    def test_list_secrets(self, vault_integration: VaultIntegration) -> None:
        """Test listing secrets at a path."""
        vault_integration.connect()

        secrets = vault_integration.list_secrets("test")

        assert isinstance(secrets, list)
        assert len(secrets) >= 1
        # Should contain our test secrets
        assert any("api-key" in s for s in secrets) or "api-key" in secrets

    def test_list_secrets_empty_path(self, vault_integration: VaultIntegration) -> None:
        """Test listing secrets at root path."""
        vault_integration.connect()

        secrets = vault_integration.list_secrets("")

        assert isinstance(secrets, list)
        # Root should have our test and production paths
        assert len(secrets) >= 1


class TestVaultIntegrationMetadata:
    """Tests for Vault secret metadata operations."""

    def test_get_secret_metadata(self, vault_integration: VaultIntegration) -> None:
        """Test retrieving secret metadata."""
        vault_integration.connect()

        metadata = vault_integration.get_secret_metadata("test/api-key")

        assert metadata is not None
        assert "created_time" in metadata or "current_version" in metadata
        # Vault KV v2 metadata should include version info

    def test_get_metadata_nonexistent(self, vault_integration: VaultIntegration) -> None:
        """Test retrieving metadata for nonexistent secret."""
        vault_integration.connect()

        metadata = vault_integration.get_secret_metadata("nonexistent/path")
        assert metadata is None


class TestVaultIntegrationHealth:
    """Tests for Vault health check operations."""

    def test_check_health_connected(self, vault_integration: VaultIntegration) -> None:
        """Test health check when connected."""
        vault_integration.connect()

        health = vault_integration.check_health()

        assert health["healthy"] is True
        assert "initialized" in health
        assert health["initialized"] is True
        assert "sealed" in health
        assert health["sealed"] is False  # Dev mode is never sealed
        assert "version" in health

    def test_check_health_not_connected(self, vault_config) -> None:
        """Test health check when not connected."""
        integration = VaultIntegration(
            address=vault_config["address"],
            token=vault_config["token"],
            mount_path=vault_config["mount_path"],
        )
        # Don't connect

        health = integration.check_health()

        assert health["healthy"] is False
        assert "error" in health


class TestVaultIntegrationEndToEnd:
    """End-to-end integration tests simulating real usage."""

    def test_full_secret_lifecycle(self, vault_integration: VaultIntegration) -> None:
        """Test a complete secret workflow: connect, list, read, check metadata."""
        # Connect
        assert vault_integration.connect() is True

        # List available secrets
        secrets = vault_integration.list_secrets("test")
        assert len(secrets) > 0

        # Read each secret
        for secret_path in secrets:
            full_path = f"test/{secret_path}" if not secret_path.endswith("/") else None
            if full_path:
                secret_data = vault_integration.get_secret(full_path)
                # Some paths might be directories
                if secret_data is not None:
                    assert isinstance(secret_data, dict)

        # Check health
        health = vault_integration.check_health()
        assert health["healthy"] is True

        # Disconnect
        vault_integration.disconnect()
        assert vault_integration.is_connected() is False

    def test_monitoring_workflow(self, vault_integration: VaultIntegration) -> None:
        """Test the monitoring workflow for secret expiration tracking.

        This simulates Chronowarden's core functionality of monitoring
        secrets for expiration dates.
        """
        vault_integration.connect()

        # Get secrets with expiry dates
        secrets_to_monitor = [
            "test/api-key",
            "test/database-credentials",
            "test/certificate",
            "production/critical-secret",
        ]

        expiring_soon = []
        for secret_path in secrets_to_monitor:
            secret = vault_integration.get_secret(secret_path)
            if secret and "expiry_date" in secret:
                expiring_soon.append(
                    {
                        "path": secret_path,
                        "expiry_date": secret["expiry_date"],
                        "description": secret.get("description", ""),
                    }
                )

        # Should have found secrets with expiry dates
        assert len(expiring_soon) > 0

        # All should have valid expiry date strings
        for secret in expiring_soon:
            assert secret["expiry_date"] is not None
            assert "T" in secret["expiry_date"]  # ISO format
