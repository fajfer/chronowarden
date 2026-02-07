// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import { writable } from 'svelte/store';
import type { FilterState, EngineType, SecretStatus } from '$lib/types';
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

/** Toggle an engine type in the filter. */
export function toggleEngineType(engineType: EngineType): void {
  filters.update((f) => {
    const engineTypes = f.engineTypes.includes(engineType)
      ? f.engineTypes.filter((e) => e !== engineType)
      : [...f.engineTypes, engineType];
    return { ...f, engineTypes };
  });
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

/** Set the isPublic filter. */
export function setIsPublic(isPublic: boolean | null): void {
  filters.update((f) => ({ ...f, isPublic }));
}
