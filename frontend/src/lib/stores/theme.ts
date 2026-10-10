// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import { derived, writable } from 'svelte/store';
import { fetchApiInfo } from '#lib/api/vaults.js';

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
  return Object.prototype.hasOwnProperty.call(THEME_DEFINITIONS, value);
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

const activeThemeId = writable<ThemeId>(DEFAULT_THEME_ID);

export const availableThemes: ThemeDefinition[] = (
  Object.keys(THEME_DEFINITIONS) as ThemeId[]
).map((themeId) => getTheme(themeId));

export const currentTheme = derived(activeThemeId, ($activeThemeId) => getTheme($activeThemeId));

function applyTheme(themeId: ThemeId): void {
  activeThemeId.set(themeId);
  if (typeof window !== 'undefined') {
    document.documentElement.dataset.theme = themeId;
  }
}

/** Return the theme the user picked earlier, or null if they never chose one. */
function readStoredThemeId(): ThemeId | null {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    return stored && isThemeId(stored) ? stored : null;
  } catch {
    // Ignore storage failures (e.g. blocked/disabled localStorage).
    return null;
  }
}

/**
 * Initialize the theme: the user's own choice wins, otherwise the instance default from `/api/v1/info`
 * (`ui.default_theme` or CHRONOWARDEN_THEME on the backend), otherwise 'default'.
 */
export async function initTheme(): Promise<void> {
  if (typeof window === 'undefined') {
    return;
  }

  const stored = readStoredThemeId();
  if (stored) {
    applyTheme(stored);
    return;
  }

  applyTheme(DEFAULT_THEME_ID);
  try {
    const info = await fetchApiInfo();
    if (readStoredThemeId() === null) {
      applyTheme(normalizeThemeId(info.default_theme));
    }
  } catch {
    // Backend unreachable: keep the built-in default.
  }
}

/** Set the active theme as the user's own choice and persist it for future sessions. */
export function setTheme(themeId: string): void {
  const normalizedThemeId = normalizeThemeId(themeId);
  applyTheme(normalizedThemeId);
  try {
    localStorage.setItem(THEME_STORAGE_KEY, normalizedThemeId);
  } catch {
    // Ignore storage failures (e.g. blocked/disabled localStorage).
  }
}
