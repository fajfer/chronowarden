// SPDX-FileCopyrightText: 2025 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

/**
 * API service for Chronowarden backend
 */

import type { Secret, SecretCreate, SecretUpdate, VaultConnection, VaultHealth, ApiHealth, ApiInfo } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * Generic fetch wrapper with error handling
 */
async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP error ${response.status}`);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

/**
 * API health check
 */
export async function getHealth(): Promise<ApiHealth> {
  return fetchApi<ApiHealth>('/health');
}

/**
 * Get API info
 */
export async function getApiInfo(): Promise<ApiInfo> {
  return fetchApi<ApiInfo>('/');
}

// Secrets API

/**
 * List all secrets
 */
export async function listSecrets(engineType?: string, isPublic?: boolean): Promise<Secret[]> {
  const params = new URLSearchParams();
  if (engineType) params.append('engine_type', engineType);
  if (isPublic !== undefined) params.append('is_public', String(isPublic));
  
  const query = params.toString();
  return fetchApi<Secret[]>(`/api/v1/secrets/${query ? `?${query}` : ''}`);
}

/**
 * Get public secrets (no auth required)
 */
export async function listPublicSecrets(): Promise<Secret[]> {
  return fetchApi<Secret[]>('/api/v1/secrets/public/');
}

/**
 * Get a secret by ID
 */
export async function getSecret(id: number): Promise<Secret> {
  return fetchApi<Secret>(`/api/v1/secrets/${id}`);
}

/**
 * Create a new secret
 */
export async function createSecret(secret: SecretCreate): Promise<Secret> {
  return fetchApi<Secret>('/api/v1/secrets/', {
    method: 'POST',
    body: JSON.stringify(secret),
  });
}

/**
 * Update a secret
 */
export async function updateSecret(id: number, secret: SecretUpdate): Promise<Secret> {
  return fetchApi<Secret>(`/api/v1/secrets/${id}`, {
    method: 'PUT',
    body: JSON.stringify(secret),
  });
}

/**
 * Delete a secret
 */
export async function deleteSecret(id: number): Promise<void> {
  return fetchApi<void>(`/api/v1/secrets/${id}`, {
    method: 'DELETE',
  });
}

// Vault API

/**
 * Connect to HashiCorp Vault
 */
export async function connectVault(connection: VaultConnection): Promise<{ message: string }> {
  return fetchApi<{ message: string }>('/api/v1/vault/connect', {
    method: 'POST',
    body: JSON.stringify(connection),
  });
}

/**
 * Disconnect from Vault
 */
export async function disconnectVault(): Promise<{ message: string }> {
  return fetchApi<{ message: string }>('/api/v1/vault/disconnect', {
    method: 'POST',
  });
}

/**
 * Get Vault health status
 */
export async function getVaultHealth(): Promise<VaultHealth> {
  return fetchApi<VaultHealth>('/api/v1/vault/health');
}

/**
 * Get a secret from Vault
 */
export async function getVaultSecret(path: string, key?: string): Promise<{ data: Record<string, unknown> }> {
  return fetchApi<{ data: Record<string, unknown> }>('/api/v1/vault/secrets/get', {
    method: 'POST',
    body: JSON.stringify({ path, key }),
  });
}

/**
 * List secrets in Vault
 */
export async function listVaultSecrets(path: string = ''): Promise<{ secrets: string[] }> {
  const params = new URLSearchParams({ path });
  return fetchApi<{ secrets: string[] }>(`/api/v1/vault/secrets/list?${params}`);
}
