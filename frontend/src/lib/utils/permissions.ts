// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

export type Role = 'admin' | 'read-write' | 'read-only';

export interface MockUser {
  username: string;
  name: string;
  role: Role;
  password: string;
}

// Demo-only mock users — not used in production authentication
export const MOCK_USERS: MockUser[] = [
  { username: 'admin', name: 'Alice Admin', role: 'admin', password: 'admin' },
  { username: 'bob', name: 'Bob Engineer', role: 'read-write', password: 'bob' },
  { username: 'carol', name: 'Carol Viewer', role: 'read-only', password: 'carol' },
];

/**
 * Check if a role can edit secrets.
 */
export function canEdit(role: Role): boolean {
  return role === 'admin' || role === 'read-write';
}

/**
 * Check if a role can trigger sync.
 */
export function canSync(role: Role): boolean {
  return role === 'admin' || role === 'read-write';
}

/**
 * Check if a role can bulk edit secrets.
 */
export function canBulkEdit(role: Role): boolean {
  return role === 'admin';
}

/**
 * Check if a role can manage owner profiles.
 */
export function canManageOwners(role: Role): boolean {
  return role === 'admin';
}

/**
 * Check if a role can delete resources.
 */
export function canDelete(role: Role): boolean {
  return role === 'admin';
}
