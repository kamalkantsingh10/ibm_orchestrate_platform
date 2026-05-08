# Story 12.2: Queue rail and case canvas — tabular density and document-grade IA

Status: backlog

## Story

As an officer scanning my queue and reading a case,
I want the queue rail to communicate risk × SLA × continuity at a glance and the case canvas to read as a regulator-grade document with a sticky section nav,
So that I can pick the right case and find any section in it without scroll-hunting.

## Scope note

This story is the macro-IA refactor. It depends on Story 12.1's full-viewport shell and design tokens being in place — the queue rail and canvas grow into the new grid columns 12.1 created.

Two cohesive workstreams land together:

1. **Queue rail (`apps/cockpit-ui/src/components/cockpit/QueueRail/`).** Transform the current name+age+badge list into a tabular rail with filter chips at the top, risk-band markers using the 4-tier confidence primitive (shape + position, not just hue), an SLA chip, and a continuity glyph for prior-touch cases. The keyboard hint footer becomes always-visible (today it only shows on the empty state).

2. **Case canvas (`apps/cockpit-ui/src/routes/cases.$caseId.tsx`).** Restructure as a document: a compact title block (the H1 currently wraps to 3 lines and dominates above-the-fold — it must be at most 96px tall total), a horizontal "quick facts" strip, a sticky section nav rail anchored to the right edge, and clearly delimited sections (Documents · Identity · UBO · Screening · Risk · Decision) with consistent 64px inter-section rhythm. The document-upload zone collapses behind a `+ Add documents` button at the Documents section header.

The sections themselves keep their current internal markup in this story; the sub-rebuilds (Documents/Risk/UBO/Agent) are 12.3 and 12.4. This story is the chrome around them.

## Acceptance Criteria

### Queue rail

1. **AC1 — Filter chips at the top of the rail.** The rail header (above the case list) shows four filter chips: `All (n)` · `Mine` · `High risk` · `Due today`, each rendering a count from the `useCases()` data. Clicking toggles a single active filter (chip rendered with `ink-900` background, `paper` text). Filter logic is purely client-side — no API change. Default active chip: `All`. A second header row below the chips reads `Sorted: risk × SLA × age` in `text-caption` `ink-500`.

2. **AC2 — Risk-band marker (4-tier confidence primitive in shape + position).** Each row's first column is a 24×24 risk marker. The four bands map to four shapes:
   - `high` → filled square in `signal-rose`
   - `medium_high` → square half-filled diagonally in `signal-amber`
   - `medium_low` → square outline in `signal-amber`
   - `low` → small dot centered in `signal-sage`
   - `None` (unscored) → empty 24×24 placeholder with hairline `ink-200` border
   - Render via SVG primitives so shapes survive monochrome printing.

3. **AC3 — Row layout (4 columns).** Each row is a 4-column flex/grid: `[risk 24px] [name 1fr, single-line truncated] [sla chip auto] [status pill auto]`. Name uses `text-body` 500; SLA chip uses `text-caption` tabular figures. The "Ready" badge is replaced by a more honest status pill: `Decision ready` / `Intake running` / `Awaiting docs` / `Approved` driven by the existing case-state machine.

4. **AC4 — SLA chip.** Read `case.customer_metadata.extra.sla_due_at` (already populated by Story 4-1). Render relative time:
   - `> 24h remaining` → `2d` in `ink-500`
   - `1h..24h remaining` → `Nh` in `ink-700`
   - `< 1h remaining` → `Due` in `signal-amber`
   - `Past due` → `Overdue` in `signal-rose` weight 600
   - Missing SLA → no chip rendered.

5. **AC5 — Continuity glyph.** If `case.assigned_to_user_id === current_user.id`, prepend a 12×2px horizontal rule in `accent-claret` to the left of the risk marker. Otherwise no glyph.

6. **AC6 — Selected row treatment.** Selected row has a 2px left bar in `accent-claret` and `ink-50` background. Hover (non-selected) shows a `ink-50` background and `ink-100` left border. No drop shadows.

