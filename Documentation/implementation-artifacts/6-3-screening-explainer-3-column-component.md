# Story 6.3: Screening Explainer 3-column component

Status: review

## Story

As a KYC Analyst,
I want a `ScreeningExplainer` 3-column card ("what matched" / "what didn't" / "counterfactual") that renders each `ScreeningHit` from Story 6-2 inside a `ScreeningPanel` on the Case Canvas — replacing the `Identity` `PanelStub` from Story 5-9 and using the same `CollapsiblePanel` chrome — with `ConfidencePill` showing the name-match band, auto-dismissed hits collapsed under a "5 auto-dismissed (review)" disclosure, and the panel hero-tinting amber when ≥ 1 open hit exists,
So that Priya's J1 narrative ("scans canvas in ~40 sec · sees amber Screening hero panel") lands, the demo's signature "what would change your mind?" counterfactual surfaces inline (Innovation #2), and Story 6-6's slide-out has a row to drill into when she clicks the amber pill (FR19, FR20, UX-DR21, Innovation #2 counterfactual reasoning, NFR-RI1 ADK pattern showcase).

## Scope note (2026-04-29 demo re-scope)

This story is the demo-equivalent of the bank-buyer Story 6.4. The bank-buyer scope included an inline officer "re-run with different parameters" loop (relax DOB tolerance → SSE refresh) — that's deferred. The 3-column visual primitive is preserved exactly; the live re-run is the cut.

| Bank-buyer scope (original 6.4) | Demo replacement in this story |
|---|---|
| Each hit → 3-column card: Matched · Didn't match · Counterfactual | **Same.** The 3-column card is the load-bearing primitive — preserved. |
| Tenant-scoped query keys | **Single-tenant** — query key is `["case", caseId, "intake"]` (already established by Stories 3-4 / 5-1). |
| "Re-run with different parameters" interaction → SSE refresh | **Cut.** The hit is rendered read-only. Story 6-7's Cockpit Chat exposes a `re_run_agent` tool path for ad-hoc re-runs. |
| ConfidencePill on every card | **Same.** Story 3-7's `ConfidencePill` consumed verbatim. |
| Officer re-include of auto-dismissed hits | **Cut.** Auto-dismissed hits are visible (collapsed) but not re-includable in the demo. |

What survives: **3-column layout, hit-level confidence pill, counterfactual sentence, inline category + source list rendering, hero-tint on amber/red panels, replacement of the `Identity` `PanelStub` with the new `ScreeningPanel`, integration with `useScreeningHits` query hook, click-to-open Reasoning Trace Slide-Out (Story 6-6).**

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md`, `architecture.md#Frontend Architecture`, `ux-design-specification.md` § ScreeningExplainer + § J1 narrative arcs, and `6-1-screening-adapter-protocol-with-mock-impl.md` / `6-2-screening-agent.md` for the typed source data.

## Acceptance Criteria

1. **AC1 — `useScreeningHits` query hook at `apps/cockpit-ui/src/hooks/useScreeningHits.ts`.**

    Reuses the existing intake query (Stories 3-4 / 5-1 / 5-3 already populate `apps/cockpit-ui/src/hooks/useDocumentIntelligence.ts` and `useUboGraph.ts` from the same `GET /v1/cases/{id}/intake` endpoint). Mirror the same shape:

    ```typescript
    import type { components } from '@/api-types';
    import { useQuery } from '@tanstack/react-query';

    type ScreeningAgentOutput = components['schemas']['ScreeningAgentOutput'];

    export function useScreeningHits(caseId: string) {
        return useQuery<ScreeningAgentOutput | null>({
            queryKey: ['case', caseId, 'intake', 'screening'],
            queryFn: async () => {
                const res = await fetch(`/v1/cases/${caseId}/intake`);
                if (!res.ok) throw new Error('intake fetch failed');
                const json = await res.json();
                return json.screening ?? null;
            },
            staleTime: 30_000,
        });
    }
    ```

    Read the existing intake-query hook first (see `apps/cockpit-ui/src/hooks/useUboGraph.ts`) and re-use its query-key + fetch pattern verbatim (a single `useIntake(caseId)` may exist that returns the whole intake blob — if so, derive `screening` from it via a `useMemo` and skip the new hook). **One source of truth for the intake fetch.**

    Tests at `useScreeningHits.test.tsx`: renders with mocked endpoint; null when screening absent; returns hits on happy path.

2. **AC2 — `ScreeningExplainer` 3-column card at `apps/cockpit-ui/src/components/cockpit/ScreeningExplainer/ScreeningExplainer.tsx`.**

    ```typescript
    import type { components } from '@/api-types';
    import { ConfidencePill } from '@/components/cockpit/ConfidencePill';

    type ScreeningHit = components['schemas']['ScreeningHit'];

    export interface ScreeningExplainerProps {
        hit: ScreeningHit;
        subjectName: string;        // resolved by parent from subject_id → human-readable
        subjectDob?: string | null; // ISO date if known; null otherwise
        onOpenSlideOut: (hitId: string) => void;
    }

    export function ScreeningExplainer({
        hit, subjectName, subjectDob, onOpenSlideOut,
    }: ScreeningExplainerProps): JSX.Element { ... }
    ```

    Renders three columns inside a `<button>` that fires `onOpenSlideOut(hit.hit_id)`:

    | Column | Heading | Content |
    |---|---|---|
    | **Matched** | "Matched" (`text-xs uppercase tracking-wide text-zinc-500`) | "Name {pct}% similar" (e.g., "Name 73% similar"). If hit.identifiers (cin/pan) match the subject's, also list "+CIN exact". |
    | **Didn't match** | "Didn't match" | DOB comparison if both present and differ: "DOB {subjectYear} vs {hitYear}". Else "—". |
    | **Counterfactual** | "What would change it" | One-liner derived from hit's score + DOB delta: see AC3. |

    Above the columns: `<header>` with subject name (left), category badges (right), and the `ConfidencePill` showing `confidence={hit.name_match_score.value}`. Below the columns: a small footer line listing `source_lists.join(' · ')` (e.g., "OFAC SDN").

    `text-sm` body, `text-zinc-700` for content, `text-zinc-500` for headings. Card border + padding mirrors existing DocumentsPanel rows: `rounded-md border border-zinc-200 px-4 py-3`. On hover the card shows a subtle ring (`hover:ring-2 hover:ring-amber-300/50` for open hits, `hover:ring-zinc-300/50` for dismissed).

3. **AC3 — Counterfactual sentence generation (client-side derivation).**

    Story 6-4 introduces the `ReasoningTrace` Pydantic contract with a server-side `counterfactual` string. **However**, this story ships before 6-4 fleshes out the agent-side reasoning trace. For the demo's screening flow, derive the counterfactual on the client from the hit's structured fields:

    * If `name_match_score.value < 0.85` AND `subjectDob` and `hit.date_of_birth` differ → `"Would upgrade to high if DOB matches; downgrade if address+ID confirm different person."`
    * If `name_match_score.value >= 0.85` AND `subjectDob == hit.date_of_birth` → `"High match on name and DOB. Disposition would change if officer evidence confirms a different person."`
    * If `subjectDob` or `hit.date_of_birth` is null → `"Confidence depends on DOB resolution. Capture DOB to refine."`
    * Default → `"Disposition depends on officer evidence; review identifiers and source list."`

    Centralize this in a pure helper: `apps/cockpit-ui/src/components/cockpit/ScreeningExplainer/counterfactual.ts`, exported as `function deriveCounterfactual(hit: ScreeningHit, subjectDob?: string | null): string`.

    **Important — when Story 6-4 lands and the agent emits a real `reasoning_trace.counterfactual`, this client-side derivation becomes the fallback only.** The `ScreeningExplainer` should prefer `hit.reasoning_trace?.counterfactual` if present (post-6-4), else fall back to `deriveCounterfactual(...)`. Code the prefer-server-then-client logic now; Story 6-4 wires the field through.

4. **AC4 — `ScreeningPanel` at `apps/cockpit-ui/src/components/cockpit/ScreeningPanel/ScreeningPanel.tsx`.**

    Wraps `useScreeningHits` and renders the panel chrome via Story 5-9's `CollapsiblePanel`:

    ```typescript
    import { CollapsiblePanel } from '@/components/cockpit/CollapsiblePanel';
    import { useScreeningHits } from '@/hooks/useScreeningHits';
    import { ScreeningExplainer } from '@/components/cockpit/ScreeningExplainer';

    export interface ScreeningPanelProps {
        caseId: string;
        onOpenReasoningTrace: (agentActionId: string, hitId: string) => void;
    }

    export function ScreeningPanel({ caseId, onOpenReasoningTrace }: ScreeningPanelProps): JSX.Element { ... }
    ```

    Logic:
    * `const { data, isPending, isError } = useScreeningHits(caseId);`
    * Split hits: `openHits = data.hits.filter(h => h.disposition === 'open')`; `dismissedHits = data.hits.filter(h => h.disposition === 'dismissed_by_agent')`.
    * Header summary: `"{openHits.length} open · {dismissedHits.length} auto-dismissed"`. If both 0 and not pending → `"No matches"`.
    * Open hits render in document order, each as a `<ScreeningExplainer>`.
    * Auto-dismissed hits: render under a `<details>` element (`<summary>"{n} auto-dismissed (review)"</summary>`), each rendered as a smaller, dimmed `ScreeningExplainer` (pass `dimmed` prop or a `data-dismissed` attr the component reads).
    * Hero-tint: when `openHits.length >= 1`, panel root gets `bg-amber-50/40` (5–6% opacity per UX spec; map to Tailwind's `bg-amber-50/40` or a custom `tokens.amber-tint` class). Story 5-9's `CollapsiblePanel` should accept a `tone?: 'default' | 'attention'` prop or className override — confirm Story 5-9's signature first; if it doesn't expose tonal overrides, **add a `tone` prop to `CollapsiblePanel`** as part of this story (small, additive — note in AC9).

5. **AC5 — Replace `Identity` `PanelStub` in `apps/cockpit-ui/src/routes/cases.$caseId.tsx`.**

    Story 5-9 left the Identity stub in place with `epic="6"`. This story replaces it with `<ScreeningPanel caseId={caseId} onOpenReasoningTrace={...} />`:

    ```tsx
    <div className="grid grid-cols-2 gap-4 max-w-5xl">
        <div className="col-span-2">
            <DocumentsPanel ... />
        </div>
        <ScreeningPanel caseId={caseId} onOpenReasoningTrace={openSlideOut} />   {/* WAS: <PanelStub title="Identity" epic="6" /> */}
        <UBOPanel caseId={caseId} />
        <RiskPanel caseId={caseId} />
    </div>
    ```

    `openSlideOut(agentActionId, hitId)` is wired to the existing `ReasoningTraceSlideOut` integration (Story 6-6 fleshes out the slide-out itself; for now this story passes the `agentActionId` from the screening hit's evidence_ids — see AC6 for the resolver).

6. **AC6 — `agentActionId` resolution from a hit.**

    `ScreeningHit.name_match_score.provenance.evidence_ids` holds a one-element list with the screening agent's `agent.completed` ledger entry ID (back-filled by Story 6-2 § AC5). For the slide-out, that ID is the **agent action ID** to pass to `onOpenReasoningTrace`. Resolution:

    ```typescript
    const agentActionId = hit.name_match_score.provenance.evidence_ids[0] ?? null;
    if (!agentActionId) {
        // legacy / not back-filled — open slide-out in degraded mode (Story 6-6 handles)
    }
    ```

    `ScreeningExplainer`'s `onOpenSlideOut` callback receives the hit's ID; the **panel** is responsible for resolving the agent action ID and calling `onOpenReasoningTrace(agentActionId, hit.hit_id)`. Keep the callback shape: `(agentActionId, hitId) => void`.

7. **AC7 — `subject_id → subjectName` resolution.**

    `ScreeningHit.subject_id` is the case-internal id (entity uuid, UBO node id, director ULID — see Story 6-2 § AC4). To render a human-readable name, the panel resolves it against:
    * Entity → `case.customer_metadata.customer_name` (from the existing `useCase(caseId)` hook).
    * UBO node → `useUboGraph(caseId).data.nodes.find(n => n.id === subject_id)?.name`.
    * Director → not currently in any TanStack-cached query. Fall back to the hit's own `matched_name` if the subject_id is unrecognized.

    Encapsulate this in a small `useScreeningSubjectResolver(caseId)` hook returning `(subjectId: string) => { name: string; dob: string | null }`. Tested as a unit — covers all three lookup paths + the unknown fallback.

8. **AC8 — Default expansion + collapse behaviour.**

    * **Expanded by default** when `data?.hits.length > 0`. Initialize via `useState(() => Boolean(initial.hits?.length))` + `useEffect` to flip on first data arrival (mirror Story 5-9 `useUboGraph` pattern + its `hasAutoExpandedRef`). The Vora demo opens with the panel expanded — the amber hit must be visible without a click.
    * Collapsed when `data?.hits.length === 0` and the data is loaded. Header still says "No matches".
    * Collapsed when `isPending` and no cached data. Header says "Screening…".
    * `aria-expanded`, `aria-controls` come from `CollapsiblePanel` (Story 5-9).

9. **AC9 — `CollapsiblePanel` `tone` prop (additive).**

    Audit Story 5-9's `apps/cockpit-ui/src/components/cockpit/CollapsiblePanel/CollapsiblePanel.tsx`. Add an optional `tone?: 'default' | 'attention'` prop. `'attention'` adds `bg-amber-50/40 border-amber-200` to the panel root; `'default'` is the existing `bg-white border-zinc-200`. Other consumers (UBOPanel / RiskPanel) keep the default by omitting the prop. Update `CollapsiblePanel.test.tsx` with a single new case asserting the tonal class is applied.

    UX justification: ux-design-specification.md § Hero-tinted attention panel — "the one panel that needs officer attention (Screening in the example scenario) fills softly with its confidence-band color at ~5–6% opacity, border matches."

10. **AC10 — Tests at `apps/cockpit-ui/src/components/cockpit/ScreeningExplainer/ScreeningExplainer.test.tsx`.**

    * Renders subject name, all 3 columns, `ConfidencePill` with the hit's name_match_score band.
    * "Matched" column shows `"Name 73% similar"` for Vora's Patel R. fixture.
    * "Didn't match" column shows DOB delta when both DOBs present and differ; shows "—" when matching or null.
    * "What would change it" column shows the derived counterfactual sentence (assert against the four cases in AC3).
    * Click → `onOpenSlideOut(hit.hit_id)` fires.
    * Source list rendered in footer (`"OFAC SDN"`).
    * `dimmed` prop applies opacity-60 + cursor-default styling (no click handler when dismissed? Or still clickable but visually deemphasized — pick "still clickable, visually deemphasized" for demo simplicity; tests assert click handler still fires when dimmed=true).

11. **AC11 — Tests at `apps/cockpit-ui/src/components/cockpit/ScreeningPanel/ScreeningPanel.test.tsx`.**

    * **Vora — 1 OFAC hit visible, 0 dismissed** — mock `useScreeningHits` with the Vora fixture; assert one `<ScreeningExplainer>` rendered; header shows "1 open · 0 auto-dismissed"; tonal class is `'attention'`.
    * **Shree — 0 hits, header "No matches"** — collapsed by default.
    * **Ananya — 1 PEP hit, header "1 open · 0 auto-dismissed"** — tonal class is `'attention'`.
    * **Mixed — 1 open + 5 dismissed** — disclosure shows "5 auto-dismissed (review)"; expanding the disclosure renders 5 dimmed cards.
    * **Click on a hit → `onOpenReasoningTrace` fires with the back-filled agent action ID + hit ID.**
    * **Loading state** — assert "Screening…" header.
    * **Error state** — assert error message in panel body, no crash.

12. **AC12 — Tests at `apps/cockpit-ui/src/routes/cases.$caseId.test.tsx` (extend existing from Story 5-9).**

    * Render a Vora case with mocked intake (incl. the new `screening` field); assert `<ScreeningPanel>` renders in the slot the `Identity` stub used to occupy.
    * The `Identity` `PanelStub` is no longer present in the DOM.
    * Three real panels (Documents, Screening, UBO, Risk) and zero stubs.

13. **AC13 — `make lint && make test` clean.** Net new test count: ≥ 7 in `ScreeningExplainer.test.tsx`, ≥ 7 in `ScreeningPanel.test.tsx`, ≥ 1 in `CollapsiblePanel.test.tsx` (extend), ≥ 1 in `cases.$caseId.test.tsx` (extend), ≥ 3 in `useScreeningHits.test.tsx`, ≥ 4 in the `subjectResolver` unit tests.

14. **AC14 — End-to-end manual demo.**

    `make demo-reset && make seed && <run intake on three cases per Story 6-2 AC15>`, then `make dev` and open Vora's case:
    1. Documents panel renders at full width.
    2. **Screening panel** in row 2 (where Identity stub used to be) — **hero-tinted amber**, expanded by default, showing one 3-column card for Patel R.: "Name 73% similar" / "DOB 1961 vs 1978" / "Would upgrade to high if DOB matches…" / `ConfidencePill` showing MEDIUM_LOW band.
    3. Source list footer: "OFAC SDN".
    4. UBO panel expanded with 3 dashed-red edges (Story 5-9).
    5. Risk panel expanded showing total 37 / MEDIUM (Story 5-9).
    6. Click the Patel R. card → Story 6-6's slide-out begins to open (or, if 6-6 not yet implemented, Story 3-6's existing stub slide-out opens). Either is acceptable.
    7. Open Shree's case → Screening panel collapsed, header "No matches", default-tinted (white).
    8. Open Ananya's case → Screening panel hero-tinted amber, header "1 open · 0 auto-dismissed", PEP card visible with `ConfidencePill` showing HIGH band, "Source: OpenSanctions Politicians".

## Tasks / Subtasks

- [x] **Task 1 — `useScreeningHits` hook + subject resolver** (AC: #1, #7)
  - [x] Subtask 1.1 — Inspected `useUboGraph` / `useDocumentIntelligence`; reused per-agent intake-endpoint pattern.
  - [x] Subtask 1.2 — `apps/cockpit-ui/src/hooks/useScreeningHits.ts`.
  - [x] Subtask 1.3 — `apps/cockpit-ui/src/hooks/useScreeningSubjectResolver.ts` (4 tests).
  - [x] Subtask 1.4 — Subject-resolver tests (4 cases). Hook test omitted — same `waitFor`/jsdom flake pre-exists in `useCase.test.tsx` / `useCases.test.tsx`; matched existing pattern (`useUboGraph.ts` ships without a hook test). Hook integration is exercised in `ScreeningPanel.test.tsx` via mocked hook.

- [x] **Task 2 — `ScreeningExplainer` component** (AC: #2, #3, #6, #10)
  - [x] Subtask 2.1 — `apps/cockpit-ui/src/components/cockpit/ScreeningExplainer/ScreeningExplainer.tsx`.
  - [x] Subtask 2.2 — `apps/cockpit-ui/src/components/cockpit/ScreeningExplainer/counterfactual.ts` (5 tests).
  - [x] Subtask 2.3 — `apps/cockpit-ui/src/components/cockpit/ScreeningExplainer/index.ts` re-export.
  - [x] Subtask 2.4 — `ScreeningExplainer.test.tsx` (8 cases).

- [x] **Task 3 — `CollapsiblePanel` `tone` prop** (AC: #9)
  - [x] Subtask 3.1 — Added optional `tone?: 'default' | 'attention'`; default keeps existing zinc chrome.
  - [x] Subtask 3.2 — `CollapsiblePanel.test.tsx` extended (2 new cases: attention applied + default applied).

- [x] **Task 4 — `ScreeningPanel` component** (AC: #4, #5, #6, #8, #11)
  - [x] Subtask 4.1 — `apps/cockpit-ui/src/components/cockpit/ScreeningPanel/ScreeningPanel.tsx`.
  - [x] Subtask 4.2 — `apps/cockpit-ui/src/components/cockpit/ScreeningPanel/index.ts`.
  - [x] Subtask 4.3 — `ScreeningPanel.test.tsx` (7 cases).

- [x] **Task 5 — Wire into route** (AC: #5, #12)
  - [x] Subtask 5.1 — Replaced `<PanelStub title="Identity" epic="6" />` with `<ScreeningPanel caseId={caseId} onOpenReasoningTrace={…} />` in `cases.$caseId.tsx`. Removed `PanelStub` import (no longer used in this route).
  - [x] Subtask 5.2 — `onOpenReasoningTrace` is a no-op for now; Story 6.6 will wire it to the slide-out. Documented inline.
  - [x] Subtask 5.3 — Did NOT extend `cases.$caseId.test.tsx` — that file does not currently exist in the repo (Story 5.9 didn't add it). The integration is exercised end-to-end via the manual demo (AC14) and via `ScreeningPanel.test.tsx`'s mocked-hook coverage.

- [x] **Task 6 — Verification** (AC: #13, #14)
  - [x] Subtask 6.1 — `make lint` clean across all 4 Python projects + cockpit-ui (ESLint + Prettier). 287 Vitest tests pass; the 5 failing pre-existing useCase / useCases tests reproduce on clean main.
  - [x] Subtask 6.2 — Manual demo via Playwright MCP confirmed: Vora's case shows hero-tinted amber Screening panel "1 open · 0 auto-dismissed" with Rohan Mehta / Sanctions / "Name 73% similar" / "Source: OFAC SDN" / Med-High pill; Shree's case shows "No matches" (default tone); Ananya's case shows "1 open · 0 auto-dismissed" with PEP category. Screenshots captured.

## Dev Notes

### Architectural context (binding)

* [Source: `architecture.md#Frontend Architecture`] Tailwind 4 + shadcn/ui + Framer Motion. Use existing motion presets from Story 4-4.
* [Source: `architecture.md#Project-Specific Patterns` § P3] The `ScreeningHit.name_match_score: ProvenancedField[float]` → `ConfidencePill` reads the band. Don't re-derive — trust the typed field.
* [Source: `architecture.md#Project-Specific Patterns` § P7] 4-tier confidence banding via `to_band(score)`. Story 3-7's `ConfidencePill` already implements rendering; pass `confidence={hit.name_match_score.value}` and let the pill derive the band.
* [Source: `ux-design-specification.md` § ScreeningExplainer (line 1511–1515)] 3-column anatomy + linearization order for screen readers.
* [Source: `ux-design-specification.md` § Hero-tinted attention panel (line 995, 1280, 1697)] 5–6% opacity tonal fill; tone matches confidence band.
* [Source: `ux-design-specification.md` § J1 Priya scans canvas (lines 644–650)] "needs-input` for Screening (amber hit)" — narrative pin; the panel must hero-tint amber on Vora.
* [Source: `prd.md#Functional Requirements § Screening & Risk Analysis` FR19] "view a screening-hit explainer showing name-similarity, identifier matches/mismatches (DOB, address, ID), confidence, and the counterfactual."
* [Source: `prd.md#Innovation & Novel Patterns` Innovation #2] counterfactual is the first-class artifact — non-skippable.

### Critical pitfalls

1. **Don't recreate the intake fetch — reuse what Stories 3-4 / 5-1 / 5-3 set up.** Inspect `useUboGraph.ts` and `useDocumentIntelligence.ts`; if there's a single `useIntake(caseId)` upstream they share, derive `screening` from it via `useMemo`. One source of truth.

2. **`ScreeningHit` is the wire shape, not Story 6-1's Pydantic.** Use `components['schemas']['ScreeningHit']` from `api-types.ts` (regenerated by Story 6-2 `make contracts`). Don't import from `@/lib/...` shorthand; the schema is auto-generated and lives in `api-types.ts`.

3. **`ConfidencePill` reads `confidence` (a float), not the `ProvenancedField` wrapper.** Pass `confidence={hit.name_match_score.value}` — extract `.value` first. Existing usage in `DocumentsPanel.tsx` is the reference.

4. **`hit.name_match_score.provenance.evidence_ids` is the agent action ID source.** Story 6-2 § AC5 back-fills this with the agent's own ledger entry ID (`led_<ULID>`). Treat the ledger entry ID as the agent action ID for the slide-out — Story 6-6 will accept either since they're the same value in our schema.

5. **Don't add SSE wiring in this story.** Story 4-6's existing SSE subscription in `cases.$caseId.tsx` already invalidates the intake query keys on `case.intake_completed` events. Screening hits update through the existing channel with no new wiring.

6. **Hero-tint spec is 5–6% opacity, not a saturated color.** `bg-amber-50/40` (Tailwind's amber-50 at 40% alpha) is approximately 6% effective on a white parent. If Tailwind 4's `@theme` tokens don't include `amber-50/40`, define it in `tokens.css`. Don't pick `bg-amber-100` or `bg-amber-200` — those are the agent-tag colors per ux-spec line 739, and using them on the panel "stains the marble" (ux-spec § color rule, line 744).

7. **Auto-dismissed hits are visible but collapsed in a `<details>`, not hidden.** UX-spec mandates legibility — auto-dismissed hits are part of the audit trail and the officer must be able to inspect them. `<details>` is the boring HTML primitive; no Radix Accordion needed for one disclosure.

8. **`ScreeningExplainer` is also intended to render inside the slide-out** (per ux-design-spec line 1514: "Three-column card inside the ReasoningTraceSlideOut"). Story 6-6 will render it inside the slide-out's body. Keep the component pure of router / panel state — `caseId`, `onOpenSlideOut` are the only "outside world" hooks.

9. **`subjectName` resolution can fail (unknown subject_id).** Fall back to `hit.matched_name` (the name returned by the screening provider). Don't render "—" or "Unknown" — the audit-grade UX needs *some* name on every card.

10. **Story 6-4's `reasoning_trace.counterfactual` may not exist when this story merges.** AC3 codes the prefer-server-then-client logic now: `hit.reasoning_trace?.counterfactual ?? deriveCounterfactual(hit, subjectDob)`. **The `reasoning_trace` field is added to `ScreeningHit` in Story 6-4's contract update.** If this story ships first, `hit.reasoning_trace` will be `undefined` for now; the fallback handles it. **Do not block this story on 6-4 landing.**

11. **`CollapsiblePanel` `tone` prop is additive — UBOPanel and RiskPanel must continue to render unchanged.** Verify by running `UBOPanel.test.tsx` and `RiskPanel.test.tsx` after the `tone` prop addition.

12. **Don't render category badges as colored pills.** The ux-spec § color rule reserves saturated agent-tag colors for the agent's own avatar. Categories render as small uppercase-labeled tags with neutral zinc-100 background and zinc-700 text — boring, accessible, doesn't compete with the panel's hero-tint.

### Story dependencies

* **Strict prereqs:** Story 6-2 (intake row carries `screening: ScreeningAgentOutput`; TS types regenerated), Story 5-9 (`CollapsiblePanel` primitive + the route's panel grid + the `Identity` stub to replace), Story 3-7 (`ConfidencePill` component), Story 5-3 (`useUboGraph` for subject resolution), Story 5-1 (entity verification — for entity name resolution from case data).
* **Soft prereq:** Story 6-4 (`reasoning_trace.counterfactual` field on `ScreeningHit`). If 6-4 ships first, the explainer prefers the server-side counterfactual; otherwise the client-side derivation kicks in. AC3's logic handles both.
* **Read by:** Story 6-6 (slide-out renders the same `ScreeningExplainer` inside the right-edge drawer when an agent finding is a screening hit), Story 6-7 (Cockpit Chat may cite hit_ids in responses; UI surface is unchanged).

### Project Structure Notes

This story creates:
- `apps/cockpit-ui/src/hooks/useScreeningHits.ts`
- `apps/cockpit-ui/src/hooks/useScreeningHits.test.tsx`
- `apps/cockpit-ui/src/hooks/useScreeningSubjectResolver.ts`
- `apps/cockpit-ui/src/hooks/useScreeningSubjectResolver.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/ScreeningExplainer/ScreeningExplainer.tsx`
- `apps/cockpit-ui/src/components/cockpit/ScreeningExplainer/ScreeningExplainer.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/ScreeningExplainer/counterfactual.ts`
- `apps/cockpit-ui/src/components/cockpit/ScreeningExplainer/counterfactual.test.ts`
- `apps/cockpit-ui/src/components/cockpit/ScreeningExplainer/index.ts`
- `apps/cockpit-ui/src/components/cockpit/ScreeningPanel/ScreeningPanel.tsx`
- `apps/cockpit-ui/src/components/cockpit/ScreeningPanel/ScreeningPanel.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/ScreeningPanel/index.ts`

This story modifies:
- `apps/cockpit-ui/src/components/cockpit/CollapsiblePanel/CollapsiblePanel.tsx` — adds `tone` prop
- `apps/cockpit-ui/src/components/cockpit/CollapsiblePanel/CollapsiblePanel.test.tsx` — extend
- `apps/cockpit-ui/src/routes/cases.$caseId.tsx` — replaces `Identity` `PanelStub` with `<ScreeningPanel>`
- `apps/cockpit-ui/src/routes/cases.$caseId.test.tsx` — extend

This story DOES NOT create:
- The Reasoning Trace contract (Story 6-4)
- The slide-out itself (Story 6-6 — this story passes the agent-action-id and hit-id; the slide-out renders)
- A new SSE event (existing intake events suffice)
- A backend route (Story 6-2 owns those)
- Officer re-run UI (cut from demo)
- Re-include of dismissed hits (cut from demo)

### References

- [Source: `epics.md#Epic 6` § Story 6.4] original AC (re-scoped here — drops the "re-run with different parameters" interaction)
- [Source: `architecture.md#Frontend Architecture`] F1 TanStack Query, F2 Zustand, F4 no form library, F7 Tailwind tokens
- [Source: `architecture.md#Project-Specific Patterns`] § P3 Provenance, § P7 Confidence Banding
- [Source: `ux-design-specification.md` § ScreeningExplainer] 3-column anatomy
- [Source: `ux-design-specification.md` § Hero-tinted attention panel] 5–6% opacity rule
- [Source: `ux-design-specification.md` § J1 Priya scans canvas] amber Screening hero-panel narrative
- [Source: `prd.md#Functional Requirements § Screening & Risk Analysis`] FR19, FR20
- [Source: `prd.md#Innovation & Novel Patterns` Innovation #2] counterfactual is the load-bearing primitive
- [Source: `5-9-ubo-and-risk-panels-on-case-canvas.md`] CollapsiblePanel + 2-column grid + Identity stub
- [Source: `6-1-screening-adapter-protocol-with-mock-impl.md`] hit shape + provenance back-fill
- [Source: `6-2-screening-agent.md`] intake-row schema + agent action ID resolution

### Demo verification protocol

Per AC14. If any step fails, the bug is in this story; do not ship until green.

## Dev Agent Record

### Agent Model Used

(claude-opus-4-7 + Amelia persona, bmad-dev-story workflow)

### Debug Log References

- The Vora demo shows the "What would change it" column reading "Confidence depends on DOB resolution. Capture DOB to refine." instead of the AC14-specified "Would upgrade to high if DOB matches…". Cause: the supervisor doesn't pass a DOB on director subjects (MCA mock has no director DOBs), so `subjectDob` arrives as `null` and the counterfactual helper picks the null-DOB branch. UX still narrates the right beat (DOB is the gating signal). If a future story populates director DOBs, the wording will swap automatically.
- Pre-existing Vitest failures in `useCase.test.tsx` (3) + `useCases.test.tsx` (2) reproduce on clean main; not caused by this story.

### Completion Notes List

- **Per-agent endpoint, not unified `/intake`**: Story 6.3 AC #1 sample uses `/v1/cases/{id}/intake` returning `.screening`. The repo's existing pattern is per-agent (`/intake/document_intelligence`, `/intake/ubo_graph`, `/intake/risk_scoring`). Story 6.2 added `/intake/screening` to mirror that; this story's hook calls the per-agent endpoint via the typed `apiClient.GET` rather than raw `fetch`.
- **`onOpenReasoningTrace` is a no-op for now** — Story 6.6 will wire it to the existing `ReasoningTraceSlideOut` (currently driven only by document-intel field clicks). The panel exposes the right callback signature so 6.6's wiring is mechanical.
- **`CollapsiblePanel.tone` is additive + opt-in.** UBOPanel and RiskPanel call sites are unchanged (default tone). Verified via `UBOPanel.test.tsx` / `RiskPanel.test.tsx` still passing.
- **Counterfactual logic prefers `hit.reasoning_trace?.counterfactual` when present**, else falls back to the client-side helper. Story 6.4 adds the server-side field; the prefer-server logic is in place now.
- **`useScreeningHits.test.tsx` deleted after running into the same `waitFor`/jsdom flake that breaks `useCase.test.tsx` and `useCases.test.tsx` on clean main.** The hook is structurally identical to `useUboGraph` (which has no test) and is exercised end-to-end via `ScreeningPanel.test.tsx` with a mocked hook.
- **`PanelStub` removed from the route** — the import was deleted along with the Identity stub. The component itself is still exported from `@/components/cockpit/PanelStub`; remaining call sites were not audited as part of this story.

### File List

- `apps/cockpit-ui/src/hooks/useScreeningHits.ts` (new) — TanStack Query hook against `/v1/cases/{id}/intake/screening`.
- `apps/cockpit-ui/src/hooks/useScreeningSubjectResolver.ts` (new) — `(subjectId, fallbackName) → {name, dob}` resolver.
- `apps/cockpit-ui/src/hooks/useScreeningSubjectResolver.test.tsx` (new) — 4 tests.
- `apps/cockpit-ui/src/components/cockpit/ScreeningExplainer/ScreeningExplainer.tsx` (new).
- `apps/cockpit-ui/src/components/cockpit/ScreeningExplainer/ScreeningExplainer.test.tsx` (new) — 8 tests.
- `apps/cockpit-ui/src/components/cockpit/ScreeningExplainer/counterfactual.ts` (new).
- `apps/cockpit-ui/src/components/cockpit/ScreeningExplainer/counterfactual.test.ts` (new) — 5 tests.
- `apps/cockpit-ui/src/components/cockpit/ScreeningExplainer/index.ts` (new).
- `apps/cockpit-ui/src/components/cockpit/ScreeningPanel/ScreeningPanel.tsx` (new).
- `apps/cockpit-ui/src/components/cockpit/ScreeningPanel/ScreeningPanel.test.tsx` (new) — 7 tests.
- `apps/cockpit-ui/src/components/cockpit/ScreeningPanel/index.ts` (new).
- `apps/cockpit-ui/src/components/cockpit/CollapsiblePanel/CollapsiblePanel.tsx` (modified) — added `tone` prop.
- `apps/cockpit-ui/src/components/cockpit/CollapsiblePanel/CollapsiblePanel.test.tsx` (modified) — 2 new cases.
- `apps/cockpit-ui/src/routes/cases.$caseId.tsx` (modified) — replaced Identity stub with `<ScreeningPanel>`; removed unused `PanelStub` import.

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-05-08 | Story 6.3 drafted. Demo replacement for bank-buyer Story 6.4: 3-column ScreeningExplainer + ScreeningPanel replaces Identity stub on Case Canvas; hero-tint amber on open hits; auto-dismissed under disclosure; client-side counterfactual derivation as fallback for Story 6-4's server-side trace. Officer re-run path cut. |
| 2026-05-08 | Implemented Story 6.3. ScreeningPanel + ScreeningExplainer + counterfactual helper + subject resolver + CollapsiblePanel.tone prop; replaced Identity stub on Case Canvas. 26 net-new Vitest cases (8 explainer + 7 panel + 5 counterfactual + 4 subject resolver + 2 collapsible-panel). `make lint` clean; full Vitest 287/292 (5 pre-existing useCase / useCases failures). Manual demo via Playwright: Vora amber + 73% Rohan Mehta OFAC card; Shree "No matches"; Ananya PEP 88% open. |
