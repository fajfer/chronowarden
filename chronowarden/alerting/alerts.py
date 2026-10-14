# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Alerts and the rules that raise them (ADR-025). Pure functions, no I/O."""

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Optional

from chronowarden.audit.chain import canonical_json
from chronowarden.models.secret import SecretMetadataResponse

# Alerts that fire while a condition holds, are repeated and resolve; the rest fire once
SECRET_STATE_ALERTS = ("SecretExpiringSoon", "SecretExpired", "SecretRotationUnconfirmed")
VAULT_STATE_ALERTS = ("VaultUnreachable",)
STATE_ALERTS = SECRET_STATE_ALERTS + VAULT_STATE_ALERTS

# Audit events that become event alerts (ADR-014 event types)
AUDIT_EVENT_ALERTS = {
    "secret.version": "SecretRotated",
    "secret.confirmed": "SecretRotationConfirmed",
    "compliance.snapshot": "ComplianceSnapshotCreated",
}


@dataclass(frozen=True)
class Alert:
    """One alert: its labels (`identity` fixes the fingerprint), annotations and the owners it goes to."""

    name: str
    identity: dict[str, str]
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)
    owner_ids: tuple[str, ...] = ()
    starts_at: Optional[str] = None

    @property
    def fingerprint(self) -> str:
        """SHA-256 of the name and the identity labels: stable while owners, systems or severity change."""
        return hashlib.sha256(canonical_json({"alertname": self.name, **self.identity}).encode("utf-8")).hexdigest()

    @property
    def all_labels(self) -> dict[str, str]:
        """The labels sent in the payload."""
        return {"alertname": self.name, **self.identity, **self.labels}


def _secret_identity(vault: str, engine: str, path: str) -> dict[str, str]:
    return {"vault": vault, "engine": engine, "secret_path": path}


def _secret_labels(secret: SecretMetadataResponse) -> dict[str, str]:
    return {
        "severity": secret.severity,
        "system": secret.system.name if secret.system else "",
        "owners": ", ".join(sorted(owner.name for owner in secret.effective_owners)),
    }


def _owner_ids(secret: SecretMetadataResponse) -> tuple[str, ...]:
    return tuple(sorted(owner.id for owner in secret.effective_owners))


def secret_state_alerts(secrets: list[SecretMetadataResponse]) -> list[Alert]:
    """The state alerts that hold now: expiring soon, expired and rotation unconfirmed past the grace period."""
    alerts = []
    for secret in secrets:
        if secret.removed_at is not None:
            continue
        identity = _secret_identity(secret.vault_name, secret.engine_id, secret.secret_path)
        common = {"identity": identity, "labels": _secret_labels(secret), "owner_ids": _owner_ids(secret)}
        if secret.status.value == "warning":
            alerts.append(
                Alert(
                    "SecretExpiringSoon",
                    **common,
                    annotations={
                        "summary": f"{secret.full_path} must be rotated by {secret.ttl}",
                        "description": f"{secret.days_remaining} day(s) left of its {secret.severity} rotation period",
                    },
                )
            )
        elif secret.status.value == "expired":
            alerts.append(
                Alert(
                    "SecretExpired",
                    **common,
                    annotations={
                        "summary": f"{secret.full_path} is past its rotation date ({secret.ttl})",
                        "description": "Rotate it in the backend; the next sync notices the new version",
                    },
                )
            )
        if secret.confirmation_overdue:
            alerts.append(
                Alert(
                    "SecretRotationUnconfirmed",
                    **common,
                    annotations={
                        "summary": f"The rotation of {secret.full_path} isn't confirmed as applied",
                        "description": "Confirm it in Chronowarden once the new version is used everywhere (ADR-021)",
                    },
                )
            )
    return alerts


def vault_unreachable_alert(vault: str, reason: str, error: Optional[str]) -> Alert:
    """A vault Chronowarden can't sync: offline or failing authentication."""
    return Alert(
        "VaultUnreachable",
        {"vault": vault},
        labels={"reason": reason},
        annotations={"summary": f"Chronowarden can't reach vault '{vault}' ({reason})", "description": error or ""},
    )


def audit_event_alert(event: dict[str, Any], secrets: dict[tuple[str, str, str], SecretMetadataResponse]) -> Alert:
    """An event alert from an audit event in `AUDIT_EVENT_ALERTS` (the secret gives its owners and labels)."""
    name = AUDIT_EVENT_ALERTS[event["event_type"]]
    after = json.loads(event["after"]) if event.get("after") else {}
    if name == "ComplianceSnapshotCreated":
        what = after.get("label") or f"{after.get('period')} ({after.get('cadence')})"
        return Alert(
            name,
            {"snapshot": event["subject"].removeprefix("snapshot:")},
            labels={"period": after.get("period") or "", "label": after.get("label") or ""},
            annotations={
                "summary": f"Compliance snapshot {what} was taken",
                "description": f"{after.get('rows')} secret(s), SHA-256 {after.get('sha256')}",
            },
            starts_at=event["timestamp"],
        )
    key = (event["vault_name"], event["engine_id"], event["secret_path"])
    secret = secrets.get(key)
    full_path = "/".join(key)
    if name == "SecretRotated":
        annotations = {
            "summary": f"{full_path} was rotated (version {after.get('current')})",
            "description": "Confirm the rotation once it is applied, if confirmation is required (ADR-021)",
        }
    else:
        annotations = {
            "summary": f"The rotation of {full_path} was confirmed as applied",
            "description": f"Applied at {after.get('applied_at')}",
        }
    return Alert(
        name,
        {**_secret_identity(*key), "event": str(event["id"])},
        labels=_secret_labels(secret) if secret else {},
        annotations=annotations,
        owner_ids=_owner_ids(secret) if secret else (),
        starts_at=event["timestamp"],
    )


def period_ended_alert(cadence: str, period: str, end: str) -> Alert:
    """A reporting period that ended and can be closed with a snapshot."""
    return Alert(
        "CompliancePeriodEnded",
        {"cadence": cadence, "period": period},
        annotations={
            "summary": f"Reporting period {period} ({cadence}) ended",
            "description": "Close it in Compliance to freeze its snapshot and PDF report",
        },
        starts_at=end,
    )
