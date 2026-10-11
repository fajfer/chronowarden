<!-- SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org> -->
<!--                                                               -->
<!-- SPDX-License-Identifier: EUPL-1.2                              -->

<script lang="ts">
  import type { Owner, System, SystemFormData } from '#lib/types/index.js';

  let { system = null, owners = [], open = false, onClose, onSave }: {
    system?: System | null;
    owners?: Owner[];
    open?: boolean;
    onClose: () => void;
    onSave?: (data: SystemFormData) => void;
  } = $props();

  let name = $state('');
  let description = $state('');
  let cmdbUri = $state('');
  let assetNumber = $state('');
  let ownerIds = $state<string[]>([]);

  $effect(() => {
    name = system?.name ?? '';
    description = system?.description ?? '';
    cmdbUri = system?.cmdb_uri ?? '';
    assetNumber = system?.asset_number ?? '';
    ownerIds = system?.owners.map((o) => o.id) ?? [];
  });

  function toggleOwner(id: string) {
    ownerIds = ownerIds.includes(id) ? ownerIds.filter((x) => x !== id) : [...ownerIds, id];
  }

  function handleSave() {
    onSave?.({
      name: name.trim(),
      description: description.trim(),
      cmdb_uri: cmdbUri.trim() || null,
      asset_number: assetNumber.trim() || null,
      owner_ids: ownerIds,
    });
    onClose();
  }

  const inputClass =
    'w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded-lg text-sm text-gray-200 focus:outline-none focus:border-indigo-500';
</script>

{#if open}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60" role="presentation" onclick={onClose}
       onkeydown={(e: KeyboardEvent) => e.key === 'Escape' && onClose()}>
    <div class="bg-gray-800 border border-gray-700 rounded-xl shadow-2xl w-full max-w-md mx-4 max-h-[90vh] overflow-y-auto"
         role="dialog" aria-modal="true" aria-labelledby="system-modal-title" tabindex="-1"
         onclick={(e: MouseEvent) => e.stopPropagation()}
         onkeydown={(e: KeyboardEvent) => e.key === 'Escape' && onClose()}>
      <div class="flex items-center justify-between px-6 py-4 border-b border-gray-700">
        <h2 id="system-modal-title" class="text-lg font-semibold text-white">{system ? 'Edit System' : 'Create System'}</h2>
        <button onclick={onClose} class="text-gray-400 hover:text-white text-xl">&times;</button>
      </div>

      <div class="px-6 py-4 space-y-4">
        <div>
          <label for="system-name" class="block text-xs text-gray-500 uppercase mb-1">Name</label>
          <input id="system-name" type="text" bind:value={name} class={inputClass} />
        </div>
        <div>
          <label for="system-description" class="block text-xs text-gray-500 uppercase mb-1">Description</label>
          <textarea id="system-description" rows="2" bind:value={description} class={inputClass}></textarea>
        </div>
        <div>
          <label for="system-cmdb" class="block text-xs text-gray-500 uppercase mb-1">CMDB link</label>
          <input id="system-cmdb" type="url" placeholder="https://cmdb.example.com/ci/…" bind:value={cmdbUri} class={inputClass} />
        </div>
        <div>
          <label for="system-asset" class="block text-xs text-gray-500 uppercase mb-1">Asset number</label>
          <input id="system-asset" type="text" bind:value={assetNumber} class={inputClass} />
        </div>
        <fieldset>
          <legend class="block text-xs text-gray-500 uppercase mb-1">Owners</legend>
          {#if owners.length === 0}
            <p class="text-sm text-gray-500">No owners yet: create them in the Owners tab.</p>
          {:else}
            <div class="space-y-1">
              {#each owners as owner (owner.id)}
                <label class="flex items-center gap-2 text-sm text-gray-200">
                  <input type="checkbox" checked={ownerIds.includes(owner.id)} onchange={() => toggleOwner(owner.id)} class="accent-indigo-500" />
                  {owner.name}
                </label>
              {/each}
            </div>
          {/if}
        </fieldset>
      </div>

      <div class="px-6 py-4 border-t border-gray-700 flex justify-end gap-2">
        <button onclick={handleSave} disabled={!name.trim()}
                class="px-4 py-2 text-sm rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition-colors disabled:opacity-50">
          Save
        </button>
        <button onclick={onClose}
                class="px-4 py-2 text-sm rounded-lg bg-gray-700 hover:bg-gray-600 text-gray-200 transition-colors">
          Cancel
        </button>
      </div>
    </div>
  </div>
{/if}
