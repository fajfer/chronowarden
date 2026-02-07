<script lang="ts">
  // SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
  //
  // SPDX-License-Identifier: EUPL-1.2

  import type { VaultInstance } from '$lib/types';

  // Demo data
  const vaults: VaultInstance[] = [
    { name: 'production', connected: true, healthy: true, version: '1.15.0', sealed: false, initialized: true },
    { name: 'staging', connected: true, healthy: true, version: '1.15.0', sealed: false, initialized: true },
    { name: 'dev', connected: true, healthy: false, version: '1.14.0', sealed: false, initialized: true, error: 'Intermittent connectivity' },
  ];
</script>

<div class="space-y-6">
  <h1 class="text-2xl font-bold text-white">Vault Instances</h1>

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
            <span class="{vault.healthy ? 'text-green-400' : 'text-red-400'}">{vault.healthy ? 'Healthy' : 'Unhealthy'}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-500">Version</span>
            <span class="text-gray-300">{vault.version ?? '—'}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-500">Sealed</span>
            <span class="text-gray-300">{vault.sealed ? 'Yes' : 'No'}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-500">Connected</span>
            <span class="text-gray-300">{vault.connected ? 'Yes' : 'No'}</span>
          </div>
          {#if vault.error}
            <div class="mt-2 px-3 py-2 bg-red-900/20 border border-red-800 rounded text-xs text-red-300">{vault.error}</div>
          {/if}
        </div>
      </div>
    {/each}
  </div>
</div>
