# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Revert an audit event by restoring its previous value (ADR-014): only Chronowarden's own data (ADR-004)."""

import json
from typing import Any

from chronowarden.assignments import AssignmentIndex

# Why each kind of event can't be reverted from Chronowarden
_NOT_REVERTIBLE = {
    "secret.metadata": "custom metadata belongs to the backend and other teams; Chronowarden writes only its own keys",
    "secret.settings": "version-cleanup settings belong to the backend",
    "secret.version": "a secret version can't be undone from Chronowarden",
    "secret.config_applied": "severity and TTL come from config.yaml; change the config instead",
    "config.baseline": "change config.yaml instead",
    "config.changed": "change config.yaml instead",
}


class RevertError(Exception):
    """An event can't be reverted; `status` is the HTTP status to answer with."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def _system_value(index: AssignmentIndex, identity: tuple[str, str, str]) -> Any:
    system = index.system_of(identity)
    return {"system": system.model_dump() if system else None}


def _owners_value(index: AssignmentIndex, identity: tuple[str, str, str]) -> Any:
    return {"owners": [owner.model_dump() for owner in index.owners_of(identity)]}


def revert_event(db: Any, event: dict, source: str) -> dict:
    """
    Restore the value an event replaced, and record that as a new event of the same type.

    Args:
        db: The Chronowarden database.
        event: The stored event to revert.
        source: Audit source of the request (`ui` or `api`).

    Returns:
        The new event.

    Raises:
        RevertError: 422 for events that can't be reverted, 409 when the value changed since the event or what it
            refers to no longer exists.
    """
    event_type = event["event_type"]
    if event_type not in ("secret.system", "secret.owners"):
        reason = _NOT_REVERTIBLE.get(event_type, "only system and owner assignments of secrets can be reverted")
        raise RevertError(422, f"Event {event['id']} ({event_type}) can't be reverted: {reason}")

    identity = (event["vault_name"], event["engine_id"], event["secret_path"])
    before, after = json.loads(event["before"]), json.loads(event["after"])
    index = AssignmentIndex(db)
    current = _system_value(index, identity) if event_type == "secret.system" else _owners_value(index, identity)
    if current != {key: after[key] for key in current}:
        raise RevertError(
            409, f"Event {event['id']} can't be reverted: the value changed since; revert the newer event"
        )

    if event_type == "secret.system":
        system = before["system"]
        if system is not None and db.get_system(system["id"]) is None:
            raise RevertError(409, f"System '{system['name']}' no longer exists")
        db.set_secret_system(identity, system["id"] if system else None)
        restored = _system_value(AssignmentIndex(db), identity)
    else:
        owner_ids = [owner["id"] for owner in before["owners"]]
        missing = sorted(set(owner_ids) - {owner["id"] for owner in db.list_owners()})
        if missing:
            raise RevertError(409, f"Owner(s) no longer exist: {', '.join(missing)}")
        db.set_secret_owners(identity, owner_ids)
        restored = _owners_value(AssignmentIndex(db), identity)

    new_event = db.append_audit_event(
        event_type, source, identity=identity, before=current, after={**restored, "reverts": event["id"]}
    )
    return new_event
