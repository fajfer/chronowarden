<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-007: SvelteKit SPA served by FastAPI, API under /api/v1

- **Status:** Accepted (retroactive)
- **Date:** 2026-02-07
- **Evidence:** `53c4a90` (SvelteKit), `fe68be8` (adapter-static + Dockerfile), `2e1d3b7` (`/api/v1` + SPA catch-all), `1268ede` (PR #56).

## Context

Not recorded. Commit `2e1d3b7`: "Move root API path to /api/v1, render everything else as frontend".

## Decision

Build the frontend with SvelteKit + `adapter-static` (fallback `index.html`, `ssr = false`). FastAPI serves `frontend/build` and routes every non-API path to the SPA; the REST API lives under `/api/v1`.

## Consequences

One container and one port. API routes must be registered before the SPA catch-all. The frontend API base is configurable via `VITE_API_BASE_URL`.

## Related files

- [`chronowarden/app.py`](../../chronowarden/app.py)
- [`frontend/vite.config.ts`](../../frontend/vite.config.ts) (adapter config; `svelte.config.js` until SvelteKit 3)
- [`frontend/src/lib/api/client.ts`](../../frontend/src/lib/api/client.ts)
