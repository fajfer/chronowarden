<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-020: PDF reports with Typst

- **Status:** Proposed (accepted after the spike in the policies spec, task 1)
- **Date:** 2026-10-11
- **Evidence:** maintainer decision of 2026-10-11
- **Supersedes:** none

## Context

Snapshots need a printable, archivable report. The renderer must work in the distroless image on amd64 and arm64.

## Decision

Render reports with **Typst** (the `typst` Python wheel): PDF/A output, restylable templates, a bundled font with its
licence in `LICENSES/`. Rejected: WeasyPrint (needs Pango, breaks distroless) and fpdf2 (no PDF/A).

## Consequences

- A spike must confirm the wheel works on arm64 in the distroless image before acceptance.
- Report templates are versioned with the code.

## Related files

- `chronowarden/compliance/` (renderer), `pyproject.toml`, `LICENSES/`
