<!-- SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org> -->
<!--                                                               -->
<!-- SPDX-License-Identifier: EUPL-1.2                              -->

<script lang="ts">
  import { getStatusColor, getStatusBgColor, getStatusLabel, getStatusDotBg } from '$lib/utils/statusColor';
  import type { SecretStatus } from '$lib/types';

  let { status }: { status: SecretStatus } = $props();

  const color = $derived(getStatusColor(status));
  const bgColor = $derived(getStatusBgColor(status));
  const label = $derived(getStatusLabel(status));
  const dotBg = $derived(getStatusDotBg(status));
</script>

<span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium {color} {bgColor}">
  <span class="w-1.5 h-1.5 rounded-full {dotBg}"></span>{label}
</span>
