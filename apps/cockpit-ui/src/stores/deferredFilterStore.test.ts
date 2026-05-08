// deferredFilterStore tests — Story 4.2 AC #9.

import { beforeEach, describe, expect, it } from 'vitest';
import { useDeferredFilter } from './deferredFilterStore';

describe('useDeferredFilter', () => {
  beforeEach(() => {
    useDeferredFilter.getState().reset();
  });

  it('starts empty', () => {
    expect(useDeferredFilter.getState().deferUntilByCaseId).toEqual({});
  });

  it('defer stores ISO string for the case', () => {
    const until = new Date('2099-01-01T00:00:00Z');
    useDeferredFilter.getState().defer('case_1', until);
    expect(useDeferredFilter.getState().deferUntilByCaseId['case_1']).toBe(until.toISOString());
  });

  it('isDeferred returns true while in future, false after expiry', () => {
    const future = new Date('2099-01-01T00:00:00Z');
    useDeferredFilter.getState().defer('case_1', future);
    expect(useDeferredFilter.getState().isDeferred('case_1')).toBe(true);
    expect(
      useDeferredFilter.getState().isDeferred('case_1', new Date('2100-01-01T00:00:00Z')),
    ).toBe(false);
  });

  it('clear removes an entry; reset clears all', () => {
    const until = new Date('2099-01-01T00:00:00Z');
    useDeferredFilter.getState().defer('case_1', until);
    useDeferredFilter.getState().defer('case_2', until);
    useDeferredFilter.getState().clear('case_1');
    expect(useDeferredFilter.getState().deferUntilByCaseId).toEqual({
      case_2: until.toISOString(),
    });
    useDeferredFilter.getState().reset();
    expect(useDeferredFilter.getState().deferUntilByCaseId).toEqual({});
  });

  it('isDeferred returns false for an unknown case', () => {
    expect(useDeferredFilter.getState().isDeferred('case_unknown')).toBe(false);
  });
});
