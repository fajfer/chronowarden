# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""API package for Chronowarden."""

from chronowarden.api.health import router as health_router
from chronowarden.api.secrets import router as secrets_router
from chronowarden.api.sync import router as sync_router
from chronowarden.api.vault import router as vault_router

__all__ = [
    "health_router",
    "secrets_router",
    "sync_router",
    "vault_router",
]
