# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Metadata management for Chronowarden expiry monitoring."""

import logging
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from hvac.exceptions import VaultError

from chronowarden.config import AppConfig
from chronowarden.database import Database, SecretMetadataCache
from chronowarden.integrations.vault import VaultIntegration

logger = logging.getLogger("uvicorn.error")

_ISO_8601_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


def parse_date(date_str: str, format_hint: str = "YYYY-MM-DD") -> Optional[datetime]:
    """
    Parse a date string with auto-detection of format.

    Supported formats:
        - ISO 8601: '2026-02-07T14:02:00.859376388Z'
        - YYYY-MM-DD: '2026-02-07'
        - YYYY-DD-MM: '2026-07-02'

    Args:
        date_str: The date string to parse.
        format_hint: Hint for ambiguous dates ('YYYY-MM-DD' or 'YYYY-DD-MM').

    Returns:
        Parsed datetime, or None if parsing fails.
    """
    if not date_str or not isinstance(date_str, str):
        return None

    date_str = date_str.strip()

    if _ISO_8601_PATTERN.match(date_str):
        try:
            cleaned = date_str.rstrip("Z")
            if "." in cleaned:
                parts = cleaned.split(".")
                fractional = parts[1][:6]
                cleaned = f"{parts[0]}.{fractional}"
            dt = datetime.fromisoformat(cleaned)
            if date_str.endswith("Z"):
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            logger.warning("Failed to parse ISO 8601 date: %s", date_str)
            return None

    bare_match = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", date_str)
    if bare_match:
        year = int(bare_match.group(1))
        part2 = int(bare_match.group(2))
        part3 = int(bare_match.group(3))

        if format_hint == "YYYY-DD-MM":
            day, month = part2, part3
        else:
            month, day = part2, part3

        try:
            return datetime(year, month, day, tzinfo=timezone.utc)
        except ValueError:
            if format_hint == "YYYY-MM-DD":
                try:
                    return datetime(year, part3, part2, tzinfo=timezone.utc)
                except ValueError:
                    pass
            logger.warning("Failed to parse date: %s", date_str)
            return None

    logger.warning("Unrecognized date format: %s", date_str)
    return None


def format_date(dt: datetime, date_format: str = "YYYY-MM-DD") -> str:
    """
    Format a datetime to a date string.

    Args:
        dt: The datetime to format.
        date_format: Target format ('YYYY-MM-DD' or 'YYYY-DD-MM').

    Returns:
        Formatted date string.
    """
    if date_format == "YYYY-DD-MM":
        return dt.strftime("%Y-%d-%m")
    return dt.strftime("%Y-%m-%d")


def calculate_ttl(updated_time: str, severity: str, config: AppConfig) -> Optional[str]:
    """
    Calculate the expiry date (TTL) for a secret.

    Args:
        updated_time: The secret's metadata.updated_time from Vault (ISO 8601).
        severity: The resolved severity profile name.
        config: Application configuration containing expiry profiles.

    Returns:
        Calculated TTL as a date string, or None if calculation fails.
    """
    if severity == "none":
        return None

    parsed_updated = parse_date(updated_time)
    if parsed_updated is None:
        logger.warning("Cannot parse updated_time: %s", updated_time)
        return None

    rotation_days = config.get_rotation_days(severity)
    expiry_dt = parsed_updated + timedelta(days=rotation_days)

    return format_date(expiry_dt, config.date_format)


def is_secret_enabled(custom_metadata: dict[str, Any]) -> bool:
    """
    Determine if a secret is enabled for monitoring.

    Args:
        custom_metadata: The custom_metadata dict from Vault.

    Returns:
        True if the secret is enabled, False otherwise.
    """
    enabled_value = custom_metadata.get("chronowarden_enabled")
    if enabled_value is None:
        return True

    if isinstance(enabled_value, bool):
        return enabled_value

    if isinstance(enabled_value, str):
        return enabled_value.lower() not in ("false", "0", "no")

    return bool(enabled_value)


