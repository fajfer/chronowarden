<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# frontend: SvelteKit SPA

## Purpose

Dashboard UI for secret health, owners, vaults and sync. It is built to static files with `adapter-static`
(fallback `index.html`) and served by FastAPI from `frontend/build`
([ADR-007](../.ai/adr/ADR-007-sveltekit-spa-served-by-fastapi.md)).

## Files

- `vite.config.ts`: Vite plugins and the SvelteKit 3 options, including the `adapter-static` config (`build/`,
  fallback `index.html`). There is no `svelte.config.js` since SvelteKit 3 (#79). `tsconfig.json` extends
  `$app/tsconfig`.
- `src/lib/api/`: `client.ts` (`apiGet/apiPost/apiPatch/...`, `ApiError`), plus one file per backend router
  (`secrets.ts`, `sync.ts`, `vaults.ts`, `owners.ts`).
- `src/lib/stores/`: `secrets` (list, loading, error, `secretStats`), `filters`, `sync` (+ toasts), `theme`, `auth`.
- `src/lib/types/`: TypeScript mirrors of backend models, re-exported from `types/index.ts`.
- `src/lib/components/`: `Filters`, `SecretModal`, `OwnerModal`, `StatusBadge`, `ExpiryHorizon`, `Navbar`,
  `Sidebar`, …
- `src/lib/utils/`: `dateFormat.ts`, `statusColor.ts` (status → label and colour).
- `src/routes/`: `/` dashboard, `/secrets`, `/vaults`, `/sync`, `/settings`, `/login`; `+layout.ts` sets
  `ssr = false`.
- `static/`: logos and mascots per theme. `mockups/`: standalone HTML mockups the UI was built from (`4ee2142`).

## Contracts

- API base: `VITE_API_BASE_URL`, default `/api/v1`. All calls go through `client.ts`.
- Types in `src/lib/types/` mirror backend models; the rule is in [models](../chronowarden/models/AGENTS.md).
  `SecretStatus` = `'expired' | 'warning' | 'ok' | 'no_ttl'`.
- Theme: a theme the user picked in Settings (`setTheme`, stored in `localStorage` as `chronowarden_theme`) wins;
  otherwise `initTheme` uses `default_theme` from `GET /api/v1/info` (backend `ui.default_theme`, then
  `CHRONOWARDEN_THEME`, #57). Only `setTheme` writes to `localStorage`. Theme CSS overrides live in `src/app.css` under `[data-theme="bison"]`.
- `localStorage` access is wrapped in try/catch and failures are ignored (`014f9e2`).

## How to

- **Import shared code** as `#lib/<path>.js` (e.g. `#lib/stores/theme.js`): the `.js` extension resolves to the
  `.ts` file. `#lib` is declared in `package.json` `imports`; the old `$lib` alias no longer exists.
- **Call a new endpoint**: add a typed function in the matching `src/lib/api/*.ts` (doc comment with method and
  path), add or extend the type in `src/lib/types/`.
- **Add a theme**: add an entry to `THEME_DEFINITIONS` in `stores/theme.ts` and its ID to `THEME_IDS` in
  `chronowarden/config.py`, assets to `static/`, and `[data-theme="<id>"]` overrides to `app.css`.
- **Add a page**: `src/routes/<name>/+page.svelte`, plus a `{ href, label }` entry in the link groups in
  `components/Sidebar.svelte`.

## Gotchas

- The secrets table filters **client-side** in `routes/secrets/+page.svelte` (`filteredSecrets`) over the full
  `secrets` store. `loadSecrets()` calls `fetchSecrets()` with no params, so the backend query filters are unused
  here. A filter bug is usually in that `$derived.by` block or in `stores/filters.ts`.
- `stores/auth.ts` is a placeholder: there is no auth backend, and it defaults to authenticated.
- Svelte 5 runes (`$derived`, `$state`) are used in pages; stores use `svelte/store`.
- `npm run check` currently reports 0 errors and 6 warnings; don't add new ones.
- Don't edit `build/` or `.svelte-kit/`; they are generated.
- Regenerate `package-lock.json` with the npm the build uses (Node 22, see `Dockerfile` and `ci.yaml`), e.g.
  `docker run --rm -v $PWD:/w -w /w node:22-alpine npm install --package-lock-only`. A lockfile written by a newer npm
  can drop optional entries and make `npm ci` fail in Docker and CI.
- Open UI items: PR #60 TODOs:
  ExpiryHorizon stacks secrets over 90 days (hide them past 100), remove the navbar theme switcher, larger mascot,
  clickable severities; hat insignia vs hamburger icon (#47).

## Related ADRs

[ADR-007](../.ai/adr/ADR-007-sveltekit-spa-served-by-fastapi.md)

## Validate

`cd frontend && npm run check` (types). Run the UI with `npm run dev`; it needs the backend for data.
