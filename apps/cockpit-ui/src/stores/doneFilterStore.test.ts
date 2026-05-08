// doneFilterStore tests — Story 4.2 AC #9.

import { beforeEach, describe, expect, it } from 'vitest';
import { useDoneFilter } from './doneFilterStore';

describe('useDoneFilter', () => {
  beforeEach(() => {
    useDoneFilter.getState().reset();
  });

  it('starts empty', () => {
    expect(useDoneFilter.getState().doneCaseIds.size).toBe(0);
  });

  it('markDone adds; unmarkDone removes', () => {
    useDoneFilter.getState().markDone('case_1');
    expect(useDoneFilter.getState().doneCaseIds.has('case_1')).toBe(true);
    useDoneFilter.getState().unmarkDone('case_1');
    expect(useDoneFilter.getState().doneCaseIds.has('case_1')).toBe(false);
  });

  it('reset clears all', () => {
    useDoneFilter.getState().markDone('a');
    useDoneFilter.getState().markDone('b');
    useDoneFilter.getState().reset();
    expect(useDoneFilter.getState().doneCaseIds.size).toBe(0);
  });

  it('markDone twice is idempotent', () => {
    useDoneFilter.getState().markDone('case_1');
    useDoneFilter.getState().markDone('case_1');
    expect(useDoneFilter.getState().doneCaseIds.size).toBe(1);
  });
});
