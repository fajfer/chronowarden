// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import { writable } from 'svelte/store';
import { ApiError } from '#lib/api/client.js';
import { triggerVaultSync } from '#lib/api/sync.js';
import type { SyncResult } from '#lib/types/index.js';

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

/** Body of the 503 `detail` returned when a vault can't be reconnected for a sync. */
interface SyncUnavailableDetail {
  message: string;
  reason: string;
  error: string | null;
  retry_scheduled: boolean;
}

/** Parse the structured 503 detail from a failed sync, or null if the error is something else. */
function parseSyncUnavailable(err: unknown): SyncUnavailableDetail | null {
  if (!(err instanceof ApiError) || err.status !== 503) return null;
  try {
    const detail = JSON.parse(err.message).detail;
    return detail && typeof detail === 'object' ? (detail as SyncUnavailableDetail) : null;
  } catch {
    return null;
  }
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
    const unavailable = parseSyncUnavailable(err);
    if (unavailable?.retry_scheduled) {
      addToast(
        `${vaultName} is unreachable (${unavailable.reason}). Chronowarden keeps retrying and syncs it automatically once it's back.`,
        'info',
      );
    } else if (unavailable) {
      addToast(`${vaultName}: ${unavailable.reason} error, not retried. ${unavailable.error ?? ''}`.trim(), 'error');
    } else {
      const message = err instanceof Error ? err.message : 'Sync failed';
      addToast(`Sync failed for ${vaultName}: ${message}`, 'error');
    }
    return null;
  }
}
