# Story 12.1: Full-viewport shell, design tokens, chrome, and mode switcher

Status: backlog

## Story

As an officer arriving at the cockpit,
I want the cockpit to fill my entire browser viewport with proper workstation chrome (header, mode switcher, status bar) and a coordinated visual system,
So that the cockpit reads as a tier-1-bank workstation rather than a centered marketing-style page.

## Scope note

This is the foundation story for Epic 12. Three workstreams land together because they all touch the shell (`__root.tsx`) and the global token surface; splitting them creates a thrash window where token migrations ship before the components that consume them are ready.

The three workstreams:

1. **Full-viewport shell.** The cockpit currently centers content inside a max-width container at 1440px+, leaving empty grey gutters. Replace with a CSS grid that fills 100vw × 100vh: `[header 56px] [main 1fr] [statusbar 28px]`. The main row is itself a grid `[queue 320px] [canvas 1fr] [agentrail 360px]` (with the agent rail collapsible to 56px in 12.4).

2. **Design tokens reset.** Reduce the palette to a 10-step graphite scale, one accent (claret), a small set of signal hues. Codify a 7-step type ramp. Pair a low-contrast serif (Source Serif 4) with a humanist sans (Inter Tight). Enable tabular figures globally on numeric containers. Enforce 8px spacing.

3. **Chrome (header + status bar) and 6-mode switcher.** Replace the current orphan "Investigation" pill with a proper segmented control. Build a useful header (monogram + breadcrumb + global search + user) and a useful status bar (ledger count, API health, case ID, keys).

This story does not touch the queue rail, canvas content, or agent pane — those are 12.2/12.3/12.4. It only changes the shell that wraps them and the tokens they inherit.

## Acceptance Criteria

1. **AC1 — Shell is full-viewport.** `apps/cockpit-ui/src/routes/__root.tsx` renders a single CSS grid at `100vw × 100vh` with three rows: `header` (56px) · `main` (1fr) · `statusbar` (28px). The `main` row is itself a grid with three columns: `queue` (320px) · `canvas` (1fr) · `agentrail` (360px). No `max-width`, no `mx-auto`, no decorative side gutters anywhere in the shell. At 1440 × 900 there is no empty grey margin on the left or right of the cockpit.

2. **AC2 — Design tokens (`tailwind.config.ts`).** Replace existing color tokens with:
   - `ink-50`..`ink-900` graphite scale (10 steps; eyedropper-tested for WCAG AA contrast on `paper` background)
   - `paper` (off-white surface, `#FAFAF7` or equivalent)
   - `accent-claret` (single accent, e.g. `#7A1F2B`); `accent-claret-soft` for backgrounds
   - `signal-sage` (positive), `signal-amber` (warning), `signal-rose` (negative)
   - Existing decorative blues (`blue-*`, `sky-*`, `indigo-*`) removed from component code; if any external dependency injects them, alias to `ink-500` for one release.

3. **AC3 — Type ramp (`tailwind.config.ts` + `src/index.css`).** A 7-step ramp with codified line-heights:
   - `text-display` 56/60 (serif, 500)
   - `text-h1` 28/34 (serif, 500)
   - `text-h2` 20/28 (serif, 500)
   - `text-h3` 16/22 (sans, 600)
   - `text-body` 14/22 (sans, 400)
   - `text-caption` 12/18 (sans, 500)
   - `text-micro` 11/16 (sans, 600, uppercase tracking-wide)
   - Body face: Inter Tight (Google Fonts) at 400/500/600
   - Display face: Source Serif 4 (Google Fonts) at 400/500
   - Both fonts loaded with `font-display: swap` via `<link>` tags in `index.html`

4. **AC4 — Tabular figures.** A `.tabular` utility class is added to `index.css` with `font-variant-numeric: tabular-nums slashed-zero`. All numeric values (risk scores, percentages, timestamps, counts) inside the cockpit use it — wired by adding the class to the numeric `<span>` containers. A failing-on-purpose Vitest snapshot in `apps/cockpit-ui/src/__tests__/tokens.test.tsx` asserts the `.tabular` class exists in the rendered DOM for the existing risk score header (`apps/cockpit-ui/src/components/cockpit/RiskPanel/`).

