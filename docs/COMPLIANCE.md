<!--
SPDX-FileCopyrightText: 2025 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->

# Chronowarden Financial Sector Compliance Guide

This document outlines how Chronowarden supports compliance with financial sector regulations,
particularly for the Polish banking sector and European Union directives.

## Table of Contents

- [Overview](#overview)
- [DORA Compliance](#dora-compliance)
- [Polish Banking Sector (KNF)](#polish-banking-sector-knf)
- [SPDX and SBOM](#spdx-and-sbom)
- [Security Features](#security-features)
- [Audit and Logging](#audit-and-logging)
- [Deployment Considerations](#deployment-considerations)

## Overview

Chronowarden is designed with financial sector compliance in mind, providing:

- **Secret lifecycle management** with expiration tracking
- **Audit logging** for all secret access and modifications
- **Integration** with enterprise secret management solutions (HashiCorp Vault, Azure Key Vault)
- **SBOM generation** for software supply chain security
- **SPDX-compliant licensing** for regulatory transparency

## DORA Compliance

### Digital Operational Resilience Act (EU 2022/2554)

DORA establishes requirements for ICT risk management in the financial sector. Chronowarden
addresses several DORA requirements:

#### Article 6 - ICT Risk Management Framework

| DORA Requirement | Chronowarden Feature |
|-----------------|---------------------|
| Identification of ICT assets | Secret inventory and tracking |
| Continuous monitoring | Expiration date monitoring with alerts |
| Incident detection | Prometheus metrics for anomaly detection |
| Documentation | Comprehensive logging and audit trails |

#### Article 9 - Protection and Prevention

| DORA Requirement | Chronowarden Feature |
|-----------------|---------------------|
| Access control | Integration with Vault/Azure RBAC |
| Encryption | Secrets stored encrypted at rest |
| Secure communication | TLS encryption for all API calls |
| Authentication | Token-based authentication |

#### Article 11 - ICT Response and Recovery

| DORA Requirement | Chronowarden Feature |
|-----------------|---------------------|
| Alert mechanisms | Expiring secret notifications |
| Backup procedures | Integration with enterprise backup solutions |
| Recovery testing | Health check endpoints for monitoring |

#### Article 28 - ICT Third-Party Risk

| DORA Requirement | Chronowarden Feature |
|-----------------|---------------------|
| Supply chain security | SBOM generation for dependencies |
| Vendor assessment | SPDX licensing compliance |
| Continuous monitoring | Prometheus metrics and health checks |

### DORA Implementation Timeline

- **January 2025**: DORA enforcement begins
- Chronowarden provides tools for ongoing compliance monitoring

## Polish Banking Sector (KNF)

### KNF Recommendations

The Polish Financial Supervision Authority (Komisja Nadzoru Finansowego) has specific
requirements for IT systems in financial institutions.

#### Recommendation D (IT Management)

| KNF Requirement | Chronowarden Feature |
|-----------------|---------------------|
| IT system inventory | Secret and certificate tracking |
| Change management | Version tracking for secrets |
| Access management | RBAC integration |
| Security monitoring | Real-time expiration alerts |

#### Recommendation M (Operational Risk)

| KNF Requirement | Chronowarden Feature |
|-----------------|---------------------|
| Risk identification | Expiring credentials identification |
| Risk monitoring | Dashboard for secret health |
| Incident management | Alert notifications |
| Business continuity | High availability deployment |

### Compliance Checklist for Polish Banks

- [ ] Secret inventory documented
- [ ] Expiration alerts configured (30+ days advance)
- [ ] Audit logging enabled
- [ ] RBAC policies defined
- [ ] Incident response procedures established
- [ ] SBOM generated and archived
- [ ] Third-party dependency review completed

## SPDX and SBOM

### Software Bill of Materials (SBOM)

SBOM generation is critical for:

1. **Supply chain security** - Identifying all dependencies
2. **Vulnerability management** - Tracking CVEs in dependencies
3. **Regulatory compliance** - DORA Article 28 requirements
4. **License compliance** - Ensuring all dependencies are properly licensed

### Generating SBOM

Chronowarden supports SBOM generation using Syft:

```bash
# Generate SBOM in SPDX format
docker run --rm -v $(pwd):/src anchore/syft:latest \
  packages dir:/src/backend \
  -o spdx-json=/src/sbom/chronowarden-backend.spdx.json

# Generate SBOM in CycloneDX format
docker run --rm -v $(pwd):/src anchore/syft:latest \
  packages dir:/src/backend \
  -o cyclonedx-json=/src/sbom/chronowarden-backend.cdx.json

# Generate SBOM for Docker image
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  anchore/syft:latest \
  packages chronowarden-backend:latest \
  -o spdx-json > sbom/chronowarden-backend-image.spdx.json
```

### Automated SBOM Generation in CI/CD

```yaml
# Example GitHub Actions workflow
- name: Generate SBOM
  uses: anchore/sbom-action@v0
  with:
    image: chronowarden-backend:${{ github.sha }}
    format: spdx-json
    output-file: sbom.spdx.json
    
- name: Archive SBOM
  uses: actions/upload-artifact@v4
  with:
    name: sbom
    path: sbom.spdx.json
```

### SPDX License Headers

All source files include SPDX license headers:

```python
# SPDX-FileCopyrightText: 2025 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2
```

This ensures:
- Clear copyright attribution
- Machine-readable license identification
- Compliance with REUSE specification

### EUPL-1.2 License

Chronowarden is licensed under EUPL-1.2 (European Union Public License), which:
- Is compatible with major open source licenses
- Is officially recognized by the EU
- Provides legal clarity for European institutions
- Supports multilingual legal validity

## Security Features

### Encryption

| Feature | Implementation |
|---------|----------------|
| At-rest encryption | Via Vault/Azure Key Vault |
| In-transit encryption | TLS 1.3 |
| Token encryption | Industry standard methods |

### Authentication & Authorization

| Feature | Implementation |
|---------|----------------|
| API authentication | Bearer tokens |
| Vault authentication | Token, AppRole, Kubernetes |
| Azure authentication | DefaultAzureCredential |
| RBAC | Via backend secret stores |

### Container Security

| Feature | Implementation |
|---------|----------------|
| Base image | Distroless (minimal CVE surface) |
| User | Non-root execution |
| Filesystem | Read-only root |
| Capabilities | All dropped |
| Seccomp | RuntimeDefault profile |

## Audit and Logging

### Log Format

All operations are logged with:
- Timestamp (ISO 8601)
- Operation type
- User/service identity
- Resource accessed
- Result (success/failure)
- Request ID for correlation

### Log Categories

| Category | Level | Description |
|----------|-------|-------------|
| `chronowarden.api` | INFO | API request/response |
| `chronowarden.integrations` | INFO | Backend operations |
| `chronowarden.security` | WARNING | Security events |
| `chronowarden.audit` | INFO | Compliance-relevant events |

### Log Retention

For DORA compliance, logs should be retained for:
- **Minimum**: 3 years
- **Recommended**: 7 years (aligned with KNF recommendations)

### Prometheus Metrics

Available metrics for monitoring:

```
# API metrics
chronowarden_api_requests_total{method, endpoint, status}
chronowarden_api_request_duration_seconds{method, endpoint}

# Secret metrics
chronowarden_secrets_total{engine_type}
chronowarden_secrets_expiring_soon{engine_type}
chronowarden_secrets_expired{engine_type}

# Integration metrics
chronowarden_integration_health{backend}
chronowarden_integration_requests_total{backend, operation}
```

## Deployment Considerations

### High Availability

For financial sector deployments:

```yaml
# Minimum production configuration
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1
      maxSurge: 1
```

### Pod Disruption Budget

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: chronowarden-pdb
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: chronowarden
```

### Network Policies

Restrict network access to:
- Ingress: Only from authorized sources
- Egress: Only to secret backends (Vault, Azure)

### Backup and Recovery

1. **Secret metadata backup**: Via Kubernetes ConfigMaps/Secrets backup
2. **Configuration backup**: GitOps (ArgoCD, Flux)
3. **Recovery testing**: Regular DR drills

### Compliance Monitoring Dashboard

Recommended Grafana dashboard panels:

1. **Secret Expiration Overview**
   - Expired secrets count
   - Expiring within 7/30/90 days
   
2. **Integration Health**
   - Vault/Azure connectivity
   - Authentication status
   
3. **API Health**
   - Request rate
   - Error rate
   - Latency percentiles

4. **Compliance Metrics**
   - Audit log volume
   - Security event count

## Appendix: Regulatory References

### EU Regulations

- [DORA - Regulation (EU) 2022/2554](https://eur-lex.europa.eu/eli/reg/2022/2554)
- [GDPR - Regulation (EU) 2016/679](https://eur-lex.europa.eu/eli/reg/2016/679)
- [NIS2 - Directive (EU) 2022/2555](https://eur-lex.europa.eu/eli/dir/2022/2555)

### Polish Regulations

- [KNF Recommendation D](https://www.knf.gov.pl/)
- [KNF Recommendation M](https://www.knf.gov.pl/)
- [Act on Cybersecurity (Ustawa o krajowym systemie cyberbezpieczeństwa)](https://isap.sejm.gov.pl/)

### Standards

- [ISO 27001:2022](https://www.iso.org/standard/27001) - Information Security Management
- [ISO 27017:2015](https://www.iso.org/standard/43757.html) - Cloud Security
- [SPDX 2.3](https://spdx.github.io/spdx-spec/v2.3/) - Software Package Data Exchange
- [CycloneDX 1.5](https://cyclonedx.org/) - SBOM Standard
