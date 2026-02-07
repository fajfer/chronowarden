// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

export type SeverityType = 'default' | 'critical' | 'pci-dss-4.0' | 'none';

export type SecretStatus = 'healthy' | 'warning' | 'critical' | 'expired';

export interface TtlHistoryEntry {
  date: string;
  ttl: number;
  days_until_expiry: number;
}

export interface Secret {
  id: number;
  name: string;
  path: string;
  engine: string;
  engine_type: string;
  vault: string;
  owner_id: string | null;
  owner_name: string | null;
  severity: SeverityType;
  enabled: boolean;
  ttl: number;
  expiry_date: string;
  days_until_expiry: number | null;
  status: SecretStatus;
  last_updated: string;
  created_at: string;
  raw_metadata: Record<string, unknown>;
  ttl_history: TtlHistoryEntry[];
}
