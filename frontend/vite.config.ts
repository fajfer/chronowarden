// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
// SPDX-License-Identifier: EUPL-1.2

import tailwindcss from '@tailwindcss/vite';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()]
});
