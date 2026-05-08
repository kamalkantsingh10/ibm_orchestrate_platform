// ScreeningExplainer tests — Story 6.3 / AC #10.

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { components } from '@/api-types';
import { ScreeningExplainer } from './ScreeningExplainer';

type ScreeningHit = components['schemas']['ScreeningHit'];

function makeHit(overrides: Partial<ScreeningHit> = {}): ScreeningHit {
  return {
    hit_id: 'hit_mock_abc',
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

describe('ScreeningExplainer', () => {
  it('renders subject name + 3 columns + ConfidencePill', () => {
    render(
      <ScreeningExplainer
        hit={makeHit()}
        subjectName="Rohan Mehta"
        subjectDob="1978-01-01"
        onOpenSlideOut={() => {}}
      />,
    );
    expect(screen.getByText('Rohan Mehta')).toBeInTheDocument();
    expect(screen.getByText(/Matched/i)).toBeInTheDocument();
    expect(screen.getByText(/Didn/i)).toBeInTheDocument();
    expect(screen.getByText(/What would change it/i)).toBeInTheDocument();
    expect(screen.getByText(/Name 73% similar/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Confidence: Med-High/)).toBeInTheDocument();
  });

  it('shows DOB delta in "Didn\'t match" column when years differ', () => {
    render(
      <ScreeningExplainer
        hit={makeHit({ date_of_birth: '1961-05-12' })}
        subjectName="Rohan Mehta"
        subjectDob="1978-01-01"
        onOpenSlideOut={() => {}}
      />,
    );
    expect(screen.getByText('DOB 1978 vs 1961')).toBeInTheDocument();
  });

  it('shows "—" when DOB matches', () => {
    render(
      <ScreeningExplainer
        hit={makeHit({ date_of_birth: '1985-11-04' })}
        subjectName="Ananya Iyer"
        subjectDob="1985-11-04"
        onOpenSlideOut={() => {}}
      />,
    );
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('uses client-side counterfactual when no reasoning_trace present', () => {
    render(
      <ScreeningExplainer
        hit={makeHit({ date_of_birth: '1961-05-12' })}
        subjectName="Rohan Mehta"
        subjectDob="1978-01-01"
        onOpenSlideOut={() => {}}
      />,
    );
    expect(screen.getByText(/Would upgrade to high if DOB matches/)).toBeInTheDocument();
  });

  it('prefers a server-side reasoning_trace.counterfactual when provided', () => {
    const hit = {
      ...makeHit(),
      reasoning_trace: { counterfactual: 'Server says: re-run with relaxed DOB tolerance.' },
    } as unknown as ScreeningHit;
    render(
      <ScreeningExplainer
        hit={hit}
        subjectName="Rohan Mehta"
        subjectDob="1978-01-01"
        onOpenSlideOut={() => {}}
      />,
    );
    expect(screen.getByText('Server says: re-run with relaxed DOB tolerance.')).toBeInTheDocument();
  });

  it('renders source list footer', () => {
    render(
      <ScreeningExplainer
        hit={makeHit({ source_lists: ['OFAC SDN', 'Other List'] })}
        subjectName="Rohan Mehta"
        subjectDob={null}
        onOpenSlideOut={() => {}}
      />,
    );
    expect(screen.getByText(/Source: OFAC SDN · Other List/)).toBeInTheDocument();
  });

  it('fires onOpenSlideOut(hit.hit_id) on click', () => {
    const fn = vi.fn();
    render(
      <ScreeningExplainer
        hit={makeHit()}
        subjectName="Rohan Mehta"
        subjectDob="1978-01-01"
        onOpenSlideOut={fn}
      />,
    );
    fireEvent.click(screen.getByTestId('screening-explainer-hit_mock_abc'));
    expect(fn).toHaveBeenCalledWith('hit_mock_abc');
  });

  it('applies the dimmed treatment when dismissed but stays clickable', () => {
    const fn = vi.fn();
    render(
      <ScreeningExplainer
        hit={makeHit()}
        subjectName="Rohan Mehta"
        subjectDob="1978-01-01"
        dimmed
        onOpenSlideOut={fn}
      />,
    );
    const card = screen.getByTestId('screening-explainer-hit_mock_abc');
    expect(card).toHaveAttribute('data-dismissed', 'true');
    fireEvent.click(card);
    expect(fn).toHaveBeenCalledWith('hit_mock_abc');
  });
});
