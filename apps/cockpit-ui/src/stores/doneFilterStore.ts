// "Mark done in my view" filter — Story 4.2 AC #6.
//
// Local-only "I'm done with this case in my view"; ephemeral. QueueRail
// filters these out as well as the deferred set.

import { create } from 'zustand';

interface DoneFilterState {
  doneCaseIds: Set<string>;
  markDone: (caseId: string) => void;
  unmarkDone: (caseId: string) => void;
  reset: () => void;
}

export const useDoneFilter = create<DoneFilterState>((set) => ({
  doneCaseIds: new Set<string>(),
  markDone: (caseId) =>
    set((state) => {
      const next = new Set(state.doneCaseIds);
      next.add(caseId);
      return { doneCaseIds: next };
    }),
  unmarkDone: (caseId) =>
    set((state) => {
      const next = new Set(state.doneCaseIds);
      next.delete(caseId);
      return { doneCaseIds: next };
    }),
  reset: () => set({ doneCaseIds: new Set<string>() }),
}));
