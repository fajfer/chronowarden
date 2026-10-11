<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Supply chain: Scorecard, SLSA Build L3 provenance, SBOMs

- **Status:** in progress
- **Date:** 2026-10-11
- **Issue:** #87, #88, #89, #90, #91, #92

## Goal

Every tagged release from v0.7.0 on is a GitHub Release whose image and files can be verified by anyone: **SLSA
Build L3** provenance for the production image (multi-arch manifest digest) and for the release files, a cosign
keyless signature, and image and source **SBOMs in CycloneDX and SPDX** bound to the image with `cosign attest`. The
OpenSSF Scorecard rises from **6.8** to about **8.7**. The README explains how to verify a release.

## Baseline (Scorecard, scan of 2026-10-10 18:49)

| Check (risk) | Now | Cause | Target | How |
|---|---|---|---|---|
| Token-Permissions (High) | 0 | `docker.yaml` grants `packages: write` at the top level | 10 | Top level `contents: read`; write permissions per job |
| Security-Policy (Medium) | 0 | No `SECURITY.md` | 10 | `SECURITY.md` + GitHub private vulnerability reporting |
| Signed-Releases (High) | -1 | Releases exist (v0.6.0–v0.6.3) but carry no assets | 10 | Releases with `*.intoto.jsonl` provenance as assets |
| Pinned-Dependencies (Medium) | 6 | `FROM` without digest, unpinned `pip install`, `uv.lock` not committed | 10 | Digests on every `FROM`, `uv sync --locked` from a committed `uv.lock` |
| Branch-Protection (High) | -1 | No token; today a classic rule on `main` (1 approval, admins exempt), no rulesets | 3–8 | Rulesets on `main` and `v*`; `SCORECARD_TOKEN` |
| CII-Best-Practices (Low) | 2 | Badge "in progress" | 5 | Finish the "passing" questionnaire |
| Fuzzing (Medium) | 0 | Python counts only via OSS-Fuzz/ClusterFuzzLite | 10 | ClusterFuzzLite + atheris (required) |
| Code-Review (High) | 0 | Solo maintainer | 0 | Accepted: no second human reviewer |

Estimates use Scorecard's risk weights (Critical 10, High 7.5, Medium 5, Low 2.5); the same model gives today's 6.8.

## SLSA level

**Build L3** is the highest level in the SLSA v1.x build track and is reachable on GitHub-hosted runners: the
provenance comes from `slsa-framework/slsa-github-generator` reusable workflows, which run separately from the build
job, so the build can't forge its own provenance. GitHub artifact attestations are **not** used (decided).

## Non-goals

- SLSA Source track; reproducible or hermetic builds; publishing to PyPI.
- Provenance and SBOMs for `-dev` images.
- Any runtime change.

## Scope

`.github/workflows/`, `.github/dependabot.yml`, `.gitignore`, `uv.lock`, `Dockerfile`, `SECURITY.md` (new),
`README.md`, `deploy/AGENTS.md`, `CHANGELOG.md`, `.ai/adr/`, `.clusterfuzzlite/`, `fuzz/`.

## Load

- [root AGENTS.md](../../AGENTS.md)
- [deploy](../../deploy/AGENTS.md)
- [ADR-008](../adr/ADR-008-container-and-deployment-targets.md)
- `.github/workflows/docker.yaml`, `.github/workflows/scorecard.yml`, `.github/dependabot.yml`, `Dockerfile`

## ADRs affected

New **ADR-018 Release integrity** (task 9). Extends ADR-008.

## Tasks

| # | Task | Load | Done when | Status | Commit |
|---|---|---|---|---|---|
| 1 | `SECURITY.md`: supported versions (latest minor), reporting through GitHub private vulnerability reporting, **acknowledgement within 7 days**, links to GHSA-63g5-x4f2-2rg5 and GHSA-7p2g-v7c6-vpww; maintainer turns on private reporting | root | Security-Policy 10 | done | 41da102 |
| 2 | Token permissions: `docker.yaml` top level `permissions: {}`; `packages: write` (and `id-token` for cosign) on the job only | deploy | zizmor clean; Token-Permissions 10 | done | 8a8e157 |
| 3 | Pin the build: commit `uv.lock` (remove from `.gitignore`); every `FROM` by digest with the tag in a comment, keeping `--platform=$BUILDPLATFORM` on the frontend stage; replace `pip install .` with `uv` from a digest-pinned image and `uv sync --locked --no-dev --no-editable`; CI `uv sync --locked`; Dependabot `docker`, `uv`, `npm` (`/frontend`) | deploy, `Dockerfile` | Both targets build; the `docker.yaml` smoke test passes; distroless `site-packages` path still matches; Pinned-Dependencies 10 | done | d262b84 |
| 4 | `release.yaml` on `v*` tags: `uv build` (wheel + sdist), source SBOMs, SHA-256 of every asset → `generator_generic_slsa3.yml` → `gh release create` (pre-release for `-rc.N`) with the matching `CHANGELOG.md` section as notes and all files + `*.intoto.jsonl`; rc tags pushed by the agent on the maintainer's go | deploy | `v0.7.0-rc.1` produces a pre-release; `slsa-verifier verify-artifact` passes for the wheel | doing | |
| 5 | Image: `docker.yaml` exposes the production manifest digest; on tags `generator_container_slsa3.yml` (provenance in GHCR) and cosign keyless signing of the digest | deploy | `slsa-verifier verify-image …` and `cosign verify …` pass | doing | |
| 6 | SBOMs with syft (SHA-pinned action): production image per platform and source (`uv.lock` + `frontend/package-lock.json`), each CycloneDX 1.6 JSON and SPDX 2.3 JSON; attached to the Release and bound to the image digest with `cosign attest`; schemas validated in CI | deploy | 6 SBOMs per release; `cosign verify-attestation` finds them | todo | |
| 7 | zizmor and Scorecard: the SLSA generator is called by tag (`@v2.x.y`), with a justified zizmor ignore for that `uses:` only; Scorecard gets `repo_token: ${{ secrets.SCORECARD_TOKEN }}` | deploy | zizmor clean; Scorecard green | done | |
| 8 | Maintainer, manual (agent drafts instructions and questionnaire answers in a scratch file): ruleset on `main` (PR required for everyone, CI and zizmor required, 0 approvals, no force push or deletion), tag ruleset for `v*`, `SCORECARD_TOKEN`, OpenSSF Best Practices "passing" | none | Branch-Protection and CII scored | doing | |
| 9 | ADR-018; README "Verifying releases" (`slsa-verifier`, `cosign verify`, `cosign verify-attestation`); `deploy/AGENTS.md`; CHANGELOG | [.ai/adr](../adr/README.md), deploy | ADR indexed; commands run against the release | doing | |
| 10 | **Required:** ClusterFuzzLite (`.clusterfuzzlite/`, PR + weekly batch) with atheris fuzzers for `parse_date`, `calculate_ttl` and `load_config` (YAML bytes) | [core](../../chronowarden/AGENTS.md) | Fuzzing 10; crashes found are fixed with regression tests | done | 76c2bc4 |

## Validation

zizmor and Scorecard green; `v0.7.0-rc.1` produces a pre-release with wheel, sdist, 6 SBOMs and provenance; the README
verification commands pass; `docker build` of both targets; `uv run pytest`.
