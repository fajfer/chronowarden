# SPDX-FileCopyrightText: 2025 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Azure Key Vault integration for Chronowarden.

This module provides integration with Azure Key Vault for monitoring
secrets, certificates, and their expiration dates. It is designed
for compliance with financial sector requirements including DORA
(Digital Operational Resilience Act).
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from chronowarden.integrations.base import BaseIntegration

logger = logging.getLogger(__name__)


@dataclass
class SecretExpiryInfo:
    """Information about a secret's expiration status.

    Attributes:
        name: Name of the secret.
        expires_on: Expiration datetime (None if no expiry set).
        days_until_expiry: Days until expiration (None if no expiry or expired).
        is_expired: Whether the secret has already expired.
        is_expiring_soon: Whether the secret expires within the alert threshold.
        created_on: When the secret was created.
        updated_on: When the secret was last updated.
        enabled: Whether the secret is currently enabled.
    """

    name: str
    expires_on: Optional[datetime]
    days_until_expiry: Optional[int]
    is_expired: bool
    is_expiring_soon: bool
    created_on: Optional[datetime]
    updated_on: Optional[datetime]
    enabled: bool


@dataclass
class CertificateExpiryInfo:
    """Information about a certificate's expiration status.

    Attributes:
        name: Name of the certificate.
        expires_on: Expiration datetime.
        days_until_expiry: Days until expiration.
        is_expired: Whether the certificate has expired.
        is_expiring_soon: Whether the certificate expires within the alert threshold.
        thumbprint: Certificate thumbprint.
        subject: Certificate subject.
        issuer: Certificate issuer.
        enabled: Whether the certificate is currently enabled.
    """

    name: str
    expires_on: Optional[datetime]
    days_until_expiry: Optional[int]
    is_expired: bool
    is_expiring_soon: bool
    thumbprint: Optional[str]
    subject: Optional[str]
    issuer: Optional[str]
    enabled: bool


