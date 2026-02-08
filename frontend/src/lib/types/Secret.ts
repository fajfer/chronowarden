// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

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
  enabled: boolean;
  last_synced: string | null;
  status: SecretStatus;
}

/**
 * Payload for updating Chronowarden-specific metadata fields.
 */
export interface SecretMetadataUpdate {
  severity?: string;
  enabled?: boolean;
}
