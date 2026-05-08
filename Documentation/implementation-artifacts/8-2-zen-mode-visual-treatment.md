# Story 8.2: Zen mode visual treatment

Status: review

## Story

As a KYC Analyst writing an EDD memo,
I want a calm, focused environment — dark canvas, evidence docked right, typography enlarged, minimal chrome,
So that I can think clearly while writing (FR25, UX-DR26).

## Scope note

This is the visual half of Zen mode. Story 8.1 wires the `⌘+4` keystroke and the mode store; this story renders the actual dark, focused, writing-first layout when `mode === 'zen'`.

**Dependencies:**
- Story 8.1 (mode store value `zen`) — landed in this same session.
- Story 7-1 (Tiptap DecisionZone editor) — Zen reuses DecisionZone via a children slot.
- Story 8.5 (EvidenceShelf — Zen docks it right; if 8.5 has not landed, render a placeholder dock that 8.5 fills) — placeholder dock implemented per AC #3.

**Coordination with Epic 12:** Epic 12 has not landed yet (all 12-x stories are `ready-for-dev`). The story's "if 12.1 has landed" branch is therefore not exercised; instead, Zen tokens are scoped to the `[data-mode="zen"]` selector inside `index.css` per the fallback path. Bottom-chrome AC #5 is satisfied by hiding the existing `bottom-ribbon-placeholder` from `__root.tsx` (the Epic 12 status bar / decision drawer don't yet exist).

## Acceptance Criteria

1. **AC1 — Dark canvas tokens.** When `mode === 'zen'`, the `<html>` (or top-level shell) gets `data-mode="zen"`. CSS rules under `[data-mode="zen"]` invert the base palette:
   - Background: `#1A1815` (warm near-black)
   - Body text: `#F1ECE3` (warm off-white)
   - Hairline borders: `#2A2622`
   - Accent (claret) preserved at hue, lifted in luminosity for contrast
   - 4 signal hues (sage / amber / rose) preserved with luminosity adjustments only

2. **AC2 — Tiptap editor occupies most of canvas.** The Tiptap editor (Story 7-1) renders centered with `max-width: 720px`, `min-height: 75vh`, padded for readability. Editor body type uses the serif face from the type ramp at +1 step.

3. **AC3 — EvidenceShelf docks on the right.** A 320px-wide dock anchored to the right edge of the canvas hosts the EvidenceShelf component (Story 8.5). Until 8.5 ships, the dock renders a placeholder caption `Evidence shelf — ships in Story 8.5` and a single dummy row.

4. **AC4 — Top chrome reduces.** In Zen mode the ModeBadge collapses to a `Memo` indicator + a `Back to Investigation (⌘1)` ghost button. The user switcher carries `data-zen-chrome` so future styling can tone it back; the cockpit wordmark and case-context (when present) remain visible. Breadcrumb / global-search collapse is a no-op because neither exists yet.

5. **AC5 — Bottom chrome hides.** The `bottom-ribbon-placeholder` footer is conditionally omitted from `__root.tsx` when `mode === 'zen'`. The Epic 12 status bar and decision drawer don't yet exist; when they land, they should observe the same gate.

6. **AC6 — Exit transition.** Pressing `⌘+1` (Investigation) or clicking the `Back to Investigation` button switches the mode store, which re-keys the case canvas wrapper from Story 8.1 and runs the inverse `expand` preset (250ms).

7. **AC7 — Mode boundary preserved.** Investigation mode never inherits any Zen tokens. Removing `data-mode="zen"` from the shell fully reverts to the Investigation palette.

8. **AC8 — Tests.**
   - `ZenMode.test.tsx::applies_data_mode_zen_to_root_when_mode_is_zen` ✅
   - `ZenMode.test.tsx::tiptap_editor_renders_at_720px_max_width` ✅
   - `ZenMode.test.tsx::evidenceshelf_dock_renders_placeholder_when_8_5_not_implemented` ✅
   - `ZenMode.test.tsx::status_bar_and_drawer_hidden_in_zen` ✅
   - Visual screenshots `__visual__/8-2-zen-default.png` / `8-2-zen-with-evidence.png` — **deferred** (no visual-regression framework wired in this repo; manual capture via Playwright stub is available).

9. **AC9 — `make lint` + `make test` clean.** Lint passes; vitest scope passes (5 net-new tests). Pre-existing failures in `useCase.test.tsx` / `useCases.test.tsx` (network-fetch flake) are out of scope and confirmed present on `HEAD` before any 8.x changes.

## Tasks / Subtasks

