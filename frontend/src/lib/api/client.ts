// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

const BASE_URL = '/api/v1';

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const options: RequestInit = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body !== undefined) {
    options.body = JSON.stringify(body);
  }
  const response = await fetch(`${BASE_URL}${path}`, options);
  if (!response.ok) {
    throw new ApiError(response.status, `API error: ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

/**
 * Perform a GET request.
 */
export function apiGet<T>(path: string): Promise<T> {
  return request<T>('GET', path);
}

/**
 * Perform a POST request.
 */
export function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return request<T>('POST', path, body);
}

/**
 * Perform a PUT request.
 */
export function apiPut<T>(path: string, body?: unknown): Promise<T> {
  return request<T>('PUT', path, body);
}

/**
 * Perform a DELETE request.
 */
export function apiDelete<T>(path: string): Promise<T> {
  return request<T>('DELETE', path);
}
