// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import type { OwnerRef, SystemRef } from './System';

/**
 * Computed status for a secret based on TTL and days remaining.
 */
export type SecretStatus = 'expired' | 'warning' | 'ok' | 'no_ttl';

/**
 * Secret metadata response from the cache, matching the backend SecretMetadataResponse model.
 */
export interface Secret {
  id: number;
  vault_name: string;
  engine_id: string;
  secret_path: string;
  full_path: string;
  ttl: string | null;
  ttl_date: string | null;
  days_remaining: number | null;
  severity: string;
  rotation_period_days: number;
  alert_threshold_days: number;
  last_synced: string | null;
  status: SecretStatus;
  /** When sync stopped finding the secret in its backend (#86); null while it exists. */
  removed_at: string | null;
  /** Assigned system, or null when unassigned (#61). */
  system: SystemRef | null;
  /** Owners assigned to the secret itself. */
  owners: OwnerRef[];
  /** The secret's own owners, or else its system's owners (ADR-010). */
  effective_owners: OwnerRef[];
}

/**
 * Result of purging removed secrets.
 */
export interface PurgeResult {
  purged: number;
  secrets: string[];
}
