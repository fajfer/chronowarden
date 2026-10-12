<!-- SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org> -->
<!--                                                               -->
<!-- SPDX-License-Identifier: EUPL-1.2                              -->

<script lang="ts">
  import Modal from './Modal.svelte';
  import type { Owner, Secret, System } from '#lib/types/index.js';
  import StatusBadge from './StatusBadge.svelte';
  import { formatDate } from '#lib/utils/dateFormat.js';
  import { fetchOwners } from '#lib/api/owners.js';
  import { fetchSystems } from '#lib/api/systems.js';
  import {
    confirmRotation, fetchSecret, fetchSecretHistory, setSecretOwners, setSecretPrivileged, setSecretSystem,
  } from '#lib/api/secrets.js';
  import { revertAuditEvent } from '#lib/api/audit.js';
  import { updateSecret, loadSecrets } from '#lib/stores/secrets.js';
  import AuditEventList from './AuditEventList.svelte';
  import { safeHttpUrl } from '#lib/utils/safeUrl.js';
  import type { AuditEvent } from '#lib/types/index.js';
  import { addToast } from '#lib/stores/sync.js';

  let { secret, onClose }: {
    secret: Secret | null;
    onClose: () => void;
  } = $props();

  let systems = $state<System[]>([]);
  let owners = $state<Owner[]>([]);
  let systemId = $state('');
  let ownerIds = $state<string[]>([]);
  let saving = $state(false);
  let history = $state<AuditEvent[]>([]);
  let appliedAt = $state('');
  let confirming = $state(false);

  /** Now, as a value for a datetime-local input (local time, minutes). */
  function nowLocal(): string {
    const d = new Date();
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  }

  async function loadHistory(id: number) {
    try {
      history = await fetchSecretHistory(id);
    } catch {
      history = [];
    }
  }

  async function togglePrivileged() {
    if (!secret) return;
    try {
      const updated = await setSecretPrivileged(secret.id, !secret.privileged);
      updateSecret(updated);
      secret = updated;
      addToast(`${updated.full_path} is ${updated.privileged ? 'now' : 'no longer'} privileged`, 'success');
      await loadHistory(updated.id);
    } catch (err) {
      addToast(err instanceof Error ? err.message : 'Changing the privileged flag failed', 'error');
    }
  }

  async function handleConfirm() {
    if (!secret || !appliedAt) return;
    confirming = true;
    try {
      const updated = await confirmRotation(secret.id, new Date(appliedAt).toISOString());
      updateSecret(updated);
      secret = updated;
      addToast(`Confirmed ${updated.full_path} applied`, 'success');
      await loadHistory(updated.id);
    } catch (err) {
      addToast(err instanceof Error ? err.message : 'Confirming failed', 'error');
    } finally {
      confirming = false;
    }
  }

  async function handleRevert(event: AuditEvent) {
    if (!secret) return;
    try {
      await revertAuditEvent(event.id);
      addToast(`Reverted #${event.id}`, 'success');
      const fresh = await fetchSecret(secret.id);
      updateSecret(fresh);
      secret = fresh;
      await loadSecrets();
    } catch (err) {
      addToast(err instanceof Error ? err.message : 'Revert failed', 'error');
    }
  }

  // Reload the choices and reset the form whenever another secret is opened
  $effect(() => {
    if (!secret) return;
    systemId = secret.system?.id ?? '';
    ownerIds = secret.owners.map((o) => o.id);
    fetchSystems().then((s) => (systems = s)).catch(() => (systems = []));
    fetchOwners().then((o) => (owners = o)).catch(() => (owners = []));
    appliedAt = nowLocal();
    loadHistory(secret.id);
  });

  const assignedSystem = $derived(systems.find((s) => s.id === systemId) ?? null);
  const dirty = $derived(
    !!secret &&
      (systemId !== (secret.system?.id ?? '') ||
        [...ownerIds].sort().join() !== secret.owners.map((o) => o.id).sort().join()),
  );

  function toggleOwner(id: string) {
    ownerIds = ownerIds.includes(id) ? ownerIds.filter((x) => x !== id) : [...ownerIds, id];
  }

  async function saveAssignment() {
    if (!secret) return;
    saving = true;
    try {
      let updated = await setSecretSystem(secret.id, systemId || null);
      updated = await setSecretOwners(secret.id, ownerIds);
      updateSecret(updated);
      secret = updated;
      addToast(`Updated assignment of ${updated.full_path}`, 'success');
      await loadHistory(updated.id);
    } catch (err) {
      addToast(err instanceof Error ? err.message : 'Saving the assignment failed', 'error');
    } finally {
      saving = false;
    }
  }
</script>

