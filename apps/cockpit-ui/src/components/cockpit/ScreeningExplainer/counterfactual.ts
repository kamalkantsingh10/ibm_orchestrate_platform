// counterfactual derivation — Story 6.3 / AC #3.
//
// Pure helper. Story 6.4 will introduce a server-side
// `reasoning_trace.counterfactual` on each ScreeningHit; until that lands,
// this client-side derivation is the source. Components should prefer the
// server-side value when present and fall back to this helper.

import type { components } from '@/api-types';

type ScreeningHit = components['schemas']['ScreeningHit'];

export function deriveCounterfactual(hit: ScreeningHit, subjectDob?: string | null): string {
  const score = hit.name_match_score.value;
  const hitDob = hit.date_of_birth ?? null;
  const subjDob = subjectDob ?? null;

  if (score >= 0.85 && subjDob !== null && hitDob !== null && subjDob === hitDob) {
    return 'High match on name and DOB. Disposition would change if officer evidence confirms a different person.';
  }
  if (score < 0.85 && subjDob !== null && hitDob !== null && subjDob !== hitDob) {
    return 'Would upgrade to high if DOB matches; downgrade if address+ID confirm different person.';
  }
  if (subjDob === null || hitDob === null) {
    return 'Confidence depends on DOB resolution. Capture DOB to refine.';
  }
  return 'Disposition depends on officer evidence; review identifiers and source list.';
}
