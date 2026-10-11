# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Rotation confirmation: has the newest version of a secret been applied where it is used? (ADR-021)"""

from datetime import datetime, timedelta, timezone
from typing import Any, NamedTuple, Optional

from chronowarden.config import AppConfig
from chronowarden.database import SecretIdentity
from chronowarden.metadata import calculate_ttl, parse_date


class ConfirmationStatus(NamedTuple):
    """A secret's confirmation state."""

    required: bool
    awaiting: bool
    overdue: bool
    latest: Optional[dict]


def current_version(db: Any, identity: SecretIdentity) -> Optional[dict]:
    """Return the newest version sync saw (`current`, `created_time`), or None before the first sync."""
    state = db.get_observed_state(identity)
    return state["version"] if state else None


def confirmation_status(db: Any, config: AppConfig, identity: SecretIdentity, severity: str) -> ConfirmationStatus:
    """
    Work out whether a secret waits for confirmation and whether that is overdue.

    A secret awaits confirmation when confirmation is required and its newest version has no confirmation; it is
    overdue once that version is older than the grace period. Confirmations of older versions don't count.

    Args:
        db: The Chronowarden database.
        config: Application configuration (cascade and grace).
        identity: The secret.
        severity: Its resolved severity (selects the grace period).

    Returns:
        The confirmation status.
    """
    vault_name, engine_id, secret_path = identity
    required = config.resolve_confirmation_required(engine_id, vault_name, secret_path)
    latest = db.latest_confirmation(identity)
    version = current_version(db, identity)
    if not required or version is None or version.get("current") is None:
        return ConfirmationStatus(required, False, False, latest)
    awaiting = latest is None or latest["version"] < version["current"]
    created = parse_date(version.get("created_time") or "")
    grace = timedelta(days=config.get_confirmation_grace_days(severity))
    overdue = awaiting and created is not None and datetime.now(tz=timezone.utc) - created > grace
    return ConfirmationStatus(required, awaiting, overdue, latest)


def rotation_base(db: Any, identity: SecretIdentity, updated_time: str) -> str:
    """
    Return the time the next rotation counts from: the later of the backend's update and a confirmed applied date.

    Only a confirmation of the newest version counts (ADR-021).

    Args:
        db: The Chronowarden database.
        identity: The secret.
        updated_time: The backend's `updated_time`.

    Returns:
        An ISO 8601 timestamp for `calculate_ttl`.
    """
    latest = db.latest_confirmation(identity)
    version = current_version(db, identity)
    if latest is None or version is None or latest["version"] != version.get("current"):
        return updated_time
    applied, updated = parse_date(latest["applied_at"]), parse_date(updated_time)
    if applied is None or (updated is not None and updated >= applied):
        return updated_time
    return latest["applied_at"]


def refresh_cached_ttl(db: Any, config: AppConfig, identity: SecretIdentity) -> None:
    """
    Recalculate a cached secret's TTL after its confirmation changed; the next sync writes it to the backend.

    Args:
        db: The Chronowarden database.
        config: Application configuration.
        identity: The secret.
    """
    entry = db.get_secret_metadata(*identity)
    if entry is None or entry.updated_time is None or entry.severity is None:
        return
    ttl = calculate_ttl(rotation_base(db, identity, entry.updated_time), entry.severity, config)
    if ttl != entry.ttl:
        db.upsert_secret_metadata(entry.model_copy(update={"ttl": ttl}))
