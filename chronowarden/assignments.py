# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Resolve system and owner assignments of secrets (ADR-010, ADR-017)."""

from typing import Any, Optional

from chronowarden.confirmations import ConfirmationIndex
from chronowarden.database import SecretIdentity
from chronowarden.models.system import OwnerRef, SystemRef


class AssignmentIndex:
    """All assignments loaded once, so listing secrets doesn't query per secret."""

    def __init__(self, db: Any) -> None:
        """
        Load systems, owners and assignments from the database.

        Args:
            db: The Chronowarden database.
        """
        self.db = db
        self._systems = {system["id"]: system for system in db.list_systems()}
        self._owner_names = {owner["id"]: owner["name"] for owner in db.list_owners()}
        self._secret_systems, self._secret_owners = db.get_assignments()
        self.confirmations = ConfirmationIndex(db)

    def _owner_refs(self, owner_ids: list[str]) -> list[OwnerRef]:
        """Turn owner IDs into references, skipping IDs that no longer exist."""
        return [OwnerRef(id=oid, name=self._owner_names[oid]) for oid in owner_ids if oid in self._owner_names]

    def system_of(self, identity: SecretIdentity) -> Optional[SystemRef]:
        """Return the secret's system, or None when unassigned."""
        system = self._systems.get(self._secret_systems.get(identity, ""))
        return SystemRef(id=system["id"], name=system["name"]) if system else None

    def owners_of(self, identity: SecretIdentity) -> list[OwnerRef]:
        """Return the owners assigned to the secret itself."""
        return self._owner_refs(self._secret_owners.get(identity, []))

    def effective_owners_of(self, identity: SecretIdentity) -> list[OwnerRef]:
        """Return the secret's own owners, or else its system's owners."""
        own = self.owners_of(identity)
        if own:
            return own
        system = self._systems.get(self._secret_systems.get(identity, ""))
        return self._owner_refs(system["owner_ids"]) if system else []

    def system_owner_refs(self, system: dict) -> list[OwnerRef]:
        """Return a system's owners as references."""
        return self._owner_refs(system["owner_ids"])

    def matches(
        self,
        identity: SecretIdentity,
        system_id: Optional[str] = None,
        owner_id: Optional[str] = None,
        unassigned: Optional[bool] = None,
    ) -> bool:
        """
        Check a secret against the assignment filters of `GET /secrets/`.

        Args:
            identity: The secret.
            system_id: Keep secrets assigned to this system.
            owner_id: Keep secrets this owner is effectively responsible for.
            unassigned: True keeps secrets with neither system nor own owners; False keeps the others.

        Returns:
            Whether the secret passes every given filter.
        """
        if system_id is not None and self._secret_systems.get(identity) != system_id:
            return False
        if owner_id is not None and owner_id not in {ref.id for ref in self.effective_owners_of(identity)}:
            return False
        if unassigned is not None:
            is_unassigned = identity not in self._secret_systems and not self._secret_owners.get(identity)
            if is_unassigned != unassigned:
                return False
        return True
