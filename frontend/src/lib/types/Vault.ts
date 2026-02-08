// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

/**
 * Vault instance health matching the backend VaultInstanceHealth model.
 */
export interface VaultInstanceHealth {
  name: string;
  connected: boolean;
  healthy: boolean;
  initialized: boolean | null;
  sealed: boolean | null;
  version: string | null;
  error: string | null;
}

/**
 * Sync result matching the backend sync endpoint response.
 */
export interface SyncResult {
  vault: string;
  secrets_synced: number;
  secrets: SyncedSecretEntry[];
}

/**
 * Individual synced secret entry from the sync response.
 */
export interface SyncedSecretEntry {
  engine: string;
  path: string;
  ttl: string | null;
  severity: string | null;
  enabled: boolean;
}

/**
 * API root info from GET /.
 */
export interface ApiInfo {
  name: string;
  version: string;
  docs: string;
}

/**
 * Health check response from GET /api/v1/health.
 */
export interface HealthStatus {
  status: string;
}
