// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import { apiGet } from './client';
import type { Secret } from '$lib/types';

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
