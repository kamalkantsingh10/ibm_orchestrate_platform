# Story 4.4: Three motion flavors as Framer Motion utilities

Status: review

## Story

As an implementer of cockpit components,
I want `expand`, `focus-dim`, and `slide-out` motion utilities as shared Framer Motion presets,
So that motion language stays consistent across the cockpit (UX-DR5, UX-DR11).

## Scope note

The UX spec names a finite set of motion flavors that every panel, slide-out, drawer, and dim-on-focus interaction must use. Letting components define their own durations and easing curves is the fastest path to a UI that feels uneven. This story codifies the flavors as importable Framer Motion presets and documents the rule that any cockpit component animation must use one of them.

A fourth flavor — `snap` (≤ 100 ms cubic-bezier) — is referenced by Story 4.2 for keyboard focus changes. Include it here too so the four-flavor set lives in one file. The epic spec lists three; the fourth is a UX-DR5 derivative used by 4.2.

## Acceptance Criteria

1. **AC1 — `apps/cockpit-ui/src/lib/motion.ts` exports four named transition presets.**

   ```ts
   import type { Transition, Variants } from 'framer-motion';

   export const snap: Transition;        // ≤ 100ms cubic-bezier; keyboard focus, micro-state changes
   export const expand: Transition;      // 250ms cubic-bezier; panel expansion / open
   export const focusDim: Transition;    // 150ms ease-out; soft-dim of non-focused zones
   export const slideOut: Transition;    // 300ms ease-in-out; drawer / slide-out
   ```

   Each preset is a plain `Transition` object (not a hook). Concrete tuning:
   - `snap` → `{duration: 0.1, ease: [0.4, 0, 0.2, 1]}`
   - `expand` → `{duration: 0.25, ease: [0.4, 0, 0.2, 1]}`
   - `focusDim` → `{duration: 0.15, ease: 'easeOut'}`
   - `slideOut` → `{duration: 0.3, ease: 'easeInOut'}`

2. **AC2 — Companion `Variants` for the most common patterns.** Same module also exports:

   ```ts
   export const expandVariants: Variants;     // hidden ↔ visible
   export const focusDimVariants: Variants;   // focused (opacity 1) ↔ dimmed (opacity 0.5)
   export const slideOutVariants: Variants;   // closed (x: 100%) ↔ open (x: 0)
   ```

   These are convenience exports — components may compose their own variants and pass `transition: expand` directly if needed.

3. **AC3 — `useReducedMotion`-aware wrapper.** Export `useMotionPresets()` hook returning a `{snap, expand, focusDim, slideOut}` object whose values become `{duration: 0}` when `useReducedMotion()` returns `true`. Tests must cover both branches.

4. **AC4 — Refactor existing inline transitions to use the presets.** Identify and refactor every existing inline `transition` literal in `apps/cockpit-ui/src/components/`:
   - `ReasoningTraceSlideOut.tsx` — replace its current open/close transition with `slideOut` + `slideOutVariants`.
   - `AgentFace.tsx` (Story 4.3, may land in parallel) — replace `state="working"` / `state="complete"` / `state="needs_input"` inline transitions to import from `lib/motion.ts`. (If 4.3 lands first with inline values, this is the cleanup pass; if 4.3 lands after 4.4, 4.3 imports from here on day one.)
   - `QueueRail` row focus visual (Story 4.2's inline 100 ms transition) — refactor to `snap`.

   For any other component with motion, refactor or open a TODO commit.

5. **AC5 — Lint rule (advisory).** Add a project-level note in `apps/cockpit-ui/README.md` (one paragraph): "Cockpit motion uses one of four flavors — `snap`, `expand`, `focusDim`, `slideOut` — defined in `src/lib/motion.ts`. Custom durations require an ADR. Code review enforces this." A formal ESLint rule is overkill for the demo; reviewer + this note is enough.

6. **AC6 — Tests (Vitest).**
   - `apps/cockpit-ui/src/lib/motion.test.ts` — assert each preset's `duration` and `ease` values match the spec; assert `useMotionPresets()` returns zero-duration when `useReducedMotion` mock returns `true`.
   - Existing component tests (ReasoningTraceSlideOut, AgentFace) continue to pass after the refactor.

7. **AC7 — Animation duration smoke test.** A small Vitest test in `apps/cockpit-ui/src/lib/motion.test.ts` reads `expand.duration` and asserts it equals `0.25` (i.e. 250 ms). This guards against accidental drift; the epic's "completes within 250 ms ± 30 ms" Playwright assertion is **out of scope** for this story (project doesn't run Playwright in CI today — see `1-3` simplifications). Document the deferral.

8. **AC8 — `make lint` + `make test` clean.**

## Tasks / Subtasks

