<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-006: Config is the source of truth for severity

- **Status:** Accepted (retroactive)
- **Date:** 2026-02-08
- **Evidence:** `6b6c075`, `82b165b` (sync overwrites remote metadata), `architecture/integrations.c4`.

## Context

Severity used to come from Vault custom metadata, which let backend state and Chronowarden disagree.

## Decision

Severity resolves from YAML config via the cascade secret → engine → vault → global default. Sync writes the resolved `chronowarden_severity` and `chronowarden_ttl` back to the backend when they differ. `severity: none` means monitor but never rotate (no TTL). It complements `chronowarden_enabled`, which turns tracking off entirely.

## Consequences

Manual severity changes via the API are overwritten on the next sync unless config agrees. Severity values are validated against configured `expiry_profiles`.

## Related files

- [`chronowarden/config.py`](../../chronowarden/config.py)
- [`chronowarden/metadata.py`](../../chronowarden/metadata.py)
- [`config.example.yaml`](../../config.example.yaml)
