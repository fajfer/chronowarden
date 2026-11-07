<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Podman and Buildah everywhere (0.11)

- **Status:** in progress
- **Date:** 2026-11-07
- **Issue:** none

## Goal

Chronowarden is built, tested and documented with podman and buildah only (ADR-031): CI builds the images with
buildah and runs them with podman, the integration tests use podman, the build file is a `Containerfile`, and a
single host runs Chronowarden with `podman kube play` and the Kubernetes manifests. Releases stay as verifiable as
before (SLSA provenance, cosign, SBOMs, VEX).

## Non-goals

- Changing what the images contain or their targets.
- Helm charts or other deployment tooling.
- A build cache (slower builds are accepted).

## Scope

`Containerfile`, `.containerignore`, `.github/workflows/`, `deploy/`, `README.md`, `docs/`, `.ai/docs/dev-env.md`,
`devenv/` (only where it names Docker files).

## Load

- [root AGENTS.md](../../AGENTS.md)
- [deploy](../../deploy/AGENTS.md), [release](../docs/release.md)
- [ADR-032](../adr/ADR-032-podman-preferred-docker-documented.md), [ADR-028](../adr/ADR-028-spdx-3-sboms.md),
  [ADR-024](../adr/ADR-024-headless-image.md)

## ADRs affected

ADR-008 is superseded by ADR-031 (done with the ADR).

## Tasks

| # | Task | Load | Done when | Status | Commit |
|---|---|---|---|---|---|
| 1 | Check the tools that look for `Dockerfile`: does Dependabot's `docker` ecosystem update a `Containerfile`? Does ClusterFuzzLite require `.clusterfuzzlite/Dockerfile`? Record the answers here | `.github/dependabot.yml`, `.clusterfuzzlite/` | Both answered with a source (docs or a test PR) | done | Dependabot: `DOCKER_REGEXP = /dockerfile\|containerfile/i` (dependabot-core `docker/file_fetcher.rb`), so a `Containerfile` is updated. ClusterFuzzLite: `cifuzz` builds `os.path.join(build_integration_path, 'Dockerfile')` (oss-fuzz `infra/cifuzz/continuous_integration.py`), so `.clusterfuzzlite/Dockerfile` keeps its name |
| 2 | Rename `Dockerfile` → `Containerfile`, `.dockerignore` → `.containerignore`; update every reference (workflows, devenv, docs, AGENTS.md files, Dependabot config if task 1 needs it) | spec Load | `git grep -n Dockerfile` finds only `.clusterfuzzlite/` (if required) and history | done | this PR; `.dockerignore` kept identical to `.containerignore` (ADR-032) |
| 3 | `docker.yaml`: buildah builds and pushes the multi-arch production and headless images (emulation for arm64), `podman login`, smoke tests with `podman run`; digests from buildah's digest file feed SLSA, cosign and SBOM jobs; no `docker/*` actions left | `.github/workflows/docker.yaml`, deploy | A PR build passes the smoke tests; zizmor clean; a release candidate tag shows provenance, signature, SBOMs and VEX verifiable as in the README | todo | |
| 4 | Integration tests on podman: start the podman socket in CI and point testcontainers at it (`DOCKER_HOST`, Ryuk as needed); same for local runs in the dev-env doc | `.github/workflows/ci.yaml`, `tests/integration/`, `.ai/docs/dev-env.md` | The OpenBao, Vault and Keycloak integration tests pass in CI on podman; the check keeps its name "Integration tests (OpenBao, Vault)" (required in the ruleset) | doing | this PR; slirp4netns instead of pasta, whose Ubuntu AppArmor profile blocks podman's teardown (17 passed locally) |
| 5 | Single host: check which kinds in `deploy/kubernetes/` `podman kube play` runs (Deployment, PVC, Service, CronJob?); document `podman kube play` with them; a single-host alternative for anything unsupported (e.g. the sync CronJob → a systemd timer running the headless image); remove `deploy/compose/` | `deploy/`, `README.md` | The documented commands start Chronowarden on a host with podman and keep its DB across a restart | done | this PR: kube play runs Deployment, PVC and the config Secret (Service and CronJob unsupported: `--publish`, and the server's own sync); checked locally 2026-11-07, DB kept across `kube down`/`play` |
| 6 | Docs: podman/buildah commands first in `README.md`, `docs/` and `.ai/docs/`; the README also shows the Docker one-liners (ADR-032). The index digest comes from `skopeo inspect --raw` (podman's own inspect gives the platform image's or a re-serialised manifest) | `README.md`, `docs/`, `.ai/docs/` | Every `docker` command left is a Docker alternative next to a podman one, or the `docker.yaml` signing identity | done | this PR; the README quick start was checked with podman (volume keeps the DB) |

## Validation

`uv run black --check . && uv run ruff check . && uv run pytest`, zizmor on the workflows, CI green including the
integration tests, then a release candidate (on the maintainer's go) verified with the README's commands.

## Open questions

- None yet; task 1 and task 5 may raise some.
