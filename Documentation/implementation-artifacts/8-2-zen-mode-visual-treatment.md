# Story 8.2: Zen mode visual treatment

Status: backlog

## Story

As a KYC Analyst writing an EDD memo,
I want a calm, focused environment — dark canvas, evidence docked right, typography enlarged, minimal chrome,
So that I can think clearly while writing (FR25, UX-DR26).

## Scope note

This is the visual half of Zen mode. Story 8.1 wires the `⌘+4` keystroke and the mode store; this story renders the actual dark, focused, writing-first layout when `mode === 'zen'`.

**Dependencies:**
- Story 8.1 (mode store value `zen`)
- Story 7-1 (Tiptap DecisionZone editor — Zen is a different host for the same editor)
- Story 8.5 (EvidenceShelf — Zen docks it right; if 8.5 has not landed, render a placeholder dock that 8.5 fills)

**Coordination with Epic 12:** if Story 12.1's design tokens have landed, Zen extends them with dark variants (`paper-dark`, `ink-50-dark` etc.). If 12.1 has not landed, this story defines zen-specific tokens scoped to a `[data-mode="zen"]` selector.

## Acceptance Criteria

1. **AC1 — Dark canvas tokens.** When `mode === 'zen'`, the `<html>` (or top-level shell) gets `data-mode="zen"`. CSS rules under `[data-mode="zen"]` invert the base palette:
   - Background: `#1A1815` (warm near-black, not pure black — readability for long writing sessions)
   - Body text: `#F1ECE3` (warm off-white)
   - Hairline borders: `#2A2622`
   - Accent (claret) is preserved at the same hue but lifted in luminosity for contrast
   - The 4 signal hues (sage / amber / rose) are preserved with luminosity adjustments only

2. **AC2 — Tiptap editor occupies most of canvas.** The Tiptap editor (Story 7-1) renders centered with `max-width: 720px`, `min-height: 75vh`, padded for readability. Editor body type uses the serif face from the type ramp at +1 step (e.g., `text-h3` size becomes the body in Zen — 18/28 serif).

3. **AC3 — EvidenceShelf docks on the right.** A 320px-wide dock anchored to the right edge of the canvas hosts the EvidenceShelf component (Story 8.5). If 8.5 has not yet landed, the dock renders a placeholder list with caption `Evidence shelf — ships in Story 8.5` and a single dummy row.

4. **AC4 — Top chrome reduces.** In Zen mode:
   - The 6-mode segmented control (or Story 4-7 mode switcher) collapses to a single mode indicator: `Memo` label + a `Back to Investigation (⌘1)` ghost button
   - The breadcrumb and global search are hidden
   - The case name remains visible in `text-caption` to the left of the mode indicator
   - The user switcher remains in the right corner with reduced opacity (60%)

5. **AC5 — Bottom chrome hides.** The Story 12.1 status bar and the Story 12.5 decision drawer are both hidden in Zen mode (the writing surface should not compete with footer chrome). Pressing `Esc` from within the editor returns focus, not exits Zen.

6. **AC6 — Exit transition.** Pressing `⌘+1` (Investigation) or clicking `Back to Investigation` runs the inverse `expand` preset (250ms) and restores the dense Investigation layout with the canvas scrolled to the Decision section anchor.

7. **AC7 — Mode boundary preserved.** Investigation mode never inherits any of the Zen tokens. The `[data-mode="zen"]` selector is the only switch; removing the attribute fully reverts.

8. **AC8 — Tests.**
   - `ZenMode.test.tsx::applies_data_mode_zen_to_root_when_mode_is_zen`
   - `ZenMode.test.tsx::tiptap_editor_renders_at_720px_max_width`
   - `ZenMode.test.tsx::evidenceshelf_dock_renders_placeholder_when_8_5_not_implemented`
   - `ZenMode.test.tsx::status_bar_and_drawer_hidden_in_zen`
   - Visual screenshot: `__visual__/8-2-zen-default.png`, `8-2-zen-with-evidence.png`

9. **AC9 — `make lint` + `make test` clean.**

## Tasks / Subtasks

- [ ] **Task 1 — Dark token variants** (AC: #1)
  - [ ] Add `[data-mode="zen"]` rules to `apps/cockpit-ui/src/index.css`
  - [ ] If Epic 12.1 tokens are present: dark variants live in the same file; otherwise scoped to zen selector
- [ ] **Task 2 — `ZenMode` wrapper component** (AC: #1, #2, #3)
  - [ ] New `apps/cockpit-ui/src/components/cockpit/ZenMode/ZenMode.tsx`
  - [ ] Centers Tiptap editor at 720px
  - [ ] Renders right-edge evidence dock (with placeholder if 8.5 not landed)
- [ ] **Task 3 — Reduced top chrome** (AC: #4)
- [ ] **Task 4 — Hidden bottom chrome** (AC: #5)
  - [ ] Conditionally render StatusBar + DecisionDrawer based on `mode !== 'zen'`
- [ ] **Task 5 — Exit transition** (AC: #6)
- [ ] **Task 6 — Visual QA + tests** (AC: #8, #9)

## Dev Notes

- **Why warm near-black, not pure black.** Long writing sessions read better on `#1A1815` than `#000`. This is documented in UX-DR1.
- **The 720px editor max-width** matches Medium / Stripe docs convention. It's load-bearing for readability — wider lines lose the reader's eye.
- **`data-mode="zen"` over a CSS class** is intentional. The attribute selector composes naturally with future modes (`data-mode="audit"`) without class-name explosion.
- **EvidenceShelf placeholder** (AC3) means 8.2 is not blocked on 8.5 — they can ship in either order.

### File List

**To create**
- `apps/cockpit-ui/src/components/cockpit/ZenMode/ZenMode.tsx`
- `apps/cockpit-ui/src/components/cockpit/ZenMode/ZenMode.test.tsx`
- `apps/cockpit-ui/src/__tests__/__visual__/8-2-zen-default.png`
- `apps/cockpit-ui/src/__tests__/__visual__/8-2-zen-with-evidence.png`

**To modify**
- `apps/cockpit-ui/src/index.css` (add `[data-mode="zen"]` rule block)
- `apps/cockpit-ui/src/routes/cases.$caseId.tsx` (render `<ZenMode>` when `mode === 'zen'`)
- `apps/cockpit-ui/src/components/cockpit/CockpitChrome/Header.tsx` (reduced chrome in Zen)
- `apps/cockpit-ui/src/components/cockpit/CockpitChrome/StatusBar.tsx` (hide in Zen)
- `apps/cockpit-ui/src/components/cockpit/DecisionDrawer/DecisionDrawer.tsx` (hide in Zen)
- `Documentation/implementation-artifacts/sprint-status.yaml`
