// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

import type { SecretStatus } from './Secret';

export interface FilterState {
  search: string;
  vaultName: string | null;
  engineId: string | null;
  severity: string | null;
  /** System ID, `UNASSIGNED_SYSTEM` for secrets without a system, or null for all. */
  systemId: string | null;
  /** Only secrets with the privileged flag. */
  privilegedOnly: boolean;
  statuses: SecretStatus[];
}

/** Filter value for secrets without a system. */
export const UNASSIGNED_SYSTEM = '__unassigned__';

export const DEFAULT_FILTERS: FilterState = {
  search: '',
  vaultName: null,
  engineId: null,
  severity: null,
  systemId: null,
  privilegedOnly: false,
  statuses: [],
};
