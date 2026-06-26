// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import { writable } from 'svelte/store';
import type { FilterState, SecretStatus } from '$lib/types';
import { DEFAULT_FILTERS } from '$lib/types';

export const filters = writable<FilterState>({ ...DEFAULT_FILTERS });

/** Clear all filters to defaults. */
export function clearFilters(): void {
  filters.set({ ...DEFAULT_FILTERS });
}

/** Set the search query. */
export function setSearch(search: string): void {
  filters.update((f) => ({ ...f, search }));
}

/** Toggle a status in the filter. */
export function toggleStatus(status: SecretStatus): void {
  filters.update((f) => {
    const statuses = f.statuses.includes(status)
      ? f.statuses.filter((s) => s !== status)
      : [...f.statuses, status];
    return { ...f, statuses };
  });
}

/** Set the vault name filter. */
export function setVaultName(vaultName: string | null): void {
  filters.update((f) => ({ ...f, vaultName }));
}

/** Set the severity filter. */
export function setSeverity(severity: string | null): void {
  filters.update((f) => ({ ...f, severity }));
}

/** Set the engine id filter. */
export function setEngineId(engineId: string | null): void {
  filters.update((f) => ({ ...f, engineId }));
}

/** Set the enabled filter. */
export function setEnabled(enabled: boolean | null): void {
  filters.update((f) => ({ ...f, enabled }));
}
