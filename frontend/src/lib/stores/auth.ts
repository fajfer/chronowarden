// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

/**
 * Auth store: the caller from GET /auth/me (ADR-015, ADR-026).
 *
 * The helpers only decide which controls to show; the server checks every request again.
 */

import { writable, derived, get } from 'svelte/store';
import { fetchMe, postLogout } from '#lib/api/auth.js';
import { ApiError, onUnauthorized } from '#lib/api/client.js';
import type { Me, Secret } from '#lib/types/index.js';

/** The caller, or null when not logged in. */
export const currentUser = writable<Me | null>(null);
/** False until the first /auth/me answer, so pages don't flash the login screen. */
export const authChecked = writable(false);
/** Why the caller can't get in, when logged in at the IdP or proxy but refused here (403 without a role). */
export const authError = writable<string | null>(null);

export const isAuthenticated = derived(currentUser, ($user) => $user !== null);
export const isAdmin = derived(currentUser, ($user) => $user?.role === 'admin');
/** Owners and admins may trigger a sync (ADR-026). */
export const canSync = derived(currentUser, ($user) => $user?.role === 'admin' || $user?.role === 'owner');

/** The login page with a way back to where the user was. */
export function loginPath(): string {
  if (typeof window === 'undefined') return '/login';
  const here = window.location.pathname + window.location.search;
  return here.startsWith('/login') ? '/login' : `/login?${new URLSearchParams({ next: here })}`;
}

/** Load the caller; a 401 leaves the store empty, a 403 records why. */
export async function initAuth(): Promise<void> {
  if (typeof window === 'undefined') return;
  onUnauthorized(() => {
    currentUser.set(null);
    if (!window.location.pathname.startsWith('/login')) window.location.assign(loginPath());
  });
  try {
    currentUser.set(await fetchMe());
    authError.set(null);
  } catch (e) {
    currentUser.set(null);
    authError.set(e instanceof ApiError && e.status === 403 ? e.message : null);
  } finally {
    authChecked.set(true);
  }
}

/** Whether the caller acts for one of these owners (admins act for everyone). */
export function actsFor(user: Me | null, ownerIds: string[]): boolean {
  if (user === null) return false;
  if (user.role === 'admin') return true;
  return user.role === 'owner' && ownerIds.some((id) => user.owner_ids.includes(id));
}

/** Whether the caller may change a secret's assignments, confirmation and privileged flag. */
export function canEditSecret(user: Me | null, secret: Secret): boolean {
  return actsFor(user, secret.effective_owners.map((owner) => owner.id));
}

/** Log out here and, behind a proxy, at the proxy. */
export async function logout(): Promise<void> {
  const user = get(currentUser);
  let logoutUrl: string | null = null;
  try {
    logoutUrl = (await postLogout()).logout_url;
  } catch {
    // the session is gone either way once the cookie is cleared
  }
  currentUser.set(null);
  window.location.assign(logoutUrl ?? (user?.auth_mode === 'proxy' ? '/' : '/login'));
}
