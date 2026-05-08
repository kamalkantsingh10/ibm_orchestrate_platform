// useCases — Story 2.3 AC #1, Story 4.6 (SSE invalidation).
// Polling removed — SSE event handler in `lib/sse.ts` invalidates ['cases']
// on `case.state_changed` while the analyst has any case open.

import { useQuery } from '@tanstack/react-query';
import type { Case } from '@/lib/types/case';
import { apiClient } from '@/lib/api';

export function useCases() {
  return useQuery<Case[]>({
    queryKey: ['cases'],
    refetchInterval: false,
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