7. **AC7 — Keyboard hint pinned at the bottom.** The hint `j / k navigate · Enter open · x defer · d done · Esc clear` is a sticky 28px footer of the rail, present on **all** queue states (loading / empty / populated / case-open). Currently it appears only on the empty-state placeholder.

### Case canvas

8. **AC8 — Title block ≤ 96px tall.** New component `apps/cockpit-ui/src/components/cockpit/CaseTitleBlock/CaseTitleBlock.tsx`. Layout:
   - Row 1 (~40px): case name in `text-h1` (28/34 serif), single-line, ellipsis-truncated; right-aligned: SLA chip + `Decision ready` ribbon (when state matches) in `signal-amber`.
   - Row 2 (~28px): customer-type pill (Individual / Company / Trust derived from `customer_metadata.entity_type`) · vertical separator · case ID in monospace `text-caption` with click-to-copy icon · vertical separator · `Country: IN` chip · vertical separator · `Last update <relative>`.
   - Total max height 96px including padding.
   - The huge wrapping H1 currently in `cases.$caseId.tsx` is removed.

9. **AC9 — Quick-facts strip.** Beneath the title block, a 56px strip with up to 5 bullets separated by `ink-200` vertical rules: `Risk Score 32 / Low` · `UBO 6 nodes · 2 flagged` · `Documents 5 PDFs · 10 fields` · `Screening pending` · `Last agent run <relative>`. All values use `text-caption` 500 with tabular figures. This strip is data-driven — bullets are conditionally rendered based on which agents have completed.

10. **AC10 — Sticky section nav rail.** New component `apps/cockpit-ui/src/components/cockpit/SectionNav/SectionNav.tsx`. Positioned `position: sticky; top: 0;` inside the canvas, 200px wide, on the **right** edge of the canvas (so the document body remains the dominant left-aligned column). Lists six anchors: `Documents` · `Identity` · `UBO` · `Screening` · `Risk` · `Decision`. The currently in-view section is highlighted with a 2px left bar in `accent-claret` and `text-h3` weight; others use `text-body` weight 400. Clicking smooth-scrolls to the section anchor (`#section-documents` etc.). Implementation uses `IntersectionObserver` on the section headings.

11. **AC11 — Section rhythm.** Each section is wrapped in a `<section id="section-...">` block with: top hairline `ink-200` divider · 64px top padding · `text-h2` heading (serif 20/28) · standard 32px gap before content. Sections in this story: `Documents`, `Identity` (kept as the existing "Coming in Epic 6" stub but restyled — see AC13), `UBO`, `Screening` (kept as a stub), `Risk`, `Decision` (anchor for Story 12.5). The existing per-section internal markup is unchanged; only the section frame is new.

12. **AC12 — Upload zone collapses behind a button.** The `DocumentUploadZone` (currently a 200px dashed banner above the fold) is moved inside the Documents section header as a `+ Add documents` `<button>` on the right side of the section heading. Clicking expands the existing upload zone inline below the section heading; a chevron toggles it closed. Closed by default for cases with `state == decision_ready` and `documents.length > 0`. Open by default for cases with `documents.length === 0`. The "Process now" button moves into the expanded panel.

13. **AC13 — Identity stub restyle.** The `Coming in Epic 6` placeholder is replaced by a one-line skeleton row: a 12px `ink-300` placeholder rectangle + caption `Identity verification ships in Epic 6 (5-1 Entity Verification agent)`. No "Coming in Epic 6" giant heading.

14. **AC14 — Decision anchor placeholder.** A `<section id="section-decision">` is rendered at the bottom of the canvas with the heading "Decision" and a 1-line placeholder `Decision tools open in the bottom drawer when this case is decision-ready (Story 12.5)`. The actual drawer is built in 12.5; this story only reserves the section anchor so the SectionNav's `Decision` link works.

### General

