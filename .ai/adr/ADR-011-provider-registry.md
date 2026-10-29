<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-011: Generic provider registry

- **Status:** Accepted
- **Date:** 2026-10-09
- **Evidence:** maintainer decisions of 2026-10-14; issue #72; spec `.ai/specs/implemented/2026-10-09-generic-provider-registry.md`; PR #26 gap analysis.

## Context

ADR-003 introduced `BaseIntegration`, but nothing enforces it, and `VaultManager`, `VaultConfig` and the `/vault` and `/sync` APIs are Vault-specific. The README roadmap promises "additional backends for public cloud providers".

## Decision

Settled by the maintainer on 2026-10-14:

- **Interface:** `BaseIntegration` becomes an `abc.ABC`; `list_secrets`, `get_secret_metadata`,
  `write_secret_metadata`, `discover_engines`, `check_health`, `is_connected`, `connect`, `disconnect`,
  `last_error` and `last_error_kind` are abstract, so a provider missing one fails when it is instantiated.
- **Config:** each backend entry in `vaults:` gets `type:` (`vault` by default, so existing configs load unchanged;
  `openbao`, `azure-key-vault` and `gcp-secret-manager` later).
- **API:** `/api/v1/vault/*` becomes `/api/v1/providers/*` and `/api/v1/sync/vault/{name}` becomes
  `/api/v1/sync/provider/{name}`, with the frontend in the same change; breaking for API users, no shim before 1.0.
- **Metadata:** only providers that can store key/value metadata on each secret are supported, so `chronowarden_*`
  keys always live in the backend (ADR-006). Azure Key Vault (tags) and GCP Secret Manager (labels/annotations)
  qualify; providers without per-secret metadata (e.g. GitLab CI variables) are out of scope.
- The registry is proven with **Azure Key Vault and GCP Secret Manager**, each in its own spec after the refactor.

## Consequences

Once accepted, ADR-003 gets `Superseded by ADR-011`, and the first cloud provider (milestone 1.x) builds on it.

## Related files

- [`chronowarden/integrations/base.py`](../../chronowarden/integrations/base.py)
- [`chronowarden/integrations/manager.py`](../../chronowarden/integrations/manager.py)
- [`chronowarden/config.py`](../../chronowarden/config.py)
