// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import { writable } from 'svelte/store';
import { triggerVaultSync } from '$lib/api/sync';
import type { SyncResult } from '$lib/types';

export interface ToastMessage {
  id: number;
  message: string;
  type: 'success' | 'error' | 'info';
}

let toastId = 0;

export const syncHistory = writable<SyncResult[]>([]);
export const toasts = writable<ToastMessage[]>([]);

/** Add a toast notification that auto-dismisses after 5 seconds. */
export function addToast(message: string, type: 'success' | 'error' | 'info' = 'info'): void {
  const id = ++toastId;
  toasts.update((t) => [...t, { id, message, type }]);
  setTimeout(() => {
    toasts.update((t) => t.filter((toast) => toast.id !== id));
  }, 5000);
}

/** Trigger a sync for a specific vault via the backend. */
export async function syncVault(vaultName: string): Promise<SyncResult | null> {
  addToast(`Syncing ${vaultName}…`, 'info');
  try {
    const result = await triggerVaultSync(vaultName);
    syncHistory.update((h) => [result, ...h]);
    addToast(`Synced ${vaultName}: ${result.secrets_synced} secrets processed`, 'success');
    return result;
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Sync failed';
    addToast(`Sync failed for ${vaultName}: ${message}`, 'error');
    return null;
  }
}
