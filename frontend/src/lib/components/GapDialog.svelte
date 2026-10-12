<!-- SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org> -->
<!--                                                               -->
<!-- SPDX-License-Identifier: EUPL-1.2                              -->

<script lang="ts">
  import Modal from './Modal.svelte';
  import type { GapReport } from '#lib/types/index.js';

  let { report, title, busy = false, onConfirm, onCancel }: {
    report: GapReport | null;
    title: string;
    busy?: boolean;
    onConfirm: () => void;
    onCancel: () => void;
  } = $props();

  const GAP_LABELS: Record<string, string> = {
    no_owner: 'No effective owner',
    no_system: 'No system',
    expired: 'Expired',
    no_ttl: 'No TTL',
    privileged_without_owner: 'Privileged without an owner',
    awaiting_confirmation: 'Rotation awaiting confirmation',
  };
</script>

{#if report}
  <Modal onClose={onCancel} labelledby="gap-dialog-title" width="max-w-lg">
    <div class="border-b border-gray-700 px-6 py-4">
      <h2 id="gap-dialog-title" class="text-lg font-semibold text-white">{title}</h2>
      <p class="mt-1 text-sm text-gray-400">{report.total} secret(s) in scope.</p>
    </div>
    <div class="space-y-3 px-6 py-4 text-sm">
      {#if report.secrets.length === 0}
        <p class="text-green-300">No gaps: every secret in scope has an owner, a system, a TTL and confirmed rotations.</p>
      {:else}
        <p class="text-amber-300">
          {report.secrets.length} secret(s) have gaps. The snapshot records the inventory as it is; it doesn't record
          these warnings.
        </p>
        <ul class="space-y-1">
          {#each Object.entries(report.counts).filter(([, n]) => n > 0) as [gap, n]}
            <li class="flex justify-between text-gray-300"><span>{GAP_LABELS[gap] ?? gap}</span><span class="font-mono">{n}</span></li>
          {/each}
        </ul>
        <details>
          <summary class="cursor-pointer text-xs text-gray-500">Show secrets</summary>
          <ul class="mt-2 max-h-48 space-y-1 overflow-y-auto font-mono text-xs text-gray-400">
            {#each report.secrets as secret (secret.id)}
              <li>{secret.full_path}: {secret.gaps.map((g) => GAP_LABELS[g] ?? g).join(', ')}</li>
            {/each}
          </ul>
        </details>
      {/if}
    </div>
    <div class="flex justify-end gap-2 border-t border-gray-700 px-6 py-4">
      <button onclick={onConfirm} disabled={busy}
              class="rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white transition-colors hover:bg-indigo-500 disabled:opacity-50">
        {busy ? 'Freezing…' : report.secrets.length ? 'Freeze anyway' : 'Freeze snapshot'}
      </button>
      <button onclick={onCancel} class="rounded-lg bg-gray-700 px-4 py-2 text-sm text-gray-200 transition-colors hover:bg-gray-600">
        Cancel
      </button>
    </div>
  </Modal>
{/if}
