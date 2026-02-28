# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Secret engine model definitions for Chronowarden."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class EngineType(str, Enum):
    """Types of secret storage engines."""

    MANUAL = "manual"
    AZURE_KEYVAULT = "azure_keyvault"
    HASHICORP_VAULT = "hashicorp_vault"
    X509 = "x509"


class SecretEngine(BaseModel):
    """Base class for secret storage backends."""

    id: int
    name: str
    engine_type: EngineType
    description: Optional[str] = None
    owner_id: int


class ManualEngine(SecretEngine):
    """Manual secret engine - purely based on user input."""

    engine_type: EngineType = EngineType.MANUAL


class HashicorpVaultEngine(SecretEngine):
    """HashiCorp Vault secret engine."""

    engine_type: EngineType = EngineType.HASHICORP_VAULT
    vault_address: str
    vault_namespace: Optional[str] = None
    mount_path: str = "secret"
    auth_method: str = "token"


class AzureKeyVaultEngine(SecretEngine):
    """Azure Key Vault secret engine."""

    engine_type: EngineType = EngineType.AZURE_KEYVAULT
    subscription_id: str
    resource_group: str
    vault_name: str


class X509Engine(SecretEngine):
    """X.509 certificate engine."""

    engine_type: EngineType = EngineType.X509
    ca_certificate_path: Optional[str] = None
