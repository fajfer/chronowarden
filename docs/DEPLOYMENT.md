<!--
SPDX-FileCopyrightText: 2025 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->

# Chronowarden Container & Kubernetes Deployment Guide

This guide covers building, running, and deploying Chronowarden using Docker and Kubernetes.

## Table of Contents

- [Overview](#overview)
- [Docker Images](#docker-images)
  - [Backend Image](#backend-image)
  - [Frontend Image](#frontend-image)
- [Local Development with Docker Compose](#local-development-with-docker-compose)
- [Kubernetes Deployment](#kubernetes-deployment)
  - [Prerequisites](#prerequisites)
  - [Directory Structure](#directory-structure)
  - [Deploying to Development](#deploying-to-development)
  - [Deploying to Production](#deploying-to-production)
- [Security Considerations](#security-considerations)
- [Monitoring & Observability](#monitoring--observability)
- [Troubleshooting](#troubleshooting)

## Overview

Chronowarden provides production-ready containerization with the following features:

- **Multi-stage Docker builds** for optimized image sizes
- **Distroless production images** for minimal attack surface
- **Development images** with debugging tools
- **Kubernetes manifests** with Kustomize overlays
- **Security best practices** including non-root users, read-only filesystems, and network policies

## Docker Images

### Backend Image

The backend Dockerfile (`backend/Dockerfile`) provides two build targets:

#### Production Image (Default)

Uses Google's distroless Python image for minimal attack surface:

```bash
# Build production image
docker build -t chronowarden-backend:latest ./backend

# Run production container
docker run -p 8000:8000 chronowarden-backend:latest
```

**Features:**
- Based on `gcr.io/distroless/python3-debian12`
- Runs as non-root user (`nonroot`)
- No shell or package manager
- Minimal CVE exposure

#### Development Image

Full Python image with debugging tools:

```bash
# Build development image
docker build --target development -t chronowarden-backend:dev ./backend

# Run with auto-reload
docker run -p 8000:8000 -v $(pwd)/backend/src:/app/chronowarden chronowarden-backend:dev
```

**Features:**
- Based on `python:3.11-slim`
- Includes: curl, vim, procps, net-tools, iputils-ping
- Development dependencies installed (pytest, ruff, black)
- Auto-reload enabled for development
- Health check with curl

### Frontend Image

The frontend Dockerfile (`frontend/Dockerfile`) provides two build targets:

#### Production Image (Default)

Uses nginx:alpine to serve static files:

```bash
# Build production image
docker build -t chronowarden-frontend:latest ./frontend

# Run production container
docker run -p 8080:8080 chronowarden-frontend:latest
```

**Features:**
- Based on `nginx:alpine`
- Optimized static file serving
- Security headers configured
- Gzip compression enabled
- SPA routing support

#### Development Image

Node.js image with hot-reload:

```bash
# Build development image
docker build --target development -t chronowarden-frontend:dev ./frontend

# Run with hot-reload
docker run -p 5173:5173 -v $(pwd)/frontend/src:/app/src chronowarden-frontend:dev
```

**Features:**
- Based on `node:22-slim`
- Vite dev server with HMR
- Volume mounting for live development

## Local Development with Docker Compose

### Quick Start

```bash
# Start all services in development mode
docker compose up

# Start in detached mode
docker compose up -d

# View logs
docker compose logs -f

# Stop services
docker compose down
```

### Production Mode

```bash
# Build and start with production configuration
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# View logs
docker compose logs -f

# Stop and remove volumes
docker compose down -v
```

### Service URLs

| Service  | Development          | Production          |
|----------|---------------------|---------------------|
| Backend  | http://localhost:8000 | http://localhost:8000 |
| Frontend | http://localhost:5173 | http://localhost:8080 |

### API Endpoints

| Endpoint    | Description                    |
|-------------|--------------------------------|
| `/`         | API information                |
| `/health`   | Health check                   |
| `/ready`    | Readiness check                |
| `/metrics`  | Prometheus metrics             |
| `/docs`     | OpenAPI documentation          |

## Kubernetes Deployment

### Prerequisites

- Kubernetes cluster (v1.24+)
- kubectl configured
- kustomize (built into kubectl v1.14+)
- Container registry access

### Directory Structure

```
k8s/
├── base/                           # Base manifests
│   ├── kustomization.yaml
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── backend-deployment.yaml
│   ├── backend-service.yaml
│   ├── frontend-deployment.yaml
│   ├── frontend-service.yaml
│   └── ingress.yaml
└── overlays/
    ├── development/               # Development environment
    │   └── kustomization.yaml
    └── production/                # Production environment
        ├── kustomization.yaml
        ├── hpa.yaml               # Horizontal Pod Autoscaler
        ├── pdb.yaml               # Pod Disruption Budget
        └── networkpolicy.yaml     # Network Policies
```

### Deploying to Development

```bash
# Preview the manifests
kubectl kustomize k8s/overlays/development

# Apply to cluster
kubectl apply -k k8s/overlays/development

# Verify deployment
kubectl get all -n chronowarden-dev

# Port-forward for local access
kubectl port-forward -n chronowarden-dev svc/chronowarden-backend-dev 8000:8000
kubectl port-forward -n chronowarden-dev svc/chronowarden-frontend-dev 8080:8080
```

### Deploying to Production

#### 1. Build and Push Images

```bash
# Set your registry
REGISTRY=ghcr.io/fajfer

# Build and tag images
docker build -t $REGISTRY/chronowarden-backend:0.1.0 ./backend
docker build -t $REGISTRY/chronowarden-frontend:0.1.0 ./frontend

# Push to registry
docker push $REGISTRY/chronowarden-backend:0.1.0
docker push $REGISTRY/chronowarden-frontend:0.1.0
```

#### 2. Configure TLS

Create a TLS secret for HTTPS:

```bash
# Using cert-manager (recommended)
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: chronowarden-tls
  namespace: chronowarden-prod
spec:
  secretName: chronowarden-tls
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
    - chronowarden.example.com
EOF

# Or manually create from existing certificates
kubectl create secret tls chronowarden-tls \
  --cert=path/to/cert.pem \
  --key=path/to/key.pem \
  -n chronowarden-prod
```

#### 3. Deploy

```bash
# Preview the manifests
kubectl kustomize k8s/overlays/production

# Apply to cluster
kubectl apply -k k8s/overlays/production

# Verify deployment
kubectl get all -n chronowarden-prod

# Check HPA status
kubectl get hpa -n chronowarden-prod

# Check PDB status
kubectl get pdb -n chronowarden-prod
```

### Customizing Deployments

Edit the kustomization files to customize:

```yaml
# k8s/overlays/production/kustomization.yaml
images:
  - name: chronowarden-backend
    newName: your-registry.com/chronowarden-backend
    newTag: "1.0.0"
```

### Resource Limits

| Environment | Component | CPU Request | CPU Limit | Memory Request | Memory Limit |
|-------------|-----------|-------------|-----------|----------------|--------------|
| Development | Backend   | 50m         | 200m      | 64Mi           | 256Mi        |
| Development | Frontend  | 25m         | 100m      | 16Mi           | 64Mi         |
| Production  | Backend   | 250m        | 1000m     | 256Mi          | 1Gi          |
| Production  | Frontend  | 50m         | 200m      | 32Mi           | 128Mi        |

## Security Considerations

### Container Security

1. **Non-root execution**: All containers run as non-root users
2. **Read-only filesystem**: Production backend uses read-only root filesystem
3. **Distroless images**: Minimal attack surface with no shell
4. **Security contexts**: Proper seccomp profiles and capability drops

### Kubernetes Security

1. **Network Policies**: Restrict pod-to-pod communication
2. **Pod Security**: Non-root users, capability drops, seccomp profiles
3. **RBAC**: Apply least-privilege access controls
4. **Secrets Management**: Use external secret stores for sensitive data

### Recommended Additional Security

```bash
# Install and configure Pod Security Standards
kubectl label namespace chronowarden-prod \
  pod-security.kubernetes.io/enforce=restricted \
  pod-security.kubernetes.io/audit=restricted \
  pod-security.kubernetes.io/warn=restricted
```

## Monitoring & Observability

### Prometheus Metrics

The backend exposes Prometheus metrics at `/metrics`:

```yaml
# Example ServiceMonitor for Prometheus Operator
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: chronowarden-backend
  namespace: chronowarden-prod
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: chronowarden-backend
  endpoints:
    - port: http
      path: /metrics
      interval: 30s
```

### Available Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `chronowarden_api_requests_total` | Counter | Total API requests |
| `chronowarden_api_request_duration_seconds` | Histogram | Request latency |

### Health Checks

| Probe | Endpoint | Description |
|-------|----------|-------------|
| Liveness | `/health` | Is the application alive? |
| Readiness | `/ready` | Is the application ready to serve traffic? |
| Startup | `/health` | Has the application started? |

## Troubleshooting

### Common Issues

#### Container Won't Start

```bash
# Check pod events
kubectl describe pod <pod-name> -n <namespace>

# Check container logs
kubectl logs <pod-name> -n <namespace>
```

#### Health Check Failures

```bash
# Verify endpoint from within cluster
kubectl run debug --rm -it --image=curlimages/curl -- curl http://chronowarden-backend:8000/health
```

#### Permission Denied Errors

The distroless image runs as user 65532 (nonroot). Ensure any mounted volumes have correct permissions.

#### Image Pull Errors

```bash
# Create image pull secret
kubectl create secret docker-registry regcred \
  --docker-server=ghcr.io \
  --docker-username=<username> \
  --docker-password=<token> \
  -n <namespace>

# Add to deployment
spec:
  template:
    spec:
      imagePullSecrets:
        - name: regcred
```

### Debug Commands

```bash
# Get all resources in namespace
kubectl get all -n chronowarden

# Describe deployment
kubectl describe deployment chronowarden-backend -n chronowarden

# View logs with follow
kubectl logs -f deployment/chronowarden-backend -n chronowarden

# Execute shell in development container
kubectl exec -it deployment/chronowarden-backend -n chronowarden-dev -- /bin/bash

# Port forward for local testing
kubectl port-forward svc/chronowarden-backend 8000:8000 -n chronowarden
```

### Log Levels

Set log level via ConfigMap:

```yaml
data:
  LOG_LEVEL: "DEBUG"  # DEBUG, INFO, WARNING, ERROR
```

Apply changes:

```bash
kubectl rollout restart deployment/chronowarden-backend -n chronowarden
```
