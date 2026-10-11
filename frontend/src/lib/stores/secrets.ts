// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import { writable, derived } from 'svelte/store';
import * as secretsApi from '#lib/api/secrets.js';
import type { Secret } from '#lib/types/index.js';

/** Secrets that exist in their backend: what tables, stats and the dashboard show. */
export const secrets = writable<Secret[]>([]);
/** Secrets sync no longer finds in their backend (#86), shown only on request. */
export const removedSecrets = writable<Secret[]>([]);
export const secretsLoading = writable<boolean>(false);
export const secretsError = writable<string | null>(null);

export const secretStats = derived(secrets, ($secrets) => {
  const total = $secrets.length;
  let ok = 0;
  let warning = 0;
  let expired = 0;
  let noTtl = 0;

  for (const s of $secrets) {
    switch (s.status) {
      case 'ok': ok++; break;
      case 'warning': warning++; break;
      case 'expired': expired++; break;
      case 'no_ttl': noTtl++; break;
    }
  }

  return { total, ok, warning, expired, noTtl };
});

export const criticalSecrets = derived(secrets, ($secrets) => {
  return $secrets.filter((s) => s.status === 'warning' || s.status === 'expired');
});

/** Fetch all secrets from the backend. */
export async function loadSecrets(): Promise<void> {
  secretsLoading.set(true);
  secretsError.set(null);
  try {
    const data = await secretsApi.fetchSecrets(undefined, undefined, undefined, true);
    secrets.set(data.filter((s) => s.removed_at === null));
    removedSecrets.set(data.filter((s) => s.removed_at !== null));
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to load secrets';
    secretsError.set(message);
  } finally {
    secretsLoading.set(false);
  }
}

/** Replace one secret in the store, e.g. after changing its assignment. */
export function updateSecret(updated: Secret): void {
  const replace = (list: Secret[]) => list.map((s) => (s.id === updated.id ? updated : s));
  secrets.update(replace);
  removedSecrets.update(replace);
}
