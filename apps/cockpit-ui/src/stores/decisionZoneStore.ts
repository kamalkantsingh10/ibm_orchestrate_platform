// DecisionZone focus store — Story 7.2 / AC #4, #11.
//
// The DecisionZone component owns the source of truth for "is the
// analyst focused into the rationale editor"; the route reads it to
// drive the canvas-dim animation on the panel grid above. Zustand
// matches the architecture's "global UI state" choice (architecture.md
// § F2) and avoids prop-drilling between sibling subtrees.

import { create } from 'zustand';

interface DecisionZoneFocusState {
  isFocused: boolean;
  setFocused: (focused: boolean) => void;
}

export const useDecisionZoneFocusStore = create<DecisionZoneFocusState>((set) => ({
  isFocused: false,
  setFocused: (focused) => set({ isFocused: focused }),
}));

/** Reader hook — components that only need to react to focus changes. */
export function useDecisionZoneFocus(): boolean {
  return useDecisionZoneFocusStore((s) => s.isFocused);
}