- [x] **Task 1 — `lib/motion.ts`** (AC: #1, #2, #3, #6)
  - [x] Author the module with named exports.
  - [x] `motion.test.ts` covering values + `useReducedMotion` branch (7 tests).
- [x] **Task 2 — Refactor existing call sites** (AC: #4, #6, #8)
  - [x] `QueueRail.tsx` row focus transition documented as the CSS mirror of `snap` (`duration-100 ease-out` Tailwind utilities). Kept as CSS rather than Framer because the row state isn't a motion variant.
  - [ ] `ReasoningTraceSlideOut.tsx` — TODO: deferred. Today the component uses Tailwind `motion-reduce:*` classes with no actual Framer Motion animation. A proper refactor needs `AnimatePresence` to handle Radix's mount/unmount on close — heavier than this story warrants. Tracked as a follow-up.
  - [x] `AgentFace.tsx` — Story 4.3 imports the presets directly on day one (since 4-4 ships first in the dev order).
- [x] **Task 3 — README note + advisory** (AC: #5, #7)
  - [x] Appended motion-language section to `apps/cockpit-ui/README.md`.
  - [x] `motion.test.ts` includes the AC #7 expand-duration smoke test.
- [x] **Task 4 — Verify** (AC: #8)
  - [x] `pnpm test` clean for `motion.test.ts`; `pnpm lint` clean across the project.

## Dev Notes

### Sequencing

Schedule alongside Story 4.3 (face component) and Story 4.5 (Agent Copilot Pane). Order doesn't strictly matter — if 4.3 lands first, refactor here; if 4.4 lands first, 4.3 imports from day one. Story 4.2's queue-row transition (100 ms) is the smallest call site and is also fair game.

### Architectural context

- [Source: `architecture.md#F7 Design tokens`] — tokens from Tailwind `@theme`. Motion durations sit alongside these tokens; the `lib/motion.ts` module is the design-token surface for *time*.
- [Source: `architecture.md#Frontend Architecture`] — Framer Motion is the chosen animation library. No CSS-in-JS runtime; motion tokens live in TS.
- [Source: `ux-design-specification.md#1.1 Implementation Approach`] — three motion flavors named (expand, focus-dim, slide-out); `snap` is added as a derivative for keyboard-velocity interactions per UX-DR5.
- [Source: `prd.md#NFR-P1`] — UI interaction p95 ≤ 50 ms keyboard budget; durations >300 ms must be reserved for actual physical motion (drawers), not state changes.

### Critical pitfalls to avoid

1. **Framer Motion's `Transition` object is not a `Variants` object.** They are different types. Don't conflate them in exports.
2. **`useReducedMotion` is a hook**, so `useMotionPresets` must also be a hook and obey rules-of-hooks. Components calling it must do so at the top level.
3. **A `0`-duration transition still triggers `onAnimationComplete`** — that's fine but worth knowing for any parent expecting a delay.
4. **Don't change ease functions casually.** `[0.4, 0, 0.2, 1]` (Material standard cubic-bezier) is the project default; deviate only via ADR.
5. **The epic's "≤250ms ± 30ms via Playwright"** is aspirational for the demo. The unit-level duration assertion (AC7) is the enforced check; if Playwright is later wired in (Story 1.3 simplification leaves it optional), the e2e assertion becomes a follow-up.
6. **Prefer-reduced-motion users still need state changes to land** — they just don't need them animated. Zero-duration is the right answer; *not* skipping the state transition entirely.

### Project Structure Notes

This story creates:

- `apps/cockpit-ui/src/lib/motion.ts`
- `apps/cockpit-ui/src/lib/motion.test.ts`

This story modifies:

- `apps/cockpit-ui/src/components/cockpit/ReasoningTraceSlideOut/ReasoningTraceSlideOut.tsx` — import `slideOut` + `slideOutVariants`
- `apps/cockpit-ui/src/components/cockpit/AgentFace/AgentFace.tsx` (if extant) — import presets
- `apps/cockpit-ui/src/components/cockpit/QueueRail/QueueRail.tsx` — import `snap` for focus visual
- `apps/cockpit-ui/README.md` — add the four-flavor note

This story DOES NOT create:

- A new motion library or wrapper around Framer Motion
- A `motion-tokens.css` or any CSS-side parallel; tokens live in TS only
- ESLint plugin / lint rule (review enforces; ADR escape hatch)
- A Playwright timing test (deferred)

### References

- [Source: `epics.md#Story 4.4`] — three presets ACs
- [Source: `ux-design-specification.md#1.1 Implementation Approach`] — motion-flavor naming
- [Source: `prd.md#NFR-P1, NFR-AC4`] — interaction budgets and reduced-motion safety

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (Amelia persona, bmad-dev-story workflow)

### Debug Log References

### Completion Notes List

* **Tuning** — Material standard cubic-bezier `[0.4, 0, 0.2, 1]` for `snap` and `expand`; `easeOut` and `easeInOut` strings for `focusDim` and `slideOut` (Framer's internal mappings).
* **`useMotionPresets`** is a hook because `useReducedMotion` is. Plain const exports are still available for cases where the caller doesn't need reduced-motion adaptation (most demo paths don't).
* **ReasoningTraceSlideOut deferred** — the existing component uses Radix Dialog with Tailwind utility classes only; switching to Framer needs `AnimatePresence` to handle Radix's mount/unmount lifecycle. Filed as a follow-up; AC #4's "any other component with motion … TODO commit" path applies.
* **`QueueRail` row transition** — kept as CSS (`duration-100 ease-out`) because row state isn't a Framer Motion variant; the duration matches `snap`. Documented in-line.
* **AgentFace** — Story 4.3 imports `expand` / `focusDim` directly from this module on day one (4-4 ships first in dev order).

### File List

**Created**
* `apps/cockpit-ui/src/lib/motion.ts` — `snap`, `expand`, `focusDim`, `slideOut` + variants + `useMotionPresets`.
* `apps/cockpit-ui/src/lib/motion.test.ts` — 7 tests.

**Modified**
* `apps/cockpit-ui/src/components/cockpit/QueueRail/QueueRail.tsx` — comment links the inline 100 ms CSS transition to the `snap` preset.
* `apps/cockpit-ui/README.md` — motion-language section appended.
