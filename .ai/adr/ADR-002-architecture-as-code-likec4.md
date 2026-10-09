<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-002: Architecture as code in LikeC4

- **Status:** Accepted (retroactive)
- **Date:** 2025-02-20
- **Evidence:** `architecture/main.c4` in initial commit `35f8416`; the architecture rule in `AGENTS.md`.

## Context

Not recorded beyond `AGENTS.md`, which stores the architecture as code and points agents at an architecture MCP endpoint.

## Decision

Model the system in LikeC4 DSL under `architecture/`. Changes that affect the architecture update the model in the same change.

## Consequences

Agents consult the architecture MCP endpoint or the `.c4` files. No automated validation runs today (see `architecture/AGENTS.md`).

## Related files

- [`architecture/main.c4`](../../architecture/main.c4)
- [`architecture/specification.c4`](../../architecture/specification.c4)
- [`architecture/integrations.c4`](../../architecture/integrations.c4)
