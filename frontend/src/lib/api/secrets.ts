// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import { apiDelete, apiGet, apiPost, apiPut } from './client';
import type { AuditEvent, PurgeResult, Secret } from '#lib/types/index.js';

/** GET /api/v1/secrets/ — list cached secret metadata with optional filters. */
export function fetchSecrets(
  vaultName?: string,
  engineId?: string,
  severity?: string,
  includeRemoved = false,
): Promise<Secret[]> {
  const params = new URLSearchParams();
  if (vaultName) params.set('vault_name', vaultName);
  if (engineId) params.set('engine_id', engineId);
  if (severity) params.set('severity', severity);
  if (includeRemoved) params.set('include_removed', 'true');
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

/** DELETE /api/v1/secrets/:id — purge a secret that is no longer in its backend (409 otherwise). */
export function purgeSecret(id: number): Promise<void> {
  return apiDelete(`/secrets/${id}`);
}

/** DELETE /api/v1/secrets/removed — purge every removed secret, optionally of one vault or engine. */
export function purgeRemovedSecrets(vaultName?: string, engineId?: string): Promise<PurgeResult> {
  const params = new URLSearchParams();
  if (vaultName) params.set('vault_name', vaultName);
  if (engineId) params.set('engine_id', engineId);
  const qs = params.toString();
  return apiDelete<PurgeResult>(`/secrets/removed${qs ? `?${qs}` : ''}`);
}

/** GET /api/v1/secrets/:id/history — the secret's audit events, newest first. */
export function fetchSecretHistory(id: number): Promise<AuditEvent[]> {
  return apiGet<AuditEvent[]>(`/secrets/${id}/history`);
}

/** POST /api/v1/secrets/:id/confirmations — confirm the newest version was applied at `appliedAt` (ISO 8601). */
export function confirmRotation(id: number, appliedAt: string): Promise<Secret> {
  return apiPost<Secret>(`/secrets/${id}/confirmations`, { applied_at: appliedAt });
}
