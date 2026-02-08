// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import { writable, derived } from 'svelte/store';
import * as secretsApi from '$lib/api/secrets';
import type { Secret, SecretMetadataUpdate } from '$lib/types';

export const secrets = writable<Secret[]>([]);
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
    const data = await secretsApi.fetchSecrets();
    secrets.set(data);
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to load secrets';
    secretsError.set(message);
  } finally {
    secretsLoading.set(false);
  }
}

/** Update secret metadata via the backend. */
export async function editSecretMetadata(id: number, data: SecretMetadataUpdate): Promise<Secret> {
  const updated = await secretsApi.updateSecretMetadata(id, data);
  secrets.update((list) => list.map((s) => (s.id === id ? updated : s)));
  return updated;
}
