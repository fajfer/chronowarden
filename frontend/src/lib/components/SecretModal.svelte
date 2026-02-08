<!-- SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org> -->
<!--                                                               -->
<!-- SPDX-License-Identifier: EUPL-1.2                              -->

<script lang="ts">
  import type { Secret } from '$lib/types';
  import StatusBadge from './StatusBadge.svelte';
  import { formatDate } from '$lib/utils/dateFormat';

  let { secret, onClose }: {
    secret: Secret | null;
    onClose: () => void;
  } = $props();
</script>

{#if secret}
  <!-- svelte-ignore a11y_no_static_element_interactions a11y_click_events_have_key_events -->
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onclick={onClose}>
    <!-- svelte-ignore a11y_no_static_element_interactions a11y_click_events_have_key_events -->
    <div class="bg-gray-800 border border-gray-700 rounded-xl shadow-2xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto"
         onclick={(e: MouseEvent) => e.stopPropagation()}>
      <div class="flex items-center justify-between px-6 py-4 border-b border-gray-700">
        <h2 class="text-lg font-semibold text-white">{secret.full_path}</h2>
        <button onclick={onClose} class="text-gray-400 hover:text-white text-xl">&times;</button>
      </div>

      <div class="px-6 py-4 space-y-4 text-sm">
        <div class="flex gap-2">
          <StatusBadge status={secret.status} />
          <span class="inline-flex items-center px-2 py-0.5 rounded border text-xs font-medium text-blue-400 border-blue-500">
            {secret.severity}
          </span>
          {#if !secret.enabled}
            <span class="inline-flex items-center px-2 py-0.5 rounded border text-xs font-medium text-gray-400 border-gray-500">
              Disabled
            </span>
          {/if}
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div>
            <p class="text-gray-500 text-xs">Vault</p>
            <p class="text-gray-200">{secret.vault_name}</p>
          </div>
          <div>
            <p class="text-gray-500 text-xs">Engine</p>
            <p class="text-gray-200">{secret.engine_id}</p>
          </div>
          <div>
            <p class="text-gray-500 text-xs">Secret Path</p>
            <p class="text-gray-200">{secret.secret_path}</p>
          </div>
          <div>
            <p class="text-gray-500 text-xs">Severity</p>
            <p class="text-gray-200">{secret.severity}</p>
          </div>
          <div>
            <p class="text-gray-500 text-xs">TTL Date</p>
            <p class="text-gray-200">{formatDate(secret.ttl_date)}</p>
          </div>
          <div>
            <p class="text-gray-500 text-xs">Days Remaining</p>
            <p class="text-gray-200">{secret.days_remaining ?? '—'}</p>
          </div>
          <div>
            <p class="text-gray-500 text-xs">Rotation Period</p>
            <p class="text-gray-200">{secret.rotation_period_days} days</p>
          </div>
          <div>
            <p class="text-gray-500 text-xs">Last Synced</p>
            <p class="text-gray-200">{formatDate(secret.last_synced)}</p>
          </div>
        </div>
      </div>

      <div class="px-6 py-4 border-t border-gray-700 flex justify-end">
        <button
          onclick={onClose}
          class="px-4 py-2 text-sm rounded-lg bg-gray-700 hover:bg-gray-600 text-gray-200 transition-colors"
        >
          Close
        </button>
      </div>
    </div>
  </div>
{/if}
