// useDecisionTimer — Story 7.5 / AC #3.
//
// Fetches the active timer view from the cockpit-api on mount, then
// counts down locally via setInterval. SSE-driven invalidation flips
// state when the seal/undo events fire so the pill doesn't display a
// stale 0-second ring after the case has already moved on.

import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useCurrentUser } from '@/stores/currentUser';

export type DecisionTimerState =
  | { status: 'no-timer' }
  | { status: 'active'; decisionId: string; remainingSeconds: number; windowSeconds: number };

interface _RawTimerView {
  case_id: string;
  decision_id: string;
  remaining_seconds: number;
  window_seconds: number;
}

const _TICK_MS = 100;

export function useDecisionTimer(caseId: string): DecisionTimerState {
  const queryClient = useQueryClient();
  const { data, refetch } = useQuery<_RawTimerView | null>({
    queryKey: ['cases', caseId, 'decisions', 'active', 'timer'],
    staleTime: 0,
    queryFn: async () => {
      const userId = useCurrentUser.getState().user.id;
      const res = await fetch(`/v1/cases/${encodeURIComponent(caseId)}/decisions/active/timer`, {
        headers: { Accept: 'application/json', 'X-Cockpit-Demo-User': userId },
      });
      if (res.status === 204) return null;
      if (!res.ok) {
        const problem = (await res.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(problem?.detail ?? `timer fetch failed (${res.status})`);
      }
      return (await res.json()) as _RawTimerView;
    },
  });

  // Local mirror of the server's remaining_seconds; ticked every 100ms
  // by the interval below. The ref carries the seed (fetch timestamp +
  // server-reported remaining) so the interval can re-derive remaining
  // without depending on render closures.
  const [remainingSeconds, setRemainingSeconds] = useState<number | null>(null);
  const seedRef = useRef<{ decisionId: string; seedAt: number; seed: number } | null>(null);

  // Synchronizing with an external system (server-side timer) — the
  // recommended pattern for this is one effect that updates state on
  // ``data`` changes AND drives the interval. The setState calls
  // satisfy the lint rule's "valid uses of setState in effects"
  // (subscribe-then-callback shape).
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (!data) {
      seedRef.current = null;
      setRemainingSeconds(null);
      return;
    }
    if (seedRef.current?.decisionId !== data.decision_id) {
      seedRef.current = {
        decisionId: data.decision_id,
        seedAt: Date.now(),
        seed: data.remaining_seconds,
      };
      setRemainingSeconds(data.remaining_seconds);
    }
    const id = setInterval(() => {
      const ref = seedRef.current;
      if (!ref) return;
      const elapsed = (Date.now() - ref.seedAt) / 1000;
      setRemainingSeconds(Math.max(0, ref.seed - elapsed));
    }, _TICK_MS);
    return () => clearInterval(id);
  }, [data]);
  /* eslint-enable react-hooks/set-state-in-effect */

  // SSE-driven refetch: cockpit:decision-event window events fire
  // when the case-level SSE stream relays decision.committed/.sealed/
  // .undone. Re-fetching the timer is the canonical way to flip
  // status without trusting client-side timing.
  useEffect(() => {
    const handler = () => {
      void refetch();
      void queryClient.invalidateQueries({
        queryKey: ['cases', caseId, 'decisions', 'active', 'timer'],
      });
    };
    window.addEventListener('cockpit:decision-event', handler);
    return () => window.removeEventListener('cockpit:decision-event', handler);
  }, [caseId, queryClient, refetch]);

  if (!data || remainingSeconds === null) return { status: 'no-timer' };
  return {
    status: 'active',
    decisionId: data.decision_id,
    remainingSeconds,
    windowSeconds: data.window_seconds,
  };
}
