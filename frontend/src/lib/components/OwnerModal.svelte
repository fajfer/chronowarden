<!-- SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org> -->
<!--                                                               -->
<!-- SPDX-License-Identifier: EUPL-1.2                              -->

<script lang="ts">
  import Modal from './Modal.svelte';
  import type { Owner } from '#lib/types/index.js';

  let { owner = null, open = false, canEditIdentity = true, onClose, onSave }: {
    owner?: Owner | null;
    open?: boolean;
    /** Email and IdP group decide who acts for the owner, so only admins change them (ADR-026). */
    canEditIdentity?: boolean;
    onClose: () => void;
    onSave?: (data: { name: string; email: string; idp_group: string }) => void;
  } = $props();

  let name = $state('');
  let email = $state('');
  let idpGroup = $state('');

  $effect(() => {
    name = owner?.name ?? '';
    email = owner?.email ?? '';
    idpGroup = owner?.idp_group ?? '';
  });

  function handleSave() {
    onSave?.({ name, email, idp_group: idpGroup.trim() });
    onClose();
  }
</script>

{#if open}
  <Modal onClose={onClose} labelledby="owner-modal-title" width="max-w-md">
    <div class="flex items-center justify-between px-6 py-4 border-b border-gray-700">
      <h2 id="owner-modal-title" class="text-lg font-semibold text-white">{owner ? 'Edit Owner' : 'Create Owner'}</h2>
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
          disabled={!canEditIdentity}
          class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded-lg text-sm text-gray-200
                 focus:outline-none focus:border-indigo-500 disabled:opacity-50"
        />
        <p class="mt-1 text-xs text-gray-500">A user signing in with this email acts for the owner.</p>
      </div>
      <div>
        <label for="owner-idp-group" class="block text-xs text-gray-500 uppercase mb-1">IdP group (optional)</label>
        <input
          id="owner-idp-group"
          type="text"
          bind:value={idpGroup}
          disabled={!canEditIdentity}
          placeholder="e.g. team-payments"
          class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded-lg text-sm text-gray-200 placeholder-gray-600
                 focus:outline-none focus:border-indigo-500 disabled:opacity-50"
        />
        <p class="mt-1 text-xs text-gray-500">Members of this group act for the owner too (team owners).</p>
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
  </Modal>
{/if}
