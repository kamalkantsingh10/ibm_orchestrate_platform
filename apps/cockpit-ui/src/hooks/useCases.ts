// useCases — Story 2.3 AC #1.
// Polls GET /v1/cases every 5 seconds (matches the demo's freshness budget).
// TODO(story-4-6): once SSE lands, switch to refetchInterval: false and
// invalidate ["cases"] from the SSE event handler.

import { useQuery } from '@tanstack/react-query';
import type { Case } from '@/lib/types/case';
import { apiClient } from '@/lib/api';

export function useCases() {
  return useQuery<Case[]>({
    queryKey: ['cases'],
    refetchInterval: 5_000,
    staleTime: 0,
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/v1/cases');
      if (error || !data) {
        throw error ?? new Error('GET /v1/cases failed');
      }
      return data.items;
    },
  });
}
