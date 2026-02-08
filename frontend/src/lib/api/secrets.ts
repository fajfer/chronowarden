// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import { apiGet, apiPatch } from './client';
import type { Secret, SecretMetadataUpdate } from '$lib/types';

/** GET /api/v1/secrets/ — list cached secret metadata with optional filters. */
export function fetchSecrets(
  vaultName?: string,
  engineId?: string,
  severity?: string,
  enabled?: boolean,
): Promise<Secret[]> {
  const params = new URLSearchParams();
  if (vaultName) params.set('vault_name', vaultName);
  if (engineId) params.set('engine_id', engineId);
  if (severity) params.set('severity', severity);
  if (enabled !== undefined) params.set('enabled', String(enabled));
  const qs = params.toString();
  return apiGet<Secret[]>(`/secrets/${qs ? `?${qs}` : ''}`);
}

/** GET /api/v1/secrets/:id — fetch a single cached secret. */
export function fetchSecret(id: number): Promise<Secret> {
  return apiGet<Secret>(`/secrets/${id}`);
}

/** PATCH /api/v1/secrets/:id — update Chronowarden metadata fields. */
export function updateSecretMetadata(id: number, data: SecretMetadataUpdate): Promise<Secret> {
  return apiPatch<Secret>(`/secrets/${id}`, data);
}
