// /queue — analyst route. Story 1.4 created the stub; Story 2.3 mounts the
// Queue Rail with live polling; Story 4.2 adds keyboard navigation + defer
// popover + ephemeral done/deferred view filters.

import { useMemo, useState } from 'react';
import { createRoute, redirect, useNavigate } from '@tanstack/react-router';
import { Route as RootRoute } from './__root';
import { QueueRail } from '@/components/cockpit/QueueRail/QueueRail';
import { DeferPopover } from '@/components/cockpit/DeferPopover';
import { useCases } from '@/hooks/useCases';
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts';
import { defaultRouteFor } from '@/lib/routeFor';
import { useCurrentUser } from '@/stores/currentUser';
import { useQueueFocus } from '@/stores/queueFocusStore';
import { useDeferredFilter } from '@/stores/deferredFilterStore';
import { useDoneFilter } from '@/stores/doneFilterStore';

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
  const focusedIndex = useQueueFocus((s) => s.focusedIndex);
  const focusedCaseId = useQueueFocus((s) => s.focusedCaseId);
  const isDeferredFn = useDeferredFilter((s) => s.isDeferred);
  const doneCaseIds = useDoneFilter((s) => s.doneCaseIds);
  const [deferOpen, setDeferOpen] = useState(false);

  // Story 4.2 view filters — ephemeral, local-only.
  const visibleCases = useMemo(() => {
    return cases.filter((c) => !doneCaseIds.has(c.id) && !isDeferredFn(c.id));
  }, [cases, doneCaseIds, isDeferredFn]);

  useKeyboardShortcuts({
    cases: visibleCases,
    onOpenDefer: () => setDeferOpen(true),
    isDeferOpen: deferOpen,
    onCloseDefer: () => setDeferOpen(false),
  });

  const focusedCase = focusedCaseId
    ? (visibleCases.find((c) => c.id === focusedCaseId) ?? null)
    : null;
  const focusedAnchor = focusedCase
    ? document.querySelector<HTMLElement>(`button[data-focused="true"]`)
    : null;

  return (
    <div className="flex h-full">
      <aside className="flex-shrink-0">
        <QueueRail
          cases={visibleCases}
          isPending={isPending}
          isError={isError}
          onRetry={refetch}
          onSelect={(caseId) => navigate({ to: '/cases/$caseId', params: { caseId } })}
          focusedIndex={
            // Map focusedIndex into the (post-filter) visible array.
            focusedCase ? visibleCases.findIndex((c) => c.id === focusedCase.id) : focusedIndex
          }
        />
      </aside>
      <main className="flex-1 p-8 text-sm text-zinc-500">
        <p>Select a case to open.</p>
        <p className="mt-2 text-xs text-zinc-400">
          Keyboard: <kbd>j</kbd> / <kbd>k</kbd> move · <kbd>Enter</kbd> open · <kbd>x</kbd> defer ·{' '}
          <kbd>d</kbd> done · <kbd>Esc</kbd> clear
        </p>
      </main>
      <DeferPopover
        open={deferOpen}
        onOpenChange={setDeferOpen}
        caseId={focusedCase?.id ?? null}
        caseName={focusedCase?.customer_metadata.customer_name ?? null}
        anchor={focusedAnchor}
      />
    </div>
  );
}
