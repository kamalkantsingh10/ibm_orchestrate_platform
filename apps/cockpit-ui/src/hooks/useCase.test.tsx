// Tests for useCase (Story 2.2 AC #10).
//
// Mocks fetch directly via vi.stubGlobal — MSW + vitest-jsdom + undici has
// known intercept issues; the three scenarios from AC #10 are easier to
// express with a fetch stub. We can revisit MSW for cross-test sharing in
// a later story if the test surface grows.

import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { useCase } from './useCase';
import { useCurrentUser } from '@/stores/currentUser';
import { DEMO_USERS } from '@/lib/demoUsers';

const CASE_ID = 'case_01HZ7ZK4G7EXAMPLE0000000DD';

function makeWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

function jsonResponse(body: unknown, status = 200, contentType = 'application/json'): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': contentType },
  });
}

beforeEach(() => {
  localStorage.clear();
  const analyst = DEMO_USERS.find((u) => u.role === 'analyst')!;
  useCurrentUser.setState({ user: analyst });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('useCase', () => {
  it('calls the typed client with the case_id from the hook arg', async () => {
    const fetchMock = vi.fn().mockImplementation((input: RequestInfo) => {
      const url = input instanceof Request ? input.url : String(input);
      const id = url.split('/').pop() ?? '';
      return Promise.resolve(
        jsonResponse({
          id,
          state: 'intake_scheduled',
          customer_metadata: { customer_name: 'Acme', extra: {} },
          assigned_to_user_id: null,
          risk_band: null,
          created_at: '2026-04-30T12:00:00Z',
          updated_at: '2026-04-30T12:00:00Z',
          closure_date: null,
          _links: { documents: null, reasoning_traces: null },
        }),
      );
    });
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useCase(CASE_ID), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const firstCall = fetchMock.mock.calls[0];
    expect(firstCall).toBeDefined();
    const url = (firstCall![0] as Request).url;
    expect(url).toContain(`/v1/cases/${CASE_ID}`);
    expect(result.current.data?.id).toBe(CASE_ID);
  });

  it('propagates the current user id as the X-Cockpit-Demo-User header', async () => {
    const lead = DEMO_USERS.find((u) => u.role === 'team_lead')!;
    useCurrentUser.setState({ user: lead });

    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        id: CASE_ID,
        state: 'intake_scheduled',
        customer_metadata: { customer_name: 'Acme', extra: {} },
        assigned_to_user_id: null,
        risk_band: null,
        created_at: '2026-04-30T12:00:00Z',
        updated_at: '2026-04-30T12:00:00Z',
        closure_date: null,
        _links: { documents: null, reasoning_traces: null },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useCase(CASE_ID), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const firstCall = fetchMock.mock.calls[0];
    expect(firstCall).toBeDefined();
    const req = firstCall![0] as Request;
    expect(req.headers.get('x-cockpit-demo-user')).toBe(lead.id);
  });

  it('surfaces the RFC 7807 problem body on 404', async () => {
    const problem = {
      type: 'about:blank',
      title: 'Not Found',
      status: 404,
      detail: `Case ${CASE_ID} not found`,
      instance: `/v1/cases/${CASE_ID}`,
    };
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse(problem, 404, 'application/problem+json')),
    );

    const { result } = renderHook(() => useCase(CASE_ID), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isError).toBe(true));

    const err = result.current.error as { detail?: string } | null;
    expect(err?.detail).toBe(problem.detail);
  });
});
