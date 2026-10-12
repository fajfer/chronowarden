// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import type { AuditEvent } from '#lib/types/index.js';

type Values = Record<string, unknown> | null;

const LABELS: Record<string, string> = {
  'secret.baseline': 'First seen',
  'secret.metadata': 'Metadata changed in the backend',
  'secret.settings': 'Backend settings changed',
  'secret.version': 'New version (rotated)',
  'secret.config_applied': 'Severity/TTL applied from config',
  'secret.system': 'System changed',
  'secret.owners': 'Owners changed',
  'secret.confirmed': 'Rotation confirmed',
  'secret.privileged': 'Privileged flag changed',
  'secret.removed': 'Removed from the backend',
  'secret.reappeared': 'Back in the backend',
  'secret.purged': 'Purged',
  'system.created': 'System created',
  'system.updated': 'System updated',
  'system.owners': 'System owners changed',
  'system.deleted': 'System deleted',
  'owner.created': 'Owner created',
  'owner.updated': 'Owner updated',
  'owner.deleted': 'Owner deleted',
  'owner.route_added': 'Notification route added',
  'owner.route_deleted': 'Notification route removed',
  'config.baseline': 'Config recorded',
  'config.changed': 'Config changed',
};

/** Event types the backend can revert (it re-checks and explains refusals). */
export function isRevertible(event: AuditEvent): boolean {
  const after = event.after as Values;
  if (after && 'reverts' in after) return false;
  return (
    event.event_type === 'secret.system' ||
    event.event_type === 'secret.owners' ||
    event.event_type === 'secret.privileged' ||
    (event.event_type === 'secret.confirmed' && !(after && 'revoked' in after))
  );
}

export function eventLabel(event: AuditEvent): string {
  return LABELS[event.event_type] ?? event.event_type;
}

/** Where the event happened: the secret's path, or its subject (system, owner, config). */
export function eventTarget(event: AuditEvent): string {
  if (event.vault_name) return `${event.vault_name}/${event.engine_id}/${event.secret_path}`;
  return event.subject ?? '';
}

function show(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'string') return value;
  return JSON.stringify(value);
}

function names(value: unknown): string {
  const list = (value as { name?: string; id: string }[] | null) ?? [];
  return list.length ? list.map((o) => o.name ?? o.id).join(', ') : 'none';
}

/** Key-by-key "old → new" for events whose before/after are flat maps. */
function keyChanges(before: Values, after: Values): string {
  const keys = Array.from(new Set([...Object.keys(before ?? {}), ...Object.keys(after ?? {})])).filter(
    (k) => k !== 'reverts',
  );
  return keys.map((k) => `${k}: ${show(before?.[k])} → ${show(after?.[k])}`).join('; ');
}

/** One-line, human-readable summary of what changed. */
export function describeEvent(event: AuditEvent): string {
  const before = event.before as Values;
  const after = event.after as Values;
  const reverted = after && 'reverts' in after ? ` (reverts #${after.reverts})` : '';
  switch (event.event_type) {
    case 'secret.system': {
      const name = (v: Values) => (v?.system as { name?: string } | null)?.name ?? 'unassigned';
      return `${name(before)} → ${name(after)}${reverted}`;
    }
    case 'secret.owners':
      return `${names(before?.owners)} → ${names(after?.owners)}${reverted}`;
    case 'secret.version': {
      const v = (x: Values) => (x ? `v${x.current}` : '—');
      return `${v(before)} → ${v(after)}${after?.created_time ? ` (created ${after.created_time})` : ''}`;
    }
    case 'secret.confirmed':
      if (after && 'revoked' in after) return `confirmation revoked${reverted}`;
      return `v${after?.version} applied ${after?.applied_at}${after?.confirmed_by ? ` by ${after.confirmed_by}` : ''}`;
    case 'secret.baseline':
      return `version ${(after?.version as Values)?.current ?? '?'}`;
    case 'secret.removed':
    case 'secret.reappeared':
    case 'config.baseline':
    case 'config.changed':
      return '';
    case 'secret.purged':
      return `system ${(before?.system as { name?: string } | null)?.name ?? 'none'}, owners ${names(before?.owners)}`;
    case 'system.created':
    case 'owner.created':
      return show(after?.name);
    case 'system.deleted':
    case 'owner.deleted':
      return show(before?.name);
    case 'owner.route_added':
      return show(after?.address);
    case 'owner.route_deleted':
      return show(before?.address);
    default:
      return keyChanges(before, after);
  }
}
