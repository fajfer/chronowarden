<!-- SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org> -->
<!--                                                               -->
<!-- SPDX-License-Identifier: EUPL-1.2                              -->

<script lang="ts">
  import { canTriggerSync } from '$lib/stores/auth';
  import { addToast, setSyncStatus } from '$lib/stores/sync';

  let { vaults = ['production', 'staging', 'dev'] }: {
    vaults?: string[];
  } = $props();

  let dropdownOpen = $state(false);
  let syncing = $state(false);

  async function handleSync(vault: string) {
    syncing = true;
    setSyncStatus(vault, true);
    dropdownOpen = false;
    addToast(`Syncing ${vault}…`, 'info');

    // Simulate sync delay
    await new Promise((r) => setTimeout(r, 2000));

    setSyncStatus(vault, false);
    addToast(`Sync completed for ${vault}`, 'success');
    syncing = false;
  }
</script>

{#if $canTriggerSync}
  <div class="relative">
    <button
      onclick={() => dropdownOpen = !dropdownOpen}
      disabled={syncing}
      class="flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg transition-colors
             {syncing ? 'bg-gray-600 text-gray-400 cursor-not-allowed' : 'bg-indigo-600 hover:bg-indigo-500 text-white'}"
    >
      <span>{syncing ? '⏳' : '🔄'}</span>
      <span>Sync</span>
    </button>

    {#if dropdownOpen && !syncing}
      <div class="absolute right-0 top-full mt-1 w-44 bg-gray-800 border border-gray-700 rounded-lg shadow-xl z-50">
        {#each vaults as vault}
          <button
            onclick={() => handleSync(vault)}
            class="w-full text-left px-4 py-2 text-sm text-gray-300 hover:bg-gray-700 transition-colors"
          >
            {vault}
          </button>
        {/each}
        <div class="border-t border-gray-700">
          <button
            onclick={() => { vaults.forEach(v => handleSync(v)); }}
            class="w-full text-left px-4 py-2 text-sm text-indigo-400 hover:bg-gray-700 transition-colors font-medium"
          >
            Sync All
          </button>
        </div>
      </div>
    {/if}
  </div>
{/if}
