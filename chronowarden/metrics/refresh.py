# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Set the per-secret metrics from the enriched secrets (#71)."""

from collections import Counter
from typing import Any

from chronowarden.metadata import parse_date
from chronowarden.metrics.prometheus import (
    SECRET_CONFIRMATION_OVERDUE,
    SECRET_EXPIRY_TIMESTAMP,
    SECRET_LAST_ROTATION_TIMESTAMP,
    SECRETS,
)
from chronowarden.models.secret import SecretMetadataResponse

_PER_SECRET = (SECRET_EXPIRY_TIMESTAMP, SECRET_LAST_ROTATION_TIMESTAMP, SECRET_CONFIRMATION_OVERDUE)


def set_secret_metrics(secrets: list[SecretMetadataResponse]) -> None:
    """
    Replace every secret series with the given secrets, so removed secrets lose theirs.

    Removed secrets (still cached until purged) are left out.
    """
    present = [secret for secret in secrets if secret.removed_at is None]
    for gauge in (SECRETS, *_PER_SECRET):
        gauge.clear()
    for (vault, status), count in Counter((s.vault_name, s.status.value) for s in present).items():
        SECRETS.labels(vault=vault, status=status).set(count)
    for secret in present:
        labels = {
            "vault": secret.vault_name,
            "engine": secret.engine_id,
            "secret_path": secret.secret_path,
            "severity": secret.severity,
        }
        if secret.ttl_date is not None:
            SECRET_EXPIRY_TIMESTAMP.labels(**labels).set(secret.ttl_date.timestamp())
        rotated = parse_date(secret.updated_time) if secret.updated_time else None
        if rotated is not None:
            SECRET_LAST_ROTATION_TIMESTAMP.labels(**labels).set(rotated.timestamp())
        SECRET_CONFIRMATION_OVERDUE.labels(**labels).set(1 if secret.confirmation_overdue else 0)


def refresh_secret_metrics(database: Any, config: Any) -> None:
    """Recompute the secret metrics from the cache when metrics are enabled (ADR-022); a no-op otherwise."""
    if not config.metrics.enabled:
        return
    from chronowarden.api.secrets import enriched_secrets  # the API's status and confirmation logic

    set_secret_metrics(enriched_secrets(database, config))
