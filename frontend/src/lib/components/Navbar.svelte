<!-- SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org> -->
<!--                                                               -->
<!-- SPDX-License-Identifier: EUPL-1.2                              -->

<script lang="ts">
  import { currentUser, logout } from '$lib/stores/auth';
  import { currentTheme } from '$lib/stores/theme';
  import { goto } from '$app/navigation';
  import SyncButton from './SyncButton.svelte';

  let { onToggleSidebar }: {
    onToggleSidebar?: () => void;
  } = $props();

  function handleLogout() {
    logout();
    goto('/login');
  }
</script>

<nav class="bg-gray-800 border-b border-gray-700 px-4 py-3">
  <div class="flex items-center justify-between">
    <div class="flex items-center gap-3">
      {#if onToggleSidebar}
        <button onclick={onToggleSidebar} class="text-gray-400 hover:text-white lg:hidden">
          ☰
        </button>
      {/if}
      <a href="/" class="flex items-center gap-2">
        <img src={$currentTheme.logo.src} alt={$currentTheme.logo.alt} class="h-12 w-auto object-contain" />
        <span class="sr-only">Chronowarden</span>
      </a>
    </div>

    <div class="flex items-center gap-3">
      <SyncButton />
      <span class="text-sm text-gray-400">{$currentUser?.name ?? ''}</span>
      <button
        onclick={handleLogout}
        class="px-3 py-1.5 text-sm rounded-lg bg-gray-700 hover:bg-gray-600 text-gray-300 transition-colors"
      >
        Logout
      </button>
    </div>
  </div>
</nav>
