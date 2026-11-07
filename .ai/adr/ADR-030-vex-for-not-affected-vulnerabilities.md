<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-030: CycloneDX VEX for every vulnerability we're not affected by

- **Status:** Accepted
- **Date:** 2026-11-07
- **Evidence:** maintainer decisions of 2026-11-07; Dependabot alert #67 (GHSA-gcqx-w48m-w2h4, `deepmerge`)
- **Supersedes:** none

## Context

Scanners flag every vulnerable component in our SBOMs (ADR-028), whether or not the vulnerable code can run. A user
in a regulated environment who scans a release gets those findings with no way to tell which ones we checked.
Dismissing a Dependabot alert records our reasoning only on GitHub, where scanners and auditors don't look. VEX
(Vulnerability Exploitability eXchange) states, per vulnerability and component, whether a product is affected and
why, in a form scanners read.

## Decision

- **When:** every vulnerability alert (Dependabot, or a scanner run on our SBOMs) judged *not exploitable* in
  Chronowarden gets a VEX statement before the alert is dismissed, and the dismissal links to it. A vulnerability
  that's fixed by upgrading needs no statement.
- **Format:** CycloneDX 1.6 VEX, matching our CycloneDX SBOMs.
- **Source of truth:** `vex/chronowarden.vex.cdx.json` in the repository. Each entry has the vulnerability ID (GHSA,
  plus the CVE when there is one), the affected components by package URL, `analysis.state: not_affected`, a
  CycloneDX `justification` and a `detail` with the threat model: who could reach the code, and why they can't.
- **Published:** at release, one VEX document per SBOM is generated from the source of truth, pointing at that
  SBOM's components by BOM-Link (`urn:cdx:<serial>/<version>#<bom-ref>`), since the SBOMs get new serial numbers
  every release. Statements for components the SBOM doesn't contain are left out. The VEX documents are attached to
  the GitHub release, and the image ones are attested to the image with `cosign attest`, next to the SBOMs.
- **Never** a statement without a checked reason: a `not_affected` claim names what was verified (dependency path,
  shipped artefacts, call sites).

## Consequences

- Scanners that read CycloneDX VEX with BOM-Links (e.g. `trivy sbom --vex`) drop the findings we've analysed; grype
  reads OpenVEX and CSAF, not CycloneDX VEX, so its users still see them.
- Every new statement is reviewed like code, through a PR.
- A statement goes stale when the component changes: a dependency update re-checks the statements for that package.
- Release workflows gain a generation step; a statement whose JSON is invalid fails the release.

## Related files

- `vex/chronowarden.vex.cdx.json`, `.github/workflows/release.yaml`, `.github/workflows/docker.yaml`,
  `.ai/docs/release.md`, `README.md`
