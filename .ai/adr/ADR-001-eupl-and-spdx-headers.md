<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-001: EUPL-1.2 licence with SPDX headers

- **Status:** Accepted (retroactive)
- **Date:** 2025-02-20
- **Evidence:** Initial commit `35f8416`; headers across the tree.

## Context

The project needed a licence and a way to state it per file.

## Decision

License the code under EUPL-1.2 (`LICENSE`, `LICENSES/EUPL-1.2.txt`, `pyproject.toml`). Every file carries `SPDX-FileCopyrightText` and `SPDX-License-Identifier: EUPL-1.2` headers in its own comment syntax.

## Consequences

Every new file needs a header; year ranges are updated when stale (root `AGENTS.md`). Files that can't hold comments use a `.license` sidecar.

## Related files

- [`LICENSE`](../../LICENSE)
- [`LICENSES/EUPL-1.2.txt`](../../LICENSES/EUPL-1.2.txt)
- [`pyproject.toml`](../../pyproject.toml)
