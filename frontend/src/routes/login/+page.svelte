<script lang="ts">
  // SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
  //
  // SPDX-License-Identifier: EUPL-1.2

  import { fetchApiInfo } from '#lib/api/vaults.js';
  import { loginUrl } from '#lib/api/auth.js';
  import { authChecked, authError, isAuthenticated } from '#lib/stores/auth.js';
  import type { AuthMode } from '#lib/types/index.js';
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import { onMount } from 'svelte';

  // Error codes from GET /api/v1/auth/callback
  const ERRORS: Record<string, string> = {
    expired: 'The login took too long or was already used. Please sign in again.',
    denied: 'The identity provider did not complete the login.',
    failed: 'The login could not be verified. If this keeps happening, ask an admin to check the server log.',
    no_role: 'You are signed in, but none of your groups has a Chronowarden role. Ask an admin to add one.',
  };

  let mode = $state<AuthMode | null>(null);

  const next = $derived.by(() => {
    const value = page.url.searchParams.get('next') ?? '/';
    return value.startsWith('/') && !value.startsWith('//') ? value : '/';
  });
  const error = $derived(ERRORS[page.url.searchParams.get('error') ?? ''] ?? $authError);

  onMount(async () => {
    try {
      mode = (await fetchApiInfo()).auth_mode;
    } catch {
      mode = null;
    }
  });

  $effect(() => {
    if ($authChecked && $isAuthenticated) goto(next);
  });
</script>

<div class="min-h-screen bg-gray-900 flex items-center justify-center p-4">
  <div class="w-full max-w-sm">
    <div class="text-center mb-8">
      <h1 class="text-3xl font-bold text-white mt-4">Chronowarden</h1>
      <p class="text-gray-500 mt-2">Secret Expiration Monitoring</p>
    </div>

    <div class="bg-gray-800 border border-gray-700 rounded-xl p-6 shadow-2xl space-y-4">
      {#if error}
        <p class="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">{error}</p>
      {/if}

      {#if mode === 'oidc'}
        <a
          href={loginUrl(next)}
          class="block w-full py-2.5 text-center bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-lg transition-colors"
        >
          Sign in
        </a>
      {:else if mode === 'proxy'}
        <p class="text-sm text-gray-400">
          Chronowarden expects your identity from the reverse proxy in front of it, but none arrived. Reload the page;
          if this stays, the proxy isn't forwarding the identity headers (see <code>auth.proxy</code>).
        </p>
        <button
          onclick={() => window.location.assign(next)}
          class="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-lg transition-colors"
        >
          Reload
        </button>
      {:else if mode === 'none'}
        <p class="text-sm text-gray-400">Authentication is off; continuing…</p>
      {:else}
        <p class="text-sm text-gray-400">Can't reach the Chronowarden API.</p>
      {/if}
    </div>
  </div>
</div>
