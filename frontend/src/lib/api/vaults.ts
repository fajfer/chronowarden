// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import { apiGet } from './client';
import type { VaultInstanceHealth, HealthStatus, ApiInfo } from '#lib/types/index.js';

/** GET /api/v1/vault/instances — list configured vault instance names. */
export function fetchVaultInstances(): Promise<{ instances: string[] }> {
  return apiGet<{ instances: string[] }>('/vault/instances');
}

/** GET /api/v1/vault/health — health of all vault instances. */
export function fetchAllVaultHealth(): Promise<VaultInstanceHealth[]> {
  return apiGet<VaultInstanceHealth[]>('/vault/health');
}

/** GET /api/v1/vault/:name/health — health of a single vault. */
export function fetchVaultHealth(name: string): Promise<VaultInstanceHealth> {
  return apiGet<VaultInstanceHealth>(`/vault/${name}/health`);
}

/** GET /api/v1/health — basic health check. */
export function fetchHealthCheck(): Promise<HealthStatus> {
  return apiGet<HealthStatus>('/health');
}

/** GET /api/v1/info — API name, version and docs link. */
export function fetchApiInfo(): Promise<ApiInfo> {
  return apiGet<ApiInfo>('/info');
}
