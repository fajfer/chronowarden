<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# OpenSSF Best Practices: passing criteria

Evidence for every criterion of the "passing" badge, so the answers on
[bestpractices.dev project 13350](https://www.bestpractices.dev/en/projects/13350/passing) can be checked and
defended. Update a row when the evidence changes, and keep the site in sync with this file.

- **Snapshot of the site:** 2026-10-11, badge `in_progress`, 19%, last edited 2026-06-24. 14 Met, 1 Unmet
  (`release_notes`), the rest unanswered.
- **Source of the criteria:** `criteria/criteria.yml` level 0 in
  [coreinfrastructure/best-practices-badge](https://github.com/coreinfrastructure/best-practices-badge), 67
  active criteria (31 MUST, 9 SHOULD, 12 SUGGESTED unanswered on the site).
- **Columns:** *Site* is the answer on bestpractices.dev at the snapshot; *Answer* is what it should say now;
  *Evidence* backs it up; *Improved* says when the evidence appeared; *Next* is how to strengthen it.
- **R** = `https://github.com/fajfer/chronowarden`.

## Basics

| Criterion | Level | Site | Answer | Evidence | Improved | Next |
|---|---|---|---|---|---|---|
| description_good | MUST | ? | Met | README first paragraph: monitors expiring secrets in Vault/OpenBao through KV metadata. | | |
| interact | MUST | ? | Met | README: issues, Matrix room, releases, contribution via `CONTRIBUTING.md`. | | |
| contribution | MUST | Met | Met | R/blob/main/CONTRIBUTING.md (was justified with GitHub defaults only). | 2026-10-11, `CONTRIBUTING.md` PR | Replace the justification with the file URL. |
| contribution_requirements | SHOULD | ? | Met | `CONTRIBUTING.md`: conventional commits, checks to run, tests required. | 2026-10-11 | |
| floss_license | MUST | Met | Met | EUPL-1.2, R/blob/main/LICENSE | | |
| floss_license_osi | SUGGESTED | Met | Met | EUPL-1.2 is OSI-approved. | | |
| license_location | MUST | Met | Met | R/blob/main/LICENSE and `LICENSES/`; SPDX header on every file (ADR-001). | | |
| documentation_basics | MUST | Met | Met | README (install, config, API), docs site https://fajfer.github.io/chronowarden/ | | Keep `docs/` current; AI drafts carry a notice until reviewed. |
| documentation_interface | MUST | ? | Met | README "API Endpoints"; OpenAPI at `/docs` on every instance; `config.example.yaml` documents every option. | | |
| sites_https | MUST | Met | Met | GitHub, GHCR and GitHub Pages are HTTPS-only. | | |
| discussion | MUST | Met | Met | GitHub issues and PRs (searchable, URL per thread). | | |
| english | SHOULD | Met | Met | Docs, issues and code in English. | | |
| maintained | MUST | Met | Met | Releases 0.6.0–0.6.3 in October 2026; milestones 0.7–1.x. | | |

## Change control

| Criterion | Level | Site | Answer | Evidence | Improved | Next |
|---|---|---|---|---|---|---|
| repo_public | MUST | Met | Met | R | | |
| repo_track | MUST | Met | Met | git history with authors and dates. | | |
| repo_interim | MUST | ? | Met | Every change lands on `main` through a public PR (ruleset), so interim work is visible. | 2026-10-11, `main` ruleset | |
| repo_distributed | SUGGESTED | Met | Met | git | | |
| version_unique | MUST | ? | Met | SemVer tags `vX.Y.Z`; `release.yaml` refuses a tag that doesn't match `pyproject.toml`. | 2026-10-11, #118 | |
| version_semver | SUGGESTED | ? | Met | CHANGELOG header: Semantic Versioning, pre-1.0 breaking changes marked **Breaking**. | 2026-10-09, 0.6.0 | 1.0 stability promise (ADR-016). |
| version_tags | SUGGESTED | ? | Met | Tags v0.6.0–v0.6.3; the `release tags` ruleset prevents moving or deleting them. | 2026-10-11, tag ruleset | |
| release_notes | MUST | **Unmet** | Met | R/blob/main/CHANGELOG.md (Keep a Changelog) from 0.6.0; each GitHub Release carries its section (`scripts/release_notes.sh`). | 2026-10-09 CHANGELOG; 2026-10-11 #118 | Fix the site: it still says "No release notes file found". |
| release_notes_vulns | MUST | ? | Met | 0.6.1 and 0.6.2 entries name GHSA-63g5-x4f2-2rg5 and GHSA-7p2g-v7c6-vpww. | 2026-10-10 | Request CVE IDs with future advisories. |

## Reporting

| Criterion | Level | Site | Answer | Evidence | Improved | Next |
|---|---|---|---|---|---|---|
| report_process | MUST | Met | Met | GitHub issues, R/issues; `CONTRIBUTING.md`. | | |
| report_tracker | SHOULD | ? | Met | GitHub issues with labels and milestones. | | |
| report_responses | MUST | ? | Met | Issues from the last months are answered and triaged into milestones. | | Keep answering within days. |
| enhancement_responses | SHOULD | ? | Met | Enhancements triaged into milestones (0.7, 0.7.x, 0.8, ...). | 2026-10-11 triage | |
| report_archive | MUST | ? | Met | Issues are public and searchable. | | |
| vulnerability_report_process | MUST | ? | Met | R/blob/main/SECURITY.md | 2026-10-11, #101 | |
| vulnerability_report_private | MUST | ? | Met | GitHub private vulnerability reporting, enabled and linked from `SECURITY.md`. | 2026-10-11 | |
| vulnerability_report_response | MUST | ? | Met | `SECURITY.md` promises acknowledgement within 7 days (criterion: 14). Both 2026 advisories were fixed and released the same day. | 2026-10-11, #101 | |

## Quality

| Criterion | Level | Site | Answer | Evidence | Improved | Next |
|---|---|---|---|---|---|---|
| build | MUST | ? | Met | `uv sync` / `uv build`, `npm run build`, `docker build` (README). | | |
| build_common_tools | SUGGESTED | ? | Met | uv, npm, Docker. | | |
| build_floss_tools | SHOULD | ? | Met | All build tools are FLOSS. | | |
| test | MUST | ? | Met | pytest suite, 327 tests (`uv run pytest`); README "Testing". | | |
| test_invocation | SHOULD | ? | Met | Standard `uv run pytest`. | | |
| test_most | SUGGESTED | ? | Met | Config, metadata, API, DB and Vault integration are covered. | | Publish coverage (`--cov`) in CI to back this with a number. |
| test_continuous_integration | SUGGESTED | ? | Met | `ci.yaml` on every push and PR; required by the `main` ruleset. | 2026-10-11 ruleset | |
| test_policy | MUST | ? | Met | `CONTRIBUTING.md` and `AGENTS.md`: new features need tests, bug fixes need regression tests. | 2026-10-11 | |
| tests_are_added | MUST | ? | Met | Recent changes add tests, e.g. #116 (regression tests for fuzzing finds), 0.6.3 metadata merge tests. | 2026-10-11 | |
| tests_documented_added | SUGGESTED | ? | Met | Same policy text. | 2026-10-11 | |
| warnings | MUST | ? | Met | black, ruff, svelte-check and zizmor in CI. | | |
| warnings_fixed | MUST | ? | Met | CI fails on any finding; required checks block the merge. | 2026-10-11 ruleset | |
| warnings_strict | SUGGESTED | ? | Met | ruff, `svelte-check`, zizmor (online audits in CI). | | Consider ruff's wider rule sets (`B`, `S`). |

## Security

| Criterion | Level | Site | Answer | Evidence | Improved | Next |
|---|---|---|---|---|---|---|
| know_secure_design | MUST | ? | Met | Maintainer: one line on experience. Design: metadata-only access (ADR-004), least-privilege Vault policy, distroless image. | | Maintainer writes the line. |
| know_common_errors | MUST | ? | Met | Path traversal and Vault path injection found, fixed and published (GHSAs); CodeQL, zizmor, fuzzing. | 2026-10-09/10 | |
| crypto_published | MUST | ? | N/A | Chronowarden implements no cryptography; TLS to Vault comes from Python's `ssl` via hvac/requests. | | |
| crypto_call | SHOULD | ? | N/A | Same. | | |
| crypto_floss | MUST | ? | N/A | Same. | | |
| crypto_keylength | MUST | ? | N/A | Same. | | |
| crypto_working | MUST | ? | N/A | Same. | | |
| crypto_weaknesses | SHOULD | ? | N/A | Same. | | |
| crypto_pfs | SHOULD | ? | N/A | Same; TLS settings are the platform's. | | |
| crypto_password_storage | MUST | ? | N/A | Stores no user passwords (no authentication before 0.9, ADR-015). | | Revisit with authentication in 0.9. |
| crypto_random | MUST | ? | N/A | Generates no keys or nonces. | | Revisit with authentication in 0.9. |
| delivery_mitm | MUST | Met | Met | HTTPS only (GitHub, GHCR); from 0.7.0 images are cosign-signed with SLSA Build L3 provenance. | 2026-10-11, #118 | |
| delivery_unsigned | MUST | ? | Met | No hashes over HTTP; `SHA256SUMS` and provenance on the Release. | 2026-10-11, #118 | |
| vulnerabilities_fixed_60_days | MUST | ? | Met | No known unpatched vulnerabilities; both advisories fixed in releases the day they were found. | | |
| vulnerabilities_critical_fixed | SHOULD | ? | Met | Same. | | |
| no_leaked_credentials | MUST | ? | Met | No credentials in the repository; dev tokens are generated at runtime by `dev-setup.py`. | | Enable GitHub secret scanning push protection if not on. |

## Analysis

| Criterion | Level | Site | Answer | Evidence | Improved | Next |
|---|---|---|---|---|---|---|
| static_analysis | MUST | ? | Met | CodeQL (Python, JS/TS, Actions) on every PR; ruff; zizmor. | | |
| static_analysis_common_vulnerabilities | SUGGESTED | ? | Met | CodeQL security queries. | | |
| static_analysis_fixed | MUST | ? | Met | CodeQL and zizmor findings are fixed before merge (e.g. the release cache finding on #118). | 2026-10-11 | |
| static_analysis_often | SUGGESTED | ? | Met | Every push and PR. | | |
| dynamic_analysis | SUGGESTED | ? | Met | ClusterFuzzLite + atheris: 5 min on PRs touching code, 30 min weekly. | 2026-10-11, #116 | Add fuzzers for API input parsing. |
| dynamic_analysis_unsafe | SUGGESTED | ? | N/A | Python and TypeScript are memory-safe. | | |
| dynamic_analysis_enable_assertions | SUGGESTED | ? | Met | The fuzz harnesses assert each function's contract. | 2026-10-11, #116 | |
| dynamic_analysis_fixed | MUST | ? | Met | The three bugs the fuzzers found were fixed with regression tests (#116). | 2026-10-11 | |

## To reach "passing"

1. Merge the `CONTRIBUTING.md` PR, then update `contribution` and `release_notes` on the site.
2. Answer the rest with the *Answer* and *Evidence* columns; the maintainer writes `know_secure_design`.
3. Afterwards, Scorecard's CII-Best-Practices check moves from 2 (in progress) to 5 (passing).
