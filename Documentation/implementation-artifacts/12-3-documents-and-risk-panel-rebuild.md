# Story 12.3: Documents panel and Risk panel rebuild

Status: backlog

## Story

As an officer reading evidence on a case,
I want the Documents panel to be a single sortable table of fields and the Risk panel to lead with one large number plus a horizontal stacked bar and one decomposition table,
So that I can sort weakest evidence to the top and read the risk verdict in under a second.

## Scope note

Depends on 12.1 (tokens) and 12.2 (canvas section frames). This story rebuilds the internal markup of two of the canvas's most read panels:

1. **Documents panel** (`apps/cockpit-ui/src/components/cockpit/DocumentsPanel/`). Currently renders as one heading per PDF with a stacked list of fields underneath each, with two icons per row (a small doc icon plus the confidence pill). It will become a single sortable table covering all extracted fields across all documents, with columns Document · Field · Value · Confidence · Source. Default sort is `Confidence ascending` so weakest evidence surfaces first.

2. **Risk panel** (`apps/cockpit-ui/src/components/cockpit/RiskPanel/` + `RiskScoreBar/`). Currently renders a donut + a list of components + a duplicated decomposition list (same data shown twice). It will become: one large numeric (`text-display`) + band label, one horizontal stacked bar, one plain-language summary, one decomposition table with right-aligned tabular figures. Donut is removed.

Both panels keep their existing data sources and APIs untouched. The reasoning-trace slide-out (Epic 6) integration on each Confidence cell stays wired.

## Acceptance Criteria

### Documents panel

1. **AC1 — Single tabular layout.** Replace the current heading-per-document markup with a single `<table>` rendering all fields across all documents. Columns: `Document` · `Field` · `Value` · `Confidence` · `Source`. The table fills the section's full width. Header row uses `text-micro` 600 uppercase tracking-wide in `ink-500`.

2. **AC2 — Document grouping via blank cells.** Within the table body, rows are sorted first by the active sort column, but the `Document` cell is blank for the 2nd through Nth row of any consecutive same-document group — the filename is shown only on the first row of the group. This creates visual grouping without repeating the filename. When sort is applied, regroup such that rows from the same document remain consecutive within the sort.

3. **AC3 — Sortable header.** Click a header cell to toggle sort: `Confidence` (numeric, default ascending), `Document` (alphabetic), `Field` (alphabetic). The active sort header shows a 8px arrow glyph in `ink-700`. Default sort on initial render: `Confidence ascending` (weakest first).

4. **AC4 — Confidence cell.** The Confidence column renders the existing `ConfidencePill` component (Story 3-7) with no double-icon stacking — the small doc icon currently next to the pill is removed (its function moves to the Source column). Clicking the pill opens the existing reasoning-trace slide-out (Story 6-6) for that field — preserving Epic 6 functionality.

5. **AC5 — Source column.** A single icon-only affordance per row: a 16px document glyph in `ink-500` that, on hover, shows a tooltip with `Document Intelligence · fixture_doc_ai` (or whichever provenance the field carries). On click, opens the same reasoning trace as the Confidence pill (functionally equivalent — two click targets, one outcome).

6. **AC6 — Section header text.** The Documents section heading reads `Documents · <n> fields extracted across <m> PDFs` followed by a `text-caption` subline `Sorted by <active sort column>`. The "Document Intelligence" pill currently next to the heading is removed (its content moves into the per-row Source column tooltip).

7. **AC7 — Row affordance.** Hover any row → `ink-50` background; the row is keyboard-focusable; pressing `Enter` opens the reasoning-trace slide-out for that field.

8. **AC8 — Empty state.** If `documents.length === 0`, show a single empty-state row in the table body: `No documents yet — drop PDFs above to begin extraction.` (referencing the now-collapsible upload zone from 12.2). No table chrome shown.

### Risk panel

9. **AC9 — Banker hero.** Replace the donut chart with a hero block at the top of the Risk section:
   - Large numeric in `text-display` (56px serif), `ink-900` color → e.g., `32`
   - Right-aligned band label in `text-h2` weight 500 → `LOW`, color-keyed: `signal-sage` for low, `signal-amber` for medium / medium_high, `signal-rose` for high
   - Underneath, a one-sentence summary in `text-body` `ink-700` describing the verdict — derived from the existing decomposition data, e.g. `Low risk — driven by IN customer country, offset by 2 foreign-corporate UBO holders and 1 officer correction.` The summary is built by a small pure helper `buildRiskSummary(decomposition)` in `apps/cockpit-ui/src/components/cockpit/RiskPanel/buildRiskSummary.ts`.

10. **AC10 — Horizontal stacked bar.** Beneath the hero, a single 12px-tall horizontal stacked bar showing each component's contribution proportional to the total. Colors: `ink-300` / `ink-500` / `ink-700` rotation for components (so the bar reads in monochrome), with the dominant component highlighted in `accent-claret`. Hovering a segment shows a tooltip: `Ownership Clarity — 16.8 of 32`.

