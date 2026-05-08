// Queue keyboard focus — Story 4.2 AC #1.
//
// Tracks which queue row is *keyboard-focused* (j/k movement). Distinct from
// the URL-active case (`activeCaseId` on QueueRail): keyboard focus moves
// without opening the case; Enter is what navigates.

import { create } from 'zustand';

interface QueueFocusState {
  focusedCaseId: string | null;
  focusedIndex: number; // 0-based; -1 if no focus
  setFocus: (caseId: string, index: number) => void;
  clearFocus: () => void;
}

export const useQueueFocus = create<QueueFocusState>((set) => ({
  focusedCaseId: null,
  focusedIndex: -1,
  setFocus: (caseId, index) => set({ focusedCaseId: caseId, focusedIndex: index }),
  clearFocus: () => set({ focusedCaseId: null, focusedIndex: -1 }),
}));
