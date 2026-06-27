<!-- SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org> -->
<!--                                                               -->
<!-- SPDX-License-Identifier: EUPL-1.2                              -->

<script lang="ts">
  import { page } from '$app/state';
  import { onMount } from 'svelte';
  import { currentTheme } from '$lib/stores/theme';
  import { secretStats } from '$lib/stores/secrets';
  import { fetchVaultInstances } from '$lib/api/vaults';

  let { open = true }: { open?: boolean } = $props();

  let vaultCount = $state<number | null>(null);

  onMount(async () => {
    try {
      vaultCount = (await fetchVaultInstances()).instances.length;
    } catch {
      vaultCount = null;
    }
  });

  type Link = { href: string; label: string; badge?: () => string | number | null };

  const sections: { title: string; links: Link[] }[] = [
    {
      title: 'Monitor',
      links: [
        { href: '/', label: 'Dashboard' },
        { href: '/secrets', label: 'Secrets', badge: () => $secretStats.total || null },
        { href: '/vaults', label: 'Vaults', badge: () => vaultCount },
      ],
    },
    { title: 'Operate', links: [{ href: '/sync', label: 'Sync history' }] },
    { title: 'Configure', links: [{ href: '/settings', label: 'Settings' }] },
  ];
</script>

{#if open}
  <aside class="w-56 min-h-[calc(100vh-57px)] bg-gray-900 border-r border-gray-700 flex-shrink-0 flex flex-col">
    <nav class="p-3 flex-1">
      {#each sections as section}
        <p class="px-2 pt-3 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-gray-600">{section.title}</p>
        {#each section.links as link}
          {@const active = page.url.pathname === link.href}
          <a
            href={link.href}
            class="flex items-center gap-3 px-3 py-2 rounded-lg text-sm border-l-2 transition-colors
                   {active
                     ? 'bg-indigo-600/15 text-indigo-300 font-medium border-indigo-400'
                     : 'text-gray-400 border-transparent hover:bg-gray-800 hover:text-gray-200'}"
          >
            <span class="w-3.5 h-3.5 rounded border-[1.5px] border-current opacity-70"></span>
            <span class="flex-1">{link.label}</span>
            {#if link.badge}
              {@const value = link.badge()}
              {#if value != null}
                <span class="font-mono text-[11px] text-gray-500">{value}</span>
              {/if}
            {/if}
          </a>
        {/each}
      {/each}
    </nav>

    <div class="m-3 flex items-center gap-3 rounded-lg border border-gray-700 bg-gray-800/60 p-3">
      <img src={$currentTheme.mascot.src} alt={$currentTheme.mascot.alt} class="h-16 w-16 object-contain shrink-0" />
      <div class="min-w-0">
        <div class="text-xs font-medium text-gray-300">Visit our website</div>
        <div class="text-[10px] text-gray-500">PCI-DSS 4.0 · DORA</div>
      </div>
    </div>
  </aside>
{/if}
