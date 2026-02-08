<script lang="ts">
  // SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
  //
  // SPDX-License-Identifier: EUPL-1.2

  import { syncHistory } from '$lib/stores/sync';
  import { syncVault } from '$lib/stores/sync';
  import { loadSecrets } from '$lib/stores/secrets';
  import { fetchVaultInstances } from '$lib/api/vaults';
  import { formatDate } from '$lib/utils/dateFormat';

  let vaultNames = $state<string[]>([]);
  let syncing = $state(false);

  async function loadVaults() {
    try {
      const result = await fetchVaultInstances();
      vaultNames = result.instances;
    } catch {
      vaultNames = [];
    }
  }

  async function handleSync(vault: string) {
    syncing = true;
    await syncVault(vault);
    await loadSecrets();
    syncing = false;
  }

  $effect(() => {
    loadVaults();
  });
</script>

<div class="space-y-6">
  <div class="flex items-center justify-between">
    <h1 class="text-2xl font-bold text-white">Sync</h1>
  </div>

  <!-- Trigger Sync -->
  <div class="bg-gray-800 border border-gray-700 rounded-lg p-6">
    <h2 class="text-lg font-semibold text-white mb-4">Trigger Vault Sync</h2>
    {#if vaultNames.length === 0}
      <p class="text-gray-500">No vault instances configured</p>
    {:else}
      <div class="flex flex-wrap gap-2">
        {#each vaultNames as vault}
          <button
            onclick={() => handleSync(vault)}
            disabled={syncing}
            class="px-4 py-2 text-sm rounded-lg transition-colors
                   {syncing ? 'bg-gray-600 text-gray-400 cursor-not-allowed' : 'bg-indigo-600 hover:bg-indigo-500 text-white'}"
          >
            Sync {vault}
          </button>
        {/each}
      </div>
    {/if}
  </div>

  <!-- Sync History -->
  <div class="bg-gray-800 border border-gray-700 rounded-lg overflow-hidden">
    <div class="px-6 py-4 border-b border-gray-700">
      <h2 class="text-lg font-semibold text-white">Sync History (this session)</h2>
    </div>

    {#if $syncHistory.length === 0}
      <div class="px-6 py-12 text-center text-gray-500">
        <p>No syncs triggered yet this session.</p>
        <p class="text-sm mt-1">Use the buttons above or the Sync button in the navbar.</p>
      </div>
    {:else}
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-gray-400 text-xs uppercase border-b border-gray-700">
              <th class="px-4 py-3 text-left">Vault</th>
              <th class="px-4 py-3 text-left">Secrets Synced</th>
              <th class="px-4 py-3 text-left">Details</th>
            </tr>
          </thead>
          <tbody>
            {#each $syncHistory as entry}
              <tr class="border-b border-gray-700/50 hover:bg-gray-700/30 transition-colors">
                <td class="px-4 py-3 text-gray-300">{entry.vault}</td>
                <td class="px-4 py-3 text-gray-300">{entry.secrets_synced}</td>
                <td class="px-4 py-3 text-gray-400 text-xs">
                  {#if entry.secrets.length > 0}
                    {entry.secrets.map((s) => `${s.engine}/${s.path}`).join(', ')}
                  {:else}
                    No changes
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </div>
</div>
