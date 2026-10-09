<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-009: Start with offline vaults and reconnect in the background

- **Status:** Accepted (retroactive)
- **Date:** 2026-03-18
- **Evidence:** `6fa3f3f`, `81e61e1`, `542888f`, `49344f8`, `80be914`; issues #7, #44, PR #49; open follow-up #59.

## Context

Commit `6fa3f3f`: "Allow vaults to reconnect and allow Chronowarden to start with offline vaults".

## Decision

Connection failures are classified (`auth`, `offline`, `vault`, `unexpected`). Non-auth failures are retried by a background loop every `vault_reconnect_interval` s, for at most `vault_reconnect_max_attempts` cycles. Auth failures are not retried automatically. AppRole tokens are regenerated on reconnect.

## Consequences

`/vault/health` reports per-vault status; `INTEGRATION_HEALTH` reflects it. A manual sync restarts the loop.

## Related files

- [`chronowarden/integrations/manager.py`](../../chronowarden/integrations/manager.py)
- [`chronowarden/integrations/vault.py`](../../chronowarden/integrations/vault.py)
- [`chronowarden/api/sync.py`](../../chronowarden/api/sync.py)
