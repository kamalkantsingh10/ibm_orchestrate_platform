// TanStack Query hook for GET /v1/cases/{case_id}/intake/ubo_graph — Story 5.3 AC #9.
//
// Distinguishes "intake not yet run" (returns null — empty state) from
// other 404s (re-throws so the route's error boundary handles "case not
// found"). Mirrors useDocumentIntelligence behaviour.

import { useQuery } from '@tanstack/react-query';
import type { components } from '@/api-types';
import { apiClient } from '@/lib/api';

export type UBOGraph = components['schemas']['UBOGraph'];

export function useUboGraph(caseId: string) {
  return useQuery<UBOGraph | null>({
    queryKey: ['cases', caseId, 'intake', 'ubo_graph'],
    staleTime: 30_000,
    queryFn: async () => {
      const { data, error, response } = await apiClient.GET(
        '/v1/cases/{case_id}/intake/ubo_graph',
        { params: { path: { case_id: caseId } } },
      );
      if (response.status === 404) {
        const detail = String((error as { detail?: string } | undefined)?.detail ?? '');
        if (detail.toLowerCase().includes('not yet run')) return null;
        throw error ?? new Error(`GET ubo_graph 404 for case ${caseId}`);
      }
      if (error || !data) {
        throw error ?? new Error(`GET ubo_graph failed for case ${caseId}`);
      }
      return data;
    },
  });
}
