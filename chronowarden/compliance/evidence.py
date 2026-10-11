# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Scope, gaps, summaries and snapshot documents over enriched secrets (#94). No I/O."""

import csv
import hashlib
import io
from typing import Any, Optional

from chronowarden.audit.chain import canonical_json
from chronowarden.config import ComplianceScope
from chronowarden.models.secret import SecretMetadataResponse

SNAPSHOT_FORMAT = 1

GAP_TYPES = ("no_owner", "no_system", "expired", "no_ttl", "privileged_without_owner", "awaiting_confirmation")

CSV_COLUMNS = (
    "vault",
    "engine",
    "path",
    "severity",
    "status",
    "ttl_date",
    "last_rotation",
    "system",
    "system_cmdb_uri",
    "system_asset_number",
    "owners",
    "privileged",
    "removed_at",
    "last_confirmed_applied_at",
    "awaiting_confirmation",
)


def in_scope(secret: SecretMetadataResponse, scope: ComplianceScope) -> bool:
    """Whether a secret falls in a scope; empty lists match everything."""
    return (
        (not scope.vaults or secret.vault_name in scope.vaults)
        and (not scope.engines or secret.engine_id in scope.engines)
        and (not scope.systems or (secret.system is not None and secret.system.name in scope.systems))
        and (not scope.privileged_only or secret.privileged)
    )


def gaps_of(secret: SecretMetadataResponse) -> list[str]:
    """The evidence gaps of one secret, in `GAP_TYPES` order."""
    found = {
        "no_owner": not secret.effective_owners,
        "no_system": secret.system is None,
        "expired": secret.status.value == "expired",
        "no_ttl": secret.status.value == "no_ttl",
        "privileged_without_owner": secret.privileged and not secret.effective_owners,
        "awaiting_confirmation": secret.awaiting_confirmation,
    }
    return [gap for gap in GAP_TYPES if found[gap]]


def summary(secrets: list[SecretMetadataResponse]) -> dict[str, list[dict[str, Any]]]:
    """Total and privileged counts per vault, engine and system (unassigned secrets under system null)."""

    def count(key: Any) -> list[dict[str, Any]]:
        groups: dict[Any, dict[str, Any]] = {}
        for secret in secrets:
            group_key, fields = key(secret)
            group = groups.setdefault(group_key, {**fields, "total": 0, "privileged": 0})
            group["total"] += 1
            group["privileged"] += int(secret.privileged)
        return sorted(groups.values(), key=lambda g: tuple(str(v) for v in g.values()))

    return {
        "by_vault": count(lambda s: (s.vault_name, {"vault": s.vault_name})),
        "by_engine": count(lambda s: ((s.vault_name, s.engine_id), {"vault": s.vault_name, "engine": s.engine_id})),
        "by_system": count(
            lambda s: (s.system.id if s.system else None, {"system": s.system.name if s.system else None})
        ),
    }


def snapshot_row(secret: SecretMetadataResponse, systems: dict[str, dict]) -> dict[str, Any]:
    """
    Freeze one secret for a snapshot.

    Args:
        secret: The enriched secret at snapshot time.
        systems: System records by id (for the CMDB link and asset number).

    Returns:
        The row; `awaiting_confirmation` is null where confirmation isn't required.
    """
    system = systems.get(secret.system.id) if secret.system else None
    confirmation = secret.last_confirmation
    return {
        "vault": secret.vault_name,
        "engine": secret.engine_id,
        "path": secret.secret_path,
        "severity": secret.severity,
        "status": secret.status.value,
        "ttl_date": secret.ttl,
        "last_rotation": secret.updated_time,
        "system": (
            {"name": system["name"], "cmdb_uri": system["cmdb_uri"], "asset_number": system["asset_number"]}
            if system
            else None
        ),
        "owners": sorted(owner.name for owner in secret.effective_owners),
        "privileged": secret.privileged,
        "removed_at": secret.removed_at.isoformat() if secret.removed_at else None,
        "last_confirmed_applied_at": confirmation.applied_at if confirmation else None,
        "awaiting_confirmation": secret.awaiting_confirmation if secret.confirmation_required else None,
    }


def build_document(
    rows: list[dict[str, Any]],
    created_at: str,
    scope: ComplianceScope,
    audit_head: dict[str, Any],
    label: Optional[str] = None,
    cadence: Optional[str] = None,
    period: Optional[str] = None,
    supersedes: Optional[int] = None,
) -> tuple[str, str]:
    """
    Build a snapshot's canonical JSON and its SHA-256.

    Returns:
        (canonical JSON text, hex SHA-256 of its UTF-8 bytes).
    """
    document = {
        "format": SNAPSHOT_FORMAT,
        "created_at": created_at,
        "label": label,
        "cadence": cadence,
        "period": period,
        "scope": scope.model_dump(),
        "supersedes": supersedes,
        "audit": audit_head,
        "rows": sorted(rows, key=lambda r: (r["vault"], r["engine"], r["path"])),
    }
    text = canonical_json(document)
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()


def rows_to_csv(rows: list[dict[str, Any]]) -> str:
    """Flatten snapshot rows to CSV (owners joined with '; ')."""
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    for row in rows:
        system = row["system"] or {}
        writer.writerow(
            {
                **{key: row[key] for key in CSV_COLUMNS if key in row and key not in ("system", "owners")},
                "system": system.get("name"),
                "system_cmdb_uri": system.get("cmdb_uri"),
                "system_asset_number": system.get("asset_number"),
                "owners": "; ".join(row["owners"]),
            }
        )
    return out.getvalue()
