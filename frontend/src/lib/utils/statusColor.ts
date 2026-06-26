// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import type { SecretStatus } from '$lib/types';

/**
 * Determine status from days until expiry.
 */
export function getStatusFromDays(days: number | null | undefined): SecretStatus {
  if (days == null) return 'no_ttl';
  if (days <= 0) return 'expired';
  if (days <= 30) return 'warning';
  return 'ok';
}

/**
 * Get text color class for a status.
 */
export function getStatusColor(status: SecretStatus): string {
  switch (status) {
    case 'ok': return 'text-green-400';
    case 'warning': return 'text-yellow-400';
    case 'expired': return 'text-red-400';
    case 'no_ttl': return 'text-gray-500';
  }
}

/**
 * Get background color class for a status.
 */
export function getStatusBgColor(status: SecretStatus): string {
  switch (status) {
    case 'ok': return 'bg-green-500/20';
    case 'warning': return 'bg-yellow-500/20';
    case 'expired': return 'bg-red-500/20';
    case 'no_ttl': return 'bg-gray-500/20';
  }
}

/**
 * Get icon for a status.
 */
export function getStatusIcon(status: SecretStatus): string {
  switch (status) {
    case 'ok': return '🟢';
    case 'warning': return '🟡';
    case 'expired': return '🔴';
    case 'no_ttl': return '⚫';
  }
}

/**
 * Get color class for a severity level.
 */
export function getSeverityColor(severity: string): string {
  switch (severity) {
    case 'critical': return 'text-red-400 border-red-500';
    case 'pci-dss-4.0': return 'text-orange-400 border-orange-500';
    case 'default': return 'text-blue-400 border-blue-500';
    case 'none': return 'text-gray-400 border-gray-500';
    default: return 'text-gray-400 border-gray-500';
  }
}

/**
 * Human-friendly label for a status.
 */
export function getStatusLabel(status: SecretStatus): string {
  switch (status) {
    case 'ok': return 'Healthy';
    case 'warning': return 'Warning';
    case 'expired': return 'Overdue';
    case 'no_ttl': return 'No TTL';
  }
}

/**
 * Solid background colour class for a status dot.
 */
export function getStatusDotBg(status: SecretStatus): string {
  switch (status) {
    case 'ok': return 'bg-green-400';
    case 'warning': return 'bg-yellow-400';
    case 'expired': return 'bg-red-400';
    case 'no_ttl': return 'bg-gray-500';
  }
}

/**
 * Dot classes (fill + soft ring) for timeline / chart markers.
 */
export function getStatusDotClasses(status: SecretStatus): string {
  switch (status) {
    case 'ok': return 'bg-green-400 ring-4 ring-green-400/20';
    case 'warning': return 'bg-yellow-400 ring-4 ring-yellow-400/20';
    case 'expired': return 'bg-red-400 ring-4 ring-red-400/20';
    case 'no_ttl': return 'bg-gray-500 ring-4 ring-gray-500/20';
  }
}
