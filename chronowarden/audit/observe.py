# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Record changes made in the backend (metadata keys, settings, new versions) by comparing with the last sync."""

from typing import Any, Optional

from chronowarden.database import SecretIdentity

SETTINGS = ("delete_version_after", "max_versions", "cas_required")


def observed_state(vault_metadata: dict[str, Any]) -> dict[str, Any]:
    """
    Extract what Chronowarden tracks from a KV v2 metadata response; secret values are never part of it.

    Args:
        vault_metadata: The `data` of a KV v2 metadata read.

    Returns:
        Custom metadata, version-cleanup settings, and the current version with its creation time.
    """
    current = vault_metadata.get("current_version")
    versions = vault_metadata.get("versions") or {}
    return {
        "custom_metadata": dict(vault_metadata.get("custom_metadata") or {}),
        "settings": {key: vault_metadata.get(key) for key in SETTINGS},
        "version": {
            "current": current,
            "created_time": (versions.get(str(current)) or {}).get("created_time"),
        },
    }


def _changed_keys(before: dict[str, Any], after: dict[str, Any]) -> Optional[tuple[dict, dict]]:
    """Return the differing keys as (old values, new values), None for missing; None when nothing differs."""
    keys = sorted(key for key in before.keys() | after.keys() if before.get(key) != after.get(key))
    if not keys:
        return None
    return {key: before.get(key) for key in keys}, {key: after.get(key) for key in keys}


def record_observed_changes(db: Any, identity: SecretIdentity, state: dict[str, Any]) -> None:
    """
    Compare a secret's backend state with the last sync and record what changed (source `sync`).

    The first sight of a secret records one `secret.baseline` event instead of a diff.

    Args:
        db: The Chronowarden database.
        identity: The secret.
        state: Its current state from `observed_state`.
    """
    previous = db.get_observed_state(identity)
    if previous is None:
        db.append_audit_event("secret.baseline", "sync", identity=identity, after=state)
    else:
        metadata = _changed_keys(previous["custom_metadata"], state["custom_metadata"])
        if metadata is not None:
            db.append_audit_event("secret.metadata", "sync", identity=identity, before=metadata[0], after=metadata[1])
        settings = _changed_keys(previous["settings"], state["settings"])
        if settings is not None:
            db.append_audit_event("secret.settings", "sync", identity=identity, before=settings[0], after=settings[1])
        if previous["version"]["current"] != state["version"]["current"]:
            db.append_audit_event(
                "secret.version", "sync", identity=identity, before=previous["version"], after=state["version"]
            )
    db.set_observed_state(identity, state)


def record_config_applied(db: Any, identity: SecretIdentity, state: dict[str, Any], written: dict[str, str]) -> None:
    """
    Record Chronowarden writing its own keys (severity, TTL from config) and remember them as observed.

    Without this, the next sync would report Chronowarden's own write as a change made in the backend.

    Args:
        db: The Chronowarden database.
        identity: The secret.
        state: The state observed before the write (updated in place).
        written: The `chronowarden_*` keys and values written.
    """
    changed = _changed_keys({key: state["custom_metadata"].get(key) for key in written}, written)
    state["custom_metadata"].update(written)
    db.set_observed_state(identity, state)
    if changed is not None:
        db.append_audit_event("secret.config_applied", "sync", identity=identity, before=changed[0], after=changed[1])
