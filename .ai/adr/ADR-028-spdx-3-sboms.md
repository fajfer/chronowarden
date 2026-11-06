<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-028: Release integrity with SBOMs in SPDX 3.0

- **Status:** Proposed
- **Date:** 2026-11-07
- **Evidence:** maintainer request of 2026-11-07; syft v1.46.0 added SPDX 3 output (anchore/syft#4269); the
  in-toto SPDX 3 predicate `https://spdx.dev/Document/v3`
- **Supersedes:** ADR-018

## Context

ADR-018 chose SPDX 2.3 because syft could not write SPDX 3 at the time. SPDX 3.0 is the current specification,
and the maintainer doesn't want releases to ship an SBOM below it. syft v1.54.0, which the pinned
`anchore/sbom-action/download-syft` already installs, writes SPDX 3.0.1 JSON-LD.

## Decision

ADR-018 stands, except for the SPDX version:

- **SLSA Build L3** provenance through `slsa-framework/slsa-github-generator` reusable workflows, for the production
  image and the release files. No GitHub artifact attestations.
- The production image is signed with **cosign** (keyless).
- SBOMs in **CycloneDX 1.6 and SPDX 3.0** (JSON-LD, spec version 3.0.1), for the production image (per platform)
  and the source, attached to the GitHub Release and bound to the image digest with **`cosign attest`**. The SPDX
  attestation uses the in-toto predicate type `https://spdx.dev/Document/v3`.
- No SPDX 2.x SBOM is published alongside: there are no compatibility shims before 1.0.
- `-dev` images get none of this.
- Release candidates are GitHub pre-releases.

## Consequences

- Consumers that only read SPDX 2.x must convert the SBOM or use the CycloneDX one.
- `cosign verify-attestation` for the SPDX SBOM takes `--type https://spdx.dev/Document/v3`; the `spdxjson`
  shorthand means SPDX 2.
- CI checks the JSON-LD `@context` and the `CreationInfo` spec version, as it checked `spdxVersion` before.
- syft's SPDX 3 encoder relies on `spdx/tools-golang` v0.6.0-rc4, a release candidate; watch syft updates for
  changes to the output.
- The rest of ADR-018's consequences carry over unchanged.

## Related files

- `.github/workflows/release.yaml`, `.github/workflows/docker.yaml`, `README.md`
