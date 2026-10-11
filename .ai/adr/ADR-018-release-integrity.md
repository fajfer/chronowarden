<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-018: Release integrity with SLSA Build L3, cosign and SBOMs

- **Status:** Accepted
- **Date:** 2026-10-11
- **Evidence:** maintainer decisions of 2026-10-10 and 2026-10-11; supply-chain spec
- **Supersedes:** none

## Context

Users in regulated environments need to verify that an image was built from this repository by its CI, what it
contains, and that it hasn't been altered. The OpenSSF Scorecard measures the same.

## Decision

- **SLSA Build L3** provenance through `slsa-framework/slsa-github-generator` reusable workflows, for the production
  image and the release files. No GitHub artifact attestations.
- The production image is signed with **cosign** (keyless).
- SBOMs in **CycloneDX 1.6 and SPDX 2.3**, for the production image (per platform) and the source, attached to the
  GitHub Release and bound to the image digest with **`cosign attest`**.
- `-dev` images get none of this.
- Release candidates are GitHub pre-releases.

## Consequences

- Releases are created by `release.yaml` from tags; the README documents the verification commands.
- The SLSA generator must be referenced by tag, not SHA (a documented zizmor exception).
- `main` is PR-only through rulesets, so every change is built and checked before release.

## Related files

- `.github/workflows/release.yaml`, `.github/workflows/docker.yaml`, `Dockerfile`, `README.md`
