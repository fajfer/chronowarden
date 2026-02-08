<!-- SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org> -->
<!--                                                               -->
<!-- SPDX-License-Identifier: EUPL-1.2                              -->

<script lang="ts">
  import type { Secret } from '$lib/types';
  import StatusBadge from './StatusBadge.svelte';
  import { formatDate } from '$lib/utils/dateFormat';
  import { getDaysUntilExpiry } from '$lib/utils/dateFormat';
  import { getStatusFromDays } from '$lib/utils/statusColor';

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
        <h2 class="text-lg font-semibold text-white">{secret.name}</h2>
        <button onclick={onClose} class="text-gray-400 hover:text-white text-xl">&times;</button>
      </div>

      <div class="px-6 py-4 space-y-4 text-sm">
        {#if true}
          {@const days = getDaysUntilExpiry(secret.expiry_date)}
          <div class="flex gap-2">
            <StatusBadge status={getStatusFromDays(days)} />
          <span class="inline-flex items-center px-2 py-0.5 rounded border text-xs font-medium text-blue-400 border-blue-500">
            {secret.engine_type}
          </span>
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div>
            <p class="text-gray-500 text-xs">ID</p>
            <p class="text-gray-200">{secret.id}</p>
          </div>
          <div>
            <p class="text-gray-500 text-xs">Engine Type</p>
            <p class="text-gray-200">{secret.engine_type}</p>
          </div>
          <div>
            <p class="text-gray-500 text-xs">Public</p>
            <p class="text-gray-200">{secret.is_public ? 'Yes' : 'No'}</p>
          </div>
          <div>
            <p class="text-gray-500 text-xs">Owner ID</p>
            <p class="text-gray-200">{secret.owner_id}</p>
          </div>
          <div>
            <p class="text-gray-500 text-xs">Expiry Date</p>
            <p class="text-gray-200">{formatDate(secret.expiry_date)}</p>
          </div>
          <div>
            <p class="text-gray-500 text-xs">Days Until Expiry</p>
            <p class="text-gray-200">{days ?? '—'}</p>
          </div>
          <div>
            <p class="text-gray-500 text-xs">Created</p>
            <p class="text-gray-200">{formatDate(secret.created_at)}</p>
          </div>
          <div>
            <p class="text-gray-500 text-xs">Alert Threshold</p>
            <p class="text-gray-200">{secret.expiry_time_alert} days</p>
          </div>
          <div>
            <p class="text-gray-500 text-xs">Reminder Interval</p>
            <p class="text-gray-200">{secret.expiry_time_interval} days</p>
          </div>
          <div>
            <p class="text-gray-500 text-xs">Backend ID</p>
            <p class="text-gray-200">{secret.backend_id}</p>
          </div>
        </div>

        {#if secret.description}
          <div>
            <p class="text-gray-500 text-xs">Description</p>
            <p class="text-gray-200">{secret.description}</p>
          </div>
        {/if}
        {/if}
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
