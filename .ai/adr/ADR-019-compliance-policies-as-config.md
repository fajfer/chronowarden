<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-019: Compliance policies as config, with examples instead of built-in packs

- **Status:** Accepted
- **Date:** 2026-10-11
- **Evidence:** maintainer decisions of 2026-10-10 and 2026-10-11
- **Supersedes:** none

## Context

Organizations answer to different regulators and internal standards. A built-in "KNF" or "PCI DSS" pack would be an
interpretation of law or a standard that Chronowarden would have to maintain and could get wrong.

## Decision

- Policies are defined in `config.yaml` (like severity, ADR-006), strictly validated.
- Rules come from a fixed set evaluated on data Chronowarden has: rotation age, expiry, owner, system, unconfirmed
  rotations. No review-based rules (Chronowarden stores no review state).
- Framework policies (KNF KRI ICT, PCI DSS 4.0, DORA) ship only as **example YAML in the docs**, marked
  non-authoritative.
- A policy editor in the UI waits for authentication (ADR-015).

## Consequences

- Each organization owns its interpretation; examples are a starting point.
- Policy changes are config changes, visible in git and in the audit log.

## Related files

- `chronowarden/config.py`, `chronowarden/compliance/`, `config.example.yaml`
