// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import { apiPost } from './client';
import type { SyncResult } from '$lib/types';

/** POST /api/v1/sync/vault/:name — trigger sync for a specific vault. */
export function triggerVaultSync(vaultName: string): Promise<SyncResult> {
  return apiPost<SyncResult>(`/sync/vault/${vaultName}`);
}
