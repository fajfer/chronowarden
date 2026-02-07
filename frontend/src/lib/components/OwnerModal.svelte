<!-- SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org> -->
<!--                                                               -->
<!-- SPDX-License-Identifier: EUPL-1.2                              -->

<script lang="ts">
  import type { Owner, NotificationRoute } from '$lib/types';

  let { owner = null, onClose, onSave }: {
    owner?: Owner | null;
    onClose: () => void;
    onSave?: (data: Partial<Owner>) => void;
  } = $props();

  let name = $state(owner?.name ?? '');
  let email = $state(owner?.email ?? '');

  $effect(() => {
    name = owner?.name ?? '';
    email = owner?.email ?? '';
  });

  function handleSave() {
    onSave?.({ name, email });
    onClose();
  }
</script>

{#if owner !== null || owner === undefined}
  <!-- Only render if explicitly opened -->
{/if}

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 hidden" onclick={onClose}>
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="bg-gray-800 border border-gray-700 rounded-xl shadow-2xl w-full max-w-md mx-4"
       onclick={(e: MouseEvent) => e.stopPropagation()}>
    <div class="flex items-center justify-between px-6 py-4 border-b border-gray-700">
      <h2 class="text-lg font-semibold text-white">{owner ? 'Edit Owner' : 'Create Owner'}</h2>
      <button onclick={onClose} class="text-gray-400 hover:text-white text-xl">&times;</button>
    </div>

    <div class="px-6 py-4 space-y-4">
      <div>
        <label for="owner-name" class="block text-xs text-gray-500 uppercase mb-1">Name</label>
        <input
          id="owner-name"
          type="text"
          bind:value={name}
          class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded-lg text-sm text-gray-200
                 focus:outline-none focus:border-indigo-500"
        />
      </div>
      <div>
        <label for="owner-email" class="block text-xs text-gray-500 uppercase mb-1">Email</label>
        <input
          id="owner-email"
          type="email"
          bind:value={email}
          class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded-lg text-sm text-gray-200
                 focus:outline-none focus:border-indigo-500"
        />
      </div>
    </div>

    <div class="px-6 py-4 border-t border-gray-700 flex justify-end gap-2">
      <button onclick={handleSave}
              class="px-4 py-2 text-sm rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition-colors">
        Save
      </button>
      <button onclick={onClose}
              class="px-4 py-2 text-sm rounded-lg bg-gray-700 hover:bg-gray-600 text-gray-200 transition-colors">
        Cancel
      </button>
    </div>
  </div>
</div>
