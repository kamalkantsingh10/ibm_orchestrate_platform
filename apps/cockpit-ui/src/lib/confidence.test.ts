// Tests for confidence banding — Story 3.3 / AC #6.

import { describe, expect, it } from 'vitest';
import { CONFIDENCE_THRESHOLDS, ConfidenceBand, toBand } from './confidence';

describe('toBand — golden cases', () => {
  it.each([
    [0.0, ConfidenceBand.LOW],
    [0.39, ConfidenceBand.LOW],
    [0.4, ConfidenceBand.MEDIUM_LOW],
    [0.64, ConfidenceBand.MEDIUM_LOW],
    [0.65, ConfidenceBand.MEDIUM_HIGH],
    [0.84, ConfidenceBand.MEDIUM_HIGH],
    [0.85, ConfidenceBand.HIGH],
    [1.0, ConfidenceBand.HIGH],
  ])('confidence %f → %s', (confidence, expected) => {
    expect(toBand(confidence)).toBe(expected);
  });
});

describe('toBand — error cases', () => {
  it.each([-0.1, 1.1, Number.NaN, Number.POSITIVE_INFINITY])('rejects out-of-range %s', (bad) => {
    expect(() => toBand(bad)).toThrow(RangeError);
  });
});

describe('CONFIDENCE_THRESHOLDS', () => {
  it('is in declining order', () => {
    const mins = CONFIDENCE_THRESHOLDS.map((row) => row.min);
    const sorted = [...mins].sort((a, b) => b - a);
    expect(mins).toEqual(sorted);
  });

  it('covers all 4 bands exactly once', () => {
    const bands = new Set(CONFIDENCE_THRESHOLDS.map((row) => row.band));
    expect(bands).toEqual(
      new Set([
        ConfidenceBand.LOW,
        ConfidenceBand.MEDIUM_LOW,
        ConfidenceBand.MEDIUM_HIGH,
        ConfidenceBand.HIGH,
      ]),
    );
    expect(CONFIDENCE_THRESHOLDS.length).toBe(4);
  });
});
