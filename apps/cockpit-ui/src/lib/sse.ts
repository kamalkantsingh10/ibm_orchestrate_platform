// Server-Sent Events wrapper — Story 4.6 AC #7.
//
// Subscribes to /v1/cases/{caseId}/stream?as=<userId> and translates the
// three event types into TanStack Query invalidations. Auth via query
// string because EventSource cannot send custom headers.

import type { QueryClient } from '@tanstack/react-query';

const _DEFAULT_BASE_URL = '';

export interface SubscribeOptions {
  baseUrl?: string;
  /** Used to inject a mock EventSource in tests. Defaults to global. */
  EventSourceCtor?: typeof EventSource;
}

export function subscribeToCase(
  caseId: string,
  userId: string,
  queryClient: QueryClient,
  opts: SubscribeOptions = {},
): () => void {
  const ESCtor = opts.EventSourceCtor ?? EventSource;
  if (typeof ESCtor === 'undefined') {
    // SSR / non-browser — no-op.
    return () => {};
  }
  const base = opts.baseUrl ?? _DEFAULT_BASE_URL;
  const url = `${base}/v1/cases/${encodeURIComponent(caseId)}/stream?as=${encodeURIComponent(userId)}`;
  const es = new ESCtor(url);

  es.addEventListener('agent.state_changed', (e: MessageEvent) => {
    void queryClient.invalidateQueries({ queryKey: ['cases', caseId, 'agent-mesh-state'] });
    // Also invalidate the per-agent panel data so panels render in lockstep
    // with the rail's "Done" pill. Without this, panels keep their stale
    // cache until React Query's staleTime expires (10–30s) — looking
    // exactly like a stuck spinner under a "Done" pill.
    let agentSlug: string | null = null;
    try {
      const parsed = e.data ? (JSON.parse(e.data as string) as { agent_slug?: unknown }) : null;
      if (parsed && typeof parsed.agent_slug === 'string') agentSlug = parsed.agent_slug;
    } catch {
      // Non-JSON payload — skip per-agent invalidation, the rail already
      // refetched above.
    }
    if (agentSlug) {
      void queryClient.invalidateQueries({ queryKey: ['cases', caseId, 'intake', agentSlug] });
      // Risk panel + queue rail also reflect risk_band changes when
      // risk_scoring lands; cheap to invalidate broader keys.
      if (agentSlug === 'risk_scoring') {
        void queryClient.invalidateQueries({ queryKey: ['case', caseId] });
        void queryClient.invalidateQueries({ queryKey: ['cases'] });
      }
    }
  });
  es.addEventListener('case.state_changed', () => {
    void queryClient.invalidateQueries({ queryKey: ['case', caseId] });
    void queryClient.invalidateQueries({ queryKey: ['cases'] });
  });
  es.addEventListener('case.documents_changed', () => {
    void queryClient.invalidateQueries({
      queryKey: ['cases', caseId, 'intake', 'document_intelligence'],
    });
    void queryClient.invalidateQueries({ queryKey: ['case', caseId] });
  });
  // Story 5.5 — officer drag-correct fired by `POST .../ubo/learning-events`.
  es.addEventListener('case.ubo_corrected', () => {
    void queryClient.invalidateQueries({ queryKey: ['cases', caseId, 'intake', 'ubo_graph'] });
  });
  // Story 5.8 — auto-recalc completes after the BackgroundTask finishes.
  // Invalidate the risk panel + case header (risk_band changed) + queue rail.
  es.addEventListener('case.risk_recalculated', () => {
    void queryClient.invalidateQueries({ queryKey: ['cases', caseId, 'intake', 'risk_scoring'] });
    void queryClient.invalidateQueries({ queryKey: ['case', caseId] });
    void queryClient.invalidateQueries({ queryKey: ['cases'] });
  });
  // Story 7.4 / 7.5 / 7.6 — decision lifecycle events. Each one fires
  // a window CustomEvent so consumers (UndoPill's useDecisionTimer,
  // Decision Zone's useSealAnimation) can react. The case query is
  // also invalidated so the canvas picks up the state change.
  for (const evt of ['decision.committed', 'decision.sealed', 'decision.undone'] as const) {
    es.addEventListener(evt, (e: MessageEvent) => {
      void queryClient.invalidateQueries({ queryKey: ['case', caseId] });
      void queryClient.invalidateQueries({
        queryKey: ['cases', caseId, 'decisions', 'active', 'timer'],
      });
      let parsed: Record<string, unknown> | null = null;
      try {
        parsed = e.data ? (JSON.parse(e.data as string) as Record<string, unknown>) : null;
      } catch {
        // Non-JSON payload — consumers fall back to refetching the
        // typed view.
      }
      window.dispatchEvent(
        new CustomEvent('cockpit:decision-event', {
          detail: { event: evt, ...(parsed ?? {}), data: parsed ?? undefined },
        }),
      );
      if (evt === 'decision.sealed') {
        // Dedicated channel for Story 7.6's seal animation — consumers
        // can listen here without filtering across all decision
        // events.
        window.dispatchEvent(
          new CustomEvent('cockpit:decision-sealed', {
            detail: { event: evt, ...(parsed ?? {}), data: parsed ?? undefined },
          }),
        );
      }
    });
  }
  es.addEventListener('error', () => {
    // EventSource auto-reconnects natively. Log; do nothing else.
    console.warn(`[sse] connection error for case ${caseId}; browser will reconnect`);
  });

  return () => {
    es.close();
  };
}
