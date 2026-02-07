<script lang="ts">
  // SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
  //
  // SPDX-License-Identifier: EUPL-1.2

  import StatsCard from '$lib/components/StatsCard.svelte';
  import StatusBadge from '$lib/components/StatusBadge.svelte';
  import SeverityBadge from '$lib/components/SeverityBadge.svelte';
  import SecretModal from '$lib/components/SecretModal.svelte';
  import { secretStats, criticalSecrets } from '$lib/stores/secrets';
  import { formatDate } from '$lib/utils/dateFormat';
  import { getStatusFromDays } from '$lib/utils/statusColor';
  import type { Secret } from '$lib/types';

  let selectedSecret = $state<Secret | null>(null);
</script>

<div class="space-y-6">
  <div class="flex items-center justify-between">
    <h1 class="text-2xl font-bold text-white">Dashboard</h1>
    <div class="flex gap-3">
      <a href="/secrets" class="px-4 py-2 text-sm rounded-lg bg-gray-700 hover:bg-gray-600 text-gray-200 transition-colors">View All Secrets</a>
    </div>
  </div>

  <!-- Stats Cards -->
  <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
    <StatsCard title="Total Secrets" value={$secretStats.total} color="text-white" />
    <StatsCard title="Healthy" value={$secretStats.healthy} color="text-green-400" bgColor="bg-green-900/20" />
    <StatsCard title="Warning" value={$secretStats.warning} color="text-yellow-400" bgColor="bg-yellow-900/20" />
    <StatsCard title="Critical" value={$secretStats.critical} color="text-red-400" bgColor="bg-red-900/20" />
    <StatsCard title="Expired" value={$secretStats.expired} color="text-gray-500" bgColor="bg-gray-800" />
  </div>

  <!-- Critical Secrets Table -->
  <div class="bg-gray-800 border border-gray-700 rounded-lg overflow-hidden">
    <div class="px-6 py-4 border-b border-gray-700">
      <h2 class="text-lg font-semibold text-white">Critical & Expired Secrets</h2>
    </div>

    {#if $criticalSecrets.length === 0}
      <div class="px-6 py-12 text-center text-gray-500">
        <p class="text-lg">🎉 No critical or expired secrets</p>
        <p class="text-sm mt-1">All secrets are healthy</p>
      </div>
    {:else}
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-gray-400 text-xs uppercase border-b border-gray-700">
              <th class="px-4 py-3 text-left">Name</th>
              <th class="px-4 py-3 text-left">Vault</th>
              <th class="px-4 py-3 text-left">Owner</th>
              <th class="px-4 py-3 text-left">Severity</th>
              <th class="px-4 py-3 text-left">Expiry</th>
              <th class="px-4 py-3 text-left">Days</th>
              <th class="px-4 py-3 text-left">Status</th>
            </tr>
          </thead>
          <tbody>
            {#each $criticalSecrets as secret}
              <tr
                class="border-b border-gray-700/50 hover:bg-gray-700/30 cursor-pointer transition-colors"
                onclick={() => selectedSecret = secret}
              >
                <td class="px-4 py-3 font-medium text-gray-200">{secret.name}</td>
                <td class="px-4 py-3 text-gray-400">{secret.vault}</td>
                <td class="px-4 py-3 text-gray-400">{secret.owner_name ?? '—'}</td>
                <td class="px-4 py-3"><SeverityBadge severity={secret.severity} /></td>
                <td class="px-4 py-3 text-gray-400">{formatDate(secret.expiry_date)}</td>
                <td class="px-4 py-3 text-gray-200">{secret.days_until_expiry ?? '—'}</td>
                <td class="px-4 py-3"><StatusBadge status={getStatusFromDays(secret.days_until_expiry)} /></td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </div>
</div>

<SecretModal secret={selectedSecret} onClose={() => selectedSecret = null} />