def sync_secret_metadata(
    vault: VaultIntegration,
    vault_name: str,
    engine_id: str,
    secret_path: str,
    config: AppConfig,
    db: Database,
) -> Optional[SecretMetadataCache]:
    """
    Synchronize metadata for a single secret between Vault and internal state.

    Config is the source of truth. During sync:
        1. Read remote metadata from Vault backend (updated_time, custom_metadata).
        2. Resolve severity purely from config cascade (config always wins).
        3. Compare remote backend state and internal DB against desired config state.
        4. Write back to Vault backend and update internal DB when they diverge.

    When severity is 'none', the secret is monitored but never rotated (TTL is null).

    Args:
        vault: The VaultIntegration instance.
        vault_name: Name of the vault.
        engine_id: Engine mount path.
        secret_path: Path to the secret within the engine.
        config: Application configuration.
        db: Database for internal state.

    Returns:
        The updated metadata cache entry, or None if sync failed.
    """
    vault_metadata = vault.get_secret_metadata(secret_path, mount_point=engine_id)
    if vault_metadata is None:
        logger.warning("No metadata found for %s/%s in vault '%s'", engine_id, secret_path, vault_name)
        return None

    custom_metadata = vault_metadata.get("custom_metadata") or {}
    updated_time = vault_metadata.get("updated_time", "")

    # Resolve severity purely from config — never from Vault metadata
    severity = config.resolve_severity(engine_id, vault_name, secret_path=secret_path)

    # Read what the remote backend currently has
    remote_severity = custom_metadata.get("chronowarden_severity")
    remote_ttl = custom_metadata.get("chronowarden_ttl")

    # Read what the internal database currently has
    cached = db.get_secret_metadata(vault_name, engine_id, secret_path)

    # Calculate the desired TTL from config
    desired_ttl = calculate_ttl(updated_time, severity, config)

    # Determine if the remote backend needs updating
    remote_needs_update = False
    if remote_severity != severity:
        remote_needs_update = True
        logger.info(
            "Remote severity mismatch for %s/%s (%s -> %s), updating backend",
            engine_id,
            secret_path,
            remote_severity,
            severity,
        )
    if remote_ttl != desired_ttl:
        remote_needs_update = True
        if remote_severity == severity:
            logger.info(
                "Remote TTL mismatch for %s/%s (%s -> %s), updating backend",
                engine_id,
                secret_path,
                remote_ttl,
                desired_ttl,
            )

    # Determine if the internal database needs updating
    db_needs_update = False
    if cached is None:
        db_needs_update = True
    elif cached.severity != severity or cached.ttl != desired_ttl or cached.updated_time != updated_time:
        db_needs_update = True
        if cached.updated_time != updated_time:
            logger.info(
                "Secret %s/%s updated_time changed (%s -> %s)",
                engine_id,
                secret_path,
                cached.updated_time,
                updated_time,
            )

    # Write to remote backend if it diverges from config
    if remote_needs_update:
        metadata_fields: dict[str, str] = {
            "chronowarden_severity": severity,
        }
        if desired_ttl is not None:
            metadata_fields["chronowarden_ttl"] = desired_ttl
        if vault.write_secret_metadata(secret_path, metadata_fields, mount_point=engine_id):
            logger.info(
                "Updated backend metadata for %s/%s (severity=%s, ttl=%s)",
                engine_id,
                secret_path,
                severity,
                desired_ttl,
            )
        else:
            logger.warning("Failed to write metadata for %s/%s", engine_id, secret_path)

    # Always build the authoritative entry from config + remote updated_time
    entry = SecretMetadataCache(
        vault_name=vault_name,
        engine_id=engine_id,
        secret_path=secret_path,
        updated_time=updated_time,
        ttl=desired_ttl,
        severity=severity,
        enabled=True,
        last_synced=datetime.now(tz=timezone.utc).isoformat(),
    )

    # Update internal database if it diverges from desired state
    if db_needs_update:
        db.upsert_secret_metadata(entry)

    return entry


def _list_secret_paths(vault: VaultIntegration, engine_id: str, prefix: str = "") -> list[str]:
    """
    Recursively list all secret paths under a given engine and prefix.

    Walks the KV v2 hierarchy depth-first, descending into subdirectories (keys that
    end with '/') and collecting all secret paths, not just those stored at the engine
    root.

    Args:
        vault: The VaultIntegration instance.
        engine_id: Engine mount path.
        prefix: Optional (empty for root) prefix to filter secrets.
    """
    paths: list[str] = []

    try:
        keys = vault.list_secrets(prefix, mount_point=engine_id)
    except VaultError:
        logger.exception("Error listing secrets in %s/%s", engine_id, prefix)
        return paths

    for key in keys:
        full_path = f"{prefix}{key}"
        if key.endswith("/"):
            paths.extend(_list_secret_paths(vault, engine_id, full_path))
        else:
            paths.append(full_path)
    return paths


def detect_changes(
    vault: VaultIntegration,
    vault_name: str,
    config: AppConfig,
    db: Database,
) -> list[SecretMetadataCache]:
    """
    Poll a vault for changes across all discovered engines.

    Args:
        vault: The VaultIntegration instance.
        vault_name: Name of the vault.
        config: Application configuration.
        db: Database for internal state.

    Returns:
        List of updated metadata cache entries.
    """
    updated: list[SecretMetadataCache] = []
    engines = vault.discover_engines()

    if not engines:
        logger.info("No KV v2 engines discovered for vault '%s'", vault_name)
        return updated

    for engine in engines:
        engine_path = engine["path"]
        logger.info("Scanning engine '%s' in vault '%s'", engine_path, vault_name)

        for secret_path in _list_secret_paths(vault, engine_path):
            try:
                result = sync_secret_metadata(vault, vault_name, engine_path, secret_path, config, db)
                if result is not None:
                    updated.append(result)
            except VaultError:
                logger.exception("Vault error syncing secret %s/%s", engine_path, secret_path)
            except sqlite3.Error:
                logger.exception("Database error syncing secret %s/%s", engine_path, secret_path)

    logger.info("Sync complete for vault '%s': %d secrets processed", vault_name, len(updated))
    return updated
