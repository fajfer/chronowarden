<!-- SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org> -->
<!--                                                               -->
<!-- SPDX-License-Identifier: EUPL-1.2                              -->

<script lang="ts">
  import type { AuditEvent } from '#lib/types/index.js';
  import { describeEvent, eventLabel, eventTarget, isRevertible } from '#lib/utils/auditFormat.js';
  import { formatDate } from '#lib/utils/dateFormat.js';

  let { events, showTarget = true, onRevert }: {
    events: AuditEvent[];
    showTarget?: boolean;
    onRevert?: (event: AuditEvent) => void;
  } = $props();

  /** Events already reverted by a later event in this list: no Revert button for them. */
  const reverted = $derived(
    new Set(events.map((e) => (e.after as { reverts?: number } | null)?.reverts).filter((id) => id !== undefined)),
  );

  const SOURCE_CLASS: Record<string, string> = {
    sync: 'bg-sky-900/50 text-sky-300',
    ui: 'bg-indigo-900/50 text-indigo-300',
    api: 'bg-violet-900/50 text-violet-300',
    config: 'bg-amber-900/50 text-amber-300',
  };
</script>

{#if events.length === 0}
  <p class="px-4 py-6 text-sm text-gray-500">No changes recorded.</p>
{:else}
  <ul class="divide-y divide-gray-700/60">
    {#each events as event (event.id)}
      <li class="flex items-start gap-3 px-4 py-2.5 text-sm">
        <span class="w-36 shrink-0 font-mono text-xs text-gray-500" title={event.timestamp}>
          #{event.id} · {formatDate(event.timestamp)}
        </span>
        <span class="shrink-0 rounded px-1.5 py-0.5 text-[11px] {SOURCE_CLASS[event.source] ?? 'bg-gray-700 text-gray-300'}">{event.source}</span>
        <div class="min-w-0 flex-1">
          <span class="text-gray-200">{eventLabel(event)}</span>
          {#if showTarget && eventTarget(event)}
            <span class="ml-1 font-mono text-xs text-gray-500">{eventTarget(event)}</span>
          {/if}
          {#if describeEvent(event)}
            <p class="mt-0.5 break-words text-xs text-gray-400">{describeEvent(event)}</p>
          {/if}
        </div>
        {#if onRevert && isRevertible(event) && !reverted.has(event.id)}
          <button onclick={() => onRevert?.(event)}
                  class="shrink-0 rounded bg-gray-700 px-2 py-1 text-xs text-gray-300 hover:bg-gray-600">Revert</button>
        {/if}
      </li>
    {/each}
  </ul>
{/if}
