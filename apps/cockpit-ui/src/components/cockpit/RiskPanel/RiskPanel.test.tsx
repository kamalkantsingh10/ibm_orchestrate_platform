// RiskPanel — Story 5.9 / AC #10.

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';
import voraScore from '../RiskScoreBar/__fixtures__/vora-risk-score.json';

const { useRiskScoreMock } = vi.hoisted(() => ({ useRiskScoreMock: vi.fn() }));

vi.mock('@/hooks/useRiskScore', () => ({
  useRiskScore: useRiskScoreMock,
}));

import { RiskPanel } from './RiskPanel';

function makeWrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  }
  return Wrapper;
}

describe('RiskPanel', () => {
  it('renders summary "37 / 100 · MEDIUM" for Vora pre-correction', async () => {
    useRiskScoreMock.mockReturnValue({ data: voraScore, isPending: false, isError: false });
    render(<RiskPanel caseId="case_x" />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByText(/37 \/ 100 · MEDIUM/i)).toBeInTheDocument();
    });
  });

  it('renders decomposition list with all 5 components when expanded', async () => {
    useRiskScoreMock.mockReturnValue({ data: voraScore, isPending: false, isError: false });
    render(<RiskPanel caseId="case_x" />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId('risk-decomposition-country')).toBeInTheDocument();
      expect(screen.getByTestId('risk-decomposition-entity_type')).toBeInTheDocument();
      expect(screen.getByTestId('risk-decomposition-ownership_clarity')).toBeInTheDocument();
      expect(screen.getByTestId('risk-decomposition-screening')).toBeInTheDocument();
      expect(screen.getByTestId('risk-decomposition-adverse_media')).toBeInTheDocument();
    });
  });

  it('renders "Computing…" summary while pending', () => {
    useRiskScoreMock.mockReturnValue({ data: null, isPending: true, isError: false });
    render(<RiskPanel caseId="case_x" />, { wrapper: makeWrapper() });
    expect(screen.getByText(/Computing/i)).toBeInTheDocument();
  });

  it('renders "—" summary when no data and not pending', () => {
    useRiskScoreMock.mockReturnValue({ data: null, isPending: false, isError: false });
    render(<RiskPanel caseId="case_x" />, { wrapper: makeWrapper() });
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('auto-expands when score data arrives', async () => {
    useRiskScoreMock.mockReturnValue({ data: voraScore, isPending: false, isError: false });
    render(<RiskPanel caseId="case_x" />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByTestId('collapsible-panel-header-risk-score')).toHaveAttribute(
        'aria-expanded',
        'true',
      );
    });
  });
});
