<!-- SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org> -->
<!--                                                               -->
<!-- SPDX-License-Identifier: EUPL-1.2                              -->

<script lang="ts">
  import type { Secret } from '$lib/types';
  import StatusBadge from './StatusBadge.svelte';
  import SeverityBadge from './SeverityBadge.svelte';
  import { formatDate } from '$lib/utils/dateFormat';
  import { getStatusFromDays } from '$lib/utils/statusColor';
  import { canEditSecrets } from '$lib/stores/auth';

  let { secret, onClose, onSave }: {
    secret: Secret | null;
    onClose: () => void;
    onSave?: (id: number, data: Partial<Secret>) => void;
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
        <div class="flex gap-2">
          <StatusBadge status={getStatusFromDays(secret.days_until_expiry)} />
          <SeverityBadge severity={secret.severity} />
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div>
            <p class="text-gray-500 text-xs">Path</p>
            <p class="text-gray-200">{secret.path}</p>
          </div>
          <div>
            <p class="text-gray-500 text-xs">Engine</p>
            <p class="text-gray-200">{secret.engine} ({secret.engine_type})</p>
          </div>
          <div>
            <p class="text-gray-500 text-xs">Vault</p>
            <p class="text-gray-200">{secret.vault}</p>
          </div>
          <div>
            <p class="text-gray-500 text-xs">Owner</p>
            <p class="text-gray-200">{secret.owner_name ?? '—'}</p>
          </div>
          <div>
            <p class="text-gray-500 text-xs">Expiry Date</p>
            <p class="text-gray-200">{formatDate(secret.expiry_date)}</p>
          </div>
          <div>
            <p class="text-gray-500 text-xs">Days Until Expiry</p>
            <p class="text-gray-200">{secret.days_until_expiry ?? '—'}</p>
          </div>
          <div>
            <p class="text-gray-500 text-xs">Created</p>
            <p class="text-gray-200">{formatDate(secret.created_at)}</p>
          </div>
          <div>
            <p class="text-gray-500 text-xs">Last Updated</p>
            <p class="text-gray-200">{formatDate(secret.last_updated)}</p>
          </div>
          <div>
            <p class="text-gray-500 text-xs">Enabled</p>
            <p class="text-gray-200">{secret.enabled ? 'Yes' : 'No'}</p>
          </div>
        </div>
      </div>

      <div class="px-6 py-4 border-t border-gray-700 flex justify-end gap-2">
        {#if onSave && $canEditSecrets}
          <button
            onclick={() => onSave?.(secret!.id, {})}
            class="px-4 py-2 text-sm rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition-colors"
          >
            Save
          </button>
        {/if}
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
