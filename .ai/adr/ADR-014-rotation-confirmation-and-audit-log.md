<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-014: Rotation confirmation and audit log

- **Status:** Proposed
- **Date:** 2026-10-09
- **Evidence:** Issues #24, #18; README compliance goals (PCI DSS 4.0, DORA).

## Context

A fresh secret in a vault isn't proof that it was applied where it is used (#18). #24 asks for an explicit confirmation via API/UI and an audit log recording when a new secret appeared, when it was notified, and when and by whom the rotation was confirmed. The rotation timer keeps running from when the new secret appeared.

## Decision

**Not decided yet.** Open points:

- Storage: an append-only table in the SQLite DB (ADR-005) vs an external sink (log shipping, SIEM).
- Identity of "who confirmed": compliance ships before authentication (ADR-010), so the first version records free
  text. ADR-015 replaces it with the authenticated user.
- Tamper evidence: is append-only enough for auditors, or is hash-chaining or an export needed?
- Retention and export format, which reports (milestone 0.8) will use.

## Consequences

Planned for milestone 0.7 (compliance). Reports and compliance evidence build on this log, which also records
system and owner assignment changes (ADR-010). If it lives in SQLite, it tightens the single-replica constraint of ADR-005.

## Related files

- [`chronowarden/database.py`](../../chronowarden/database.py)
- [`chronowarden/metadata.py`](../../chronowarden/metadata.py)
