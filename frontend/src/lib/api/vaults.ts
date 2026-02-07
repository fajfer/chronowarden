// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import { apiGet } from './client';
import type { VaultInstance } from '$lib/types';

/**
 * Fetch all vault instances.
 */
export function fetchVaults(): Promise<VaultInstance[]> {
  return apiGet<VaultInstance[]>('/vaults');
}

/**
 * Fetch a single vault by name.
 */
export function fetchVault(name: string): Promise<VaultInstance> {
  return apiGet<VaultInstance>(`/vaults/${name}`);
}
