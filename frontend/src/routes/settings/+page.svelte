<script lang="ts">
  // SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
  //
  // SPDX-License-Identifier: EUPL-1.2

  import { fetchOwners, createOwner, updateOwner, deleteOwner } from '#lib/api/owners.js';
  import { fetchDeliveries, fetchFiringAlerts } from '#lib/api/alerts.js';
  import { fetchHealthCheck, fetchApiInfo } from '#lib/api/vaults.js';
  import { fetchSystems, createSystem, updateSystem, setSystemOwners, deleteSystem } from '#lib/api/systems.js';
  import OwnerModal from '#lib/components/OwnerModal.svelte';
  import RoutesModal from '#lib/components/RoutesModal.svelte';
  import SystemModal from '#lib/components/SystemModal.svelte';
  import ApiTokensPanel from '#lib/components/ApiTokensPanel.svelte';
  import { actsFor, currentUser, isAdmin } from '#lib/stores/auth.js';
  import { safeHttpUrl } from '#lib/utils/safeUrl.js';
  import { availableThemes, currentTheme, setTheme } from '#lib/stores/theme.js';
  import { addToast } from '#lib/stores/sync.js';
  import { formatDate } from '#lib/utils/dateFormat.js';
  import type { Owner, ApiInfo, System, SystemFormData, Delivery, FiringAlert } from '#lib/types/index.js';

  let activeTab = $state<'general' | 'owners' | 'systems' | 'webhooks' | 'tokens'>('general');

  // General settings
  let apiInfo = $state<ApiInfo | null>(null);
  let healthStatus = $state<string>('unknown');

  // Owners
  let owners = $state<Owner[]>([]);
  let ownersLoading = $state(false);
  let ownersError = $state<string | null>(null);
  let modalOpen = $state(false);
  let editingOwner = $state<Owner | null>(null);
  let routesOwnerId = $state<string | null>(null);
  const routesOwner = $derived(owners.find((o) => o.id === routesOwnerId) ?? null);

  // Webhooks
  let firing = $state<FiringAlert[]>([]);
  let deliveries = $state<Delivery[]>([]);

  async function loadWebhooks() {
    try {
      [firing, deliveries] = await Promise.all([fetchFiringAlerts(), fetchDeliveries()]);
    } catch (err) {
      addToast(err instanceof Error ? err.message : 'Loading webhooks failed', 'error');
    }
  }

  // Systems
  let systems = $state<System[]>([]);
  let systemsLoading = $state(false);
  let systemsError = $state<string | null>(null);
  let systemModalOpen = $state(false);
  let editingSystem = $state<System | null>(null);

  async function loadApiInfo() {
    try {
      apiInfo = await fetchApiInfo();
    } catch {
      apiInfo = null;
    }
    try {
      const health = await fetchHealthCheck();
      healthStatus = health.status;
    } catch {
      healthStatus = 'unreachable';
    }
  }

  async function loadOwners() {
    ownersLoading = true;
    ownersError = null;
    try {
      owners = await fetchOwners();
    } catch (err) {
      ownersError = err instanceof Error ? err.message : 'Failed to load owners';
    } finally {
      ownersLoading = false;
    }
  }

  async function handleSaveOwner(data: { name: string; email: string; idp_group: string }) {
    try {
      if (editingOwner) {
        // Owners rename themselves; only admins change who acts for an owner (ADR-026)
        await updateOwner(editingOwner.id, $isAdmin ? data : { name: data.name });
        addToast(`Updated owner "${data.name}"`, 'success');
      } else {
        await createOwner(data);
        addToast(`Created owner "${data.name}"`, 'success');
      }
      await loadOwners();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Operation failed';
      addToast(message, 'error');
    }
  }

  async function handleDeleteOwner(owner: Owner) {
    try {
      await deleteOwner(owner.id);
      addToast(`Deleted owner "${owner.name}"`, 'success');
      await Promise.all([loadOwners(), loadSystems()]);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Delete failed';
      addToast(message, 'error');
    }
  }



  async function loadSystems() {
    systemsLoading = true;
    systemsError = null;
    try {
      systems = await fetchSystems();
    } catch (err) {
      systemsError = err instanceof Error ? err.message : 'Failed to load systems';
    } finally {
      systemsLoading = false;
    }
  }

  async function handleSaveSystem(data: SystemFormData) {
    try {
      if (editingSystem) {
        const { owner_ids, ...fields } = data;
        await updateSystem(editingSystem.id, fields);
        await setSystemOwners(editingSystem.id, owner_ids);
        addToast(`Updated system "${data.name}"`, 'success');
      } else {
        await createSystem(data);
        addToast(`Created system "${data.name}"`, 'success');
      }
      await loadSystems();
    } catch (err) {
      addToast(err instanceof Error ? err.message : 'Operation failed', 'error');
    }
  }

  async function handleDeleteSystem(system: System) {
    try {
      await deleteSystem(system.id);
      addToast(`Deleted system "${system.name}"`, 'success');
      await loadSystems();
    } catch (err) {
      addToast(err instanceof Error ? err.message : 'Delete failed', 'error');
    }
  }

  function openSystemModal(system: System | null) {
    editingSystem = system;
    systemModalOpen = true;
  }

  function openCreateModal() {
    editingOwner = null;
    modalOpen = true;
  }

  function openEditModal(owner: Owner) {
    editingOwner = owner;
    modalOpen = true;
  }

  $effect(() => {
    loadApiInfo();
    loadOwners();
    loadSystems();
  });
