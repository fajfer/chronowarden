<!-- SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org> -->
<!--                                                               -->
<!-- SPDX-License-Identifier: EUPL-1.2                              -->

<script lang="ts">
  import type { Snippet } from 'svelte';

  /** The shared dialog shell: a backdrop that closes on click or Escape, and a panel labelled by its heading. */
  let { onClose, labelledby, width = 'max-w-md', children }: {
    onClose: () => void;
    labelledby: string;
    width?: string;
    children: Snippet;
  } = $props();

  function onKeydown(e: KeyboardEvent): void {
    if (e.key === 'Escape') onClose();
  }
</script>

<svelte:window onkeydown={onKeydown} />

<!-- Escape is handled on the window above, so the backdrop needs no key handler of its own -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60" role="presentation" onclick={onClose}>
  <div class="bg-gray-800 border border-gray-700 rounded-xl shadow-2xl w-full {width} mx-4 max-h-[90vh] overflow-y-auto"
       role="dialog" aria-modal="true" aria-labelledby={labelledby} tabindex="-1"
       onclick={(e: MouseEvent) => e.stopPropagation()}>
    {@render children()}
  </div>
</div>
