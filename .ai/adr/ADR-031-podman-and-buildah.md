<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-031: Podman and Buildah everywhere; a Containerfile; `podman kube play` for one host

- **Status:** Superseded by ADR-032
- **Date:** 2026-11-07
- **Evidence:** maintainer decisions of 2026-11-07
- **Supersedes:** ADR-008

## Context

The dev environment already runs on podman (`dev-setup.py` prefers it), while CI builds and runs images with
Docker's tooling (Buildx, Docker's GitHub Actions, the Docker socket for testcontainers) and the docs show `docker`
commands. One toolchain is easier to reason about and to secure: fewer third-party actions in the release path, and
rootless, daemonless builds and containers.

## Decision

ADR-008 stands, except for the tools and the single-host example:

- A multi-stage **`Containerfile`** (renamed from `Dockerfile`; `.containerignore` likewise) with a distroless,
  non-root `production` target (default), a `dev` target with a shell and the `headless` target (ADR-024), built for
  amd64 and arm64 and pushed to GHCR.
- **CI uses the podman and buildah command lines** preinstalled on the runners, not GitHub Actions wrapping them:
  buildah builds both architectures into a manifest list (arm64 under emulation) and pushes it, its digest file
  feeds the SLSA provenance, cosign and SBOM jobs; smoke tests run the images with podman; the integration tests
  reach podman through its Docker-compatible socket. No layer cache: slower builds are accepted.
- **Single-host deployments use `podman kube play`** with the Kubernetes manifests in `deploy/kubernetes/`, one set
  of YAML for both. The Compose example (`deploy/compose/`) is removed.
- **Docs show podman and buildah commands.** Docker still works for users who prefer it (`docker build -f
  Containerfile .`), but isn't what we document or test.
- Release integrity (SLSA Build L3 provenance, cosign signatures, SBOMs; ADR-028, ADR-030) is unchanged; only the
  tool that produces the image digest changes.

## Consequences

- Image builds get slower (no Buildx cache in the GitHub Actions cache).
- Fewer third-party actions in the release workflow.
- Whatever `podman kube play` can't run (it supports a subset of Kubernetes kinds) needs a single-host alternative,
  documented next to the manifests.
- Tools that look for a file named `Dockerfile` (Dependabot, ClusterFuzzLite) must be checked; where one requires
  that name, that file keeps it.

## Related files

- `Containerfile`, `.containerignore`, `.github/workflows/docker.yaml`, `.github/workflows/ci.yaml`,
  `deploy/kubernetes/`, `README.md`, `.ai/docs/dev-env.md`, `deploy/AGENTS.md`
