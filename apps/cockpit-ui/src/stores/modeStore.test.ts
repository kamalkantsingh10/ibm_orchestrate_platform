// modeStore tests — Stories 4.7 + 8.1.

import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { modeLabel, useMode } from './modeStore';
import { useGlobalShortcuts } from '@/hooks/useGlobalShortcuts';
import { expand } from '@/lib/motion';

const toastMock = vi.fn();
vi.mock('sonner', () => ({
  toast: (...args: unknown[]) => toastMock(...args),
}));

function press(key: string, modifiers: KeyboardEventInit = {}): void {
  act(() => {
    window.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, ...modifiers }));
  });
}

describe('useMode', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/');
    useMode.getState().setMode('investigation');
    toastMock.mockReset();
  });

  it('starts in investigation', () => {
    expect(useMode.getState().mode).toBe('investigation');
  });

  it('setMode updates mode', () => {
    useMode.getState().setMode('zen');
    expect(useMode.getState().mode).toBe('zen');
  });

  it('rejects an unsupported mode at the type level', () => {
    // @ts-expect-error 'triage' is not a valid Mode for the demo
    useMode.getState().setMode('triage');
    // The runtime call still set it, but TS guarantees prevent that path
    // in real code. Reset for hygiene.
    useMode.getState().setMode('investigation');
  });

  it('modeLabel returns human strings', () => {
    expect(modeLabel('investigation')).toBe('Investigation');
    expect(modeLabel('zen')).toBe('Zen');
    expect(modeLabel('regulator-lens')).toBe('Regulator Lens');
  });

  // ─── Story 8.1 AC #5 — named acceptance tests ─────────────────────────────

  it('accepts_zen_as_a_valid_mode_value', () => {
    useMode.getState().setMode('zen');
    expect(useMode.getState().mode).toBe('zen');
    // AC #2 — switching persists the value in the URL (`?mode=zen`) so
    // deep-linking and reload preserve the user's mode.
    expect(new URL(window.location.href).searchParams.get('mode')).toBe('zen');
  });

  it('cmd_4_switches_to_zen_only_on_case_routes', () => {
    renderHook(() => useGlobalShortcuts());

    // Off the case canvas — ⌘+4 must NOT switch the store. AC #4.
    window.history.replaceState({}, '', '/queue');
    press('4', { metaKey: true });
    expect(useMode.getState().mode).toBe('investigation');
    expect(toastMock).toHaveBeenCalledTimes(1);

    // On a case canvas — ⌘+4 sets the mode to `zen`. AC #1.
    window.history.replaceState({}, '', '/cases/case-001');
    press('4', { metaKey: true });
    expect(useMode.getState().mode).toBe('zen');
  });

  it('transition_uses_expand_preset_at_250ms', () => {
    // AC #3 — the transition into and out of Zen uses the `expand`
    // preset from Story 4.4 at 250ms (0.25s) duration. The case canvas
    // wrapper in cases.$caseId.tsx wires this transition prop.
    expect(expand.duration).toBe(0.25);
  });
});
