// useScreeningSubjectResolver — Story 6.3 / AC #7.
//
// Maps a ScreeningHit.subject_id to a human-readable {name, dob}. Resolution
// order:
//   1. Entity (case_id or customer_id) → case.customer_metadata
//   2. UBO node → useUboGraph(caseId).data.nodes
//   3. Director (or any unknown id) → fall back to the hit's matched_name
//      (the resolver never returns a placeholder; callers always have a name).

import { useCallback } from 'react';
import { useCase } from '@/hooks/useCase';
import { useUboGraph } from '@/hooks/useUboGraph';

export interface ResolvedSubject {
  name: string;
  dob: string | null;
}

export interface SubjectResolverInput {
  subjectId: string;
  fallbackName: string;
}

export function useScreeningSubjectResolver(caseId: string) {
  const { data: caseEnv } = useCase(caseId);
  const { data: graph } = useUboGraph(caseId);

  return useCallback(
    ({ subjectId, fallbackName }: SubjectResolverInput): ResolvedSubject => {
      // Entity match — case_id (individual cases) or customer_id (corporate).
      if (caseEnv) {
        const customerId =
          typeof caseEnv.customer_metadata?.extra?.['customer_id'] === 'string'
            ? (caseEnv.customer_metadata.extra['customer_id'] as string)
            : null;
        if (subjectId === customerId || subjectId === caseId) {
          const dob =
            typeof caseEnv.customer_metadata?.extra?.['date_of_birth'] === 'string'
              ? (caseEnv.customer_metadata.extra['date_of_birth'] as string)
              : null;
          return {
            name: caseEnv.customer_metadata?.customer_name ?? fallbackName,
            dob,
          };
        }
      }

      // UBO node match — search nodes by id.
      if (graph) {
        const node = graph.nodes.find((n) => n.id === subjectId);
        if (node) {
          return { name: node.name, dob: null };
        }
      }

      return { name: fallbackName, dob: null };
    },
    [caseEnv, caseId, graph],
  );
}
