// TanStack Query hook for GET /v1/cases/{case_id}/intake/risk_scoring — Story 5.6 AC #9.
//
// Distinguishes "intake not yet run" (returns null — empty state) from
// other 404s. Mirrors useDocumentIntelligence + useUboGraph behaviour.

import { useQuery } from '@tanstack/react-query';
import type { components } from '@/api-types';
import { apiClient } from '@/lib/api';

export type RiskScore = components['schemas']['RiskScore'];

export function useRiskScore(caseId: string) {
  return useQuery<RiskScore | null>({
    queryKey: ['cases', caseId, 'intake', 'risk_scoring'],
    staleTime: 30_000,
    queryFn: async () => {
      const { data, error, response } = await apiClient.GET(
        '/v1/cases/{case_id}/intake/risk_scoring',
        { params: { path: { case_id: caseId } } },
      );
      if (response.status === 404) {
        const detail = String((error as { detail?: string } | undefined)?.detail ?? '');
        if (detail.toLowerCase().includes('not yet run')) return null;
        throw error ?? new Error(`GET risk_scoring 404 for case ${caseId}`);
      }
      if (error || !data) {
        throw error ?? new Error(`GET risk_scoring failed for case ${caseId}`);
      }
      return data;
    },
  });
}
