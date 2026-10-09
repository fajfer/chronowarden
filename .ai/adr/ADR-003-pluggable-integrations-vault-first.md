<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-003: Pluggable secret-backend integrations, Vault first

- **Status:** Accepted (retroactive)
- **Date:** 2026-02-07
- **Evidence:** `28a5a44` (hvac), `ff683ba` (`integrations/base.py`, `vault.py`), README Features/Roadmap; PR #26 gap analysis ("no provider abstraction").

## Context

Chronowarden aims at vendor neutrality (README: "Connect to multiple backends"; roadmap: public-cloud vaults). The first target was HashiCorp Vault, with OpenBao API compatibility.

## Decision

Define a provider interface `BaseIntegration` (`connect`, `disconnect`, `is_connected`, `list_secrets`, `get_secret_metadata`, `get_secret`) and implement `VaultIntegration` on `hvac`. `VaultManager` holds one connection per configured vault.

## Consequences

Only Vault/OpenBao is supported. `BaseIntegration` is not an ABC, and `VaultManager`, `VaultConfig` and the API are Vault-specific, so a second provider needs the generic provider registry spec first (`.ai/specs/2026-10-09-generic-provider-registry.md`). `models/engine.py` reserves future engine kinds.

## Related files

- [`chronowarden/integrations/base.py`](../../chronowarden/integrations/base.py)
- [`chronowarden/integrations/vault.py`](../../chronowarden/integrations/vault.py)
- [`chronowarden/integrations/manager.py`](../../chronowarden/integrations/manager.py)
