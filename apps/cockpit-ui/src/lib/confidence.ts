// Confidence band mirror of `packages/contracts/src/contracts/confidence.py`
// (Story 3.3). Cross-language parity is asserted by
// `packages/contracts/tests/test_confidence_parity.py` — keep this file in
// lockstep with the Python source.

export const ConfidenceBand = {
  LOW: 'low',
  MEDIUM_LOW: 'medium_low',
  MEDIUM_HIGH: 'medium_high',
  HIGH: 'high',
} as const;
export type ConfidenceBand = (typeof ConfidenceBand)[keyof typeof ConfidenceBand];

// Declining order — `toBand` returns the first band whose threshold is met.
export const CONFIDENCE_THRESHOLDS = [
  { band: ConfidenceBand.HIGH, min: 0.85 },
  { band: ConfidenceBand.MEDIUM_HIGH, min: 0.65 },
  { band: ConfidenceBand.MEDIUM_LOW, min: 0.4 },
  { band: ConfidenceBand.LOW, min: 0.0 },
] as const;

export function toBand(confidence: number): ConfidenceBand {
  if (Number.isNaN(confidence) || !Number.isFinite(confidence)) {
    throw new RangeError(`confidence must be in [0.0, 1.0], got ${confidence}`);
  }
  if (confidence < 0 || confidence > 1) {
    throw new RangeError(`confidence must be in [0.0, 1.0], got ${confidence}`);
  }
  for (const { band, min } of CONFIDENCE_THRESHOLDS) {
    if (confidence >= min) return band;
  }
  return ConfidenceBand.LOW;
}
