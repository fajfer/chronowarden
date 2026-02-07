<!-- SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org> -->
<!--                                                               -->
<!-- SPDX-License-Identifier: EUPL-1.2                              -->

<script lang="ts">
  let { title, value, color = 'text-white', bgColor = 'bg-gray-800' }: {
    title: string;
    value: number;
    color?: string;
    bgColor?: string;
  } = $props();
</script>

<div class="border border-gray-700 rounded-lg p-4 {bgColor}">
  <p class="text-xs text-gray-400 uppercase tracking-wider">{title}</p>
  <p class="text-2xl font-bold mt-1 {color}">{value}</p>
</div>
