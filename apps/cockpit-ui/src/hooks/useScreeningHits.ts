// useScreeningHits — Story 6.3 / AC #1.
//
// TanStack Query hook for GET /v1/cases/{case_id}/intake/screening.
// Returns null when the screening intake hasn't run yet (404 with "not yet
// run" detail) so callers can render an empty-state header without an error
// boundary. Mirrors useUboGraph behaviour.

import { useQuery } from '@tanstack/react-query';
import type { components } from '@/api-types';
import { apiClient } from '@/lib/api';

export type ScreeningAgentOutput = components['schemas']['ScreeningAgentOutput'];

export function useScreeningHits(caseId: string) {
  return useQuery<ScreeningAgentOutput | null>({
    queryKey: ['cases', caseId, 'intake', 'screening'],
    staleTime: 30_000,
    queryFn: async () => {
      const { data, error, response } = await apiClient.GET(
        '/v1/cases/{case_id}/intake/screening',
        { params: { path: { case_id: caseId } } },
      );
      if (response.status === 404) {
        const detail = String((error as { detail?: string } | undefined)?.detail ?? '');
        if (detail.toLowerCase().includes('not yet run')) return null;
        throw error ?? new Error(`GET screening 404 for case ${caseId}`);
      }
      if (error || !data) {
        throw error ?? new Error(`GET screening failed for case ${caseId}`);
      }
      return data;
    },
  });
}
