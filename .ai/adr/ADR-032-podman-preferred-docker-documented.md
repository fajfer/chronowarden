<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-032: Podman preferred, Docker documented

- **Status:** Accepted
- **Date:** 2026-11-07
- **Evidence:** maintainer decision of 2026-11-07 (during the ADR-031 migration)
- **Supersedes:** ADR-031

## Context

ADR-031 moved builds, CI and docs to podman and buildah and said Docker "isn't what we document or test". Many users
only have Docker, and the images build and run with it unchanged; leaving it out of the README makes the first
step harder for them without making anything safer.

## Decision

ADR-031 stands, except for the docs:

- A multi-stage **`Containerfile`** with the `production` (default), `dev` and `headless` targets, built for amd64
  and arm64 and pushed to GHCR.
- **CI uses the podman and buildah command lines**; integration tests reach podman through its Docker-compatible
  socket; no layer cache.
- **Single-host deployments use `podman kube play`** with the Kubernetes manifests; the Compose example is removed.
- **The README shows podman first and says it's preferred, with the Docker one-liner next to it** for building and
  running (`docker build -f Containerfile .`, `docker run …`). Guides beyond the README show podman.
- Docker reads only `.dockerignore` (or `<file>.dockerignore`), never `.containerignore`, so the repository keeps a
  `.dockerignore` identical to `.containerignore`; a test fails when they differ.
- ClusterFuzzLite keeps `.clusterfuzzlite/Dockerfile`: OSS-Fuzz's `cifuzz` builds that exact name and runs Docker
  itself on GitHub's runners.
- Release integrity (provenance, signatures, SBOMs, VEX) is unchanged.

## Consequences

- Docker users get a working build without a second ignore file going stale.
- CI tests podman only; a Docker-specific break is found by users, not by CI.

## Related files

- `Containerfile`, `.containerignore`, `.dockerignore`, `README.md`, `.github/workflows/docker.yaml`,
  `.github/workflows/ci.yaml`, `deploy/kubernetes/`
