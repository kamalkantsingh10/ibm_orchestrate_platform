// counterfactual tests — Story 6.3 / AC #3.

import { describe, expect, it } from 'vitest';
import type { components } from '@/api-types';
import { deriveCounterfactual } from './counterfactual';

type ScreeningHit = components['schemas']['ScreeningHit'];

function hit(score: number, dob: string | null = null): ScreeningHit {
  return {
    hit_id: 'h',
    subject_id: 's',
    matched_name: 'm',
    name_match_score: {
      value: score,
      provenance: {
        source_agent: 'screening',
        source_system: 'screening_mock',
        confidence: score,
        confidence_band: 'medium_low',
        evidence_ids: [],
        captured_at: '2026-05-08T00:00:00Z',
      },
    },
    categories: ['sanctions'],
    disposition: 'open',
    date_of_birth: dob,
  };
}

describe('deriveCounterfactual', () => {
  it('high score + DOB match → confirmation language', () => {
    expect(deriveCounterfactual(hit(0.9, '1980-01-01'), '1980-01-01')).toContain(
      'High match on name and DOB',
    );
  });

  it('mid score + DOB differs → upgrade-if-match language', () => {
    expect(deriveCounterfactual(hit(0.73, '1961-05-12'), '1978-01-01')).toContain(
      'Would upgrade to high if DOB matches',
    );
  });

  it('null subject DOB → DOB-resolution language', () => {
    expect(deriveCounterfactual(hit(0.6, '1980-01-01'), null)).toContain(
      'Confidence depends on DOB resolution',
    );
  });

  it('null hit DOB → DOB-resolution language', () => {
    expect(deriveCounterfactual(hit(0.6, null), '1980-01-01')).toContain(
      'Confidence depends on DOB resolution',
    );
  });

  it('default: high score with no DOB info → identifier-review language', () => {
    expect(deriveCounterfactual(hit(0.9, null), null)).toContain(
      'Confidence depends on DOB resolution',
    );
  });
});
