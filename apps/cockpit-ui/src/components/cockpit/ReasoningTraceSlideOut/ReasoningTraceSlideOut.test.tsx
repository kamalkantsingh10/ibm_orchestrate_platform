// ReasoningTraceSlideOut tests — Story 6.6 / AC #10.

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { components } from '@/api-types';

const { useReasoningTraceMock } = vi.hoisted(() => ({
  useReasoningTraceMock: vi.fn(),
}));

vi.mock('@/hooks/useReasoningTrace', () => ({
  useReasoningTrace: useReasoningTraceMock,
}));

import { ReasoningTraceSlideOut } from './ReasoningTraceSlideOut';

type ReasoningTrace = components['schemas']['ReasoningTrace'];
type ScreeningHit = components['schemas']['ScreeningHit'];
type ExtractedField = components['schemas']['ExtractedField'];

function _trace(): ReasoningTrace {
  return {
    what_searched: 'screened 1 director against the configured screening provider',
    what_hit: 'returned 1 sanctions match at score 0.73',
    confidence_self_rating: {
      value: 0.73,
      rationale: 'mean of returned hit scores; sample of 1',
      band: 'medium_high',
    },
    counterfactual: 'disposition would change with officer DOB confirmation',
  };
}

function _hit(): ScreeningHit {
  return {
    hit_id: 'hit_x',
    subject_id: 'ubo_p_09876544',
    matched_name: 'Patel R.',
    name_match_score: {
      value: 0.73,
      provenance: {
        source_agent: 'screening',
        source_system: 'screening_mock',
        confidence: 0.73,
        confidence_band: 'medium_high',
        evidence_ids: ['led_01ABCDEFGHJKMNPQRSTVWXYZ12'],
        captured_at: '2026-05-08T00:00:00Z',
      },
    },
    categories: ['sanctions'],
    source_lists: ['OFAC SDN'],
    disposition: 'open',
  };
}

