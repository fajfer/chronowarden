// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import { writable, derived } from 'svelte/store';
import * as secretsApi from '$lib/api/secrets';
import type { Secret, SecretCreate, SecretUpdate } from '$lib/types';
import { getDaysUntilExpiry } from '$lib/utils/dateFormat';
import { getStatusFromDays } from '$lib/utils/statusColor';

export const secrets = writable<Secret[]>([]);
export const secretsLoading = writable<boolean>(false);
export const secretsError = writable<string | null>(null);

export const secretStats = derived(secrets, ($secrets) => {
  const total = $secrets.length;
  let healthy = 0;
  let warning = 0;
  let critical = 0;
  let expired = 0;

  for (const s of $secrets) {
    const days = getDaysUntilExpiry(s.expiry_date);
    const status = getStatusFromDays(days);
    switch (status) {
      case 'healthy': healthy++; break;
      case 'warning': warning++; break;
      case 'critical': critical++; break;
      case 'expired': expired++; break;
    }
  }

  return { total, healthy, warning, critical, expired };
});

export const criticalSecrets = derived(secrets, ($secrets) => {
  return $secrets.filter((s) => {
    const days = getDaysUntilExpiry(s.expiry_date);
    const status = getStatusFromDays(days);
    return status === 'critical' || status === 'expired';
  });
});

/** Fetch all secrets from the backend. */
export async function loadSecrets(): Promise<void> {
  secretsLoading.set(true);
  secretsError.set(null);
  try {
    const data = await secretsApi.fetchSecrets();
    secrets.set(data);
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to load secrets';
    secretsError.set(message);
  } finally {
    secretsLoading.set(false);
  }
}

/** Create a new secret via the backend. */
export async function addSecret(data: SecretCreate): Promise<Secret> {
  const created = await secretsApi.createSecret(data);
  secrets.update((list) => [...list, created]);
  return created;
}

/** Update a secret via the backend. */
export async function editSecret(id: number, data: SecretUpdate): Promise<Secret> {
  const updated = await secretsApi.updateSecret(id, data);
  secrets.update((list) => list.map((s) => (s.id === id ? updated : s)));
  return updated;
}

/** Delete a secret via the backend. */
export async function removeSecret(id: number): Promise<void> {
  await secretsApi.deleteSecret(id);
  secrets.update((list) => list.filter((s) => s.id !== id));
}
