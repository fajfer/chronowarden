// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import { apiPost } from './client';
import type { SyncResult } from '#lib/types/index.js';

/** POST /api/v1/sync/provider/:name — trigger sync for one backend. */
export function triggerVaultSync(vaultName: string): Promise<SyncResult> {
  return apiPost<SyncResult>(`/sync/provider/${vaultName}`);
}
