<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# GCP Secret Manager provider

- **Status:** approved
- **Date:** 2026-10-29
- **Issue:** none

## Goal

An operator adds a `vaults:` entry with `type: gcp-secret-manager` and sees that project's secrets in Chronowarden
like Vault ones: severity and TTL from config, status and expiry, rotation detection from new versions, systems,
owners, confirmations, compliance and alerts. Chronowarden reads only secret and version metadata (never payloads)
and writes its `chronowarden_*` keys as secret annotations (ADR-006, ADR-011).

## Non-goals

- Accessing secret payloads (`versions.access`, ADR-004).
- Listing projects through Resource Manager; each entry names one project.
- Using Secret Manager's own `expire_time` or rotation schedule as Chronowarden's TTL (see Notes).
- Rotating secrets.

## Scope

`chronowarden/integrations/gcp_secret_manager.py` (new), `chronowarden/integrations/__init__.py`,
`chronowarden/config.py`, `pyproject.toml` (optional extra), `Dockerfile`, README "Permissions", `docs/` guide
(AI-draft notice), `config.example.yaml`, architecture model.

## Load

- [root AGENTS.md](../../AGENTS.md)
- [integrations](../../chronowarden/integrations/AGENTS.md), [architecture](../../architecture/AGENTS.md)
- [ADR-011](../adr/ADR-011-provider-registry.md), [ADR-004](../adr/ADR-004-metadata-only-access.md),
  [ADR-006](../adr/ADR-006-config-source-of-truth.md), [ADR-009](../adr/ADR-009-offline-tolerant-reconnect.md)
- [Azure Key Vault spec](2026-10-29-azure-key-vault.md) (`ProviderConfigBase`, if it lands first)
- `chronowarden/integrations/base.py`, `chronowarden/integrations/vault.py`, `chronowarden/metadata.py`

## ADRs affected

None: ADR-011 names GCP Secret Manager (labels/annotations) as a qualifying provider.

## Design

**Config** (strict, on `ProviderConfigBase`):

```yaml
vaults:
  - name: billing-prod
    type: gcp-secret-manager
    project: billing-prod-123456
    location: null                      # null = global secrets; a region (europe-west4) = regional secrets
    # Credentials: Application Default Credentials (workload identity, GOOGLE_APPLICATION_CREDENTIALS) unless set
    credentials_file: /run/secrets/gcp-sa.json
    severity: high
    engines:
      - name: billing-prod-123456       # the single engine is the project
        secrets:
          - path: stripe-api-key
            severity: critical
```

**Mapping to the interface** (Python SDK `google-cloud-secret-manager`):

| `BaseIntegration` | Secret Manager |
|---|---|
| `discover_engines()` | one engine: `{"path": <project>, "type": "gcp-secret-manager"}` |
| `list_secrets("")` | `list_secrets(parent)` short names; never folders |
| `get_secret_metadata(name)` | `get_secret` (metadata only, no payload) + `list_secret_versions`. Version ids are already integers; `created_time` = `create_time`, `deletion_time` = `destroy_time` (or disabled), `destroyed` from `state`; `custom_metadata` = annotations |
| `write_secret_metadata` | read the secret, merge `chronowarden_*` into annotations, `update_secret(update_mask=annotations)` with the read `etag`; on an etag conflict, re-read and retry once. Race-free, unlike Vault |
| `check_health()` | `list_secrets(page_size=1)` |
| `last_error_kind` | `Unauthenticated` / `PermissionDenied` / `DefaultCredentialsError` → `auth`; `ServiceUnavailable` / `DeadlineExceeded` / transport errors → `offline`; other `GoogleAPICallError` → `vault` |

**Annotations, not labels**: label values only allow lowercase letters, digits, `-` and `_` (63 characters), which
fits today's values but no free-form ones; annotations hold any string up to 16 KiB per secret. Keys
`chronowarden_severity`, `chronowarden_ttl` and `chronowarden_privileged` are valid annotation keys.

**Permissions** (README): a custom role with `secretmanager.secrets.list`, `secretmanager.secrets.get`,
`secretmanager.secrets.update` and `secretmanager.versions.list`; never `secretmanager.versions.access`.
`roles/secretmanager.viewer` covers the reads; no predefined role grants `update` without `access`.

## Tasks

| # | Task | Load | Done when | Status | Commit |
|---|---|---|---|---|---|
| 1 | Verify that `secrets.update` alone can change annotations and how an etag conflict is reported; record here | — | Both facts cited with links in Notes | todo | |
| 2 | `GcpSecretManagerConfig` in the `vaults` union (on `ProviderConfigBase`, created here if Azure isn't merged) | core, `chronowarden/config.py`, `tests/test_config.py` | Existing configs load unchanged; each validation error tested | todo | |
| 3 | `GcpSecretManagerIntegration` + builder registered; `gcp` optional extra | integrations, `base.py`, `pyproject.toml` | `tests/test_gcp_secret_manager.py` with a mocked client: listing, versions, annotation merge with etag retry, every error kind, no `access_secret_version` call | todo | |
| 4 | Sync end to end against a mocked client | `chronowarden/api/sync.py`, `tests/test_sync_api.py` | A synced GCP secret has status, owners and a detected rotation | todo | |
| 5 | Integration test | — | dropped: no official emulator; covered by task 3 and 4 mocks | dropped | |
| 6 | Images, README permissions, `docs/guides/gcp-secret-manager.md` (AI draft), `config.example.yaml`, architecture model, integrations AGENTS, CHANGELOG | deploy, architecture | `check_agents_docs.py` and LikeC4 pass; both images build; the guide names `expire_time` and rotation as not used yet | todo | |

## Validation

`uv run black --check . && uv run ruff check . && uv run pytest`, `cd frontend && npm run check`,
`python3 scripts/check_agents_docs.py`, `docker build -t chronowarden:test .` (and `--target headless`).

## Notes

- **Native expiry, to revisit in a future audit:** Secret Manager secrets carry their own `expire_time` (or `ttl`)
  and an optional rotation schedule (`rotation.next_rotation_time`, `rotation_period`). This provider ignores them
  for now: the TTL comes only from config (ADR-006). The user guide says so, and a future audit should decide whether
  to show them or let them inform the TTL (the latter needs an ADR).

## Open questions

Asked and answered 2026-10-29:

1. Scope of one entry: **one project**, with **regional secrets** through `location`; Application Default
   Credentials, with an optional `credentials_file`.
2. Secret Manager's own `expire_time` and rotation schedule: **ignored for now**, documented, and revisited in a
   future audit (Notes).
3. Integration test: **mocked client only** (there is no official emulator).

Still open (proposed default applies unless the maintainer says otherwise):

4. Order: Azure first (it creates `ProviderConfigBase`), then GCP.
