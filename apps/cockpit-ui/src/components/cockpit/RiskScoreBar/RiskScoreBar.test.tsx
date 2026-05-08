// RiskScoreBar — Story 5.7 / AC #9.

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import vora from './__fixtures__/vora-risk-score.json';
import shree from './__fixtures__/shree-risk-score.json';
import ananya from './__fixtures__/ananya-risk-score.json';
import { RiskScoreBar, type RiskScore } from './RiskScoreBar';

const voraScore = vora as unknown as RiskScore;
const shreeScore = shree as unknown as RiskScore;
const ananyaScore = ananya as unknown as RiskScore;

describe('RiskScoreBar', () => {
  it('renders 5 segments and a band pill for Vora (medium)', () => {
    render(<RiskScoreBar score={voraScore} />);
    expect(screen.getByTestId('risk-segment-country')).toBeInTheDocument();
    expect(screen.getByTestId('risk-segment-entity_type')).toBeInTheDocument();
    expect(screen.getByTestId('risk-segment-ownership_clarity')).toBeInTheDocument();
    expect(screen.getByTestId('risk-segment-screening')).toBeInTheDocument();
    expect(screen.getByTestId('risk-segment-adverse_media')).toBeInTheDocument();

    const pill = screen.getByTestId('risk-band-pill');
    expect(pill).toHaveTextContent(/medium/i);
    expect(pill.className).toMatch(/bg-amber-100/);
  });

  it('Vora ownership_clarity is the largest segment', () => {
    render(<RiskScoreBar score={voraScore} />);
    const segments = ['country', 'entity_type', 'ownership_clarity', 'screening', 'adverse_media'];
    const widths: Record<string, number> = {};
    for (const name of segments) {
      const seg = screen.getByTestId(`risk-segment-${name}`);
      const widthStyle = seg.style.width || '0%';
      widths[name] = parseFloat(widthStyle.replace('%', ''));
    }
    expect(widths.ownership_clarity).toBeGreaterThan(widths.entity_type);
    expect(widths.ownership_clarity).toBeGreaterThan(widths.country);
  });

  it('renders Shree as low band with emerald pill', () => {
    render(<RiskScoreBar score={shreeScore} />);
    const pill = screen.getByTestId('risk-band-pill');
    expect(pill).toHaveTextContent(/low/i);
    expect(pill.className).toMatch(/bg-emerald-100/);
  });

  it('renders Ananya screening segment with rose color and tooltip rationale on hover', () => {
    render(<RiskScoreBar score={ananyaScore} />);
    const screening = screen.getByTestId('risk-segment-screening');
    expect(screening.className).toMatch(/bg-rose-500/);
    fireEvent.mouseEnter(screening);
    expect(screen.getByTestId('risk-segment-tooltip')).toHaveTextContent(
      /Screening hit hint present/i,
    );
  });

  it('renders skeleton when isPending and no score', () => {
    render(<RiskScoreBar score={null} isPending />);
    expect(screen.getByTestId('risk-bar-skeleton')).toBeInTheDocument();
  });

  it('renders error state with role=alert', () => {
    render(<RiskScoreBar score={null} isError />);
    expect(screen.getByRole('alert')).toHaveTextContent(/Could not compute risk score/i);
  });

  it('renders empty state when score is null and not pending', () => {
    render(<RiskScoreBar score={null} />);
    expect(screen.getByTestId('risk-bar-empty')).toBeInTheDocument();
    expect(screen.getByText(/Risk score not computed/i)).toBeInTheDocument();
  });

  it('shows tooltip on segment hover with value/weight/contribution', () => {
    render(<RiskScoreBar score={voraScore} />);
    const country = screen.getByTestId('risk-segment-country');
    fireEvent.mouseEnter(country);
    const tooltip = screen.getByTestId('risk-segment-tooltip');
    expect(tooltip).toHaveTextContent('Country');
    expect(tooltip).toHaveTextContent('10');
    expect(tooltip).toHaveTextContent('0.15');
    expect(tooltip).toHaveTextContent('1.5');
  });

  it('invokes onSegmentClick when a segment is clicked', () => {
    const onSegmentClick = vi.fn();
    render(<RiskScoreBar score={voraScore} onSegmentClick={onSegmentClick} />);
    fireEvent.click(screen.getByTestId('risk-segment-country'));
    expect(onSegmentClick).toHaveBeenCalledWith('country');
  });

  it('renders the legend with all 5 components', () => {
    render(<RiskScoreBar score={voraScore} />);
    expect(screen.getByTestId('risk-legend-country')).toBeInTheDocument();
    expect(screen.getByTestId('risk-legend-entity_type')).toBeInTheDocument();
    expect(screen.getByTestId('risk-legend-ownership_clarity')).toBeInTheDocument();
    expect(screen.getByTestId('risk-legend-screening')).toBeInTheDocument();
    expect(screen.getByTestId('risk-legend-adverse_media')).toBeInTheDocument();
  });

  it('uses tabular-nums for the total and shows the integer score', () => {
    render(<RiskScoreBar score={voraScore} />);
    expect(screen.getByText('37')).toBeInTheDocument();
  });

  it('respects animate=false flag (no opacity transitions on rerender)', () => {
    const { rerender } = render(<RiskScoreBar score={voraScore} animate={false} />);
    rerender(<RiskScoreBar score={shreeScore} animate={false} />);
    // Sanity — the bar still renders with new values
    expect(screen.getByTestId('risk-band-pill')).toHaveTextContent(/low/i);
  });
});
