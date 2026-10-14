# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Alertmanager-compatible webhook payloads (ADR-022). Metadata only: paths, owners, systems, dates."""

from typing import Any, Optional

# What Alertmanager sends as endsAt for an alert that is still firing
ZERO_TIME = "0001-01-01T00:00:00Z"


def build_payload(notification: dict[str, Any], receiver: str, external_url: Optional[str]) -> dict[str, Any]:
    """
    One notification as an Alertmanager webhook body (version 4), with a single alert.

    Args:
        notification: `fingerprint`, `alertname`, `labels`, `annotations`, `status`, `starts_at`, `ends_at`.
        receiver: The receiver name (`owner:<id>` or `default:<name>`).
        external_url: Chronowarden's URL for `externalURL` and `generatorURL`, if configured.
    """
    base = (external_url or "").rstrip("/")
    alert = {
        "status": notification["status"],
        "labels": notification["labels"],
        "annotations": notification["annotations"],
        "startsAt": notification["starts_at"],
        "endsAt": notification["ends_at"] or ZERO_TIME,
        "generatorURL": f"{base}/compliance" if base else "",
        "fingerprint": notification["fingerprint"],
    }
    return {
        "version": "4",
        "groupKey": f"{{}}:{{alertname=\"{notification['alertname']}\"}}",
        "truncatedAlerts": 0,
        "status": notification["status"],
        "receiver": receiver,
        "groupLabels": {"alertname": notification["alertname"]},
        "commonLabels": notification["labels"],
        "commonAnnotations": notification["annotations"],
        "externalURL": base,
        "alerts": [alert],
    }
