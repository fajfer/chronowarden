<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# GitLab as the primary forge

- **Status:** approved
- **Date:** 2026-11-11
- **Issue:** none

## Goal

Chronowarden is developed on `gitlab.com/reszka-org/chronowarden`, and GitHub is an always-current mirror that
still accepts pull requests (bridged) and builds releases. No existing feature is lost, and GitLab Ultimate's
security and compliance features run on every merge request.

## Non-goals

- Moving the release build, SLSA provenance or images off GitHub (ADR-033 §6–7).
- Epics, roadmaps and iterations.
- Changing anything that ships before phase 4.

## Scope

Root files, `.github/`, a new `.gitlab-ci.yml`, `scripts/ci/`, `.ai/docs/`, `README.md`, `SECURITY.md`,
`CONTRIBUTING.md`, `mkdocs.yml`, the GitLab and GitHub project settings.

## Load

- [root AGENTS.md](../../AGENTS.md)
- [ADR-033](../adr/ADR-033-gitlab-primary-forge-agnostic-core.md), [ADR-028](../adr/ADR-028-spdx-3-sboms.md)
- [forge-access](../docs/forge-access.md), [release](../docs/release.md)

## ADRs affected

ADR-033 (new). It amends ADR-018/ADR-028 and the CI parts of ADR-031.

## Feature map

What replaces what. Nothing in the "today" column is dropped without a maintainer decision.

| Today (GitHub) | After | Free / GitHub fallback if Ultimate lapses |
|---|---|---|
| CI (`ci.yaml`, `agents-docs.yaml`) | GitLab CI calling `scripts/ci/*`; JUnit, coverage, Code Quality in MRs | same CI on GitLab Free |
| Release, SLSA L3, cosign, ghcr (`release.yaml`, `docker.yaml`) | unchanged on GitHub Actions, triggered by mirrored tags; GitLab experimental attestations as well | n/a (no Ultimate needed) |
| zizmor | kept for GitHub workflows; GitLab CI: mitigations + **requirement** for a linter (task 12) | same |
| Scorecard (`scorecard.yml`) | Scorecard CLI on GitLab, badge on both READMEs | Scorecard on GitHub Actions |
| ClusterFuzzLite | moved as is to GitLab CI | same |
| CodeQL default setup | kept on the GitHub mirror + Advanced SAST, SAST, IaC scanning on GitLab | CodeQL alone |
| Code scanning UI | vulnerability report, security dashboard, MR widget | GitHub code scanning |
| Dependabot version updates | Renovate on GitLab | Dependabot |
| Dependabot alerts | kept + dependency scanning, continuous vulnerability scanning, dependency list | Dependabot alerts |
| Secret scanning + push protection | kept + GitLab secret push protection, pipeline secret detection | GitHub's |
| Private vulnerability reporting, GHSA | kept + GitLab confidential issues and Service Desk; advisories on both | GitHub's |
| Rulesets `main`, `release tags` | protected branch and tags, approval rules and policies, push rules; GitHub locked to the mirror | GitLab Free protected branches |
| Releases | GitHub canonical for assets; GitLab Release with evidence links to them | GitHub Releases |
| Issues, PRs, milestones, labels | imported; GitHub issues stay open with a template pointing to GitLab | GitHub |
| Copilot environment | removed (unused) | — |
| Docs site (not published today) | GitLab Pages | GitHub Pages |

## Tasks

| # | Task | Load | Done when | Status | Commit |
|---|---|---|---|---|---|
| 1 | **Maintainer:** import the GitHub project into `reszka-org`, set a GitHub → GitLab pull mirror, create the agent's project access token ([forge-access](../docs/forge-access.md)) | forge-access | the project exists, mirrors main within 30 minutes, `glab auth status` works for the agent | todo | |
| 2 | Move CI logic into `scripts/ci/` so both forges call the same scripts | `.github/workflows/ci.yaml` | GitHub CI is green and calls only scripts | todo | |
| 3 | `.gitlab-ci.yml`: lint, tests, frontend check, integration tests on podman, agents-docs check, ClusterFuzzLite, with JUnit, coverage and Code Quality reports | `scripts/ci/`, ADR-031 | a GitLab pipeline is green on main, with test reports visible in an MR | todo | |
| 4 | Ultimate scanners: SAST + Advanced SAST, secret detection, dependency scanning, container scanning of the ghcr image, IaC scanning, the SBOMs as CycloneDX reports | ADR-028 | the vulnerability report and dependency list show main; a finding blocks an MR via a policy | todo | |
| 5 | Measure compute minutes for two weeks; decide what stays parallel | — | usage per pipeline recorded in this spec | todo | |
| 6 | Docs on GitLab Pages | `mkdocs.yml` | the docs site is published and linked from both READMEs | todo | |
| 7 | Scorecard CLI on GitLab and a badge on both READMEs; GitHub's `scorecard.yml` stays until the GitLab badge works | `.github/workflows/scorecard.yml` | the badge shows a GitLab score | todo | |
| 8 | Renovate on GitLab; Dependabot version updates off on GitHub (alerts stay) | `.github/dependabot.yml`, release.md | Renovate MRs arrive grouped as Dependabot's did | todo | |
| 9 | **Switch:** protected branch/tags, approval rules, policies and push rules on GitLab; flip to a GitLab → GitHub push mirror; GitHub `main` writable only by the mirror; issue template on GitHub; README, SECURITY.md, CONTRIBUTING.md point to GitLab | ADR-033 | a merge on GitLab appears on GitHub within minutes; a direct push to GitHub `main` is refused | todo | |
| 10 | PR bridge: GitHub PR → GitLab MR (commits kept), status reported back | ADR-033 §3 | a fork PR on GitHub becomes an MR, and after merging, GitHub shows the PR as merged | todo | |
| 11 | Release on the new topology: an rc tag pushed on GitLab builds on GitHub; GitLab Release links to the assets; GitLab experimental SLSA attestations | release.md, ADR-028 | the rc verifies as in the README, and the GitLab attestation verifies with `glab attestation verify` | todo | |
| 12 | Find or build a security linter for `.gitlab-ci.yml` (requirement from ADR-033 §10) | — | the linter runs in CI and fails on an unpinned image or script injection | todo | |
| 13 | Ultimate extras, one change each: DAST and API security testing against a CI-started app, license approval policies, compliance framework, audit events review, requirements for spec "Done when" items, Service Desk, error tracking, dependency proxy | ADR-033 §5 | each is enabled and listed in the feature map with its fallback | todo | |

## Validation

- A merge on GitLab reaches GitHub, and a bridged PR shows as merged on GitHub.
- An rc release verifies with the README commands, and with `slsa-verifier` in CI.
- `python3 scripts/check_agents_docs.py`

## Open questions

- Does the grant come from the Nonprofit or the Open Source programme, and how many compute minutes does it
  include? (Check under the group's Billing and Usage quotas.)
- Can Scorecard publish a badge for a gitlab.com project? Its publishing path is GitHub OIDC; if not, task 7
  falls back to a badge generated from the GitLab pipeline's result.
