<!-- SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org> -->
<!--                                                               -->
<!-- SPDX-License-Identifier: EUPL-1.2                              -->

<script lang="ts">
  import { syncVault } from '$lib/stores/sync';
  import { fetchVaultInstances } from '$lib/api/vaults';
  import { loadSecrets } from '$lib/stores/secrets';

  let vaultNames = $state<string[]>([]);
  let dropdownOpen = $state(false);
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
    dropdownOpen = false;
    await syncVault(vault);
    await loadSecrets();
    syncing = false;
  }

  async function handleSyncAll() {
    syncing = true;
    dropdownOpen = false;
    for (const v of vaultNames) {
      await syncVault(v);
    }
    await loadSecrets();
    syncing = false;
  }

  $effect(() => {
    loadVaults();
  });
</script>

<div class="relative">
  <button
    onclick={() => dropdownOpen = !dropdownOpen}
    disabled={syncing}
    class="flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg transition-colors
           {syncing ? 'bg-gray-600 text-gray-400 cursor-not-allowed' : 'bg-indigo-600 hover:bg-indigo-500 text-white'}"
  >
    <span>Sync</span>
  </button>

  {#if dropdownOpen && !syncing}
    <div class="absolute right-0 top-full mt-1 w-44 bg-gray-800 border border-gray-700 rounded-lg shadow-xl z-50">
      {#if vaultNames.length === 0}
        <p class="px-4 py-2 text-sm text-gray-500">No vaults configured</p>
      {:else}
        {#each vaultNames as vault}
          <button
            onclick={() => handleSync(vault)}
            class="w-full text-left px-4 py-2 text-sm text-gray-300 hover:bg-gray-700 transition-colors"
          >
            {vault}
          </button>
        {/each}
        <div class="border-t border-gray-700">
          <button
            onclick={handleSyncAll}
            class="w-full text-left px-4 py-2 text-sm text-indigo-400 hover:bg-gray-700 transition-colors font-medium"
          >
            Sync All
          </button>
        </div>
      {/if}
    </div>
  {/if}
</div>
