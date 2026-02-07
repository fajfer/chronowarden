// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import { apiGet, apiPost, apiPut, apiDelete } from './client';
import type { Owner } from '$lib/types';

/**
 * Fetch all owners.
 */
export function fetchOwners(): Promise<Owner[]> {
  return apiGet<Owner[]>('/owners');
}

/**
 * Fetch a single owner by ID.
 */
export function fetchOwner(id: string): Promise<Owner> {
  return apiGet<Owner>(`/owners/${id}`);
}

/**
 * Create a new owner.
 */
export function createOwner(data: Partial<Owner>): Promise<Owner> {
  return apiPost<Owner>('/owners', data);
}

/**
 * Update an owner by ID.
 */
export function updateOwner(id: string, data: Partial<Owner>): Promise<Owner> {
  return apiPut<Owner>(`/owners/${id}`, data);
}

/**
 * Delete an owner by ID.
 */
export function deleteOwner(id: string): Promise<void> {
  return apiDelete<void>(`/owners/${id}`);
}
