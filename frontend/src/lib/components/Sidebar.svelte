<!-- SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org> -->
<!--                                                               -->
<!-- SPDX-License-Identifier: EUPL-1.2                              -->

<script lang="ts">
  import { page } from '$app/state';

  let { open = true }: { open?: boolean } = $props();

  const links = [
    { href: '/', label: 'Dashboard', icon: '📊' },
    { href: '/secrets', label: 'Secrets', icon: '🔑' },
    { href: '/vaults', label: 'Vaults', icon: '🏦' },
    { href: '/sync', label: 'Sync', icon: '🔄' },
    { href: '/settings', label: 'Settings', icon: '⚙️' },
  ];
</script>

{#if open}
  <aside class="w-56 min-h-[calc(100vh-57px)] bg-gray-800 border-r border-gray-700 flex-shrink-0">
    <nav class="p-3 space-y-1">
      {#each links as link}
        <a
          href={link.href}
          class="flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors
                 {page.url.pathname === link.href
                   ? 'bg-indigo-600/20 text-indigo-400 font-medium'
                   : 'text-gray-400 hover:bg-gray-700 hover:text-gray-200'}"
        >
          <span>{link.icon}</span>
          <span>{link.label}</span>
        </a>
      {/each}
    </nav>
  </aside>
{/if}
