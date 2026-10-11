// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import { apiGet, apiPost } from './client';
import type { AuditChainStatus, AuditEvent, AuditFilters } from '#lib/types/index.js';

/** GET /api/v1/audit/events — events, newest first. */
export function fetchAuditEvents(filters: AuditFilters = {}): Promise<AuditEvent[]> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== '') params.set(key, String(value));
  }
  const qs = params.toString();
  return apiGet<AuditEvent[]>(`/audit/events${qs ? `?${qs}` : ''}`);
}

/** GET /api/v1/audit/verify — recompute the hash chain. */
export function verifyAuditLog(): Promise<AuditChainStatus> {
  return apiGet<AuditChainStatus>('/audit/verify');
}

/** POST /api/v1/audit/events/:id/revert — restore the value an event replaced. */
export function revertAuditEvent(id: number): Promise<AuditEvent> {
  return apiPost<AuditEvent>(`/audit/events/${id}/revert`);
}

/** URL of the full JSON Lines export (a download, not a fetch). */
export function auditExportUrl(): string {
  return `${(import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')}/audit/events.jsonl`;
}