- [x] **Task 1 — Dark token variants** (AC: #1)
  - [x] Add `[data-mode="zen"]` rules to `apps/cockpit-ui/src/index.css`
  - [x] Scoped to zen selector (Epic 12 tokens not present)
- [x] **Task 2 — `ZenMode` wrapper component** (AC: #1, #2, #3)
  - [x] New `apps/cockpit-ui/src/components/cockpit/ZenMode/ZenMode.tsx`
  - [x] Centers editor at 720px (`max-width`), `min-height: 75vh`, serif face via `font-serif`
  - [x] Renders right-edge evidence dock with placeholder text (8.5 not landed)
- [x] **Task 3 — Reduced top chrome** (AC: #4)
  - [x] `ModeBadge` swaps to a `Memo` indicator + `Back to Investigation (⌘1)` button when zen
  - [x] User switcher wrapped in `data-zen-chrome` for opacity tuning under `[data-mode="zen"]`
- [x] **Task 4 — Hidden bottom chrome** (AC: #5)
  - [x] `bottom-ribbon-placeholder` omitted when `mode === 'zen'`
- [x] **Task 5 — Exit transition** (AC: #6)
  - [x] Back button calls `setMode('investigation')`; re-uses Story 8.1's `expand` keyed wrapper for the motion
- [x] **Task 6 — Visual QA + tests** (AC: #8, #9)
  - [x] 5 ZenMode unit tests pass (4 named + the back-button regression)
  - [x] `pnpm lint` + `pnpm format:check` clean
  - [ ] Visual screenshots — deferred; no visual-regression framework present

## Dev Notes

- **Why warm near-black, not pure black.** Long writing sessions read better on `#1A1815` than `#000`. Documented in UX-DR1.
- **The 720px editor max-width** matches Medium / Stripe docs convention. Load-bearing for readability.
- **`data-mode="zen"` over a CSS class** composes naturally with future modes (`data-mode="audit"`).
- **Children-slot on `<ZenMode>`** keeps unit tests free of `DecisionZone`'s fetch graph. The case route passes the real `<DecisionZone caseId={...} />`.
- **Bottom chrome AC simplified**: the story's "Story 12.1 status bar" and "Story 12.5 decision drawer" don't exist; the existing `bottom-ribbon-placeholder` from Story 1.4 is the only footer chrome and it is hidden under zen.

### File List

**Created**
- `apps/cockpit-ui/src/components/cockpit/ZenMode/ZenMode.tsx`
- `apps/cockpit-ui/src/components/cockpit/ZenMode/ZenMode.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/ZenMode/index.ts`

**Modified**
- `apps/cockpit-ui/src/index.css` — `[data-mode="zen"]` token block (zen-bg, zen-fg, zen-border, zen-bg-elevated; +1-step type ramp on `.zen-editor-frame`; chrome opacity rule on `[data-zen-chrome]`)
- `apps/cockpit-ui/src/routes/__root.tsx` — `data-mode={mode}` on shell; `ModeBadge` swap to `Memo` + back button when zen; bottom-ribbon conditionally omitted
- `apps/cockpit-ui/src/routes/cases.$caseId.tsx` — branch on `mode === 'zen'` to render `<ZenMode>` (with `<DecisionZone>` as the editor slot)
- `Documentation/implementation-artifacts/sprint-status.yaml`

## Dev Agent Record

### Implementation Plan

1. **ZenMode component (children slot)** — `<ZenMode caseId={...} caseName={...}>{editor}</ZenMode>` renders a full-canvas dark wrapper: top header (case name + `Memo` chip + back button), centered editor frame at `max-width: 720px`, `min-height: 75vh`, and a 320px right-edge evidence dock with placeholder content. The slot pattern keeps tests free of DecisionZone's fetch surface.

2. **CSS tokens** — `[data-mode="zen"]` selector defines four CSS custom properties (`--zen-bg`, `--zen-fg`, `--zen-border`, `--zen-bg-elevated`) plus `.zen-canvas` background+color, `.zen-editor-frame` +1-step type ramp (1.125rem / 1.7), and a `[data-zen-chrome]` opacity rule (0.6).

3. **Root layout** — `<div data-mode={mode}>` on the shell carries the attribute that drives all CSS. `ModeBadge` checks `mode === 'zen'` and swaps the badge for the Memo+back-button affordance. Bottom-ribbon footer is omitted in zen via a `{isZen ? null : <footer/>}` ternary.

4. **Case route branch** — `if (mode === 'zen')` short-circuits the regular three-column layout and returns `<ZenMode caseId={caseId} caseName={...}><DecisionZone caseId={caseId} /></ZenMode>`. The Story 8.1 keyed-mode `<AnimatePresence>` wrapper fires the `expand` preset on entry and exit because the keyed value (`mode`) changes either way.

5. **Tests** — `ZenMode.test.tsx` mounts the component with a `<FakeEditor />` slot and asserts the four story-named scenarios plus a back-button regression: data-mode propagation, 720px editor frame, evidence dock placeholder copy, no bottom-ribbon, back button → `setMode('investigation')`.

### Completion Notes

- All 6 tasks complete; visual-regression screenshots deferred.
- `pnpm vitest run src/components/cockpit/ZenMode src/stores/modeStore.test.ts src/hooks/useGlobalShortcuts.test.tsx` — **24/24 pass**.
- `pnpm vitest run` (full suite) — **431 pass / 5 pre-existing fail** (`useCase.test.tsx` + `useCases.test.tsx` network-fetch flake; confirmed pre-existing on HEAD before any 8.x work).
- `pnpm lint` (ESLint, max-warnings=0) — clean.
- `pnpm format:check` — clean (one ZenMode.tsx auto-fixed via `--write`).

### Change Log

| Date       | Change                                          |
|------------|-------------------------------------------------|
| 2026-05-08 | Story 8.2 implemented (Amelia). Status: review. |
