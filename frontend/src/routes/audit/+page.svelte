<script lang="ts">
  // SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
  //
  // SPDX-License-Identifier: EUPL-1.2

  import AuditEventList from '#lib/components/AuditEventList.svelte';
  import { auditExportUrl, fetchAuditEvents, revertAuditEvent, verifyAuditLog } from '#lib/api/audit.js';
  import { loadSecrets } from '#lib/stores/secrets.js';
  import { addToast } from '#lib/stores/sync.js';
  import type { AuditChainStatus, AuditEvent } from '#lib/types/index.js';

  const PAGE = 100;
  const TYPES = [
    'secret.system', 'secret.owners', 'secret.confirmed', 'secret.version', 'secret.metadata', 'secret.settings',
    'secret.config_applied', 'secret.baseline', 'secret.removed', 'secret.reappeared', 'secret.purged',
    'system.created', 'system.updated', 'system.owners', 'system.deleted',
    'owner.created', 'owner.updated', 'owner.deleted', 'owner.route_added', 'owner.route_deleted',
    'config.baseline', 'config.changed',
  ];

  let events = $state<AuditEvent[]>([]);
  let chain = $state<AuditChainStatus | null>(null);
  let loading = $state(false);
  let error = $state<string | null>(null);
  let hasMore = $state(false);
  let eventType = $state('');
  let vaultName = $state('');
  let secretPath = $state('');

  async function load(append = false) {
    loading = true;
    error = null;
    try {
      const page = await fetchAuditEvents({
        event_type: eventType || undefined,
        vault_name: vaultName || undefined,
        secret_path: secretPath || undefined,
        before_id: append && events.length ? events[events.length - 1].id : undefined,
        limit: PAGE,
      });
      events = append ? [...events, ...page] : page;
      hasMore = page.length === PAGE;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load the audit log';
    } finally {
      loading = false;
    }
  }

  async function verify() {
    try {
      chain = await verifyAuditLog();
    } catch {
      chain = null;
    }
  }

  async function handleRevert(event: AuditEvent) {
    try {
      const created = await revertAuditEvent(event.id);
      addToast(`Reverted #${event.id} (new event #${created.id})`, 'success');
      await Promise.all([load(), verify(), loadSecrets()]);
    } catch (err) {
      addToast(err instanceof Error ? err.message : 'Revert failed', 'error');
    }
  }

  $effect(() => {
    load();
    verify();
  });

  const inputClass =
    'bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-300 focus:outline-none focus:border-indigo-500';
</script>

<div class="space-y-4">
  <div class="flex items-end justify-between gap-4">
    <div>
      <h1 class="text-2xl font-bold text-white">Audit log</h1>
      <p class="mt-1 text-sm text-gray-400">Every change Chronowarden made or saw, append-only and hash-chained</p>
    </div>
    <a href={auditExportUrl()} download
       class="whitespace-nowrap rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-gray-300 hover:bg-gray-700">
      Export JSONL
    </a>
  </div>

  {#if chain}
    <div class="rounded-lg border px-4 py-3 text-sm {chain.valid ? 'border-green-800 bg-green-900/20 text-green-300' : 'border-red-700 bg-red-900/30 text-red-300'}">
      {#if chain.valid}
        Chain intact: {chain.events} event(s). Head hash <span class="break-all font-mono text-xs">{chain.head_hash}</span>
      {:else}
        Chain broken at event #{chain.first_invalid_id}: {chain.reason}. The log was changed outside Chronowarden.
      {/if}
    </div>
  {/if}

  <div class="flex flex-wrap items-center gap-2">
    <select class={inputClass} bind:value={eventType} onchange={() => load()} aria-label="Event type">
      <option value="">All event types</option>
      {#each TYPES as type}<option value={type}>{type}</option>{/each}
    </select>
    <input class={inputClass} placeholder="Vault" bind:value={vaultName} onchange={() => load()} aria-label="Vault" />
    <input class="{inputClass} w-64" placeholder="Exact secret path" bind:value={secretPath} onchange={() => load()} aria-label="Secret path" />
  </div>

  {#if error}
    <div class="rounded-lg border border-red-700 bg-red-900/30 px-4 py-3 text-red-300">{error}</div>
  {:else}
    <div class="overflow-hidden rounded-lg border border-gray-700 bg-gray-800">
      <AuditEventList {events} onRevert={handleRevert} />
      {#if hasMore}
        <div class="border-t border-gray-700 px-4 py-3 text-center">
          <button onclick={() => load(true)} disabled={loading} class="text-sm text-indigo-400 hover:text-indigo-300">
            {loading ? 'Loading…' : 'Load older'}
          </button>
        </div>
      {/if}
    </div>
  {/if}
</div>
