<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-033: GitLab as the primary forge, GitHub as a mirror, a forge-agnostic core

- **Status:** Accepted
- **Date:** 2026-11-11
- **Evidence:** maintainer decisions of 2026-11-11 on the forge migration questions; GitLab docs on
  bidirectional mirroring, SLSA level 3 attestations (Experiment) and CI/CD for external repositories; GitLab
  Ultimate for the `reszka-org` group from 2026-11-11, renewed yearly
- **Supersedes:** none. It amends ADR-018/ADR-028 (where releases are built) and the CI parts of ADR-031.

## Context

Chronowarden got a yearly GitLab Ultimate licence for the `gitlab.com/reszka-org` group. The maintainer wants
GitLab to be the main forge and wants to use as much of Ultimate as possible. GitHub stays, because that's where
people find and star projects.

The forces:
- **Two forges that both accept merges conflict.** GitLab's own docs warn against bidirectional mirroring as a
  permanent setup. Mirroring carries git refs, but not pull requests, issues, reviews, releases or CI results.
- **Ultimate features are GitLab-only by definition.** The licence is renewed yearly and could lapse, so nothing a
  release depends on may need Ultimate.
- **SLSA Build L3 provenance** comes from `slsa-github-generator` and is verified with `slsa-verifier`, both tied
  to GitHub Actions. GitLab's own SLSA L3 attestations are an Experiment, "not ready for production use". Moving
  releases would also change the cosign signer identity users verify against.
- **GitHub's visible signals decay** when nothing merges there (OpenSSF Scorecard, activity).
- **No losing features:** dropping an existing capability requires the maintainer's explicit agreement.

## Decision

1. **Where merges happen.** `gitlab.com/reszka-org/chronowarden` is the single source of truth: all merges,
   issues, reviews and planning happen there.
2. **The GitHub repo is a push mirror** (GitLab → GitHub, protected refs and tags), so nothing ever merges on
   GitHub and nothing can conflict. Until the switch, the direction is reversed (GitHub → GitLab pull mirror) so
   GitLab CI can run in parallel.
3. **GitHub pull requests are bridged to GitLab merge requests.**
   - **Merging:** bridged MRs merge without squashing or rebasing. The PR's commits then reach GitHub `main`
     through the mirror, GitHub marks the PR as merged, and the contributor keeps the credit.
   - **GitHub issues stay open,** with a template that points to GitLab.
   - **Keeping it in sync is automation's job,** not the maintainer's.
4. **A forge-agnostic core.**
   - Build, test, release, signing, SBOM and VEX logic lives in scripts that run locally, on GitLab Free and on
     GitHub Actions. Forge CI files only call those scripts and set triggers.
   - Tools in the core must work on both forges (Renovate instead of Dependabot for updates, cosign, syft,
     ClusterFuzzLite, the Scorecard CLI).
5. **GitLab Ultimate is used freely outside the core:** security scanners and policies, the vulnerability
   report, compliance, audit events, approvals, requirements, DAST and API security testing.
   - **Fallbacks:** each Ultimate feature in use is listed in the migration spec with its fallback on GitLab Free
     or GitHub.
   - **Out of scope:** epics, roadmaps and iterations aren't used; planning stays in `.ai/`.
6. **Releases are still built on GitHub Actions,** triggered by tags mirrored from GitLab, so SLSA L3,
   `slsa-verifier`, the cosign identity and `ghcr.io` stay as they are.
   - **GitLab's experimental attestations** are produced alongside.
   - **When releases move:** only with a major version, once GitLab's attestations are GA and verifiable with
     common tools.
7. **Images stay on `ghcr.io`.** GitLab scans them from there.
8. **Scorecard runs on GitLab,** and its badge is shown in the README on both forges.
9. **Security reports are accepted on both forges.**
   - **Intake:** GitHub private vulnerability reporting, and GitLab confidential issues or Service Desk.
   - **Publishing:** advisories go out on both.
   - **CVE IDs:** each vulnerability gets exactly one CVE ID, requested through the GitHub advisory unless decided
     otherwise per case.
10. **zizmor has no GitLab CI equivalent.** Accepted for now, with mitigations: images pinned by digest, pipeline
    execution policies, CI lint, review. A security linter for `.gitlab-ci.yml` is a **requirement**, tracked in
    the spec, until one is in place.
11. **Dropping any existing feature needs the maintainer's explicit decision,** recorded in this ADR or its
    successor.
12. **Agents on GitLab** use a project access token with the Developer role. Its scopes and expiry are recorded
    in [forge-access](../docs/forge-access.md). Developer can't merge to protected branches or create protected
    tags, which enforces "no merge or tag without the maintainer's go" on GitLab.

## Consequences

- **Two CI configurations,** GitHub Actions for releases and GitHub-side scanners, and GitLab CI for everything
  else. They stay thin because the logic is in scripts.
- **A PR bridge and a mirror to keep working;** a broken mirror shows as a stale GitHub repo.
- **The licence renewal (yearly, from 11 November) is a calendar item.** If it lapses, only the non-core layer is
  lost.
- **Agent docs route forge tasks:** `glab` for GitLab, and `gh` for the GitHub mirror, releases and advisories.
- **Scorecard's checks** that read GitHub settings and PRs score lower on the GitHub mirror; the GitLab score is
  the one shown.

## Related files

- `.ai/specs/2026-11-11-gitlab-primary-forge.md`, `.ai/docs/forge-access.md`
- `.github/workflows/`, `.github/dependabot.yml`, `README.md`, `SECURITY.md`, `CONTRIBUTING.md`, `mkdocs.yml`
