<script lang="ts">
  // SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
  //
  // SPDX-License-Identifier: EUPL-1.2

  import { secrets, secretsLoading, secretsError } from '$lib/stores/secrets';
  import { filters } from '$lib/stores/filters';
  import Filters from '$lib/components/Filters.svelte';
  import StatusBadge from '$lib/components/StatusBadge.svelte';
  import SecretModal from '$lib/components/SecretModal.svelte';
  import { formatDate } from '$lib/utils/dateFormat';
  import type { Secret } from '$lib/types';

  let selectedSecret = $state<Secret | null>(null);
  let sortField = $state<string>('full_path');
  let sortDir = $state<'asc' | 'desc'>('asc');

  const filteredSecrets = $derived.by(() => {
    let result = [...$secrets];
    const f = $filters;

    if (f.search) {
      const search = f.search.toLowerCase();
      result = result.filter((s) => s.full_path.toLowerCase().includes(search));
    }
    if (f.statuses.length > 0) {
      result = result.filter((s) => f.statuses.includes(s.status));
    }

    result.sort((a, b) => {
      let cmp = 0;
      const aVal = (a as unknown as Record<string, unknown>)[sortField];
      const bVal = (b as unknown as Record<string, unknown>)[sortField];

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

  function sortIcon(field: string): string {
    if (sortField !== field) return '↕';
    return sortDir === 'asc' ? '↑' : '↓';
  }
</script>

<div class="space-y-4">
  <h1 class="text-2xl font-bold text-white">Secrets</h1>

  <Filters />

  {#if $secretsLoading}
    <div class="text-center text-gray-400 py-12">Loading…</div>
  {:else if $secretsError}
    <div class="px-4 py-3 bg-red-900/30 border border-red-700 rounded-lg text-red-300">
      {$secretsError}
    </div>
  {:else}
    <div class="bg-gray-800 border border-gray-700 rounded-lg overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-gray-400 text-xs uppercase border-b border-gray-700">
              <th class="px-4 py-3 text-left cursor-pointer hover:text-gray-200" onclick={() => toggleSort('full_path')}>
                Path {sortIcon('full_path')}
              </th>
              <th class="px-4 py-3 text-left cursor-pointer hover:text-gray-200" onclick={() => toggleSort('severity')}>
                Severity {sortIcon('severity')}
              </th>
              <th class="px-4 py-3 text-left">Enabled</th>
              <th class="px-4 py-3 text-left cursor-pointer hover:text-gray-200" onclick={() => toggleSort('ttl_date')}>
                TTL {sortIcon('ttl_date')}
              </th>
              <th class="px-4 py-3 text-left">Days</th>
              <th class="px-4 py-3 text-left">Status</th>
              <th class="px-4 py-3 text-left">Actions</th>
            </tr>
          </thead>
          <tbody>
            {#each filteredSecrets as secret (secret.id)}
              <tr class="border-b border-gray-700/50 hover:bg-gray-700/30 transition-colors">
                <td class="px-4 py-3">
                  <button onclick={() => selectedSecret = secret} class="font-medium text-indigo-400 hover:text-indigo-300 text-left">
                    {secret.full_path}
                  </button>
                </td>
                <td class="px-4 py-3 text-gray-400">{secret.severity}</td>
                <td class="px-4 py-3 text-gray-400">{secret.enabled ? '✓' : '—'}</td>
                <td class="px-4 py-3 text-gray-400">{formatDate(secret.ttl_date)}</td>
                <td class="px-4 py-3 text-gray-200">{secret.days_remaining ?? '—'}</td>
                <td class="px-4 py-3"><StatusBadge status={secret.status} /></td>
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
