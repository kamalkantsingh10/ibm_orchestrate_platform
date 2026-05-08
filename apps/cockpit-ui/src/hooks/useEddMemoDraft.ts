// useEddMemoDraft — Story 8.3 / AC #7.
//
// Reads the Writing agent's v2 EDD memo from
// `GET /v1/cases/{case_id}/intake/writing_edd_memo`. Returns `null` when
// the case has not been escalated to EDD (404). Surfaces other errors so
// the route boundary can react.

import { useQuery } from '@tanstack/react-query';
import { useCurrentUser } from '@/stores/currentUser';
import { eddMemoToHtml, type EddMemoOutput } from '@/lib/eddMemoToHtml';

export interface EddMemoDraft {
  memo: EddMemoOutput;
  /** Five-section HTML (h2 + p) with `{{led_<ULID>}}` tokens rewritten to
   *  Tiptap citation chips. Drop directly into the editor's `setContent`
   *  on first load. */
  html: string;
}

export function useEddMemoDraft(caseId: string) {
  return useQuery<EddMemoDraft | null>({
    queryKey: ['cases', caseId, 'intake', 'writing_edd_memo'],
    staleTime: 30_000,
    queryFn: async () => {
      const userId = useCurrentUser.getState().user.id;
      const res = await fetch(`/v1/cases/${encodeURIComponent(caseId)}/intake/writing_edd_memo`, {
        headers: {
          Accept: 'application/json',
          'X-Cockpit-Demo-User': userId,
        },
      });
      if (res.status === 404) {
        // Either case-not-found (route boundary handles) or EDD memo
        // not yet generated. Both treated as null — DecisionZone will
        // fall back to v1 rationale or the empty editor.
        return null;
      }
      if (!res.ok) {
        const problem = (await res.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(problem?.detail ?? `EDD memo fetch failed (${res.status})`);
      }
      const memo = (await res.json()) as EddMemoOutput;
      return { memo, html: eddMemoToHtml(memo) };
    },
  });
}
