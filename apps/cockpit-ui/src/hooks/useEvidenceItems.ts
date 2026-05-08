// useEvidenceItems — Story 8.5 / AC #1.
//
// Reads the case's attached evidence list from
// `GET /v1/cases/{case_id}/evidence`. Newest first (server returns it
// pre-sorted). Returns `[]` when nothing is attached.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useCurrentUser } from '@/stores/currentUser';

export interface EvidenceItem {
  filename: string;
  size_bytes: number;
  uploaded_at: string;
}

interface ListResponse {
  case_id: string;
  items: EvidenceItem[];
}

export function useEvidenceItems(caseId: string) {
  return useQuery<EvidenceItem[]>({
    queryKey: ['cases', caseId, 'evidence'],
    staleTime: 10_000,
    queryFn: async () => {
      const userId = useCurrentUser.getState().user.id;
      const res = await fetch(`/v1/cases/${encodeURIComponent(caseId)}/evidence`, {
        headers: {
          Accept: 'application/json',
          'X-Cockpit-Demo-User': userId,
        },
      });
      if (!res.ok) {
        throw new Error(`evidence list fetch failed (${res.status})`);
      }
      const body = (await res.json()) as ListResponse;
      return body.items;
    },
  });
}

export interface UploadEvidenceArgs {
  file: File | Blob;
  filename: string;
}

export function useUploadEvidence(caseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ file, filename }: UploadEvidenceArgs) => {
      const userId = useCurrentUser.getState().user.id;
      const fd = new FormData();
      fd.append('files', file, filename);
      const res = await fetch(`/v1/cases/${encodeURIComponent(caseId)}/documents?kind=evidence`, {
        method: 'POST',
        headers: {
          'X-Cockpit-Demo-User': userId,
        },
        body: fd,
      });
      if (!res.ok) {
        const problem = (await res.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(problem?.detail ?? `evidence upload failed (${res.status})`);
      }
      return (await res.json()) as { uploaded: EvidenceItem[] };
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['cases', caseId, 'evidence'] });
    },
  });
}

export function useDeleteEvidence(caseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (filename: string) => {
      const userId = useCurrentUser.getState().user.id;
      const res = await fetch(
        `/v1/cases/${encodeURIComponent(caseId)}/evidence/${encodeURIComponent(filename)}`,
        {
          method: 'DELETE',
          headers: { 'X-Cockpit-Demo-User': userId },
        },
      );
      if (!res.ok && res.status !== 204) {
        throw new Error(`evidence delete failed (${res.status})`);
      }
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['cases', caseId, 'evidence'] });
    },
  });
}