11. **AC11 — Decomposition table.** A single table with columns `Component` · `Weight` · `Value` · `Contribution` · `Note`. Numeric columns right-aligned with `.tabular`. Five rows: Country, Entity Type, Ownership Clarity, Screening, Adverse Media. Note column carries the existing per-component sentence (e.g. `2 nominee-suspected edge(s); 1 officer-corrected edge(s)`).

12. **AC12 — Donut + duplicated lists removed.** The existing `RiskScoreBar` donut SVG is deleted. The two duplicated lists (`Risk components` and `Risk decomposition`) currently rendered below the donut are merged into the single decomposition table.

13. **AC13 — Recalculate button placement.** If a `Recalculate` button currently floats below the panel, move it to the panel header (right-aligned). For now, this is a no-op that stays — Story 5-8 wires auto-recalc on UBO correction; this story only relocates the existing button.

14. **AC14 — Reasoning-trace integration preserved.** Clicking a row in the decomposition table opens the existing reasoning-trace slide-out for that component (preserves Epic 6 functionality). Hover the row → `ink-50` background.

### General

15. **AC15 — `make lint` + `make test` clean.** Existing tests for `DocumentsPanel.test.tsx` and `RiskPanel.test.tsx` are updated to reflect the new DOM. New tests:
    - `DocumentsPanel.test.tsx::sorts_by_confidence_ascending_by_default`
    - `DocumentsPanel.test.tsx::filename_blanks_on_grouped_rows`
    - `RiskPanel.test.tsx::renders_hero_band_label_color_keyed_to_band`
    - `buildRiskSummary.test.ts::generates_one_sentence_from_top_two_drivers`

16. **AC16 — Visual QA.** Manual screenshots at 1440×900 of both panels committed under `__visual__/12-3-documents.png`, `12-3-risk.png`.

## Tasks / Subtasks

- [ ] **Task 1 — Documents panel table rewrite** (AC: #1, #2, #3, #6, #8)
- [ ] **Task 2 — Confidence + Source columns** (AC: #4, #5, #7)
- [ ] **Task 3 — Risk hero block** (AC: #9)
- [ ] **Task 4 — `buildRiskSummary` helper + tests** (AC: #9, #15)
- [ ] **Task 5 — Horizontal stacked bar** (AC: #10)
- [ ] **Task 6 — Decomposition table** (AC: #11, #14)
- [ ] **Task 7 — Remove donut + dedupe lists** (AC: #12)
- [ ] **Task 8 — Recalculate button placement** (AC: #13)
- [ ] **Task 9 — Tests + lint + visual QA** (AC: #15, #16)
  - [ ] Update existing `DocumentsPanel.test.tsx` and `RiskPanel.test.tsx`
  - [ ] Add new tests including `buildRiskSummary.test.ts`
  - [ ] Commit visual screenshots
  - [ ] Update `sprint-status.yaml` to `review`

## Dev Notes

- **The reasoning-trace slide-out integration** (Story 6-6) is shipped via `apps/cockpit-ui/src/components/cockpit/ReasoningTraceSlideOut/`. Both panels currently call into it; this story preserves both call sites.
- **The donut deletion is intentional.** Donuts read as consumer-app charts; tier-1-bank workstations use stacked horizontal bars + tables for risk decomposition. The information density is the same; the visual register is different.
- **`buildRiskSummary` heuristic.** Pick the top-2 contributing components by `Contribution`, plus any component flagged by an officer correction (already present in the decomposition note). Compose a single sentence with the band as the subject.
- **Tabular figures everywhere in the table.** Apply `.tabular` to all numeric `<td>`s. The 8px right padding on numeric cells gives the right-aligned tabular figures breathing room.
- **No new data fetches.** Both panels already receive their data via the existing case-detail query. This is purely a presentation rewrite.

### File List

**To create**
- `apps/cockpit-ui/src/components/cockpit/RiskPanel/buildRiskSummary.ts`
- `apps/cockpit-ui/src/components/cockpit/RiskPanel/buildRiskSummary.test.ts`
- `apps/cockpit-ui/src/components/cockpit/RiskPanel/StackedRiskBar.tsx`
- `apps/cockpit-ui/src/__tests__/__visual__/12-3-documents.png`
- `apps/cockpit-ui/src/__tests__/__visual__/12-3-risk.png`

**To modify**
- `apps/cockpit-ui/src/components/cockpit/DocumentsPanel/DocumentsPanel.tsx`
- `apps/cockpit-ui/src/components/cockpit/DocumentsPanel/DocumentsPanel.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/RiskPanel/RiskPanel.tsx`
- `apps/cockpit-ui/src/components/cockpit/RiskPanel/RiskPanel.test.tsx`

**To delete**
- `apps/cockpit-ui/src/components/cockpit/RiskScoreBar/` (donut SVG component — no longer used)

**To update**
- `Documentation/implementation-artifacts/sprint-status.yaml`