15. **AC15 — `make lint` + `make test` clean.** Existing tests for `QueueRail.test.tsx` and `cases.$caseId.test.tsx` are updated to reflect the new DOM. Two new tests: `QueueRail.test.tsx::filter_chips_filter_visible_cases` and `CaseTitleBlock.test.tsx::title_block_height_does_not_exceed_96px` (the second uses `getBoundingClientRect` on the rendered element via Vitest + jsdom — if jsdom layout doesn't yield reliable heights, replace with a max-height CSS assertion in a snapshot).

16. **AC16 — Visual QA at 1366×768 and 1920×1080.** Manual screenshots committed under `__visual__/12-2-queue-1366.png`, `12-2-canvas-1366.png`, `12-2-canvas-1920.png`.

## Tasks / Subtasks

- [ ] **Task 1 — Queue rail filter chips + sort header** (AC: #1)
- [ ] **Task 2 — Risk marker SVG primitive** (AC: #2)
  - [ ] New component `apps/cockpit-ui/src/components/cockpit/QueueRail/RiskMarker.tsx`
  - [ ] Unit tests for the four band shapes
- [ ] **Task 3 — Row layout + SLA chip + continuity glyph + status pill** (AC: #3, #4, #5, #6)
- [ ] **Task 4 — Pinned keyboard hint footer** (AC: #7)
- [ ] **Task 5 — `CaseTitleBlock` component** (AC: #8)
- [ ] **Task 6 — Quick-facts strip** (AC: #9)
- [ ] **Task 7 — `SectionNav` component with IntersectionObserver** (AC: #10)
- [ ] **Task 8 — Section frame rewrite in `cases.$caseId.tsx`** (AC: #11, #13, #14)
- [ ] **Task 9 — Upload zone collapse** (AC: #12)
- [ ] **Task 10 — Tests + lint + visual QA** (AC: #15, #16)
  - [ ] Update existing `QueueRail.test.tsx` and `cases.$caseId.test.tsx`
  - [ ] Add new tests
  - [ ] Commit visual screenshots
  - [ ] Update `sprint-status.yaml` to `review`

## Dev Notes

- **The queue rail's existing keyboard handlers (Story 4-2) must continue to work** when the row layout changes — `j`/`k` index into the array of visible rows after filter is applied.
- **`SectionNav` on the right edge** keeps the document body left-aligned and naturally scannable. Avoid putting it on the left because that would compete with the Queue Rail.
- **Risk marker shapes are intentional** — the spec calls for the 4-tier confidence primitive to work in monochrome. Color is supplementary.
- **Quick-facts strip is data-driven**: when an agent hasn't run yet, that bullet is omitted (don't show `Risk Score —` placeholders). This keeps the strip honest.
- **Title block 96px max** is the load-bearing visual constraint of this story. The current display H1 wrapping to 3 lines is the single biggest aesthetic problem to fix.

### File List

**To create**
- `apps/cockpit-ui/src/components/cockpit/QueueRail/RiskMarker.tsx`
- `apps/cockpit-ui/src/components/cockpit/QueueRail/RiskMarker.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/QueueRail/FilterChips.tsx`
- `apps/cockpit-ui/src/components/cockpit/CaseTitleBlock/CaseTitleBlock.tsx`
- `apps/cockpit-ui/src/components/cockpit/CaseTitleBlock/CaseTitleBlock.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/QuickFactsStrip/QuickFactsStrip.tsx`
- `apps/cockpit-ui/src/components/cockpit/SectionNav/SectionNav.tsx`
- `apps/cockpit-ui/src/components/cockpit/SectionNav/SectionNav.test.tsx`
- `apps/cockpit-ui/src/__tests__/__visual__/12-2-*.png`

**To modify**
- `apps/cockpit-ui/src/components/cockpit/QueueRail/QueueRail.tsx`
- `apps/cockpit-ui/src/components/cockpit/QueueRail/QueueRail.test.tsx`
- `apps/cockpit-ui/src/routes/cases.$caseId.tsx`
- `apps/cockpit-ui/src/routes/cases.$caseId.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/DocumentUploadZone/DocumentUploadZone.tsx` (now rendered inside Documents section, collapsible)
- `Documentation/implementation-artifacts/sprint-status.yaml`
