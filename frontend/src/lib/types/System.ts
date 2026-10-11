// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

/**
 * An owner as referenced from a system or a secret.
 */
export interface OwnerRef {
  id: string;
  name: string;
}

/**
 * A system as referenced from a secret.
 */
export interface SystemRef {
  id: string;
  name: string;
}

/**
 * System matching the backend System model (#61, ADR-010).
 */
export interface System {
  id: string;
  name: string;
  description: string;
  cmdb_uri: string | null;
  asset_number: string | null;
  owners: OwnerRef[];
  created_at: string | null;
}

/**
 * Payload for creating a system.
 */
export interface SystemCreate {
  name: string;
  description?: string;
  cmdb_uri?: string | null;
  asset_number?: string | null;
  owner_ids?: string[];
}

/**
 * Payload for updating a system; omitted fields stay unchanged.
 */
export interface SystemUpdate {
  name?: string;
  description?: string;
  cmdb_uri?: string | null;
  asset_number?: string | null;
}

/**
 * What the system form returns: the fields plus the complete owner list.
 */
export interface SystemFormData {
  name: string;
  description: string;
  cmdb_uri: string | null;
  asset_number: string | null;
  owner_ids: string[];
}
