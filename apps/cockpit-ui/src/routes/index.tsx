// Root index — redirects to the active user's default route (Story 1.4).

import { createRoute, redirect } from '@tanstack/react-router';
import { Route as RootRoute } from './__root';
import { defaultRouteFor } from '@/lib/routeFor';
import { useCurrentUser } from '@/stores/currentUser';

export const Route = createRoute({
  getParentRoute: () => RootRoute,
  path: '/',
  beforeLoad: () => {
    const { user } = useCurrentUser.getState();
    throw redirect({ to: defaultRouteFor(user.role) });
  },
});
