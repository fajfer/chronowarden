# SPDX-FileCopyrightText: 2025 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

.PHONY: help build build-dev build-test test test-unit test-integration test-docker \
        up up-dev up-test down clean sbom lint format

# Default target
help:
	@echo "Chronowarden - Secret Management Service"
	@echo ""
	@echo "Development Commands:"
	@echo "  make up              Start development environment"
	@echo "  make up-test         Start test environment with Vault"
	@echo "  make down            Stop all services"
	@echo "  make test            Run all tests locally"
	@echo "  make test-docker     Run tests in Docker containers"
	@echo "  make lint            Run linters"
	@echo "  make format          Format code"
	@echo ""
	@echo "Build Commands:"
	@echo "  make build           Build production images"
	@echo "  make build-dev       Build development images"
	@echo "  make build-test      Build test images"
	@echo ""
	@echo "Compliance Commands:"
	@echo "  make sbom            Generate Software Bill of Materials"
	@echo "  make clean           Clean build artifacts"

# ---------------------------------------------------------------------------
# Development
# ---------------------------------------------------------------------------
up:
	docker compose up -d

up-dev:
	docker compose up

up-test:
	docker compose -f docker-compose.test.yml up -d vault vault-init
	@echo "Vault available at http://localhost:8200 (token: test-root-token)"

down:
	docker compose down
	docker compose -f docker-compose.test.yml down

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------
test:
	cd backend && pytest tests/ -v --tb=short

test-unit:
	cd backend && pytest tests/ \
		--ignore=tests/test_vault_integration.py \
		-v --tb=short

test-integration:
	@echo "Starting Vault for integration tests..."
	docker compose -f docker-compose.test.yml up -d vault vault-init
	@sleep 5
	cd backend && \
		VAULT_ADDR=http://localhost:8200 \
		VAULT_TOKEN=test-root-token \
		VAULT_MOUNT_PATH=chronowarden \
		pytest tests/test_vault_integration.py -v --tb=short
	docker compose -f docker-compose.test.yml down

test-docker:
	docker compose -f docker-compose.test.yml up \
		--build \
		--abort-on-container-exit \
		--exit-code-from test-runner

# ---------------------------------------------------------------------------
# Building
# ---------------------------------------------------------------------------
build:
	docker build -t chronowarden-backend:latest ./backend
	docker build -t chronowarden-frontend:latest ./frontend

build-dev:
	docker build --target development -t chronowarden-backend:dev ./backend
	docker build --target development -t chronowarden-frontend:dev ./frontend

build-test:
	docker build --target test -t chronowarden-backend:test ./backend

# ---------------------------------------------------------------------------
# Linting & Formatting
# ---------------------------------------------------------------------------
lint:
	cd backend && ruff check .
	cd backend && black --check .

format:
	cd backend && ruff check --fix .
	cd backend && black .

# ---------------------------------------------------------------------------
# Compliance (DORA/KNF)
# ---------------------------------------------------------------------------
sbom:
	@mkdir -p sbom
	@echo "Generating SBOM for backend source..."
	docker run --rm -v $(PWD):/src anchore/syft:latest \
		packages dir:/src/backend \
		-o spdx-json=/src/sbom/chronowarden-backend-source.spdx.json
	@echo "SBOM generated: sbom/chronowarden-backend-source.spdx.json"
	@echo ""
	@echo "To generate SBOM for Docker images, first build them with 'make build'"
	@echo "Then run:"
	@echo "  docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \\"
	@echo "    anchore/syft:latest packages chronowarden-backend:latest \\"
	@echo "    -o spdx-json > sbom/chronowarden-backend-image.spdx.json"

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
clean:
	docker compose down -v --rmi local
	docker compose -f docker-compose.test.yml down -v --rmi local
	rm -rf test-results/
	rm -rf backend/.pytest_cache/
	rm -rf backend/htmlcov/
	rm -rf backend/.coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
