// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

export const BASE_URL = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '');

/**
 * API error with HTTP status code, a readable message and the raw response body.
 */
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public body = '',
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

/**
 * Readable message from an error body: FastAPI's `detail` as a string, a `{ message }` object, or a 422 list.
 */
function errorDetail(text: string): string {
  try {
    const detail = JSON.parse(text)?.detail;
    if (typeof detail === 'string') return detail;
    if (detail && typeof detail.message === 'string') return detail.message;
    if (Array.isArray(detail)) return detail.map((d) => d?.msg ?? String(d)).join('; ');
  } catch {
    // not JSON: use the text as it is
  }
  return text;
}

let unauthorizedHandler: (() => void) | null = null;

/** Called when the API answers 401 (session expired or never started); the auth store sends the user to log in. */
export function onUnauthorized(handler: () => void): void {
  unauthorizedHandler = handler;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const options: RequestInit = {
    method,
    // Lets the audit log tell changes made in the UI from other API clients (source `ui`, ADR-014)
    headers: { 'Content-Type': 'application/json', 'X-Chronowarden-Client': 'ui' },
  };
  if (body !== undefined) {
    options.body = JSON.stringify(body);
  }
  const response = await fetch(`${BASE_URL}${path}`, options);
  if (response.status === 401 && path !== '/auth/me') {
    unauthorizedHandler?.();
  }
  if (!response.ok) {
    const text = await response.text().catch(() => response.statusText);
    throw new ApiError(response.status, errorDetail(text), text);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

/** Perform a GET request. */
export function apiGet<T>(path: string): Promise<T> {
  return request<T>('GET', path);
}

/** Perform a POST request. */
export function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return request<T>('POST', path, body);
}

/** Perform a PUT request. */
export function apiPut<T>(path: string, body?: unknown): Promise<T> {
  return request<T>('PUT', path, body);
}

/** Perform a DELETE request. */
export function apiDelete<T = void>(path: string): Promise<T> {
  return request<T>('DELETE', path);
}

