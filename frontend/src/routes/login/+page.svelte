<script lang="ts">
  // SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
  //
  // SPDX-License-Identifier: EUPL-1.2

  import { login } from '$lib/stores/auth';
  import { goto } from '$app/navigation';

  let username = $state('');
  let password = $state('');
  let error = $state('');

  function handleSubmit(e: Event) {
    e.preventDefault();
    if (login(username, password)) {
      goto('/');
    } else {
      error = 'Invalid credentials. Use admin/admin.';
    }
  }
</script>

<div class="min-h-screen bg-gray-900 flex items-center justify-center p-4">
  <div class="w-full max-w-sm">
    <div class="text-center mb-8">
      <span class="text-5xl">⏱</span>
      <h1 class="text-3xl font-bold text-white mt-4">Chronowarden</h1>
      <p class="text-gray-500 mt-2">Secret Expiration Monitoring</p>
    </div>

    <form onsubmit={handleSubmit} class="bg-gray-800 border border-gray-700 rounded-xl p-6 shadow-2xl space-y-4">
      {#if error}
        <div class="px-3 py-2 bg-red-900/30 border border-red-700 rounded-lg text-sm text-red-300">{error}</div>
      {/if}

      <div>
        <label for="username" class="block text-xs text-gray-500 uppercase mb-1">Username</label>
        <input
          id="username"
          type="text"
          bind:value={username}
          placeholder="admin"
          class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded-lg text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-indigo-500"
        />
      </div>

      <div>
        <label for="password" class="block text-xs text-gray-500 uppercase mb-1">Password</label>
        <input
          id="password"
          type="password"
          bind:value={password}
          placeholder="••••••"
          class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded-lg text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-indigo-500"
        />
      </div>

      <button type="submit" class="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-lg transition-colors">
        Login
      </button>

      <p class="text-xs text-gray-600 text-center">Hint: admin / admin</p>
    </form>
  </div>
</div>
