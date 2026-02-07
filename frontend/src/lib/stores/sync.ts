// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import { writable } from 'svelte/store';
import type { SyncResult, SyncStatus } from '$lib/types';

export interface ToastMessage {
  id: number;
  message: string;
  type: 'success' | 'error' | 'info';
}

let toastId = 0;

export const syncHistory = writable<SyncResult[]>([]);
export const syncStatuses = writable<SyncStatus[]>([]);
export const toasts = writable<ToastMessage[]>([]);

/**
 * Add a toast notification.
 */
export function addToast(message: string, type: 'success' | 'error' | 'info' = 'info'): void {
  const id = ++toastId;
  toasts.update((t) => [...t, { id, message, type }]);
  setTimeout(() => {
    toasts.update((t) => t.filter((toast) => toast.id !== id));
  }, 5000);
}

/**
 * Set sync status for a vault.
 */
export function setSyncStatus(vault: string, syncing: boolean): void {
  syncStatuses.update((statuses) => {
    const existing = statuses.findIndex((s) => s.vault === vault);
    if (existing >= 0) {
      const updated = [...statuses];
      updated[existing] = { ...updated[existing], syncing };
      return updated;
    }
    return [...statuses, { vault, syncing }];
  });
}

/**
 * Add a sync result to history.
 */
export function addSyncResult(result: SyncResult): void {
  syncHistory.update((history) => [result, ...history]);
}

/**
 * Connect to WebSocket for real-time sync updates.
 */
export function connectWebSocket(): void {
  if (typeof window === 'undefined') return;
  try {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/api/v1/ws/sync`);
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as SyncResult;
        addSyncResult(data);
        addToast(`Sync completed for ${data.vault}`, data.status === 'success' ? 'success' : 'error');
      } catch {
        // Ignore parse errors
      }
    };
  } catch {
    // WebSocket not available
  }
}
