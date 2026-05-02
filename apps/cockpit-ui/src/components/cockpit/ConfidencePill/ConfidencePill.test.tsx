// Tests for ConfidencePill — Story 3.7 / AC #8.

import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ConfidenceBand } from '@/lib/confidence';
import { ConfidencePill } from './ConfidencePill';
import { bandLabel } from './bandLabel';

// ───────────── 4 bands × 3 variants ─────────────

describe('band × variant matrix', () => {
  const cases: Array<[number, ConfidenceBand, string]> = [
    [0.92, ConfidenceBand.HIGH, 'High'],
    [0.78, ConfidenceBand.MEDIUM_HIGH, 'Med-High'],
    [0.62, ConfidenceBand.MEDIUM_LOW, 'Medium'],
    [0.18, ConfidenceBand.LOW, 'Low'],
  ];
  const variants: Array<'inline-small' | 'inline-default' | 'panel-header'> = [
    'inline-small',
    'inline-default',
    'panel-header',
  ];

  for (const [confidence, band, label] of cases) {
    for (const variant of variants) {
      it(`renders ${band} band in ${variant} variant`, () => {
        render(<ConfidencePill confidence={confidence} variant={variant} />);
        const pill = screen.getByRole('img');
        // shape attribute matches the band
        expect(pill.querySelector(`[data-band-shape="${band}"]`)).toBeTruthy();
        if (variant === 'inline-small') {
          // No visible label
          expect(pill.textContent).not.toContain(label);
        } else {
          expect(pill.textContent).toContain(label);
        }
      });
    }
  }
});

// ───────────── numeric formatting ─────────────

describe('numeric formatting', () => {
  it('rounds confidence to nearest integer percent', () => {
    render(<ConfidencePill confidence={0.624} variant="inline-default" showNumeric />);
    expect(screen.getByRole('img').textContent).toContain('62%');
  });

  it('renders 100% for confidence=1.0', () => {
    render(<ConfidencePill confidence={1.0} variant="inline-default" showNumeric />);
    expect(screen.getByRole('img').textContent).toContain('100%');
  });

  it('panel-header variant defaults to showing numeric', () => {
    render(<ConfidencePill confidence={0.85} variant="panel-header" />);
    expect(screen.getByRole('img').textContent).toContain('85%');
  });

  it('inline-small without showNumeric does not render visible percent', () => {
    render(<ConfidencePill confidence={0.62} variant="inline-small" />);
    const pill = screen.getByRole('img');
    expect(pill.textContent).not.toContain('%');
    // But aria-label still includes the percent for AT
    expect(pill.getAttribute('aria-label')).toContain('62%');
  });
});

// ───────────── unknown state ─────────────

describe('unknown state', () => {
  let warnSpy: ReturnType<typeof vi.spyOn>;
  beforeEach(() => {
    warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
  });
  afterEach(() => {
    warnSpy.mockRestore();
  });

  it.each([Number.NaN, Number.POSITIVE_INFINITY, -0.1, 1.1])(
    'renders unknown for invalid confidence %s',
    (bad) => {
      render(<ConfidencePill confidence={bad} variant="inline-default" />);
      const pill = screen.getByRole('img');
      expect(pill.querySelector('[data-band-shape="unknown"]')).toBeTruthy();
      expect(pill.textContent).toContain('Unknown');
      expect(warnSpy).toHaveBeenCalled();
    },
  );

  it('renders unknown when explicit band mismatches confidence', () => {
    render(
      <ConfidencePill confidence={0.62} band={ConfidenceBand.HIGH} variant="inline-default" />,
    );
    const pill = screen.getByRole('img');
    expect(pill.querySelector('[data-band-shape="unknown"]')).toBeTruthy();
    expect(warnSpy).toHaveBeenCalled();
  });
});

// ───────────── interactive ─────────────

describe('interactive variant', () => {
  it('renders <button> when interactive', () => {
    const onClick = vi.fn();
    render(<ConfidencePill confidence={0.92} interactive onClick={onClick} />);
    expect(screen.getByRole('button')).toBeTruthy();
  });

  it('click invokes onClick', () => {
    const onClick = vi.fn();
    render(<ConfidencePill confidence={0.92} interactive onClick={onClick} />);
    fireEvent.click(screen.getByRole('button'));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('is not a button when not interactive', () => {
    render(<ConfidencePill confidence={0.92} />);
    expect(screen.queryByRole('button')).toBeNull();
    expect(screen.getByRole('img')).toBeTruthy();
  });

  it('aria-label of button includes click hint', () => {
    render(<ConfidencePill confidence={0.92} interactive onClick={() => {}} />);
    expect(screen.getByRole('button').getAttribute('aria-label')).toContain('click to inspect');
  });
});

// ───────────── bandLabel helper ─────────────

describe('bandLabel helper', () => {
  it.each([
    [ConfidenceBand.HIGH, 'High'],
    [ConfidenceBand.MEDIUM_HIGH, 'Med-High'],
    [ConfidenceBand.MEDIUM_LOW, 'Medium'],
    [ConfidenceBand.LOW, 'Low'],
    ['unknown' as const, 'Unknown'],
  ])('maps %s to %s', (band, expected) => {
    expect(bandLabel(band)).toBe(expected);
  });
});
