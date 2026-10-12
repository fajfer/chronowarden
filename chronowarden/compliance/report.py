# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""PDF reports of compliance snapshots with Typst (ADR-020)."""

import json
from collections import Counter
from pathlib import Path
from typing import Any

import typst

from chronowarden.timestamps import utc_timestamp

TEMPLATE = Path(__file__).with_name("report.typ")

_STATUS_LABELS = (("ok", "Healthy"), ("warning", "Warning"), ("expired", "Overdue"), ("no_ttl", "No TTL"))

_RULE_TEXT = {
    "not_expired": "Not past its TTL",
    "has_owner": "Has an owner (its own or its system's)",
    "has_system": "Assigned to a system",
    "rotation_confirmed": "Rotations confirmed as applied within the grace period",
}


def rule_text(rule: dict[str, Any]) -> str:
    """A rule in words, e.g. 'Rotated within the last 90 days'."""
    if rule["type"] == "max_rotation_age":
        return f"Rotated within the last {rule['days']} days"
    return _RULE_TEXT[rule["type"]]


def threshold_text(thresholds: dict[str, Any]) -> str:
    """When a control turns amber or red, in words."""
    parts = []
    for status in ("amber", "red"):
        if thresholds.get(status) is not None:
            parts.append(f"{status} from {thresholds[status]} failing")
        if thresholds.get(f"{status}_pct") is not None:
            parts.append(f"{status} from {thresholds[f'{status}_pct']:g}% failing")
    return ("; ".join(parts) if parts else "red from 1 failing").capitalize()


def scope_text(scope: dict[str, Any]) -> str:
    """A snapshot scope in words."""
    parts = [f"{name}: {', '.join(scope[name])}" for name in ("vaults", "engines", "systems") if scope.get(name)]
    if scope.get("privileged_only"):
        parts.append("privileged secrets only")
    return "; ".join(parts) or "All secrets"


def report_data(snapshot: dict[str, Any], generator: str) -> dict[str, Any]:
    """
    The data the template renders, from a stored snapshot.

    Args:
        snapshot: The snapshot row with its `content` (the canonical JSON document).
        generator: Who generated the report, e.g. "Chronowarden 0.7.2".

    Returns:
        Plain JSON-able data; every text the template shows is in here.
    """
    document = json.loads(snapshot["content"])
    statuses = Counter(row["status"] for row in document["rows"])
    title = "Secret rotation compliance report"
    subtitle = document.get("period") or document.get("label") or f"Snapshot {snapshot['id']}"
    return {
        "title": title,
        "subtitle": subtitle,
        "generator": generator,
        "generated_at": utc_timestamp(),
        "snapshot": {
            "id": snapshot["id"],
            "created_at": document["created_at"],
            "label": document.get("label"),
            "period": f"{document['period']} ({document['cadence']})" if document.get("period") else None,
            "supersedes": str(document["supersedes"]) if document.get("supersedes") is not None else None,
            "scope_text": scope_text(document.get("scope") or {}),
            "row_count": len(document["rows"]),
            "sha256": snapshot["sha256"],
            "audit": document["audit"],
            "export_path": f"GET /api/v1/compliance/snapshots/{snapshot['id']}.json",
        },
        "inventory": [{"label": label, "count": statuses.get(status, 0)} for status, label in _STATUS_LABELS],
        "policies": [
            {
                **policy,
                "framework_text": " ".join(part for part in (policy.get("framework"), policy.get("version")) if part)
                or None,
                "controls": [
                    {
                        **control,
                        "rule_text": rule_text(control["rule"]),
                        "threshold_text": threshold_text(control["thresholds"]),
                    }
                    for control in policy["controls"]
                ],
            }
            for policy in document.get("policies", [])
        ],
    }


def render_report(snapshot: dict[str, Any], generator: str) -> bytes:
    """
    Render a snapshot's report as PDF/A-2b with Typst's embedded fonts only (ADR-020).

    Blocking (Typst compiles in-process); call it through `asyncio.to_thread` from async code.
    """
    data = json.dumps(report_data(snapshot, generator), ensure_ascii=False)
    return typst.compile(str(TEMPLATE), sys_inputs={"data": data}, ignore_system_fonts=True, pdf_standards=["a-2b"])