class AzureKeyVaultIntegration(BaseIntegration):
    """Integration with Azure Key Vault for secret and certificate monitoring.

    This integration focuses on monitoring secrets and certificates for
    expiration, which is critical for:
    - DORA compliance (financial sector operational resilience)
    - Polish banking sector regulations (KNF requirements)
    - General security posture management

    Note:
        This integration requires Azure SDK packages:
        - azure-identity
        - azure-keyvault-secrets
        - azure-keyvault-certificates
    """

    def __init__(
        self,
        vault_url: str,
        credential: Optional[Any] = None,
        expiry_alert_days: int = 30,
    ) -> None:
        """
        Initialize Azure Key Vault integration.

        Args:
            vault_url: Azure Key Vault URL (e.g., https://myvault.vault.azure.net/).
            credential: Azure credential object. If None, uses DefaultAzureCredential.
            expiry_alert_days: Number of days before expiry to trigger alerts.
        """
        self._vault_url = vault_url
        self._expiry_alert_days = expiry_alert_days
        self._credential = credential
        self._secret_client: Optional[Any] = None
        self._certificate_client: Optional[Any] = None
        self._connected = False

    def connect(self) -> bool:
        """
        Establish connection to Azure Key Vault.

        Returns:
            bool: True if connection successful.

        Note:
            Requires azure-identity and azure-keyvault-* packages.
        """
        try:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.certificates import CertificateClient
            from azure.keyvault.secrets import SecretClient

            if self._credential is None:
                self._credential = DefaultAzureCredential()

            self._secret_client = SecretClient(
                vault_url=self._vault_url,
                credential=self._credential,
            )
            self._certificate_client = CertificateClient(
                vault_url=self._vault_url,
                credential=self._credential,
            )

            # Test connection by listing secrets (limited to 1)
            list(self._secret_client.list_properties_of_secrets(max_page_size=1))

            self._connected = True
            logger.info("Successfully connected to Azure Key Vault at %s", self._vault_url)
            return True

        except ImportError:
            logger.exception("Azure SDK packages not installed")
            return False
        except Exception:
            logger.exception("Failed to connect to Azure Key Vault")
            return False

    def disconnect(self) -> None:
        """Close connection to Azure Key Vault."""
        if self._secret_client is not None:
            self._secret_client.close()
            self._secret_client = None
        if self._certificate_client is not None:
            self._certificate_client.close()
            self._certificate_client = None
        self._connected = False
        logger.info("Disconnected from Azure Key Vault")

    def is_connected(self) -> bool:
        """
        Check if connected to Azure Key Vault.

        Returns:
            bool: True if connected.
        """
        return self._connected and self._secret_client is not None

    def get_secret(self, path: str, key: Optional[str] = None) -> Optional[dict[str, Any]]:
        """
        Retrieve a secret from Azure Key Vault.

        Args:
            path: Name of the secret.
            key: Ignored for Azure Key Vault (single value per secret).

        Returns:
            Secret data dictionary or None if not found.
        """
        if not self._secret_client:
            logger.error("Not connected to Azure Key Vault")
            return None

        try:
            secret = self._secret_client.get_secret(path)
            return {
                "value": secret.value,
                "name": secret.name,
                "enabled": secret.properties.enabled,
                "expires_on": secret.properties.expires_on.isoformat() if secret.properties.expires_on else None,
                "created_on": secret.properties.created_on.isoformat() if secret.properties.created_on else None,
                "updated_on": secret.properties.updated_on.isoformat() if secret.properties.updated_on else None,
            }
        except Exception:
            logger.exception("Error retrieving secret from Azure Key Vault: %s", path)
            return None

    def list_secrets(self, path: str = "") -> list[str]:
        """
        List all secrets in Azure Key Vault.

        Args:
            path: Ignored for Azure Key Vault (flat namespace).

        Returns:
            List of secret names.
        """
        if not self._secret_client:
            logger.error("Not connected to Azure Key Vault")
            return []

        try:
            secrets = self._secret_client.list_properties_of_secrets()
            return [secret.name for secret in secrets if secret.name]
        except Exception:
            logger.exception("Error listing secrets from Azure Key Vault")
            return []

    def get_secret_metadata(self, path: str) -> Optional[dict[str, Any]]:
        """
        Get metadata about a secret including expiration info.

        Args:
            path: Name of the secret.

        Returns:
            Metadata dictionary including expiration information.
        """
        if not self._secret_client:
            logger.error("Not connected to Azure Key Vault")
            return None

        try:
            secret = self._secret_client.get_secret(path)
            props = secret.properties
            now = datetime.now(timezone.utc)

            expires_on = props.expires_on
            days_until_expiry = None
            is_expired = False
            is_expiring_soon = False

            if expires_on:
                # Ensure timezone-aware comparison
                if expires_on.tzinfo is None:
                    expires_on = expires_on.replace(tzinfo=timezone.utc)
                delta = expires_on - now
                days_until_expiry = delta.days
                is_expired = days_until_expiry < 0
                is_expiring_soon = 0 <= days_until_expiry <= self._expiry_alert_days

            return {
                "name": secret.name,
                "enabled": props.enabled,
                "expires_on": expires_on.isoformat() if expires_on else None,
                "days_until_expiry": days_until_expiry,
                "is_expired": is_expired,
                "is_expiring_soon": is_expiring_soon,
                "created_on": props.created_on.isoformat() if props.created_on else None,
                "updated_on": props.updated_on.isoformat() if props.updated_on else None,
                "content_type": props.content_type,
                "tags": props.tags,
            }
        except Exception:
            logger.exception("Error getting secret metadata from Azure Key Vault: %s", path)
            return None

    def get_expiring_secrets(self, days: Optional[int] = None) -> list[SecretExpiryInfo]:
        """
        Get all secrets expiring within the specified number of days.

        This method is critical for DORA compliance monitoring.

        Args:
            days: Number of days to look ahead. Defaults to expiry_alert_days.

        Returns:
            List of SecretExpiryInfo for secrets expiring soon.
        """
        if not self._secret_client:
            logger.error("Not connected to Azure Key Vault")
            return []

        alert_days = days if days is not None else self._expiry_alert_days
        expiring_secrets: list[SecretExpiryInfo] = []
        now = datetime.now(timezone.utc)

        try:
            for props in self._secret_client.list_properties_of_secrets():
                expires_on = props.expires_on
                if expires_on is None:
                    continue

                # Ensure timezone-aware comparison
                if expires_on.tzinfo is None:
                    expires_on = expires_on.replace(tzinfo=timezone.utc)

                delta = expires_on - now
                days_until_expiry = delta.days
                is_expired = days_until_expiry < 0
                is_expiring_soon = 0 <= days_until_expiry <= alert_days

                if is_expired or is_expiring_soon:
                    expiring_secrets.append(
                        SecretExpiryInfo(
                            name=props.name or "",
                            expires_on=expires_on,
                            days_until_expiry=days_until_expiry if not is_expired else None,
                            is_expired=is_expired,
                            is_expiring_soon=is_expiring_soon,
                            created_on=props.created_on,
                            updated_on=props.updated_on,
                            enabled=props.enabled or False,
                        )
                    )

            return sorted(expiring_secrets, key=lambda x: x.expires_on or datetime.max.replace(tzinfo=timezone.utc))

        except Exception:
            logger.exception("Error getting expiring secrets from Azure Key Vault")
            return []

    def list_certificates(self) -> list[str]:
        """
        List all certificates in Azure Key Vault.

        Returns:
            List of certificate names.
        """
        if not self._certificate_client:
            logger.error("Not connected to Azure Key Vault")
            return []

        try:
            certificates = self._certificate_client.list_properties_of_certificates()
            return [cert.name for cert in certificates if cert.name]
        except Exception:
            logger.exception("Error listing certificates from Azure Key Vault")
            return []

    def get_certificate_metadata(self, name: str) -> Optional[dict[str, Any]]:
        """
        Get metadata about a certificate including expiration info.

        Args:
            name: Name of the certificate.

        Returns:
            Metadata dictionary including expiration information.
        """
        if not self._certificate_client:
            logger.error("Not connected to Azure Key Vault")
            return None

        try:
            cert = self._certificate_client.get_certificate(name)
            props = cert.properties
            now = datetime.now(timezone.utc)

            expires_on = props.expires_on
            days_until_expiry = None
            is_expired = False
            is_expiring_soon = False

            if expires_on:
                if expires_on.tzinfo is None:
                    expires_on = expires_on.replace(tzinfo=timezone.utc)
                delta = expires_on - now
                days_until_expiry = delta.days
                is_expired = days_until_expiry < 0
                is_expiring_soon = 0 <= days_until_expiry <= self._expiry_alert_days

            return {
                "name": cert.name,
                "enabled": props.enabled,
                "expires_on": expires_on.isoformat() if expires_on else None,
                "days_until_expiry": days_until_expiry,
                "is_expired": is_expired,
                "is_expiring_soon": is_expiring_soon,
                "created_on": props.created_on.isoformat() if props.created_on else None,
                "updated_on": props.updated_on.isoformat() if props.updated_on else None,
                "thumbprint": props.x509_thumbprint.hex() if props.x509_thumbprint else None,
                "subject": cert.policy.subject if cert.policy else None,
                "issuer": cert.policy.issuer_name if cert.policy else None,
                "tags": props.tags,
            }
        except Exception:
            logger.exception("Error getting certificate metadata from Azure Key Vault: %s", name)
            return None

    def get_expiring_certificates(self, days: Optional[int] = None) -> list[CertificateExpiryInfo]:
        """
        Get all certificates expiring within the specified number of days.

        This method is critical for DORA compliance monitoring and
        certificate lifecycle management in financial institutions.

        Args:
            days: Number of days to look ahead. Defaults to expiry_alert_days.

        Returns:
            List of CertificateExpiryInfo for certificates expiring soon.
        """
        if not self._certificate_client:
            logger.error("Not connected to Azure Key Vault")
            return []

        alert_days = days if days is not None else self._expiry_alert_days
        expiring_certs: list[CertificateExpiryInfo] = []
        now = datetime.now(timezone.utc)

        try:
            for props in self._certificate_client.list_properties_of_certificates():
                expires_on = props.expires_on
                if expires_on is None:
                    continue

                if expires_on.tzinfo is None:
                    expires_on = expires_on.replace(tzinfo=timezone.utc)

                delta = expires_on - now
                days_until_expiry = delta.days
                is_expired = days_until_expiry < 0
                is_expiring_soon = 0 <= days_until_expiry <= alert_days

                if is_expired or is_expiring_soon:
                    # Get full certificate for additional details
                    try:
                        cert = self._certificate_client.get_certificate(props.name)
                        subject = cert.policy.subject if cert.policy else None
                        issuer = cert.policy.issuer_name if cert.policy else None
                    except Exception:
                        subject = None
                        issuer = None

                    expiring_certs.append(
                        CertificateExpiryInfo(
                            name=props.name or "",
                            expires_on=expires_on,
                            days_until_expiry=days_until_expiry if not is_expired else None,
                            is_expired=is_expired,
                            is_expiring_soon=is_expiring_soon,
                            thumbprint=props.x509_thumbprint.hex() if props.x509_thumbprint else None,
                            subject=subject,
                            issuer=issuer,
                            enabled=props.enabled or False,
                        )
                    )

            return sorted(expiring_certs, key=lambda x: x.expires_on or datetime.max.replace(tzinfo=timezone.utc))

        except Exception:
            logger.exception("Error getting expiring certificates from Azure Key Vault")
            return []

    def check_health(self) -> dict[str, Any]:
        """
        Check Azure Key Vault health status.

        Returns:
            Health status dictionary.
        """
        if not self._connected:
            return {"healthy": False, "error": "Not connected"}

        try:
            # Try to list secrets as a health check
            list(self._secret_client.list_properties_of_secrets(max_page_size=1))
            return {
                "healthy": True,
                "vault_url": self._vault_url,
                "expiry_alert_days": self._expiry_alert_days,
            }
        except Exception:
            logger.exception("Azure Key Vault health check failed")
            return {"healthy": False, "error": "Health check failed"}
