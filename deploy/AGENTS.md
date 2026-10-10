<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# deploy: container image, Compose, Kubernetes, CI

## Purpose

How Chronowarden is built and run: the multi-stage `Dockerfile` (repo root), a Compose example
(`deploy/compose/`), bare Kubernetes manifests with kustomize (`deploy/kubernetes/`), and the GitHub workflows
(`.github/`). See [ADR-008](../.ai/adr/ADR-008-container-and-deployment-targets.md).

## Files

- `../Dockerfile`: `frontend-builder` (node:22-alpine, `npm ci && npm run build`) → `backend-builder` (venv,
  `pip install .`) → `dev` target (shell, `--reload`) and `production` (default target,
  `gcr.io/distroless/python3-debian13:nonroot`).
- `compose/config.yaml`: example config with the Compose service snippet in comments.
- `kubernetes/`: `deployment.yaml`, `service.yaml` (ClusterIP :8000), `pvc.yaml` (1Gi RWO), `kustomization.yaml`
  (namespace `chronowarden`; ingress and config Secret are left to the user).
- `../config.example.yaml`: the full config reference ([core](../chronowarden/AGENTS.md)).
- `../.github/workflows/`: `docker.yaml` (builds both targets for amd64 and arm64; pushes to `ghcr.io` except on PRs),
  `ci.yaml` (black, ruff, pytest, `npm run check`), `scorecard.yml`, `zizmor.yaml`,
  `agents-docs.yaml`.

## Contracts

- Image: listens on `0.0.0.0:8000`; `CHRONOWARDEN_CONFIG=/data/config.yaml` by default; Python 3.13
  (`PYTHON_VERSION` build arg); the production image has no shell.
- Kubernetes: config comes from Secret `chronowarden-config` mounted at `/etc/chronowarden/config.yaml`;
  `workingDir: /app/data` on the PVC (so `chronowarden.db` persists); runs as UID 1000, non-root, all capabilities
  dropped; liveness/readiness on `/api/v1/health`.
- Image tags: the git ref name; PRs get `pr-<number>`; the dev target gets a `-dev` suffix.
- Custom CAs: mount a directory and set `ca_certs_dir` (commented examples in `compose/config.yaml`, `deployment.yaml`
  and `kustomization.yaml`).
- Workflow actions are pinned by commit SHA with a version comment; `persist-credentials: false` on checkout
  (zizmor findings fixed in `a53c13a`).

## How to

- **New env var or config key for deployments**: document it in `config.example.yaml` and in the relevant
  manifest or comment here; keep the Compose and Kubernetes examples consistent.
- **Change the image**: keep both `dev` and `production` targets working; `docker.yaml` builds both.
- **New workflow**: top-level `permissions: {}` (or minimal), SHA-pinned actions, `persist-credentials: false`.

## Gotchas

- The DB file is written to the process working directory. In Docker, mount it as `/app/chronowarden.db`
  (README); in Kubernetes, the PVC is the working directory.
- Production crashed when the distroless Python differed from the builder's (`pydantic_core` import error, PR #17).
  `PYTHON_VERSION`, the distroless tag and the hard-coded `python3.13/site-packages` path must change together.
- `docker.yaml` has no smoke test that starts the built image (proposed in PR #17, not merged).
- Planned: headless image without the frontend, e.g. for a CronJob (#48); `dev-setup.py` rework with podman and
  testcontainers (#78). Cleanup exists: `dev-setup.py --cleanup` (#31).
- `deployment.yaml` uses the image `ghcr.io/fajfer/chronowarden:main-dev` (the dev target).

## Related ADRs

[ADR-007](../.ai/adr/ADR-007-sveltekit-spa-served-by-fastapi.md),
[ADR-008](../.ai/adr/ADR-008-container-and-deployment-targets.md)

## Validate

`docker build -t chronowarden:test .` and `docker build --target dev -t chronowarden:test-dev .`;
`kubectl kustomize deploy/kubernetes` to render the manifests.
