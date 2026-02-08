// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import { apiGet, apiPost, apiPut, apiDelete } from './client';
import type { Secret, SecretCreate, SecretUpdate, EngineType } from '$lib/types';

/** GET /api/v1/secrets/ — list all secrets with optional filters. */
export function fetchSecrets(engineType?: EngineType, isPublic?: boolean): Promise<Secret[]> {
  const params = new URLSearchParams();
  if (engineType) params.set('engine_type', engineType);
  if (isPublic !== undefined) params.set('is_public', String(isPublic));
  const qs = params.toString();
  return apiGet<Secret[]>(`/secrets/${qs ? `?${qs}` : ''}`);
}

/** GET /api/v1/secrets/public/ — list public secrets only. */
export function fetchPublicSecrets(): Promise<Secret[]> {
  return apiGet<Secret[]>('/secrets/public/');
}

/** GET /api/v1/secrets/:id — fetch a single secret. */
export function fetchSecret(id: number): Promise<Secret> {
  return apiGet<Secret>(`/secrets/${id}`);
}

/** POST /api/v1/secrets/ — create a secret. */
export function createSecret(data: SecretCreate): Promise<Secret> {
  return apiPost<Secret>('/secrets/', data);
}

/** PUT /api/v1/secrets/:id — update a secret. */
export function updateSecret(id: number, data: SecretUpdate): Promise<Secret> {
  return apiPut<Secret>(`/secrets/${id}`, data);
}

/** DELETE /api/v1/secrets/:id — delete a secret. */
export function deleteSecret(id: number): Promise<void> {
  return apiDelete(`/secrets/${id}`);
}
