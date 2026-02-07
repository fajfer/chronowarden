<!-- SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org> -->
<!--                                                               -->
<!-- SPDX-License-Identifier: EUPL-1.2                              -->

<script lang="ts">
  import { canBulkEditSecrets } from '$lib/stores/auth';

  let { selectedCount, onEnable, onDisable, onChangeSeverity }: {
    selectedCount: number;
    onEnable: () => void;
    onDisable: () => void;
    onChangeSeverity: (severity: string) => void;
  } = $props();
</script>

{#if $canBulkEditSecrets && selectedCount > 0}
  <div class="flex items-center gap-3 px-4 py-3 bg-indigo-900/30 border border-indigo-700 rounded-lg">
    <span class="text-sm text-indigo-300">{selectedCount} selected</span>
    <button onclick={onEnable} class="px-3 py-1 text-xs rounded bg-green-700 hover:bg-green-600 text-white">
      Enable
    </button>
    <button onclick={onDisable} class="px-3 py-1 text-xs rounded bg-red-700 hover:bg-red-600 text-white">
      Disable
    </button>
    <select
      onchange={(e: Event) => onChangeSeverity((e.target as HTMLSelectElement).value)}
      class="px-2 py-1 text-xs rounded bg-gray-700 border border-gray-600 text-gray-200"
    >
      <option value="">Change Severity</option>
      <option value="critical">Critical</option>
      <option value="pci-dss-4.0">PCI-DSS 4.0</option>
      <option value="default">Default</option>
      <option value="none">None</option>
    </select>
  </div>
{/if}
