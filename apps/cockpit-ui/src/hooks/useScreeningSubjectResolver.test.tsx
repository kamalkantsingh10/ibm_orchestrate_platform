// useScreeningSubjectResolver tests — Story 6.3 / AC #7.

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';

const { useCaseMock, useUboGraphMock } = vi.hoisted(() => ({
  useCaseMock: vi.fn(),
  useUboGraphMock: vi.fn(),
}));

vi.mock('@/hooks/useCase', () => ({ useCase: useCaseMock }));
vi.mock('@/hooks/useUboGraph', () => ({ useUboGraph: useUboGraphMock }));

import { useScreeningSubjectResolver } from './useScreeningSubjectResolver';

function makeWrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  }
  return Wrapper;
}

describe('useScreeningSubjectResolver', () => {
  it('resolves entity subject via case_id', () => {
    useCaseMock.mockReturnValue({
      data: {
        id: 'case_x',
        customer_metadata: {
          customer_name: 'Ananya Iyer',
          extra: { date_of_birth: '1985-11-04' },
        },
      },
    });
    useUboGraphMock.mockReturnValue({ data: null });
    const { result } = renderHook(() => useScreeningSubjectResolver('case_x'), {
      wrapper: makeWrapper(),
    });
    expect(result.current({ subjectId: 'case_x', fallbackName: 'fallback' })).toEqual({
      name: 'Ananya Iyer',
      dob: '1985-11-04',
    });
  });

  it('resolves UBO node match by id', () => {
    useCaseMock.mockReturnValue({
      data: { id: 'case_x', customer_metadata: { customer_name: 'Vora', extra: {} } },
    });
    useUboGraphMock.mockReturnValue({
      data: {
        nodes: [
          { id: 'ubo_p_09876544', name: 'Rohan Mehta', kind: 'person' },
          { id: 'ubo_e_root', name: 'Vora', kind: 'entity' },
        ],
        edges: [],
      },
    });
    const { result } = renderHook(() => useScreeningSubjectResolver('case_x'), {
      wrapper: makeWrapper(),
    });
    expect(result.current({ subjectId: 'ubo_p_09876544', fallbackName: 'fallback' })).toEqual({
      name: 'Rohan Mehta',
      dob: null,
    });
  });

  it('falls back to matched_name on unknown subject_id', () => {
    useCaseMock.mockReturnValue({
      data: { id: 'case_x', customer_metadata: { customer_name: 'Vora', extra: {} } },
    });
    useUboGraphMock.mockReturnValue({ data: { nodes: [], edges: [] } });
    const { result } = renderHook(() => useScreeningSubjectResolver('case_x'), {
      wrapper: makeWrapper(),
    });
    expect(result.current({ subjectId: 'ubo_p_unknown', fallbackName: 'Director X' })).toEqual({
      name: 'Director X',
      dob: null,
    });
  });

  it('returns fallback when case + graph are pending', () => {
    useCaseMock.mockReturnValue({ data: undefined });
    useUboGraphMock.mockReturnValue({ data: undefined });
    const { result } = renderHook(() => useScreeningSubjectResolver('case_x'), {
      wrapper: makeWrapper(),
    });
    expect(result.current({ subjectId: 'whatever', fallbackName: 'X' })).toEqual({
      name: 'X',
      dob: null,
    });
  });
});
