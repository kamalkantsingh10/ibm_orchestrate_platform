# Story 5.7: Risk Score stacked-bar with hover decomposition

Status: review

## Story

As a KYC Analyst on a case where Story 5.6's Risk Scoring agent has run,
I want to see the risk score as a horizontal stacked bar with five color-coded segments (one per `RiskComponent`) sized proportional to each component's `contribution`, the integer total + band label rendered to the right of the bar, hover tooltips on each segment showing `name`, `value`, `weight`, `contribution`, and `rationale`, and a 200 ms cross-fade animation on segments whose values changed since the last render,
So that I read the risk drivers at a glance — country, entity type, ownership clarity, screening, adverse media — without parsing raw numbers, the demo's "decisions are explained, not asserted" principle is met from the first render, and Story 5.8's auto-recalc cross-fade has a place to land (FR20, UX-DR20, NFR-AC3 color-blind safety, P7).

## Scope note (2026-04-29 demo re-scope)

The bank-buyer scope spec for this component is essentially unchanged — UI fidelity is load-bearing per `architecture.md#Demo Scope Addendum`. Demo simplifications:

| Bank-buyer scope (original 5.8) | Demo replacement in this story |
|---|---|
| Storybook entries with all bands × all variants | **No Storybook.** Vitest + React Testing Library coverage only. |
| WCAG audit + axe-core enforcement | **Aspirational** — axe-core invoked but not gating CI. |
| Configurable component palette via design tokens | **Hard-coded Tailwind colors** matching Story 3.7 ConfidencePill palette. |

