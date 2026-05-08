// Deferred-cases view filter — Story 4.2 AC #5, #5a.
//
// Local-only "this case is deferred until X". No backend roundtrip; data
// dies with the page. The QueueRail filters out cases whose id is here AND
// whose `defer_until` is still in the future.

import { create } from 'zustand';

interface DeferredFilterState {
  /** Map of caseId → ISO-8601 string at which the deferral expires. */
  deferUntilByCaseId: Record<string, string>;
  defer: (caseId: string, until: Date) => void;
  clear: (caseId: string) => void;
  reset: () => void;
  /** True if the case is currently deferred (defer_until > now). */
  isDeferred: (caseId: string, now?: Date) => boolean;
}

export const useDeferredFilter = create<DeferredFilterState>((set, get) => ({
  deferUntilByCaseId: {},
  defer: (caseId, until) =>
    set((state) => ({
      deferUntilByCaseId: { ...state.deferUntilByCaseId, [caseId]: until.toISOString() },
    })),
  clear: (caseId) =>
    set((state) => {
      const next = { ...state.deferUntilByCaseId };
      delete next[caseId];
      return { deferUntilByCaseId: next };
    }),
  reset: () => set({ deferUntilByCaseId: {} }),
  isDeferred: (caseId, now = new Date()) => {
    const iso = get().deferUntilByCaseId[caseId];
    if (!iso) return false;
    const until = new Date(iso);
    return until.getTime() > now.getTime();
  },
}));
