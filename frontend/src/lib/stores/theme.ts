// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import { env } from '$env/dynamic/public';
import { derived, writable } from 'svelte/store';

const THEME_STORAGE_KEY = 'chronowarden_theme';

const THEME_DEFINITIONS = {
  default: {
    label: 'Default',
    logo: {
      src: '/logo.png',
      alt: 'Chronowarden',
    },
    mascot: {
      src: '/goat.png',
      alt: 'Chronowarden goat mascot',
    },
  },
  bison: {
    label: 'Bison',
    logo: {
      src: '/logo-bison.png',
      alt: 'Chronowarden',
    },
    mascot: {
      src: '/goat-bison.png',
      alt: 'Chronowarden bison goat mascot',
    },
  },
} as const;

export type ThemeId = keyof typeof THEME_DEFINITIONS;

export interface ThemeDefinition {
  id: ThemeId;
  label: string;
  logo: {
    src: string;
    alt: string;
  };
  mascot: {
    src: string;
    alt: string;
  };
}

const DEFAULT_THEME_ID: ThemeId = 'default';

function isThemeId(value: string): value is ThemeId {
  return value in THEME_DEFINITIONS;
}

function normalizeThemeId(candidate: string | null | undefined): ThemeId {
  if (!candidate) {
    return DEFAULT_THEME_ID;
  }

  const normalized = candidate.trim().toLowerCase();
  if (isThemeId(normalized)) {
    return normalized;
  }

  return DEFAULT_THEME_ID;
}

function getTheme(themeId: ThemeId): ThemeDefinition {
  const definition = THEME_DEFINITIONS[themeId];
  return {
    id: themeId,
    label: definition.label,
    logo: {
      src: definition.logo.src,
      alt: definition.logo.alt,
    },
    mascot: {
      src: definition.mascot.src,
      alt: definition.mascot.alt,
    },
  };
}

const configuredThemeId = normalizeThemeId(env.PUBLIC_CHRONOWARDEN_THEME);
const activeThemeId = writable<ThemeId>(configuredThemeId);

export const availableThemes: ThemeDefinition[] = (
  Object.keys(THEME_DEFINITIONS) as ThemeId[]
).map((themeId) => getTheme(themeId));

export const currentTheme = derived(activeThemeId, ($activeThemeId) => getTheme($activeThemeId));

function applyTheme(themeId: ThemeId): void {
  if (typeof window === 'undefined') {
    return;
  }

  document.documentElement.dataset.theme = themeId;

  try {
    localStorage.setItem(THEME_STORAGE_KEY, themeId);
  } catch {
    // Ignore storage failures (e.g. blocked/disabled localStorage).
  }
}

/** Initialize theme from local storage or configured default. */
export function initTheme(): void {
  if (typeof window === 'undefined') {
    return;
  }

  let storedThemeId = configuredThemeId;
  try {
    storedThemeId = normalizeThemeId(localStorage.getItem(THEME_STORAGE_KEY));
  } catch {
    // Ignore storage failures and fall back to configured default.
  }

  activeThemeId.set(storedThemeId);
  applyTheme(storedThemeId);
}

/** Set active theme and persist it for future sessions. */
export function setTheme(themeId: string): void {
  const normalizedThemeId = normalizeThemeId(themeId);
  activeThemeId.set(normalizedThemeId);
  applyTheme(normalizedThemeId);
}