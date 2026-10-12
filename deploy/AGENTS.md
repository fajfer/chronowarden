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
- `../.github/workflows/`: `docker.yaml` (both targets, amd64 + arm64, pushed except on PRs; on `v*` tags: cosign
  signature, SLSA provenance, image SBOMs), `release.yaml` (`v*` tags: wheel, sdist, source SBOMs, provenance, notes
  from `scripts/release_notes.sh`; `-rc.N` = pre-release), `ci.yaml`, `scorecard.yml`, `zizmor.yaml`,
  `agents-docs.yaml`, `cflite_pr.yml` / `cflite_batch.yml` (ClusterFuzzLite: 5 min on code PRs, 30 min weekly); `ci.yaml` runs
  `pytest -m integration` too (testcontainers, images and seeding in `devenv/`).

## Contracts

- Image: listens on `0.0.0.0:8000`; `CHRONOWARDEN_CONFIG=/data/config.yaml` by default; Python 3.13; the production
  image has no shell.
- Build inputs are pinned: every `FROM` by digest (tag kept beside it), Python dependencies from the committed
  `uv.lock` (`uv sync --locked --no-dev --no-editable`, uv from a pinned image). Dependabot updates the digests,
  `uv.lock` and `frontend/package-lock.json` weekly; Python minor/major and Node major updates are ignored.
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
  The `python:3.13.*-slim` tags, the distroless image and the hard-coded `python3.13/site-packages` path must
  change together.
- `docker.yaml` smoke-tests the production image (health + path traversal) before pushing; 30-minute timeout.
- Fuzzing: atheris harnesses in `fuzz/` (`fuzz_*.py`, each asserts its function's contract), built by
  `.clusterfuzzlite/` on the OSS-Fuzz builder, which runs **Python 3.11** (the project declares 3.12+):
  `build.sh` installs the `uv.lock` versions with uv (hash-pinned in `.clusterfuzzlite/requirements.txt`) and the
  package with `--ignore-requires-python`. Code the fuzzers import must keep running on 3.11.
- The SLSA generator is referenced by tag (`@v2.1.0`; the verifier trusts only tagged releases, ADR-018): the one
  `zizmor: ignore[unpinned-uses]`. A release tag fails unless `pyproject.toml` and `CHANGELOG.md` match it.
- `frontend-builder` runs on `$BUILDPLATFORM`: its output is arch-independent, and `npm ci` under QEMU arm64
  emulation hung intermittently (v0.6.2 tag build). Keep it native.
- `dev-setup.py` (podman, else docker) keeps a `config.yaml` it didn't write; `devenv/` images are fully qualified.
- `deployment.yaml` pins the production image (`ghcr.io/fajfer/chronowarden:v0.7.1`); bump the tag with each
  release.

## Related ADRs

[ADR-007](../.ai/adr/ADR-007-sveltekit-spa-served-by-fastapi.md),
[ADR-008](../.ai/adr/ADR-008-container-and-deployment-targets.md)

## Validate

`docker build -t chronowarden:test .` and `docker build --target dev -t chronowarden:test-dev .`;
`kubectl kustomize deploy/kubernetes` to render the manifests.
