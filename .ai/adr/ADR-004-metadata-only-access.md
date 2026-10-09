<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-004: Metadata-only access to secret backends

- **Status:** Accepted (retroactive)
- **Date:** 2026-02-07
- **Evidence:** `37b490e` (capabilities reduced to metadata), `ac38af9` (secret-value endpoint deleted), README "Vault Permissions".

## Context

README: built "with focus on compliance for financial institutions (PCI DSS 4.0, DORA)" and "Secure - Never reads actual secret values, only metadata".

## Decision

Chronowarden never reads secret values. It lists and reads KV v2 metadata and writes only its own `chronowarden_*` custom metadata. The required Vault policy is limited to `+/metadata/*` (list, read, update), `+/metadata` (list) and `sys/mounts` (read).

## Consequences

No endpoint returns secret values; `VaultIntegration.get_secret` stays unexposed. Changing the policy users must grant needs the user's approval.

## Related files

- [`README.md`](../../README.md)
- [`chronowarden/integrations/vault.py`](../../chronowarden/integrations/vault.py)
- [`chronowarden/api/vault.py`](../../chronowarden/api/vault.py)