{#if secret}
  <Modal onClose={onClose} labelledby="secret-modal-title" width="max-w-lg">
    <div class="flex items-center justify-between px-6 py-4 border-b border-gray-700">
      <h2 id="secret-modal-title" class="text-lg font-semibold text-white">{secret.full_path}</h2>
      <button onclick={onClose} class="text-gray-400 hover:text-white text-xl">&times;</button>
    </div>

    <div class="px-6 py-4 space-y-4 text-sm">
      {#if secret.removed_at}
        <div class="px-3 py-2 bg-red-900/30 border border-red-800 rounded-lg text-red-300">
          No longer in the backend since {formatDate(secret.removed_at)}. Purge it from the secrets table once it's no
          longer needed for reporting.
        </div>
      {/if}
      <div class="flex flex-wrap gap-2">
        <StatusBadge status={secret.status} />
        {#if secret.awaiting_confirmation}
          <span class="inline-flex items-center px-2 py-0.5 rounded border text-xs font-medium {secret.confirmation_overdue ? 'text-red-400 border-red-500' : 'text-amber-400 border-amber-500'}">
            {secret.confirmation_overdue ? 'Confirmation overdue' : 'Awaiting confirmation'}
          </span>
        {/if}
        <span class="inline-flex items-center px-2 py-0.5 rounded border text-xs font-medium text-blue-400 border-blue-500">
          {secret.severity}
        </span>
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
        <div class="col-span-2">
          <label class="flex items-center gap-2 text-gray-200">
            <input type="checkbox" checked={secret.privileged} onchange={togglePrivileged} class="accent-rose-500" />
            Privileged
            <span class="text-xs text-gray-500">(written to the backend as chronowarden_privileged)</span>
          </label>
        </div>
      </div>

      {#if secret.confirmation_required || secret.last_confirmation}
        <div class="border-t border-gray-700 pt-4 space-y-2">
          <h3 class="text-xs text-gray-500 uppercase">Rotation confirmation</h3>
          <p class="text-xs text-gray-400">
            {#if secret.last_confirmation}
              Last confirmed: version {secret.last_confirmation.version} applied {formatDate(secret.last_confirmation.applied_at)}{secret.last_confirmation.confirmed_by ? ` by ${secret.last_confirmation.confirmed_by}` : ''}.
            {:else}
              Never confirmed.
            {/if}
            {#if secret.awaiting_confirmation}The newest version waits for confirmation that it is applied where it's used.{/if}
          </p>
          {#if secret.awaiting_confirmation || !secret.confirmation_required}
            <div class="flex items-end gap-2">
              <div>
                <label for="applied-at" class="block text-gray-500 text-xs mb-1">Applied at (your local time)</label>
                <input id="applied-at" type="datetime-local" bind:value={appliedAt}
                       class="px-3 py-1.5 bg-gray-900 border border-gray-600 rounded-lg text-sm text-gray-200 focus:outline-none focus:border-indigo-500" />
              </div>
              <button onclick={handleConfirm} disabled={confirming || !appliedAt}
                      class="px-3 py-1.5 text-sm rounded-lg bg-amber-600 hover:bg-amber-500 text-white transition-colors disabled:opacity-50">
                {confirming ? 'Confirming…' : 'Confirm applied'}
              </button>
            </div>
          {/if}
        </div>
      {/if}

      <div class="border-t border-gray-700 pt-4 space-y-3">
        <h3 class="text-xs text-gray-500 uppercase">Assignment</h3>
        <div>
          <label for="secret-system" class="block text-gray-500 text-xs mb-1">System</label>
          <select id="secret-system" bind:value={systemId}
                  class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded-lg text-sm text-gray-200 focus:outline-none focus:border-indigo-500">
            <option value="">Unassigned</option>
            {#each systems as system (system.id)}<option value={system.id}>{system.name}</option>{/each}
          </select>
          {#if safeHttpUrl(assignedSystem?.cmdb_uri)}
            <a href={safeHttpUrl(assignedSystem?.cmdb_uri)} target="_blank" rel="noopener noreferrer"
               class="inline-block mt-1 text-xs text-indigo-400 hover:text-indigo-300">Open in CMDB{assignedSystem?.asset_number ? ` (${assignedSystem.asset_number})` : ''}</a>
          {/if}
        </div>
        <fieldset>
          <legend class="block text-gray-500 text-xs mb-1">Owners of this secret</legend>
          {#if owners.length === 0}
            <p class="text-gray-500">No owners yet: create them in Settings → Owners.</p>
          {:else}
            <div class="flex flex-wrap gap-x-4 gap-y-1">
              {#each owners as owner (owner.id)}
                <label class="flex items-center gap-2 text-gray-200">
                  <input type="checkbox" checked={ownerIds.includes(owner.id)} onchange={() => toggleOwner(owner.id)} class="accent-indigo-500" />
                  {owner.name}
                </label>
              {/each}
            </div>
          {/if}
        </fieldset>
        <p class="text-xs text-gray-400">
          Responsible:
          {#if secret.effective_owners.length}
            <span class="text-gray-200">{secret.effective_owners.map((o) => o.name).join(', ')}</span>
            {#if secret.owners.length === 0}<span class="text-gray-500">(from the system)</span>{/if}
          {:else}
            <span class="text-yellow-400">nobody (unassigned)</span>
          {/if}
        </p>
      </div>

      <details class="border-t border-gray-700 pt-4">
        <summary class="cursor-pointer text-xs text-gray-500 uppercase">History ({history.length})</summary>
        <div class="mt-2 -mx-4 max-h-64 overflow-y-auto">
          <AuditEventList events={history} showTarget={false} onRevert={handleRevert} />
        </div>
      </details>
    </div>

    <div class="px-6 py-4 border-t border-gray-700 flex justify-end gap-2">
      <button onclick={saveAssignment} disabled={!dirty || saving}
              class="px-4 py-2 text-sm rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition-colors disabled:opacity-50">
        {saving ? 'Saving…' : 'Save assignment'}
      </button>
      <button
        onclick={onClose}
        class="px-4 py-2 text-sm rounded-lg bg-gray-700 hover:bg-gray-600 text-gray-200 transition-colors"
      >
        Close
      </button>
    </div>
  </Modal>
{/if}
