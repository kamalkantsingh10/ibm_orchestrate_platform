// paletteStore tests — Story 4.8 AC #10.

import { beforeEach, describe, expect, it } from 'vitest';
import { usePalette } from './paletteStore';

describe('usePalette', () => {
  beforeEach(() => {
    usePalette.getState().setOpen(false);
  });

  it('starts closed', () => {
    expect(usePalette.getState().open).toBe(false);
  });

  it('setOpen flips state', () => {
    usePalette.getState().setOpen(true);
    expect(usePalette.getState().open).toBe(true);
  });

  it('toggle inverts state', () => {
    usePalette.getState().toggle();
    expect(usePalette.getState().open).toBe(true);
    usePalette.getState().toggle();
    expect(usePalette.getState().open).toBe(false);
  });
});
