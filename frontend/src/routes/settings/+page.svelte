<script lang="ts">
  // SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
  //
  // SPDX-License-Identifier: EUPL-1.2

  import { fetchOwners, createOwner, updateOwner, deleteOwner, testNotificationRoute } from '$lib/api/owners';
  import { fetchHealthCheck, fetchApiInfo } from '$lib/api/vaults';
  import OwnerModal from '$lib/components/OwnerModal.svelte';
  import { addToast } from '$lib/stores/sync';
  import type { Owner, ApiInfo } from '$lib/types';

  let activeTab = $state<'general' | 'owners'>('general');

  // General settings
  let apiInfo = $state<ApiInfo | null>(null);
  let healthStatus = $state<string>('unknown');

  // Owners
  let owners = $state<Owner[]>([]);
  let ownersLoading = $state(false);
  let ownersError = $state<string | null>(null);
  let modalOpen = $state(false);
  let editingOwner = $state<Owner | null>(null);

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

  async function handleSaveOwner(data: { name: string; email: string }) {
    try {
      if (editingOwner) {
        await updateOwner(editingOwner.id, data);
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
      await loadOwners();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Delete failed';
      addToast(message, 'error');
    }
  }

  async function handleTestRoute(ownerId: string, routeId: string) {
    try {
      const result = await testNotificationRoute(ownerId, routeId);
      addToast(result.message, result.success ? 'success' : 'error');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Test failed';
      addToast(message, 'error');
    }
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
  {:else}
    <!-- Owners tab -->
    <div class="space-y-4">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold text-white">Owner Profiles</h2>
        <button onclick={openCreateModal}
                class="px-4 py-2 text-sm rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition-colors">
          Create Owner
        </button>
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
                <th class="px-4 py-3 text-left">Routes</th>
                <th class="px-4 py-3 text-left">Actions</th>
              </tr>
            </thead>
            <tbody>
              {#each owners as owner}
                <tr class="border-b border-gray-700/50 hover:bg-gray-700/30 transition-colors">
                  <td class="px-4 py-3 text-gray-200">{owner.name}</td>
                  <td class="px-4 py-3 text-gray-400">{owner.email}</td>
                  <td class="px-4 py-3 text-gray-400">
                    {owner.notification_routes.length}
                    {#each owner.notification_routes as route}
                      <span class="ml-1 text-xs px-1 py-0.5 rounded bg-gray-700 text-gray-300">{route.type}: {route.address}</span>
                    {/each}
                  </td>
                  <td class="px-4 py-3 flex gap-2">
                    <button onclick={() => openEditModal(owner)} class="text-xs px-2 py-1 rounded bg-gray-700 hover:bg-gray-600 text-gray-300">Edit</button>
                    {#each owner.notification_routes as route}
                      <button onclick={() => handleTestRoute(owner.id, route.id)} class="text-xs px-2 py-1 rounded bg-gray-700 hover:bg-gray-600 text-gray-300">Test {route.type}</button>
                    {/each}
                    <button onclick={() => handleDeleteOwner(owner)} class="text-xs px-2 py-1 rounded bg-red-900/50 hover:bg-red-800/50 text-red-300">Delete</button>
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

<OwnerModal
  owner={editingOwner}
  open={modalOpen}
  onClose={() => modalOpen = false}
  onSave={handleSaveOwner}
/>
