// queueFocusStore tests — Story 4.2 AC #9.

import { beforeEach, describe, expect, it } from 'vitest';
import { useQueueFocus } from './queueFocusStore';

describe('useQueueFocus', () => {
  beforeEach(() => {
    useQueueFocus.getState().clearFocus();
  });

  it('starts with no focus', () => {
    const s = useQueueFocus.getState();
    expect(s.focusedCaseId).toBeNull();
    expect(s.focusedIndex).toBe(-1);
  });

  it('setFocus stores both caseId and index', () => {
    useQueueFocus.getState().setFocus('case_X', 2);
    const s = useQueueFocus.getState();
    expect(s.focusedCaseId).toBe('case_X');
    expect(s.focusedIndex).toBe(2);
  });

  it('clearFocus resets to initial', () => {
    useQueueFocus.getState().setFocus('case_X', 2);
    useQueueFocus.getState().clearFocus();
    const s = useQueueFocus.getState();
    expect(s.focusedCaseId).toBeNull();
    expect(s.focusedIndex).toBe(-1);
  });
});
