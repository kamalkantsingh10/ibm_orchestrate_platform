// Story 5.5 — TanStack mutation hook for the drag-correct flow.
//
// On success, invalidates the UBO graph query so the canvas refetches.
// Story 5.8 will additionally invalidate `risk_scoring`.

import { useMutation, useQueryClient } from '@tanstack/react-query';
import type { components } from '@/api-types';
import { apiClient } from '@/lib/api';

export type LearningEventInput = components['schemas']['LearningEventInput'];
export type LearningEventResponse = components['schemas']['LearningEventResponse'];

export function useUboCorrection(caseId: string) {
  const queryClient = useQueryClient();
  return useMutation<LearningEventResponse, Error, LearningEventInput>({
    mutationFn: async (input) => {
      const { data, error } = await apiClient.POST('/v1/cases/{case_id}/ubo/learning-events', {
        params: { path: { case_id: caseId } },
        body: input,
      });
      if (error) {
        const detail = (error as { detail?: string } | undefined)?.detail;
        throw new Error(detail ?? `UBO correction failed for case ${caseId}`);
      }
      if (!data) {
        throw new Error(`UBO correction returned no data for case ${caseId}`);
      }
      return data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ['cases', caseId, 'intake', 'ubo_graph'],
      });
      // Story 5.8 will add: ['cases', caseId, 'intake', 'risk_scoring']
    },
  });
}
