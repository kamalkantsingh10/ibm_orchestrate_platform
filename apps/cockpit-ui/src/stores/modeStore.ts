// Cockpit mode store — Story 4.7.
//
// Investigation is the default; Zen lands in Epic 8; Regulator-Lens has
// its own route. ⌘+1 sets investigation; ⌘+2…⌘+6 currently surface a
// "not yet available" toast (Story 4.7 AC #2) and do NOT mutate this
// store.

import { create } from 'zustand';

export type Mode = 'investigation' | 'zen' | 'regulator-lens';

interface ModeState {
  mode: Mode;
  setMode: (mode: Mode) => void;
}

export const useMode = create<ModeState>((set) => ({
  mode: 'investigation',
  setMode: (mode) => set({ mode }),
}));

const _MODE_LABELS: Record<Mode, string> = {
  investigation: 'Investigation',
  zen: 'Zen',
  'regulator-lens': 'Regulator Lens',
};

export function modeLabel(mode: Mode): string {
  return _MODE_LABELS[mode];
}
