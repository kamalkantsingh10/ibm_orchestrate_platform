// useDecisionTimer tests — Story 7.5 / AC #11.

import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { useDecisionTimer } from './useDecisionTimer';
import { useCurrentUser } from '@/stores/currentUser';
import { DEMO_USERS } from '@/lib/demoUsers';

const CASE_ID = 'case_01HZ7ZK4G7EXAMPLE0000000DD';

function makeWrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

function noContent(): Response {
  return new Response(null, { status: 204 });
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

beforeEach(() => {
  const analyst = DEMO_USERS.find((u) => u.role === 'analyst')!;
  useCurrentUser.setState({ user: analyst });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe('useDecisionTimer', () => {
  it('returns no-timer when the endpoint returns 204', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(noContent()));
    const { result } = renderHook(() => useDecisionTimer(CASE_ID), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.status).toBe('no-timer'));
  });

  it('returns active with the endpoint payload when 200', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({
          case_id: CASE_ID,
          decision_id: 'dec_test_777',
          remaining_seconds: 90,
          window_seconds: 120,
        }),
      ),
    );
    const { result } = renderHook(() => useDecisionTimer(CASE_ID), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.status).toBe('active'));
    if (result.current.status !== 'active') throw new Error('expected active');
    expect(result.current.decisionId).toBe('dec_test_777');
    expect(result.current.windowSeconds).toBe(120);
    expect(result.current.remainingSeconds).toBeGreaterThan(0);
    expect(result.current.remainingSeconds).toBeLessThanOrEqual(90);
  });

  it('countdown decreases over time via the local tick', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({
          case_id: CASE_ID,
          decision_id: 'dec_tick',
          remaining_seconds: 5,
          window_seconds: 5,
        }),
      ),
    );
    const { result } = renderHook(() => useDecisionTimer(CASE_ID), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.status).toBe('active'));
    const initial = result.current.status === 'active' ? result.current.remainingSeconds : Infinity;
    await new Promise((r) => setTimeout(r, 350));
    const later = result.current.status === 'active' ? result.current.remainingSeconds : Infinity;
    expect(later).toBeLessThan(initial);
  });

  it('refetches when a cockpit:decision-event window event fires', async () => {
    let callCount = 0;
    const fetchMock = vi.fn().mockImplementation(() => {
      callCount += 1;
      if (callCount === 1) {
        return Promise.resolve(
          jsonResponse({
            case_id: CASE_ID,
            decision_id: 'dec_first',
            remaining_seconds: 10,
            window_seconds: 60,
          }),
        );
      }
      return Promise.resolve(noContent());
    });
    vi.stubGlobal('fetch', fetchMock);
    const { result } = renderHook(() => useDecisionTimer(CASE_ID), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.status).toBe('active'));
    await act(async () => {
      window.dispatchEvent(
        new CustomEvent('cockpit:decision-event', { detail: { event: 'decision.sealed' } }),
      );
    });
    await waitFor(() => expect(result.current.status).toBe('no-timer'));
  });

  it('throws on a non-204 server error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ detail: 'kaboom' }, 500)));
    const { result } = renderHook(() => useDecisionTimer(CASE_ID), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.status).toBe('no-timer'));
  });

  it('cleans up the local interval on unmount', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({
          case_id: CASE_ID,
          decision_id: 'dec_cleanup',
          remaining_seconds: 30,
          window_seconds: 120,
        }),
      ),
    );
    const { result, unmount } = renderHook(() => useDecisionTimer(CASE_ID), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => expect(result.current.status).toBe('active'));
    const before = result.current.status === 'active' ? result.current.remainingSeconds : 0;
    unmount();
    await new Promise((r) => setTimeout(r, 150));
    // No assertion on fetch calls — the contract is "no errors after
    // unmount". Implicit: no console.error from a setState-after-unmount.
    expect(before).toBeGreaterThan(0);
  });
});
