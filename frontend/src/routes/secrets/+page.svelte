<script lang="ts">
  // SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
  //
  // SPDX-License-Identifier: EUPL-1.2

  import { secrets, secretsLoading, secretsError } from '$lib/stores/secrets';
  import { filters } from '$lib/stores/filters';
  import Filters from '$lib/components/Filters.svelte';
  import StatusBadge from '$lib/components/StatusBadge.svelte';
  import SecretModal from '$lib/components/SecretModal.svelte';
  import { getStatusDotBg } from '$lib/utils/statusColor';
  import type { Secret } from '$lib/types';

  let selectedSecret = $state<Secret | null>(null);
  let sortField = $state<string>('full_path');
  let sortDir = $state<'asc' | 'desc'>('asc');
  let selectedIds = $state<number[]>([]);

  const filteredSecrets = $derived.by(() => {
    let result = [...$secrets];
    const f = $filters;

    if (f.search) {
      const search = f.search.toLowerCase();
      result = result.filter((s) => s.full_path.toLowerCase().includes(search));
    }
    if (f.vaultName) result = result.filter((s) => s.vault_name === f.vaultName);
    if (f.severity) result = result.filter((s) => s.severity === f.severity);
    if (f.engineId) result = result.filter((s) => s.engine_id === f.engineId);
    if (f.statuses.length > 0) result = result.filter((s) => f.statuses.includes(s.status));

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

  const allVisibleSelected = $derived(
    filteredSecrets.length > 0 && filteredSecrets.every((s) => selectedIds.includes(s.id)),
  );

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

  function toggleRow(id: number) {
    selectedIds = selectedIds.includes(id)
      ? selectedIds.filter((x) => x !== id)
      : [...selectedIds, id];
  }

  function toggleAll() {
    selectedIds = allVisibleSelected ? [] : filteredSecrets.map((s) => s.id);
  }

  /** Percentage of the rotation cycle that has elapsed (0–100). */
  function elapsedPct(s: Secret): number {
    if (s.days_remaining == null || !s.rotation_period_days) return 0;
    const p = s.rotation_period_days;
    return Math.max(2, Math.min(100, Math.round(((p - s.days_remaining) / p) * 100)));
  }

  function daysColor(s: Secret): string {
    if (s.days_remaining == null) return 'text-gray-500';
    if (s.status === 'expired') return 'text-red-400';
    if (s.status === 'warning') return 'text-yellow-400';
    return 'text-green-400';
  }

  function exportCsv() {
    const cols = ['full_path', 'engine_id', 'vault_name', 'owner', 'severity', 'rotation_period_days', 'days_remaining', 'status'];
    const header = cols.join(',');
    const rows = filteredSecrets.map((s) =>
      cols.map((c) => {
        const v = (s as unknown as Record<string, unknown>)[c];
        return v == null ? '' : `"${String(v).replace(/"/g, '""')}"`;
      }).join(','),
    );
    const blob = new Blob([[header, ...rows].join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'chronowarden-secrets.csv';
    a.click();
    URL.revokeObjectURL(url);
  }
</script>

<div class="space-y-4">
  <div class="flex items-end justify-between gap-4">
    <div>
      <h1 class="text-2xl font-bold text-white">Secrets</h1>
      <p class="mt-1 text-sm text-gray-400">{$secrets.length} tracked · metadata only, values never read</p>
    </div>
    <div class="flex gap-2">
      <button class="px-3 py-1.5 text-sm rounded-lg bg-gray-800 border border-gray-700 text-gray-300 hover:bg-gray-700 transition-colors">Columns</button>
      <button onclick={exportCsv} class="px-3 py-1.5 text-sm rounded-lg bg-gray-800 border border-gray-700 text-gray-300 hover:bg-gray-700 transition-colors">Export CSV</button>
    </div>
  </div>

  <Filters />

  {#if $secretsLoading}
    <div class="text-center text-gray-400 py-12">Loading…</div>
  {:else if $secretsError}
    <div class="px-4 py-3 bg-red-900/30 border border-red-700 rounded-lg text-red-300">{$secretsError}</div>
  {:else}
    {#if selectedIds.length > 0}
      <div class="flex items-center gap-3 px-4 py-2 bg-indigo-600/10 border border-indigo-500/40 rounded-lg text-sm text-gray-200">
        <span class="font-medium">{selectedIds.length} selected</span>
        <button class="text-indigo-300 hover:text-indigo-200">Set severity</button>
        <button class="text-indigo-300 hover:text-indigo-200">Toggle tracking</button>
        <button onclick={() => (selectedIds = [])} class="ml-auto text-gray-400 hover:text-gray-200">Clear</button>
      </div>
    {/if}

    <div class="bg-gray-800 border border-gray-700 rounded-lg overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-gray-500 text-[11px] uppercase tracking-wider bg-gray-900/40 border-b border-gray-700">
              <th class="px-4 py-3 w-10">
                <input type="checkbox" checked={allVisibleSelected} onchange={toggleAll} class="accent-indigo-500 align-middle" />
              </th>
              <th class="px-4 py-3 text-left font-semibold cursor-pointer hover:text-gray-300" onclick={() => toggleSort('secret_path')}>Secret {sortIcon('secret_path')}</th>
              <th class="px-4 py-3 text-left font-semibold cursor-pointer hover:text-gray-300" onclick={() => toggleSort('engine_id')}>Engine {sortIcon('engine_id')}</th>
              <th class="px-4 py-3 text-left font-semibold">Owner</th>
              <th class="px-4 py-3 text-left font-semibold cursor-pointer hover:text-gray-300" onclick={() => toggleSort('severity')}>Severity {sortIcon('severity')}</th>
              <th class="px-4 py-3 text-left font-semibold">Rotation cycle</th>
              <th class="px-4 py-3 text-right font-semibold cursor-pointer hover:text-gray-300" onclick={() => toggleSort('days_remaining')}>Remaining {sortIcon('days_remaining')}</th>
              <th class="px-4 py-3 text-left font-semibold">Status</th>
              <th class="px-4 py-3 w-10"></th>
            </tr>
          </thead>
          <tbody>
            {#each filteredSecrets as secret (secret.id)}
              <tr class="border-b border-gray-700/50 hover:bg-gray-700/30 transition-colors">
                <td class="px-4 py-3">
                  <input type="checkbox" checked={selectedIds.includes(secret.id)} onchange={() => toggleRow(secret.id)} class="accent-indigo-500 align-middle" />
                </td>
                <td class="px-4 py-3">
                  <button onclick={() => (selectedSecret = secret)} class="text-left block">
                    <span class="font-mono text-gray-200">{secret.secret_path}</span>
                    <span class="block text-xs text-gray-500 mt-0.5">{secret.vault_name}</span>
                  </button>
                </td>
                <td class="px-4 py-3">
                  <span class="font-mono text-xs text-gray-400 bg-gray-700/50 rounded px-1.5 py-0.5">{secret.engine_id}</span>
                </td>
                <td class="px-4 py-3 {secret.owner ? 'text-gray-300' : 'text-gray-600'}">{secret.owner ?? '—'}</td>
                <td class="px-4 py-3">
                  <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-700/60 text-gray-300">{secret.severity}</span>
                </td>
                <td class="px-4 py-3">
                  {#if secret.days_remaining != null && secret.rotation_period_days}
                    <div class="flex items-center gap-2.5">
                      <div class="w-28 h-1.5 rounded-full bg-gray-700 overflow-hidden">
                        <div class="h-full {getStatusDotBg(secret.status)}" style="width: {elapsedPct(secret)}%;"></div>
                      </div>
                      <span class="font-mono text-xs text-gray-500">{secret.rotation_period_days}d</span>
                    </div>
                  {:else}
                    <span class="font-mono text-xs text-gray-600">—</span>
                  {/if}
                </td>
                <td class="px-4 py-3 text-right font-mono font-semibold {daysColor(secret)}">
                  {secret.days_remaining != null ? secret.days_remaining + 'd' : '—'}
                </td>
                <td class="px-4 py-3"><StatusBadge status={secret.status} /></td>
                <td class="px-4 py-3">
                  <button onclick={() => (selectedSecret = secret)} class="text-gray-500 hover:text-white" title="View details">⋯</button>
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

<SecretModal secret={selectedSecret} onClose={() => (selectedSecret = null)} />
