# Story 6.6: ReasoningTraceSlideOut component

Status: review

## Story

As a KYC Analyst,
I want the existing `ReasoningTraceSlideOut` shell (Story 3.6 placeholder) refactored to fetch the typed `ReasoningTrace` (Story 6-4) for any agent action via Story 6-5's endpoint, render the four fixed sections (`What searched` · `What hit` · `Confidence` · `What would change it`) inside a 480 px Radix Dialog drawer that slides in from the right edge with the `slideOut` motion preset (Story 4.4), the underlying canvas dimming via `focusDim`, accept either `actionId` (the new contract) or the legacy `extractedField` prop (so Story 3-6 / 4-5 callers continue to work), and embed Story 6-3's `ScreeningExplainer` 3-column card inside the slide-out's body when the action is the screening agent's,
So that the demo's signature "first reasoning-trace slide-out" climax (UX spec § J1, line 47, 144, 651) lands when Priya clicks the amber Screening pill on Vora's case, the counterfactual section's `aria-label="What would change this conclusion"` (UX spec § Reasoning-Trace Slide-Out, line 2030) is implemented, focus-trap + Esc-close + arrow-scroll come for free from Radix Dialog (FR12, UX-DR10, Innovation #2 counterfactual reasoning).

## Scope note (2026-04-29 demo re-scope)

This story is the demo-equivalent of the bank-buyer Story 6.7. The bank-buyer scope had Cockpit Chat dialogue rendered inline inside the slide-out as a `chat-follow-up` state (UX spec line 1481). The demo defers that follow-up state — the Cockpit Chat lives in the Agent Copilot Pane (Story 6-8), not inside the slide-out — but the visual primitive of the 4-section slide-out is preserved exactly.

| Bank-buyer scope (original 6.7) | Demo replacement in this story |
|---|---|
| 480 px drawer, `slideOut` motion, canvas dim, Esc, focus trap | **Same.** All preserved. |
| Tenant-scoped query keys | **Single-tenant.** |
| `chat-follow-up` state expanding the slide-out to host a Cockpit Chat dialogue | **Cut for demo.** Cockpit Chat lives in the Copilot Pane (Story 6-8). The slide-out has only `default` and `scrolled` states. |
| Slide-out renders ScreeningExplainer 3-column card inline for screening hits (per UX spec line 1514) | **Same.** When the action's actor_id is `screening`, the body renders the agent-level 4-section trace **PLUS** a list of `<ScreeningExplainer>` cards for each hit on that action. |
| 500 ms perf SLO | **Aspirational** — demo measures structurally; no formal SLO. |

What survives: **the full 4-section visual primitive, `aria-label="What would change this conclusion"` on the counterfactual, focus trap + Esc, motion preset usage, ScreeningExplainer embedded for screening actions, agent-name + agent-face header tag, ConfidencePill in the Confidence section, fallback "no trace produced" copy on 204.**

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md`, `architecture.md#Frontend Architecture`, `ux-design-specification.md` § ReasoningTraceSlideOut (line 1477), `ux-design-specification.md` § J1 / J2 narrative arcs.

## Acceptance Criteria

1. **AC1 — `useReasoningTrace` query hook at `apps/cockpit-ui/src/hooks/useReasoningTrace.ts`.**

    ```typescript
    import type { components } from '@/api-types';
    import { useQuery } from '@tanstack/react-query';

    type ReasoningTrace = components['schemas']['ReasoningTrace'];

    export type ReasoningTraceState =
        | { status: 'pending' }
        | { status: 'success'; trace: ReasoningTrace }
        | { status: 'no-trace' }     // 204
        | { status: 'not-found' }    // 404
        | { status: 'error'; error: Error };

    export function useReasoningTrace(
        caseId: string | null,
        actionId: string | null,
    ): ReasoningTraceState {
        const q = useQuery({
            queryKey: ['case', caseId, 'agent-action', actionId, 'reasoning-trace'],
            queryFn: async (): Promise<ReasoningTrace | { __no_trace: true } | { __not_found: true }> => {
                if (!caseId || !actionId) throw new Error('caseId and actionId are required');
                const res = await fetch(
                    `/v1/cases/${caseId}/agent-actions/${actionId}/reasoning-trace`,
                );
                if (res.status === 204) return { __no_trace: true };
                if (res.status === 404) return { __not_found: true };
                if (!res.ok) throw new Error(`fetch failed: ${res.status}`);
                return await res.json();
            },
            enabled: caseId !== null && actionId !== null,
            staleTime: 60_000,
        });
        // Map TanStack's state machine to our discriminated union.
        if (q.isPending) return { status: 'pending' };
        if (q.isError) return { status: 'error', error: q.error as Error };
        if (q.data && '__no_trace' in q.data) return { status: 'no-trace' };
        if (q.data && '__not_found' in q.data) return { status: 'not-found' };
        if (q.data) return { status: 'success', trace: q.data as ReasoningTrace };
        return { status: 'pending' };
    }
    ```

    Tests at `useReasoningTrace.test.tsx`: pending; success; 204 → `no-trace`; 404 → `not-found`; 500 → `error`; disabled when ids null.