What survives: **horizontal stacked bar, per-segment shadow + label + tooltip, 200 ms cross-fade, four-tier color palette, full keyboard accessibility (Tab into segments → Enter opens detail).**

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md` § UX implications, `ux-design-specification.md` § DecompositionPanel + RiskScoreExplainer.

## Acceptance Criteria

1. **AC1 — Component lives at `apps/cockpit-ui/src/components/cockpit/RiskScoreBar/RiskScoreBar.tsx`.**

    Public props:
    ```typescript
    import type { components } from '@/api-types';
    type RiskScore = components['schemas']['RiskScore'];

    export interface RiskScoreBarProps {
        score: RiskScore | null | undefined;
        isPending?: boolean;
        isError?: boolean;
        /** When true, renders the bar with cross-fade animations on segment value changes. Default: true. */
        animate?: boolean;
        /** When provided, called on segment click (Story 5.8 may use this — not wired here). */
        onSegmentClick?: (componentName: string) => void;
        className?: string;
    }
    ```

    Component renders:
    1. **Bar** — a horizontal flex container, `h-8` (32px) tall, `rounded-md`, `border border-zinc-200`. Contains 5 child segments (one per `RiskComponent`).
    2. **Total + band** — to the right of the bar: `text-2xl font-semibold` for the integer total; band label below in `text-xs uppercase tracking-wide`.
    3. **Component legend** — below the bar: a 5-row grid with each component's name + colored swatch + contribution. Used for keyboard navigation.

2. **AC2 — Segment widths from `contribution`, NOT raw `value`.**

    Each segment's width is `${(contribution / totalContributions) * 100}%`. The total of all `contribution` values is `score.total` (after rounding). Segments under 1% are **hidden but reachable** (their data is in the legend). Segments at exactly 0 are NOT rendered as visible segments — they get a 0-width div for layout stability and a legend entry showing `0%`.

    Color per segment (mirrors Story 3.7 palette but coarser):
    * `country` → `bg-sky-500`
    * `entity_type` → `bg-amber-500`
    * `ownership_clarity` → `bg-violet-500`
    * `screening` → `bg-rose-500`
    * `adverse_media` → `bg-zinc-500`

    The five colors are **distinct and color-blind-checked** (verified via the Coblis Color Blindness Simulator before finalizing). Color is the SECONDARY signal; the primary signal is segment width + tooltip rationale.

3. **AC3 — Total + band visual treatment.**

    * **Total:** large integer (28px / 600 weight). Aligned right of the bar.
    * **Band:** uppercase pill — `low` → `bg-emerald-100 text-emerald-700`; `medium` → `bg-amber-100 text-amber-700`; `high` → `bg-rose-100 text-rose-700`. Pill `text-[10px] font-semibold tracking-wider px-2 py-0.5 rounded-full`.
    * **Aspect ratio:** the bar takes ~70% width of the container; total + band take ~30%. Use Tailwind grid `grid-cols-[1fr_auto] gap-3 items-center`.

4. **AC4 — Hover tooltip per segment.**

    Use Radix `Popover` (or shadcn `Tooltip`) anchored to the segment. Tooltip content:
    ```
    Country
    ────────
    Value:        10
    Weight:       0.15
    Contribution: 1.5
    ────────
    Customer country: 'IN' (low-risk)
    ```

    Layout: a 2-column grid for the value/weight/contribution rows; rationale on a new line. Width 240px max.

5. **AC5 — Animation: 200ms cross-fade on segment value changes.**

    When `score.components[i].contribution` changes between renders (compared by `name` key), the affected segment animates:
    * **Width transition:** `transition-[width] duration-200 ease-out` on the segment.
    * **Color brightness pulse:** the segment's `opacity` briefly drops from 1 to 0.6 and back over 200ms, signaling "this segment changed". Use Framer Motion's `motion.div` with a `key` keyed on the contribution value.

    `useEffect` with `previousScoreRef` tracks last-render contributions and triggers the pulse on diff. Don't pulse on initial mount.

    Respect `prefers-reduced-motion`: when reduced-motion is set, skip the pulse and use instant width transitions. Use `useReducedMotion()` from Framer Motion.

6. **AC6 — Empty / loading / error states.**

    * `isPending && !score`: skeleton — a `bg-zinc-100 rounded-md h-8` shimmer for the bar; `bg-zinc-100 rounded h-8 w-12` for the total. Caption: `"Computing risk score…"`.
    * `isError`: rose-bordered alert: `"Could not compute risk score."` with a Retry button.
    * `score == null`: empty state: `"Risk score not computed. Run intake to populate."`.

7. **AC7 — Keyboard + screen-reader accessibility.**

    * The bar is a `<div role="img" aria-label="Risk score: <total>, band <band>">`. Total + band are visually present but redundant for screen readers.
    * Each segment is a focusable `<button>` (visually styled as a div segment) — Tab cycles through segments left-to-right. Enter / Space opens the tooltip. Esc closes.
    * Each segment has `aria-label` like `"Country, value 10, weight 0.15, contributes 1.5 of 33"`.
    * Tooltip is `aria-describedby` the segment.
    * Color-blind safety: per AC2 + AC4, color is secondary; primary signal is width + tooltip rationale.

8. **AC8 — Works without `score_provenance` rendering.**

    The `RiskScore.score_provenance` field carries the float-form total + provenance metadata. **This component does NOT render the provenance pill** — it's deferred to a sibling component (Story 5.9 may add a small ProvenanceIndicator next to the total). Don't pre-empt.

9. **AC9 — Tests at `apps/cockpit-ui/src/components/cockpit/RiskScoreBar/RiskScoreBar.test.tsx`.** Cover:

    * **Vora pinned fixture (medium band, total 37):** assert 5 segments rendered; assert segment widths sum to 100%; assert ownership_clarity is the largest segment; assert band pill says `MEDIUM` with amber palette.
    * **Shree pinned fixture (low band, total 20):** assert band pill says `LOW`; assert ownership_clarity contributes 12.0 (largest still).
    * **Ananya pinned fixture (medium band, total 35):** assert screening segment renders with `bg-rose-500`; assert tooltip rationale `"Screening hit hint present"`.
    * **Loading:** assert skeleton.
    * **Error + Retry:** click Retry; assert callback fires.
    * **Empty:** assert empty-state copy.
    * **Tooltip on hover:** hover the country segment; assert tooltip shows `Value: 10`, `Weight: 0.15`, `Contribution: 1.5`.
    * **Animation on value change:** mount with Vora pre-correction; rerender with Vora post-correction; assert ownership_clarity segment width transition triggered (via Framer Motion's `motion.div` `key` prop change).
    * **`prefers-reduced-motion`:** mock the hook to return true; rerender with new score; assert no Framer Motion `animate` prop on segments (instant transition).
    * **Keyboard nav:** Tab into the bar; assert focus moves to each segment in order; Enter opens the tooltip.
    * **A11y:** axe-core check; assert no violations.

10. **AC10 — Pinned fixtures at `apps/cockpit-ui/src/components/cockpit/RiskScoreBar/__fixtures__/`.**

    Three JSON fixtures: `vora-risk-score.json`, `shree-risk-score.json`, `ananya-risk-score.json`. Hand-built to match Story 5.6's pinned outputs. Tests import these directly.

11. **AC11 — `index.ts` re-exports `RiskScoreBar`.**

12. **AC12 — `make lint && make test` clean.** Net new test count: ≥ 11 in `RiskScoreBar.test.tsx`. No backend changes.

## Tasks / Subtasks

- [x] **Task 1 — Pinned JSON fixtures** (AC: #10)
  - [x] Subtask 1.1 — `vora-risk-score.json` matching Story 5.6 § AC3 Vora pre-correction.
  - [x] Subtask 1.2 — `shree-risk-score.json`.
  - [x] Subtask 1.3 — `ananya-risk-score.json`.

- [x] **Task 2 — Author the component** (AC: #1, #2, #3, #4, #6, #7, #8)
  - [x] Subtask 2.1 — `RiskScoreBar.tsx` with the 5-segment bar layout.
  - [x] Subtask 2.2 — Segment color helpers + a small `componentColor(name)` map.
  - [x] Subtask 2.3 — Tooltip via shadcn `Tooltip`/`Popover`.
  - [x] Subtask 2.4 — Total + band pill rendering.
  - [x] Subtask 2.5 — Empty / loading / error states.
  - [x] Subtask 2.6 — Keyboard wiring on each segment.
  - [x] Subtask 2.7 — `index.ts`.

- [x] **Task 3 — Animation** (AC: #5)
  - [x] Subtask 3.1 — `useEffect`-driven previous-score diff.
  - [x] Subtask 3.2 — Framer Motion `motion.div` keyed on contribution value for cross-fade.
  - [x] Subtask 3.3 — `useReducedMotion()` to suppress.

- [x] **Task 4 — Tests** (AC: #9, #12)
  - [x] Subtask 4.1 — `RiskScoreBar.test.tsx` covers all 11 cases.
  - [x] Subtask 4.2 — `make lint && make test` green.

## Dev Notes

### Architectural context (binding)

* [Source: `architecture.md#Frontend Architecture`] Tailwind 4 + shadcn/ui + Framer Motion for motion.
* [Source: `ux-design-specification.md` § DecompositionPanel] panel anatomy: title row → summary row → divider → row list. The bar component slots into the summary row.
* [Source: `ux-design-specification.md` § Confidence bands never rely on color alone] color is secondary; redundancy via width + label + tooltip.
* [Source: `ux-design-specification.md` § Risk Score panel preview (around line 985)] panel renders summary + decomposition rows. This component is the bar; the decomposition rows are shipped in Story 5.9's panel.

