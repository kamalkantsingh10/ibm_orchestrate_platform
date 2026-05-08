// useWritingAgentDraft — Story 7.1 / AC #3 (Story 7.3 wires the API).
//
// Reads Story 7.3's drafted rationale from
// `GET /v1/cases/{case_id}/intake/writing`. Returns `null` when the
// writing agent hasn't run yet; surfaces other errors so the route
// boundary can react.

import { useQuery } from '@tanstack/react-query';
import { useCurrentUser } from '@/stores/currentUser';

export interface WritingAgentDraft {
  rationaleHtml: string;
  agentActionId: string;
}

export function useWritingAgentDraft(caseId: string) {
  return useQuery<WritingAgentDraft | null>({
    queryKey: ['cases', caseId, 'intake', 'writing'],
    staleTime: 30_000,
    queryFn: async () => {
      const userId = useCurrentUser.getState().user.id;
      const res = await fetch(`/v1/cases/${encodeURIComponent(caseId)}/intake/writing`, {
        headers: {
          Accept: 'application/json',
          'X-Cockpit-Demo-User': userId,
        },
      });
      if (res.status === 404) {
        // Either "case not found" (route boundary already caught) or
        // "writing agent not yet run". Treat both as null — the
        // DecisionZone simply renders the empty editor in that case.
        return null;
      }
      if (!res.ok) {
        const problem = (await res.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(problem?.detail ?? `writing draft fetch failed (${res.status})`);
      }
      // Story 7.3 returns a DraftedRationale (snake_case wire format).
      // Map the only field the UI consumes — html → rationaleHtml — and
      // surface the latest agent_action_id from the ledger when 7.3
      // wires it through. (Today the contract doesn't carry it; the
      // demo doesn't need it for editor pre-loading.)
      const body = (await res.json()) as { html?: string };
      if (!body?.html) return null;
      return { rationaleHtml: body.html, agentActionId: '' };
    },
  });
}
