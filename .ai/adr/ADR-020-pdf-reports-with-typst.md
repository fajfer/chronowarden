<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-020: PDF reports with Typst

- **Status:** Accepted
- **Date:** 2026-10-11
- **Evidence:** maintainer decision of 2026-10-11; spike of 2026-10-12 (below)
- **Supersedes:** none

## Context

Snapshots need a printable, archivable report. The renderer must work in the distroless image on amd64 and arm64.

## Decision

Render reports with **Typst** (the `typst` Python wheel, Apache-2.0): PDF/A-2b output, restylable templates, and
the fonts embedded in Typst itself (Libertinus Serif and others), compiled with `ignore_system_fonts=True` so the
output doesn't depend on the host. No font file is kept in the repository. Rejected: WeasyPrint (needs Pango, breaks
distroless) and fpdf2 (no PDF/A).

## Spike (2026-10-12)

`typst` 0.15.0 (`cp38-abi3` wheels for x86_64 and aarch64, glibc 2.17+) compiled an A4 report with a table, Polish
diacritics and `sys.inputs`, with `pdf_standards=["a-2b"]` and only embedded fonts:

- amd64, `gcr.io/distroless/python3-debian13:nonroot` with a read-only root filesystem: 18 KB PDF in 0.02 s.
- arm64, the same image built natively on a GitHub `ubuntu-24.04-arm` runner (run 38228649272): the same output.
- veraPDF (`--flavour 2b`): PASS.
- Cost: the wheel installs 77 MiB (one native library), the largest dependency in the image.

## Consequences

- The image grows by about 77 MiB uncompressed.
- Tests check the text extracted from rendered PDFs, not their bytes.
- Report templates are versioned with the code.

## Later decisions

- Extended by ADR-024: Typst is the optional `reports` extra; the headless image leaves it out and answers 501.

## Related files

- `chronowarden/compliance/` (renderer), `pyproject.toml`, `LICENSES/`
