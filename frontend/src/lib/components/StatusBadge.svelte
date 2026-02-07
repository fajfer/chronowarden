<!-- SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org> -->
<!--                                                               -->
<!-- SPDX-License-Identifier: EUPL-1.2                              -->

<script lang="ts">
  import { getStatusColor, getStatusBgColor, getStatusIcon } from '$lib/utils/statusColor';
  import type { SecretStatus } from '$lib/types';

  let { status }: { status: SecretStatus } = $props();

  const color = $derived(getStatusColor(status));
  const bgColor = $derived(getStatusBgColor(status));
  const icon = $derived(getStatusIcon(status));
</script>

<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium {color} {bgColor}">
  {icon} {status}
</span>
