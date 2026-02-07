// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import type { SecretStatus, SeverityType } from './Secret';

export interface FilterState {
  search: string;
  vaults: string[];
  severities: SeverityType[];
  statuses: SecretStatus[];
  engines: string[];
  owners: string[];
  enabled: boolean | null;
}

export const DEFAULT_FILTERS: FilterState = {
  search: '',
  vaults: [],
  severities: [],
  statuses: [],
  engines: [],
  owners: [],
  enabled: null,
};
