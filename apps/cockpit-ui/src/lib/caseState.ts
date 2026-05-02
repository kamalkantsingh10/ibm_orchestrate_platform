// Case state → display label + Tailwind classes. Story 2.3 AC #3.
//
// Consumed by QueueRail row badges (this story) and the future Audit Trail
// timeline (Story 9-1). Keep the mapping in one place so the demo's badge
// vocabulary stays consistent.

import type { CaseState } from '@/lib/types/case';

export interface StateBadge {
  label: string;
  // Tailwind classes for background + text — applied to the badge wrapper.
  classes: string;
}

export const CASE_STATE_BADGES: Record<CaseState, StateBadge> = {
  intake_scheduled: {
    label: 'Intake scheduled',
    classes: 'bg-slate-100 text-slate-800',
  },
  decision_ready: {
    label: 'Ready',
    classes: 'bg-blue-100 text-blue-800',
  },
  committed: {
    label: 'Committed',
    classes: 'bg-green-100 text-green-800',
  },
  escalated: {
    label: 'Escalated',
    classes: 'bg-amber-100 text-amber-800',
  },
  closed: {
    label: 'Closed',
    classes: 'bg-zinc-100 text-zinc-600',
  },
};

export function badgeFor(state: CaseState): StateBadge {
  return CASE_STATE_BADGES[state];
}
