# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Chronowarden - Secret management service."""

from importlib.metadata import version

from chronowarden.app import app

__version__ = version("chronowarden")
__all__ = ["app"]
