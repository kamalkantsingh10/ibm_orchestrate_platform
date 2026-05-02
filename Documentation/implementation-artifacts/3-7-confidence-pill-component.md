# Story 3.7: ConfidencePill component

Status: review

## Story

As a KYC Analyst scanning the Documents panel (Story 3-6) and — soon — every other agent-driven panel,
I want confidence visualized as a four-tier banded pill (Low / Med-Low / Med-High / High) with shape + position + label redundancy and the optional numeric percentage, in three size variants (inline-small, inline-default, panel-header),
So that I instantly read trustworthiness across colors, shapes, and labels (NFR-AC3 color-blind safety) without reading raw 0.62-style floats, the demo's "confidence is visual, not textual" principle (UX-DR8) is met from the first agent output the analyst sees, and Story 3-6's `ProvenanceIndicator` composes a real pill instead of a stub (P7, FR10, UX-DR8).

## Scope note (2026-04-29 demo re-scope)

This story is the demo-equivalent of the bank-buyer Story 3.13. The component scope is essentially unchanged — the bank-buyer scope already specified a 4-tier pill with shape+position+label redundancy. The demo retains it verbatim because UI fidelity to the mockups is a load-bearing demo constraint (per `architecture.md#Demo Scope Addendum` § What stays).

| Bank-buyer scope (original 3.13) | Demo replacement in this story |
|---|---|
| ConfidencePill + Storybook entries with all 4 bands × 3 variants | **Same component, no Storybook.** Storybook isn't wired in the demo (out of scope for the cockpit-ui scaffolding). Visual coverage is via Vitest snapshot-style tests + manual demo verification. |
| Hover popover showing the full reasoning trace | **Hover popover deferred to Story 6-7** (alongside the full ReasoningTraceSlideOut content). The pill in this story is non-popover; click is delegated to the parent (Story 3-6's `ProvenanceIndicator` handles click). |
| Tooltip with numeric value when shape-only `inline-small` is hovered | **Deferred.** Demo accessibility is satisfied via `aria-label`; visible tooltip is a polish item. |

What survives: **the four-tier banded pill, three variants, shape+position+label redundancy, the `unknown` fallback for invalid input, full keyboard + screen-reader support.** Those are the demo's NFR-AC3 compliance + UX-DR8 fidelity assets.

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md`, `architecture.md#Project-Specific Patterns` P7, and `ux-design-specification.md` § ConfidencePill.

## Acceptance Criteria

1. **AC1 — `ConfidencePill` component lives at `apps/cockpit-ui/src/components/cockpit/ConfidencePill/ConfidencePill.tsx`.**

    Public props:
    ```typescript
    export interface ConfidencePillProps {
      /** [0.0, 1.0]. NaN, <0, or >1 renders the "unknown" band. */
      confidence: number;
      /** When provided, renders alongside the band shape + label. Omit to compute from `confidence`. */
      band?: ConfidenceBand;
      /** Visual size variant. Defaults to "inline-default". */
      variant?: 'inline-small' | 'inline-default' | 'panel-header';
      /** When true, renders the percentage next to the label. Default: variant === 'panel-header'. */
      showNumeric?: boolean;
      /** When true, renders as a focusable interactive element with onClick. */
      interactive?: boolean;
      onClick?: () => void;
      className?: string;
    }
    ```

    The component:
    - Computes the band via `band ?? toBand(confidence)` (using Story 3-3's TS helper at `lib/confidence.ts`).
    - When `confidence` is `NaN`, `< 0`, `> 1`, or `band` is mismatched-but-explicit (a defensive check), renders the **unknown** state (AC4) instead of throwing.
    - Renders three layers: shape marker → label text → optional percentage. The shape conveys the band even without color.
    - Wraps in a `<span>` (or `<button>` when `interactive`).

2. **AC2 — Shape markers per band (the "shape" half of shape+position+label redundancy).**

    Each band gets a distinct **shape**, rendered via inline SVG:
    - **HIGH** — solid filled disc (●)
    - **MEDIUM_HIGH** — half-filled disc (◐) — left half filled, right half hollow with the same outline weight
    - **MEDIUM_LOW** — hollow ring (○) with thicker outline (~2px relative)
    - **LOW** — hollow triangle (△) — pointing up to evoke "uncertain / suspect"
    - **unknown** — small "?" inside a dashed circle (∅-ish)

    Shape SVGs live as small inline components at the top of the file (do NOT import from `lucide-react` — none of these specific shapes are reliably present in Lucide; rolling them inline keeps the component self-contained). Each SVG is 10×10 viewBox, scaled to `w-2.5 h-2.5` (10px) for `inline-small`/`inline-default` and `w-3.5 h-3.5` (14px) for `panel-header`.

3. **AC3 — Color tokens per band.**

    Tailwind classes (kept token-friendly so a future story can swap to CSS-variable-driven theming):
    - **HIGH** — `text-emerald-600 bg-emerald-50 ring-emerald-600/20`
    - **MEDIUM_HIGH** — `text-sky-600 bg-sky-50 ring-sky-600/20`
    - **MEDIUM_LOW** — `text-amber-600 bg-amber-50 ring-amber-600/20`
    - **LOW** — `text-rose-600 bg-rose-50 ring-rose-600/20`
    - **unknown** — `text-zinc-500 bg-zinc-50 ring-zinc-300`

    The `bg-*` is the pill background; `text-*` is the shape + label color; `ring-*` is the optional 1px ring (used for focus + hover). **Color is the SECONDARY signal** per NFR-AC3 — the shape is the primary band signal. **Test asserts** (AC8) that the rendered DOM contains both the band's shape SVG `data-band-shape` attribute AND the band label text — color is incidental.

4. **AC4 — Unknown state.** When `confidence` is invalid (NaN, < 0, > 1) OR when `band` is provided but doesn't match `toBand(confidence)` (AC1 mismatch case):
    - Render the unknown shape + label `"?"` (or just `"—"` — pick one; document the choice).
    - When `process.env.NODE_ENV !== 'production'` (i.e., dev/test), emit a `console.warn("ConfidencePill: invalid confidence ${value}, rendering unknown band")` once per render. **Use a module-level `Set` of already-warned values** to prevent log spam from re-renders.
    - **TypeScript catches the type at the call site:** `confidence: number` is mandatory; passing `confidence={undefined}` is a TS error. The runtime guard is for the case where a backend response has a corrupt value despite the contract validators.

5. **AC5 — Variants.**

    - **`inline-small`** (10px shape, no label, optional numeric):
      - Shape only by default. If `showNumeric={true}`, render `<shape> 62%` with the percentage immediately right of the shape.
      - Used in dense contexts (e.g., the future status pill row, ScreeningExplainer rows).
      - aria-label always conveys the full info: `"Confidence: Medium-Low, 62%"`.
    - **`inline-default`** (10px shape + label):
      - Renders `<shape> Medium-Low` (or `<shape> Medium-Low 62%` when `showNumeric={true}`).
      - The default variant. Used by Story 3-6's `ProvenanceIndicator`.
    - **`panel-header`** (14px shape + label + numeric):
      - Renders `<shape> Medium-Low 62%` always (numeric defaults to true).
      - Used in DecompositionPanel headers (Epic 5+).

    Sizing convention: the pill's text is `text-xs` (12px) for inline variants and `text-sm` (14px) for panel-header. Padding adapts: `px-1.5 py-0.5` for inline, `px-2 py-1` for panel-header.

6. **AC6 — Label text per band.**

    The user-visible label:
    - **HIGH** → `"High"`
    - **MEDIUM_HIGH** → `"Med-High"`
    - **MEDIUM_LOW** → `"Medium"` (per UX spec § ConfidencePill anatomy: "High | Med-High | Medium | Low")
    - **LOW** → `"Low"`
    - **unknown** → `"Unknown"`

    Note the asymmetry: `MEDIUM_LOW` is labeled `"Medium"` per the UX spec, NOT `"Med-Low"`. This is deliberate — the four-tier band has been visually labeled as `Low / Medium / Med-High / High` to keep the lower-confidence label simple. **Don't second-guess this** — the UX spec is explicit. Document the asymmetry in a comment block in the component file.

    Helper: `bandLabel(band: ConfidenceBand | 'unknown'): string` — exported from the component file alongside the React component for testing + reuse by `ProvenanceIndicator` if needed.

7. **AC7 — Accessibility.**

    - `role="img"` for non-interactive variants; the entire pill is ARIA-labeled as a unit (so screen readers don't read shape/label/percentage as three separate elements).
    - `aria-label="Confidence: Medium-Low, 62%"` (or `"Confidence: High"` when no numeric is shown). For unknown: `"Confidence: unknown — invalid value"`.
    - When `interactive={true}`:
      - Renders as `<button type="button">` with `aria-label` as above plus `" — click to inspect"`.
      - Keyboard: Tab focuses; Enter and Space invoke `onClick`; focus-visible adds `ring-2 ring-zinc-400` outline.
    - The shape SVG has `aria-hidden="true"` (parent's aria-label covers it).
    - Color contrast: Tailwind's `text-*-600` on `bg-*-50` meets WCAG AA at 12px text. **Verify with the axe-core check** (run via vitest setup) for at least one band.
    - Respects `prefers-reduced-motion`: hover/focus transitions use `transition-colors duration-150` for default, but skip transitions when reduced-motion is preferred (use Tailwind's `motion-reduce:transition-none`).

8. **AC8 — Vitest unit tests cover bands × variants × invalid inputs.** `apps/cockpit-ui/src/components/cockpit/ConfidencePill/ConfidencePill.test.tsx`:

    - **Band coverage:** parametrize over the 4 bands × 3 variants = 12 combos; each renders the right shape (assert via `data-band-shape="high|medium_high|medium_low|low"`), the right label text (per AC6), and the right pill background class (use `getByRole('img').classList`).
    - **Numeric formatting:** `confidence={0.624}` with `showNumeric={true}` renders `"62%"` (rounded to nearest integer); `confidence={0.85}` renders `"85%"`; `confidence={1.0}` renders `"100%"`.
    - **Inline-small without numeric:** `variant="inline-small"`, default `showNumeric=false` → no `%` text rendered; `aria-label` still includes `", 62%"`.
    - **Unknown state:** `confidence={NaN}` → unknown shape + `"Unknown"` label + warn logged (assert via spy on `console.warn`); same for `<0` and `>1`.
    - **Mismatched band:** `confidence={0.62}` + `band={ConfidenceBand.HIGH}` → unknown state (band doesn't match `toBand(0.62)`).
    - **Interactive:** `interactive={true}` + `onClick={spy}` → renders `<button>`; click calls spy; keyboard Enter calls spy; keyboard Space calls spy.
    - **Non-interactive:** default `interactive=undefined` → renders `<span>` or `<div>`; no button element; not focusable.
    - **Aria-label:** assert text matches the AC7 patterns for each band/variant.
    - **bandLabel helper:** parametrized test of all 5 input values mapped to the AC6 labels.

9. **AC9 — Story 3-6's `ProvenanceIndicator` consumes the real pill.** This story does NOT modify the `ProvenanceIndicator` component — Story 3-6's implementation either already imports from `apps/cockpit-ui/src/components/cockpit/ConfidencePill/ConfidencePill` (if Story 3-7 was sequenced first per Story 3-6 dev notes) OR replaces a stub. Verify by:
    1. Run `make test` — Story 3-6's `ProvenanceIndicator.test.tsx` and `DocumentsPanel.test.tsx` still pass against the real pill.
    2. Open the demo (`make dev`) and visually confirm pills in the Documents panel render with shape + label + (where `panel-header`-sized) numeric.

10. **AC10 — Visual coverage table.** A markdown table at the top of `ConfidencePill.tsx` (or a sibling `README.md` if the dev prefers — small, ~10 lines) documents the band × variant matrix as visible dev-time reference:

    ```
    | Variant         | LOW          | MEDIUM_LOW   | MEDIUM_HIGH  | HIGH         | unknown      |
    |-----------------|--------------|--------------|--------------|--------------|--------------|
    | inline-small    | △            | ○            | ◐            | ●            | ?            |
    | inline-default  | △ Low        | ○ Medium     | ◐ Med-High   | ● High       | ? Unknown    |
    | panel-header    | △ Low 18%    | ○ Medium 62% | ◐ Med-High 78% | ● High 92%  | ? Unknown   |
    ```

    Helps future maintainers eyeball the pill's intended states without running the demo.

11. **AC11 — `make lint` + `make test` clean.** New test count adds at least: 18+ in `ConfidencePill.test.tsx`. ESLint + Prettier + tsc strict pass. Story 3-6's existing tests still pass against the real pill.

## Tasks / Subtasks

- [ ] **Task 1 — Author the component file** (AC: #1, #2, #3, #4, #5, #6, #7)
  - [ ] Subtask 1.1 — Create `apps/cockpit-ui/src/components/cockpit/ConfidencePill/ConfidencePill.tsx` and `index.ts` (barrel export).
  - [ ] Subtask 1.2 — Define the inline shape SVGs at the top of the file: `<HighShape>`, `<MediumHighShape>`, `<MediumLowShape>`, `<LowShape>`, `<UnknownShape>`. Each is a stateless functional component returning a 10×10 viewBox SVG with `data-band-shape="..."` attribute for testing. Use stroke-width that scales with the SVG size.
  - [ ] Subtask 1.3 — Define `bandLabel(band: ConfidenceBand | 'unknown'): string` per AC6. Export.
  - [ ] Subtask 1.4 — Implement the main component per AC1. Use a switch/lookup keyed by `band` (or `'unknown'`) for shape + colors + label. Compute the band via `band ?? toBand(confidence)` with the invalid-confidence check inside a try/catch (since `toBand` from Story 3-3 raises on invalid input, the catch sets `band = 'unknown'`).
  - [ ] Subtask 1.5 — Compute the percentage as `Math.round(confidence * 100)` only when `band !== 'unknown'`.
  - [ ] Subtask 1.6 — Implement `aria-label` per AC7. The accessibility test in AC8 will assert the patterns.
  - [ ] Subtask 1.7 — Add `motion-reduce:transition-none` per AC7's reduced-motion handling. Default transition: `transition-colors duration-150`.
  - [ ] Subtask 1.8 — Add the AC10 markdown matrix as a comment block at the top of the file (or as a sibling `README.md`).

- [ ] **Task 2 — Tests** (AC: #8)
  - [ ] Subtask 2.1 — Create `ConfidencePill.test.tsx` next to the component. Use `@testing-library/react` (already a dep).
  - [ ] Subtask 2.2 — Implement the 4×3 band×variant matrix as a parametrized test using `describe.each` or `it.each`. Assert shape, label, and class names per AC8.
  - [ ] Subtask 2.3 — Implement the unknown-state tests (NaN, <0, >1, mismatched band). Spy on `console.warn` via `vi.spyOn(console, 'warn')` and assert the warning fired.
  - [ ] Subtask 2.4 — Implement the interactive tests (button rendering, click handler, Enter/Space keyboard activation).
  - [ ] Subtask 2.5 — Implement the `bandLabel` helper test as a parametrized test.

- [ ] **Task 3 — Verify integration with Story 3-6** (AC: #9)
  - [ ] Subtask 3.1 — Run `make test` in `apps/cockpit-ui`. Confirm Story 3-6's `ProvenanceIndicator.test.tsx` and `DocumentsPanel.test.tsx` pass — either:
      - (sequenced first) they were already importing from `ConfidencePill/ConfidencePill`, no change needed; OR
      - (sequenced after) Story 3-6 used a stub; replace the stub import with the real one. Search for `// STUB — Story 3-7` comments in `apps/cockpit-ui/src/` and remove the stubs.
  - [ ] Subtask 3.2 — Run `make dev`; navigate to `/cases/<vora-id>`; manually inspect each pill in the Documents panel — should show shape + label, click should be delegated to the parent's `ProvenanceIndicator` handler (which opens the slide-out from Story 3-6).

- [ ] **Task 4 — Final lint/test pass** (AC: #11)
  - [ ] Subtask 4.1 — Run `make lint` from repo root; clean.
  - [ ] Subtask 4.2 — Run `make test`. Confirm `apps/cockpit-ui` test count up by ≥18; no regressions.

## Dev Notes

### Sequencing with Story 3-6

If 3-6 was implemented first with a stub `<ConfidencePill>`, this story's Task 3 includes stub-cleanup. If 3-7 was sequenced first, this story has no integration debt. **Either order works**; the visible test signal is whether Story 3-6's `ProvenanceIndicator.test.tsx` references the real pill's `data-band-shape` attribute. If it doesn't, Task 3.1 patches it.

### Architectural context (binding)

[Source: `architecture.md#Project-Specific Patterns` P7 Confidence Banding Pattern] — "UI renders bands via shape + position + label (NFR-AC3)." The triple redundancy is the demo's color-blind compliance argument. **The shape is non-negotiable.** Don't skip it for "design simplicity."

[Source: `ux-design-specification.md` § ConfidencePill] — Anatomy: shape-marker + label-text + optional numeric-value. Variants: inline-small, inline-default, panel-header. This story implements all three exactly per the spec.

[Source: `architecture.md#Demo Scope Addendum (2026-04-29)` § What stays] — UI fidelity to mockup is a load-bearing demo constraint. The pill is a recurring visual primitive across the cockpit; nailing it now pays dividends across Epic 4–7's panel work.

[Source: `prd.md#NFR-AC3, FR10`] — color-blind safety is a hard requirement; 4-tier banded confidence is the chosen visual idiom. Story 3-7 is the canonical implementation.

[Source: `architecture.md#Anti-Patterns to Refuse`] — N/A directly, but adjacent: "Pydantic schemas duplicated in apps." The `ConfidenceBand` enum + `toBand` helper from Story 3-3's TS mirror is the single source of truth — this story does NOT redefine band thresholds.

### Critical pitfalls to avoid

1. **Color is secondary, shape is primary.** A common mistake: lazily skip the SVG shapes and rely only on color. **Don't.** A color-blind officer reading the cockpit MUST distinguish all 4 bands without color. The shape SVGs (filled disc / half / hollow ring / triangle / question) are the primary signal; color is a redundant aid. The AC8 test asserts shape attribute existence — use that as the safety net.

2. **`MEDIUM_LOW` label is `"Medium"`, not `"Med-Low"`.** Per UX spec. Easy to misremember. AC6 documents this; if the dev finds the asymmetry confusing, push back via PR comment but **do not unilaterally change** — coordinate with the UX direction owner.

3. **`toBand` raises on NaN/inf/out-of-range.** The component's runtime guard wraps the call in try/catch (or pre-validates with `Number.isNaN(c) || c < 0 || c > 1`). Don't propagate the exception — the component should never throw.

4. **`band` prop overrides `confidence`-derived band only when consistent.** The component computes `derivedBand = toBand(confidence)`. If `band` is provided AND `band !== derivedBand`, the component renders the **unknown** state (warning of mismatch). This is the single-source-of-truth discipline — disagreement means a bug upstream, surface it visibly. **Don't trust `band` blindly** — that's how component contracts erode.

5. **`console.warn` spam protection.** Re-renders with the same invalid input would log on every render. Use a module-level `Set<string>` of already-warned signatures: `const _warned = new Set<string>(); function warnOnce(key, msg) { if (!_warned.has(key)) { _warned.add(key); console.warn(msg); } }`. The signature can be `${confidence}_${band}`.

6. **Don't add a Tooltip dep.** Radix Tooltip would be the reflexive choice for "hover shows %". This story explicitly defers tooltips to Story 6-7. Keeping the deps tight matters — `@radix-ui/react-tooltip` is ~5KB gzipped, not free.

7. **Inline SVG, not Lucide.** Lucide has `Circle`, `Triangle`, etc. but their stroke and fill behavior doesn't easily map to "filled disc vs half-disc vs hollow ring." Inline SVG (5 small components, ~10 lines each) is cleaner. Use `viewBox="0 0 10 10"` so the shape scales naturally with parent font-size + Tailwind `w-*`/`h-*` classes.

8. **Don't add the popover state machine.** The pill's `interactive` mode is just `<button>` + `onClick`. The popover (hover preview) AND slide-out (click) are both Story 6-7's job. The current click delegation is to the parent (Story 3-6's `ProvenanceIndicator` opens the slide-out shell). Don't add a self-managed `Popover.Root` here.

9. **Tailwind class-name strings get long.** A common pattern: build the full class via `clsx` (already a dep). Pattern:
    ```typescript
    const classes = clsx(
      'inline-flex items-center gap-1 rounded-full ring-1',
      variant === 'panel-header' ? 'px-2 py-1 text-sm' : 'px-1.5 py-0.5 text-xs',
      bandColors[band],   // e.g., 'text-emerald-600 bg-emerald-50 ring-emerald-600/20'
      interactive && 'cursor-pointer focus-visible:ring-2 focus-visible:ring-zinc-400',
      className,          // prop-passed extension
    );
    ```

10. **`Number.isNaN` not global `isNaN`.** Global `isNaN("abc")` returns `true` (string coerced); `Number.isNaN("abc")` returns `false` (only true for actual NaN). Use the latter to avoid false positives.

11. **`prefers-reduced-motion` handled via Tailwind, not JS.** `motion-reduce:transition-none` handles the entire CSS-transition skip. No need to read `window.matchMedia("(prefers-reduced-motion: reduce)")` in JS — Tailwind compiles to the right CSS.

12. **Don't mutate `confidence` to "fix" out-of-range values.** Some libraries clamp `1.5` to `1.0`. **Don't.** Out of range → unknown band. Surfacing the bug is better than hiding it.

13. **`aria-label` on `<button>` overrides the default text-content reading.** When the pill is interactive, the button's child elements (shape, label, percent) are read via the explicit aria-label — no need to add `aria-hidden` to children. Confirm with axe-core in the AC8 test.

14. **Visual matrix in the AC10 doc table is dev-facing only.** Don't ship it as a customer-facing legend. The user discovers the band semantics through repeated exposure (per UX spec § Discoverability principles).

15. **`text-emerald-600` vs `text-green-600`.** The Tailwind palette has both `green` and `emerald`. The UX spec doesn't specify a precise hue; **bind on `emerald-600`** (slightly cooler green, matches the cockpit's other surfaces better). Same for `sky-600` (vs `blue`), `amber-600` (vs `yellow`/`orange`), `rose-600` (vs `red`). Document these choices in the file's docstring.

### Architecture patterns relevant here

[Source: `architecture.md#Project-Specific Patterns` P7] — Internal `[0.0, 1.0]` floats; display 4-tier banded enum. **The display boundary is `<ConfidencePill confidence={c} />`.** No code path consumes a raw float for UI rendering; the pill mediates.

### Project Structure Notes

This story creates:

- `apps/cockpit-ui/src/components/cockpit/ConfidencePill/ConfidencePill.tsx`
- `apps/cockpit-ui/src/components/cockpit/ConfidencePill/ConfidencePill.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/ConfidencePill/index.ts`

This story modifies (Task 3, only if Story 3-6 stubbed the pill):

- `apps/cockpit-ui/src/components/cockpit/ProvenanceIndicator/ProvenanceIndicator.tsx` — replace stub import with the real component
- (any other files where Story 3-6 left `// STUB — Story 3-7 owns the full component` markers)

This story DOES NOT create:

- A Storybook setup (out of scope for the demo's tooling)
- A Tooltip-driven hover preview (Story 6-7)
- A self-managed popover (Story 6-7)
- New Tailwind tokens or theme extensions (uses Tailwind's stock palette)
- A pill-data API endpoint (no — confidence is part of `Provenance`, fetched by Story 3-6's hook)

### References

- [Source: `architecture.md#Project-Specific Patterns` P7] — confidence banding pattern
- [Source: `ux-design-specification.md` § ConfidencePill] — anatomy, variants, accessibility
- [Source: `architecture.md#Demo Scope Addendum (2026-04-29)`] — UI fidelity is preserved
- [Source: `prd.md#NFR-AC3, FR10, UX-DR8`] — color-blind safety, 4-tier confidence visualization
- [Source: `epics.md#Epic 3` § Story 3.13] — original AC (re-scoped here)
- [Source: `3-3-pydantic-contracts-for-ledger-provenance-confidence.md`] — `ConfidenceBand`, `toBand`, `CONFIDENCE_THRESHOLDS` in TS
- [Source: `3-6-documents-panel-on-case-canvas-with-provenance-pills.md`] — `ProvenanceIndicator` (consumer)

### Previous Story Intelligence

[Source: `1-4-cockpit-shell-with-user-switcher-three-hardcoded-roles.md`]
- Component file structure: one folder per component (`ComponentName/ComponentName.tsx`, `index.ts`, `ComponentName.test.tsx`). Mirror.
- `clsx` is the canonical class-composition helper (used in `UserSwitcher.tsx` and `QueueRail.tsx`).

[Source: `2-3-case-appears-in-queue-rail-basic-ordering.md`]
- Vitest test pattern: `import { render, screen } from '@testing-library/react'`. Tests are co-located with components. `vi.spyOn(console, 'warn')` is the canonical warning spy.

[Source: `3-3-pydantic-contracts-for-ledger-provenance-confidence.md`]
- `ConfidenceBand` is `as const`-typed in TS, NOT a TS `enum`. Import as `import { ConfidenceBand } from '@/lib/confidence'`. Use `ConfidenceBand.HIGH`, etc.
- `toBand(confidence: number): ConfidenceBand` raises `RangeError` on invalid input. The component's try/catch is the right pattern.
- `CONFIDENCE_THRESHOLDS` is exported as an array of `{ band, min }` objects in declining order. Useful for the AC10 dev matrix at minimum.

[Source: `3-6-documents-panel-on-case-canvas-with-provenance-pills.md`]
- `ProvenanceIndicator` composes `ConfidencePill` (this story). The size used by `ProvenanceIndicator` is `inline-default` per Story 3-6's anatomy spec.
- Click on the pill is delegated to `ProvenanceIndicator`'s `onClick` (which opens the placeholder slide-out). The pill itself is non-interactive when used inside `ProvenanceIndicator` (the pill's `interactive` prop stays default, the parent's button is the click target).

### Demo verification protocol (operator hand-off)

```bash
# After implementing, the dev must verify:

# 1. Component renders all 4 bands × 3 variants (manual via Vitest):
cd apps/cockpit-ui
pnpm run test ConfidencePill
# Expected: 18+ tests pass; the 4×3 matrix is exhaustively covered.

# 2. Story 3-6 integration (if it was sequenced first):
pnpm run test
# Expected: ProvenanceIndicator.test.tsx, DocumentsPanel.test.tsx pass against the real pill.

# 3. Visual smoke (manual):
make demo-reset && make seed && make dev
# Open http://localhost:5173/queue
# Click Vora Capital
# Inspect the Documents panel:
# - CIN field: HIGH band (filled disc, emerald color, "High" label)
# - registered_address: MEDIUM_LOW (hollow ring, amber, "Medium")
# - bank_statement_q1.pdf account_holder_name: MEDIUM_HIGH (half disc, sky, "Med-High")
# Each should be visibly distinct via shape AND label, not just color.

# 4. Color-blind sanity check (manual):
# Open the cockpit in a browser; activate a color-blindness simulator
# (e.g., Chrome DevTools Rendering → Emulate vision deficiencies).
# Cycle through Protanopia, Deuteranopia, Tritanopia.
# Expected: all 4 bands remain distinguishable via shape + label even without color.

# 5. Numeric formatting:
# Inspect a panel-header pill (will exist in Epic 5; for now spot-check via tests).
# Expected: percentages render as integers ("62%", not "62.4%").

# 6. Reduced motion:
# Set `prefers-reduced-motion: reduce` in OS settings; refresh the cockpit.
# Hover over pills.
# Expected: no transition animation; pills snap to focused state.

# 7. Lint + test green:
make lint && make test
```

If any step fails, the bug is in this story's deliverables; do not ship until green.

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (Amelia persona, bmad-dev-story workflow)

### Debug Log References

* React-refresh constraint required moving `bandLabel` out of `ConfidencePill.tsx` (file may only export components). Now lives in sibling `bandLabel.ts` and is re-exported via `index.ts`.
* `vi.spyOn(console, 'warn').mockImplementation(() => {})` silences the unknown-state warnings during tests; spy assertions confirm they fire.

### Completion Notes List

* All 4 bands × 3 variants (12 combinations) render correctly with shape + label + percent per AC8. Color is the SECONDARY signal — tests assert via `data-band-shape="…"` attribute, not color class.
* Unknown state fires for: NaN, Infinity, <0, >1, AND mismatch between explicit `band` prop and `toBand(confidence)`. Warn-once via module-level Set keyed by `${confidence}_${band}` to prevent re-render spam.
* Inline SVG shapes (HIGH solid disc, MED_HIGH half-disc, MED_LOW hollow ring with thicker stroke, LOW upward triangle, UNKNOWN dashed circle with `?`) — 5 small components at the top of `ConfidencePill.tsx`. No Lucide deps for these.
* Color tokens: `emerald-600` / `sky-600` / `amber-600` / `rose-600` over `-50` backgrounds with `-600/20` rings, per Pitfall #15.
* `MEDIUM_LOW` labels as **"Medium"** (not "Med-Low") per UX spec asymmetry — documented at `bandLabel`.
* Reduced-motion handled via Tailwind `motion-reduce:transition-none` (no JS `matchMedia`).

### File List

**Created**
* `apps/cockpit-ui/src/components/cockpit/ConfidencePill/ConfidencePill.tsx`
* `apps/cockpit-ui/src/components/cockpit/ConfidencePill/bandLabel.ts`
* `apps/cockpit-ui/src/components/cockpit/ConfidencePill/ConfidencePill.test.tsx` — 30 tests
* `apps/cockpit-ui/src/components/cockpit/ConfidencePill/index.ts`

**Modified**
* `Documentation/implementation-artifacts/sprint-status.yaml` — story marked `review`

(Story 3.6's `ProvenanceIndicator` consumes the pill directly — Story 3.7 was sequenced first so no stub cleanup was needed.)

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-04-30 | Story 3.7 drafted. Demo replacement for the bank-buyer Story 3.13 (essentially unchanged scope — UI fidelity preserved per Demo Scope Addendum). Implements the 4-band × 3-variant ConfidencePill with shape + position + label redundancy (NFR-AC3 color-blind safety), unknown fallback, accessibility, and reduced-motion support. The canonical confidence renderer for the entire cockpit, consumed first by Story 3-6's ProvenanceIndicator. |
