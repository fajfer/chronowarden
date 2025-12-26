# SPDX-FileCopyrightText: 2025 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for Azure Key Vault integration.

These tests include both unit tests (with mocking) and integration tests
(requiring Azure credentials). Integration tests are skipped unless
AZURE_KEYVAULT_URL is set.

For local testing with Azure:
- Set AZURE_KEYVAULT_URL to your vault URL
- Ensure you're logged in with `az login` or have appropriate credentials
"""

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from chronowarden.integrations.azure_keyvault import (
    AzureKeyVaultIntegration,
    CertificateExpiryInfo,
    SecretExpiryInfo,
)


class TestAzureKeyVaultUnitTests:
    """Unit tests for Azure Key Vault integration using mocks."""

    @pytest.fixture
    def mock_secret_client(self):
        """Create a mock SecretClient."""
        return MagicMock()

    @pytest.fixture
    def mock_certificate_client(self):
        """Create a mock CertificateClient."""
        return MagicMock()

    @pytest.fixture
    def integration(self):
        """Create an Azure Key Vault integration instance."""
        return AzureKeyVaultIntegration(
            vault_url="https://test-vault.vault.azure.net/",
            expiry_alert_days=30,
        )

    def test_init(self, integration: AzureKeyVaultIntegration) -> None:
        """Test initialization of Azure Key Vault integration."""
        assert integration._vault_url == "https://test-vault.vault.azure.net/"
        assert integration._expiry_alert_days == 30
        assert integration._connected is False

    def test_is_connected_false_initially(self, integration: AzureKeyVaultIntegration) -> None:
        """Test that integration is not connected initially."""
        assert integration.is_connected() is False

    def test_check_health_not_connected(self, integration: AzureKeyVaultIntegration) -> None:
        """Test health check when not connected."""
        health = integration.check_health()
        assert health["healthy"] is False
        assert health["error"] == "Not connected"

    def test_list_secrets_not_connected(self, integration: AzureKeyVaultIntegration) -> None:
        """Test listing secrets when not connected."""
        secrets = integration.list_secrets()
        assert secrets == []

    def test_get_secret_not_connected(self, integration: AzureKeyVaultIntegration) -> None:
        """Test getting a secret when not connected."""
        secret = integration.get_secret("test-secret")
        assert secret is None

    def test_get_secret_metadata_not_connected(self, integration: AzureKeyVaultIntegration) -> None:
        """Test getting secret metadata when not connected."""
        metadata = integration.get_secret_metadata("test-secret")
        assert metadata is None

    def test_get_expiring_secrets_not_connected(self, integration: AzureKeyVaultIntegration) -> None:
        """Test getting expiring secrets when not connected."""
        expiring = integration.get_expiring_secrets()
        assert expiring == []

    def test_list_certificates_not_connected(self, integration: AzureKeyVaultIntegration) -> None:
        """Test listing certificates when not connected."""
        certs = integration.list_certificates()
        assert certs == []

    def test_get_expiring_certificates_not_connected(self, integration: AzureKeyVaultIntegration) -> None:
        """Test getting expiring certificates when not connected."""
        expiring = integration.get_expiring_certificates()
        assert expiring == []

    @patch("azure.keyvault.certificates.CertificateClient")
    @patch("azure.keyvault.secrets.SecretClient")
    @patch("azure.identity.DefaultAzureCredential")
    def test_connect_success(
        self,
        mock_credential_class,
        mock_secret_client_class,
        mock_cert_client_class,
        integration: AzureKeyVaultIntegration,
    ) -> None:
        """Test successful connection to Azure Key Vault."""
        mock_secret_client = MagicMock()
        mock_secret_client.list_properties_of_secrets.return_value = iter([])
        mock_secret_client_class.return_value = mock_secret_client

        result = integration.connect()

        assert result is True
        assert integration._connected is True
        assert integration.is_connected() is True

    @patch("azure.keyvault.certificates.CertificateClient")
    @patch("azure.keyvault.secrets.SecretClient")
    @patch("azure.identity.DefaultAzureCredential")
    def test_connect_failure(
        self,
        mock_credential_class,
        mock_secret_client_class,
        mock_cert_client_class,
        integration: AzureKeyVaultIntegration,
    ) -> None:
        """Test connection failure to Azure Key Vault."""
        mock_secret_client = MagicMock()
        mock_secret_client.list_properties_of_secrets.side_effect = Exception("Connection failed")
        mock_secret_client_class.return_value = mock_secret_client

        result = integration.connect()

        assert result is False
        assert integration._connected is False

    def test_disconnect(self, integration: AzureKeyVaultIntegration) -> None:
        """Test disconnection from Azure Key Vault."""
        # Manually set connected state and clients
        integration._connected = True
        integration._secret_client = MagicMock()
        integration._certificate_client = MagicMock()

        integration.disconnect()

        assert integration._connected is False
        assert integration._secret_client is None
        assert integration._certificate_client is None


class TestSecretExpiryInfo:
    """Tests for SecretExpiryInfo dataclass."""

    def test_create_expiring_secret(self) -> None:
        """Test creating an expiring secret info."""
        expires_on = datetime.now(timezone.utc) + timedelta(days=15)
        info = SecretExpiryInfo(
            name="test-secret",
            expires_on=expires_on,
            days_until_expiry=15,
            is_expired=False,
            is_expiring_soon=True,
            created_on=datetime.now(timezone.utc) - timedelta(days=30),
            updated_on=datetime.now(timezone.utc) - timedelta(days=1),
            enabled=True,
        )

        assert info.name == "test-secret"
        assert info.days_until_expiry == 15
        assert info.is_expired is False
        assert info.is_expiring_soon is True

    def test_create_expired_secret(self) -> None:
        """Test creating an expired secret info."""
        expires_on = datetime.now(timezone.utc) - timedelta(days=5)
        info = SecretExpiryInfo(
            name="expired-secret",
            expires_on=expires_on,
            days_until_expiry=None,
            is_expired=True,
            is_expiring_soon=False,
            created_on=None,
            updated_on=None,
            enabled=False,
        )

        assert info.name == "expired-secret"
        assert info.is_expired is True
        assert info.days_until_expiry is None


class TestCertificateExpiryInfo:
    """Tests for CertificateExpiryInfo dataclass."""

    def test_create_expiring_certificate(self) -> None:
        """Test creating an expiring certificate info."""
        expires_on = datetime.now(timezone.utc) + timedelta(days=7)
        info = CertificateExpiryInfo(
            name="test-cert",
            expires_on=expires_on,
            days_until_expiry=7,
            is_expired=False,
            is_expiring_soon=True,
            thumbprint="abc123def456",
            subject="CN=test.example.com",
            issuer="Self",
            enabled=True,
        )

        assert info.name == "test-cert"
        assert info.thumbprint == "abc123def456"
        assert info.subject == "CN=test.example.com"
        assert info.is_expiring_soon is True


# Integration tests - only run if AZURE_KEYVAULT_URL is set
@pytest.mark.skipif(
    os.environ.get("AZURE_KEYVAULT_URL") is None,
    reason="AZURE_KEYVAULT_URL not set - skipping Azure integration tests",
)
class TestAzureKeyVaultIntegration:
    """Integration tests for Azure Key Vault (requires real Azure credentials)."""

    @pytest.fixture
    def azure_integration(self):
        """Create Azure Key Vault integration from environment."""
        vault_url = os.environ.get("AZURE_KEYVAULT_URL")
        integration = AzureKeyVaultIntegration(vault_url=vault_url)
        yield integration
        integration.disconnect()

    def test_connect_to_azure(self, azure_integration: AzureKeyVaultIntegration) -> None:
        """Test connection to real Azure Key Vault."""
        result = azure_integration.connect()
        assert result is True
        assert azure_integration.is_connected() is True

    def test_list_secrets_azure(self, azure_integration: AzureKeyVaultIntegration) -> None:
        """Test listing secrets from real Azure Key Vault."""
        azure_integration.connect()
        secrets = azure_integration.list_secrets()
        assert isinstance(secrets, list)

    def test_health_check_azure(self, azure_integration: AzureKeyVaultIntegration) -> None:
        """Test health check against real Azure Key Vault."""
        azure_integration.connect()
        health = azure_integration.check_health()
        assert health["healthy"] is True
        assert "vault_url" in health
