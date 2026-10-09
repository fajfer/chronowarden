# Configuration Guide

Chronowarden uses a `config.yaml` file to define connected Vault instances and severity rules.

```yaml
vaults:
  production:
    url: [https://vault.example.com](https://vault.example.com)
    token: your-vault-token
    severity_levels:
      critical:
        rotation_period_days: 30
        alert_threshold_days: 7