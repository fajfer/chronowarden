# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""API package for Chronowarden."""

from chronowarden.api.audit import router as audit_router
from chronowarden.api.compliance import router as compliance_router
from chronowarden.api.health import router as health_router
from chronowarden.api.owners import router as owners_router
from chronowarden.api.secrets import router as secrets_router
from chronowarden.api.sync import router as sync_router
from chronowarden.api.systems import router as systems_router
from chronowarden.api.vault import router as vault_router

__all__ = [
    "audit_router",
    "compliance_router",
    "health_router",
    "owners_router",
    "secrets_router",
    "sync_router",
    "systems_router",
    "vault_router",
]
