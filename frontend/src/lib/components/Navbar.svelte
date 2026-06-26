<!-- SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org> -->
<!--                                                               -->
<!-- SPDX-License-Identifier: EUPL-1.2                              -->

<script lang="ts">
  import { currentUser, logout } from '$lib/stores/auth';
  import { currentTheme, availableThemes, setTheme } from '$lib/stores/theme';
  import { fetchVaultInstances, fetchApiInfo } from '$lib/api/vaults';
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import SyncButton from './SyncButton.svelte';

  let { onToggleSidebar }: {
    onToggleSidebar?: () => void;
  } = $props();

  let vaultCount = $state<number | null>(null);
  let version = $state<string | null>(null);

  onMount(async () => {
    try {
      const { instances } = await fetchVaultInstances();
      vaultCount = instances.length;
    } catch {
      vaultCount = null;
    }
    try {
      version = (await fetchApiInfo()).version;
    } catch {
      version = null;
    }
  });

  function handleLogout() {
    logout();
    goto('/login');
  }
</script>

<nav class="bg-gray-900 border-b border-gray-700 px-4 py-2.5">
  <div class="flex items-center justify-between gap-4">
    <div class="flex items-center gap-3 min-w-0">
      {#if onToggleSidebar}
        <button onclick={onToggleSidebar} class="text-gray-400 hover:text-white lg:hidden" aria-label="Toggle sidebar">
          ☰
        </button>
      {/if}
      <a href="/" class="flex items-center gap-2 shrink-0">
        <img src={$currentTheme.logo.src} alt={$currentTheme.logo.alt} class="h-9 w-auto object-contain" />
        <span class="sr-only">Chronowarden</span>
      </a>
      {#if version}
        <span class="hidden sm:inline-block font-mono text-[11px] text-gray-500 border border-gray-700 rounded px-1.5 py-0.5">v{version}</span>
      {/if}
    </div>

    <div class="flex items-center gap-3">
      {#if vaultCount !== null}
        <div class="hidden md:flex items-center gap-2 text-xs text-gray-400">
          <span class="w-1.5 h-1.5 rounded-full bg-green-400 ring-4 ring-green-400/20"></span>
          {vaultCount} {vaultCount === 1 ? 'vault' : 'vaults'} connected
        </div>
      {/if}

      <div class="hidden sm:flex gap-0.5 bg-gray-800 border border-gray-700 rounded-lg p-0.5">
        {#each availableThemes as theme}
          <button
            onclick={() => setTheme(theme.id)}
            class="px-2.5 py-1 rounded-md text-xs transition-colors
                   {$currentTheme.id === theme.id ? 'bg-gray-700 text-white' : 'text-gray-400 hover:text-gray-200'}"
          >
            {theme.label}
          </button>
        {/each}
      </div>

      <SyncButton />

      <span class="hidden lg:inline text-sm text-gray-400">{$currentUser?.name ?? ''}</span>
      <button
        onclick={handleLogout}
        class="px-3 py-1.5 text-sm rounded-lg bg-gray-700 hover:bg-gray-600 text-gray-300 transition-colors"
      >
        Logout
      </button>
    </div>
  </div>
</nav>
