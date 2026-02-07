<!-- SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org> -->
<!--                                                               -->
<!-- SPDX-License-Identifier: EUPL-1.2                              -->

<script lang="ts">
  import { getSeverityColor } from '$lib/utils/statusColor';

  let { severity }: { severity: string } = $props();

  const colorClass = $derived(getSeverityColor(severity));
</script>

<span class="inline-flex items-center px-2 py-0.5 rounded border text-xs font-medium {colorClass}">
  {severity}
</span>
