// Composes the route tree (Story 1.4).
//
// Code-based composition (deviation from Story 1.4 Subtask 2.1 file-based
// codegen). Reason: Vitest specs need the route tree at unit-test time, and
// the Vite plugin's codegen runs only on dev/build. Code-based works for the
// 4-route demo and avoids a test-side codegen step. Documented in
// Completion Notes.

import { createRouter } from '@tanstack/react-router';
import { Route as RootRoute } from './routes/__root';
import { Route as IndexRoute } from './routes/index';
import { Route as QueueRoute } from './routes/queue';
import { Route as ApprovalsRoute } from './routes/approvals';
import { Route as RegulatorLensRoute } from './routes/regulator-lens';
import { Route as CaseDetailRoute } from './routes/cases.$caseId';

const routeTree = RootRoute.addChildren([
  IndexRoute,
  QueueRoute,
  ApprovalsRoute,
  RegulatorLensRoute,
  CaseDetailRoute,
]);

export const router = createRouter({ routeTree });

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}
