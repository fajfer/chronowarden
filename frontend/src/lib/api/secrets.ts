// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import { apiGet, apiPut } from './client';
import type { Secret } from '#lib/types/index.js';

/** GET /api/v1/secrets/ — list cached secret metadata with optional filters. */
export function fetchSecrets(
  vaultName?: string,
  engineId?: string,
  severity?: string,
): Promise<Secret[]> {
  const params = new URLSearchParams();
  if (vaultName) params.set('vault_name', vaultName);
  if (engineId) params.set('engine_id', engineId);
  if (severity) params.set('severity', severity);
  const qs = params.toString();
  return apiGet<Secret[]>(`/secrets/${qs ? `?${qs}` : ''}`);
}

/** GET /api/v1/secrets/:id — fetch a single cached secret. */
export function fetchSecret(id: number): Promise<Secret> {
  return apiGet<Secret>(`/secrets/${id}`);
}

/** PUT /api/v1/secrets/:id/system — assign a secret to a system, or unassign it with null. */
export function setSecretSystem(id: number, systemId: string | null): Promise<Secret> {
  return apiPut<Secret>(`/secrets/${id}/system`, { system_id: systemId });
}

/** PUT /api/v1/secrets/:id/owners — replace the owners assigned to a secret. */
export function setSecretOwners(id: number, ownerIds: string[]): Promise<Secret> {
  return apiPut<Secret>(`/secrets/${id}/owners`, { owner_ids: ownerIds });
}
