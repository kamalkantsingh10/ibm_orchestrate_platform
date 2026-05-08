// useUboCorrection — Story 5.5 / AC #12.
//
// We mock @/lib/api directly because openapi-fetch fails to parse a
// relative URL with an empty baseUrl in jsdom. The mock lets us assert
// the exact path + body the hook constructs.

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { postMock } = vi.hoisted(() => ({ postMock: vi.fn() }));

vi.mock('@/lib/api', () => ({
  apiClient: {
    POST: postMock,
  },
}));

import { useUboCorrection } from './useUboCorrection';

const VORA_ID = 'case_01KQC7GQ70GYHP15CZ8JB5ZT6A';
const COASTAL = 'ubo_e_coastal_equity_partners_pte_ltd';
const VORA_ROOT = 'ubo_e_u67120mh2024ptc444789';

function makeWrapper(client: QueryClient) {
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  }
  return Wrapper;
}

describe('useUboCorrection', () => {
  let client: QueryClient;

  beforeEach(() => {
    client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    postMock.mockReset();
    postMock.mockResolvedValue({
      data: {
        ledger_entry_id: 'led_01KR2AJKNXSCYKYYBQ3FFS3PNC',
        case_id: VORA_ID,
        recorded_at: '2026-05-08T00:00:00Z',
      },
      error: undefined,
    });
  });

  afterEach(() => {
    client.clear();
  });

  it('POSTs to /v1/cases/{case_id}/ubo/learning-events with the typed body', async () => {
    const { result } = renderHook(() => useUboCorrection(VORA_ID), {
      wrapper: makeWrapper(client),
    });
    await act(async () => {
      await result.current.mutateAsync({
        edge_kind: 'owns',
        from_id: COASTAL,
        original_to_id: VORA_ROOT,
        new_to_id: VORA_ROOT,
        correction_tag: 'real_ubo',
        evidence_note: 'RM email 2024-11',
        opt_in_for_retraining: true,
      });
    });
    expect(postMock).toHaveBeenCalledTimes(1);
    const [path, options] = postMock.mock.calls[0];
    expect(path).toBe('/v1/cases/{case_id}/ubo/learning-events');
    expect(options.params.path.case_id).toBe(VORA_ID);
    expect(options.body.correction_tag).toBe('real_ubo');
    expect(options.body.opt_in_for_retraining).toBe(true);
  });

  it('invalidates the UBO graph query on success', async () => {
    const invalidateSpy = vi.spyOn(client, 'invalidateQueries');
    const { result } = renderHook(() => useUboCorrection(VORA_ID), {
      wrapper: makeWrapper(client),
    });
    await act(async () => {
      await result.current.mutateAsync({
        edge_kind: 'owns',
        from_id: COASTAL,
        original_to_id: VORA_ROOT,
        new_to_id: VORA_ROOT,
        correction_tag: 'real_ubo',
        evidence_note: 'test',
        opt_in_for_retraining: false,
      });
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ['cases', VORA_ID, 'intake', 'ubo_graph'],
    });
  });

  it('throws when the server returns an error envelope', async () => {
    postMock.mockResolvedValueOnce({
      data: undefined,
      error: { detail: 'edge not found' },
    });
    const { result } = renderHook(() => useUboCorrection(VORA_ID), {
      wrapper: makeWrapper(client),
    });
    await act(async () => {
      try {
        await result.current.mutateAsync({
          edge_kind: 'owns',
          from_id: COASTAL,
          original_to_id: VORA_ROOT,
          new_to_id: VORA_ROOT,
          correction_tag: 'real_ubo',
          evidence_note: 'test',
          opt_in_for_retraining: false,
        });
      } catch {
        // expected
      }
    });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toBe('edge not found');
  });
});
