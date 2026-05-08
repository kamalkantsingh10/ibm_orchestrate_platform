// UBOPanel — Story 5.9 / AC #10.

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';
import voraGraph from '../UBOCanvas/__fixtures__/vora-ubo-graph.json';

const { useUboGraphMock, useUboCorrectionMock, useCaseMock } = vi.hoisted(() => ({
  useUboGraphMock: vi.fn(),
  useUboCorrectionMock: vi.fn(),
  useCaseMock: vi.fn(),
}));

vi.mock('@/hooks/useUboGraph', () => ({
  useUboGraph: useUboGraphMock,
}));
vi.mock('@/hooks/useUboCorrection', () => ({
  useUboCorrection: useUboCorrectionMock,
}));
vi.mock('@/hooks/useCase', () => ({
  useCase: useCaseMock,
}));

import { UBOPanel } from './UBOPanel';

function makeWrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  }
  return Wrapper;
}

describe('UBOPanel', () => {
  it('renders summary "6 nodes · 3 flagged" for Vora', async () => {
    useUboGraphMock.mockReturnValue({ data: voraGraph, isPending: false, isError: false });
    useUboCorrectionMock.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
    useCaseMock.mockReturnValue({ data: { customer_metadata: { customer_type: 'company' } } });
    render(<UBOPanel caseId="case_x" />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByText(/6 nodes · 3 flagged/i)).toBeInTheDocument();
    });
  });

  it('renders "Building…" summary while pending', () => {
    useUboGraphMock.mockReturnValue({ data: null, isPending: true, isError: false });
    useUboCorrectionMock.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
    useCaseMock.mockReturnValue({ data: { customer_metadata: { customer_type: 'company' } } });
    render(<UBOPanel caseId="case_x" />, { wrapper: makeWrapper() });
    expect(screen.getByText(/Building/i)).toBeInTheDocument();
  });

  it('renders "—" summary when no data and not pending', () => {
    useUboGraphMock.mockReturnValue({ data: null, isPending: false, isError: false });
    useUboCorrectionMock.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
    useCaseMock.mockReturnValue({ data: { customer_metadata: { customer_type: 'company' } } });
    render(<UBOPanel caseId="case_x" />, { wrapper: makeWrapper() });
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('auto-expands when graph data arrives', async () => {
    useUboGraphMock.mockReturnValue({ data: voraGraph, isPending: false, isError: false });
    useUboCorrectionMock.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
    useCaseMock.mockReturnValue({ data: { customer_metadata: { customer_type: 'company' } } });
    render(<UBOPanel caseId="case_x" />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId('collapsible-panel-header-ubo-ownership')).toHaveAttribute(
        'aria-expanded',
        'true',
      );
    });
  });

  it('renders the UBO panel header even when graph is null', () => {
    useUboGraphMock.mockReturnValue({ data: null, isPending: false, isError: false });
    useUboCorrectionMock.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
    useCaseMock.mockReturnValue({ data: { customer_metadata: { customer_type: 'company' } } });
    render(<UBOPanel caseId="case_x" />, { wrapper: makeWrapper() });
    expect(screen.getByText('UBO Ownership')).toBeInTheDocument();
  });

  it('shows "Not applicable" copy for individual customers without a UBO graph', async () => {
    useUboGraphMock.mockReturnValue({ data: null, isPending: false, isError: false });
    useUboCorrectionMock.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
    useCaseMock.mockReturnValue({ data: { customer_metadata: { customer_type: 'individual' } } });
    render(<UBOPanel caseId="case_x" />, { wrapper: makeWrapper() });
    // Auto-expansion only triggers on graph data, but individuals never get one — so the
    // panel header summary shows the N/A copy directly.
    expect(screen.getByText(/N\/A — individual customer/i)).toBeInTheDocument();
  });
});
