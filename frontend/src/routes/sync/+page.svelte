<script lang="ts">
  // SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
  //
  // SPDX-License-Identifier: EUPL-1.2

  import { syncHistory } from '$lib/stores/sync';
  import { formatDate } from '$lib/utils/dateFormat';

  import type { SyncResult } from '$lib/types';

  // Demo history data
  const demoHistory: SyncResult[] = [
    { vault: 'production', secrets_synced: 45, status: 'success', duration: 3200, timestamp: new Date(Date.now() - 3600000).toISOString() },
    { vault: 'staging', secrets_synced: 22, status: 'success', duration: 1800, timestamp: new Date(Date.now() - 7200000).toISOString() },
    { vault: 'dev', secrets_synced: 0, status: 'error', error: 'Connection timeout', duration: 5000, timestamp: new Date(Date.now() - 10800000).toISOString() },
    { vault: 'production', secrets_synced: 44, status: 'success', duration: 3100, timestamp: new Date(Date.now() - 86400000).toISOString() },
  ];

  const history = $derived($syncHistory.length > 0 ? $syncHistory : demoHistory);
</script>

<div class="space-y-6">
  <h1 class="text-2xl font-bold text-white">Sync History</h1>

  <div class="bg-gray-800 border border-gray-700 rounded-lg overflow-hidden">
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="text-gray-400 text-xs uppercase border-b border-gray-700">
            <th class="px-4 py-3 text-left">Timestamp</th>
            <th class="px-4 py-3 text-left">Vault</th>
            <th class="px-4 py-3 text-left">Secrets Scanned</th>
            <th class="px-4 py-3 text-left">Status</th>
            <th class="px-4 py-3 text-left">Duration</th>
          </tr>
        </thead>
        <tbody>
          {#each history as entry}
            <tr class="border-b border-gray-700/50 hover:bg-gray-700/30 transition-colors">
              <td class="px-4 py-3 text-gray-300">{formatDate(entry.timestamp)}</td>
              <td class="px-4 py-3 text-gray-300">{entry.vault}</td>
              <td class="px-4 py-3 text-gray-300">{entry.secrets_synced}</td>
              <td class="px-4 py-3">
                <span class="px-2 py-0.5 rounded-full text-xs font-medium {entry.status === 'success' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}">
                  {entry.status}
                </span>
              </td>
              <td class="px-4 py-3 text-gray-400">{entry.duration ? `${(entry.duration / 1000).toFixed(1)}s` : '—'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </div>
</div>
