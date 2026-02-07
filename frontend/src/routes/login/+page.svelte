<script lang="ts">
  // SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
  //
  // SPDX-License-Identifier: EUPL-1.2

  import { initAuth } from '$lib/stores/auth';
  import { goto } from '$app/navigation';

  let name = $state('');

  function handleSubmit(e: Event) {
    e.preventDefault();
    if (!name.trim()) return;
    initAuth();
    goto('/');
  }
</script>

<div class="min-h-screen bg-gray-900 flex items-center justify-center p-4">
  <div class="w-full max-w-sm">
    <div class="text-center mb-8">
      <h1 class="text-3xl font-bold text-white mt-4">Chronowarden</h1>
      <p class="text-gray-500 mt-2">Secret Expiration Monitoring</p>
    </div>

    <form onsubmit={handleSubmit} class="bg-gray-800 border border-gray-700 rounded-xl p-6 shadow-2xl space-y-4">
      <p class="text-sm text-gray-400">
        No authentication is configured on the backend. Enter your name to continue.
      </p>

      <div>
        <label for="name" class="block text-xs text-gray-500 uppercase mb-1">Your Name</label>
        <input
          id="name"
          type="text"
          bind:value={name}
          placeholder="Operator"
          class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded-lg text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-indigo-500"
        />
      </div>

      <button type="submit" class="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-lg transition-colors">
        Continue
      </button>
    </form>
  </div>
</div>
