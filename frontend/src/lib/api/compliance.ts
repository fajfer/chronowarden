// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import { apiGet, apiPost } from './client';
import type {
  ComplianceScope, ComplianceSummary, GapReport, PeriodStatus, PolicyDefinition, PolicyEvaluation, SnapshotInfo,
  SnapshotRequest,
} from '#lib/types/index.js';

const BASE = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '');

/** GET /api/v1/compliance/summary — total and privileged counts per vault, engine and system. */
export function fetchComplianceSummary(): Promise<ComplianceSummary> {
  return apiGet<ComplianceSummary>('/compliance/summary');
}

/** GET /api/v1/compliance/gaps — evidence gaps for a scope or a configured cadence. */
export function fetchGaps(scope: ComplianceScope | null, cadence?: string): Promise<GapReport> {
  const params = new URLSearchParams();
  if (cadence) params.set('cadence', cadence);
  if (scope) {
    scope.vaults.forEach((v) => params.append('vaults', v));
    scope.engines.forEach((e) => params.append('engines', e));
    scope.systems.forEach((s) => params.append('systems', s));
    if (scope.privileged_only) params.set('privileged_only', 'true');
  }
  const qs = params.toString();
  return apiGet<GapReport>(`/compliance/gaps${qs ? `?${qs}` : ''}`);
}

/** GET /api/v1/compliance/periods — ended reporting periods and whether they were closed. */
export function fetchPeriods(): Promise<PeriodStatus[]> {
  return apiGet<PeriodStatus[]>('/compliance/periods');
}

/** GET /api/v1/compliance/snapshots — snapshots, newest first. */
export function fetchSnapshots(): Promise<SnapshotInfo[]> {
  return apiGet<SnapshotInfo[]>('/compliance/snapshots');
}

/** POST /api/v1/compliance/snapshots — freeze a snapshot. */
export function createSnapshot(request: SnapshotRequest): Promise<SnapshotInfo> {
  return apiPost<SnapshotInfo>('/compliance/snapshots', request);
}

/** GET /api/v1/compliance/settings — compliance settings from config.yaml. */
export function fetchComplianceSettings(): Promise<Record<string, unknown>> {
  return apiGet<Record<string, unknown>>('/compliance/settings');
}

/** GET /api/v1/compliance/policies — configured policies with their YAML. */
export function fetchPolicies(): Promise<PolicyDefinition[]> {
  return apiGet<PolicyDefinition[]>('/compliance/policies');
}

/** GET /api/v1/compliance/policies/{id}/evaluation — a policy evaluated now, with its trend across snapshots. */
export function fetchPolicyEvaluation(id: string): Promise<PolicyEvaluation> {
  return apiGet<PolicyEvaluation>(`/compliance/policies/${encodeURIComponent(id)}/evaluation`);
}

/** Download URL of a snapshot export (`json` is the verifiable form, `pdf` the report). */
export function snapshotExportUrl(id: number, format: 'json' | 'csv' | 'pdf'): string {
  return format === 'pdf'
    ? `${BASE}/compliance/snapshots/${id}/report.pdf`
    : `${BASE}/compliance/snapshots/${id}.${format}`;
}
