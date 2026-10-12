# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Record configuration changes that affect secrets (severity cascade, expiry profiles, policies) in the audit log."""

import json
import logging
from typing import Any

from chronowarden.audit.chain import canonical_json
from chronowarden.config import AppConfig

logger = logging.getLogger("uvicorn.error")

_STATE_KEY = "config"


def secret_affecting_config(config: AppConfig) -> dict[str, Any]:
    """
    Return the parts of the config that decide how secrets are treated, without addresses or credentials.

    Args:
        config: The loaded configuration.

    Returns:
        Expiry profiles, the per-vault severity cascade and, when any are configured, the compliance policies
        (ADR-019). Leaving the key out without policies keeps upgrades from recording a change.
    """
    affecting: dict[str, Any] = {
        "expiry_profiles": {name: profile.model_dump() for name, profile in sorted(config.expiry_profiles.items())},
        "vaults": [
            {
                "name": vault.name,
                "severity": vault.severity,
                "engines": [engine.model_dump() for engine in vault.engines],
            }
            for vault in config.vaults
        ],
    }
    if config.compliance.policies:
        affecting["compliance_policies"] = [policy.model_dump() for policy in config.compliance.policies]
    return affecting


def record_config_change(db: Any, config: AppConfig) -> None:
    """
    Compare the secret-affecting config with the last run and record a `config.changed` event if it differs.

    The first run records `config.baseline`.

    Args:
        db: The Chronowarden database.
        config: The configuration loaded at startup.
    """
    current = secret_affecting_config(config)
    previous_text = db.get_audit_state(_STATE_KEY)
    current_text = canonical_json(current)
    if previous_text == current_text:
        return
    if previous_text is None:
        db.append_audit_event("config.baseline", "config", subject="config", after=current)
    else:
        db.append_audit_event(
            "config.changed", "config", subject="config", before=json.loads(previous_text), after=current
        )
        logger.info("Configuration affecting secrets changed since the last start; recorded in the audit log")
    db.set_audit_state(_STATE_KEY, current_text)
