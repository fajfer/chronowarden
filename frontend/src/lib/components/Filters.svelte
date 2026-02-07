<!-- SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org> -->
<!--                                                               -->
<!-- SPDX-License-Identifier: EUPL-1.2                              -->

<script lang="ts">
  import { filters, setSearch, toggleEngineType, toggleStatus, clearFilters } from '$lib/stores/filters';
  import type { EngineType, SecretStatus } from '$lib/types';

  const engineTypes: EngineType[] = ['manual', 'azure_keyvault', 'hashicorp_vault', 'x509'];
  const statuses: SecretStatus[] = ['healthy', 'warning', 'critical', 'expired'];
</script>

<div class="bg-gray-800 border border-gray-700 rounded-lg p-4 space-y-3">
  <div class="flex items-center justify-between">
    <h3 class="text-sm font-medium text-gray-300">Filters</h3>
    <button onclick={clearFilters} class="text-xs text-indigo-400 hover:text-indigo-300">Clear All</button>
  </div>

  <input
    type="text"
    placeholder="Search by name…"
    value={$filters.search}
    oninput={(e: Event) => setSearch((e.target as HTMLInputElement).value)}
    class="w-full px-3 py-2 text-sm bg-gray-900 border border-gray-600 rounded-lg text-gray-200
           placeholder-gray-500 focus:outline-none focus:border-indigo-500"
  />

  <div class="flex flex-wrap gap-4 text-xs">
    <div>
      <p class="text-gray-500 uppercase mb-1">Engine Type</p>
      <div class="flex flex-wrap gap-1">
        {#each engineTypes as et}
          <button
            onclick={() => toggleEngineType(et)}
            class="px-2 py-1 rounded {$filters.engineTypes.includes(et)
              ? 'bg-indigo-600 text-white'
              : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}"
          >
            {et}
          </button>
        {/each}
      </div>
    </div>

    <div>
      <p class="text-gray-500 uppercase mb-1">Status</p>
      <div class="flex flex-wrap gap-1">
        {#each statuses as status}
          <button
            onclick={() => toggleStatus(status)}
            class="px-2 py-1 rounded {$filters.statuses.includes(status)
              ? 'bg-indigo-600 text-white'
              : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}"
          >
            {status}
          </button>
        {/each}
      </div>
    </div>
  </div>
</div>
