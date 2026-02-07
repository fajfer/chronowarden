// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import { writable, derived } from 'svelte/store';
import { MOCK_USERS, canEdit, canSync, canBulkEdit, canManageOwners } from '$lib/utils/permissions';
import type { Role, MockUser } from '$lib/utils/permissions';

const STORAGE_KEY = 'chronowarden_auth';

export const currentUser = writable<MockUser | null>(null);
export const currentRole = writable<Role>('read-only');
export const isAuthenticated = derived(currentUser, ($user) => $user !== null);

export const canEditSecrets = derived(currentRole, ($role) => canEdit($role));
export const canTriggerSync = derived(currentRole, ($role) => canSync($role));
export const canBulkEditSecrets = derived(currentRole, ($role) => canBulkEdit($role));
export const canManageOwnerProfiles = derived(currentRole, ($role) => canManageOwners($role));

/**
 * Initialize auth state from localStorage.
 */
export function initAuth(): void {
  if (typeof window === 'undefined') return;
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const data = JSON.parse(stored) as { username: string };
      const user = MOCK_USERS.find((u) => u.username === data.username);
      if (user) {
        currentUser.set(user);
        currentRole.set(user.role);
      }
    }
  } catch {
    // Ignore parse errors
  }
}

/**
 * Log in with username and password.
 */
export function login(username: string, password: string): boolean {
  const user = MOCK_USERS.find((u) => u.username === username && u.password === password);
  if (!user) return false;
  currentUser.set(user);
  currentRole.set(user.role);
  if (typeof window !== 'undefined') {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ username: user.username }));
  }
  return true;
}

/**
 * Log out the current user.
 */
export function logout(): void {
  currentUser.set(null);
  currentRole.set('read-only');
  if (typeof window !== 'undefined') {
    localStorage.removeItem(STORAGE_KEY);
  }
}

/**
 * Switch to a different mock user by username.
 */
export function switchUser(username: string): void {
  const user = MOCK_USERS.find((u) => u.username === username);
  if (user) {
    currentUser.set(user);
    currentRole.set(user.role);
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ username: user.username }));
    }
  }
}
