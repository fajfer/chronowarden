// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import { apiGet } from './client';
import type { Delivery, FiringAlert } from '#lib/types/index.js';

/** GET /api/v1/alerts — alerts firing now, oldest first. */
export function fetchFiringAlerts(): Promise<FiringAlert[]> {
  return apiGet<FiringAlert[]>('/alerts');
}

/** GET /api/v1/webhooks/deliveries — the webhook delivery log, newest first. */
export function fetchDeliveries(limit = 100): Promise<Delivery[]> {
  return apiGet<Delivery[]>(`/webhooks/deliveries?limit=${limit}`);
}
