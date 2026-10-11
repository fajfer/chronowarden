<script lang="ts">
  // SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
  //
  // SPDX-License-Identifier: EUPL-1.2

  import GapDialog from '#lib/components/GapDialog.svelte';
  import SecretModal from '#lib/components/SecretModal.svelte';
  import {
    createSnapshot, fetchComplianceSettings, fetchComplianceSummary, fetchGaps, fetchPeriods, fetchSnapshots,
    snapshotExportUrl,
  } from '#lib/api/compliance.js';
  import { fetchSystems } from '#lib/api/systems.js';
  import { secrets } from '#lib/stores/secrets.js';
  import { addToast } from '#lib/stores/sync.js';
  import { formatDate } from '#lib/utils/dateFormat.js';
  import type {
    ComplianceScope, ComplianceSummary, GapReport, PeriodStatus, Secret, SnapshotInfo, SnapshotRequest, System,
  } from '#lib/types/index.js';

  type Tab = 'overview' | 'snapshots' | 'tree' | 'settings';
  let tab = $state<Tab>('overview');

  let summary = $state<ComplianceSummary | null>(null);
  let periods = $state<PeriodStatus[]>([]);
  let snapshots = $state<SnapshotInfo[]>([]);
  let settings = $state<Record<string, unknown> | null>(null);
  let systems = $state<System[]>([]);
  let selectedSecret = $state<Secret | null>(null);

  // Ad-hoc snapshot form
  let label = $state('');
  let scopeVault = $state('');
  let scopeSystem = $state('');
  let privilegedOnly = $state(false);

  // Gap dialog for the snapshot about to be taken
  let pending = $state<SnapshotRequest | null>(null);
  let pendingTitle = $state('');
  let gapReport = $state<GapReport | null>(null);
  let freezing = $state(false);

  // Tree view
  let treeBy = $state<'vault' | 'system'>('vault');

  const openPeriods = $derived(periods.filter((p) => p.snapshot_id === null));
  const vaultNames = $derived(Array.from(new Set($secrets.map((s) => s.vault_name))).sort());

  async function loadAll() {
    const results = await Promise.allSettled([
      fetchComplianceSummary(), fetchPeriods(), fetchSnapshots(), fetchComplianceSettings(), fetchSystems(),
    ]);
    if (results[0].status === 'fulfilled') summary = results[0].value;
    if (results[1].status === 'fulfilled') periods = results[1].value;
    if (results[2].status === 'fulfilled') snapshots = results[2].value;
    if (results[3].status === 'fulfilled') settings = results[3].value;
    if (results[4].status === 'fulfilled') systems = results[4].value;
  }

  function adhocScope(): ComplianceScope {
    return {
      vaults: scopeVault ? [scopeVault] : [],
      engines: [],
      systems: scopeSystem ? [scopeSystem] : [],
      privileged_only: privilegedOnly,
    };
  }

  async function prepare(request: SnapshotRequest, title: string) {
    try {
      gapReport = await fetchGaps(request.scope ?? null, request.cadence);
      pending = request;
      pendingTitle = title;
    } catch (err) {
      addToast(err instanceof Error ? err.message : 'Checking gaps failed', 'error');
    }
  }

  function prepareAdhoc() {
    if (!label.trim()) return;
    const scope = adhocScope();
    prepare({ label: label.trim(), scope }, `Snapshot "${label.trim()}"`);
  }

  function prepareClose(period: PeriodStatus) {
    prepare({ cadence: period.cadence, period: period.period }, `Close ${period.period} (${period.cadence})`);
  }

  async function freeze() {
    if (!pending) return;
    freezing = true;
    try {
      const created = await createSnapshot(pending);
      addToast(`Snapshot #${created.id} frozen (${created.row_count} secrets)`, 'success');
      label = '';
      cancel();
      tab = 'snapshots';
      await loadAll();
    } catch (err) {
      addToast(err instanceof Error ? err.message : 'Freezing the snapshot failed', 'error');
    } finally {
      freezing = false;
    }
  }

  function cancel() {
    pending = null;
    gapReport = null;
  }

  interface TreeNode {
    key: string;
    label: string;
    secrets: Secret[];
    children: TreeNode[];
  }

  function counts(list: Secret[]) {
    return {
      total: list.length,
      privileged: list.filter((s) => s.privileged).length,
      expired: list.filter((s) => s.status === 'expired').length,
      warning: list.filter((s) => s.status === 'warning').length,
      noTtl: list.filter((s) => s.status === 'no_ttl').length,
    };
  }

  function groupBy(list: Secret[], key: (s: Secret) => string): Map<string, Secret[]> {
    const groups = new Map<string, Secret[]>();
    for (const s of list) groups.set(key(s), [...(groups.get(key(s)) ?? []), s]);
    return new Map([...groups.entries()].sort(([a], [b]) => a.localeCompare(b)));
  }

  const tree = $derived.by((): TreeNode[] => {
    if (treeBy === 'system') {
      return [...groupBy($secrets, (s) => s.system?.name ?? '~Unassigned').entries()].map(([name, list]) => ({
        key: name, label: name === '~Unassigned' ? 'Unassigned' : name, secrets: list, children: [],
      }));
    }
    return [...groupBy($secrets, (s) => s.vault_name).entries()].map(([vault, list]) => ({
      key: vault,
      label: vault,
      secrets: list,
      children: [...groupBy(list, (s) => s.engine_id).entries()].map(([engine, engineList]) => ({
        key: `${vault}/${engine}`, label: engine, secrets: engineList, children: [],
      })),
    }));
  });

  $effect(() => {
    loadAll();
  });

  const tabs: { id: Tab; label: string }[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'snapshots', label: 'Snapshots' },
    { id: 'tree', label: 'Tree' },
    { id: 'settings', label: 'Settings' },
  ];
  const inputClass =
    'bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-indigo-500';
