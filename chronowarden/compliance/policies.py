# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Evaluate compliance policies from config against enriched secrets (ADR-019). No I/O."""

from datetime import datetime, timedelta
from fnmatch import fnmatchcase
from typing import Any

from chronowarden.config import CompliancePolicy, ControlScope, ControlThresholds, PolicyControl, PolicyRule
from chronowarden.metadata import parse_date
from chronowarden.models.secret import SecretMetadataResponse

RAG_ORDER = ("green", "amber", "red")


def in_control_scope(secret: SecretMetadataResponse, scope: ControlScope) -> bool:
    """Whether a secret falls in a control's scope; empty lists and null match everything."""
    return (
        (not scope.vaults or secret.vault_name in scope.vaults)
        and (not scope.engines or secret.engine_id in scope.engines)
        and (not scope.systems or (secret.system is not None and secret.system.name in scope.systems))
        and (not scope.severities or secret.severity in scope.severities)
        and (not scope.paths or any(fnmatchcase(secret.full_path, pattern) for pattern in scope.paths))
        and (scope.privileged is None or secret.privileged == scope.privileged)
    )


def fails(secret: SecretMetadataResponse, rule: PolicyRule, now: datetime) -> bool:
    """Whether a secret breaks a rule at `now`."""
    if rule.type == "max_rotation_age":
        rotated = parse_date(secret.updated_time) if secret.updated_time else None
        return rotated is None or now - rotated > timedelta(days=rule.days)
    if rule.type == "not_expired":
        return secret.status.value == "expired"
    if rule.type == "has_owner":
        return not secret.effective_owners
    if rule.type == "has_system":
        return secret.system is None
    return secret.confirmation_overdue


def rag(failing: int, total: int, thresholds: ControlThresholds) -> str:
    """
    The control's status from its failing count.

    Counts compare the number of failing secrets, percentages the share of those in scope. Without thresholds,
    one failure is red. Nothing in scope is green.
    """
    if failing == 0 or total == 0:
        return "green"
    pct = failing * 100 / total
    if all(value is None for value in (thresholds.amber, thresholds.red, thresholds.amber_pct, thresholds.red_pct)):
        return "red"
    if (thresholds.red is not None and failing >= thresholds.red) or (
        thresholds.red_pct is not None and pct >= thresholds.red_pct
    ):
        return "red"
    if (thresholds.amber is not None and failing >= thresholds.amber) or (
        thresholds.amber_pct is not None and pct >= thresholds.amber_pct
    ):
        return "amber"
    return "green"


def worst(statuses: list[str]) -> str:
    """The worst RAG status of a list (green when empty)."""
    return max(statuses, key=RAG_ORDER.index, default="green")


def evaluate_control(control: PolicyControl, secrets: list[SecretMetadataResponse], now: datetime) -> dict[str, Any]:
    """
    Evaluate one control.

    Returns:
        The control's definition, counts, status and failing secrets (full path and owner names, never values).
    """
    in_scope = [secret for secret in secrets if in_control_scope(secret, control.scope)]
    failing = sorted((s for s in in_scope if fails(s, control.rule, now)), key=lambda s: s.full_path)
    return {
        "id": control.id,
        "title": control.title,
        "source": control.source,
        "rule": control.rule.model_dump(),
        "thresholds": control.thresholds.model_dump(exclude_none=True),
        "in_scope": len(in_scope),
        "failing": len(failing),
        "status": rag(len(failing), len(in_scope), control.thresholds),
        "failing_secrets": [
            {"full_path": s.full_path, "owners": sorted(owner.name for owner in s.effective_owners)} for s in failing
        ],
    }


def evaluate_policy(policy: CompliancePolicy, secrets: list[SecretMetadataResponse], now: datetime) -> dict[str, Any]:
    """
    Evaluate a policy against the secrets still in the backend (removed ones are skipped).

    The result holds the policy's definition too, so a snapshot can be reported on after the config changes.
    """
    present = [secret for secret in secrets if secret.removed_at is None]
    controls = [evaluate_control(control, present, now) for control in policy.controls]
    return {
        "id": policy.id,
        "name": policy.name,
        "framework": policy.framework,
        "version": policy.version,
        "status": worst([control["status"] for control in controls]),
        "counts": {status: sum(1 for c in controls if c["status"] == status) for status in RAG_ORDER},
        "controls": controls,
    }
