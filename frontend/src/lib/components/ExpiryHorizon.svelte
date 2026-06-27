<!-- SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org> -->
<!--                                                               -->
<!-- SPDX-License-Identifier: EUPL-1.2                              -->

<script lang="ts">
  import type { Secret } from '$lib/types';
  import { getStatusDotClasses } from '$lib/utils/statusColor';
  import { setSeverity, clearFilters } from '$lib/stores/filters';
  import { goto } from '$app/navigation';

  let { secrets = [] }: { secrets?: Secret[] } = $props();

  // Time window plotted on the axis (days). Secrets beyond the window are
  // pinned to the edges; overdue secrets fall in the shaded zone left of "now".
  const DOMAIN_MIN = -10;
  const DOMAIN_MAX = 95;

  const clampPct = (d: number): number => {
    const c = Math.max(DOMAIN_MIN, Math.min(DOMAIN_MAX, d));
    return ((c - DOMAIN_MIN) / (DOMAIN_MAX - DOMAIN_MIN)) * 100;
  };

  // Stable colour per severity lane, assigned in order of appearance.
  const LANE_COLORS = ['bg-indigo-400', 'bg-orange-400', 'bg-emerald-400', 'bg-sky-400', 'bg-fuchsia-400'];

  const MAX_VISIBLE_DAYS = 100;

  const lanes = $derived.by(() => {
    const tracked = secrets.filter((s) => s.days_remaining != null && (s.days_remaining as number) <= MAX_VISIBLE_DAYS);
    const severities = Array.from(new Set(tracked.map((s) => s.severity)));
    return severities.map((severity, i) => ({
      severity,
      color: LANE_COLORS[i % LANE_COLORS.length],
      items: tracked
        .filter((s) => s.severity === severity)
        .map((s) => ({
          id: s.id,
          left: clampPct(s.days_remaining as number),
          label: s.secret_path.split('/').pop() ?? s.secret_path,
          dot: getStatusDotClasses(s.status),
          days: s.days_remaining,
        })),
    }));
  });

  function filterBySeverity(severity: string) {
    clearFilters();
    setSeverity(severity);
    goto('/secrets');
  }

  const gridlines = [
    { left: clampPct(0), label: 'now' },
    { left: clampPct(7), label: '7d' },
    { left: clampPct(30), label: '30d' },
    { left: clampPct(60), label: '60d' },
    { left: clampPct(90), label: '90d' },
  ];
  const nowLeft = clampPct(0);
</script>

<div class="bg-gray-800 border border-gray-700 rounded-lg p-5">
  <div class="flex items-center justify-between mb-4">
    <div class="flex items-baseline gap-3">
      <h2 class="text-base font-semibold text-white">Expiry horizon</h2>
      <span class="text-xs text-gray-500">next 90 days, by severity policy</span>
    </div>
    <div class="hidden sm:flex gap-4 text-xs text-gray-400">
      <span class="flex items-center gap-1.5"><span class="w-2 h-2 rounded-full bg-green-400"></span>Healthy</span>
      <span class="flex items-center gap-1.5"><span class="w-2 h-2 rounded-full bg-yellow-400"></span>Due soon</span>
      <span class="flex items-center gap-1.5"><span class="w-2 h-2 rounded-full bg-red-400"></span>Overdue</span>
    </div>
  </div>

  {#if lanes.length === 0}
    <p class="text-sm text-gray-500 py-6 text-center">No secrets with a rotation policy to plot.</p>
  {:else}
    <div class="relative">
      <!-- gridline / now / overdue overlay, aligned to the track region -->
      <div class="pointer-events-none absolute top-0 bottom-0 right-0" style="left: 7rem;">
        <div class="absolute top-0 bottom-0 left-0 bg-red-500/5 border-r border-dashed border-red-500/40" style="width: {nowLeft}%;"></div>
        {#each gridlines as g}
          <div class="absolute top-0 bottom-0 w-px bg-white/5" style="left: {g.left}%;"></div>
        {/each}
        <div class="absolute top-0 bottom-0 border-l border-indigo-400" style="left: {nowLeft}%;"></div>
      </div>

      <!-- severity lanes -->
      {#each lanes as lane}
        <div class="flex items-center h-12">
          <button
            onclick={() => filterBySeverity(lane.severity)}
            class="w-28 flex-shrink-0 flex items-center gap-2 text-xs text-gray-400 hover:text-white transition-colors group"
            title="Filter secrets by {lane.severity}"
          >
            <span class="w-2 h-2 rounded-sm {lane.color}"></span>
            <span class="truncate group-hover:underline">{lane.severity}</span>
          </button>
          <div class="relative flex-1 h-full">
            {#each lane.items as it (it.id)}
              <div
                class="absolute top-1/2 -translate-x-1/2 -translate-y-1/2 flex flex-col items-center gap-1 w-24"
                style="left: {it.left}%;"
                title="{it.label} · {it.days}d remaining"
              >
                <span class="w-3 h-3 rounded-full border-2 border-gray-800 {it.dot}"></span>
                <span class="font-mono text-[9px] text-gray-400 truncate max-w-24 text-center">{it.label}</span>
              </div>
            {/each}
          </div>
        </div>
      {/each}

      <!-- axis labels -->
      <div class="flex mt-2">
        <div class="w-28 flex-shrink-0"></div>
        <div class="relative flex-1 h-4">
          {#each gridlines as g}
            <span class="absolute -translate-x-1/2 font-mono text-[10px] text-gray-500" style="left: {g.left}%;">{g.label}</span>
          {/each}
        </div>
      </div>
    </div>
  {/if}
</div>
