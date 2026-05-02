// TanStack Query hook for GET /v1/cases/{case_id}/intake/document_intelligence — Story 3.6 AC #2.
//
// Distinguishes "intake not yet run" (returns null — empty state) from
// other 404s (re-throws so the route's error boundary handles "case not
// found"). 30s staleTime; SSE invalidation lands in Story 4-6.

import { useQuery } from '@tanstack/react-query';
import type { components } from '@/api-types';
import { apiClient } from '@/lib/api';

export type DocumentIntelligenceOutput = components['schemas']['DocumentIntelligenceOutput'];

export function useDocumentIntelligence(caseId: string) {
  return useQuery<DocumentIntelligenceOutput | null>({
    queryKey: ['cases', caseId, 'intake', 'document_intelligence'],
    staleTime: 30_000,
    queryFn: async () => {
      const { data, error, response } = await apiClient.GET(
        '/v1/cases/{case_id}/intake/document_intelligence',
        { params: { path: { case_id: caseId } } },
      );
      if (response.status === 404) {
        // Distinguish by detail string: "not yet run" → null (empty state);
        // anything else → error (e.g., "case not found" → route boundary).
        const detail = String((error as { detail?: string } | undefined)?.detail ?? '');
        if (detail.toLowerCase().includes('not yet run')) return null;
        throw error ?? new Error(`GET intake 404 for case ${caseId}`);
      }
      if (error || !data) {
        throw error ?? new Error(`GET intake failed for case ${caseId}`);
      }
      return data;
    },
  });
}
