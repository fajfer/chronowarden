# Chronowarden Backend

<!--
SPDX-FileCopyrightText: 2025 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->

FastAPI-based backend for Chronowarden secret management service.

## Features

- REST API with OpenAPI specification
- HashiCorp Vault integration
- Prometheus-compatible metrics
- Secret expiration tracking

## Development

### Prerequisites

- Python 3.11+
- uv package manager

### Installation

```bash
uv sync
```

### Running the server

```bash
uv run uvicorn chronowarden:app --reload
```

### Running tests

```bash
uv run pytest
```

## API Documentation

When the server is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

## Endpoints

- `GET /health` - Health check
- `GET /ready` - Readiness check
- `GET /metrics` - Prometheus metrics
- `GET /api/v1/secrets/` - List secrets
- `POST /api/v1/secrets/` - Create secret
- `GET /api/v1/secrets/{id}` - Get secret
- `PUT /api/v1/secrets/{id}` - Update secret
- `DELETE /api/v1/secrets/{id}` - Delete secret
- `POST /api/v1/vault/connect` - Connect to Vault
- `POST /api/v1/vault/disconnect` - Disconnect from Vault
- `GET /api/v1/vault/health` - Vault health status
