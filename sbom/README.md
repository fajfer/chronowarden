# SPDX-FileCopyrightText: 2025 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

# SBOM Directory

This directory contains Software Bill of Materials (SBOM) files for Chronowarden.

## Purpose

SBOMs are critical for:
- **DORA Compliance**: Article 28 requires ICT third-party risk management
- **Supply Chain Security**: Track all dependencies and their versions
- **Vulnerability Management**: Identify affected components when CVEs are disclosed
- **License Compliance**: Ensure all dependencies are properly licensed

## Generating SBOMs

### Using Docker (Recommended)

```bash
# Generate SBOM for backend source
docker run --rm -v $(pwd):/src anchore/syft:latest \
  packages dir:/src/backend \
  -o spdx-json=/src/sbom/chronowarden-backend.spdx.json

# Generate SBOM for Docker image
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  anchore/syft:latest \
  packages chronowarden-backend:latest \
  -o spdx-json > sbom/chronowarden-backend-image.spdx.json
```

### Using Local Syft

```bash
# Install syft
curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh -s -- -b /usr/local/bin

# Generate SBOM
syft packages ./backend -o spdx-json > sbom/chronowarden-backend.spdx.json
```

## CI/CD Integration

See `docs/COMPLIANCE.md` for GitHub Actions workflow examples.

## File Formats

| Format | Extension | Use Case |
|--------|-----------|----------|
| SPDX JSON | `.spdx.json` | Standard interchange format |
| CycloneDX JSON | `.cdx.json` | Vulnerability scanning tools |
| SPDX Tag-Value | `.spdx` | Human-readable format |

## Retention

Per DORA and KNF requirements, SBOMs should be retained for at least 3 years
alongside release artifacts.
