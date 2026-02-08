// SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
// SPDX-License-Identifier: EUPL-1.2

import { test, expect } from '@playwright/test';

test('dashboard loads successfully', async ({ page }) => {
	await page.goto('/');
	await expect(page).toHaveTitle(/Chronowarden|Dashboard/i);
});

test('dashboard shows connected vaults', async ({ page }) => {
	await page.goto('/');
	await expect(page.locator('text=dev-openbao')).toBeVisible({ timeout: 10000 });
	await expect(page.locator('text=dev-vault-1.21.3')).toBeVisible({ timeout: 10000 });
	await expect(page.locator('text=dev-vault-1.20.1')).toBeVisible({ timeout: 10000 });
});
