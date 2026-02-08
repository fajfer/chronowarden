// SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
// SPDX-License-Identifier: EUPL-1.2

import { test, expect } from '@playwright/test';

test('API health endpoint responds', async ({ request }) => {
	const health = await request.get('http://localhost:8000/api/v1/health');
	expect(health.ok()).toBeTruthy();
});

test('API vault instances endpoint responds', async ({ request }) => {
	const vaults = await request.get('http://localhost:8000/api/v1/vault/instances');
	expect(vaults.ok()).toBeTruthy();

	const data = await vaults.json();
	expect(data.instances).toBeDefined();
	expect(data.instances.length).toBeGreaterThanOrEqual(3);
});

test('API vault health endpoint responds', async ({ request }) => {
	const health = await request.get('http://localhost:8000/api/v1/vault/health');
	expect(health.ok()).toBeTruthy();

	const data = await health.json();
	expect(data.length).toBeGreaterThanOrEqual(3);
	expect(data[0].connected).toBe(true);
});
