// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import { apiGet } from './client';
import type { VaultInstanceHealth, HealthStatus, ApiInfo } from '#lib/types/index.js';

/** GET /api/v1/providers/instances — names of the configured backends. */
export function fetchVaultInstances(): Promise<{ instances: string[] }> {
  return apiGet<{ instances: string[] }>('/providers/instances');
}

/** GET /api/v1/providers/health — health of every backend. */
export function fetchAllVaultHealth(): Promise<VaultInstanceHealth[]> {
  return apiGet<VaultInstanceHealth[]>('/providers/health');
}

/** GET /api/v1/providers/:name/health — health of one backend. */
export function fetchVaultHealth(name: string): Promise<VaultInstanceHealth> {
  return apiGet<VaultInstanceHealth>(`/providers/${name}/health`);
}

/** GET /api/v1/health — basic health check. */
export function fetchHealthCheck(): Promise<HealthStatus> {
  return apiGet<HealthStatus>('/health');
}

/** GET /api/v1/info — API name, version and docs link. */
export function fetchApiInfo(): Promise<ApiInfo> {
  return apiGet<ApiInfo>('/info');
}
