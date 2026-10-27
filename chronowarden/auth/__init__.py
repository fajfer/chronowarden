# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Authentication and permissions for the UI and API (ADR-015, ADR-026)."""

from chronowarden.auth.dependencies import (
    authenticated,
    check_acts_for,
    request_actor,
    require_role,
)
from chronowarden.auth.principal import ANONYMOUS_ADMIN, Principal, role_for

__all__ = [
    "ANONYMOUS_ADMIN",
    "Principal",
    "authenticated",
    "check_acts_for",
    "request_actor",
    "require_role",
    "role_for",
]
