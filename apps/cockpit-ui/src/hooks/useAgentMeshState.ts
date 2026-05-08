// TanStack Query hook for GET /v1/cases/{case_id}/agent-mesh-state — Story 4.5/4.6.
//
// Polling dropped (Story 4.6). The SSE handler invalidates this query key
// on agent.state_changed events while a case is open.

import { useQuery } from '@tanstack/react-query';
import type { components } from '@/api-types';
import { apiClient } from '@/lib/api';

export type AgentMeshSnapshot = components['schemas']['AgentMeshSnapshot'];

export function useAgentMeshState(caseId: string) {
  return useQuery<AgentMeshSnapshot>({
    queryKey: ['cases', caseId, 'agent-mesh-state'],
    refetchInterval: false,
    staleTime: 0,
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/v1/cases/{case_id}/agent-mesh-state', {
        params: { path: { case_id: caseId } },
      });
      if (error || !data) {
        throw error ?? new Error(`GET agent-mesh-state failed for case ${caseId}`);
      }
      return data;
    },
  });
}
