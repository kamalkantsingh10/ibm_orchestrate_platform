// useSealAnimation tests — Story 7.6 / AC #8.

import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useSealAnimation } from './useSealAnimation';

const CASE_ID = 'case_01HZ7ZK4G7EXAMPLE0000000DD';
const OTHER_CASE_ID = 'case_01HZ7ZK4G7OTHER000000000QH';
const LED_ID = 'led_01ABCDEFGHJKMNPQRSTVWXYZ12';

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('useSealAnimation', () => {
  it('initial phase is idle', () => {
    const { result } = renderHook(() => useSealAnimation(CASE_ID));
    expect(result.current.phase).toBe('idle');
  });

  it('decision.sealed event flips to sealing', () => {
    const { result } = renderHook(() => useSealAnimation(CASE_ID));
    act(() => {
      window.dispatchEvent(
        new CustomEvent('cockpit:decision-sealed', {
          detail: { case_id: CASE_ID, ledger_entry_id: LED_ID, event: 'decision.sealed' },
        }),
      );
    });
    expect(result.current.phase).toBe('sealing');
    if (result.current.phase === 'sealing') {
      expect(result.current.ledgerEntryId).toBe(LED_ID);
    }
  });

  it('after 400ms, transitions from sealing to sealed', () => {
    const { result } = renderHook(() => useSealAnimation(CASE_ID));
    act(() => {
      window.dispatchEvent(
        new CustomEvent('cockpit:decision-sealed', {
          detail: { case_id: CASE_ID, ledger_entry_id: LED_ID, event: 'decision.sealed' },
        }),
      );
    });
    act(() => {
      vi.advanceTimersByTime(400);
    });
    expect(result.current.phase).toBe('sealed');
    if (result.current.phase === 'sealed') {
      expect(result.current.ledgerEntryId).toBe(LED_ID);
    }
  });

  it('non-matching case_id is ignored', () => {
    const { result } = renderHook(() => useSealAnimation(CASE_ID));
    act(() => {
      window.dispatchEvent(
        new CustomEvent('cockpit:decision-sealed', {
          detail: {
            case_id: OTHER_CASE_ID,
            ledger_entry_id: LED_ID,
            event: 'decision.sealed',
          },
        }),
      );
    });
    expect(result.current.phase).toBe('idle');
  });

  it('non-sealed event without ledger id is ignored', () => {
    const { result } = renderHook(() => useSealAnimation(CASE_ID));
    act(() => {
      window.dispatchEvent(
        new CustomEvent('cockpit:decision-event', {
          detail: { event: 'decision.committed' },
        }),
      );
    });
    expect(result.current.phase).toBe('idle');
  });

  it('reload starts idle even when the case is already committed', () => {
    // No event fires after mount. The hook stays idle. The component
    // is responsible for rendering the steady-state SealedIndicator
    // from the case envelope, not from this hook (story pitfall #5).
    const { result } = renderHook(() => useSealAnimation(CASE_ID));
    expect(result.current.phase).toBe('idle');
    act(() => {
      vi.advanceTimersByTime(10_000);
    });
    expect(result.current.phase).toBe('idle');
  });
});
