// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

/**
 * Return a URL only if it is http(s), for use as an href; anything else (javascript:, data:) gives null.
 * The backend validates CMDB links too; this guards data stored before that check (0.7.1).
 */
export function safeHttpUrl(url: string | null | undefined): string | null {
  return url && /^https?:\/\//i.test(url.trim()) ? url.trim() : null;
}
