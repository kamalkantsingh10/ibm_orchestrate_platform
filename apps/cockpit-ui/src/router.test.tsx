// Integration tests for role-gated routing (Story 1.4 AC #5, #7, #8, #9, #14).
//
// Builds a fresh router per test (separate memory history) so tests don't
// share state. Asserts that loading a wrong-role route redirects to the
// active role's default route.

import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { RouterProvider, createMemoryHistory, createRouter } from '@tanstack/react-router';

import { Route as RootRoute } from './routes/__root';
import { Route as IndexRoute } from './routes/index';
import { Route as QueueRoute } from './routes/queue';
import { Route as ApprovalsRoute } from './routes/approvals';
import { Route as RegulatorLensRoute } from './routes/regulator-lens';
import { DEMO_USERS } from '@/lib/demoUsers';
import { useCurrentUser } from '@/stores/currentUser';

function makeRouter(initialPath: string) {
  const routeTree = RootRoute.addChildren([
    IndexRoute,
    QueueRoute,
    ApprovalsRoute,
    RegulatorLensRoute,
  ]);
  return createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: [initialPath] }),
  });
}

describe('role-gated routing', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    const analyst = DEMO_USERS.find((u) => u.role === 'analyst')!;
    useCurrentUser.setState({ user: analyst });
  });

  it('analyst landing on / lands on /queue', async () => {
    const analyst = DEMO_USERS.find((u) => u.role === 'analyst')!;
    useCurrentUser.setState({ user: analyst });
    const router = makeRouter('/');
    render(<RouterProvider router={router} />);
    await waitFor(() => expect(router.state.location.pathname).toBe('/queue'));
  });

  it('team lead loading /queue redirects to /approvals', async () => {
    const lead = DEMO_USERS.find((u) => u.role === 'team_lead')!;
    useCurrentUser.setState({ user: lead });
    const router = makeRouter('/queue');
    render(<RouterProvider router={router} />);
    await waitFor(() => expect(router.state.location.pathname).toBe('/approvals'));
  });

  it('regulator loading /queue redirects to /regulator-lens', async () => {
    const regulator = DEMO_USERS.find((u) => u.role === 'regulator')!;
    useCurrentUser.setState({ user: regulator });
    const router = makeRouter('/queue');
    render(<RouterProvider router={router} />);
    await waitFor(() => expect(router.state.location.pathname).toBe('/regulator-lens'));
  });

  it('analyst loading /approvals redirects to /queue', async () => {
    const analyst = DEMO_USERS.find((u) => u.role === 'analyst')!;
    useCurrentUser.setState({ user: analyst });
    const router = makeRouter('/approvals');
    render(<RouterProvider router={router} />);
    await waitFor(() => expect(router.state.location.pathname).toBe('/queue'));
  });
});
