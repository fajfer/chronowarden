// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import { format, formatDistanceToNow } from 'date-fns';

/**
 * Format a date string to a readable format.
 */
export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  try {
    return format(new Date(dateStr), 'MMM d, yyyy');
  } catch {
    return '—';
  }
}

/**
 * Format a date string to a relative time string.
 */
export function formatRelative(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  try {
    return formatDistanceToNow(new Date(dateStr), { addSuffix: true });
  } catch {
    return '—';
  }
}

/**
 * Calculate days until a given expiry date.
 */
export function getDaysUntilExpiry(expiryDate: string | null | undefined): number | null {
  if (!expiryDate) return null;
  try {
    const now = new Date();
    const expiry = new Date(expiryDate);
    const diffMs = expiry.getTime() - now.getTime();
    return Math.ceil(diffMs / (1000 * 60 * 60 * 24));
  } catch {
    return null;
  }
}
