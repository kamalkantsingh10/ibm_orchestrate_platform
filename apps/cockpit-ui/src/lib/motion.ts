// Motion presets — Story 4.4.
//
// Four named flavors, four file-scoped constants. Every cockpit animation
// MUST use one of these (custom durations require an ADR — see
// `apps/cockpit-ui/README.md`).
//
// Tuning rationale:
//   - `snap` (100 ms) — keyboard focus, micro-state changes; under the
//     50 ms p95 budget for keyboard interactions plus 50 ms perceptual
//     headroom.
//   - `expand` (250 ms) — panel expansion / open. Material standard
//     cubic-bezier so the easing matches shadcn/ui defaults.
//   - `focusDim` (150 ms) — soft-dim of non-focused zones. Fast enough
//     that the dim never feels intentional/heavy.
//   - `slideOut` (300 ms) — drawer / slide-out. Slow enough to read as
//     spatial motion, fast enough to not block keyboard chains.

import { useReducedMotion, type Transition, type Variants } from 'framer-motion';

const _MATERIAL_STANDARD: [number, number, number, number] = [0.4, 0, 0.2, 1];

export const snap: Transition = { duration: 0.1, ease: _MATERIAL_STANDARD };
export const expand: Transition = { duration: 0.25, ease: _MATERIAL_STANDARD };
export const focusDim: Transition = { duration: 0.15, ease: 'easeOut' };
export const slideOut: Transition = { duration: 0.3, ease: 'easeInOut' };

export const expandVariants: Variants = {
  hidden: { opacity: 0, scale: 0.97 },
  visible: { opacity: 1, scale: 1 },
};

export const focusDimVariants: Variants = {
  focused: { opacity: 1 },
  dimmed: { opacity: 0.5 },
};

export const slideOutVariants: Variants = {
  closed: { x: '100%' },
  open: { x: 0 },
};

export interface MotionPresets {
  snap: Transition;
  expand: Transition;
  focusDim: Transition;
  slideOut: Transition;
}

const _ZERO: Transition = { duration: 0 };
const _REDUCED: MotionPresets = {
  snap: _ZERO,
  expand: _ZERO,
  focusDim: _ZERO,
  slideOut: _ZERO,
};

const _FULL: MotionPresets = { snap, expand, focusDim, slideOut };

/**
 * Story 4.4 AC #3 — returns zero-duration transitions when the user has
 * `prefers-reduced-motion: reduce` set; full presets otherwise. The state
 * change still happens; just instantly.
 */
export function useMotionPresets(): MotionPresets {
  return useReducedMotion() ? _REDUCED : _FULL;
}
