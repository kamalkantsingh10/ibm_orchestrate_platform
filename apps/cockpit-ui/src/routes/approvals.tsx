// /approvals — team lead route (Story 1.4 AC #8). Story 10-1 will populate this.

import { createRoute, redirect } from '@tanstack/react-router';
import { Route as RootRoute } from './__root';
import { defaultRouteFor } from '@/lib/routeFor';
import { useCurrentUser } from '@/stores/currentUser';

export const Route = createRoute({
  getParentRoute: () => RootRoute,
  path: '/approvals',
  beforeLoad: () => {
    const { user } = useCurrentUser.getState();
    if (user.role !== 'team_lead') {
      throw redirect({ to: defaultRouteFor(user.role) });
    }
  },
  component: ApprovalsRoute,
});

function ApprovalsRoute() {
  return (
    <section className="p-6">
      <h1 className="text-2xl font-semibold tracking-tight">Approvals</h1>
      <p className="mt-2 text-sm text-zinc-500">Story 10-1 will populate this.</p>
    </section>
  );
}
