// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

/**
 * Engine types matching the backend EngineType enum.
 */
export type EngineType = 'manual' | 'azure_keyvault' | 'hashicorp_vault' | 'x509';

/**
 * Derived status for UI display based on days until expiry.
 */
export type SecretStatus = 'healthy' | 'warning' | 'critical' | 'expired';

/**
 * Secret model matching the backend Secret pydantic model.
 */
export interface Secret {
  id: number;
  name: string;
  description: string | null;
  is_public: boolean;
  expiry_time_alert: number;
  expiry_time_interval: number;
  owner_id: number;
  routing_ids: number[];
  backend_id: number;
  created_at: string;
  expiry_date: string | null;
  engine_type: EngineType;
}

/**
 * Payload for creating a new secret.
 */
export interface SecretCreate {
  name: string;
  description?: string | null;
  is_public?: boolean;
  expiry_time_alert?: number;
  expiry_time_interval?: number;
  owner_id: number;
  routing_ids?: number[];
  backend_id: number;
  expiry_date?: string | null;
  engine_type: EngineType;
}

/**
 * Payload for updating a secret.
 */
export interface SecretUpdate {
  name?: string;
  description?: string | null;
  is_public?: boolean;
  expiry_time_alert?: number;
  expiry_time_interval?: number;
  routing_ids?: number[];
  expiry_date?: string | null;
}
