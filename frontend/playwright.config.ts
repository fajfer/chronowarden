// SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
// SPDX-License-Identifier: EUPL-1.2

import { defineConfig } from '@playwright/test';

export default defineConfig({
	testDir: './e2e',
	fullyParallel: false,
	forbidOnly: !!process.env.CI,
	retries: process.env.CI ? 2 : 0,
	workers: 1,
	reporter: [['html'], ['github']],
	use: {
		baseURL: 'http://localhost:5173',
		trace: 'on-first-retry',
		screenshot: 'only-on-failure'
	},
	webServer: [
		{
			command: 'cd .. && uv run uvicorn chronowarden:app',
			url: 'http://localhost:8000/health',
			timeout: 30 * 1000,
			reuseExistingServer: !process.env.CI
		},
		{
			command: 'npm run dev',
			url: 'http://localhost:5173',
			timeout: 30 * 1000,
			reuseExistingServer: !process.env.CI
		}
	]
});
