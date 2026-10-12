<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Headless image without the UI or Typst

- **Status:** approved
- **Date:** 2026-10-12
- **Issue:** #48

## Goal

Operators who only use the API, or who run Chronowarden as a Kubernetes `CronJob`, can deploy a `headless` image
with no frontend and no Typst. It is smaller and has less to patch, runs the same API and sync, and says clearly
when a feature it leaves out (the UI, PDF reports) is asked for.

## Non-goals

- Removing anything from the default production image: it keeps the UI and PDF reports.
- The in-process scheduled sync and the one-shot sync command themselves (ADR-013); this spec only packages and
  documents them for the headless image once they exist.
- A different database or state store for CronJob runs (SQLite on a PVC as today).

## Scope

`Dockerfile`, `.github/workflows/docker.yaml`, `pyproject.toml` (optional `reports` extra), `chronowarden/app.py`
(SPA serving, `/info`), `chronowarden/compliance/report.py`, `chronowarden/api/compliance.py`, `deploy/`,
`README.md`, `CHANGELOG.md`, `.ai/adr/`.

## Load

- [root AGENTS.md](../../AGENTS.md)
- [deploy](../../deploy/AGENTS.md), [core](../../chronowarden/AGENTS.md),
  [compliance](../../chronowarden/compliance/AGENTS.md)
- [ADR-008](../adr/ADR-008-container-and-deployment-targets.md), [ADR-013](../adr/ADR-013-in-process-and-headless-sync.md),
  [ADR-020](../adr/ADR-020-pdf-reports-with-typst.md)

## ADRs affected

New **ADR-024 Headless image without the UI or Typst**, extending ADR-008 (a third image target) and ADR-020
(Typst becomes the optional `reports` extra; the default image still installs it). ADR-013 already anticipates a
headless image that drops the frontend stage.

## Design

- **Typst is optional.** `typst` moves to an extra, `chronowarden[reports]`. `report.py` imports it lazily;
  without it, `GET /compliance/snapshots/{id}/report.pdf` answers **501** with a message naming the image to use.
  Snapshots, JSON and CSV exports, and policy evaluation work the same in both images.
- **The UI is optional.** Without a frontend build, `/` and other non-API paths answer 404 (no SPA fallback),
  and `/api` keeps working. `GET /api/v1/info` reports `features: {ui, pdf_reports}`.
- **Image target `headless`** in the `Dockerfile`: the same distroless base and non-root user as `production`,
  without the frontend build stage and without the `reports` extra. CI publishes it as `:<tag>-headless` for
  amd64 and arm64 with the same cosign signature, SLSA provenance and SBOM attestations as the production image.
- **CronJob example** in `deploy/kubernetes/` using the headless image and the one-shot sync from ADR-013, on the
  same PVC as the server or on its own.

## Tasks

| # | Task | Load | Done when | Status | Commit |
|---|---|---|---|---|---|
| 1 | Write ADR-024; mark ADR-008 and ADR-020 as extended in their text and the index | [.ai/adr](../adr/README.md), ADR-008, ADR-020 | ADR-024 Accepted by the maintainer and indexed | todo | |
| 2 | Move `typst` to the `reports` extra; lazy import; 501 from `report.pdf` without it; `features` in `/info` | `pyproject.toml`, `chronowarden/compliance/report.py`, `chronowarden/api/compliance.py`, `chronowarden/app.py` | Tests run with and without Typst importable (monkeypatched) | todo | |
| 3 | No SPA fallback when the frontend build is missing; API unaffected | `chronowarden/app.py`, `tests/test_app.py` | Test: no build dir → `/` is 404, `/api/v1/health` is 200 | todo | |
| 4 | `headless` Dockerfile target; the production target installs `.[reports]` | `Dockerfile`, deploy | Both targets build for amd64 and arm64; headless image has no `typst` and no `frontend/build` | todo | |
| 5 | CI: build, smoke-test (health 200, `/` 404, `report.pdf` 501), sign, attest and push `:<tag>-headless` | `.github/workflows/docker.yaml` | A tag build publishes a verified headless image | todo | |
| 6 | Kubernetes CronJob example and Compose snippet for the headless image (after ADR-013's one-shot sync exists) | deploy | Manifests validate with `kubectl kustomize` | todo | |
| 7 | README (image variants, sizes), `deploy/AGENTS.md`, CHANGELOG, architecture note if the model changes | [architecture](../../architecture/AGENTS.md), deploy | Docs match | todo | |

## Validation

`uv run pytest`, black, ruff, `npm run check`, `check_agents_docs.py`, `docker build` of all three targets,
`cosign verify` and `slsa-verifier verify-image` on a published `-headless` image.

## Decisions (maintainer, 2026-10-12)

- Tag: `:<tag>-headless` on the same image name, like `-dev`.
- Ships with 0.8, together with the one-shot sync ([scheduled sync spec](2026-10-12-scheduled-sync.md)).
- `report.pdf` stays in the headless OpenAPI schema and answers 501.
