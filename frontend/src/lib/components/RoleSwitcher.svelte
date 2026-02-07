<!-- SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org> -->
<!--                                                               -->
<!-- SPDX-License-Identifier: EUPL-1.2                              -->

<script lang="ts">
  import { currentUser, switchUser } from '$lib/stores/auth';
  import { MOCK_USERS } from '$lib/utils/permissions';

  let dropdownOpen = $state(false);
</script>

<div class="relative">
  <button
    onclick={() => dropdownOpen = !dropdownOpen}
    class="flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg bg-gray-700 hover:bg-gray-600 text-gray-200"
  >
    <span>👤</span>
    <span>{$currentUser?.name ?? 'User'}</span>
    <span class="text-xs text-gray-400">({$currentUser?.role ?? 'unknown'})</span>
  </button>

  {#if dropdownOpen}
    <div class="absolute right-0 top-full mt-1 w-56 bg-gray-800 border border-gray-700 rounded-lg shadow-xl z-50">
      {#each MOCK_USERS as user}
        <button
          onclick={() => { switchUser(user.username); dropdownOpen = false; }}
          class="w-full text-left px-4 py-2 text-sm hover:bg-gray-700 transition-colors
                 {$currentUser?.username === user.username ? 'text-indigo-400' : 'text-gray-300'}"
        >
          <span class="font-medium">{user.name}</span>
          <span class="text-xs text-gray-500 ml-1">({user.role})</span>
        </button>
      {/each}
    </div>
  {/if}
</div>
