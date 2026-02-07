<script lang="ts">
  // SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
  //
  // SPDX-License-Identifier: EUPL-1.2

  import { secrets } from '$lib/stores/secrets';
  import { filters } from '$lib/stores/filters';
  import { canBulkEditSecrets } from '$lib/stores/auth';
  import Filters from '$lib/components/Filters.svelte';
  import StatusBadge from '$lib/components/StatusBadge.svelte';
  import SeverityBadge from '$lib/components/SeverityBadge.svelte';
  import SecretModal from '$lib/components/SecretModal.svelte';
  import BulkActions from '$lib/components/BulkActions.svelte';
  import { formatDate } from '$lib/utils/dateFormat';
  import { getStatusFromDays } from '$lib/utils/statusColor';
  import type { Secret, SecretStatus } from '$lib/types';

  let selectedSecret = $state<Secret | null>(null);
  let selectedIds = $state<Set<number>>(new Set());
  let sortField = $state<string>('name');
  let sortDir = $state<'asc' | 'desc'>('asc');

  const availableVaults = $derived([...new Set($secrets.map(s => s.vault))]);
  const availableEngines = $derived([...new Set($secrets.map(s => s.engine))]);

  const filteredSecrets = $derived.by(() => {
    let result = [...$secrets];
    const f = $filters;

    if (f.search) {
      const search = f.search.toLowerCase();
      result = result.filter(s => s.name.toLowerCase().includes(search) || s.path.toLowerCase().includes(search));
    }
    if (f.vaults.length > 0) {
      result = result.filter(s => f.vaults.includes(s.vault));
    }
    if (f.engines.length > 0) {
      result = result.filter(s => f.engines.includes(s.engine));
    }
    if (f.severities.length > 0) {
      result = result.filter(s => f.severities.includes(s.severity));
    }
    if (f.statuses.length > 0) {
      result = result.filter(s => {
        const status = getStatusFromDays(s.days_until_expiry);
        return f.statuses.includes(status);
      });
    }
    if (f.enabled !== null) {
      result = result.filter(s => s.enabled === f.enabled);
    }

    // Sorting
    result.sort((a, b) => {
      let cmp = 0;
      const field = sortField;
      const aVal = (a as Record<string, unknown>)[field];
      const bVal = (b as Record<string, unknown>)[field];

      if (aVal == null && bVal == null) cmp = 0;
      else if (aVal == null) cmp = 1;
      else if (bVal == null) cmp = -1;
      else if (typeof aVal === 'string') cmp = aVal.localeCompare(bVal as string);
      else if (typeof aVal === 'number') cmp = (aVal as number) - (bVal as number);
      else cmp = 0;

      return sortDir === 'desc' ? -cmp : cmp;
    });

    return result;
  });

  function toggleSort(field: string) {
    if (sortField === field) {
      sortDir = sortDir === 'asc' ? 'desc' : 'asc';
    } else {
      sortField = field;
      sortDir = 'asc';
    }
  }

  function toggleSelect(id: number) {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    selectedIds = next;
  }

  function toggleSelectAll() {
    if (selectedIds.size === filteredSecrets.length) {
      selectedIds = new Set();
    } else {
      selectedIds = new Set(filteredSecrets.map(s => s.id));
    }
  }

  function sortIcon(field: string): string {
    if (sortField !== field) return '↕';
    return sortDir === 'asc' ? '↑' : '↓';
  }

  // Mobile detection
  let isMobile = $state(false);
  $effect(() => {
    if (typeof window !== 'undefined') {
      const check = () => { isMobile = window.innerWidth < 768; };
      check();
      window.addEventListener('resize', check);
      return () => window.removeEventListener('resize', check);
    }
  });
</script>

