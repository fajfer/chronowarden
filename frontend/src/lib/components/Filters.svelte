<!-- SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org> -->
<!--                                                               -->
<!-- SPDX-License-Identifier: EUPL-1.2                              -->

<script lang="ts">
  import {
    filters, setSearch, toggleStatus,
    setVaultName, setSeverity, setEngineId, setSystemId, togglePrivilegedOnly, clearFilters,
  } from '#lib/stores/filters.js';
  import { secrets } from '#lib/stores/secrets.js';
  import { getStatusLabel } from '#lib/utils/statusColor.js';
  import { UNASSIGNED_SYSTEM } from '#lib/types/index.js';
  import type { SecretStatus, SystemRef } from '#lib/types/index.js';

  const statuses: SecretStatus[] = ['ok', 'warning', 'expired', 'no_ttl'];

  const vaultOptions = $derived(Array.from(new Set($secrets.map((s) => s.vault_name))).sort());
  const severityOptions = $derived(Array.from(new Set($secrets.map((s) => s.severity))).sort());
  const engineOptions = $derived(Array.from(new Set($secrets.map((s) => s.engine_id))).sort());
  const systemOptions = $derived(
    Array.from(new Map($secrets.filter((s) => s.system).map((s) => [s.system!.id, s.system!])).values())
      .sort((a: SystemRef, b: SystemRef) => a.name.localeCompare(b.name)),
  );

  const hasActive = $derived(
    !!($filters.search || $filters.vaultName || $filters.severity || $filters.engineId || $filters.systemId ||
      $filters.privilegedOnly || $filters.statuses.length),
  );

  const selectClass =
    'bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-300 focus:outline-none focus:border-indigo-500';
</script>

<div class="flex flex-wrap items-center gap-2">
  <div class="relative">
    <span class="absolute left-3 top-1/2 -translate-y-1/2 w-3 h-3 rounded-full border-[1.5px] border-gray-500"></span>
    <input
      type="text"
      placeholder="Search path…"
      value={$filters.search}
      oninput={(e: Event) => setSearch((e.target as HTMLInputElement).value)}
      class="w-64 pl-9 pr-3 py-2 text-sm bg-gray-800 border border-gray-700 rounded-lg text-gray-200
             placeholder-gray-500 focus:outline-none focus:border-indigo-500"
    />
  </div>

  <select class={selectClass} value={$filters.vaultName ?? ''} onchange={(e: Event) => setVaultName((e.target as HTMLSelectElement).value || null)}>
    <option value="">All vaults</option>
    {#each vaultOptions as v}<option value={v}>{v}</option>{/each}
  </select>

  <select class={selectClass} value={$filters.severity ?? ''} onchange={(e: Event) => setSeverity((e.target as HTMLSelectElement).value || null)}>
    <option value="">All severities</option>
    {#each severityOptions as s}<option value={s}>{s}</option>{/each}
  </select>

  <select class={selectClass} value={$filters.engineId ?? ''} onchange={(e: Event) => setEngineId((e.target as HTMLSelectElement).value || null)}>
    <option value="">All engines</option>
    {#each engineOptions as eng}<option value={eng}>{eng}</option>{/each}
  </select>

  <select class={selectClass} value={$filters.systemId ?? ''} onchange={(e: Event) => setSystemId((e.target as HTMLSelectElement).value || null)}>
    <option value="">All systems</option>
    <option value={UNASSIGNED_SYSTEM}>Unassigned</option>
    {#each systemOptions as sys (sys.id)}<option value={sys.id}>{sys.name}</option>{/each}
  </select>

  <button
    onclick={togglePrivilegedOnly}
    aria-pressed={$filters.privilegedOnly}
    class="px-2.5 py-1 rounded-full text-xs font-medium transition-colors
           {$filters.privilegedOnly ? 'bg-rose-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}"
  >
    Privileged only
  </button>

  <div class="flex flex-wrap gap-1">
    {#each statuses as status}
      <button
        onclick={() => toggleStatus(status)}
        class="px-2.5 py-1 rounded-full text-xs font-medium transition-colors
               {$filters.statuses.includes(status)
                 ? 'bg-indigo-600 text-white'
                 : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}"
      >
        {getStatusLabel(status)}
      </button>
    {/each}
  </div>

  {#if hasActive}
    <button onclick={clearFilters} class="ml-1 text-xs text-indigo-400 hover:text-indigo-300">Clear all</button>
  {/if}
</div>
