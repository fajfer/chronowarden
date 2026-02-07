<script lang="ts">
  // SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
  //
  // SPDX-License-Identifier: EUPL-1.2

  let activeTab = $state<'general' | 'owners'>('general');
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
            <p class="text-gray-200">API Base URL</p>
            <p class="text-xs text-gray-500">Backend API endpoint</p>
          </div>
          <span class="text-gray-400">http://localhost:8000</span>
        </div>
        <div class="flex items-center justify-between py-2 border-b border-gray-700">
          <div>
            <p class="text-gray-200">Polling Interval</p>
            <p class="text-xs text-gray-500">How often to check for sync updates</p>
          </div>
          <span class="text-gray-400">6h</span>
        </div>
        <div class="flex items-center justify-between py-2">
          <div>
            <p class="text-gray-200">Version</p>
            <p class="text-xs text-gray-500">Current application version</p>
          </div>
          <span class="text-gray-400">0.0.1</span>
        </div>
      </div>
    </div>
  {:else}
    <!-- Owners tab content -->
    {@render ownersContent()}
  {/if}
</div>

{#snippet ownersContent()}
  {@const demoOwners = [
    { id: 'owner-1', name: 'Alice Admin', email: 'alice@example.com', routes: 2 },
    { id: 'owner-2', name: 'Bob Engineer', email: 'bob@example.com', routes: 1 },
  ]}

  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-semibold text-white">Owner Profiles</h2>
      <button class="px-4 py-2 text-sm rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition-colors">
        Create Owner
      </button>
    </div>

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
          {#each demoOwners as owner}
            <tr class="border-b border-gray-700/50 hover:bg-gray-700/30 transition-colors">
              <td class="px-4 py-3 text-gray-200">{owner.name}</td>
              <td class="px-4 py-3 text-gray-400">{owner.email}</td>
              <td class="px-4 py-3 text-gray-400">{owner.routes}</td>
              <td class="px-4 py-3 flex gap-2">
                <button class="text-xs px-2 py-1 rounded bg-gray-700 hover:bg-gray-600 text-gray-300">Edit</button>
                <button class="text-xs px-2 py-1 rounded bg-gray-700 hover:bg-gray-600 text-gray-300">Test</button>
                <button class="text-xs px-2 py-1 rounded bg-red-900/50 hover:bg-red-800/50 text-red-300">Delete</button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </div>
{/snippet}
