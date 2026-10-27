# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Authentication and permissions for the UI and API (ADR-015, ADR-026)."""

from chronowarden.auth.dependencies import (
    admin_only,
    authenticated,
    check_acts_for,
    owner_or_admin,
    request_actor,
    require_role,
)
from chronowarden.auth.principal import ANONYMOUS_ADMIN, Principal, role_for

__all__ = [
    "ANONYMOUS_ADMIN",
    "Principal",
    "admin_only",
    "authenticated",
    "check_acts_for",
    "owner_or_admin",
    "request_actor",
    "require_role",
    "role_for",
]
