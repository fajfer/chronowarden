// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import type { SecretStatus } from './Secret';

export interface FilterState {
  search: string;
  vaultName: string | null;
  engineId: string | null;
  severity: string | null;
  statuses: SecretStatus[];
  enabled: boolean | null;
}

export const DEFAULT_FILTERS: FilterState = {
  search: '',
  vaultName: null,
  engineId: null,
  severity: null,
  statuses: [],
  enabled: null,
};
