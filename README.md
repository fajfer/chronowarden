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

> [!WARNING]
> **The API and UI have no authentication yet** (planned for a later release). Anyone who can reach the HTTP port
> can read all tracked metadata (including other teams' custom metadata values kept in the audit log) and trigger
> syncs. Run Chronowarden only on a trusted network or behind an authenticating reverse proxy, and never expose it
> directly to the internet. Set `allowed_hosts` in `config.yaml` to the names you serve it under: other web pages
> then can't reach it through DNS rebinding (cross-site writes are refused either way).

Join us on [Matrix](https://matrix.to/#/#chronowarden:reszka.org) to discuss and troubleshoot!

## Features

- **Vendor neutrality** - Connect to multiple backends instances simultaneously
- **Credential Health Dashboard** - Visual status of secrets (OK, Warning, Expired, No TTL)
- **Compliance Evidence** - Privileged flag (`chronowarden_privileged`), gap warnings, opt-in reporting periods and
  frozen, SHA-256 hashed inventory snapshots with CSV/JSON export; a Compliance tab with summaries and a tree
- **Audit Log** - Append-only, hash-chained record of every change (assignments, systems, owners, removed
  secrets, config), exportable as JSON Lines
- **Systems and Owners** - Assign secrets to business systems (CMDB link, asset number) and owners, and see who is
  responsible for each secret
- **Severity Levels** - Classify secrets by (user-defined) compliance requirements (PCI-DSS, Critical, Default)
- **Secure** - Never reads actual secret values, only metadata
- **Real-Time Sync** - Live and on-demand synchronization with backends
- **Prometheus Metrics** - Optional monitoring endpoint (`metrics.enabled: true`; off by default)
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
  ghcr.io/fajfer/chronowarden:v0.7.2
```

Add `-v $(pwd)/chronowarden.db:/app/chronowarden.db` to keep the database. From 0.7 it holds system and owner
assignments that can't be rebuilt from Vault, so **back up `chronowarden.db`**; it is upgraded automatically on
startup.

#### Building image
Production (default) — distroless, no shell, 86MB \
`docker build -t fajfer/chronowarden:0.7.2 .`

Development — full shell, git, --reload, 286MB \
`docker build --target dev -t fajfer/chronowarden:0.7.2-dev .`

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

For local testing with dev Vault instances (podman preferred, docker works too):

```bash
uv run python dev-setup.py
```

This script:
- starts OpenBao (port 8200) and HashiCorp Vault (port 8201) dev servers with podman, or docker if podman isn't
  installed (`CHRONOWARDEN_CONTAINER_RUNTIME=docker` to choose);
- seeds three KV v2 engines with sample secrets and an AppRole with the policy below;
- writes `config.yaml` for both (only if it doesn't exist or was written by `dev-setup.py`; `--force` replaces
  another one, `--config PATH` writes elsewhere) and prints the dev root tokens.

**Cleanup** (stops and removes both dev containers):
```bash
uv run python dev-setup.py --cleanup
```

**Integration tests** run Chronowarden against real OpenBao and Vault containers (testcontainers); CI runs them too:
```bash
uv run pytest -m integration
```
With podman, point testcontainers at its API socket: `DOCKER_HOST=unix://$XDG_RUNTIME_DIR/podman/podman.sock`
(`systemctl --user start podman.socket`) and `TESTCONTAINERS_RYUK_DISABLED=true`.

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
- `chronowarden_privileged` - Written only when someone marks a secret privileged in Chronowarden (or reverts that);
  you can also set it yourself (`true`)

Chronowarden merges these keys into the existing metadata; other keys and settings stay as they are. It reads the
metadata and writes it back, so a change someone makes to the same secret's custom metadata between that read and
write is lost (Vault has no check-and-set for metadata).

## API Endpoints

### Secrets
- `GET /api/v1/secrets` - List all tracked secrets with metadata
  - Query params: `vault_name`, `engine_id`, `severity`, `system_id`, `owner_id` (effective owner), `unassigned`,
    `include_removed` (secrets deleted in the backend are hidden by default)
- `GET /api/v1/secrets/{id}` - Get secret metadata by ID, including its system, owners and effective owners
- `PUT /api/v1/secrets/{id}/system` - Assign the secret to a system (`{"system_id": "..."}`, or `null` to unassign)
- `PUT /api/v1/secrets/{id}/owners` - Replace the secret's owners (`{"owner_ids": [...]}`)
- `POST /api/v1/secrets/{id}/confirmations` - Confirm the newest version is applied (`{"applied_at": "...",
  "confirmed_by": "pipeline"}`); the next rotation counts from that date if it is later than the backend update
- `DELETE /api/v1/secrets/{id}`, `DELETE /api/v1/secrets/removed` - Purge secrets that sync no longer finds in their
  backend, with their assignments (`removed` takes `vault_name`/`engine_id`); a secret that still exists gives `409`

Severity is set in `config.yaml` only (per vault, engine or secret). A secret's effective owners are its own owners,
or else its system's owners.

### Systems and owners
- `GET/POST /api/v1/systems/`, `GET/PUT/DELETE /api/v1/systems/{id}` - Systems (name, description, CMDB URI, asset
  number); deleting a system that still has secrets returns `409` with their list
- `PUT /api/v1/systems/{id}/owners` - Replace a system's owners
- `GET/POST /api/v1/owners/`, `GET/PUT/DELETE /api/v1/owners/{id}` - Owners; deleting one removes it from every
  secret and system

### Sync
- `POST /api/v1/sync/vault/{vault_name}` - Trigger synchronization for a specific Vault instance
  - Scans the specified vault instance and updates local cache
  - A disconnected vault is reconnected first. If that fails, the response is `503` with the `reason`
    (`offline`, `auth`, ...) and whether a background retry is scheduled; the vault is then synced
    automatically as soon as the retry reconnects it

### Compliance
- `PUT /api/v1/secrets/{id}/privileged` - Set `chronowarden_privileged` in the backend (`{"privileged": true}`)
- `GET /api/v1/compliance/summary` - Total and privileged secrets per vault, engine and system
- `GET /api/v1/compliance/gaps` - Secrets without owner or system, expired or without TTL, privileged without owner,
  or awaiting confirmation (scope: `vaults`, `engines`, `systems`, `privileged_only`, or `cadence`)
- `GET /api/v1/compliance/periods` - Ended reporting periods and the snapshot closing each
- `GET/POST /api/v1/compliance/snapshots` - Frozen snapshots: ad hoc (`label`, `scope`) or closing a period
  (`cadence`, `period`; `supersedes` to correct one); `GET .../snapshots/{id}.json` returns the hashed bytes,
  `.csv` the rows
- `GET /api/v1/compliance/settings` - Reporting and confirmation settings from `config.yaml`

Snapshot exports list secret paths and owners; keep them as confidential as the instance itself.

### Audit log
- `GET /api/v1/audit/events` - Change history, newest first (filters: `vault_name`, `engine_id`, `secret_path`,
  `event_type`, `subject`, `since`, `until`; paging with `before_id`)
- `GET /api/v1/audit/events.jsonl` - Export of the whole log as stored, for archiving or independent checks
- `GET /api/v1/audit/verify` - Recompute the hash chain; returns the head hash to note down
- `POST /api/v1/audit/events/{id}/revert` - Undo a system or owner assignment change (recorded as a new event);
  backend data, severity and TTL can't be reverted from Chronowarden
- `GET /api/v1/secrets/{id}/history` - Changes to one secret

### Vaults
- `GET /api/v1/vault/instances` - List configured Vault instances with connection status

### Health
- `GET /api/v1/health` - Health check endpoint (used by Kubernetes probes)
- `GET /api/v1/ready` - Readiness check endpoint
- `GET /api/v1/info` - API name and version
- `GET /api/v1/metrics` - Prometheus metrics, when `metrics.enabled: true` is set (otherwise `404`)

## Secret Status

| Status | Description | Condition |
|--------|-------------|-----------|
| 🟢 OK | Secret is healthy | `days_remaining > alert_threshold` |
| 🟡 Warning | Rotation needed soon | `0 < days_remaining ≤ alert_threshold` |
| 🔴 Expired | Rotation overdue | `days_remaining ≤ 0` |
| ⚪ No TTL | No rotation configured | `chronowarden_ttl` not set |

Where rotations must be confirmed (`confirmation_required`, per vault, engine or secret), a new version is also
shown as **awaiting confirmation** until someone confirms it was applied, and as overdue after `confirmation_grace`.

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

## Verifying releases

From 0.7.0 on, every release is built by GitHub Actions from a tag and comes with
[SLSA Build L3](https://slsa.dev/spec/v1.1/levels) provenance and a [cosign](https://docs.sigstore.dev/) keyless
signature. Verify an image by its digest:

```bash
DIGEST=$(docker buildx imagetools inspect ghcr.io/fajfer/chronowarden:v0.7.0 --format '{{json .Manifest.Digest}}' | tr -d '"')

# Built by this repository's workflow from the tag (SLSA provenance)
slsa-verifier verify-image "ghcr.io/fajfer/chronowarden@${DIGEST}" \
  --source-uri github.com/fajfer/chronowarden --source-tag v0.7.0

# Signed by the release workflow
cosign verify "ghcr.io/fajfer/chronowarden@${DIGEST}" \
  --certificate-identity-regexp '^https://github.com/fajfer/chronowarden/\.github/workflows/docker\.yaml@refs/tags/v' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

Each release also carries SBOMs in [CycloneDX 1.6](https://cyclonedx.org/) and [SPDX 2.3](https://spdx.dev/)
JSON: one per image platform (`chronowarden-image-{amd64,arm64}.*`) and one for the source
(`chronowarden-source.*`, from `uv.lock` and `frontend/package-lock.json`). The image SBOMs are also attested to the
image:

```bash
cosign verify-attestation "ghcr.io/fajfer/chronowarden@${DIGEST}" --type cyclonedx \
  --certificate-identity-regexp '^https://github.com/fajfer/chronowarden/\.github/workflows/docker\.yaml@refs/tags/v' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

The wheel, sdist and source SBOMs on the [GitHub release](https://github.com/fajfer/chronowarden/releases) are covered by
`chronowarden.intoto.jsonl`:

```bash
slsa-verifier verify-artifact chronowarden-0.7.0-py3-none-any.whl \
  --provenance-path chronowarden.intoto.jsonl --source-uri github.com/fajfer/chronowarden --source-tag v0.7.0
```

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
| **0.7 Compliance evidence** | Systems and owners, hash-chained audit log with change history and revert, rotation confirmation, privileged flag, frozen snapshots and reporting periods, removed secrets, DB migrations, optional metrics, signed releases with SLSA provenance and SBOMs, fuzzing, dev-setup rework, SvelteKit 3 | #61, #24, #76, #78, #79, #86, #87-#96 | [ADR-010](.ai/adr/ADR-010-owners-systems-and-permissions.md), [ADR-014](.ai/adr/ADR-014-rotation-confirmation-and-audit-log.md), [ADR-017](.ai/adr/ADR-017-sqlite-holds-assignments.md), [ADR-018](.ai/adr/ADR-018-release-integrity.md), [ADR-021](.ai/adr/ADR-021-rotation-handover.md), [ADR-023](.ai/adr/ADR-023-schema-migrations-with-user-version.md) |
| **0.7.x Policies and reports** | Compliance policies in config (example YAML for KNF KRI ICT, PCI DSS 4.0, DORA in the docs), PDF reports with Typst | #97, #98 | [ADR-019](.ai/adr/ADR-019-compliance-policies-as-config.md), [ADR-020](.ai/adr/ADR-020-pdf-reports-with-typst.md) |
| **0.8 Alerting** | Built-in webhook alerting to owners, scheduled and headless sync, grace-period escalation | #48, #71, #74, #99 | [ADR-022](.ai/adr/ADR-022-webhooks-and-optional-metrics.md), [ADR-013](.ai/adr/ADR-013-in-process-and-headless-sync.md) |
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