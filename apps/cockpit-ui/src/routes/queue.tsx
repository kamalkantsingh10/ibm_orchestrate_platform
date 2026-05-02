// /queue — analyst route. Story 1.4 created the stub; Story 2.3 mounts the
// Queue Rail with live polling.

import { createRoute, redirect, useNavigate } from '@tanstack/react-router';
import { Route as RootRoute } from './__root';
import { QueueRail } from '@/components/cockpit/QueueRail/QueueRail';
import { useCases } from '@/hooks/useCases';
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
  const { data: cases = [], isPending, isError, refetch } = useCases();
  const navigate = useNavigate();
  return (
    <div className="flex h-full">
      <aside className="flex-shrink-0">
        <QueueRail
          cases={cases}
          isPending={isPending}
          isError={isError}
          onRetry={refetch}
          onSelect={(caseId) => navigate({ to: '/cases/$caseId', params: { caseId } })}
        />
      </aside>
      <main className="flex-1 p-8 text-sm text-zinc-500">Select a case to open.</main>
    </div>
  );
}
