## Chronowarden
<!--
SPDX-FileCopyrightText: 2025 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
Serwis do zarządzania sekretami

```python
class Secret(BaseModel):
"""this is a base class for secrets from all engines"""
  id: int
  name: str
  description: str
  # Is the secret visible without logging?
  is_public: Bool
  # When the secret itself was created
  created_at: timedate
  # When to alert the user (eg. 30 days before)
  expiry_time_alert: int
  # How often to remind the user
  # TODO: Prometheus-style metrics and turn this off
  expiry_time_interval: int
  # Who is responsible for management(renewal) of the secret
  owner: Entity
  # Who to forward the information to
  routing: [Router]
  # What backend does the Secret use
  backend: SecretEngine

class AzureKeyvaultSecret(Secret):
    """example, didn't check the docs"""
    subscription_id: int
    resource_group: str

class Entity(BaseModel):
    """this is a base class for:
    - users
    - technical users
    - groups
    """

class SecretEngine(BaseModel):
    """this is a base class for secrets backend:
    - manual - purely based on user input
    - Azure KeyVault - connects to an Azure key vault 
    - Hashicorp Vault
    - X.509
    """

class SecretTemplate(Secret):
    """predefiniowane defaulty dla secretów"""

class Router(BaseModel):
    """TODO"""
```

# Uprawnienia
- Część funkcjonalności jest dostępna bez logowania
  - Wszystkie secrety z atrybutem `is_public: true`
  - Przydatne np. dla certyfikatów x509 
- Rodzaje uprawnień na użytkowniku
  - read-only
  - read-write - edycja pól
  - admin - zarządzanie uprawnieniami dla innych
- Obiekt utworzony przez ownera jest widoczny tylko dla ownera, chyba, że zostaną zmodyfikowane uprawnienia
  - Router - np. poświadczenia mailowe, konfiguracja webhooka
  - SecretEngine - konkretne poświadczenia na danego użytkownika
  - Secret

# Mechanizm działania
### Secret Engine - manual
- Użytkownik tworzy secret
- Chronowarden zostaje striggerowany, jeżeli zbliża się `Secret.expiry_time_alert`
- Chronowarden do wszystkich obiektów `Secret.routing` wysyła informację o wygasającym secrecie
- Chronowarden odczekuje `Secret.expiry_time_interval` i ponawia poprzedni krok, jeżeli po wyliczeniu `Secret.expiry_time_alert` warunek jest spełniony

# Backend
### Installation

```bash
uv sync
```

### Running the server

```bash
uv run uvicorn chronowarden:app --reload
```

### Unit tests

```bash
uv run pytest
```

# Integration tests

The idea is to test on both of these platforms to maintain compatibility, even though [OpenBao intends to remain API compatible with HashiCorp Vault](https://openbao.org/api-docs/libraries/).

### https://openbao.org/docs/install/#container-registries
`docker run -p 127.0.0.1:8200:8200 --name openbao-dev --detach quay.io/openbao/openbao`

### https://hub.docker.com/r/hashicorp/vault
`docker run -p 127.0.0.1:8201:8201 --cap-add=IPC_LOCK -e 'VAULT_DEV_LISTEN_ADDRESS=0.0.0.0:8201' -d --name=dev-vault hashicorp/vault`
