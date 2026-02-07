<script lang="ts">
  // SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
  //
  // SPDX-License-Identifier: EUPL-1.2

  import '../app.css';
  import Navbar from '$lib/components/Navbar.svelte';
  import Sidebar from '$lib/components/Sidebar.svelte';
  import Toast from '$lib/components/Toast.svelte';
  import { isAuthenticated, initAuth } from '$lib/stores/auth';
  import { loadDemoSecrets } from '$lib/stores/secrets';
  import { goto } from '$app/navigation';
  import { page } from '$app/state';

  let { children } = $props();
  let sidebarOpen = $state(true);

  $effect(() => {
    initAuth();
    loadDemoSecrets();
  });

  $effect(() => {
    if (!$isAuthenticated && page.url.pathname !== '/login') {
      goto('/login');
    }
  });

  const isLoginPage = $derived(page.url.pathname === '/login');
</script>

{#if isLoginPage}
  {@render children()}
{:else if $isAuthenticated}
  <div class="min-h-screen bg-gray-900 text-gray-100">
    <Navbar onToggleSidebar={() => sidebarOpen = !sidebarOpen} />
    <div class="flex">
      <Sidebar open={sidebarOpen} />
      <main class="flex-1 p-6 lg:ml-0 overflow-x-hidden">
        {@render children()}
      </main>
    </div>
    <Toast />
  </div>
{/if}