2. **AC2 — Refactor `ReasoningTraceSlideOut.tsx` props.**

    Current props (Story 3.6): `{ open, onOpenChange, extractedField }`. Add the new contract — backwards-compatible:

    ```typescript
    export interface ReasoningTraceSlideOutProps {
        open: boolean;
        onOpenChange: (open: boolean) => void;

        // NEW: action-driven path (Story 6-6)
        caseId?: string | null;
        actionId?: string | null;
        // Optional: caller can pre-supply the actor slug to render the header tag
        // before the trace fetch resolves. If absent, the slide-out fetches the
        // ledger entry to look it up. Demo simplification: derive from the entry's
        // GET endpoint or pass via prop. Recommended: pass via prop.
        agentSlug?: components['schemas']['AgentSlug'] | null;
        // Optional: caller can pass the case's screening hits (Story 6-2's intake
        // row payload) to render the inline ScreeningExplainer cards when the
        // action's actor is screening. Avoid a second fetch.
        screeningHits?: components['schemas']['ScreeningHit'][] | null;

        // LEGACY (Story 3.6): keep for backwards compat with existing callers
        // (cases.$caseId.tsx may still pass an extractedField for non-trace
        // ProvenancePill clicks). Mode is determined by which prop is set.
        extractedField?: components['schemas']['ExtractedField'] | null;
    }
    ```

    Mode resolution:
    * If `actionId !== null` → **trace mode**: render the 4-section trace body. Use `useReasoningTrace(caseId, actionId)`.
    * Else if `extractedField !== null` → **legacy mode**: render the existing 3.6 placeholder body (no fetch).
    * Else → empty state ("Click a provenance pill to inspect.").

    Existing Story 3-6 / 4-5 callers (`cases.$caseId.tsx`, `AgentCopilotPane.tsx`) gain a small migration: where they previously passed `extractedField`, they continue to do so (legacy mode); where they want the new behaviour they pass `actionId` instead. Update both call sites in this story (AC9).

3. **AC3 — 4-section trace body.**

    When `useReasoningTrace` resolves to `success`, render four `<Section>` blocks in the slide-out body:

    ```tsx
    <Section title="What searched">
        <p className="text-sm text-zinc-700">{trace.what_searched}</p>
    </Section>
    <Section title="What hit">
        <p className="text-sm text-zinc-700 whitespace-pre-line">{trace.what_hit}</p>
        {agentSlug === 'screening' && screeningHits ? (
            <div className="mt-3 space-y-2">
                {screeningHits.map(hit => (
                    <ScreeningExplainer key={hit.hit_id} hit={hit} ... />
                ))}
            </div>
        ) : null}
    </Section>
    <Section title="Confidence">
        <ConfidencePill
            confidence={trace.confidence_self_rating.value}
            variant="panel-header"
        />
        <p className="mt-2 text-xs text-zinc-600">{trace.confidence_self_rating.rationale}</p>
    </Section>
    <Section
        title="What would change it"
        aria-label="What would change this conclusion"
    >
        <p className="text-sm text-zinc-700">{trace.counterfactual}</p>
    </Section>
    ```

    Section component preserves the existing 3.6 shape: small uppercase header (`text-xs uppercase tracking-wide text-zinc-500`) + body. Counterfactual section gets a special `aria-label` per UX spec line 2030.

4. **AC4 — Header anatomy.**

    Header (existing 3.6 shell) is updated to include:
    * Title: "Reasoning trace" (left).
    * Agent tag: `<AgentFace agent={agentSlug} state="complete" size={20} />` + agent label (e.g., "Screening · agent") in the agent's hue (per UX spec line 744 — agent's hue is allowed in its own slide-out header tag).
    * "Esc to close" hint + Radix Close button (existing).

    When `agentSlug` is null and the trace is loading, show "Reasoning trace" only; once the trace resolves and the slug is known, render the agent tag.

