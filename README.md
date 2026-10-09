# Chronowarden
<!--
SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/fajfer/chronowarden/badge)](https://scorecard.dev/viewer/?uri=github.com/fajfer/chronowarden)

**Monitor and track expiring secrets across your Vault infrastructure**

<img src="https://raw.githubusercontent.com/fajfer/chronowarden/refs/heads/main/frontend/static/goat.png" width="258">

Chronowarden is a secret lifecycle observability service that syncs with your secret providers, tracking TTLs and rotation requirements through custom metadata. It provides a web UI and REST API to visualize secret health and alert on expiring credentials.

This is very early work being built with focus on compliance for financial institutions ([PCI DSS 4.0](https://www.pcisecuritystandards.org/document_library/), [DORA](https://www.eiopa.europa.eu/digital-operational-resilience-act-dora_en)) and best practices ([NIST SP 800-63B-4](https://csrc.nist.gov/pubs/sp/800/63/b/4/final)) regarding credential rotation.

Join us on [Matrix](https://matrix.to/#/#chronowarden:reszka.org) to discuss and troubleshoot!

## Features

- **Vendor neutrality** - Connect to multiple backends instances simultaneously
- **Credential Health Dashboard** - Visual status of secrets (OK, Warning, Expired, No TTL)
- **Severity Levels** - Classify secrets by (user-defined) compliance requirements (PCI-DSS, Critical, Default)
- **Secure** - Never reads actual secret values, only metadata
- **Real-Time Sync** - Live and on-demand synchronization with backends
- **Prometheus Metrics** - Built-in monitoring endpoint for alerting
- **Modern Web UI** - SvelteKit frontend with dark mode

## How does it work?

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   Vaults    │ ───► │ Chronowarden │ ───► │   Web UI    │
│ (Multiple)  │      │   Backend    │      │  (Svelte)   │
└─────────────┘      └──────────────┘      └─────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │   SQLite DB  │
                     │  (Metadata)  │
                     └──────────────┘
```

## Quick Start

### Docker
```bash
docker run --network=host --rm -p 8000:8000 \
    -v $(pwd)/config.yaml:/data/config.yaml \
  ghcr.io/fajfer/chronowarden:v0.5.0
```

Add `-v $(pwd)/chronowarden.db:/app/chronowarden.db` if you already have a DB

#### Building image
Production (default) — distroless, no shell, 86MB \
`docker build -t fajfer/chronowarden:0.5.0 .`

Development — full shell, git, --reload, 286MB \
`docker build --target dev -t fajfer/chronowarden:0.5.0-dev .`

### Prerequisites

- Python 3.12+ (tested on 3.13.5)
- Node.js 18+ (for frontend)
- Docker (optional, for dev Vaults)

### Backend Setup

1. **Install dependencies:**
   ```bash
   uv sync
   ```

2. **Configure vaults:**
   
   Copy the example config and add your Vault instances:
   ```bash
   cp config.example.yaml config.yaml
   ```

   Edit `config.yaml`:
   ```yaml
   vaults:
     - name: production
       address: https://vault.example.com:8200
       token_env: VAULT_PRODUCTION_TOKEN  # or token_file / token; AppRole is also supported
       mount_path: secret
       verify_ssl: true
       severity: critical  # default severity for every engine in this vault

   expiry_profiles:  # built-in profiles shown; add your own or override them
     default:
       rotation_period: "365d"
     critical:
       rotation_period: "6m"
     pci-dss-4.0:
       rotation_period: "90d"
   ```

   See [`config.example.yaml`](config.example.yaml) for every option, including per-engine and per-secret
   severity overrides. The config is validated strictly: unknown keys, unknown severities and invalid values
   stop the server at startup with a message naming each problem.

3. **Run the server:**
   ```bash
   uv run uvicorn chronowarden:app --reload
   ```

   API will be available at `http://localhost:8000`

### Frontend Setup

1. **Install dependencies:**
   ```bash
   cd frontend
   npm install
   ```

2. **Run development server:**
   ```bash
   npm run dev
   ```

   UI will be available at `http://localhost:5173`

   Optionally set `VITE_API_BASE_URL` to point the frontend API client at a custom base path
   (defaults to `/api/v1`).

## Development Environment

For local testing with dev Vault instances:

```bash
uv run python dev-setup.py
```

This script:
- Starts OpenBao (port 8200) and HashiCorp Vault (port 8201) containers
- Extracts root tokens from logs
- Creates `config.yaml` with all dev vaults configured

**Cleanup:**
```bash
docker stop vault-dev openbao-dev
docker rm vault-dev openbao-dev
```

## Vault Permissions

Chronowarden requires read/write access to **secret metadata only**. It never reads actual secret values.

**Required capabilities:**
```hcl
# For KV v2 engines
path "+/metadata/*" {
  capabilities = ["list", "read", "update"]
}

path "+/metadata" {
  capabilities = ["list"]
}

# Engine discovery
path "sys/mounts" {
  capabilities = ["read"]
}
```

**Custom metadata fields** (written by Chronowarden from `config.yaml`, which is the source of truth):
- `chronowarden_ttl` - Expiry date: the secret's last update plus its profile's rotation period
- `chronowarden_severity` - Severity level resolved from config. `none` means tracked but never rotated

## API Endpoints

### Secrets
- `GET /api/v1/secrets` - List all tracked secrets with metadata
  - Query params: `vault_name`, `engine_id`, `severity`
- `GET /api/v1/secrets/{id}` - Get secret metadata by ID

Severity is set in `config.yaml` only (per vault, engine or secret); the API is read-only for secrets.

### Sync
- `POST /api/v1/sync/vault/{vault_name}` - Trigger synchronization for a specific Vault instance
  - Scans the specified vault instance and updates local cache

### Vaults
- `GET /api/v1/vault/instances` - List configured Vault instances with connection status

### Health
- `GET /api/v1/health` - Health check endpoint (used by Kubernetes probes)
- `GET /api/v1/ready` - Readiness check endpoint
- `GET /api/v1/info` - API name and version
- `GET /api/v1/metrics` - Prometheus metrics

## Secret Status

| Status | Description | Condition |
|--------|-------------|-----------|
| 🟢 OK | Secret is healthy | `days_remaining > alert_threshold` |
| 🟡 Warning | Rotation needed soon | `0 < days_remaining ≤ alert_threshold` |
| 🔴 Expired | Rotation overdue | `days_remaining ≤ 0` |
| ⚪ No TTL | No rotation configured | `chronowarden_ttl` not set |

`alert_threshold` is set per expiry profile in `config.yaml` (default `30d`); see
[`config.example.yaml`](config.example.yaml).

## Testing

**Unit tests:**
```bash
uv run pytest
```

**With coverage:**
```bash
uv run pytest --cov=chronowarden --cov-report=html
```

## Integration Testing

Test compatibility with both HashiCorp Vault and OpenBao:

**OpenBao (port 8200):**
```bash
docker run -p 127.0.0.1:8200:8200 --name openbao-dev --detach quay.io/openbao/openbao
```

**HashiCorp Vault (port 8201):**
```bash
docker run -p 127.0.0.1:8201:8201 --cap-add=IPC_LOCK \
  -e 'VAULT_DEV_LISTEN_ADDRESS=0.0.0.0:8201' \
  -d --name=vault-dev hashicorp/vault
```

Chronowarden maintains compatibility with both platforms as [OpenBao intends to remain API compatible](https://openbao.org/api-docs/libraries/).

## Deployment

See [deploy/](deploy/) for:
- Docker Compose setup (`deploy/compose/`)
- Kubernetes manifests (`deploy/kubernetes/`)

## Roadmap

Milestones are tracked on [GitHub](https://github.com/fajfer/chronowarden/milestones). Design decisions are recorded
as ADRs in [`.ai/adr/`](.ai/adr/README.md).

| Milestone | Goal | Issues | Decisions |
|---|---|---|---|
| **0.6 Foundations** | Clean core: config-only severity, no pre-1.0 shims, validated config, reliable sync, better logs, per-profile alert threshold | #73, #30, #12, #59, #58, #70, #19, #57, #31 | n/a |
| **0.7 Compliance evidence** | Systems (CMDB URI, asset number, owners) and owners assigned to secrets, rotation confirmation and audit log, automatic reports, dev-setup rework | #61, #24, #78 | [ADR-010](.ai/adr/ADR-010-owners-systems-and-permissions.md), [ADR-014](.ai/adr/ADR-014-rotation-confirmation-and-audit-log.md) |
| **0.8 Alerting** | Scheduled and headless sync, per-secret metrics with owner and system labels for Prometheus/Alertmanager | #48, #71 | [ADR-012](.ai/adr/ADR-012-alertmanager-native-alerting.md), [ADR-013](.ai/adr/ADR-013-in-process-and-headless-sync.md) |
| **0.9 Access control** | Authentication for UI and API (only owners edit their secrets), then RBAC | n/a | [ADR-015](.ai/adr/ADR-015-authentication.md) |
| **1.0** | Stability promise for config, API, metrics and DB schema | n/a | [ADR-016](.ai/adr/ADR-016-stability-policy-for-1-0.md) |
| **1.x Backends** | Generic provider registry, then public cloud vaults | #72 | [ADR-011](.ai/adr/ADR-011-provider-registry.md) |

## License

Licensed under the [EUPL-1.2](LICENSE) - see [LICENSES/](LICENSES/) for full text.

## Logo & mascot

<img src="https://raw.githubusercontent.com/fajfer/chronowarden/refs/heads/main/frontend/static/logo.png" width=600>

Our logo and mascot (currently unnamed), designed by Aleksandra Lejman, wears a vintage, polish banking guard uniform to symbolize security and honor the banking sector where the idea for this software was born.

The choice of a goat for the mascot was inspired by the author's daughter, Irena, who is a huge fan of the classic [Koziołek Matołek](https://en.wikipedia.org/wiki/Kozio%C5%82ek_Mato%C5%82ek) series

## Support

Community support is available through [Matrix](https://matrix.to/#/#gcups:fsfe.org) channel as well as issues on GitHub

For commercial support, consultations and training feel free to reach me via email at damian (at) fajfer.org to discuss your needs and get a custom quote.

## Docs

uv run mkdocs serve