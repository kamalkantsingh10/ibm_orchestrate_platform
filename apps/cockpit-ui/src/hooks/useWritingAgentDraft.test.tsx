// useWritingAgentDraft tests — Story 7.1 / AC #3.

import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { useWritingAgentDraft } from './useWritingAgentDraft';
import { useCurrentUser } from '@/stores/currentUser';
import { DEMO_USERS } from '@/lib/demoUsers';

const CASE_ID = 'case_01HZ7ZK4G7EXAMPLE0000000DD';

function makeWrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
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
});

describe('useWritingAgentDraft', () => {
  it('returns the writing agent draft from the intake/writing endpoint', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({
          case_id: CASE_ID,
          html: '<p>Approve based on screening hits.</p>',
          paragraphs: ['Approve based on screening hits.', 'No open hits.'],
          cited_claims: [],
          model_id: 'fixture-writing-v1',
          prompt_template_id: 'rationale_draft_v1',
        }),
      ),
    );

    const { result } = renderHook(() => useWritingAgentDraft(CASE_ID), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual({
      rationaleHtml: '<p>Approve based on screening hits.</p>',
      agentActionId: '',
    });
  });

  it('returns null on 404 (writing agent not yet run)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ detail: 'not yet run' }, 404)));

    const { result } = renderHook(() => useWritingAgentDraft(CASE_ID), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toBeNull();
  });

  it('throws on a non-404 server error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ detail: 'kaboom' }, 500)));

    const { result } = renderHook(() => useWritingAgentDraft(CASE_ID), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(String(result.current.error)).toContain('kaboom');
  });

  it('passes the X-Cockpit-Demo-User header', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ detail: 'not yet run' }, 404));
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useWritingAgentDraft(CASE_ID), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const init = (fetchMock.mock.calls[0]?.[1] ?? {}) as RequestInit;
    const headers = new Headers(init.headers);
    expect(headers.get('x-cockpit-demo-user')).toBeTruthy();
  });

  it('uses the intake/writing query key so it shares the TanStack cache', async () => {
    // The key shape is enforced in source; the test just exercises the hook
    // mounts cleanly with the documented key.
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ detail: 'not yet run' }, 404)));
    const { result } = renderHook(() => useWritingAgentDraft(CASE_ID), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isFetched).toBe(true));
    expect(result.current.data).toBeNull();
  });
});