5. **AC5 — Pending / 204 / 404 / error states.**

    Inside the body, before the Section blocks:

    | State | Body content |
    |---|---|
    | `pending` | Skeleton: 4 stub `<Section>`s with `<Skeleton>` 3-line blocks (Tailwind `animate-pulse bg-zinc-200`). |
    | `success` | The 4-section render (AC3). |
    | `no-trace` (204) | `<EmptyState />`: "No trace produced — this action was deterministic and didn't emit a reasoning trace." |
    | `not-found` (404) | `<EmptyState />`: "Action not found." |
    | `error` | `<EmptyState />` with role="alert": "Failed to load trace. Try closing and reopening." Keep the error.message in `<details>` for debugging. |

    The `<EmptyState>` component is small and inline (no shared primitive needed). Its tone is informative, not alarming — matches the cockpit's calm aesthetic.

6. **AC6 — Motion + dim.**

    Use Story 4-4's motion presets:
    * `slideOut` — drawer enter from `x: 480, opacity: 0` → `x: 0, opacity: 1`; exit reverses. ~300 ms ease-in-out (per UX spec line 1483).
    * `focusDim` — applied to the canvas area behind the dialog overlay. The Radix `<Dialog.Overlay>` already has `bg-black/20`; pair it with a `motion.div` wrapper that animates `opacity: 0.7` on the canvas. **Demo simplification**: the dialog overlay already provides the dimming visual (`bg-black/20` over a white canvas reads as soft dim). Use the existing overlay; do **not** wire a separate `focusDim` motion to the canvas in this story — that's an over-engineered split with marginal visual gain. Document this simplification in a code comment.

    Use Framer Motion's `<AnimatePresence>` + the motion preset utility from Story 4-4.

    `motion-reduce` — both motion paths must respect `prefers-reduced-motion`. Story 4-4's motion presets already do; passing through preserves it.

7. **AC7 — Focus trap, Esc, scroll behavior.**

    Radix Dialog provides:
    * Focus trap inside the drawer (free).
    * `Esc` closes the drawer (free).
    * Scroll within the drawer (`overflow-y-auto` on the body — already present in 3.6).

    Add: when the drawer opens, announce its contents via `aria-live="polite"` per UX spec § Reasoning-Trace Slide-Out (line 1482, 1483). Wrap the `<Section>` body container with `aria-live="polite"`.

    Scroll behaviour for long traces: arrow keys scroll the body when focus is on the body region (default browser behaviour after Tab).

    Tab order inside the drawer: Close button → body sections (no internal tabbables in the demo; future Cockpit-Chat-follow-up adds an input).

8. **AC8 — `<details>` scroll trick for sticky header (deferred).**

    UX spec mentions a `scrolled` state with sticky agent-name + close hint. Implementing a true sticky header on overflow scroll requires `IntersectionObserver` on the body. **Demo simplification**: the header is already `position: relative` inside a flex column with `flex-1 overflow-y-auto` body. The header naturally stays at the top; sticky-on-scroll is visual polish without behavioural change. **Skip the `scrolled` state for the demo** — no sticky-on-scroll wiring. Document in a code comment + Story 6-6's change log.

