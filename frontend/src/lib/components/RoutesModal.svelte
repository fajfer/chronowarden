<!-- SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org> -->
<!--                                                               -->
<!-- SPDX-License-Identifier: EUPL-1.2                              -->

<script lang="ts">
  import Modal from './Modal.svelte';
  import {
    addNotificationRoute, deleteNotificationRoute, disableRouteSigning, enableRouteSigning, testNotificationRoute,
  } from '#lib/api/owners.js';
  import { addToast } from '#lib/stores/sync.js';
  import type { Owner } from '#lib/types/index.js';

  /** Webhook routes of one owner: add, delete, sign and test (ADR-025). */
  let { owner, onClose, onChange }: {
    owner: Owner | null;
    onClose: () => void;
    onChange: () => Promise<void>;
  } = $props();

  let address = $state('');
  let busy = $state(false);
  let shownSecret = $state<string | null>(null);

  async function run(action: () => Promise<unknown>, done?: string) {
    busy = true;
    try {
      await action();
      if (done) addToast(done, 'success');
      await onChange();
    } catch (err) {
      addToast(err instanceof Error ? err.message : 'Request failed', 'error');
    } finally {
      busy = false;
    }
  }

  function add() {
    if (!owner || !address.trim()) return;
    const id = owner.id;
    run(async () => {
      await addNotificationRoute(id, { type: 'webhook', address: address.trim() });
      address = '';
    }, 'Webhook route added');
  }

  function sign(routeId: string) {
    if (!owner) return;
    const id = owner.id;
    run(async () => {
      shownSecret = (await enableRouteSigning(id, routeId)).secret;
    });
  }

  async function test(routeId: string) {
    if (!owner) return;
    try {
      const result = await testNotificationRoute(owner.id, routeId);
      addToast(result.message, result.success ? 'success' : 'error');
    } catch (err) {
      addToast(err instanceof Error ? err.message : 'Test failed', 'error');
    }
  }

  function close() {
    shownSecret = null;
    onClose();
  }

  const inputClass =
    'bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-indigo-500';
</script>

{#if owner}
  <Modal onClose={close} labelledby="routes-modal-title" width="max-w-2xl">
    <div class="flex items-center justify-between px-6 py-4 border-b border-gray-700">
      <h2 id="routes-modal-title" class="text-lg font-semibold text-white">Webhook routes: {owner.name}</h2>
      <button onclick={close} class="text-gray-400 hover:text-white text-xl" aria-label="Close">&times;</button>
    </div>

    <div class="space-y-4 px-6 py-4">
      <p class="text-xs text-gray-400">
        Alerts about secrets {owner.name} owns are POSTed to these URLs as Alertmanager-compatible JSON. Addresses are
        shown up to the host only, since webhook URLs usually carry a token.
      </p>

      {#if shownSecret}
        <div class="space-y-2 rounded-lg border border-amber-600 bg-amber-900/20 p-3 text-sm">
          <p class="text-amber-200">Signing secret: copy it into the receiver now. It won't be shown again.</p>
          <input readonly class="{inputClass} w-full font-mono text-xs" value={shownSecret}
                 aria-label="Signing secret" onfocus={(e) => (e.currentTarget as HTMLInputElement).select()} />
          <button onclick={() => (shownSecret = null)} class="text-xs text-amber-300 hover:text-amber-100">I've stored it</button>
        </div>
      {/if}

      {#if owner.notification_routes.length === 0}
        <p class="text-sm text-gray-500">No routes yet: alerts for this owner go to the default routes in config.yaml.</p>
      {:else}
        <ul class="divide-y divide-gray-700 rounded-lg border border-gray-700">
          {#each owner.notification_routes as route (route.id)}
            <li class="flex flex-wrap items-center gap-2 px-3 py-2 text-sm">
              <span class="font-mono text-gray-300">{route.address}</span>
              {#if route.signed}<span class="rounded bg-green-900/40 px-1.5 py-0.5 text-[10px] uppercase text-green-300">signed</span>{/if}
              <span class="ml-auto flex gap-2">
                <button disabled={busy} onclick={() => test(route.id)} class="rounded bg-gray-700 px-2 py-1 text-xs text-gray-200 hover:bg-gray-600">Send test</button>
                {#if route.signed}
                  <button disabled={busy} onclick={() => owner && run(() => disableRouteSigning(owner.id, route.id), 'Signing turned off')}
                          class="rounded bg-gray-700 px-2 py-1 text-xs text-gray-200 hover:bg-gray-600">Stop signing</button>
                  <button disabled={busy} onclick={() => sign(route.id)} class="rounded bg-gray-700 px-2 py-1 text-xs text-gray-200 hover:bg-gray-600">New secret</button>
                {:else}
                  <button disabled={busy} onclick={() => sign(route.id)} class="rounded bg-gray-700 px-2 py-1 text-xs text-gray-200 hover:bg-gray-600">Sign</button>
                {/if}
                <button disabled={busy} onclick={() => owner && run(() => deleteNotificationRoute(owner.id, route.id), 'Webhook route deleted')}
                        class="rounded bg-red-900/50 px-2 py-1 text-xs text-red-300 hover:bg-red-800/50">Delete</button>
              </span>
            </li>
          {/each}
        </ul>
      {/if}

      <form class="flex gap-2" onsubmit={(e) => { e.preventDefault(); add(); }}>
        <input class="{inputClass} flex-1" type="url" placeholder="https://hooks.example.com/…" bind:value={address}
               aria-label="Webhook URL" />
        <button type="submit" disabled={busy || !address.trim()}
                class="rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-500 disabled:opacity-50">Add route</button>
      </form>
    </div>
  </Modal>
{/if}
