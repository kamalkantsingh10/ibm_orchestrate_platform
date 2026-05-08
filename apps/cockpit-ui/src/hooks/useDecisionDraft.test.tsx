// useDecisionDraft tests — Story 7.1 / AC #13.

import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useDecisionDraft, DECISION_DRAFT_DEBOUNCE_MS } from './useDecisionDraft';

const CASE_ID = 'case_01HZ7ZK4G7EXAMPLE0000000DD';

beforeEach(() => {
  localStorage.clear();
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  localStorage.clear();
});

describe('useDecisionDraft', () => {
  it('returns empty state when localStorage is empty', () => {
    const { result } = renderHook(() => useDecisionDraft(CASE_ID));
    expect(result.current.draft.rationaleHtml).toBe('');
    expect(result.current.draft.outcome).toBeNull();
    expect(result.current.draft.conditions).toEqual([]);
  });

  it('hydrates from localStorage on mount', () => {
    const seed = {
      rationaleHtml: '<p>seeded</p>',
      outcome: 'approve',
      conditions: [],
      updatedAt: '2026-05-08T00:00:00.000Z',
    };
    localStorage.setItem(`cockpit:decision-draft:${CASE_ID}`, JSON.stringify(seed));
    const { result } = renderHook(() => useDecisionDraft(CASE_ID));
    expect(result.current.draft.rationaleHtml).toBe('<p>seeded</p>');
    expect(result.current.draft.outcome).toBe('approve');
  });

  it('debounces setRationale 5 seconds before writing to localStorage', () => {
    const { result } = renderHook(() => useDecisionDraft(CASE_ID));
    act(() => {
      result.current.setRationale('<p>typed</p>');
    });
    expect(localStorage.getItem(`cockpit:decision-draft:${CASE_ID}`)).toBeNull();
    act(() => {
      vi.advanceTimersByTime(DECISION_DRAFT_DEBOUNCE_MS);
    });
    const stored = localStorage.getItem(`cockpit:decision-draft:${CASE_ID}`);
    expect(stored).not.toBeNull();
    expect(JSON.parse(stored!).rationaleHtml).toBe('<p>typed</p>');
  });

  it('loadInitial seeds an empty draft but does NOT clobber an existing one', () => {
    // Empty case — loadInitial seeds.
    const { result } = renderHook(() => useDecisionDraft(CASE_ID));
    act(() => result.current.loadInitial('<p>agent draft</p>'));
    expect(result.current.draft.rationaleHtml).toBe('<p>agent draft</p>');

    // Non-empty case — loadInitial is a no-op.
    act(() => result.current.setRationale('<p>officer edits</p>'));
    act(() => result.current.loadInitial('<p>different agent draft</p>'));
    expect(result.current.draft.rationaleHtml).toBe('<p>officer edits</p>');
  });

  it('clear() removes the storage key and resets state', () => {
    localStorage.setItem(
      `cockpit:decision-draft:${CASE_ID}`,
      JSON.stringify({ rationaleHtml: '<p>x</p>', outcome: null, conditions: [], updatedAt: '' }),
    );
    const { result } = renderHook(() => useDecisionDraft(CASE_ID));
    act(() => result.current.clear());
    expect(localStorage.getItem(`cockpit:decision-draft:${CASE_ID}`)).toBeNull();
    expect(result.current.draft.rationaleHtml).toBe('');
  });

  it('changing caseId rehydrates from a different storage key', () => {
    localStorage.setItem(
      `cockpit:decision-draft:case_a`,
      JSON.stringify({ rationaleHtml: '<p>A</p>', outcome: null, conditions: [], updatedAt: '' }),
    );
    localStorage.setItem(
      `cockpit:decision-draft:case_b`,
      JSON.stringify({ rationaleHtml: '<p>B</p>', outcome: null, conditions: [], updatedAt: '' }),
    );
    const { result, rerender } = renderHook(({ id }) => useDecisionDraft(id), {
      initialProps: { id: 'case_a' },
    });
    expect(result.current.draft.rationaleHtml).toBe('<p>A</p>');
    rerender({ id: 'case_b' });
    expect(result.current.draft.rationaleHtml).toBe('<p>B</p>');
  });

  it('setOutcome to non-conditions clears any prior conditions', () => {
    const { result } = renderHook(() => useDecisionDraft(CASE_ID));
    act(() => result.current.setOutcome('approve_with_conditions'));
    act(() => result.current.setConditions(['enhanced monitoring 6mo']));
    expect(result.current.draft.conditions).toEqual(['enhanced monitoring 6mo']);
    act(() => result.current.setOutcome('approve'));
    expect(result.current.draft.conditions).toEqual([]);
  });
});
