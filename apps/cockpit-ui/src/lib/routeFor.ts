// Single source of truth for role → default route. Used by the route guards
// (beforeLoad redirects) and by the user-switcher's post-select navigation.

import type { Role } from './types/user';

export type DefaultRoute = '/queue' | '/approvals' | '/regulator-lens';

export function defaultRouteFor(role: Role): DefaultRoute {
  switch (role) {
    case 'analyst':
      return '/queue';
    case 'team_lead':
      return '/approvals';
    case 'regulator':
      return '/regulator-lens';
  }
}
