<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-011: Generic provider registry

- **Status:** Proposed
- **Date:** 2026-10-09
- **Evidence:** Issue #72; spec `.ai/specs/2026-10-09-generic-provider-registry.md`; PR #26 gap analysis.

## Context

ADR-003 introduced `BaseIntegration`, but nothing enforces it, and `VaultManager`, `VaultConfig` and the `/vault` and `/sync` APIs are Vault-specific. The README roadmap promises "additional backends for public cloud providers".

## Decision

**Not decided yet.** Options to settle in #72:

- Interface: `abc.ABC` vs `typing.Protocol`, and which of `write_secret_metadata`, `discover_engines`, `check_health` and `last_error_kind` become part of it.
- Config: a `type:` key on each backend entry (defaulting to `vault`) vs a separate top-level list per provider type.
- API: keep `/api/v1/vault/*` or rename it to a provider-neutral path (breaking for the frontend; allowed before 1.0).
- Metadata: how providers without custom metadata (e.g. some cloud vaults) store `chronowarden_*` fields.

## Consequences

Once accepted, ADR-003 gets `Superseded by ADR-011`, and the first cloud provider (milestone 1.x) builds on it.

## Related files

- [`chronowarden/integrations/base.py`](../../chronowarden/integrations/base.py)
- [`chronowarden/integrations/manager.py`](../../chronowarden/integrations/manager.py)
- [`chronowarden/config.py`](../../chronowarden/config.py)
