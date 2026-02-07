// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import { writable, get } from 'svelte/store';
import type { FilterState, SeverityType, SecretStatus } from '$lib/types';
import { DEFAULT_FILTERS } from '$lib/types';

export const filters = writable<FilterState>({ ...DEFAULT_FILTERS });

/**
 * Clear all filters to defaults.
 */
export function clearFilters(): void {
  filters.set({ ...DEFAULT_FILTERS });
}

/**
 * Set the search query.
 */
export function setSearch(search: string): void {
  filters.update((f) => ({ ...f, search }));
}

/**
 * Toggle a vault in the filter.
 */
export function toggleVault(vault: string): void {
  filters.update((f) => {
    const vaults = f.vaults.includes(vault) ? f.vaults.filter((v) => v !== vault) : [...f.vaults, vault];
    return { ...f, vaults };
  });
}

/**
 * Toggle a severity in the filter.
 */
export function toggleSeverity(severity: SeverityType): void {
  filters.update((f) => {
    const severities = f.severities.includes(severity)
      ? f.severities.filter((s) => s !== severity)
      : [...f.severities, severity];
    return { ...f, severities };
  });
}

/**
 * Toggle a status in the filter.
 */
export function toggleStatus(status: SecretStatus): void {
  filters.update((f) => {
    const statuses = f.statuses.includes(status)
      ? f.statuses.filter((s) => s !== status)
      : [...f.statuses, status];
    return { ...f, statuses };
  });
}

/**
 * Toggle an engine in the filter.
 */
export function toggleEngine(engine: string): void {
  filters.update((f) => {
    const engines = f.engines.includes(engine) ? f.engines.filter((e) => e !== engine) : [...f.engines, engine];
    return { ...f, engines };
  });
}

/**
 * Toggle an owner in the filter.
 */
export function toggleOwner(owner: string): void {
  filters.update((f) => {
    const owners = f.owners.includes(owner) ? f.owners.filter((o) => o !== owner) : [...f.owners, owner];
    return { ...f, owners };
  });
}

/**
 * Set the enabled filter.
 */
export function setEnabled(enabled: boolean | null): void {
  filters.update((f) => ({ ...f, enabled }));
}