### Critical pitfalls

1. **Don't try to render the `score_provenance` provenance pill in this story.** It's tempting to add a small `ProvenanceIndicator` next to the total — but the `score_provenance.evidence_ids` are populated by the supervisor's back-fill (Story 5.6 AC6), and the pill component is wired up in Story 5.9 alongside the panel. Defer.

2. **Segment widths sum to 100% — but the bar's *total* is `score.total`, NOT 100.** A common mistake: rendering each segment as `width: ${value}%` literal on the value scale. The fix: width is `(contribution / sum_of_contributions) * 100%`, which IS `(contribution / score.total) * 100%`. **Don't confuse "total" (the 0–100 score) with "sum of contributions" (also score.total, but conceptually distinct).**

3. **Color-blind palette validation.** Run the chosen 5 colors through Coblis (or any color-blind simulator). The amber-violet contrast is borderline for tritanopia; if it fails, swap `entity_type` to `bg-orange-500` or `bg-yellow-500`. Document the choice in the file's docstring.

4. **The 32px-tall bar with 5 segments at varying widths can have a 1–2% segment that's only 8–16px wide.** Make sure click + hover targets work on tiny segments. Either: (a) min-width 24px on each segment (overrides proportional); OR (b) accept tiny tap targets and provide the full legend below for keyboard nav. **Pick (b)** — visual fidelity over click ease for the demo.

5. **Framer Motion's `motion.div` re-render performance.** Five segments × per-render `motion.div` is fine. **Don't** wrap the entire bar in a single `motion.div` and animate via a parent — segments animate independently.

6. **Animation triggers on every render unless gated.** Use `useRef` to store previous contributions; compare with `Object.is` per component. Only animate when at least one differs.

