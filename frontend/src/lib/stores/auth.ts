// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

/**
 * Auth store — no authentication backend exists yet.
 * This is a placeholder that defaults to an authenticated state
 * since the backend has no auth middleware.
 */

import { writable, derived } from 'svelte/store';

const STORAGE_KEY = 'chronowarden_auth';

export interface AppUser {
  name: string;
}

export const currentUser = writable<AppUser | null>(null);
export const isAuthenticated = derived(currentUser, ($user) => $user !== null);

/** Initialize auth state. Auto-logs in since the backend has no auth. */
export function initAuth(): void {
  if (typeof window === 'undefined') return;
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      currentUser.set(JSON.parse(stored) as AppUser);
    } else {
      // No auth in backend — default to logged in
      const user: AppUser = { name: 'Operator' };
      currentUser.set(user);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
    }
  } catch {
    const user: AppUser = { name: 'Operator' };
    currentUser.set(user);
  }
}

/** Set user name. */
export function setUserName(name: string): void {
  const user: AppUser = { name };
  currentUser.set(user);
  if (typeof window !== 'undefined') {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
  }
}

/** Log out. */
export function logout(): void {
  currentUser.set(null);
  if (typeof window !== 'undefined') {
    localStorage.removeItem(STORAGE_KEY);
  }
}