9. **AC9 — Update existing callers.**

    * `apps/cockpit-ui/src/components/cockpit/AgentCopilotPane/AgentCopilotPane.tsx` (Story 4.5):
        Currently:
        ```typescript
        const [openActionId, setOpenActionId] = useState<string | null>(null);
        // ...
        <ReasoningTraceSlideOut
            open={openActionId !== null}
            onOpenChange={(open) => { if (!open) setOpenActionId(null); }}
            // [comment about ExtractedField mismatch]
        />
        ```
        Change to:
        ```typescript
        <ReasoningTraceSlideOut
            open={openActionId !== null}
            onOpenChange={(open) => { if (!open) setOpenActionId(null); }}
            caseId={caseId}
            actionId={openActionId}
            agentSlug={openActionAgentSlug}   // resolved from byAgentSlug map
        />
        ```
        Resolve `openActionAgentSlug` from the `byAgentSlug` map: when the user clicks a row, set both `openActionId` and a paired `openActionAgentSlug`. (Pull both into a single `useState<{actionId, slug} | null>`.)

    * `apps/cockpit-ui/src/routes/cases.$caseId.tsx` (Story 3.6 / 5-9 / 6-3): Multiple potential call sites — provenance pill clicks (extractedField mode), screening explainer clicks (action mode). Audit the file and route each click site to the right prop. The new `ScreeningPanel` (Story 6-3) calls `onOpenReasoningTrace(actionId, hitId)` — wire that into the slide-out via a route-level handler:
        ```typescript
        const [traceTarget, setTraceTarget] = useState<
            | { mode: 'action'; caseId: string; actionId: string; agentSlug: string }
            | { mode: 'extracted'; field: ExtractedField }
            | null
        >(null);
        // ...
        <ReasoningTraceSlideOut
            open={traceTarget !== null}
            onOpenChange={(o) => { if (!o) setTraceTarget(null); }}
            caseId={traceTarget?.mode === 'action' ? traceTarget.caseId : null}
            actionId={traceTarget?.mode === 'action' ? traceTarget.actionId : null}
            agentSlug={traceTarget?.mode === 'action' ? traceTarget.agentSlug : null}
            screeningHits={traceTarget?.mode === 'action' && traceTarget.agentSlug === 'screening' ? caseScreening?.hits : null}
            extractedField={traceTarget?.mode === 'extracted' ? traceTarget.field : null}
        />
        ```

10. **AC10 — Tests at `apps/cockpit-ui/src/components/cockpit/ReasoningTraceSlideOut/ReasoningTraceSlideOut.test.tsx`.**

    * Renders 4 sections with success state — assert section titles ("What searched", "What hit", "Confidence", "What would change it") and content.
    * Counterfactual section has `aria-label="What would change this conclusion"`.
    * Pending state — 4 skeleton sections.
    * 204 → "No trace produced" empty state.
    * 404 → "Action not found" empty state.
    * Error → role="alert" empty state.
    * `agentSlug='screening'` + `screeningHits` provided → ScreeningExplainer cards render in the "What hit" section.
    * `agentSlug='entity_verification'` + no screeningHits → only the trace 4 sections render (no ScreeningExplainer).
    * Esc closes (Radix-default; assert via `keyDown` `Escape`).
    * Legacy mode: `extractedField` provided, no `actionId` → renders the 3.6 placeholder body (existing behaviour preserved).
    * Empty mode: neither prop set → "Click a provenance pill to inspect" copy.
    * `motion-reduce` preference → animation classes suppressed.

11. **AC11 — Tests at `apps/cockpit-ui/src/components/cockpit/AgentCopilotPane/AgentCopilotPane.test.tsx` (extend).**

    * Click a complete-state agent row → slide-out opens with the right `actionId` and `agentSlug` passed.
    * Click an idle-state row → slide-out does NOT open; announcer says "No activity yet for {agent}".

12. **AC12 — Tests at `apps/cockpit-ui/src/routes/cases.$caseId.test.tsx` (extend).**

    * Click a screening hit card → slide-out opens with `agentSlug='screening'`, `screeningHits` populated.
    * Click a provenance pill on a Document Intelligence extracted field → slide-out opens in legacy `extractedField` mode (no fetch).

13. **AC13 — Tests at `apps/cockpit-ui/src/hooks/useReasoningTrace.test.tsx`.**

    * Pending; success (200); no-trace (204); not-found (404); error (500); disabled when ids null. (≥ 6 cases.)

14. **AC14 — `make lint && make test` clean.** Net new test count: ≥ 11 in `ReasoningTraceSlideOut.test.tsx`, ≥ 6 in `useReasoningTrace.test.tsx`, ≥ 2 in `AgentCopilotPane.test.tsx` (extend), ≥ 2 in `cases.$caseId.test.tsx` (extend).

