<!-- SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org> -->
<!--                                                               -->
<!-- SPDX-License-Identifier: EUPL-1.2                              -->

<script lang="ts">
  import { createApiToken, fetchApiTokens, revokeApiToken } from '#lib/api/auth.js';
  import { addToast } from '#lib/stores/sync.js';
  import { formatDate } from '#lib/utils/dateFormat.js';
  import type { ApiToken, NewApiToken, Owner, Role } from '#lib/types/index.js';

  let { owners }: { owners: Owner[] } = $props();

  let tokens = $state<ApiToken[]>([]);
  let name = $state('');
  let role = $state<Role>('viewer');
  let ownerId = $state('');
  let days = $state(90);
  let creating = $state(false);
  let created = $state<NewApiToken | null>(null);

  const ownerNames = $derived(new Map(owners.map((o) => [o.id, o.name])));

  async function load() {
    try {
      tokens = await fetchApiTokens();
    } catch (err) {
      addToast(err instanceof Error ? err.message : 'Loading API tokens failed', 'error');
    }
  }

  async function handleCreate(e: Event) {
    e.preventDefault();
    creating = true;
    try {
      created = await createApiToken({
        name: name.trim(),
        role,
        owner_id: role === 'owner' ? ownerId || null : null,
        expires_in_days: days,
      });
      name = '';
      await load();
    } catch (err) {
      addToast(err instanceof Error ? err.message : 'Creating the token failed', 'error');
    } finally {
      creating = false;
    }
  }

  async function handleRevoke(token: ApiToken) {
    try {
      await revokeApiToken(token.id);
      addToast(`Revoked "${token.name}"`, 'success');
      await load();
    } catch (err) {
      addToast(err instanceof Error ? err.message : 'Revoking failed', 'error');
    }
  }

  async function copyToken() {
    if (!created) return;
    try {
      await navigator.clipboard.writeText(created.token);
      addToast('Token copied', 'success');
    } catch {
      addToast('Copy failed; select the token and copy it by hand', 'error');
    }
  }

  function tokenState(token: ApiToken): string {
    if (token.revoked_at) return `revoked ${formatDate(token.revoked_at)}`;
    if (new Date(token.expires_at) <= new Date()) return 'expired';
    return `expires ${formatDate(token.expires_at)}`;
  }

  $effect(() => {
    load();
  });
</script>

<div class="space-y-4">
  <div>
    <h2 class="text-lg font-semibold text-white">API tokens</h2>
    <p class="text-xs text-gray-500">
      For pipelines and other clients: send <code>Authorization: Bearer &lt;token&gt;</code>. Each token has a role;
      an owner token acts for one owner. Changes made with a token appear as <code>token:&lt;name&gt;</code> in the audit log.
    </p>
  </div>

  {#if created}
    <div class="px-4 py-3 bg-emerald-900/30 border border-emerald-700 rounded-lg space-y-2">
      <p class="text-sm text-emerald-300">Token "{created.name}" created. Store it now: it won't be shown again.</p>
      <div class="flex gap-2">
        <code class="flex-1 min-w-0 break-all text-xs text-gray-200 bg-gray-900 rounded px-2 py-1.5">{created.token}</code>
        <button onclick={copyToken} class="text-xs px-2 py-1 rounded bg-gray-700 hover:bg-gray-600 text-gray-300">Copy</button>
        <button onclick={() => (created = null)} class="text-xs px-2 py-1 rounded bg-gray-700 hover:bg-gray-600 text-gray-300">Done</button>
      </div>
    </div>
  {/if}

  <form onsubmit={handleCreate} class="bg-gray-800 border border-gray-700 rounded-lg p-4 flex flex-wrap items-end gap-3">
    <div>
      <label for="token-name" class="block text-xs text-gray-500 uppercase mb-1">Name</label>
      <input id="token-name" bind:value={name} required maxlength="100" placeholder="e.g. deploy-pipeline"
             class="px-3 py-1.5 bg-gray-900 border border-gray-600 rounded-lg text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-indigo-500" />
    </div>
    <div>
      <label for="token-role" class="block text-xs text-gray-500 uppercase mb-1">Role</label>
      <select id="token-role" bind:value={role}
              class="px-3 py-1.5 bg-gray-900 border border-gray-600 rounded-lg text-sm text-gray-200 focus:outline-none focus:border-indigo-500">
        <option value="viewer">viewer</option>
        <option value="owner">owner</option>
        <option value="admin">admin</option>
      </select>
    </div>
    {#if role === 'owner'}
      <div>
        <label for="token-owner" class="block text-xs text-gray-500 uppercase mb-1">Acts for</label>
        <select id="token-owner" bind:value={ownerId} required
                class="px-3 py-1.5 bg-gray-900 border border-gray-600 rounded-lg text-sm text-gray-200 focus:outline-none focus:border-indigo-500">
          <option value="" disabled>Choose an owner</option>
          {#each owners as owner (owner.id)}<option value={owner.id}>{owner.name}</option>{/each}
        </select>
      </div>
    {/if}
    <div>
      <label for="token-days" class="block text-xs text-gray-500 uppercase mb-1">Expires in (days)</label>
      <input id="token-days" type="number" min="1" bind:value={days} required
             class="w-28 px-3 py-1.5 bg-gray-900 border border-gray-600 rounded-lg text-sm text-gray-200 focus:outline-none focus:border-indigo-500" />
    </div>
    <button type="submit" disabled={creating || !name.trim()}
            class="px-4 py-1.5 text-sm rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition-colors disabled:opacity-50">
      {creating ? 'Creating…' : 'Create token'}
    </button>
  </form>

  {#if tokens.length === 0}
    <div class="text-center text-gray-500 py-8">No API tokens yet</div>
  {:else}
    <div class="bg-gray-800 border border-gray-700 rounded-lg overflow-hidden">
      <table class="w-full text-sm">
        <thead>
          <tr class="text-gray-400 text-xs uppercase border-b border-gray-700">
            <th class="px-4 py-3 text-left">Name</th>
            <th class="px-4 py-3 text-left">Role</th>
            <th class="px-4 py-3 text-left">State</th>
            <th class="px-4 py-3 text-left">Last used</th>
            <th class="px-4 py-3 text-left">Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each tokens as token (token.id)}
            <tr class="border-b border-gray-700/50 {token.revoked_at ? 'text-gray-600' : 'text-gray-300'}">
              <td class="px-4 py-3">{token.name}</td>
              <td class="px-4 py-3">
                {token.role}{token.owner_id ? ` · ${ownerNames.get(token.owner_id) ?? token.owner_id}` : ''}
              </td>
              <td class="px-4 py-3">{tokenState(token)}</td>
              <td class="px-4 py-3">{token.last_used_at ? formatDate(token.last_used_at) : 'never'}</td>
              <td class="px-4 py-3">
                {#if !token.revoked_at}
                  <button onclick={() => handleRevoke(token)} class="text-xs px-2 py-1 rounded bg-red-900/50 hover:bg-red-800/50 text-red-300">Revoke</button>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
