// /queue — analyst route (Story 1.4 AC #7). Story 4-1 will populate this.

import { createRoute, redirect } from '@tanstack/react-router';
import { Route as RootRoute } from './__root';
import { defaultRouteFor } from '@/lib/routeFor';
import { useCurrentUser } from '@/stores/currentUser';

export const Route = createRoute({
  getParentRoute: () => RootRoute,
  path: '/queue',
  beforeLoad: () => {
    const { user } = useCurrentUser.getState();
    if (user.role !== 'analyst') {
      throw redirect({ to: defaultRouteFor(user.role) });
    }
  },
  component: QueueRoute,
});

function QueueRoute() {
  return (
    <section className="p-6">
      <h1 className="text-2xl font-semibold tracking-tight">Queue</h1>
      <p className="mt-2 text-sm text-zinc-500">Story 4-1 will populate this.</p>
    </section>
  );
}
