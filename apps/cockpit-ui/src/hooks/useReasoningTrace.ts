// useReasoningTrace — Story 6.6 / AC #1.
//
// Fetches the typed ReasoningTrace from Story 6.5's
// GET /v1/cases/{case_id}/agent-actions/{action_id}/reasoning-trace.
// Returns a discriminated-union state machine so callers don't have to
// translate TanStack's raw shape into UI states.

import { useQuery } from '@tanstack/react-query';
import type { components } from '@/api-types';
import { apiClient } from '@/lib/api';

export type ReasoningTrace = components['schemas']['ReasoningTrace'];

export type ReasoningTraceState =
  | { status: 'pending' }
  | { status: 'success'; trace: ReasoningTrace }
  | { status: 'no-trace' } // 204
  | { status: 'not-found' } // 404
  | { status: 'error'; error: Error };

interface _Sentinel {
  __sentinel: 'no-trace' | 'not-found';
}

function _isSentinel(v: unknown): v is _Sentinel {
  return typeof v === 'object' && v !== null && '__sentinel' in v;
}

export function useReasoningTrace(
  caseId: string | null,
  actionId: string | null,
): ReasoningTraceState {
  const q = useQuery<ReasoningTrace | _Sentinel>({
    queryKey: ['cases', caseId, 'agent-actions', actionId, 'reasoning-trace'],
    enabled: caseId !== null && actionId !== null,
    staleTime: 60_000,
    queryFn: async () => {
      const { data, error, response } = await apiClient.GET(
        '/v1/cases/{case_id}/agent-actions/{action_id}/reasoning-trace',
        { params: { path: { case_id: caseId!, action_id: actionId! } } },
      );
      if (response.status === 204) return { __sentinel: 'no-trace' };
      if (response.status === 404) return { __sentinel: 'not-found' };
      if (error || !data) {
        throw error ?? new Error(`reasoning-trace fetch failed (${response.status})`);
      }
      return data;
    },
  });

  if (q.isPending) return { status: 'pending' };
  if (q.isError) return { status: 'error', error: q.error as Error };
  if (q.data && _isSentinel(q.data)) {
    return q.data.__sentinel === 'no-trace' ? { status: 'no-trace' } : { status: 'not-found' };
  }
  if (q.data) return { status: 'success', trace: q.data };
  return { status: 'pending' };
}
