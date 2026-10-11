<script lang="ts">
  // SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
  //
  // SPDX-License-Identifier: EUPL-1.2

  import StatusBadge from '#lib/components/StatusBadge.svelte';
  import SecretModal from '#lib/components/SecretModal.svelte';
  import ExpiryHorizon from '#lib/components/ExpiryHorizon.svelte';
  import { currentTheme } from '#lib/stores/theme.js';
  import { secrets, secretStats, criticalSecrets, secretsLoading, secretsError } from '#lib/stores/secrets.js';
  import { fetchAllVaultHealth } from '#lib/api/vaults.js';
  import { setSystemId, clearFilters } from '#lib/stores/filters.js';
  import { UNASSIGNED_SYSTEM } from '#lib/types/index.js';
  import type { Secret, VaultInstanceHealth } from '#lib/types/index.js';
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';

  let selectedSecret = $state<Secret | null>(null);
  let vaults = $state<VaultInstanceHealth[]>([]);
  let horizonSystem = $state('');

  interface SystemGroup {
    id: string;
    name: string;
    total: number;
    expired: number;
    warning: number;
    noTtl: number;
  }

  /** Status counts per system, unassigned secrets last. */
  const systemGroups = $derived.by(() => {
    const groups = new Map<string, SystemGroup>();
    for (const s of $secrets) {
      const id = s.system?.id ?? UNASSIGNED_SYSTEM;
      const group = groups.get(id) ?? { id, name: s.system?.name ?? 'Unassigned', total: 0, expired: 0, warning: 0, noTtl: 0 };
      group.total += 1;
      if (s.status === 'expired') group.expired += 1;
      if (s.status === 'warning') group.warning += 1;
      if (s.status === 'no_ttl') group.noTtl += 1;
      groups.set(id, group);
    }
    return Array.from(groups.values()).sort((a, b) =>
      a.id === UNASSIGNED_SYSTEM ? 1 : b.id === UNASSIGNED_SYSTEM ? -1 : a.name.localeCompare(b.name),
    );
  });

  const horizonSecrets = $derived(
    horizonSystem === ''
      ? $secrets
      : $secrets.filter((s) => (s.system?.id ?? UNASSIGNED_SYSTEM) === horizonSystem),
  );

  function showSystem(id: string) {
    clearFilters();
    setSystemId(id);
    goto('/secrets');
  }

  const coveragePct = $derived(
    $secretStats.total > 0
      ? Math.round((($secretStats.total - $secretStats.noTtl) / $secretStats.total) * 100)
      : 0,
  );

  onMount(async () => {
    try {
      vaults = await fetchAllVaultHealth();
    } catch {
      vaults = [];
    }
  });
</script>

