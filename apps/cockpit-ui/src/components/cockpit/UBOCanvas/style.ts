// Edge styling + label helpers for UBOCanvas — Story 5.4 / AC #4, #5.
//
// react-flow `edge.style` is a CSS style object (not a className), so the
// Tailwind palette must be expanded to hex inline. Mirrors Story 3.7's
// ConfidencePill colors.

import type { CSSProperties } from 'react';
import type { UBOEdge } from './adapter';

const NOMINEE_RED = '#dc2626'; // rose-600
const OFFICER_GREEN = '#059669'; // emerald-600

const BAND_STROKE: Record<string, string> = {
  high: '#059669', // emerald-600
  medium_high: '#0284c7', // sky-600
  medium_low: '#d97706', // amber-600
  low: '#dc2626', // rose-600
};

export function edgeStyle(edge: UBOEdge): CSSProperties {
  if (edge.nominee_flag === 'nominee_suspected') {
    return { stroke: NOMINEE_RED, strokeWidth: 2, strokeDasharray: '6,4' };
  }
  if (edge.nominee_flag === 'officer_corrected') {
    return { stroke: OFFICER_GREEN, strokeWidth: 2 };
  }
  const band = edge.confidence.provenance.confidence_band;
  const stroke = BAND_STROKE[band] ?? BAND_STROKE.low;
  return { stroke, strokeWidth: 1.5 };
}

const DESIGNATION_INITIAL: Record<string, string> = {
  director: 'D',
  managing_director: 'MD',
  additional_director: 'AD',
  nominee_director: 'ND',
};

export function edgeLabel(edge: UBOEdge): string {
  if (edge.kind === 'owns') {
    return `${edge.ownership_pct ?? 0}%`;
  }
  if (edge.kind === 'beneficial') {
    return `B${edge.ownership_pct ?? 0}%`;
  }
  // director
  return DESIGNATION_INITIAL[edge.designation ?? 'director'] ?? 'D';
}

export function bandLabelText(band: string): string {
  switch (band) {
    case 'high':
      return 'High';
    case 'medium_high':
      return 'Med-High';
    case 'medium_low':
      return 'Med-Low';
    case 'low':
      return 'Low';
    default:
      return band;
  }
}
