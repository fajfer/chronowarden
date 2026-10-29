<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Releasing a version

How a release goes out, as done for 0.8.0 and 0.9.0. The maintainer gives the go for the final tag (root
**Never**); everything before it lands through PRs like any change.

## Before the release PR

1. Every spec for the release is `implemented` or explicitly left out; open specs that are only waiting on the
   maintainer say so in their task's Status.
2. Open Dependabot PRs: a runtime dependency with a security alert goes in before the tag (0.9.0: certifi). Each
   Dependabot PR is updated to `main` (`gh pr update-branch`) and merged once its checks pass, one at a time,
   because several touch `uv.lock`.
3. `gh api repos/fajfer/chronowarden/dependabot/alerts?state=open` lists what the release would ship; dev-only
   alerts don't block it.

## The release PR (`release/X.Y.Z`, `chore: Release X.Y.Z`)

- `pyproject.toml` version, then `uv lock` (only the project version changes in `uv.lock`).
- `CHANGELOG.md`: `## [Unreleased]` stays empty above `## [X.Y.Z] - <date>`, with a one-paragraph summary of the
  release; compare links at the bottom (`[Unreleased]` from the new tag, `[X.Y.Z]` from the previous one).
  `release.yaml` fails when the section is missing (`scripts/release_notes.sh`).
- Image tags: README (`ghcr.io/…:vX.Y.Z` and the three `docker build` lines), `deploy/kubernetes/deployment.yaml`,
  `deploy/kubernetes/cronjob-sync.yaml` (the image line only), the headless comment in `deploy/compose/config.yaml`.
- README roadmap: the release's row lists what actually shipped (issues and ADRs).
- The release's specs move to `.ai/specs/implemented/` (links one level deeper) and the specs index follows.

## The tag

1. After the release PR is merged, wait for every check on the `main` commit, not only the required ones
   (`gh api repos/fajfer/chronowarden/commits/<full sha>/check-runs`; `gh run list --commit` needs the full SHA).
2. On the maintainer's go: `git tag -a vX.Y.Z -m "vX.Y.Z - <theme>" <sha>` (annotated, as earlier tags) and push it.
3. `release.yaml` (wheel, sdist, source SBOMs, provenance, notes) and `docker.yaml` (images, SBOMs, provenance,
   signatures) run on the tag; both must end green and the GitHub release must list the wheel, sdist, 10 SBOMs,
   `chronowarden.intoto.jsonl` and `SHA256SUMS`.
4. Close the release's GitHub milestone and the issues it finished, each with a comment naming the evidence.
