# Chronowarden

**Chronowarden** is a secret lifecycle observability service that syncs with your Vault instances. It tracks secret TTLs and rotation requirements via custom metadata, exposing health metrics via a Svelte UI and REST API.

!!! note "Security First"
    Chronowarden **never reads actual secret values**, only metadata.

## Quick Links
- [Quickstart Guide](getting-started/quickstart.md)
- [Vault Configuration](getting-started/configuration.md)