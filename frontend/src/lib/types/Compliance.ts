// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

/** Which secrets a snapshot covers; empty lists mean all (#94). */
export interface ComplianceScope {
  vaults: string[];
  engines: string[];
  systems: string[];
  privileged_only: boolean;
}

export interface SnapshotInfo {
  id: number;
  created_at: string;
  label: string | null;
  cadence: string | null;
  period: string | null;
  supersedes: number | null;
  row_count: number;
  sha256: string;
}

export interface GapEntry {
  id: number;
  full_path: string;
  gaps: string[];
}

export interface GapReport {
  scope: ComplianceScope;
  total: number;
  counts: Record<string, number>;
  secrets: GapEntry[];
}

export interface PeriodStatus {
  cadence: string;
  period: string;
  start: string;
  end: string;
  snapshot_id: number | null;
}

export interface SummaryGroup {
  vault?: string;
  engine?: string;
  system?: string | null;
  total: number;
  privileged: number;
}

export interface ComplianceSummary {
  by_vault: SummaryGroup[];
  by_engine: SummaryGroup[];
  by_system: SummaryGroup[];
}

/** What a snapshot request carries: ad hoc (label + scope) or closing a period (cadence + period). */
export interface SnapshotRequest {
  label?: string;
  scope?: ComplianceScope;
  cadence?: string;
  period?: string;
  supersedes?: number;
}
