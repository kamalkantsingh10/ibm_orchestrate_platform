# Story 12.5: Decision drawer and Approvals/Regulator route scaffolds

Status: backlog

## Story

As an officer who needs the commit moment to be visible and as a presenter switching to Team Lead or Regulator roles mid-demo,
I want a sticky bottom decision drawer that surfaces on `decision_ready` cases and designed empty states for the Approvals and Regulator Lens routes,
So that the canvas no longer terminates at the risk panel and the role-switch demo doesn't bottom out at "Story X-Y will populate this."

## Scope note

Final story of Epic 12. Depends on 12.1 (full-viewport shell, status bar) and 12.2 (case canvas with `#section-decision` anchor reserved).

Two cohesive workstreams:

1. **Decision drawer** (`apps/cockpit-ui/src/components/cockpit/DecisionDrawer/`). A sticky bottom drawer that surfaces whenever the open case is in a `decision_ready` state. Collapsed: 52px tall, anchored above the status bar, full-viewport-width. Expanded: 320px tall with a placeholder area for the Epic 7 writing surface. This story only ships the drawer chrome and collapse/expand behavior — Epic 7 wires the actual rationale-drafting UI into the expanded slot.

2. **Approvals + Regulator route scaffolds** (`apps/cockpit-ui/src/routes/approvals.tsx`, `regulator-lens.tsx`). Replace the literal placeholder text "Story 10-1 will populate this" / "Story 9-3 will populate this" with designed empty states that respect each role's visual register. Approvals carries a Team Lead amber accent; Regulator carries a slate/audit accent. Three placeholder summary cards each, with explicit "Wired in Story X-Y" footnotes so engineers still know which epic ships the real functionality.

This story ships no new functional behavior — it ships visual scaffolding for two role demos and one decision moment. The wired implementations come in Epic 7 (decision authoring), Epic 9 (regulator), and Epic 10 (approvals).

## Acceptance Criteria

### Decision drawer

1. **AC1 — Drawer is rendered only when `case.state === 'decision_ready'`.** On any other state (`intake_running`, `awaiting_docs`, `approved`, `declined`, `escalated`), the drawer is not rendered. The drawer subscribes to the case-state field already returned by `GET /v1/cases/:id`.

2. **AC2 — Collapsed layout (52px tall).** The drawer is anchored to the bottom of the viewport, immediately above the StatusBar (28px) from Story 12.1, full-viewport-width. Collapsed contents:
   - Left: state ribbon `Decision ready` in `signal-amber` `text-caption` 600 uppercase
   - Center-left: `Decision · <case name>` in `text-body` 500 (case name truncated to fit)
   - Center-right: estimated time-to-commit text `~3 minutes to draft` in `text-caption` `ink-500`
   - Right: secondary CTA `Defer` (ghost button) · primary CTA `Draft rationale` (filled `accent-claret` button)
   - Far right: chevron-up icon to expand the drawer.

3. **AC3 — Expanded layout (320px tall).** Clicking the chevron-up or pressing `⌘↓` expands the drawer to 320px. The expanded area shows a designed empty state for Epic 7:
   - Top section header: `Rationale draft` in `text-h3`
   - Body: a 200px-tall placeholder area with `ink-200` 1px dashed border, centered text `Rationale drafting surface ships in Epic 7 (Story 7.1: DecisionZone with Tiptap editor)` in `text-body` `ink-500` with a link to the story file
   - Bottom action bar (preserved from collapsed): `Defer` + `Draft rationale` buttons, where `Draft rationale` is disabled with tooltip `Wired in Epic 7`.
   - Pressing `Esc` collapses the drawer; pressing `⌘↓` again also collapses.

4. **AC4 — Visual separation as a plane.** The drawer has a top hairline `ink-200` divider plus a soft `ink-900` 4% box-shadow (12px blur, no offset) above it so it reads as a separate plane floating above the canvas.

5. **AC5 — Drawer does not overlap the canvas content.** When the drawer is rendered, the canvas's bottom padding increases by the drawer's collapsed or expanded height plus the StatusBar height — so scrolling to the bottom of the canvas does not hide content under the drawer. Use `padding-bottom: var(--drawer-height)` on the canvas container.

6. **AC6 — Drawer state is URL-persisted.** Expanded/collapsed state lives in TanStack Router URL state (`?drawer=expanded`) so deep-linking works and reload preserves the user's choice. Default: collapsed.

7. **AC7 — `Decision` section anchor in the canvas updates.** The `<section id="section-decision">` placeholder reserved in Story 12.2 is updated: when the drawer is rendered, the section heading reads `Decision` and below it shows a one-line caption `See the bottom drawer for decision tools.` — making it explicit where the action is. When the drawer is not rendered (case not `decision_ready`), the section shows `This case is not yet ready for decision. Pending: <reason>` where reason is derived from state (`Intake running` / `Awaiting documents`).

### Approvals route scaffold

