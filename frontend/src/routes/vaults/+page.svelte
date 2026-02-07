<script lang="ts">
  // SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
  //
  // SPDX-License-Identifier: EUPL-1.2

  import { fetchAllVaultHealth } from '$lib/api/vaults';
  import type { VaultInstanceHealth } from '$lib/types';

  let vaults = $state<VaultInstanceHealth[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  async function load() {
    loading = true;
    error = null;
    try {
      vaults = await fetchAllVaultHealth();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load vault health';
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    load();
  });
</script>

<div class="space-y-6">
  <div class="flex items-center justify-between">
    <h1 class="text-2xl font-bold text-white">Vault Instances</h1>
    <button onclick={load} class="px-4 py-2 text-sm rounded-lg bg-gray-700 hover:bg-gray-600 text-gray-200 transition-colors">
      Refresh
    </button>
  </div>

  {#if loading}
    <div class="text-center text-gray-400 py-12">Loading vault health…</div>
  {:else if error}
    <div class="px-4 py-3 bg-red-900/30 border border-red-700 rounded-lg text-red-300">
      <p class="font-medium">Failed to load vault health</p>
      <p class="text-sm mt-1">{error}</p>
    </div>
  {:else if vaults.length === 0}
    <div class="text-center text-gray-500 py-12">No vault instances configured</div>
  {:else}
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {#each vaults as vault}
        <div class="bg-gray-800 border border-gray-700 rounded-lg p-6">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-lg font-semibold text-white">{vault.name}</h3>
            <span class="w-3 h-3 rounded-full {vault.healthy ? 'bg-green-400' : 'bg-red-400'}"></span>
          </div>
          <div class="space-y-2 text-sm">
            <div class="flex justify-between">
              <span class="text-gray-500">Status</span>
              <span class="{vault.healthy ? 'text-green-400' : 'text-red-400'}">
                {vault.healthy ? 'Healthy' : 'Unhealthy'}
              </span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-500">Version</span>
              <span class="text-gray-300">{vault.version ?? '—'}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-500">Sealed</span>
              <span class="text-gray-300">{vault.sealed != null ? (vault.sealed ? 'Yes' : 'No') : '—'}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-500">Connected</span>
              <span class="text-gray-300">{vault.connected ? 'Yes' : 'No'}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-500">Initialized</span>
              <span class="text-gray-300">{vault.initialized != null ? (vault.initialized ? 'Yes' : 'No') : '—'}</span>
            </div>
            {#if vault.error}
              <div class="mt-2 px-3 py-2 bg-red-900/20 border border-red-800 rounded text-xs text-red-300">{vault.error}</div>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
