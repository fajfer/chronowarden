// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import { apiGet, apiPost, apiPut, apiDelete } from './client';
import type { Owner, OwnerCreate, OwnerUpdate, NotificationRoute, NotificationRouteCreate } from '$lib/types';

/** GET /api/v1/owners — list all owners. */
export function fetchOwners(): Promise<Owner[]> {
  return apiGet<Owner[]>('/owners/');
}

/** GET /api/v1/owners/:id — get a single owner. */
export function fetchOwner(id: string): Promise<Owner> {
  return apiGet<Owner>(`/owners/${id}`);
}

/** POST /api/v1/owners — create an owner. */
export function createOwner(data: OwnerCreate): Promise<Owner> {
  return apiPost<Owner>('/owners/', data);
}

/** PUT /api/v1/owners/:id — update an owner. */
export function updateOwner(id: string, data: OwnerUpdate): Promise<Owner> {
  return apiPut<Owner>(`/owners/${id}`, data);
}

/** DELETE /api/v1/owners/:id — delete an owner. */
export function deleteOwner(id: string): Promise<void> {
  return apiDelete(`/owners/${id}`);
}

/** POST /api/v1/owners/:id/routes — add a notification route. */
export function addNotificationRoute(ownerId: string, data: NotificationRouteCreate): Promise<NotificationRoute> {
  return apiPost<NotificationRoute>(`/owners/${ownerId}/routes`, data);
}

/** DELETE /api/v1/owners/:ownerId/routes/:routeId — remove a notification route. */
export function deleteNotificationRoute(ownerId: string, routeId: string): Promise<void> {
  return apiDelete(`/owners/${ownerId}/routes/${routeId}`);
}

/** POST /api/v1/owners/:ownerId/test-route/:routeId — test a route. */
export function testNotificationRoute(
  ownerId: string,
  routeId: string,
): Promise<{ success: boolean; message: string }> {
  return apiPost<{ success: boolean; message: string }>(`/owners/${ownerId}/test-route/${routeId}`);
}