8. **AC8 — `routes/approvals.tsx` renders a designed empty state.** The literal text `Story 10-1 will populate this.` is removed. Replaced by:
   - Page heading `Approvals` in `text-h1` serif (left-aligned, not centered)
   - Subline `Cases your analysts commit for approval will appear here.` in `text-body` `ink-700`
   - A `signal-amber` 1px underline beneath the user switcher in the header (Story 12.1's Header component reads role from current user and applies the underline color: amber for Team Lead, slate for Regulator, none for Analyst)
   - Three top-line summary cards in a horizontal row:
     - `Pending approvals` · large numeric `0` in `text-display` · footnote `Wired in Story 10-1`
     - `Approved today` · `0` · footnote `Wired in Story 10-1`
     - `Escalated` · `0` · footnote `Wired in Story 10-1`
   - Below the cards, a single empty-state panel: title `No approvals waiting`, body copy `Cases your analysts commit for approval will appear here.`, disabled CTA `Configure approval rules` with tooltip `Wired in Story 10-1`.

9. **AC9 — Approvals route only accessible to Team Lead role.** The existing role gate (Story 1-4 user switcher routing) is preserved — Analyst users cannot navigate to `/approvals`. This story does not change that behavior.

### Regulator Lens route scaffold

10. **AC10 — `routes/regulator-lens.tsx` renders a designed empty state.** The literal text `Story 9-3 will populate this.` is removed. Replaced by:
    - Page heading `Regulator Lens` in `text-h1` serif (left-aligned)
    - Subline `Read-only audit view of cases, ledger entries, and exportable bundles.` in `text-body` `ink-700`
    - An `ink-700` 1px underline beneath the user switcher in the header (Regulator role accent)
    - Page background shifts to `ink-50` (slightly darker than the default `paper` to suggest audit framing)
    - A top strip in `text-caption` reading `Audit trail · 1,247 ledger entries · last sealed <static placeholder timestamp> · hash chain valid` (numbers can be hardcoded for the demo; this story does not wire to live ledger state)
    - Three placeholder columns below the strip: `Cases under review` · `Trail timeline` · `Export bundle`, each as a card with a `caption` footnote `Wired in Story 9-3` and a single placeholder body line.

11. **AC11 — Regulator Lens route only accessible to Regulator role.** Existing role gate preserved — Analyst and Team Lead users cannot navigate to `/regulator-lens`.

### General

12. **AC12 — `make lint` + `make test` clean.** New tests:
    - `DecisionDrawer.test.tsx::renders_only_when_state_is_decision_ready`
    - `DecisionDrawer.test.tsx::expand_collapse_via_keyboard_and_chevron`
    - `DecisionDrawer.test.tsx::canvas_padding_increases_to_avoid_overlap`
    - `approvals.test.tsx::renders_three_summary_cards_with_zeros_and_footnotes`
    - `regulator-lens.test.tsx::renders_audit_strip_and_three_placeholder_columns`

13. **AC13 — Visual QA at 1440×900.** Manual screenshots: `__visual__/12-5-drawer-collapsed.png`, `12-5-drawer-expanded.png`, `12-5-approvals.png`, `12-5-regulator-lens.png`.

## Tasks / Subtasks

- [ ] **Task 1 — `DecisionDrawer` chrome (collapsed)** (AC: #1, #2, #4, #5)
- [ ] **Task 2 — `DecisionDrawer` expanded state with Epic 7 placeholder** (AC: #3)
- [ ] **Task 3 — URL-persisted state + keyboard wiring** (AC: #6)
- [ ] **Task 4 — Update Decision section anchor in `cases.$caseId.tsx`** (AC: #7)
- [ ] **Task 5 — Approvals route scaffold** (AC: #8)
- [ ] **Task 6 — Header role-accent underline (Team Lead amber, Regulator slate)** (AC: #8, #10)
  - [ ] Adds a small `roleAccent.ts` helper alongside Story 12.1's Header component
- [ ] **Task 7 — Regulator Lens route scaffold** (AC: #10)
- [ ] **Task 8 — Tests + lint + visual QA** (AC: #12, #13)
  - [ ] Add new tests
  - [ ] Commit visual screenshots
  - [ ] Update `sprint-status.yaml` to `review`

## Dev Notes

- **The drawer is purely visual scaffolding.** Epic 7 (Story 7-1) drops the wired Tiptap rationale-drafting surface into the expanded area; Story 7-7 wires the POST /decision endpoint to the `Draft rationale` button. Until then, the button is disabled and the body shows the placeholder.
- **Why URL state for drawer expansion:** if a presenter shares a deep link to a case in expanded-drawer mode for a demo, the receiver sees the same state. Same pattern as Story 12.4's rail collapse and UBO expand.
- **Approvals + Regulator Lens are role-gated routes.** Story 1-4 already enforces this; we don't re-implement that gating, only the visual content of each route.
- **Role-accent underline in the header.** A small `roleAccent.ts` map (`{ analyst: null, team_lead: 'signal-amber', regulator: 'ink-700' }`) determines the underline color. Header reads current user role and applies it.
- **`Audit trail · N entries · last sealed <ts>` strip** uses static placeholder numbers because Story 9-3 ships the live ledger-summary endpoint. Do not invent a fake API for this story.
- **Canvas bottom padding (AC5)** is critical: without it, the bottom 52–320px of any case canvas would be hidden under the drawer. Use a CSS variable updated when the drawer state changes.

### File List

**To create**
- `apps/cockpit-ui/src/components/cockpit/DecisionDrawer/DecisionDrawer.tsx`
- `apps/cockpit-ui/src/components/cockpit/DecisionDrawer/DecisionDrawer.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/CockpitChrome/roleAccent.ts`
- `apps/cockpit-ui/src/__tests__/__visual__/12-5-*.png`

**To modify**
- `apps/cockpit-ui/src/routes/cases.$caseId.tsx` (Decision section update; render drawer when state matches; wire canvas padding-bottom)
- `apps/cockpit-ui/src/routes/cases.$caseId.test.tsx`
- `apps/cockpit-ui/src/routes/approvals.tsx` (replace placeholder text)
- `apps/cockpit-ui/src/routes/approvals.test.tsx` (or new if absent)
- `apps/cockpit-ui/src/routes/regulator-lens.tsx` (replace placeholder text)
- `apps/cockpit-ui/src/routes/regulator-lens.test.tsx` (or new if absent)
- `apps/cockpit-ui/src/components/cockpit/CockpitChrome/Header.tsx` (apply role-accent underline)
- `Documentation/implementation-artifacts/sprint-status.yaml`
