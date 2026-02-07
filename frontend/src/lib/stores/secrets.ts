// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import { writable, derived } from 'svelte/store';
import type { Secret } from '$lib/types';
import { getStatusFromDays } from '$lib/utils/statusColor';

export const secrets = writable<Secret[]>([]);
export const secretsLoading = writable<boolean>(false);
export const secretsError = writable<string | null>(null);

export const secretStats = derived(secrets, ($secrets) => {
  const total = $secrets.length;
  let healthy = 0;
  let warning = 0;
  let critical = 0;
  let expired = 0;

  for (const s of $secrets) {
    const status = getStatusFromDays(s.days_until_expiry);
    switch (status) {
      case 'healthy': healthy++; break;
      case 'warning': warning++; break;
      case 'critical': critical++; break;
      case 'expired': expired++; break;
    }
  }

  return { total, healthy, warning, critical, expired };
});

export const criticalSecrets = derived(secrets, ($secrets) => {
  return $secrets.filter((s) => {
    const status = getStatusFromDays(s.days_until_expiry);
    return status === 'critical' || status === 'expired';
  });
});

function daysFromNow(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString();
}

function daysAgo(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString();
}

export const DEMO_SECRETS: Secret[] = [
  {
    id: 1,
    name: 'api-gateway-key',
    path: 'apps/api-gateway/key',
    engine: 'apps',
    engine_type: 'kv-v2',
    vault: 'production',
    owner_id: 'owner-1',
    owner_name: 'Alice Admin',
    severity: 'critical',
    enabled: true,
    ttl: 86400 * 90,
    expiry_date: daysFromNow(45),
    days_until_expiry: 45,
    status: 'healthy',
    last_updated: daysAgo(5),
    created_at: daysAgo(120),
    raw_metadata: {},
    ttl_history: [],
  },
  {
    id: 2,
    name: 'db-password-prod',
    path: 'databases/prod/password',
    engine: 'databases',
    engine_type: 'kv-v2',
    vault: 'production',
    owner_id: 'owner-1',
    owner_name: 'Alice Admin',
    severity: 'pci-dss-4.0',
    enabled: true,
    ttl: 86400 * 30,
    expiry_date: daysFromNow(22),
    days_until_expiry: 22,
    status: 'warning',
    last_updated: daysAgo(8),
    created_at: daysAgo(90),
    raw_metadata: {},
    ttl_history: [],
  },
  {
    id: 3,
    name: 'tls-cert-web',
    path: 'certs/web/tls',
    engine: 'certs',
    engine_type: 'pki',
    vault: 'production',
    owner_id: 'owner-2',
    owner_name: 'Bob Engineer',
    severity: 'critical',
    enabled: true,
    ttl: 86400 * 365,
    expiry_date: daysFromNow(7),
    days_until_expiry: 7,
    status: 'critical',
    last_updated: daysAgo(2),
    created_at: daysAgo(358),
    raw_metadata: {},
    ttl_history: [],
  },
  {
    id: 4,
    name: 'aws-iam-staging',
    path: 'cloud/aws/iam-staging',
    engine: 'cloud',
    engine_type: 'aws',
    vault: 'staging',
    owner_id: 'owner-2',
    owner_name: 'Bob Engineer',
    severity: 'default',
    enabled: true,
    ttl: 86400 * 60,
    expiry_date: daysFromNow(55),
    days_until_expiry: 55,
    status: 'healthy',
    last_updated: daysAgo(3),
    created_at: daysAgo(60),
    raw_metadata: {},
    ttl_history: [],
  },
  {
    id: 5,
    name: 'compliance-audit-key',
    path: 'compliance/audit/key',
    engine: 'compliance',
    engine_type: 'kv-v2',
    vault: 'production',
    owner_id: 'owner-1',
    owner_name: 'Alice Admin',
    severity: 'pci-dss-4.0',
    enabled: true,
    ttl: 86400 * 90,
    expiry_date: daysFromNow(-5),
    days_until_expiry: -5,
    status: 'expired',
    last_updated: daysAgo(30),
    created_at: daysAgo(180),
    raw_metadata: {},
    ttl_history: [],
  },
  {
    id: 6,
    name: 'dev-api-token',
    path: 'apps/dev/api-token',
    engine: 'apps',
    engine_type: 'kv-v2',
    vault: 'dev',
    owner_id: null,
    owner_name: null,
    severity: 'none',
    enabled: true,
    ttl: 86400 * 30,
    expiry_date: daysFromNow(90),
    days_until_expiry: 90,
    status: 'healthy',
    last_updated: daysAgo(1),
    created_at: daysAgo(30),
    raw_metadata: {},
    ttl_history: [],
  },
  {
    id: 7,
    name: 'staging-db-creds',
    path: 'databases/staging/creds',
    engine: 'databases',
    engine_type: 'kv-v2',
    vault: 'staging',
    owner_id: 'owner-2',
    owner_name: 'Bob Engineer',
    severity: 'default',
    enabled: false,
    ttl: 86400 * 60,
    expiry_date: daysFromNow(10),
    days_until_expiry: 10,
    status: 'critical',
    last_updated: daysAgo(15),
    created_at: daysAgo(90),
    raw_metadata: {},
    ttl_history: [],
  },
  {
    id: 8,
    name: 'internal-cert-ca',
    path: 'certs/internal/ca',
    engine: 'certs',
    engine_type: 'pki',
    vault: 'production',
    owner_id: 'owner-1',
    owner_name: 'Alice Admin',
    severity: 'critical',
    enabled: true,
    ttl: 86400 * 365,
    expiry_date: daysFromNow(200),
    days_until_expiry: 200,
    status: 'healthy',
    last_updated: daysAgo(10),
    created_at: daysAgo(165),
    raw_metadata: {},
    ttl_history: [],
  },
];

/**
 * Load demo secrets into the store.
 */
export function loadDemoSecrets(): void {
  secrets.set(DEMO_SECRETS);
}