5. **AC5 — 8px spacing.** Tailwind's spacing scale is left default (already 4px-based), but ad-hoc utility classes like `p-3` or `p-5` (which yield 12 or 20 px — off-grid) are migrated to `p-2` (8) or `p-4` (16) or `p-6` (24) across `apps/cockpit-ui/src/components/cockpit/**`. A simple grep audit in the story's PR description lists files touched.

6. **AC6 — Header chrome (`apps/cockpit-ui/src/components/cockpit/CockpitChrome/Header.tsx`).** New file. Renders a single 56px row, full-viewport-width, with three regions:
   - Left: 32×32 monogram tile (placeholder — a `K` glyph in serif on `ink-900` ground) · `Cockpit` wordmark in `text-h3` serif · `/` separator in `ink-300` · breadcrumb (`Queue` on `/queue`, `Queue › <Case Name>` on `/cases/:id`, `Approvals` on `/approvals`, `Regulator Lens` on `/regulator-lens`)
   - Center: a 480px-wide global search trigger button — a `<button>` styled as a search input that, on click or `⌘K`, opens the existing `CommandPalette` component. Placeholder text: `Search cases, agents, fields  ⌘K`.
   - Right: notifications bell icon (placeholder — no dropdown wired in this story) · existing `UserSwitcher` component but reduced to a 32px avatar + name/role caption + caret (no boxed-pill treatment).

7. **AC7 — Status bar (`apps/cockpit-ui/src/components/cockpit/CockpitChrome/StatusBar.tsx`).** New file. Renders a single 28px row, full-viewport-width, hairline `ink-200` top border, `ink-50` background, all text in `text-caption` `ink-500`. Left to right:
   - `Ledger · <n> entries` — read live from `GET /v1/ledger/count` if available, else show `Ledger · synced` (no spinner; static caption is fine for the demo)
   - `API healthy` with a 6px `signal-sage` dot when the most recent fetch succeeded, `signal-rose` if any fetch in the last 30s errored
   - `Last sync · <relative time>` updating every 10s
   - On case routes: `Case · <case_id>` with a click-to-copy icon (uses the same copy affordance pattern as the existing case-detail page)
   - Right: keyboard hint `⌘K · j/k navigate · ? help`
   - The orphan footer-`<contentinfo>` block currently in `__root.tsx` is removed; the StatusBar replaces it.

8. **AC8 — Six-mode segmented control (`apps/cockpit-ui/src/components/cockpit/CockpitChrome/ModeSwitcher.tsx`).** New file. Renders a single segmented control immediately below the header (44px tall row, full-viewport-width, hairline bottom border) with six segments: `Triage` (⌘1) · `Investigate` (⌘2) · `Decide` (⌘3) · `Memo` (⌘4) · `Audit` (⌘5) · `Learn` (⌘6).
   - Each segment shows label in `text-caption` 500 + shortcut in `text-micro` 500 below
   - Active segment: `ink-900` background, `paper` text
   - Inactive segments wired this release: `ink-700` text on `paper` ground, hover → `ink-50` ground
   - Disabled segments (modes not yet built): `ink-300` text, no hover, tooltip "Ships in Epic N"
   - For the demo today, only `Investigate` is active; `Triage` and `Decide` and `Memo` and `Audit` and `Learn` render disabled with epic pointers (Triage→Epic 4 keyboard loop already exists so it can be marked active too if Story 4-2 is `done`; otherwise disabled). The decision is: Investigate active, Triage active, others disabled.
   - Replaces the existing `<div>Investigation</div>` orphan pill in the header.

9. **AC9 — Keyboard wiring.** ⌘1–⌘6 toggle the mode switcher's active segment when the corresponding mode is wired; for disabled segments, the keystroke shows a non-blocking toast via the existing notifications surface ("Decide mode ships in Epic 7"). ⌘K continues to open the command palette. The existing j/k/x/d keyboard handlers from Story 4-2 are unchanged.

10. **AC10 — Visual QA at 1366×768 and 1920×1080.** Manual visual check at both viewports: no horizontal scroll, no overlap, panels grow proportionally, monogram-to-statusbar reads as one cohesive workstation. Two screenshots committed under `apps/cockpit-ui/src/__tests__/__visual__/12-1-shell-1366.png` and `12-1-shell-1920.png` for review reference (not pinned tests).

11. **AC11 — `make lint` + `make test` clean.** No regressions across cockpit-ui, cockpit-api, contracts, agents.

## Tasks / Subtasks