<div class="space-y-5">
  <div class="flex items-end justify-between gap-4">
    <div>
      <h1 class="text-2xl font-bold text-white">Overview</h1>
      <p class="mt-1 text-sm text-gray-400">Credential health across your Vault infrastructure</p>
    </div>
    <a href="/secrets" class="px-4 py-2 text-sm rounded-lg bg-gray-700 hover:bg-gray-600 text-gray-200 transition-colors whitespace-nowrap">View all secrets</a>
  </div>

  {#if $secretsLoading}
    <div class="text-center text-gray-400 py-12">Loading secrets from backend…</div>
  {:else if $secretsError}
    <div class="px-4 py-3 bg-red-900/30 border border-red-700 rounded-lg text-red-300">
      <p class="font-medium">Failed to load secrets</p>
      <p class="text-sm mt-1">{$secretsError}</p>
    </div>
  {:else}
    <!-- Metric strip -->
    <div class="flex flex-wrap bg-gray-800 border border-gray-700 rounded-lg overflow-hidden">
      <div class="flex-1 min-w-[140px] p-4">
        <div class="text-3xl font-bold text-white">{$secretStats.total}</div>
        <div class="text-xs text-gray-400 mt-1">Tracked secrets</div>
      </div>
      <div class="w-px bg-gray-700"></div>
      <div class="flex-1 min-w-[140px] p-4">
        <div class="flex items-center gap-2 text-3xl font-bold text-green-400"><span class="w-2 h-2 rounded-full bg-green-400"></span>{$secretStats.ok}</div>
        <div class="text-xs text-gray-400 mt-1">Healthy</div>
      </div>
      <div class="w-px bg-gray-700"></div>
      <div class="flex-1 min-w-[140px] p-4">
        <div class="flex items-center gap-2 text-3xl font-bold text-yellow-400"><span class="w-2 h-2 rounded-full bg-yellow-400"></span>{$secretStats.warning}</div>
        <div class="text-xs text-gray-400 mt-1">Rotation due soon</div>
      </div>
      <div class="w-px bg-gray-700"></div>
      <div class="flex-1 min-w-[140px] p-4">
        <div class="flex items-center gap-2 text-3xl font-bold text-red-400"><span class="w-2 h-2 rounded-full bg-red-400"></span>{$secretStats.expired}</div>
        <div class="text-xs text-gray-400 mt-1">Overdue</div>
      </div>
      <div class="w-px bg-gray-700"></div>
      <div class="flex-1 min-w-[140px] p-4">
        <div class="flex items-center gap-2 text-3xl font-bold text-gray-500"><span class="w-2 h-2 rounded-full bg-gray-500"></span>{$secretStats.noTtl}</div>
        <div class="text-xs text-gray-400 mt-1">No rotation policy</div>
      </div>
    </div>

    <!-- Expiry horizon, optionally for one system -->
    {#if systemGroups.length > 1 || systemGroups[0]?.id !== UNASSIGNED_SYSTEM}
      <div class="flex justify-end">
        <select bind:value={horizonSystem} aria-label="System shown in the expiry horizon"
                class="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-gray-300 focus:outline-none focus:border-indigo-500">
          <option value="">All systems</option>
          {#each systemGroups as group (group.id)}<option value={group.id}>{group.name}</option>{/each}
        </select>
      </div>
    {/if}
    <ExpiryHorizon secrets={horizonSecrets} />

    <!-- Bottom row -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-5">
      <!-- Needs attention -->
      <div class="lg:col-span-2 bg-gray-800 border border-gray-700 rounded-lg overflow-hidden">
        <div class="flex items-center justify-between px-5 py-4 border-b border-gray-700">
          <h2 class="text-base font-semibold text-white">Needs attention</h2>
          <a href="/secrets" class="text-xs text-indigo-400 hover:text-indigo-300">View all →</a>
        </div>
        {#if $criticalSecrets.length === 0}
          <div class="px-6 py-10">
            <div class="mx-auto flex max-w-2xl flex-col items-center justify-center gap-5 text-center sm:flex-row sm:text-left">
              <img
                src={$currentTheme.mascot.src}
                alt={$currentTheme.mascot.alt}
                class="h-24 w-auto shrink-0 object-contain sm:h-60"
              />
              <div class="space-y-1">
                <p class="text-lg font-semibold text-green-300">Nothing expiring or overdue</p>
                <p class="text-sm text-gray-400">All tracked secrets are healthy</p>
              </div>
            </div>
          </div>
        {:else}
          <table class="w-full text-sm">
            <tbody>
              {#each $criticalSecrets as secret (secret.id)}
                <tr
                  class="border-b border-gray-700/50 last:border-0 hover:bg-gray-700/30 cursor-pointer transition-colors"
                  onclick={() => (selectedSecret = secret)}
                >
                  <td class="px-5 py-3">
                    <div class="font-mono text-gray-200">{secret.full_path}</div>
                    <div class="text-xs text-gray-500 mt-0.5">{secret.vault_name} · {secret.severity}</div>
                  </td>
                  <td class="px-3 py-3 text-right font-mono font-semibold {secret.status === 'expired' ? 'text-red-400' : 'text-yellow-400'}">
                    {secret.days_remaining != null ? `${secret.days_remaining}d` : '—'}
                  </td>
                  <td class="px-5 py-3 text-right"><StatusBadge status={secret.status} /></td>
                </tr>
              {/each}
            </tbody>
          </table>
        {/if}
      </div>

      <!-- Right column -->
      <div class="space-y-5">
        <div class="bg-gray-800 border border-gray-700 rounded-lg p-5 flex items-center gap-4">
          <div
            class="w-20 h-20 rounded-full flex items-center justify-center shrink-0"
            style="background: conic-gradient(rgb(129 140 248) {coveragePct}%, rgb(55 65 81) 0);"
          >
            <div class="w-[60px] h-[60px] rounded-full bg-gray-800 flex items-center justify-center text-lg font-bold text-white">{coveragePct}%</div>
          </div>
          <div>
            <div class="text-sm font-semibold text-white">Rotation coverage</div>
            <p class="text-xs text-gray-400 mt-1 leading-relaxed">
              {$secretStats.total - $secretStats.noTtl} of {$secretStats.total} secrets carry a rotation policy. Secrets with no TTL are invisible to alerting.
            </p>
          </div>
        </div>

        <div class="bg-gray-800 border border-gray-700 rounded-lg overflow-hidden">
          <div class="px-5 py-4 border-b border-gray-700"><h2 class="text-base font-semibold text-white">By system</h2></div>
          {#each systemGroups as group (group.id)}
            <button onclick={() => showSystem(group.id)}
                    class="w-full flex items-center gap-3 px-5 py-3 border-b border-gray-700/50 last:border-0 hover:bg-gray-700/30 text-left transition-colors">
              <span class="flex-1 text-sm {group.id === UNASSIGNED_SYSTEM ? 'text-gray-500' : 'text-gray-200'}">{group.name}</span>
              {#if group.expired}<span class="text-xs font-mono text-red-400" title="Overdue">{group.expired}</span>{/if}
              {#if group.warning}<span class="text-xs font-mono text-yellow-400" title="Rotation due soon">{group.warning}</span>{/if}
              {#if group.noTtl}<span class="text-xs font-mono text-gray-500" title="No rotation policy">{group.noTtl}</span>{/if}
              <span class="text-xs font-mono text-gray-400" title="Tracked secrets">{group.total}</span>
            </button>
          {:else}
            <div class="px-5 py-6 text-sm text-gray-500">No secrets tracked yet.</div>
          {/each}
        </div>

        <div class="bg-gray-800 border border-gray-700 rounded-lg overflow-hidden">
          <div class="px-5 py-4 border-b border-gray-700"><h2 class="text-base font-semibold text-white">Vault health</h2></div>
          {#if vaults.length === 0}
            <div class="px-5 py-6 text-sm text-gray-500">No vault status available.</div>
          {:else}
            {#each vaults as v}
              <div class="flex items-center gap-3 px-5 py-3 border-b border-gray-700/50 last:border-0">
                <span class="w-2 h-2 rounded-full shrink-0 {v.sealed ? 'bg-yellow-400' : v.healthy ? 'bg-green-400' : 'bg-red-400'}"></span>
                <div class="min-w-0">
                  <div class="text-sm text-gray-200 truncate">{v.name}</div>
                  <div class="text-xs text-gray-500">{v.version ?? 'unknown'}</div>
                </div>
                <div class="ml-auto text-xs {v.sealed ? 'text-yellow-400' : v.healthy ? 'text-green-400' : 'text-red-400'}">
                  {v.sealed ? 'Sealed' : v.healthy ? 'Healthy' : 'Error'}
                </div>
              </div>
            {/each}
          {/if}
        </div>
      </div>
    </div>
  {/if}
</div>

<SecretModal secret={selectedSecret} onClose={() => (selectedSecret = null)} />