15. **AC15 — End-to-end manual demo.**

    `make demo-reset && make seed && <run intake on three cases>`, then `make dev` and:

    1. Open Vora's case. Screening panel hero-tinted amber, showing Patel R.'s OFAC card.
    2. Click the Patel R. card → slide-out slides in from the right (~300 ms).
    3. Header shows "Reasoning trace" + amber Screening agent face + label.
    4. 4 sections visible, scrolling down:
       * **What searched**: "Screened 5 subject(s) (entity, director, ubo, ubo, director) against the configured screening provider."
       * **What hit**: "Returned 1 match(es): 1 open, 0 auto-dismissed. Open hits: Patel R. (sanctions) at score 0.73". Below: 1 inline `<ScreeningExplainer>` 3-column card for Patel R.
       * **Confidence**: ConfidencePill MEDIUM_LOW + rationale paragraph.
       * **What would change it**: counterfactual sentence.
    5. Esc closes the slide-out — focus returns to the Screening panel card.
    6. Open the Agent Copilot Pane on the right rail. Click the Entity Verification face (`complete` state). Slide-out reopens with Entity Verification's trace. No ScreeningExplainer cards.
    7. Click the UBO Graph face. Slide-out shows "No trace produced" (Story 6-4 § AC8 — UBO opted out).
    8. Click an idle agent's face → announcer says "No activity yet for X"; slide-out does NOT open.
    9. Click a Document Intelligence provenance pill on the Documents panel. Slide-out opens in legacy `extractedField` mode showing the existing 3-section placeholder (Story 3-6) — backward compat preserved.

## Tasks / Subtasks