- [ ] **Task 1 — Tokens** (AC: #2, #3, #4, #5)
  - [ ] Update `apps/cockpit-ui/tailwind.config.ts` colors and fontSize scale
  - [ ] Add `Source Serif 4` and `Inter Tight` `<link>` tags to `apps/cockpit-ui/index.html`
  - [ ] Add `.tabular` utility to `src/index.css`
  - [ ] Migrate ad-hoc `p-3`/`p-5` to grid-aligned values across `src/components/cockpit/**`
  - [ ] Add `tokens.test.tsx` snapshot
- [ ] **Task 2 — Full-viewport shell** (AC: #1)
  - [ ] Restructure `src/routes/__root.tsx` to a 3-row × 3-col CSS grid filling `100vw × 100vh`
  - [ ] Remove any `max-w-*` / `mx-auto` wrappers in the shell
- [ ] **Task 3 — Header** (AC: #6)
  - [ ] Create `src/components/cockpit/CockpitChrome/Header.tsx`
  - [ ] Move `UserSwitcher` rendering into Header; reduce its visual weight
  - [ ] Wire breadcrumb to TanStack Router state
  - [ ] Wire global search trigger to the existing `CommandPalette`
- [ ] **Task 4 — Status bar** (AC: #7)
  - [ ] Create `src/components/cockpit/CockpitChrome/StatusBar.tsx`
  - [ ] Wire to the existing API health + case-id state
  - [ ] Remove the empty `<contentinfo>` block from `__root.tsx`
- [ ] **Task 5 — Mode switcher** (AC: #8, #9)
  - [ ] Create `src/components/cockpit/CockpitChrome/ModeSwitcher.tsx`
  - [ ] Define mode→keyboard-shortcut mapping in a small `modes.ts` config alongside the component
  - [ ] Replace the orphan "Investigation" `<div>` in the existing chrome
  - [ ] Wire ⌘1–⌘6 keystrokes via the existing keybinding utility
- [ ] **Task 6 — Visual QA** (AC: #10)
  - [ ] Manual screenshot at 1366×768 and 1920×1080; commit under `__visual__/`
- [ ] **Task 7 — Tests + lint** (AC: #11)
  - [ ] `make lint` clean
  - [ ] `make test` clean (token snapshot + any unit tests for new components)
  - [ ] Update `Documentation/implementation-artifacts/sprint-status.yaml` to `review`

## Dev Notes

- **Inter Tight + Source Serif 4** are both Google-hosted under SIL OFL; safe for the demo.
- **The CSS grid shell is load-bearing.** Avoid `flex` for the top-level layout — grid gives the queue/canvas/agentrail their fixed-or-fluid widths without the percentage math `flex` would require.
- **Breadcrumb route map:** keep it in a tiny `breadcrumb.ts` alongside Header; later epics may add Approvals child routes etc.
- **Mode switcher state** lives in TanStack Router URL state (`?mode=investigate`) so deep-linking works; default if absent is `investigate`.
- **`UserSwitcher` reuse:** the existing `apps/cockpit-ui/src/components/cockpit/UserSwitcher.tsx` component is preserved in behavior; only its container styling changes. Its tests should still pass without modification.

### File List

**To create**
- `apps/cockpit-ui/src/components/cockpit/CockpitChrome/Header.tsx`
- `apps/cockpit-ui/src/components/cockpit/CockpitChrome/StatusBar.tsx`
- `apps/cockpit-ui/src/components/cockpit/CockpitChrome/ModeSwitcher.tsx`
- `apps/cockpit-ui/src/components/cockpit/CockpitChrome/breadcrumb.ts`
- `apps/cockpit-ui/src/components/cockpit/CockpitChrome/modes.ts`
- `apps/cockpit-ui/src/__tests__/tokens.test.tsx`
- `apps/cockpit-ui/src/__tests__/__visual__/12-1-shell-1366.png`
- `apps/cockpit-ui/src/__tests__/__visual__/12-1-shell-1920.png`

**To modify**
- `apps/cockpit-ui/tailwind.config.ts`
- `apps/cockpit-ui/src/index.css`
- `apps/cockpit-ui/index.html`
- `apps/cockpit-ui/src/routes/__root.tsx`
- `apps/cockpit-ui/src/components/cockpit/UserSwitcher.tsx` (visual weight reduction only)
- `Documentation/implementation-artifacts/sprint-status.yaml`
