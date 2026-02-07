// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

export interface VaultInstance {
  name: string;
  connected: boolean;
  healthy: boolean;
  version?: string;
  sealed: boolean;
  initialized: boolean;
  error?: string;
}

export interface SyncResult {
  vault: string;
  secrets_synced: number;
  status: 'success' | 'error';
  duration?: number;
  error?: string;
  timestamp: string;
}

export interface SyncStatus {
  vault: string;
  syncing: boolean;
  last_sync?: string;
}
