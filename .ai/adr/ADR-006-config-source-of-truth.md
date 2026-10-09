<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-006: Config is the source of truth for severity

- **Status:** Accepted (retroactive)
- **Date:** 2026-02-08
- **Evidence:** PR #11 (`6b6c075`), `82b165b` (sync overwrites remote metadata), `architecture/integrations.c4`.

## Context

Severity used to come from Vault custom metadata, which let backend state and Chronowarden disagree.

## Decision

Severity resolves from YAML config via the cascade secret → engine → vault → global default. Sync writes the resolved `chronowarden_severity` and `chronowarden_ttl` back to the backend when they differ. `severity: none` means monitor but never rotate (no TTL), and it replaces `chronowarden_enabled`. Secret-level overrides live in config only. These are decisions Q1–Q7 recorded in PR #11: cascade vault → engine → secret, engines listed only when overriding, nested config, secret overrides in config only, config always wins, `severity: none` for disabled secrets, and users can override the built-in profiles.

## Consequences

Manual severity changes via the API (`PATCH /secrets/{id}`) were overwritten on the next sync and conflicted with Q4. That endpoint, the leftover `enabled` field and `chronowarden_enabled` were removed in 0.6.0 (#73, `.ai/specs/implemented/2026-10-09-remove-enabled-flag.md`). Severity values are validated against configured `expiry_profiles`.

## Related files

- [`chronowarden/config.py`](../../chronowarden/config.py)
- [`chronowarden/metadata.py`](../../chronowarden/metadata.py)
- [`config.example.yaml`](../../config.example.yaml)
