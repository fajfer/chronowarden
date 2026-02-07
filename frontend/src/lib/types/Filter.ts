// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import type { EngineType, SecretStatus } from './Secret';

export interface FilterState {
  search: string;
  engineTypes: EngineType[];
  statuses: SecretStatus[];
  isPublic: boolean | null;
}

export const DEFAULT_FILTERS: FilterState = {
  search: '',
  engineTypes: [],
  statuses: [],
  isPublic: null,
};
