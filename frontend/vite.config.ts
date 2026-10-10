import adapter from '@sveltejs/adapter-static';

// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
// SPDX-License-Identifier: EUPL-1.2

import tailwindcss from '@tailwindcss/vite';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		tailwindcss(),
		sveltekit({
			adapter: adapter({
				pages: 'build',
				assets: 'build',
				fallback: 'index.html',
				strict: false
			})
		})
	],
	server: {
		proxy: {
			'/api': {
				target: 'http://localhost:8000',
				changeOrigin: true,
			},
			'/docs': {
				target: 'http://localhost:8000',
				changeOrigin: true,
			},
			'/openapi.json': {
				target: 'http://localhost:8000',
				changeOrigin: true,
			},
		},
	},
});
