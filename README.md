# Chronowarden
<!--
SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->

**Monitor and track expiring secrets across your Vault infrastructure**

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
  ghcr.io/fajfer/chronowarden:v0.2.2
```

Add `-v $(pwd)/chronowarden.db:/app/chronowarden.db` if you already have a DB

#### Building image
Production (default) — distroless, no shell, 86MB \
`docker build -t fajfer/chronowarden:0.2.2 .`

Development — full shell, git, --reload, 286MB \
`docker build --target dev -t fajfer/chronowarden:0.2.2-dev .`

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
     production:
       url: https://vault.example.com
       token: your-vault-token
       verify_ssl: true
       max_versions_per_secret: 5
   
   severity_levels:
     critical:
       rotation_period_days: 30
       alert_threshold_days: 7
     pci-dss-4.0:
       rotation_period_days: 90
       alert_threshold_days: 14
     default:
       rotation_period_days: 365
       alert_threshold_days: 30
   ```

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

## Development Environment

For local testing with dev Vault instances:

```bash
uv run python dev-setup.py
```

This script:
- Starts OpenBao (port 8200) and Vault (ports 8201, 8202) containers
- Extracts root tokens from logs
- Creates `config.yaml` with all dev vaults configured

**Cleanup:**
```bash
docker stop dev-vault-1.20.1 dev-vault-1.21.3 openbao-dev
docker rm dev-vault-1.20.1 dev-vault-1.21.3 openbao-dev
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

**Custom metadata fields:**
- `chronowarden_ttl` - Target rotation period (ISO8601 duration)
- `chronowarden_severity` - Severity level (user-defined)
- `chronowarden_enabled` - Whether to track this secret (true/false)

## API Endpoints

### Secrets
- `GET /api/v1/secrets` - List all tracked secrets with metadata
  - Query params: `vault_name`, `engine_id`, `severity`, `enabled`
- `GET /api/v1/secrets/{id}` - Get secret metadata by ID
- `PATCH /api/v1/secrets/{id}` - Update secret metadata (severity, enabled, ttl)

### Sync
- `POST /api/v1/sync` - Trigger synchronization with Vault instances
  - Scans all configured vaults and updates local cache

### Vaults
- `GET /api/v1/vaults` - List configured Vault instances with connection status

### Health
- `GET /health` - Health check endpoint
- `GET /metrics` - Prometheus metrics

## Secret Status

| Status | Description | Condition |
|--------|-------------|-----------|
| 🟢 OK | Secret is healthy | `days_remaining > alert_threshold` |
| 🟡 Warning | Rotation needed soon | `0 < days_remaining ≤ alert_threshold` |
| 🔴 Expired | Rotation overdue | `days_remaining ≤ 0` |
| ⚪ No TTL | No rotation configured | `chronowarden_ttl` not set |

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
  -d --name=dev-vault hashicorp/vault
```

Chronowarden maintains compatibility with both platforms as [OpenBao intends to remain API compatible](https://openbao.org/api-docs/libraries/).

## Deployment

See [deploy/](deploy/) for:
- Docker Compose setup (`deploy/compose/`)
- Kubernetes manifests (`deploy/kubernetes/`)

## Roadmap

- RBAC support
- Support assigning each secret/engine/provider with internal systems
- Generate automatic reports from Chronowarden for internal systems
- Better support for routing alerts
- Support additional backends for public cloud providers and their vaults

## License

Licensed under the [EUPL-1.2](LICENSE) - see [LICENSES/](LICENSES/) for full text.

## Support

Community support is available through [Matrix](https://matrix.to/#/#gcups:fsfe.org) channel as well as issues on GitHub

For commercial support, consultations and training feel free to reach me via email at damian (at) fajfer.org to discuss your needs and get a custom quote.

