// motion.ts tests — Story 4.4 AC #6, #7.

import { afterEach, describe, expect, it, vi } from 'vitest';
import { renderHook } from '@testing-library/react';
import {
  expand,
  expandVariants,
  focusDim,
  focusDimVariants,
  slideOut,
  slideOutVariants,
  snap,
  useMotionPresets,
} from './motion';

const reducedMotionMock = vi.fn<[], boolean>();

vi.mock('framer-motion', async () => {
  const actual = await vi.importActual<typeof import('framer-motion')>('framer-motion');
  return {
    ...actual,
    useReducedMotion: () => reducedMotionMock(),
  };
});

describe('motion presets', () => {
  afterEach(() => {
    reducedMotionMock.mockReset();
  });

  it('snap is 100ms cubic-bezier', () => {
    expect(snap).toMatchObject({ duration: 0.1 });
    expect(Array.isArray(snap.ease)).toBe(true);
  });

  it('expand is 250ms cubic-bezier (AC7 smoke)', () => {
    expect(expand.duration).toBe(0.25);
    expect(Array.isArray(expand.ease)).toBe(true);
  });

  it('focusDim is 150ms easeOut', () => {
    expect(focusDim).toEqual({ duration: 0.15, ease: 'easeOut' });
  });

  it('slideOut is 300ms easeInOut', () => {
    expect(slideOut).toEqual({ duration: 0.3, ease: 'easeInOut' });
  });

  it('variants are exported with the expected keys', () => {
    expect(Object.keys(expandVariants)).toEqual(['hidden', 'visible']);
    expect(Object.keys(focusDimVariants)).toEqual(['focused', 'dimmed']);
    expect(Object.keys(slideOutVariants)).toEqual(['closed', 'open']);
  });

  it('useMotionPresets returns full durations when reduced motion is off', () => {
    reducedMotionMock.mockReturnValue(false);
    const { result } = renderHook(() => useMotionPresets());
    expect(result.current.expand.duration).toBe(0.25);
    expect(result.current.snap.duration).toBe(0.1);
  });

  it('useMotionPresets returns zero-duration transitions when reduced motion is on', () => {
    reducedMotionMock.mockReturnValue(true);
    const { result } = renderHook(() => useMotionPresets());
    expect(result.current.expand.duration).toBe(0);
    expect(result.current.snap.duration).toBe(0);
    expect(result.current.focusDim.duration).toBe(0);
    expect(result.current.slideOut.duration).toBe(0);
  });
});
