# SPDX-FileCopyrightText: 2025 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Models package for Chronowarden."""

from chronowarden.models.engine import (
    AzureKeyVaultEngine,
    EngineType,
    HashicorpVaultEngine,
    ManualEngine,
    SecretEngine,
    X509Engine,
)
from chronowarden.models.entity import Entity, Group, PermissionLevel, TechnicalUser, User
from chronowarden.models.router import EmailRouter, Router, RouterType, WebhookRouter
from chronowarden.models.secret import (
    AzureKeyVaultSecret,
    HashicorpVaultSecret,
    Secret,
    SecretBase,
    SecretCreate,
    SecretTemplate,
    SecretUpdate,
)

__all__ = [
    # Engine
    "AzureKeyVaultEngine",
    "EngineType",
    "HashicorpVaultEngine",
    "ManualEngine",
    "SecretEngine",
    "X509Engine",
    # Entity
    "Entity",
    "Group",
    "PermissionLevel",
    "TechnicalUser",
    "User",
    # Router
    "EmailRouter",
    "Router",
    "RouterType",
    "WebhookRouter",
    # Secret
    "AzureKeyVaultSecret",
    "HashicorpVaultSecret",
    "Secret",
    "SecretBase",
    "SecretCreate",
    "SecretTemplate",
    "SecretUpdate",
]
