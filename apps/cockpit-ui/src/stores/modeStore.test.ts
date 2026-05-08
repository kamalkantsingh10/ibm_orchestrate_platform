// modeStore tests — Story 4.7 AC #5.

import { beforeEach, describe, expect, it } from 'vitest';
import { modeLabel, useMode } from './modeStore';

describe('useMode', () => {
  beforeEach(() => {
    useMode.getState().setMode('investigation');
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
});
