// /regulator-lens — regulator route (Story 1.4 AC #9). Story 9-3 will populate this.

import { createRoute, redirect } from '@tanstack/react-router';
import { Route as RootRoute } from './__root';
import { defaultRouteFor } from '@/lib/routeFor';
import { useCurrentUser } from '@/stores/currentUser';

export const Route = createRoute({
  getParentRoute: () => RootRoute,
  path: '/regulator-lens',
  beforeLoad: () => {
    const { user } = useCurrentUser.getState();
    if (user.role !== 'regulator') {
      throw redirect({ to: defaultRouteFor(user.role) });
    }
  },
  component: RegulatorLensRoute,
});

function RegulatorLensRoute() {
  return (
    <section className="p-6">
      <h1 className="text-2xl font-semibold tracking-tight">Regulator Lens</h1>
      <p className="mt-2 text-sm text-zinc-500">Story 9-3 will populate this.</p>
    </section>
  );
}
