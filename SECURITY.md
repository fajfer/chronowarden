<!--
SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->

# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.x     | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in Chronowarden, please report it responsibly.

### How to Report

1. **Do NOT** open a public GitHub issue for security vulnerabilities.
2. Send an email to **damian (at) fajfer.org** with:
   - A description of the vulnerability
   - Steps to reproduce
   - Potential impact assessment
   - Any suggested fixes (optional)

### What to Expect

- **Acknowledgment**: Within 48 hours of your report.
- **Initial Assessment**: Within 5 business days.
- **Resolution Timeline**: We aim to resolve critical vulnerabilities within 30 days.
- **Disclosure**: We will coordinate disclosure with you and credit reporters (unless anonymity is preferred).

### Scope

The following are in scope:

- Chronowarden backend (Python/FastAPI)
- Chronowarden frontend (SvelteKit)
- Docker images published to GHCR
- CI/CD pipeline security
- Dependency vulnerabilities

### Out of Scope

- Vulnerabilities in upstream dependencies (report to upstream maintainers)
- Issues in HashiCorp Vault or OpenBao themselves
- Social engineering attacks

## Security Practices

- All source files include SPDX license headers (REUSE compliant)
- Dependencies are regularly audited via `pip-audit` and `npm audit`
- Container images are scanned with Trivy
- OpenSSF Scorecard monitors project security posture
- SBOM (Software Bill of Materials) is generated for each release
