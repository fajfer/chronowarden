// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

const BASE_URL = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '');

/**
 * API error with HTTP status code.
 */
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
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
    const text = await response.text().catch(() => response.statusText);
    throw new ApiError(response.status, errorDetail(text));
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

/** Perform a PATCH request. */
export function apiPatch<T>(path: string, body?: unknown): Promise<T> {
  return request<T>('PATCH', path, body);
}