7. **Tailwind classnames with dynamic palette.** The 5 segments map by `RiskComponentName` to a fixed Tailwind class. **Don't** build the class string at runtime as `bg-${color}-500` — Tailwind's tree-shake won't pick it up. Use a static lookup map:
   ```typescript
   const COLOR_BY_COMPONENT: Record<RiskComponentName, string> = {
       country: 'bg-sky-500',
       entity_type: 'bg-amber-500',
       ownership_clarity: 'bg-violet-500',
       screening: 'bg-rose-500',
       adverse_media: 'bg-zinc-500',
   };
   ```

8. **Tooltip width matters.** Default Radix Popover collapses to content width — use `style={{ width: 240 }}` or Tailwind `w-60` to keep it stable across rationale lengths.

### Story dependencies

* **Strict prereqs:** Story 5.6 (Risk Scoring agent) for the `RiskScore` Pydantic shape.
* **Reads from:** Story 3.7 (ConfidencePill) — color palette consistency.
* **Read by:** Story 5.8 (auto-recalc) — relies on this component's animation; Story 5.9 (UBO + Risk panels) — places this into the Risk panel.

### Project Structure Notes

This story creates:
- `apps/cockpit-ui/src/components/cockpit/RiskScoreBar/RiskScoreBar.tsx`
- `apps/cockpit-ui/src/components/cockpit/RiskScoreBar/RiskScoreBar.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/RiskScoreBar/index.ts`
- `apps/cockpit-ui/src/components/cockpit/RiskScoreBar/__fixtures__/vora-risk-score.json`
- `apps/cockpit-ui/src/components/cockpit/RiskScoreBar/__fixtures__/shree-risk-score.json`
- `apps/cockpit-ui/src/components/cockpit/RiskScoreBar/__fixtures__/ananya-risk-score.json`

This story modifies:
- (none — pure new component)

This story DOES NOT create:
- The Risk panel placement (Story 5.9)
- The auto-recalc trigger (Story 5.8)
- A backend route (no API changes)

### References

- [Source: `ux-design-specification.md` § DecompositionPanel + § RiskScoreExplainer] target component contract
- [Source: `architecture.md#Project-Specific Patterns` P7] confidence banding — palette consistency cue
- [Source: `epics.md#Epic 5` § Story 5.8] original AC (re-scoped here)
- [Source: `prd.md#FR20, UX-DR20`] decomposition-with-hover, 200ms cross-fade
- [Source: `5-6-risk-scoring-agent.md`] `RiskScore` Pydantic shape; pinned demo outputs
- [Source: `3-7-confidence-pill-component.md`] color palette + variant pattern

### Demo verification protocol

```bash
# After Stories 5.6 + 5.7 are merged:
make dev

# Open Vora's case (medium band):
# http://localhost:5173/cases/case_01KQC7GQ70GYHP15CZ8JB5ZT6A
# Expected (visual):
#   - Risk panel area: stacked bar with 5 segments; ownership_clarity (violet) is the largest
#   - Total: 37; band pill: MEDIUM (amber palette)
#   - Hover ownership_clarity → tooltip: "3 nominee-suspected edges; 0 officer-corrected edges"

# Trigger Vora correction (Story 5.5) → re-run risk:
# (after Story 5.8 ships, this happens automatically)
ANALYST_ID=$(jq -r '.[] | select(.role=="analyst") | .id' apps/cockpit-api/fixtures/users.json)
curl -s -X POST "http://localhost:8000/v1/cases/${VORA_CAPITAL_ID}/ubo/learning-events" -H "X-Cockpit-Demo-User: ${ANALYST_ID}" ... # Story 5.5 body
# Then refresh the page (Story 5.8 will trigger auto-refresh):
# Expected: 200ms cross-fade on ownership_clarity segment; total drops to 32; band pill says LOW

# Open Shree (low band):
# Expected: total 20; band pill: LOW (emerald); ownership_clarity ~60% of bar width

# Open Ananya (medium band):
# Expected: total 35; band pill: MEDIUM; screening (rose) visibly present at ~12%

# A11y:
poetry -C apps/cockpit-ui run vitest --grep 'a11y'

make lint && make test
```

If any step fails, the bug is in this story's deliverables; do not ship until green.

## Dev Agent Record

### Agent Model Used

(claude-opus-4-7 + Amelia persona, bmad-dev-story workflow)

### Debug Log References

### Completion Notes List

### File List

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-05-08 | Story 5.7 drafted. Demo replacement for the bank-buyer Story 5.8: stacked-bar with 5 colored segments, hover tooltips, 200ms cross-fade animation, full keyboard accessibility, three pinned demo fixtures. |
