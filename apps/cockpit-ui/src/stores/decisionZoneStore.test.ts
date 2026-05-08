// decisionZoneStore tests — Story 7.2 / AC #11.

import { renderHook, act } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { useDecisionZoneFocus, useDecisionZoneFocusStore } from './decisionZoneStore';

describe('useDecisionZoneFocusStore', () => {
  beforeEach(() => {
    useDecisionZoneFocusStore.setState({ isFocused: false });
  });

  it('defaults to isFocused: false', () => {
    expect(useDecisionZoneFocusStore.getState().isFocused).toBe(false);
  });

  it('setFocused(true) flips the flag', () => {
    useDecisionZoneFocusStore.getState().setFocused(true);
    expect(useDecisionZoneFocusStore.getState().isFocused).toBe(true);
  });

  it('multiple subscribers re-render when state changes', () => {
    const a = renderHook(() => useDecisionZoneFocus());
    const b = renderHook(() => useDecisionZoneFocus());
    expect(a.result.current).toBe(false);
    expect(b.result.current).toBe(false);
    act(() => {
      useDecisionZoneFocusStore.getState().setFocused(true);
    });
    expect(a.result.current).toBe(true);
    expect(b.result.current).toBe(true);
  });
});
