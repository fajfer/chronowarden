// SPDX-FileCopyrightText: 2025 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

/**
 * Type definitions for Chronowarden API
 */

export type EngineType = 'manual' | 'azure_keyvault' | 'hashicorp_vault' | 'x509';
export type RouterType = 'email' | 'webhook' | 'slack';
export type PermissionLevel = 'read-only' | 'read-write' | 'admin';

export interface Secret {
  id: number;
  name: string;
  description: string | null;
  is_public: boolean;
  created_at: string;
  expiry_date: string | null;
  expiry_time_alert: number;
  expiry_time_interval: number;
  owner_id: number;
  routing_ids: number[];
  backend_id: number;
  engine_type: EngineType;
}

export interface SecretCreate {
  name: string;
  description?: string;
  is_public?: boolean;
  expiry_date?: string;
  expiry_time_alert?: number;
  expiry_time_interval?: number;
  owner_id: number;
  routing_ids?: number[];
  backend_id: number;
  engine_type: EngineType;
}

export interface SecretUpdate {
  name?: string;
  description?: string;
  is_public?: boolean;
  expiry_date?: string;
  expiry_time_alert?: number;
  expiry_time_interval?: number;
  routing_ids?: number[];
}

export interface VaultConnection {
  address: string;
  token: string;
  namespace?: string;
  mount_path?: string;
  verify_ssl?: boolean;
}

export interface VaultHealth {
  connected: boolean;
  healthy: boolean;
  initialized?: boolean;
  sealed?: boolean;
  version?: string;
  error?: string;
}

export interface ApiHealth {
  status: string;
}

export interface ApiInfo {
  name: string;
  version: string;
  docs: string;
}
