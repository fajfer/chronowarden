// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

export interface NotificationRoute {
  type: 'email' | 'slack' | 'webhook';
  target: string;
  enabled: boolean;
}

export interface Owner {
  id: string;
  name: string;
  email: string;
  notification_routes: NotificationRoute[];
}