</script>

<div class="space-y-6">
  <h1 class="text-2xl font-bold text-white">Settings</h1>

  <!-- Tab navigation -->
  <div class="flex gap-1 border-b border-gray-700">
    <button
      onclick={() => activeTab = 'general'}
      class="px-4 py-2 text-sm font-medium border-b-2 transition-colors
        {activeTab === 'general' ? 'border-indigo-500 text-indigo-400' : 'border-transparent text-gray-400 hover:text-gray-300'}"
    >
      General
    </button>
    <button
      onclick={() => activeTab = 'owners'}
      class="px-4 py-2 text-sm font-medium border-b-2 transition-colors
        {activeTab === 'owners' ? 'border-indigo-500 text-indigo-400' : 'border-transparent text-gray-400 hover:text-gray-300'}"
    >
      Owners
    </button>
    <button
      onclick={() => { activeTab = 'webhooks'; loadWebhooks(); }}
      class="px-4 py-2 text-sm font-medium border-b-2 transition-colors
        {activeTab === 'webhooks' ? 'border-indigo-500 text-indigo-400' : 'border-transparent text-gray-400 hover:text-gray-300'}"
    >
      Webhooks
    </button>
    <button
      onclick={() => activeTab = 'systems'}
      class="px-4 py-2 text-sm font-medium border-b-2 transition-colors
        {activeTab === 'systems' ? 'border-indigo-500 text-indigo-400' : 'border-transparent text-gray-400 hover:text-gray-300'}"
    >
      Systems
    </button>
    {#if $isAdmin}
      <button
        onclick={() => activeTab = 'tokens'}
        class="px-4 py-2 text-sm font-medium border-b-2 transition-colors
          {activeTab === 'tokens' ? 'border-indigo-500 text-indigo-400' : 'border-transparent text-gray-400 hover:text-gray-300'}"
      >
        API tokens
      </button>
    {/if}
  </div>

  {#if activeTab === 'general'}
    <div class="bg-gray-800 border border-gray-700 rounded-lg p-6 space-y-4">
      <h2 class="text-lg font-semibold text-white">General Settings</h2>
      <div class="space-y-4 text-sm">
        <div class="flex items-center justify-between py-2 border-b border-gray-700">
          <div>
            <p class="text-gray-200">API Name</p>
            <p class="text-xs text-gray-500">Backend API identity</p>
          </div>
          <span class="text-gray-400">{apiInfo?.name ?? '—'}</span>
        </div>
        <div class="flex items-center justify-between py-2 border-b border-gray-700">
          <div>
            <p class="text-gray-200">API Version</p>
            <p class="text-xs text-gray-500">Backend version</p>
          </div>
          <span class="text-gray-400">{apiInfo?.version ?? '—'}</span>
        </div>
        <div class="flex items-center justify-between py-2 border-b border-gray-700">
          <div>
            <p class="text-gray-200">Theme</p>
            <p class="text-xs text-gray-500">Frontend branding, logo, and mascot variant</p>
          </div>
          <select
            class="min-w-36 rounded-md border border-gray-600 bg-gray-900 px-3 py-1.5 text-gray-200 focus:border-indigo-500 focus:outline-none"
            aria-label="Theme"
            value={$currentTheme.id}
            onchange={(event) => setTheme((event.currentTarget as HTMLSelectElement).value)}
          >
            {#each availableThemes as theme}
              <option value={theme.id}>{theme.label}</option>
            {/each}
          </select>
        </div>
        <div class="flex items-center justify-between py-2 border-b border-gray-700">
          <div>
            <p class="text-gray-200">Health Status</p>
            <p class="text-xs text-gray-500">Backend health check</p>
          </div>
          <span class="{healthStatus === 'healthy' ? 'text-green-400' : 'text-red-400'}">{healthStatus}</span>
        </div>
        <div class="flex items-center justify-between py-2">
          <div>
            <p class="text-gray-200">API Docs</p>
            <p class="text-xs text-gray-500">Interactive API documentation</p>
          </div>
          <a href={apiInfo?.docs ?? '/docs'} target="_blank" class="text-indigo-400 hover:text-indigo-300">{apiInfo?.docs ?? '/docs'}</a>
        </div>
      </div>
    </div>
  {:else if activeTab === 'webhooks'}
    <div class="space-y-4">
      <p class="text-sm text-gray-400">
        Owners get alerts about their secrets through their webhook routes (Owners → Webhook routes); vault-health and
        compliance alerts and those of unowned secrets go to <code class="text-gray-300">alerting.default_routes</code>
        in <code class="text-gray-300">config.yaml</code>.
      </p>
      <div class="overflow-hidden rounded-lg border border-gray-700 bg-gray-800">
        <div class="border-b border-gray-700 px-5 py-3 text-sm font-semibold text-white">Firing now</div>
        {#if firing.length === 0}
          <p class="px-5 py-4 text-sm text-gray-500">Nothing is firing.</p>
        {:else}
          <ul class="divide-y divide-gray-700/50 text-sm">
            {#each firing as alert (alert.fingerprint)}
              <li class="px-5 py-2"><span class="font-mono text-xs text-red-300">{alert.alertname}</span>
                <span class="text-gray-200">{alert.annotations.summary}</span>
                <span class="block text-xs text-gray-500">since {formatDate(alert.starts_at)}</span></li>
            {/each}
          </ul>
        {/if}
      </div>
      <div class="overflow-hidden rounded-lg border border-gray-700 bg-gray-800">
        <div class="flex items-center border-b border-gray-700 px-5 py-3 text-sm font-semibold text-white">
          Deliveries
          <button onclick={loadWebhooks} class="ml-auto rounded bg-gray-700 px-2 py-1 text-xs text-gray-300 hover:bg-gray-600">Refresh</button>
        </div>
        {#if deliveries.length === 0}
          <p class="px-5 py-4 text-sm text-gray-500">No webhooks sent yet.</p>
        {:else}
          <table class="w-full text-sm">
            <thead><tr class="text-xs uppercase text-gray-500"><th class="px-5 py-2 text-left">#</th><th class="px-3 py-2 text-left">Alert</th><th class="px-3 py-2 text-left">To</th><th class="px-3 py-2 text-left">Status</th><th class="px-5 py-2 text-left">Last answer</th></tr></thead>
            <tbody>
              {#each deliveries as d (d.id)}
                <tr class="border-t border-gray-700/50">
                  <td class="px-5 py-2 font-mono text-xs text-gray-500">{d.id}</td>
                  <td class="px-3 py-2 font-mono text-xs text-gray-300">{d.alertname}</td>
                  <td class="px-3 py-2 text-gray-300">{d.receiver}</td>
                  <td class="px-3 py-2 {d.status === 'delivered' ? 'text-green-400' : d.status === 'failed' ? 'text-red-400' : 'text-yellow-400'}">{d.status} ({d.attempts})</td>
                  <td class="px-5 py-2 text-xs text-gray-400">{d.last_error ?? (d.last_status_code ? `HTTP ${d.last_status_code}` : '—')}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        {/if}
      </div>
    </div>
  {:else if activeTab === 'tokens' && $isAdmin}
    <ApiTokensPanel {owners} />
  {:else if activeTab === 'systems'}
    <div class="space-y-4">
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-lg font-semibold text-white">Systems</h2>
          <p class="text-xs text-gray-500">Business systems secrets belong to. A secret without its own owners is the responsibility of its system's owners.</p>
        </div>
        {#if $isAdmin}
          <button onclick={() => openSystemModal(null)}
                  class="px-4 py-2 text-sm rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition-colors whitespace-nowrap">
            Create System
          </button>
        {/if}
      </div>

      {#if systemsLoading}
        <div class="text-center text-gray-400 py-12">Loading systems…</div>
      {:else if systemsError}
        <div class="px-4 py-3 bg-red-900/30 border border-red-700 rounded-lg text-red-300">{systemsError}</div>
      {:else if systems.length === 0}
        <div class="text-center text-gray-500 py-12">No systems configured yet</div>
      {:else}
        <div class="bg-gray-800 border border-gray-700 rounded-lg overflow-hidden">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-gray-400 text-xs uppercase border-b border-gray-700">
                <th class="px-4 py-3 text-left">Name</th>
                <th class="px-4 py-3 text-left">CMDB</th>
                <th class="px-4 py-3 text-left">Asset</th>
                <th class="px-4 py-3 text-left">Owners</th>
                <th class="px-4 py-3 text-left">Actions</th>
              </tr>
            </thead>
            <tbody>
              {#each systems as system (system.id)}
                <tr class="border-b border-gray-700/50 hover:bg-gray-700/30 transition-colors">
                  <td class="px-4 py-3">
                    <div class="text-gray-200">{system.name}</div>
                    {#if system.description}<div class="text-xs text-gray-500">{system.description}</div>{/if}
                  </td>
                  <td class="px-4 py-3">
                    {#if safeHttpUrl(system.cmdb_uri)}
                      <a href={safeHttpUrl(system.cmdb_uri)} target="_blank" rel="noopener noreferrer" class="text-indigo-400 hover:text-indigo-300">Open</a>
                    {:else}<span class="text-gray-600">—</span>{/if}
                  </td>
                  <td class="px-4 py-3 text-gray-400">{system.asset_number ?? '—'}</td>
                  <td class="px-4 py-3 {system.owners.length ? 'text-gray-300' : 'text-gray-600'}">
                    {system.owners.length ? system.owners.map((o) => o.name).join(', ') : 'No owners'}
                  </td>
                  <td class="px-4 py-3 flex gap-2">
                    {#if $isAdmin}
                      <button onclick={() => openSystemModal(system)} class="text-xs px-2 py-1 rounded bg-gray-700 hover:bg-gray-600 text-gray-300">Edit</button>
                      <button onclick={() => handleDeleteSystem(system)} class="text-xs px-2 py-1 rounded bg-red-900/50 hover:bg-red-800/50 text-red-300">Delete</button>
                    {/if}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </div>
  {:else}
    <!-- Owners tab -->
    <div class="space-y-4">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold text-white">Owner Profiles</h2>
        {#if $isAdmin}
          <button onclick={openCreateModal}
                  class="px-4 py-2 text-sm rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition-colors">
            Create Owner
          </button>
        {/if}
      </div>

      {#if ownersLoading}
        <div class="text-center text-gray-400 py-12">Loading owners…</div>
      {:else if ownersError}
        <div class="px-4 py-3 bg-red-900/30 border border-red-700 rounded-lg text-red-300">{ownersError}</div>
      {:else if owners.length === 0}
        <div class="text-center text-gray-500 py-12">No owners configured yet</div>
      {:else}
        <div class="bg-gray-800 border border-gray-700 rounded-lg overflow-hidden">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-gray-400 text-xs uppercase border-b border-gray-700">
                <th class="px-4 py-3 text-left">Name</th>
                <th class="px-4 py-3 text-left">Email</th>
                <th class="px-4 py-3 text-left">IdP group</th>
                <th class="px-4 py-3 text-left">Routes</th>
                <th class="px-4 py-3 text-left">Actions</th>
              </tr>
            </thead>
            <tbody>
              {#each owners as owner}
                <tr class="border-b border-gray-700/50 hover:bg-gray-700/30 transition-colors">
                  <td class="px-4 py-3 text-gray-200">{owner.name}</td>
                  <td class="px-4 py-3 text-gray-400">{owner.email}</td>
                  <td class="px-4 py-3 text-gray-400">{owner.idp_group ?? '—'}</td>
                  <td class="px-4 py-3 text-gray-400">
                    {owner.notification_routes.length}
                    {#each owner.notification_routes as route}
                      <span class="ml-1 text-xs px-1 py-0.5 rounded bg-gray-700 text-gray-300">{route.address}{route.signed ? ' · signed' : ''}</span>
                    {/each}
                  </td>
                  <td class="px-4 py-3 flex gap-2">
                    {#if actsFor($currentUser, [owner.id])}
                      <button onclick={() => openEditModal(owner)} class="text-xs px-2 py-1 rounded bg-gray-700 hover:bg-gray-600 text-gray-300">Edit</button>
                      <button onclick={() => (routesOwnerId = owner.id)} class="text-xs px-2 py-1 rounded bg-gray-700 hover:bg-gray-600 text-gray-300">Webhook routes</button>
                    {/if}
                    {#if $isAdmin}
                      <button onclick={() => handleDeleteOwner(owner)} class="text-xs px-2 py-1 rounded bg-red-900/50 hover:bg-red-800/50 text-red-300">Delete</button>
                    {/if}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </div>
  {/if}
</div>

<RoutesModal owner={routesOwner} onClose={() => (routesOwnerId = null)} onChange={loadOwners} />

<OwnerModal
  owner={editingOwner}
  open={modalOpen}
  canEditIdentity={$isAdmin}
  onClose={() => modalOpen = false}
  onSave={handleSaveOwner}
/>

<SystemModal
  system={editingSystem}
  {owners}
  open={systemModalOpen}
  onClose={() => systemModalOpen = false}
  onSave={handleSaveSystem}
/>
