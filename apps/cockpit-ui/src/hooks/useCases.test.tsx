// useCases tests — Story 2.3 / AC #10.

import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { useCases } from './useCases';

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function makeWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

const SAMPLE_CASES = [
  {
    id: 'case_01HZ7ZK4G7AAAAAAAAAAAAAAAA',
    state: 'intake_scheduled',
    customer_metadata: { customer_name: 'Acme', extra: {} },
    assigned_to_user_id: null,
    risk_band: null,
    created_at: '2026-04-30T12:00:00Z',
    updated_at: '2026-04-30T12:00:00Z',
    closure_date: null,
    _links: { documents: null, reasoning_traces: null },
  },
];

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe('useCases', () => {
  it('unwraps the items array from the list envelope', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          jsonResponse({ items: SAMPLE_CASES, next_cursor: null, has_more: false }),
        ),
    );

    const { result } = renderHook(() => useCases(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toHaveLength(1);
    expect(result.current.data?.[0]?.id).toBe(SAMPLE_CASES[0]!.id);
  });

  it('refetches every 5 seconds via refetchInterval', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ items: SAMPLE_CASES, next_cursor: null, has_more: false }));
    vi.stubGlobal('fetch', fetchMock);
    vi.useFakeTimers({ shouldAdvanceTime: true });

    const { result } = renderHook(() => useCases(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const initialCount = fetchMock.mock.calls.length;
    expect(initialCount).toBeGreaterThanOrEqual(1);

    await vi.advanceTimersByTimeAsync(5_001);
    await waitFor(() => expect(fetchMock.mock.calls.length).toBeGreaterThan(initialCount));
  });
});
