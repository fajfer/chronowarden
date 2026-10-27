# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Who is making a request, with which role, acting for which owners (ADR-026)."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal, Optional

from chronowarden.config import ROLES, AuthConfig, Role

PrincipalKind = Literal["session", "token", "proxy", "anonymous"]


@dataclass(frozen=True)
class Principal:
    """
    An authenticated caller.

    `role` is None for a user whose groups match no role (they get 403, not 401). `owner_ids` are the owners the
    caller acts for: matched by email or IdP group, or the one owner an owner token is bound to.
    """

    name: str
    role: Optional[Role]
    kind: PrincipalKind
    email: Optional[str] = None
    groups: tuple[str, ...] = ()
    owner_ids: frozenset[str] = field(default_factory=frozenset)

    @property
    def actor(self) -> Optional[str]:
        """The audit log's actor: `user:<email or name>`, `token:<name>`, or None without authentication."""
        if self.kind == "anonymous":
            return None
        if self.kind == "token":
            return f"token:{self.name}"
        return f"user:{self.email or self.name}"

    def at_least(self, role: Role) -> bool:
        """Whether the caller's role is `role` or higher."""
        return self.role is not None and ROLES.index(self.role) <= ROLES.index(role)

    def acts_for(self, owner_ids: Iterable[str]) -> bool:
        """Admins act for everyone, owners for the owners they match, viewers for nobody."""
        if self.role == "admin":
            return True
        return self.role == "owner" and not self.owner_ids.isdisjoint(owner_ids)


ANONYMOUS_ADMIN = Principal(name="anonymous", role="admin", kind="anonymous")


def role_for(groups: Iterable[str], auth: AuthConfig) -> Optional[Role]:
    """
    The highest role any of the groups is mapped to, else `auth.default_role`.

    Args:
        groups: The user's IdP groups.
        auth: The auth settings.

    Returns:
        The role, or None when the user gets no access.
    """
    member_of = set(groups)
    for role in ROLES:
        if member_of.intersection(getattr(auth.roles, role)):
            return role
    return auth.default_role
