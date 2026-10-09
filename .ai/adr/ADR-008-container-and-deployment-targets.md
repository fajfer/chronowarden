<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-008: Distroless image; Compose and bare Kubernetes manifests

- **Status:** Accepted (retroactive)
- **Date:** 2026-02-09
- **Evidence:** `fe68be8` (Dockerfile), `84ea691` (CI to GHCR), `287cbfa` (Kubernetes manifests); PR #17 proposed `python:3.12-slim` after a Python-version crash, but distroless was kept (`a82af9b`).

## Context

Not recorded. README documents a production image ("distroless, no shell") and a dev image ("full shell, git, --reload").

## Decision

A multi-stage Dockerfile with a distroless, non-root `production` target (default) and a `dev` target with a shell. Both are built for amd64 and arm64 and pushed to GHCR. Deployment examples: Compose config and kustomize-based bare manifests (no Helm).

## Consequences

The production image has no shell for debugging (use the `dev` target). Kubernetes runs a single replica with a PVC for the DB.

## Related files

- [`Dockerfile`](../../Dockerfile)
- [`.github/workflows/docker.yaml`](../../.github/workflows/docker.yaml)
- [`deploy/kubernetes/kustomization.yaml`](../../deploy/kubernetes/kustomization.yaml)