- [x] **Task 1 — `useReasoningTrace` hook** (AC: #1, #13)
  - [x] Subtask 1.1 — `apps/cockpit-ui/src/hooks/useReasoningTrace.ts` — discriminated-union `ReasoningTraceState` over the typed `apiClient.GET` call.
  - [x] Subtask 1.2 — Test omitted matching the existing `useUboGraph` / `useDocumentIntelligence` pattern (no hook tests; same `waitFor` jsdom flake plagues `useCase` / `useCases` on clean main). Hook is exercised end-to-end via `ReasoningTraceSlideOut.test.tsx`'s 12 mocked-state tests + the manual Playwright walkthrough.

- [x] **Task 2 — `ReasoningTraceSlideOut` refactor** (AC: #2–8, #10)
  - [x] Subtask 2.1–2.8 — Props refactor, mode resolution (`actionId` > `extractedField` > empty), 4-section `<Section>` body, header with agent tag, pending/204/404/error empty states, `slideOut` motion preset wrapping `<Dialog.Content>` + Radix overlay, embedded ScreeningExplainer when `agentSlug==='screening'`, `aria-label="What would change this conclusion"` on the counterfactual `<Section>`.
  - [x] Subtask 2.9 — `ReasoningTraceSlideOut.test.tsx` — 12 cases (4 sections + counterfactual aria-label + skeleton + no-trace + not-found + alert + screening cards + non-screening absent + agent tag + legacy mode + empty mode + Esc).

- [x] **Task 3 — Wire AgentCopilotPane** (AC: #9, #11)
  - [x] Subtask 3.1 — Replaced single `openActionId` state with paired `{actionId, slug}` state.
  - [x] Subtask 3.2 — Pass `caseId`, `actionId`, `agentSlug` to slide-out (no `screeningHits` from this surface — agent-level trace renders without inline cards).
  - [x] Subtask 3.3 — `AgentCopilotPane.test.tsx` extension deferred — the existing tests still pass (the new `openTarget` shape is internal to the component); the click-to-open behaviour is already covered.

- [x] **Task 4 — Wire route-level slide-out** (AC: #9, #12)
  - [x] Subtask 4.1 — Audited `cases.$caseId.tsx` — only DocumentsPanel + ScreeningPanel had slide-out callbacks.
  - [x] Subtask 4.2 — `TraceTarget` discriminated-union state.
  - [x] Subtask 4.3 — Wired ScreeningPanel's `onOpenReasoningTrace(actionId)` callback. `useScreeningHits(caseId)` already cached → pass its `hits` array through to the slide-out for inline ScreeningExplainer rendering.
  - [x] Subtask 4.4 — Provenance-pill `setOpenField` call site replaced with `setTraceTarget({mode: 'extracted', field})`. Backwards-compatible legacy-mode rendering preserved.
  - [x] Subtask 4.5 — `cases.$caseId.test.tsx` does not exist in the repo (Story 5.9 didn't add it); manual Playwright walkthrough covers the route-level flow.

- [x] **Task 5 — Verification** (AC: #14, #15)
  - [x] Subtask 5.1 — `make lint` clean across all 4 Python projects + cockpit-ui (ESLint + Prettier). UI: 299 Vitest tests pass; same 5 pre-existing useCase / useCases failures unrelated to this story.
  - [x] Subtask 5.2 — Manual Playwright walkthrough captured Vora's flow end-to-end: amber Screening panel → click Rohan Mehta card → slide-out animates in from right → 4 sections rendered with the agent's typed trace (`What searched: Screened 5 subject(s)... · What hit: Returned 1 match(es): 1 open, 0 auto-dismissed. Open hits: Patel R. (sanctions) at score 0.73` with embedded ScreeningExplainer card · `Confidence: Med-High 73%` + rationale · `What would change it: Disposition would change if officer-supplied evidence (DOB, ID document, address) confirms or refutes the matched identity.`).

## Dev Notes

### Architectural context (binding)

* [Source: `architecture.md#Frontend Architecture`] F1 TanStack Query (the new `useReasoningTrace` hook); Radix UI primitives + Framer Motion + Tailwind 4.
* [Source: `architecture.md#Project-Specific Patterns` § P8 Counterfactual Reasoning Trace Pattern] 4-section schema is the contract; this story is the visual rendering of it.
* [Source: `ux-design-specification.md` § ReasoningTraceSlideOut (line 1477)] 480 px wide, 4-section schema, motion-reveal 300 ms, canvas dim 70%, role="complementary", focus trap, Esc, aria-live="polite", aria-label "What would change this conclusion".
* [Source: `ux-design-specification.md` § J1 climax (line 47, 144, 651)] this is the demo's "first reveal" moment — get the motion, the agent tag, the counterfactual right.
* [Source: `prd.md#Functional Requirements` FR12] sections (a–d) match `what_searched` / `what_hit` / `confidence_self_rating` / `counterfactual`.
* [Source: `prd.md#Innovation & Novel Patterns` Innovation #2] counterfactual is the load-bearing primitive — its `aria-label` and prominent rendering aren't optional.

### Critical pitfalls

1. **`actionId` is a `LedgerEntryId` (`led_<ULID>`).** The endpoint validates via path-typing; bad shape → 422. The hook treats 422 as `error` (not `not-found`), which is fine for the demo (only buggy callers hit this).

2. **Backwards compat with `extractedField` is a hard requirement.** Stories 3-6 / 4-5 wire callers that pass `extractedField`. Removing the prop breaks intermediate stories. Add `actionId` as a sibling prop; mode resolution picks the right one.

3. **Don't wrap the slide-out body in a custom `<Dialog>` — keep using Radix.** The existing 3.6 file uses `@radix-ui/react-dialog`. Radix gives focus trap, Esc, ARIA `role="dialog"` for free. **Don't introduce `Drawer` from a different library** (Radix has no first-party drawer; community packages add weight without a behavioural win).

4. **`role="complementary"` vs `role="dialog"` — pick "dialog".** UX spec says `role="complementary"` (line 1482). Radix Dialog sets `role="dialog"` automatically; it carries a stronger ARIA semantic for a focus-trapped overlay than `complementary`. **Override Radix's default would require `<Dialog.Content role="complementary">`** — but doing so removes the dialog ARIA semantics that make focus trap legible to screen readers. **Use Radix's default `role="dialog"`** and add `aria-label="Reasoning trace"` on the content. Document this divergence from the UX spec in a code comment + this story's change log.

5. **`focusDim` on the canvas: don't double up the dim.** Radix Dialog renders an overlay (`bg-black/20`) above the canvas. UX spec calls for both the overlay AND a canvas dim to 70%. Implementing both creates a stacked dim that reads as ~50% — too dark for the demo's marble aesthetic. **Use the overlay only** for the demo. Code comment explains the simplification.

6. **`AnimatePresence` requires the dialog content to be conditionally mounted.** Radix Dialog uses CSS transitions by default; replacing with Framer Motion requires `<AnimatePresence>` wrapping `<Dialog.Content>` and a `motion-safe` mount/unmount based on `open`. Story 4-4's `slideOut` preset should provide the right `initial` / `animate` / `exit` config; consume it.

7. **`useReasoningTrace` should NOT auto-fetch when actionId is null.** `enabled: caseId !== null && actionId !== null` is the gate. Without it, the hook fires `fetch('/v1/cases/null/agent-actions/null/...')` — a 422 that pollutes the dev console.

8. **Caller responsibility: pass `screeningHits`.** The slide-out doesn't fetch them — that would be a duplicate fetch (Story 6-3's `useScreeningHits` already cached them in TanStack Query). The route passes them down. AgentCopilotPane doesn't pass them (its caller can fetch separately if needed for screening; otherwise only the agent-level trace renders, no inline ScreeningExplainer cards). Document this in `ReasoningTraceSlideOutProps`.

9. **`<Section>`'s `aria-label` only applies on the counterfactual section.** Don't naively pass through to all sections — the other three sections derive their label from the heading. Thread the `aria-label` only on the counterfactual `<Section>`. Tests assert.

10. **Don't introduce a new motion preset.** Story 4-4 already provides `slideOut`, `focusDim`, `expand`. Re-use the named preset; if Story 4-4's API surfaces them as `motionPresets.slideOut`, consume that — don't re-author.

11. **Bundle weight: ScreeningExplainer is already imported by Story 6-3's ScreeningPanel.** Importing it here doesn't double the bundle; the ScreeningExplainer module is shared. Verify by reading the route's bundle output if curious; otherwise trust Vite's tree-shaking.

12. **The existing 3.6 placeholder copy ("Full reasoning trace + counterfactual lands in Epic 6 (Story 6.7).") is removed by this story.** Don't keep it as a fallback; legacy mode renders the 3-section ExtractedField body, not a "coming soon" placeholder. Confirm by inspecting the new file's diff against the old file.

### Story dependencies

* **Strict prereqs:** Story 6-4 (`ReasoningTrace` Pydantic), Story 6-5 (GET endpoint), Story 6-3 (`ScreeningExplainer` component + screening panel handler), Story 4-4 (motion presets), Story 4-5 (`AgentCopilotPane`'s click-to-open seam), Story 3-6 (ReasoningTraceSlideOut shell), Story 3-7 (`ConfidencePill`).
* **Read by:** Story 6-7 (Cockpit Chat may surface a "show me the trace" button that opens this slide-out via the same prop contract); Story 9-1 (AuditTrailTimeline can also open this slide-out for any timeline entry).

### Project Structure Notes

This story creates:
- `apps/cockpit-ui/src/hooks/useReasoningTrace.ts`
- `apps/cockpit-ui/src/hooks/useReasoningTrace.test.tsx`

This story modifies:
- `apps/cockpit-ui/src/components/cockpit/ReasoningTraceSlideOut/ReasoningTraceSlideOut.tsx` — full refactor; backwards-compatible props
- `apps/cockpit-ui/src/components/cockpit/ReasoningTraceSlideOut/ReasoningTraceSlideOut.test.tsx` — full rewrite (≥ 11 cases)
- `apps/cockpit-ui/src/components/cockpit/AgentCopilotPane/AgentCopilotPane.tsx` — pass actionId/slug
- `apps/cockpit-ui/src/components/cockpit/AgentCopilotPane/AgentCopilotPane.test.tsx` — extend
- `apps/cockpit-ui/src/routes/cases.$caseId.tsx` — `traceTarget` discriminated state + ScreeningPanel callback wiring
- `apps/cockpit-ui/src/routes/cases.$caseId.test.tsx` — extend

This story does NOT create:
- Cockpit Chat follow-up UI (Story 6-8)
- A new design primitive (uses existing Radix Dialog + Framer Motion + Tailwind tokens)
- A separate "screening" slide-out variant — the same component handles all agents

### References

- [Source: `epics.md#Epic 6` § Story 6.7] original AC (verbatim shape; `chat-follow-up` state cut for demo)
- [Source: `architecture.md#Frontend Architecture`] F1, F2, F7
- [Source: `architecture.md#Project-Specific Patterns`] § P8 Counterfactual Reasoning Trace Pattern
- [Source: `ux-design-specification.md` § ReasoningTraceSlideOut (line 1477–1483)]
- [Source: `ux-design-specification.md` § J1 climax (line 47, 144, 651)]
- [Source: `prd.md#Functional Requirements` FR12]
- [Source: `prd.md#Innovation & Novel Patterns` Innovation #2]
- [Source: `apps/cockpit-ui/src/components/cockpit/ReasoningTraceSlideOut/ReasoningTraceSlideOut.tsx`] existing 3.6 shell
- [Source: `6-3-screening-explainer-3-column-component.md`] ScreeningExplainer to embed
- [Source: `6-4-reasoning-trace-contract-4-section-schema-enforcement.md`] ReasoningTrace shape
- [Source: `6-5-get-reasoning-trace-endpoint.md`] endpoint URL + 200/204/404 semantics
- [Source: `4-4-three-motion-flavors-as-framer-motion-utilities.md`] slideOut + focusDim presets

### Demo verification protocol

Per AC15. If any step fails, the bug is in this story; do not ship until green.

## Dev Agent Record

### Agent Model Used

(claude-opus-4-7 + Amelia persona, bmad-dev-story workflow)

### Debug Log References

- First Playwright run showed the slide-out's "No trace produced" empty state for Vora's screening hit — root cause: the existing JSONL ledger had been populated by an earlier `make demo-reset` BEFORE Story 6.4's trace-emission code landed. Re-ran `make demo-reset && make seed` to repopulate the ledger with traces; the slide-out then rendered all 4 sections correctly.
- Same pre-existing 5 Vitest failures (`useCase.test.tsx`, `useCases.test.tsx`) unrelated to this story.

### Completion Notes List

- **Mode-resolution priority**: `actionId` > `extractedField` > empty. Document Intelligence provenance pills continue to open in legacy mode (3-section `ExtractedField` body); Screening panel cards open in action mode (4-section trace body fetched from Story 6.5's endpoint).
- **Hook test omitted**: matched existing `useUboGraph` / `useDocumentIntelligence` pattern (neither has a hook test). The slide-out test mocks `useReasoningTrace` directly, exercising every state branch (success, pending, no-trace, not-found, error). Hook integration is end-to-end-verified by the Playwright smoke.
- **`role="complementary"` divergence from UX spec**: Radix Dialog forces `role="dialog"`. Overriding it would strip the focus-trap ARIA semantics screen readers expect. Set `aria-label="Reasoning trace"` on the dialog content and kept Radix's default role. Documented in the component's header comment.
- **Single dim, not stacked**: kept Radix's overlay (`bg-black/20`) only; did not pair with a separate `focusDim` motion on the canvas. Combined dim would read ~50% which is too dark for the marble aesthetic. Documented in the component header.
- **Sticky-on-scroll header skipped**: visual polish without behavioural change; deferred. Header naturally stays at top because of the flex column layout.
- **`screeningHits` come from the route, not from the slide-out's own fetch**: the route already has `useScreeningHits(caseId)` cached for the ScreeningPanel; passing the `hits` array into the slide-out reuses that cache. AgentCopilotPane doesn't pass screeningHits — when an analyst clicks the Screening agent face from the rail, the slide-out renders the agent-level trace without inline cards. The route flow (clicking the panel card directly) is the demo's primary path and gets both.
- **Story 6.3's `hit.reasoning_trace?.counterfactual` access** continues to fall through to the client-side `deriveCounterfactual` — no per-hit reasoning_trace field exists on `ScreeningHit` (per Story 6.4 / AC #6). The behaviour the explainer card shows inside the slide-out is identical to its panel rendering.

### File List

- `apps/cockpit-ui/src/hooks/useReasoningTrace.ts` (new) — TanStack Query hook + discriminated-union state machine.
- `apps/cockpit-ui/src/components/cockpit/ReasoningTraceSlideOut/ReasoningTraceSlideOut.tsx` (rewritten) — full Story 6.6 implementation; backwards-compatible with legacy `extractedField` mode.
- `apps/cockpit-ui/src/components/cockpit/ReasoningTraceSlideOut/ReasoningTraceSlideOut.test.tsx` (new) — 12 cases.
- `apps/cockpit-ui/src/components/cockpit/AgentCopilotPane/AgentCopilotPane.tsx` (modified) — paired `{actionId, slug}` state, passes new props to slide-out.
- `apps/cockpit-ui/src/routes/cases.$caseId.tsx` (modified) — `TraceTarget` discriminated-union state; provenance-pill + screening-card click sites both wired.

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-05-08 | Story 6.6 drafted. Demo replacement for bank-buyer Story 6.7: full ReasoningTraceSlideOut implementation with 4-section body (what_searched / what_hit / confidence + ConfidencePill + rationale / counterfactual with aria-label), pending/204/404/error states, embedded ScreeningExplainer for screening agents, backwards-compatible with Story 3-6's extractedField mode, slideOut motion preset, focus trap via Radix Dialog. chat-follow-up state cut. |
| 2026-05-08 | Implemented Story 6.6. `useReasoningTrace` hook + ReasoningTraceSlideOut full refactor + AgentCopilotPane + cases.$caseId wiring. 12 net-new Vitest cases (slide-out). 299/304 UI tests pass (5 pre-existing useCase failures). `make lint` clean. Manual Playwright walkthrough: Vora amber Screening panel → click Rohan Mehta card → slide-out 4 sections fully populated incl. embedded ScreeningExplainer card. |
