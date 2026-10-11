// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

/**
 * Audit log event matching the backend AuditEvent model (ADR-014).
 */
export interface AuditEvent {
  id: number;
  timestamp: string;
  /** sync, config, ui or api */
  source: string;
  actor: string | null;
  event_type: string;
  subject: string | null;
  vault_name: string | null;
  engine_id: string | null;
  secret_path: string | null;
  before: unknown;
  after: unknown;
  prev_hash: string;
  hash: string;
}

/**
 * Result of verifying the audit log's hash chain.
 */
export interface AuditChainStatus {
  valid: boolean;
  events: number;
  head_hash: string;
  first_invalid_id: number | null;
  reason: string | null;
}

/**
 * Filters of GET /api/v1/audit/events.
 */
export interface AuditFilters {
  vault_name?: string;
  engine_id?: string;
  secret_path?: string;
  event_type?: string;
  before_id?: number;
  limit?: number;
}
