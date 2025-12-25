# SPDX-FileCopyrightText: 2025 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Integrations package for Chronowarden."""

from chronowarden.integrations.base import BaseIntegration
from chronowarden.integrations.vault import VaultIntegration

__all__ = [
    "BaseIntegration",
    "VaultIntegration",
]
