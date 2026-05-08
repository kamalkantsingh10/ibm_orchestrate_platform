# Story 8.1: ⌘+4 mode switch to Zen

Status: review

## Story

As a KYC Analyst,
I want to switch into SAR/EDD Writing Zen mode via ⌘+4,
So that my environment changes when I shift to narrative work (FR4 full, FR25, UX-DR22).

## Scope note

This story wires the `zen` mode as a real, transitionable mode. The keystroke handler, the mode store update, and the entry/exit transition motion are the deliverables. **The visual treatment of Zen mode itself is Story 8.2** — this story only ensures the switch fires.

**Dependency on Story 4-7 (mode switcher):** the mode store and the existing keyboard bindings (⌘1 Investigation, etc.) are the surface this story extends.

**Coordination with Epic 12 (if in flight):** Story 12.1 builds a 6-mode segmented control with `Zen` listed under the `Memo` segment label — if 12.1 has landed, this story flips the `Memo` segment from `disabled` to `active` and points its `⌘4` shortcut at the zen mode store. If 12.1 has not landed, this story uses the existing Story 4-7 mode switcher and adds zen as a fourth active mode. Either way, the mode store state value `zen` is the single source of truth.

## Acceptance Criteria

1. **AC1 — `⌘+4` keystroke switches to Zen.** A new keyboard handler in `apps/cockpit-ui/src/components/cockpit/CommandPalette/keyboard.ts` (or wherever Story 4-7's mode shortcuts live) maps `⌘+4` (and `Ctrl+4` on non-Mac) to `setMode('zen')`. The handler is registered on case routes only (`/cases/:caseId`), not on `/queue` or `/approvals`.

2. **AC2 — Mode store update.** `apps/cockpit-ui/src/stores/modeStore.ts` (the existing mode store from Story 4-7) accepts `'zen'` as a valid mode value. Switching to `zen` from any other mode persists the mode in URL state (`?mode=zen`) so deep-linking and reload preserve the user's mode.

3. **AC3 — Transition uses `expand` preset.** The transition into Zen mode runs the `expand` Framer Motion preset (from Story 4-4) at 250ms duration. The transition out of Zen back to Investigation uses the inverse preset at the same duration. No transition uses default browser easing.

4. **AC4 — Mode is route-gated.** Pressing `⌘+4` on `/queue`, `/approvals`, or `/regulator-lens` is a no-op (or shows the existing toast pattern from Story 12.1's mode switcher saying "Zen mode is only available inside a case"). The mode store does not switch.

5. **AC5 — Tests.** New tests in `modeStore.test.ts`:
   - `accepts_zen_as_a_valid_mode_value`
   - `cmd_4_switches_to_zen_only_on_case_routes`
   - `transition_uses_expand_preset_at_250ms`

6. **AC6 — `make lint` + `make test` clean.**

## Tasks / Subtasks

- [x] **Task 1 — Mode store** (AC: #2)
  - [x] Add `'zen'` to the mode union type in `modeStore.ts` (already present from 4.7; verified)
  - [x] Wire URL state persistence (`?mode=` read on init, `history.replaceState` on `setMode`)
- [x] **Task 2 — Keystroke binding** (AC: #1, #4)
  - [x] Register `⌘+4` / `Ctrl+4` on case routes (in `useGlobalShortcuts.ts`)
  - [x] No-op on non-case routes (toast: "Zen mode is only available inside a case")
- [x] **Task 3 — Transition motion** (AC: #3)
  - [x] Wrap the case canvas in a Framer Motion `<AnimatePresence>` that uses the `expand` preset on `mode` change
- [x] **Task 4 — Tests** (AC: #5, #6)
  - [x] Update `modeStore.test.ts` (3 named tests)
  - [x] `make lint` clean
  - [x] `pnpm vitest` clean for the touched files (modeStore + useGlobalShortcuts + motion = 26/26)
  - [x] Update `Documentation/implementation-artifacts/sprint-status.yaml` to `review`

## Dev Notes

- **Zen mode visual treatment lands in 8.2.** This story produces a working ⌘+4 switch that toggles the mode store value but visually only triggers the transition motion — the dark canvas, large type, evidence dock, etc. all come in 8.2. After 8.1 alone, pressing ⌘+4 will run the `expand` motion on the existing Investigation layout.
- **The `expand` preset** is documented in `apps/cockpit-ui/src/lib/motion.ts` from Story 4-4. Reuse, don't redefine.
- **Route-gating** is intentional: zen is a writing mode that only makes sense inside a case context.

### File List

**Modified**
- `apps/cockpit-ui/src/stores/modeStore.ts` — `?mode=` URL persistence (read on hydration, `history.replaceState` on `setMode`)
- `apps/cockpit-ui/src/stores/modeStore.test.ts` — three Story 8.1 named tests + URL-persistence assertion
- `apps/cockpit-ui/src/hooks/useGlobalShortcuts.ts` — `⌘+4` / `Ctrl+4` branch with `_isCaseRoute()` guard; off-route toast
- `apps/cockpit-ui/src/hooks/useGlobalShortcuts.test.tsx` — three new tests (Cmd+4 on-route, Cmd+4 off-route toast, Ctrl+4 binding); `beforeEach` resets `window.history`
- `apps/cockpit-ui/src/routes/cases.$caseId.tsx` — case canvas wrapped in `<AnimatePresence><motion.div key={mode} variants={expandVariants} transition={expand}>` so mode change fires the 250ms preset

## Dev Agent Record

### Implementation Plan

1. **modeStore.ts** — kept the existing `Mode` union (`'investigation' | 'zen' | 'regulator-lens'`); the `'zen'` literal was already present from Story 4.7's stub. Added private `_readUrlMode()` / `_writeUrlMode()` helpers that round-trip via `URLSearchParams`. Initial state hydrates from `?mode=` if valid; `setMode` writes the URL via `window.history.replaceState` before mutating zustand state. SSR-safe via `typeof window` guard.

2. **useGlobalShortcuts.ts** — extended the existing `Cmd+1..6` branch with an explicit `e.key === '4'` arm. On case routes (`window.location.pathname.startsWith('/cases/')`) it sets `mode='zen'` and announces; off-route it toasts "Zen mode is only available inside a case". The `_isCaseRoute()` helper is private and SSR-safe. Description copy on Cmd+2/3/5/6 toast updated to reflect Zen now wired.

3. **cases.$caseId.tsx** — pulled `mode` from the store, then wrapped the entire `<main>` content (header + Tabs.Root) in `<AnimatePresence mode="wait" initial={false}><motion.div key={mode} variants={expandVariants} initial="hidden" animate="visible" exit="hidden" transition={expand}>`. `mode` keying triggers the `expand` (250ms) preset on every transition, including out-of-Zen back to Investigation. The pre-existing focusDim grid wrapper inside the Overview tab is untouched.

4. **modeStore.test.ts** — three story-named tests: `accepts_zen_as_a_valid_mode_value` (sets mode + asserts URL), `cmd_4_switches_to_zen_only_on_case_routes` (renders `useGlobalShortcuts` via `renderHook`, mutates `window.history` between presses), and `transition_uses_expand_preset_at_250ms` (asserts `expand.duration === 0.25` from `@/lib/motion`). Existing 4.7 tests preserved. `beforeEach` resets URL to `/` to keep tests isolated.

5. **useGlobalShortcuts.test.tsx** — added Cmd+4 on-route, Cmd+4 off-route (toast assertion), and Ctrl+4 cross-platform tests. Bumped `beforeEach` to also reset `window.history` so route gating tests stay isolated.

### Completion Notes

- All 4 tasks/subtasks complete; checkboxes marked.
- `pnpm lint` (ESLint, max-warnings=0) — clean.
- `pnpm format:check` (Prettier) — clean (one file auto-fixed via `--write` for indentation under the new wrapper).
- `pnpm vitest run src/stores/modeStore.test.ts src/hooks/useGlobalShortcuts.test.tsx src/lib/motion.test.ts` — **26/26 pass**.
- Pre-existing TypeScript errors in unrelated files (`UBOPanel.tsx`, `useScreeningSubjectResolver.ts`, `useUboCorrection.{ts,test.tsx}`, `caseState.ts`, `humanize.ts`, `motion.test.ts`, `routeFor.ts`, `cases.$caseId.tsx:119`) and pre-existing test failures in `useCase.test.tsx` / `useCases.test.tsx` (network-fetch flake) are out of scope and confirmed present on `HEAD` baseline before any 8.1 changes.
- AC6 framing: `make lint` runs the same `pnpm lint && pnpm format:check` (both clean); `make test` exists, but the broader test suite has the noted pre-existing failures unrelated to 8.1.

### Change Log

| Date       | Change                                          |
|------------|-------------------------------------------------|
| 2026-05-08 | Story 8.1 implemented (Amelia). Status: review. |
