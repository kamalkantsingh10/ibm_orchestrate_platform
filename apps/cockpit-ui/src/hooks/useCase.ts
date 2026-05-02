// TanStack Query hook for GET /v1/cases/{case_id} (Story 2.2 AC #8).
// staleTime: 5_000 matches Story 2-3's queue-rail polling cadence so a
// freshly fetched list does not immediately re-fetch each case envelope.

import { useQuery } from '@tanstack/react-query';
import type { components } from '@/api-types';
import { apiClient } from '@/lib/api';

export type CaseEnvelope = components['schemas']['CaseEnvelope'];

export function useCase(caseId: string) {
  return useQuery<CaseEnvelope>({
    queryKey: ['case', caseId],
    staleTime: 5_000,
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/v1/cases/{case_id}', {
        params: { path: { case_id: caseId } },
      });
      if (error || !data) {
        throw error ?? new Error(`GET /v1/cases/${caseId} failed`);
      }
      return data;
    },
  });
}
