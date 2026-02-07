// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import { apiPost } from './client';
import type { SyncResult } from '$lib/types';

/**
 * Trigger a sync for the specified vaults.
 */
export function triggerSync(vaults?: string[]): Promise<SyncResult[]> {
  return apiPost<SyncResult[]>('/sync', vaults ? { vaults } : undefined);
}