<div class="space-y-4">
  <h1 class="text-2xl font-bold text-white">Secrets</h1>

  <Filters {availableVaults} {availableEngines} />

  <BulkActions
    selectedCount={selectedIds.size}
    onEnable={() => { selectedIds = new Set(); }}
    onDisable={() => { selectedIds = new Set(); }}
    onChangeSeverity={() => { selectedIds = new Set(); }}
  />

  {#if isMobile}
    <!-- Mobile Card View -->
    <div class="space-y-3">
      {#each filteredSecrets as secret (secret.id)}
        <div
          class="bg-gray-800 border border-gray-700 rounded-lg p-4 cursor-pointer hover:border-gray-600 transition-colors"
          onclick={() => selectedSecret = secret}
        >
          <div class="flex items-center justify-between mb-2">
            <StatusBadge status={getStatusFromDays(secret.days_until_expiry)} />
            <SeverityBadge severity={secret.severity} />
          </div>
          <h3 class="font-medium text-gray-200">{secret.name}</h3>
          <p class="text-xs text-gray-500 mt-1">Vault: {secret.vault}</p>
          <p class="text-xs text-gray-500">Owner: {secret.owner_name ?? '—'}</p>
          <p class="text-xs text-gray-500">Expires in {secret.days_until_expiry ?? '—'} days</p>
          <div class="flex gap-2 mt-3">
            <button onclick={() => selectedSecret = secret} class="px-3 py-1 text-xs rounded bg-gray-700 hover:bg-gray-600 text-gray-300">View</button>
          </div>
        </div>
      {/each}
    </div>
  {:else}
    <!-- Desktop Table View -->
    <div class="bg-gray-800 border border-gray-700 rounded-lg overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-gray-400 text-xs uppercase border-b border-gray-700">
              {#if $canBulkEditSecrets}
                <th class="px-3 py-3 w-10">
                  <input type="checkbox" checked={selectedIds.size === filteredSecrets.length && filteredSecrets.length > 0} onchange={toggleSelectAll} class="rounded bg-gray-700 border-gray-600" />
                </th>
              {/if}
              <th class="px-4 py-3 text-left cursor-pointer hover:text-gray-200" onclick={() => toggleSort('name')}>Name {sortIcon('name')}</th>
              <th class="px-4 py-3 text-left cursor-pointer hover:text-gray-200" onclick={() => toggleSort('engine')}>Engine {sortIcon('engine')}</th>
              <th class="px-4 py-3 text-left cursor-pointer hover:text-gray-200" onclick={() => toggleSort('vault')}>Vault {sortIcon('vault')}</th>
              <th class="px-4 py-3 text-left">Owner</th>
              <th class="px-4 py-3 text-left">Severity</th>
              <th class="px-4 py-3 text-left cursor-pointer hover:text-gray-200 hidden lg:table-cell" onclick={() => toggleSort('last_updated')}>Updated {sortIcon('last_updated')}</th>
              <th class="px-4 py-3 text-left cursor-pointer hover:text-gray-200" onclick={() => toggleSort('expiry_date')}>Expiry {sortIcon('expiry_date')}</th>
              <th class="px-4 py-3 text-left cursor-pointer hover:text-gray-200" onclick={() => toggleSort('days_until_expiry')}>Days {sortIcon('days_until_expiry')}</th>
              <th class="px-4 py-3 text-left">Status</th>
              <th class="px-4 py-3 text-left">Actions</th>
            </tr>
          </thead>
          <tbody>
            {#each filteredSecrets as secret (secret.id)}
              <tr class="border-b border-gray-700/50 hover:bg-gray-700/30 transition-colors">
                {#if $canBulkEditSecrets}
                  <td class="px-3 py-3">
                    <input type="checkbox" checked={selectedIds.has(secret.id)} onchange={() => toggleSelect(secret.id)} class="rounded bg-gray-700 border-gray-600" />
                  </td>
                {/if}
                <td class="px-4 py-3">
                  <button onclick={() => selectedSecret = secret} class="font-medium text-indigo-400 hover:text-indigo-300 text-left">{secret.name}</button>
                  <div class="text-xs text-gray-500">{secret.path}</div>
                </td>
                <td class="px-4 py-3 text-gray-400">{secret.engine}</td>
                <td class="px-4 py-3 text-gray-400">{secret.vault}</td>
                <td class="px-4 py-3 text-gray-400">{secret.owner_name ?? '—'}</td>
                <td class="px-4 py-3"><SeverityBadge severity={secret.severity} /></td>
                <td class="px-4 py-3 text-gray-400 hidden lg:table-cell">{formatDate(secret.last_updated)}</td>
                <td class="px-4 py-3 text-gray-400">{formatDate(secret.expiry_date)}</td>
                <td class="px-4 py-3 text-gray-200">{secret.days_until_expiry ?? '—'}</td>
                <td class="px-4 py-3"><StatusBadge status={getStatusFromDays(secret.days_until_expiry)} /></td>
                <td class="px-4 py-3">
                  <button onclick={() => selectedSecret = secret} class="text-gray-400 hover:text-white" title="View Details">⋮</button>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      {#if filteredSecrets.length === 0}
        <div class="px-6 py-12 text-center text-gray-500">No secrets match your filters</div>
      {/if}
    </div>
  {/if}
</div>

<SecretModal secret={selectedSecret} onClose={() => selectedSecret = null} />