</script>

{#snippet countBadges(list: Secret[])}
  {@const c = counts(list)}
  <span class="ml-auto flex gap-2 font-mono text-xs">
    {#if c.expired}<span class="text-red-400" title="Overdue">{c.expired}</span>{/if}
    {#if c.warning}<span class="text-yellow-400" title="Due soon">{c.warning}</span>{/if}
    {#if c.noTtl}<span class="text-gray-500" title="No TTL">{c.noTtl}</span>{/if}
    {#if c.privileged}<span class="text-rose-300" title="Privileged">{c.privileged}P</span>{/if}
    <span class="text-gray-400" title="Total">{c.total}</span>
  </span>
{/snippet}

{#snippet secretLeaves(list: Secret[])}
  <ul class="ml-6 border-l border-gray-700/60">
    {#each list as s (s.id)}
      <li>
        <button onclick={() => (selectedSecret = s)} class="flex w-full items-center gap-2 px-3 py-1 text-left text-xs hover:bg-gray-700/30">
          <span class="font-mono text-gray-300">{s.secret_path}</span>
          {#if s.privileged}<span class="text-[10px] uppercase text-rose-300">privileged</span>{/if}
          <span class="ml-auto text-gray-500">{s.status}</span>
        </button>
      </li>
    {/each}
  </ul>
{/snippet}

<div class="space-y-5">
  <div>
    <h1 class="text-2xl font-bold text-white">Compliance</h1>
    <p class="mt-1 text-sm text-gray-400">Inventory and evidence for your reviews: summaries, frozen snapshots, the tree and settings</p>
  </div>

  <div class="flex gap-1 border-b border-gray-700">
    {#each tabs as t}
      <button onclick={() => (tab = t.id)}
              class="border-b-2 px-4 py-2 text-sm font-medium transition-colors {tab === t.id ? 'border-indigo-500 text-indigo-400' : 'border-transparent text-gray-400 hover:text-gray-300'}">
        {t.label}
      </button>
    {/each}
    <a href="/audit" class="border-b-2 border-transparent px-4 py-2 text-sm font-medium text-gray-400 hover:text-gray-300">Audit log</a>
  </div>

  {#if tab === 'overview'}
    {#each openPeriods as period (period.cadence + period.period)}
      <div class="flex items-center justify-between rounded-lg border border-amber-700 bg-amber-900/20 px-4 py-3 text-sm text-amber-200">
        <span>{period.period} ({period.cadence}) ended {formatDate(period.end)}: close it to freeze its snapshot.</span>
        <button onclick={() => prepareClose(period)} class="rounded-lg bg-amber-600 px-3 py-1.5 text-white hover:bg-amber-500">Close {period.period}</button>
      </div>
    {/each}
    {#if summary}
      <div class="grid grid-cols-1 gap-5 lg:grid-cols-3">
        {#each [['By vault', summary.by_vault, (g: { vault?: string }) => g.vault], ['By engine', summary.by_engine, (g: { vault?: string; engine?: string }) => `${g.vault}/${g.engine}`], ['By system', summary.by_system, (g: { system?: string | null }) => g.system ?? 'Unassigned']] as const as [title, groups, name]}
          <div class="overflow-hidden rounded-lg border border-gray-700 bg-gray-800">
            <div class="border-b border-gray-700 px-5 py-3 text-sm font-semibold text-white">{title}</div>
            <table class="w-full text-sm">
              <thead><tr class="text-xs uppercase text-gray-500"><th class="px-5 py-2 text-left">Name</th><th class="px-3 py-2 text-right">Total</th><th class="px-5 py-2 text-right">Privileged</th></tr></thead>
              <tbody>
                {#each groups as group}
                  <tr class="border-t border-gray-700/50"><td class="px-5 py-2 text-gray-200">{name(group)}</td><td class="px-3 py-2 text-right font-mono text-gray-300">{group.total}</td><td class="px-5 py-2 text-right font-mono text-rose-300">{group.privileged}</td></tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/each}
      </div>
    {/if}
  {:else if tab === 'snapshots'}
    <div class="space-y-3 rounded-lg border border-gray-700 bg-gray-800 p-5">
      <h2 class="text-sm font-semibold text-white">Take an ad-hoc snapshot</h2>
      <div class="flex flex-wrap items-end gap-2">
        <label class="text-xs text-gray-500">Label<input class="{inputClass} mt-1 block w-56" placeholder="e.g. Audit prep October" bind:value={label} /></label>
        <label class="text-xs text-gray-500">Vault
          <select class="{inputClass} mt-1 block" bind:value={scopeVault}>
            <option value="">All vaults</option>
            {#each vaultNames as v}<option value={v}>{v}</option>{/each}
          </select>
        </label>
        <label class="text-xs text-gray-500">System
          <select class="{inputClass} mt-1 block" bind:value={scopeSystem}>
            <option value="">All systems</option>
            {#each systems as s (s.id)}<option value={s.name}>{s.name}</option>{/each}
          </select>
        </label>
        <label class="flex items-center gap-2 pb-2 text-sm text-gray-300"><input type="checkbox" bind:checked={privilegedOnly} class="accent-rose-500" /> Privileged only</label>
        <button onclick={prepareAdhoc} disabled={!label.trim()}
                class="rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-500 disabled:opacity-50">Check gaps and freeze</button>
      </div>
    </div>
    <div class="overflow-hidden rounded-lg border border-gray-700 bg-gray-800">
      {#if snapshots.length === 0}
        <p class="px-5 py-6 text-sm text-gray-500">No snapshots yet.</p>
      {:else}
        <table class="w-full text-sm">
          <thead><tr class="text-xs uppercase text-gray-500"><th class="px-5 py-2 text-left">#</th><th class="px-3 py-2 text-left">Frozen</th><th class="px-3 py-2 text-left">What</th><th class="px-3 py-2 text-right">Secrets</th><th class="px-3 py-2 text-left">SHA-256</th><th class="px-5 py-2"></th></tr></thead>
          <tbody>
            {#each snapshots as s (s.id)}
              <tr class="border-t border-gray-700/50">
                <td class="px-5 py-2 font-mono text-gray-400">{s.id}</td>
                <td class="px-3 py-2 text-gray-300">{formatDate(s.created_at)}</td>
                <td class="px-3 py-2 text-gray-200">
                  {s.label ?? `${s.period} (${s.cadence})`}
                  {#if s.supersedes}<span class="text-xs text-gray-500"> corrects #{s.supersedes}</span>{/if}
                </td>
                <td class="px-3 py-2 text-right font-mono text-gray-300">{s.row_count}</td>
                <td class="px-3 py-2 font-mono text-xs text-gray-500" title={s.sha256}>{s.sha256.slice(0, 16)}…</td>
                <td class="whitespace-nowrap px-5 py-2 text-right text-xs">
                  <a href={snapshotExportUrl(s.id, 'json')} download class="text-indigo-400 hover:text-indigo-300">JSON</a>
                  <a href={snapshotExportUrl(s.id, 'csv')} download class="ml-2 text-indigo-400 hover:text-indigo-300">CSV</a>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}
    </div>
  {:else if tab === 'tree'}
    <div class="flex gap-2 text-sm">
      {#each [['vault', 'Vault → engine'], ['system', 'System']] as const as [id, name]}
        <button onclick={() => (treeBy = id)} class="rounded-full px-3 py-1 {treeBy === id ? 'bg-indigo-600 text-white' : 'bg-gray-700 text-gray-300'}">{name}</button>
      {/each}
    </div>
    <div class="rounded-lg border border-gray-700 bg-gray-800 py-2">
      {#each tree as node (node.key)}
        <details>
          <summary class="flex cursor-pointer items-center gap-2 px-4 py-1.5 text-sm text-gray-200 hover:bg-gray-700/30">{node.label}{@render countBadges(node.secrets)}</summary>
          {#if node.children.length}
            {#each node.children as child (child.key)}
              <details class="ml-4">
                <summary class="flex cursor-pointer items-center gap-2 px-4 py-1 text-sm text-gray-300 hover:bg-gray-700/30"><span class="font-mono">{child.label}</span>{@render countBadges(child.secrets)}</summary>
                {@render secretLeaves(child.secrets)}
              </details>
            {/each}
          {:else}
            {@render secretLeaves(node.secrets)}
          {/if}
        </details>
      {/each}
    </div>
  {:else}
    <div class="space-y-2 rounded-lg border border-gray-700 bg-gray-800 p-5 text-sm">
      <p class="text-gray-400">Set in <code class="text-gray-300">config.yaml</code>; editing here comes with authentication (0.9).</p>
      <pre class="overflow-x-auto rounded bg-gray-900 p-4 text-xs text-gray-300">{JSON.stringify(settings, null, 2)}</pre>
    </div>
  {/if}
</div>

<GapDialog report={gapReport} title={pendingTitle} busy={freezing} onConfirm={freeze} onCancel={cancel} />
<SecretModal secret={selectedSecret} onClose={() => (selectedSecret = null)} />
