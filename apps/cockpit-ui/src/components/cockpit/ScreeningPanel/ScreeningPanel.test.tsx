// ScreeningPanel tests — Story 6.3 / AC #11.

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';
import type { components } from '@/api-types';

const { useScreeningHitsMock, useScreeningSubjectResolverMock } = vi.hoisted(() => ({
  useScreeningHitsMock: vi.fn(),
  useScreeningSubjectResolverMock: vi.fn(),
}));

vi.mock('@/hooks/useScreeningHits', () => ({ useScreeningHits: useScreeningHitsMock }));
vi.mock('@/hooks/useScreeningSubjectResolver', () => ({
  useScreeningSubjectResolver: useScreeningSubjectResolverMock,
}));

import { ScreeningPanel } from './ScreeningPanel';

type ScreeningHit = components['schemas']['ScreeningHit'];
type ScreeningAgentOutput = components['schemas']['ScreeningAgentOutput'];

function makeWrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  }
  return Wrapper;
}

function makeOpenHit(overrides: Partial<ScreeningHit> = {}): ScreeningHit {
  return {
    hit_id: 'hit_open_1',
    subject_id: 'ubo_p_09876544',
    matched_name: 'Patel R.',
    name_match_score: {
      value: 0.73,
      provenance: {
        source_agent: 'screening',
        source_system: 'screening_mock',
        confidence: 0.73,
        confidence_band: 'medium_low',
        evidence_ids: ['led_01ABCDEFGHJKMNPQRSTVWXYZ12'],
        captured_at: '2026-05-08T00:00:00Z',
      },
    },
    categories: ['sanctions'],
    source_lists: ['OFAC SDN'],
    disposition: 'open',
    date_of_birth: '1961-05-12',
    ...overrides,
  };
}

function makeDismissedHit(idx: number): ScreeningHit {
  return makeOpenHit({
    hit_id: `hit_dismissed_${idx}`,
    subject_id: `ubo_p_dismiss_${idx}`,
    matched_name: `Other ${idx}`,
    disposition: 'dismissed_by_agent',
    name_match_score: {
      value: 0.4,
      provenance: {
        source_agent: 'screening',
        source_system: 'screening_mock',
        confidence: 0.4,
        confidence_band: 'medium_low',
        evidence_ids: ['led_01ABCDEFGHJKMNPQRSTVWXYZ12'],
        captured_at: '2026-05-08T00:00:00Z',
      },
    },
  });
}

function output(hits: ScreeningHit[]): ScreeningAgentOutput {
  return { case_id: 'case_x', subjects_screened: hits.length || 1, hits };
}

beforeEach(() => {
  useScreeningSubjectResolverMock.mockReturnValue(
    ({ subjectId, fallbackName }: { subjectId: string; fallbackName: string }) => ({
      name: subjectId === 'ubo_p_09876544' ? 'Rohan Mehta' : fallbackName,
      dob: subjectId === 'ubo_p_09876544' ? '1978-01-01' : null,
    }),
  );
});

import { beforeEach } from 'vitest';

describe('ScreeningPanel', () => {
  it('Vora — 1 open OFAC hit, attention tone', async () => {
    useScreeningHitsMock.mockReturnValue({
      data: output([makeOpenHit()]),
      isPending: false,
      isError: false,
    });
    render(<ScreeningPanel caseId="case_x" onOpenReasoningTrace={() => {}} />, {
      wrapper: makeWrapper(),
    });
    expect(await screen.findByText('1 open · 0 auto-dismissed')).toBeInTheDocument();
    const header = screen.getByTestId('collapsible-panel-header-screening');
    const section = header.closest('section');
    expect(section).toHaveAttribute('data-tone', 'attention');
    expect(screen.getByText('Rohan Mehta')).toBeInTheDocument();
  });

  it('Shree — 0 hits, default tone, "No matches"', () => {
    useScreeningHitsMock.mockReturnValue({
      data: output([]),
      isPending: false,
      isError: false,
    });
    render(<ScreeningPanel caseId="case_x" onOpenReasoningTrace={() => {}} />, {
      wrapper: makeWrapper(),
    });
    expect(screen.getByText('No matches')).toBeInTheDocument();
    const section = screen.getByTestId('collapsible-panel-header-screening').closest('section');
    expect(section).toHaveAttribute('data-tone', 'default');
  });

  it('Mixed — 1 open + 5 dismissed renders disclosure', () => {
    const dismissed = [1, 2, 3, 4, 5].map(makeDismissedHit);
    useScreeningHitsMock.mockReturnValue({
      data: output([makeOpenHit(), ...dismissed]),
      isPending: false,
      isError: false,
    });
    render(<ScreeningPanel caseId="case_x" onOpenReasoningTrace={() => {}} />, {
      wrapper: makeWrapper(),
    });
    expect(screen.getByText('1 open · 5 auto-dismissed')).toBeInTheDocument();
    expect(screen.getByText('5 auto-dismissed (review)')).toBeInTheDocument();
  });

  it('clicking a hit fires onOpenReasoningTrace with agentActionId + hit_id', () => {
    const fn = vi.fn();
    useScreeningHitsMock.mockReturnValue({
      data: output([makeOpenHit()]),
      isPending: false,
      isError: false,
    });
    render(<ScreeningPanel caseId="case_x" onOpenReasoningTrace={fn} />, {
      wrapper: makeWrapper(),
    });
    fireEvent.click(screen.getByTestId('screening-explainer-hit_open_1'));
    expect(fn).toHaveBeenCalledWith('led_01ABCDEFGHJKMNPQRSTVWXYZ12', 'hit_open_1');
  });

  it('loading state shows "Screening…" header', () => {
    useScreeningHitsMock.mockReturnValue({ data: null, isPending: true, isError: false });
    render(<ScreeningPanel caseId="case_x" onOpenReasoningTrace={() => {}} />, {
      wrapper: makeWrapper(),
    });
    expect(screen.getByText('Screening…')).toBeInTheDocument();
  });

  it('error state shows error message in body', () => {
    useScreeningHitsMock.mockReturnValue({ data: null, isPending: false, isError: true });
    render(<ScreeningPanel caseId="case_x" onOpenReasoningTrace={() => {}} />, {
      wrapper: makeWrapper(),
    });
    fireEvent.click(screen.getByTestId('collapsible-panel-header-screening'));
    expect(screen.getByText(/Could not load screening results/i)).toBeInTheDocument();
  });

  it('Ananya — 1 PEP open hit, attention tone', () => {
    const pep = makeOpenHit({
      hit_id: 'hit_pep_1',
      subject_id: 'case_x',
      matched_name: 'Ananya Iyer',
      categories: ['pep'],
      source_lists: ['OpenSanctions Politicians'],
      date_of_birth: '1985-11-04',
      name_match_score: {
        value: 0.88,
        provenance: {
          source_agent: 'screening',
          source_system: 'screening_mock',
          confidence: 0.88,
          confidence_band: 'high',
          evidence_ids: ['led_01ABCDEFGHJKMNPQRSTVWXYZ12'],
          captured_at: '2026-05-08T00:00:00Z',
        },
      },
    });
    useScreeningHitsMock.mockReturnValue({
      data: output([pep]),
      isPending: false,
      isError: false,
    });
    render(<ScreeningPanel caseId="case_x" onOpenReasoningTrace={() => {}} />, {
      wrapper: makeWrapper(),
    });
    expect(screen.getByText('1 open · 0 auto-dismissed')).toBeInTheDocument();
    const section = screen.getByTestId('collapsible-panel-header-screening').closest('section');
    expect(section).toHaveAttribute('data-tone', 'attention');
  });
});
