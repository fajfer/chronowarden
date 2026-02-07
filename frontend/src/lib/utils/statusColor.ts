// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import type { SecretStatus } from '$lib/types';

/**
 * Determine status from days until expiry.
 */
export function getStatusFromDays(days: number | null | undefined): SecretStatus {
  if (days == null) return 'expired';
  if (days < 0) return 'expired';
  if (days < 14) return 'critical';
  if (days <= 30) return 'warning';
  return 'healthy';
}

/**
 * Get text color class for a status.
 */
export function getStatusColor(status: SecretStatus): string {
  switch (status) {
    case 'healthy': return 'text-green-400';
    case 'warning': return 'text-yellow-400';
    case 'critical': return 'text-red-400';
    case 'expired': return 'text-gray-500';
  }
}

/**
 * Get background color class for a status.
 */
export function getStatusBgColor(status: SecretStatus): string {
  switch (status) {
    case 'healthy': return 'bg-green-500/20';
    case 'warning': return 'bg-yellow-500/20';
    case 'critical': return 'bg-red-500/20';
    case 'expired': return 'bg-gray-500/20';
  }
}

/**
 * Get icon for a status.
 */
export function getStatusIcon(status: SecretStatus): string {
  switch (status) {
    case 'healthy': return '🟢';
    case 'warning': return '🟡';
    case 'critical': return '🔴';
    case 'expired': return '⚫';
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
