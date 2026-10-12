// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

/** An alert firing now (GET /alerts). */
export interface FiringAlert {
  fingerprint: string;
  alertname: string;
  labels: Record<string, string>;
  annotations: Record<string, string>;
  starts_at: string;
  last_sent_at: string | null;
}

/** One webhook in the delivery log (GET /webhooks/deliveries); no payload, no URL. */
export interface Delivery {
  id: number;
  created_at: string;
  receiver: string;
  route_id: string | null;
  default_route: string | null;
  alertname: string;
  fingerprint: string | null;
  status: 'pending' | 'delivered' | 'failed';
  attempts: number;
  next_attempt_at: string | null;
  last_attempt_at: string | null;
  last_status_code: number | null;
  last_error: string | null;
}

/** A route's new signing secret, returned only once. */
export interface SigningSecret {
  route_id: string;
  secret: string;
}

/** The outcome of a test webhook. */
export interface RouteTestResult {
  success: boolean;
  status_code: number | null;
  message: string;
}
