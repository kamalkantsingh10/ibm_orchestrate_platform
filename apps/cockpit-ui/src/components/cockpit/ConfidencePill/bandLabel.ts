// bandLabel — separated from ConfidencePill.tsx so the component file
// only exports React components (react-refresh constraint).
//
// Per UX spec § ConfidencePill: MEDIUM_LOW labels as "Medium" (not
// "Med-Low") for visual simplicity at the lower end of the band.

import { ConfidenceBand } from '@/lib/confidence';

export type BandOrUnknown = ConfidenceBand | 'unknown';

export function bandLabel(band: BandOrUnknown): string {
  switch (band) {
    case ConfidenceBand.HIGH:
      return 'High';
    case ConfidenceBand.MEDIUM_HIGH:
      return 'Med-High';
    case ConfidenceBand.MEDIUM_LOW:
      return 'Medium';
    case ConfidenceBand.LOW:
      return 'Low';
    case 'unknown':
      return 'Unknown';
  }
}
