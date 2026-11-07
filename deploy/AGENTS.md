<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# deploy: container image, Kubernetes, CI

## Purpose

How Chronowarden is built and run: the multi-stage `Containerfile` (repo root), built with buildah and run with
podman (Docker works and is documented in the README), bare Kubernetes manifests with kustomize that also run on one
host with `podman kube play` (`deploy/kubernetes/`), and the GitHub workflows (`.github/`). See
[ADR-032](../.ai/adr/ADR-032-podman-preferred-docker-documented.md).

## Files

- `../Containerfile`: `frontend-builder` (node:22-alpine, `npm ci && npm run build`) → `backend-builder` (`.venv`
  with the `reports` extra, `.venv-headless` without) → `dev` (shell, `--reload`), `headless` (distroless, no UI,
  no Typst; ADR-024) and `production` (default target, last; `gcr.io/distroless/python3-debian13:nonroot`).
- `../.containerignore` (buildah, podman) and `../.dockerignore` (Docker): identical, a test checks it.
- `kubernetes/`: `deployment.yaml`, `service.yaml` (ClusterIP :8000), `pvc.yaml` (1Gi RWO), `kustomization.yaml`
  (namespace `chronowarden`; ingress is left to the user), `config-secret.example.yaml` (the config Secret, also
  for `podman kube play`), `cronjob-sync.yaml` (optional, headless `python -m chronowarden sync`; not for kube play).
- `../config.example.yaml`: the full config reference ([core](../chronowarden/AGENTS.md)).
- `../.github/workflows/`: `docker.yaml` (three targets, amd64 + arm64, pushed except on PRs; `v*` tags: cosign,
  SLSA provenance, SBOMs and VEX for production and headless), `release.yaml` (`v*`: wheel, sdist, source SBOMs/VEX,
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
- Custom CAs: mount a directory and set `ca_certs_dir` (examples in `config-secret.example.yaml`, `deployment.yaml`,
  `kustomization.yaml`).
- Workflow actions are pinned by commit SHA with a version comment; `persist-credentials: false` on checkout
  (zizmor findings fixed in `a53c13a`).

## How to

- **New env var or config key for deployments**: document it in `config.example.yaml` and in the relevant
  manifest or comment here; keep the README's podman and Docker commands consistent with the manifests.
- **Change the image**: keep `dev`, `headless` and `production` working; `docker.yaml` builds all three.
- **New workflow**: top-level `permissions: {}` (or minimal), SHA-pinned actions, `persist-credentials: false`.

## Gotchas

- The DB is written to the working directory: a named volume at `/app/data` with `-w /app/data` (README), the PVC in
  Kubernetes. `COPY --chown` gives `/app` and `/app/data` to nonroot in the distroless stages: buildah makes a new
  `WORKDIR` root's (BuildKit, the USER's), and an empty named volume copies `/app/data`'s owner.
- Production crashed when the distroless Python differed from the builder's (`pydantic_core` import error, PR #17).
  The `python:3.13.*-slim` tags, the distroless image and the hard-coded `python3.13/site-packages` path must
  change together.
- `docker.yaml` (name kept: release verification pins the signing identity to it) builds with buildah, arm64
  emulated, no cache (60 min), and smoke-tests production (health, traversal, PDF/A) and headless with podman.
- Fuzzing: atheris harnesses in `fuzz/` (`fuzz_*.py`, each asserts its function's contract), built by
  `.clusterfuzzlite/` on the OSS-Fuzz builder, which runs **Python 3.11** (the project declares 3.12+):
  `build.sh` installs the `uv.lock` versions with uv (hash-pinned in `.clusterfuzzlite/requirements.txt`) and the
  package with `--ignore-requires-python`. Code the fuzzers import must keep running on 3.11.
- The SLSA generator is referenced by tag (`@v2.1.0`; the verifier trusts only tagged releases, ADR-028): the one
  `zizmor: ignore[unpinned-uses]`. A release tag fails unless `pyproject.toml` and `CHANGELOG.md` match it.
- `frontend-builder` runs on `$BUILDPLATFORM`: its output is arch-independent, and `npm ci` under QEMU arm64
  emulation hung intermittently (v0.6.2 tag build). Keep it native.
- `dev-setup.py` (podman, else docker) keeps a `config.yaml` it didn't write ([runs](../.ai/docs/dev-env.md));
  `deployment.yaml` and `cronjob-sync.yaml` pin image tags, bumped with each release.

## Related ADRs

[ADR-007](../.ai/adr/ADR-007-sveltekit-spa-served-by-fastapi.md), ADR-032 (linked under Purpose)

## Validate

`buildah build -t chronowarden:test .` (`--target dev`, `--target headless`); `kubectl kustomize deploy/kubernetes`.
