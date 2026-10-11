// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import { apiGet, apiPost, apiPut, apiDelete } from './client';
import type { System, SystemCreate, SystemUpdate } from '#lib/types/index.js';

/** GET /api/v1/systems — list all systems. */
export function fetchSystems(): Promise<System[]> {
  return apiGet<System[]>('/systems/');
}

/** POST /api/v1/systems — create a system. */
export function createSystem(data: SystemCreate): Promise<System> {
  return apiPost<System>('/systems/', data);
}

/** PUT /api/v1/systems/:id — update a system's fields. */
export function updateSystem(id: string, data: SystemUpdate): Promise<System> {
  return apiPut<System>(`/systems/${id}`, data);
}

/** PUT /api/v1/systems/:id/owners — replace a system's owners. */
export function setSystemOwners(id: string, ownerIds: string[]): Promise<System> {
  return apiPut<System>(`/systems/${id}/owners`, { owner_ids: ownerIds });
}

/** DELETE /api/v1/systems/:id — delete a system (409 while secrets are assigned). */
export function deleteSystem(id: string): Promise<void> {
  return apiDelete(`/systems/${id}`);
}
