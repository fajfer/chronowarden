<!-- SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org> -->
<!--                                                               -->
<!-- SPDX-License-Identifier: EUPL-1.2                              -->

<script lang="ts">
  import { filters, setSearch, toggleVault, toggleEngine, toggleSeverity, toggleStatus, clearFilters } from '$lib/stores/filters';
  import type { SeverityType, SecretStatus } from '$lib/types';

  let { availableVaults = [], availableEngines = [] }: {
    availableVaults?: string[];
    availableEngines?: string[];
  } = $props();

  const severities: SeverityType[] = ['critical', 'pci-dss-4.0', 'default', 'none'];
  const statuses: SecretStatus[] = ['healthy', 'warning', 'critical', 'expired'];
</script>

<div class="bg-gray-800 border border-gray-700 rounded-lg p-4 space-y-3">
  <div class="flex items-center justify-between">
    <h3 class="text-sm font-medium text-gray-300">Filters</h3>
    <button onclick={clearFilters} class="text-xs text-indigo-400 hover:text-indigo-300">Clear All</button>
  </div>

  <input
    type="text"
    placeholder="Search by name or path…"
    value={$filters.search}
    oninput={(e: Event) => setSearch((e.target as HTMLInputElement).value)}
    class="w-full px-3 py-2 text-sm bg-gray-900 border border-gray-600 rounded-lg text-gray-200
           placeholder-gray-500 focus:outline-none focus:border-indigo-500"
  />

  <div class="flex flex-wrap gap-4 text-xs">
    {#if availableVaults.length > 0}
      <div>
        <p class="text-gray-500 uppercase mb-1">Vault</p>
        <div class="flex flex-wrap gap-1">
          {#each availableVaults as vault}
            <button
              onclick={() => toggleVault(vault)}
              class="px-2 py-1 rounded {$filters.vaults.includes(vault)
                ? 'bg-indigo-600 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}"
            >
              {vault}
            </button>
          {/each}
        </div>
      </div>
    {/if}

    {#if availableEngines.length > 0}
      <div>
        <p class="text-gray-500 uppercase mb-1">Engine</p>
        <div class="flex flex-wrap gap-1">
          {#each availableEngines as engine}
            <button
              onclick={() => toggleEngine(engine)}
              class="px-2 py-1 rounded {$filters.engines.includes(engine)
                ? 'bg-indigo-600 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}"
            >
              {engine}
            </button>
          {/each}
        </div>
      </div>
    {/if}

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

    <div>
      <p class="text-gray-500 uppercase mb-1">Severity</p>
      <div class="flex flex-wrap gap-1">
        {#each severities as sev}
          <button
            onclick={() => toggleSeverity(sev)}
            class="px-2 py-1 rounded {$filters.severities.includes(sev)
              ? 'bg-indigo-600 text-white'
              : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}"
          >
            {sev}
          </button>
        {/each}
      </div>
    </div>
  </div>
</div>
