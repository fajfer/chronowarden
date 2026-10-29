<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Azure Key Vault provider

- **Status:** approved
- **Date:** 2026-10-29
- **Issue:** none

## Goal

An operator adds a `vaults:` entry with `type: azure-key-vault` and sees that Key Vault's secrets in Chronowarden
like Vault ones: severity and TTL from config, status and expiry, rotation detection from new versions, systems,
owners, confirmations, compliance and alerts. Chronowarden reads only secret properties (never values) and writes its
`chronowarden_*` keys as secret tags (ADR-006, ADR-011).

## Non-goals

- Reading secret values, keys or certificates (ADR-004).
- Discovering key vaults through Azure Resource Manager (subscriptions, resource groups); each entry names one vault.
- Using Key Vault's own `expires_on` as Chronowarden's TTL (see Notes).
- Rotating secrets.

## Scope

`chronowarden/integrations/azure_key_vault.py` (new), `chronowarden/integrations/__init__.py`,
`chronowarden/config.py`, `pyproject.toml` (optional extra), `Dockerfile`, README "Permissions", `docs/` guide
(AI-draft notice), `config.example.yaml`, architecture model.

## Load

- [root AGENTS.md](../../AGENTS.md)
- [integrations](../../chronowarden/integrations/AGENTS.md), [architecture](../../architecture/AGENTS.md)
- [ADR-011](../adr/ADR-011-provider-registry.md), [ADR-004](../adr/ADR-004-metadata-only-access.md),
  [ADR-006](../adr/ADR-006-config-source-of-truth.md), [ADR-009](../adr/ADR-009-offline-tolerant-reconnect.md)
- `chronowarden/integrations/base.py`, `chronowarden/integrations/vault.py`, `chronowarden/metadata.py`

## ADRs affected

None: ADR-011 names Azure Key Vault (tags) as a qualifying provider.

## Design

**Config** (strict; the shared fields move to a `ProviderConfigBase` that `VaultConfig` also extends):

```yaml
vaults:
  - name: payments-kv
    type: azure-key-vault
    vault_url: https://payments-kv.vault.azure.net/
    # Credentials: DefaultAzureCredential (workload identity, managed identity, AZURE_* env vars) unless these are set
    tenant_id: 00000000-0000-0000-0000-000000000000
    client_id: 00000000-0000-0000-0000-000000000000
    client_secret_file: /run/secrets/azure      # *_file > *_env > literal, as for Vault credentials
    severity: high
    engines:
      - name: payments-kv                       # the single engine is the vault itself
        secrets:
          - path: stripe-api-key
            severity: critical
```

**Mapping to the interface** (Python SDK `azure-keyvault-secrets` + `azure-identity`):

| `BaseIntegration` | Key Vault |
|---|---|
| `discover_engines()` | one engine: `{"path": <vault name>, "type": "azure-key-vault"}` (Key Vault has no mounts or folders) |
| `list_secrets("")` | `list_properties_of_secrets()` names, enabled and disabled; never folders |
| `get_secret_metadata(name)` | `list_properties_of_secret_versions(name)`, **not** `get_secret` (it returns the value). Versions are numbered 1…n by `created_on`; `current_version` = the newest enabled one; `custom_metadata` = tags; `deletion_time` set for disabled versions |
| `write_secret_metadata` | read tags, merge `chronowarden_*`, `update_secret_properties(name, tags=…)` on the current version. Same read-merge-write race as Vault (no ETag on tags) |
| `check_health()` | a one-item list call |
| `last_error_kind` | `ClientAuthenticationError` / 401 / 403 → `auth`; `ServiceRequestError` / timeouts → `offline`; other `HttpResponseError` → `vault` |

**Permissions** (README, beside "Vault Permissions"): a custom RBAC role with the data actions
`Microsoft.KeyVault/vaults/secrets/readMetadata/action` (list and read properties, no value) and the action that
updates secret attributes and tags. Never "Key Vault Secrets User", which can read values. Vaults on the legacy
access-policy model can only grant tag updates through `set`, which also writes values; see open questions.

**Limits**: Key Vault allows 15 tags per secret. When a write would exceed it, the write fails, sync logs which
secret and continues; the UI shows the value from config (it is the source of truth anyway).

## Tasks

| # | Task | Load | Done when | Status | Commit |
|---|---|---|---|---|---|
| 1 | Verify the update data action name and the tag limit against Microsoft's docs; record them here | — | Both facts cited with links in Notes | todo | |
| 2 | `ProviderConfigBase`; `AzureKeyVaultConfig`; `vaults` a union discriminated by `type` | core, `chronowarden/config.py`, `tests/test_config.py` | Existing configs load unchanged; each validation error tested | todo | |
| 3 | `AzureKeyVaultIntegration` + builder registered; `azure` optional extra | integrations, `base.py`, `pyproject.toml` | `tests/test_azure_key_vault.py` with a mocked `SecretClient`: listing, version numbering, tag merge, every error kind, no call that returns a value | todo | |
| 4 | Sync end to end against a mocked client | `chronowarden/api/sync.py`, `tests/test_sync_api.py` | A synced Azure secret has status, owners and a detected rotation | todo | |
| 5 | Integration test against Lowkey Vault in testcontainers | `tests/integration` | CI job green | todo | |
| 6 | Images, README permissions, `docs/guides/azure-key-vault.md` (AI draft), `config.example.yaml`, architecture model, integrations AGENTS, CHANGELOG | deploy, architecture | `check_agents_docs.py` and LikeC4 pass; both images build; the guide names `expires_on` as not used yet | todo | |

## Validation

`uv run black --check . && uv run ruff check . && uv run pytest`, `cd frontend && npm run check`,
`python3 scripts/check_agents_docs.py`, `docker build -t chronowarden:test .` (and `--target headless`).

## Notes

- **Native expiry, to revisit in a future audit:** Key Vault secrets carry their own `expires_on` (and
  `not_before`). This provider ignores them for now: the TTL comes only from config (ADR-006). The user guide says
  so, and a future audit should decide whether to show them or let them inform the TTL (the latter needs an ADR).

## Open questions

Asked and answered 2026-10-29:

1. Scope of one entry: **one key vault**; no ARM discovery.
2. Credentials: **`DefaultAzureCredential`**, with an optional explicit service principal.
3. Key Vault's own `expires_on`: **ignored for now**, documented, and revisited in a future audit (Notes).
4. Access-policy vaults: **RBAC vaults only**; the docs say an access-policy vault would need `set`, which also
   writes values.
5. Integration test: **mocked `SecretClient` + Lowkey Vault** in testcontainers.

Still open (proposed default applies unless the maintainer says otherwise):

6. Packaging: the Azure SDK as an optional `azure` extra, included in both images.