describe('ReasoningTraceSlideOut', () => {
  it('renders 4 sections in success state', () => {
    useReasoningTraceMock.mockReturnValue({ status: 'success', trace: _trace() });
    render(
      <ReasoningTraceSlideOut
        open
        onOpenChange={() => {}}
        caseId="case_x"
        actionId="led_01ABCDEFGHJKMNPQRSTVWXYZ12"
        agentSlug="screening"
      />,
    );
    expect(screen.getByText('What searched')).toBeInTheDocument();
    expect(screen.getByText('What hit')).toBeInTheDocument();
    expect(screen.getByText('Confidence')).toBeInTheDocument();
    expect(screen.getByText('What would change it')).toBeInTheDocument();
    expect(screen.getByText(_trace().what_searched)).toBeInTheDocument();
    expect(screen.getByText(_trace().counterfactual)).toBeInTheDocument();
  });

  it('counterfactual section has aria-label "What would change this conclusion"', () => {
    useReasoningTraceMock.mockReturnValue({ status: 'success', trace: _trace() });
    render(
      <ReasoningTraceSlideOut
        open
        onOpenChange={() => {}}
        caseId="case_x"
        actionId="led_01ABCDEFGHJKMNPQRSTVWXYZ12"
        agentSlug="screening"
      />,
    );
    const section = screen.getByLabelText('What would change this conclusion');
    expect(section.tagName.toLowerCase()).toBe('section');
  });

  it('renders skeleton in pending state', () => {
    useReasoningTraceMock.mockReturnValue({ status: 'pending' });
    render(
      <ReasoningTraceSlideOut
        open
        onOpenChange={() => {}}
        caseId="case_x"
        actionId="led_01ABCDEFGHJKMNPQRSTVWXYZ12"
      />,
    );
    expect(screen.getByTestId('reasoning-trace-skeleton')).toBeInTheDocument();
  });

  it('renders no-trace empty state on 204', () => {
    useReasoningTraceMock.mockReturnValue({ status: 'no-trace' });
    render(
      <ReasoningTraceSlideOut
        open
        onOpenChange={() => {}}
        caseId="case_x"
        actionId="led_01ABCDEFGHJKMNPQRSTVWXYZ12"
      />,
    );
    expect(screen.getByText(/No trace produced/i)).toBeInTheDocument();
  });

  it('renders not-found empty state on 404', () => {
    useReasoningTraceMock.mockReturnValue({ status: 'not-found' });
    render(
      <ReasoningTraceSlideOut
        open
        onOpenChange={() => {}}
        caseId="case_x"
        actionId="led_01ABCDEFGHJKMNPQRSTVWXYZ12"
      />,
    );
    expect(screen.getByText(/Action not found/i)).toBeInTheDocument();
  });

  it('renders alert role on error', () => {
    useReasoningTraceMock.mockReturnValue({
      status: 'error',
      error: new Error('boom'),
    });
    render(
      <ReasoningTraceSlideOut
        open
        onOpenChange={() => {}}
        caseId="case_x"
        actionId="led_01ABCDEFGHJKMNPQRSTVWXYZ12"
      />,
    );
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('embeds ScreeningExplainer cards when agentSlug is screening + hits provided', () => {
    useReasoningTraceMock.mockReturnValue({ status: 'success', trace: _trace() });
    render(
      <ReasoningTraceSlideOut
        open
        onOpenChange={() => {}}
        caseId="case_x"
        actionId="led_01ABCDEFGHJKMNPQRSTVWXYZ12"
        agentSlug="screening"
        screeningHits={[_hit()]}
      />,
    );
    expect(screen.getByTestId('screening-explainer-hit_x')).toBeInTheDocument();
  });

  it('does not embed ScreeningExplainer for non-screening agents', () => {
    useReasoningTraceMock.mockReturnValue({ status: 'success', trace: _trace() });
    render(
      <ReasoningTraceSlideOut
        open
        onOpenChange={() => {}}
        caseId="case_x"
        actionId="led_01ABCDEFGHJKMNPQRSTVWXYZ12"
        agentSlug="entity-verification"
      />,
    );
    expect(screen.queryByTestId(/^screening-explainer-/)).toBeNull();
  });

  it('renders the agent tag in the header when agentSlug is set', () => {
    useReasoningTraceMock.mockReturnValue({ status: 'success', trace: _trace() });
    render(
      <ReasoningTraceSlideOut
        open
        onOpenChange={() => {}}
        caseId="case_x"
        actionId="led_01ABCDEFGHJKMNPQRSTVWXYZ12"
        agentSlug="screening"
      />,
    );
    const tag = screen.getByTestId('reasoning-trace-agent-tag');
    expect(tag).toHaveTextContent('Screening');
  });

  it('legacy mode: renders extractedField body when no actionId is provided', () => {
    useReasoningTraceMock.mockReturnValue({ status: 'pending' });
    const field: ExtractedField = {
      field_name: 'company_name',
      document_ref: 'incorporation.pdf',
      value: {
        value: 'Vora Capital',
        provenance: {
          source_agent: 'document_intelligence',
          source_system: 'fixture_doc_ai',
          confidence: 0.9,
          confidence_band: 'high',
          evidence_ids: [],
          captured_at: '2026-05-08T00:00:00Z',
        },
      },
    };
    render(<ReasoningTraceSlideOut open onOpenChange={() => {}} extractedField={field} />);
    expect(screen.getByText('What was searched')).toBeInTheDocument();
    expect(screen.getByText('Vora Capital')).toBeInTheDocument();
  });

  it('empty mode: shows the click-a-pill copy when neither prop is set', () => {
    useReasoningTraceMock.mockReturnValue({ status: 'pending' });
    render(<ReasoningTraceSlideOut open onOpenChange={() => {}} />);
    expect(screen.getByText(/Click a provenance pill/i)).toBeInTheDocument();
  });

  it('Esc key closes the dialog (Radix-default)', () => {
    useReasoningTraceMock.mockReturnValue({ status: 'success', trace: _trace() });
    const onOpenChange = vi.fn();
    render(
      <ReasoningTraceSlideOut
        open
        onOpenChange={onOpenChange}
        caseId="case_x"
        actionId="led_01ABCDEFGHJKMNPQRSTVWXYZ12"
      />,
    );
    fireEvent.keyDown(document.body, { key: 'Escape' });
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
