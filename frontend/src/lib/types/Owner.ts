// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

/**
 * Notification route matching the backend NotificationRoute model.
 */
export interface NotificationRoute {
  id: string;
  owner_id: string;
  type: 'email' | 'webhook';
  address: string;
  message_template: string;
  created_at: string | null;
}

/**
 * Payload for creating a notification route.
 */
export interface NotificationRouteCreate {
  type: 'email' | 'webhook';
  address: string;
  message_template?: string;
}

/**
 * Owner model matching the backend Owner pydantic model.
 */
export interface Owner {
  id: string;
  name: string;
  email: string;
  notification_routes: NotificationRoute[];
  created_at: string | null;
}

/**
 * Payload for creating an owner.
 */
export interface OwnerCreate {
  name: string;
  email: string;
}

/**
 * Payload for updating an owner.
 */
export interface OwnerUpdate {
  name?: string;
  email?: string;
}
