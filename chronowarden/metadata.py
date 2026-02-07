# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Metadata management for Chronowarden expiry monitoring."""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from chronowarden.config import AppConfig
from chronowarden.database import Database, SecretMetadataCache
from chronowarden.integrations.vault import VaultIntegration

logger = logging.getLogger(__name__)

_ISO_8601_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
)


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


def resolve_secret_severity(
    custom_metadata: dict[str, Any],
    engine_id: Optional[str],
    vault_name: Optional[str],
    config: AppConfig,
    db: Optional[Database] = None,
) -> str:
    """
    Resolve the severity for a secret using the configuration cascade.

    Priority: secret custom_metadata → engine config (DB) → engine config (YAML) → vault → global.

    Args:
        custom_metadata: The custom_metadata dict from Vault.
        engine_id: Engine identifier.
        vault_name: Vault instance name.
        config: Application configuration.
        db: Optional database for engine-level overrides.

    Returns:
        Resolved severity string.
    """
    secret_severity = custom_metadata.get("chronowarden_severity")

    if db is not None and engine_id is not None and vault_name is not None:
        db_engine = db.get_engine_config(vault_name, engine_id)
        if db_engine and db_engine.default_severity:
            if secret_severity is None:
                return db_engine.default_severity

    return config.resolve_severity(secret_severity, engine_id, vault_name)


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

    enabled = is_secret_enabled(custom_metadata)
    severity_raw = custom_metadata.get("chronowarden_severity")

    if severity_raw == "none":
        enabled = False

    if not enabled:
        entry = SecretMetadataCache(
            vault_name=vault_name,
            engine_id=engine_id,
            secret_path=secret_path,
            updated_time=updated_time,
            ttl=custom_metadata.get("chronowarden_ttl"),
            severity=severity_raw,
            enabled=False,
            last_synced=datetime.now(tz=timezone.utc).isoformat(),
        )
        db.upsert_secret_metadata(entry)
        return entry

    severity = resolve_secret_severity(custom_metadata, engine_id, vault_name, config, db)

    cached = db.get_secret_metadata(vault_name, engine_id, secret_path)
    vault_ttl = custom_metadata.get("chronowarden_ttl")

    needs_recalculate = False
    if vault_ttl is None:
        needs_recalculate = True
        logger.info("No chronowarden_ttl found for %s/%s, calculating", engine_id, secret_path)
    elif cached is not None and cached.updated_time != updated_time:
        needs_recalculate = True
        logger.info(
            "Secret %s/%s updated_time changed (%s -> %s), recalculating TTL",
            engine_id,
            secret_path,
            cached.updated_time,
            updated_time,
        )

    if needs_recalculate:
        new_ttl = calculate_ttl(updated_time, severity, config)
        if new_ttl is not None:
            metadata_fields = {
                "chronowarden_ttl": new_ttl,
                "chronowarden_severity": severity,
            }
            if vault.write_secret_metadata(secret_path, metadata_fields, mount_point=engine_id):
                logger.info("Wrote TTL %s for %s/%s", new_ttl, engine_id, secret_path)
            else:
                logger.warning("Failed to write metadata for %s/%s", engine_id, secret_path)
            vault_ttl = new_ttl
    elif cached is not None and vault_ttl is not None and cached.ttl != vault_ttl:
        logger.info(
            "TTL mismatch for %s/%s (cached=%s, vault=%s), trusting Vault",
            engine_id,
            secret_path,
            cached.ttl,
            vault_ttl,
        )

    entry = SecretMetadataCache(
        vault_name=vault_name,
        engine_id=engine_id,
        secret_path=secret_path,
        updated_time=updated_time,
        ttl=vault_ttl,
        severity=severity,
        enabled=True,
        last_synced=datetime.now(tz=timezone.utc).isoformat(),
    )
    db.upsert_secret_metadata(entry)
    return entry


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

        try:
            secrets = vault.list_secrets("", mount_point=engine_path)
        except Exception:
            logger.exception("Error listing secrets in %s", engine_path)
            continue

        for secret_name in secrets:
            if secret_name.endswith("/"):
                continue

            try:
                result = sync_secret_metadata(vault, vault_name, engine_path, secret_name, config, db)
                if result is not None:
                    updated.append(result)
            except Exception:
                logger.exception("Error syncing secret %s/%s", engine_path, secret_name)

    logger.info("Sync complete for vault '%s': %d secrets processed", vault_name, len(updated))
    return updated
