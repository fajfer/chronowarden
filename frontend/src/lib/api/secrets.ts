// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import { apiGet, apiPost, apiPut, apiDelete } from './client';
import type { Secret } from '$lib/types';

/**
 * Fetch all secrets.
 */
export function fetchSecrets(): Promise<Secret[]> {
  return apiGet<Secret[]>('/secrets');
}

/**
 * Fetch a single secret by ID.
 */
export function fetchSecret(id: number): Promise<Secret> {
  return apiGet<Secret>(`/secrets/${id}`);
}

/**
 * Create a new secret.
 */
export function createSecret(data: Partial<Secret>): Promise<Secret> {
  return apiPost<Secret>('/secrets', data);
}

/**
 * Update a secret by ID.
 */
export function updateSecret(id: number, data: Partial<Secret>): Promise<Secret> {
  return apiPut<Secret>(`/secrets/${id}`, data);
}

/**
 * Delete a secret by ID.
 */
export function deleteSecret(id: number): Promise<void> {
  return apiDelete<void>(`/secrets/${id}`);
}
