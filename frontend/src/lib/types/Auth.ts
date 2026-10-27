// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

/** How users log in (`auth.mode`, ADR-015). */
export type AuthMode = 'oidc' | 'proxy' | 'none';

/** Roles, highest first (ADR-026). */
export type Role = 'admin' | 'owner' | 'viewer';

/**
 * The caller, matching the backend Me model.
 */
export interface Me {
  auth_mode: AuthMode;
  name: string;
  email: string | null;
  role: Role;
  kind: 'session' | 'token' | 'proxy' | 'anonymous';
  /** Owners the caller acts for (email or IdP group match). */
  owner_ids: string[];
}

/**
 * Response of POST /auth/logout.
 */
export interface LogoutResult {
  /** The proxy's sign-out URL, when there is one. */
  logout_url: string | null;
}

/**
 * An API token as listed; its value is never shown again.
 */
export interface ApiToken {
  id: string;
  name: string;
  role: Role;
  owner_id: string | null;
  created_at: string;
  expires_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
}

/**
 * Payload for creating an API token.
 */
export interface ApiTokenCreate {
  name: string;
  role: Role;
  owner_id?: string | null;
  expires_in_days: number;
}

/**
 * A token just created, with its value (shown once).
 */
export interface NewApiToken extends ApiToken {
  token: string;
}
