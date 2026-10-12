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

- `../Dockerfile`: `frontend-builder` (node:22-alpine, `npm ci && npm run build`) → `backend-builder` (`.venv`
  with the `reports` extra, `.venv-headless` without) → `dev` (shell, `--reload`), `headless` (distroless, no UI,
  no Typst; ADR-024) and `production` (default target, last; `gcr.io/distroless/python3-debian13:nonroot`).
- `compose/config.yaml`: example config with the Compose service snippet in comments.
- `kubernetes/`: `deployment.yaml`, `service.yaml` (ClusterIP :8000), `pvc.yaml` (1Gi RWO), `kustomization.yaml`
  (namespace `chronowarden`; ingress and config Secret are left to the user), `cronjob-sync.yaml` (optional,
  headless `python -m chronowarden sync`).
- `../config.example.yaml`: the full config reference ([core](../chronowarden/AGENTS.md)).
- `../.github/workflows/`: `docker.yaml` (three targets, amd64 + arm64, pushed except on PRs; `v*` tags: cosign,
  SLSA provenance and SBOMs for production and headless), `release.yaml` (`v*`: wheel, sdist, source SBOMs,
  provenance, notes; `-rc.N` = pre-release), `ci.yaml` (also `pytest -m integration`, `devenv/`), `scorecard.yml`,
  `zizmor.yaml`, `agents-docs.yaml`, `cflite_pr.yml` / `cflite_batch.yml` (ClusterFuzzLite).

## Contracts

- Image: listens on `0.0.0.0:8000`; `CHRONOWARDEN_CONFIG=/data/config.yaml` by default; Python 3.13; the production
  image has no shell.
- Build inputs are pinned: every `FROM` by digest (tag kept beside it), Python dependencies from the committed
  `uv.lock` (`uv sync --locked --no-dev --no-editable`, uv from a pinned image). Dependabot updates the digests,
  `uv.lock` and `frontend/package-lock.json` weekly; Python minor/major and Node major updates are ignored.
- Kubernetes: config comes from Secret `chronowarden-config` mounted at `/etc/chronowarden/config.yaml`;
  `workingDir: /app/data` on the PVC (so `chronowarden.db` persists); runs as UID 1000, non-root, all capabilities
  dropped; liveness/readiness on `/api/v1/health`.
- Image tags: the git ref name; PRs get `pr-<number>`; the dev and headless targets get `-dev` / `-headless`.
- Custom CAs: mount a directory and set `ca_certs_dir` (commented examples in `compose/config.yaml`, `deployment.yaml`
  and `kustomization.yaml`).
- Workflow actions are pinned by commit SHA with a version comment; `persist-credentials: false` on checkout
  (zizmor findings fixed in `a53c13a`).

## How to

- **New env var or config key for deployments**: document it in `config.example.yaml` and in the relevant
  manifest or comment here; keep the Compose and Kubernetes examples consistent.
- **Change the image**: keep `dev`, `headless` and `production` working; `docker.yaml` builds all three.
- **New workflow**: top-level `permissions: {}` (or minimal), SHA-pinned actions, `persist-credentials: false`.

## Gotchas

- The DB file is written to the process working directory. In Docker, mount it as `/app/chronowarden.db`
  (README); in Kubernetes, the PVC is the working directory.
- Production crashed when the distroless Python differed from the builder's (`pydantic_core` import error, PR #17).
  The `python:3.13.*-slim` tags, the distroless image and the hard-coded `python3.13/site-packages` path must
  change together.
- `docker.yaml` smoke-tests production (health, path traversal, a PDF/A report) and headless (health, `/` 404,
  `report.pdf` 501) before pushing; 30-minute timeout.
- Fuzzing: atheris harnesses in `fuzz/` (`fuzz_*.py`, each asserts its function's contract), built by
  `.clusterfuzzlite/` on the OSS-Fuzz builder, which runs **Python 3.11** (the project declares 3.12+):
  `build.sh` installs the `uv.lock` versions with uv (hash-pinned in `.clusterfuzzlite/requirements.txt`) and the
  package with `--ignore-requires-python`. Code the fuzzers import must keep running on 3.11.
- The SLSA generator is referenced by tag (`@v2.1.0`; the verifier trusts only tagged releases, ADR-018): the one
  `zizmor: ignore[unpinned-uses]`. A release tag fails unless `pyproject.toml` and `CHANGELOG.md` match it.
- `frontend-builder` runs on `$BUILDPLATFORM`: its output is arch-independent, and `npm ci` under QEMU arm64
  emulation hung intermittently (v0.6.2 tag build). Keep it native.
- `dev-setup.py` (podman, else docker) keeps a `config.yaml` it didn't write; `devenv/` images are fully qualified.
- `deployment.yaml` and `cronjob-sync.yaml` pin image tags; bump them with each release.

## Related ADRs

[ADR-007](../.ai/adr/ADR-007-sveltekit-spa-served-by-fastapi.md),
[ADR-008](../.ai/adr/ADR-008-container-and-deployment-targets.md)

## Validate

`docker build -t chronowarden:test .`, `--target dev` and `--target headless`;
`kubectl kustomize deploy/kubernetes` to render the manifests.
