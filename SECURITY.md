<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Security policy

## Supported versions

Chronowarden is before 1.0. Security fixes are released for the **latest minor version** only (currently 0.6.x);
upgrade to the newest release to receive them.

## Reporting a vulnerability

Please **don't open a public issue**. Report it privately through GitHub:
[Report a vulnerability](https://github.com/fajfer/chronowarden/security/advisories/new) (Security tab → Advisories
→ Report a vulnerability).

Include what you found, how to reproduce it, the affected version, and its impact as you see it.

What to expect:

- an acknowledgement **within 7 days**;
- an assessment and, if the report is confirmed, a fix in a patch release;
- a published GitHub security advisory (with a CVE where applicable) crediting you, unless you prefer otherwise.

## Scope

Chronowarden reads secret **metadata only**, never secret values. Reports about the API and UI being reachable
without authentication are known and documented (see the warning in the [README](README.md)); authentication is
planned for 0.9. Anything that lets an attacker read secret values, read files, reach Vault paths outside the
configured mounts, or change data despite these limits is in scope.

## Published advisories

- [GHSA-63g5-x4f2-2rg5](https://github.com/fajfer/chronowarden/security/advisories/GHSA-63g5-x4f2-2rg5): path
  traversal in the UI route, fixed in 0.6.1.
- [GHSA-7p2g-v7c6-vpww](https://github.com/fajfer/chronowarden/security/advisories/GHSA-7p2g-v7c6-vpww): Vault path
  injection in the passthrough endpoints, fixed in 0.6.2.
