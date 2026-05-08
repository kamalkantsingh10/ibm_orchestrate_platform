// Cockpit mode store — Stories 4.7 + 8.1.
//
// Investigation is the default; Zen lands in Story 8.1 (⌘+4 wires the
// switch on case routes); Regulator-Lens has its own route. ⌘+1 sets
// investigation, ⌘+4 sets zen, ⌘+2/3/5/6 currently surface a "not yet
// available" toast and do NOT mutate this store.
//
// Story 8.1 AC #2 — switching to a mode persists the value in the URL
// (`?mode=zen`) so deep-linking and reload preserve it.

import { create } from 'zustand';

export type Mode = 'investigation' | 'zen' | 'regulator-lens';

const _MODE_QUERY_KEY = 'mode';
const _VALID_MODES: readonly Mode[] = ['investigation', 'zen', 'regulator-lens'];

function _isMode(value: string | null): value is Mode {
  return value !== null && (_VALID_MODES as readonly string[]).includes(value);
}

function _readUrlMode(): Mode | null {
  if (typeof window === 'undefined') return null;
  const raw = new URLSearchParams(window.location.search).get(_MODE_QUERY_KEY);
  return _isMode(raw) ? raw : null;
}

function _writeUrlMode(mode: Mode): void {
  if (typeof window === 'undefined') return;
  const url = new URL(window.location.href);
  url.searchParams.set(_MODE_QUERY_KEY, mode);
  window.history.replaceState(window.history.state, '', url.toString());
}

interface ModeState {
  mode: Mode;
  setMode: (mode: Mode) => void;
}

export const useMode = create<ModeState>((set) => ({
  mode: _readUrlMode() ?? 'investigation',
  setMode: (mode) => {
    _writeUrlMode(mode);
    set({ mode });
  },
}));

const _MODE_LABELS: Record<Mode, string> = {
  investigation: 'Investigation',
  zen: 'Zen',
  'regulator-lens': 'Regulator Lens',
};

export function modeLabel(mode: Mode): string {
  return _MODE_LABELS[mode];
}
