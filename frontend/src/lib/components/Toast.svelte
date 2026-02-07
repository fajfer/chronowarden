<!-- SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org> -->
<!--                                                               -->
<!-- SPDX-License-Identifier: EUPL-1.2                              -->

<script lang="ts">
  import { toasts } from '$lib/stores/sync';

  const typeColors: Record<string, string> = {
    success: 'bg-green-800 border-green-600 text-green-200',
    error: 'bg-red-800 border-red-600 text-red-200',
    info: 'bg-indigo-800 border-indigo-600 text-indigo-200',
  };
</script>

{#if $toasts.length > 0}
  <div class="fixed bottom-4 right-4 z-50 space-y-2">
    {#each $toasts as toast (toast.id)}
      <div class="px-4 py-3 rounded-lg border text-sm shadow-lg {typeColors[toast.type] ?? typeColors.info}">
        {toast.message}
      </div>
    {/each}
  </div>
{/if}
