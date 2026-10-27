// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import { BASE_URL, apiDelete, apiGet, apiPost } from './client';
import type { ApiToken, ApiTokenCreate, LogoutResult, Me, NewApiToken } from '#lib/types/index.js';

/** GET /api/v1/auth/me — the caller; 401 when not logged in. */
export function fetchMe(): Promise<Me> {
  return apiGet<Me>('/auth/me');
}

/** POST /api/v1/auth/logout — end the session. */
export function postLogout(): Promise<LogoutResult> {
  return apiPost<LogoutResult>('/auth/logout');
}

/** URL of GET /api/v1/auth/login, which redirects to the identity provider and back to `next`. */
export function loginUrl(next: string): string {
  return `${BASE_URL}/auth/login?${new URLSearchParams({ next })}`;
}

/** GET /api/v1/auth/tokens — every API token (admin). */
export function fetchApiTokens(): Promise<ApiToken[]> {
  return apiGet<ApiToken[]>('/auth/tokens');
}

/** POST /api/v1/auth/tokens — issue a token; its value is in the response only. */
export function createApiToken(data: ApiTokenCreate): Promise<NewApiToken> {
  return apiPost<NewApiToken>('/auth/tokens', data);
}

/** DELETE /api/v1/auth/tokens/:id — revoke a token. */
export function revokeApiToken(id: string): Promise<ApiToken> {
  return apiDelete<ApiToken>(`/auth/tokens/${id}`);
}
