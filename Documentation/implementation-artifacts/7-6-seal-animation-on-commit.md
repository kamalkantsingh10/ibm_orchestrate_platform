# Story 7.6: Seal animation on commit

Status: review

## Story

As a KYC Analyst,
I want a 400 ms ease-out "seal" animation that plays on the Decision Zone when the case state transitions to `committed` (driven by Story 7-4's timer expiry SSE event `decision.sealed`) — a subtle vertical settle + opacity flash on the rationale text + a circular wax-seal-style indicator stamping into place near the Commit button — followed by the UndoPill (Story 7-5) fading out and a "Sealed (`led_<ULID>`)" indicator taking its place inline in the Decision Zone footer,
So that the demo's J1 commit beat reaches its narrative climax ("she watches the seal stamp into place"), the decision feels weighty without theatrics (UX-DR28), and Path B reviewers see a moment of motion-design polish that reinforces the "Decisions are sacred" principle (FR24, UX-DR28).

## Scope note (2026-04-29 demo re-scope)

Story preserved verbatim from bank-buyer Story 7.10 — the visual primitive is the load-bearing demo polish that earns its keep.

| Bank-buyer scope (original 7.10) | Demo replacement |
|---|---|
| 400 ms ease-out seal animation on Decision Zone | **Same.** Framer Motion driven by SSE event. |
| UndoPill fades; "Sealed" indicator with ledger entry ID replaces it | **Same** — but the indicator lives in Decision Zone's footer (not the pill location), since the pill is a viewport-pinned element. |
| Tiptap becomes read-only | **Already handled by Story 7-1's `editable` prop conditional on `case.state === 'committed'`.** This story just verifies the trigger flows correctly. |

What survives: **the entire visual primitive — vertical settle, opacity flash, wax-seal indicator, UndoPill fade, "Sealed (led_…)" inline indicator, ledger-id linkable to slide-out.**

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md`, `architecture.md#Frontend Architecture`, `ux-design-specification.md` § Seal animation (line 1290), `prd.md#Functional Requirements` FR24.

## Acceptance Criteria

1. **AC1 — `useSealAnimation(caseId)` hook at `apps/cockpit-ui/src/hooks/useSealAnimation.ts`.**

    ```typescript
    type SealState = { phase: 'idle' } | { phase: 'sealing'; ledgerEntryId: string } | { phase: 'sealed'; ledgerEntryId: string };

    export function useSealAnimation(caseId: string): SealState { ... }
    ```

    Logic:
    * Subscribe to the case's SSE channel; listen for `decision.sealed` events with matching `case_id`.
    * On event arrival → set `{ phase: 'sealing', ledgerEntryId: data.ledger_entry_id }`.
    * After 400 ms → set `{ phase: 'sealed', ledgerEntryId }`.
    * On case state ≠ `committed` (e.g., the case re-enters `decision_ready` for re-evaluation in some Future workflow) → reset to `idle`.

    The 'sealing' phase is the animation window; the component reads it to drive Framer Motion variants. The 'sealed' phase is the steady state where the inline indicator persists.

2. **AC2 — Decision Zone "sealing" Framer variants.**

    Extend `DecisionZone.tsx`:

    ```typescript
    const sealState = useSealAnimation(caseId);
    // ... derive isSealing = sealState.phase === 'sealing';

    <motion.section
        ref={containerRef}
        animate={isSealing ? 'sealing' : 'idle'}
        variants={{
            idle: { y: 0, scale: 1 },
            sealing: {
                y: [0, -2, 0],         // tiny lift then settle
                scale: [1, 0.998, 1],  // imperceptible squeeze
                transition: { duration: 0.4, ease: [0.4, 0, 0.2, 1] },
            },
        }}
        ...
    >
    ```

    Body opacity flash:

    ```tsx
    <motion.div
        className="editor-body ..."
        animate={isSealing ? { opacity: [1, 0.7, 1] } : { opacity: 1 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
    >
        <Tiptap editor />
    </motion.div>
    ```

    The whole effect is "the page exhales when the seal lands." Subtle — UX-DR28 calls it "weighty without theatrics".

3. **AC3 — Wax-seal indicator (the visible "stamp").**

    A small circular SVG element, ~40px diameter, that appears near the Commit button position (now hidden because case is sealed) with a stamp animation:

    ```tsx
    <AnimatePresence>
        {sealState.phase === 'sealing' && (
            <motion.div
                key="seal-stamp"
                className="absolute right-6 bottom-3 pointer-events-none"
                initial={{ scale: 1.6, opacity: 0, rotate: -8 }}
                animate={{ scale: 1, opacity: 1, rotate: 0 }}
                exit={{ scale: 1.05, opacity: 0 }}
                transition={{ duration: 0.4, ease: [0.34, 1.56, 0.64, 1] }}   // overshoot ease
            >
                <SealIcon />
            </motion.div>
        )}
        {sealState.phase === 'sealed' && (
            <motion.div
                key="seal-indicator"
                className="absolute right-6 bottom-3"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
            >
                <SealedIndicator ledgerEntryId={sealState.ledgerEntryId} />
            </motion.div>
        )}
    </AnimatePresence>
    ```

    `SealIcon` — a styled SVG. Demo simplification: a circle with a center dot + ring. Visual weight via `fill-amber-700 ring-amber-900` (warm wax tone). Custom-drawn:

    ```tsx
    function SealIcon() {
        return (
            <svg viewBox="0 0 40 40" width="40" height="40" aria-hidden="true">
                <circle cx="20" cy="20" r="18" className="fill-amber-700/90 stroke-amber-900 stroke-1" />
                <circle cx="20" cy="20" r="12" className="fill-none stroke-amber-100/40 stroke-1" />
                <text x="20" y="20" textAnchor="middle" dominantBaseline="central" className="fill-amber-100 text-[10px] font-serif font-semibold">SEAL</text>
            </svg>
        );
    }
    ```

    Don't pursue photorealistic wax — the demo's marble aesthetic prefers iconographic over realistic.

4. **AC4 — `SealedIndicator` inline component.**

    `apps/cockpit-ui/src/components/cockpit/DecisionZone/SealedIndicator.tsx`:

    ```tsx
    interface SealedIndicatorProps {
        ledgerEntryId: string;
    }

    export function SealedIndicator({ ledgerEntryId }: SealedIndicatorProps) {
        return (
            <button
                type="button"
                onClick={() => window.dispatchEvent(new CustomEvent('cockpit:open-trace', { detail: ledgerEntryId }))}
                className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-amber-50 ring-1 ring-amber-200 text-xs font-medium text-amber-900 hover:bg-amber-100 focus-visible:ring-2 focus-visible:ring-amber-500"
            >
                <span aria-hidden>●</span>
                <span>Sealed</span>
                <code className="font-mono text-[10px] text-amber-800">{ledgerEntryId.slice(0, 12)}…</code>
            </button>
        );
    }
    ```

    Click opens Story 6-6's reasoning trace slide-out via the same custom-event channel that Decision Zone's citation-token clicks use (Story 7-1 § AC10).

    Mounted by `DecisionZone.tsx` in the footer when `case.state === 'committed'` AND `sealState.phase === 'sealed'` (or just `case.state === 'committed'` for persistence across page reloads — the `phase: 'sealed'` is animation-driven, not state-driven; on page reload, the case is committed but `useSealAnimation` returns idle. Add the indicator render condition to be **`case.state === 'committed'` AND `caseDecision?.ledgerEntryId`** — the decision's seal ledger entry id is read from the case's intake/decision row).

    Resolve `ledgerEntryId` via `useCase(caseId)`'s envelope OR a small new hook that reads the most recent `decision.sealed` ledger entry id for the case via Story 6-7's `GET /v1/cases/{id}/ledger?actor_id=platform&event_type=decision.sealed` filter. **Pick the simpler path**: extend `useCase`'s response (Story 2-2's case envelope) to include `latest_decision: {decision_id, sealed_ledger_entry_id, outcome} | null` — populated by the case repo on read. This is a small backend addition (separate AC).

5. **AC5 — Backend: `case.latest_decision` envelope addition.**

    Extend `Case` Pydantic in `packages/contracts/src/contracts/cases.py` with a non-frozen sibling response shape (or extend the existing `Case` if non-disruptive):

    ```python
    class CaseLatestDecision(BaseModel):
        model_config = {"frozen": True}
        decision_id: str
        outcome: Literal["approve", "decline", "approve_with_conditions", "escalate_to_edd"]   # mirrors Story 7-9
        sealed_ledger_entry_id: LedgerEntryId | None     # None during pending_seal; populated on seal
    ```

    The `Case` envelope's response (`GET /v1/cases/{case_id}`) gains an optional `latest_decision: CaseLatestDecision | None` field. The cockpit-api's case router populates it by reading the most recent decision row for the case (Story 7-7 owns the `decisions` table; this story extends the envelope to surface it).

    **Implementation surface**: a small `case_service.fetch_case_envelope(...)` helper that joins the case row with the latest decision row and the most recent `decision.sealed` ledger entry. Don't bake this into `Case` itself (keep `Case` as the persistence model); add it as the route's response shape.

    **If Story 7-7 hasn't landed yet**, default `latest_decision: None`. The cockpit-ui's `useSealAnimation` falls back to listening to SSE only.

6. **AC6 — UndoPill fade out on seal.**

    Story 7-5's `useDecisionTimer` already flips to `no-timer` on the `decision.sealed` SSE event. The UndoPill auto-unmounts. **For the visual coordination**, wrap the UndoPill in `<AnimatePresence>` at the route level so unmount is animated (fade + scale-down):

    ```tsx
    <AnimatePresence>
        {timer.status === 'active' && (
            <motion.div
                key="undo-pill"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 10, scale: 0.95 }}
                transition={{ duration: 0.3 }}
            >
                <UndoPill caseId={caseId} />
            </motion.div>
        )}
    </AnimatePresence>
    ```

    Mounted in `cases.$caseId.tsx` (replaces the existing `<UndoPill>` mount from Story 7-5 — coordinate via this story's PR).

    The pill exits as the seal stamp enters → ~700 ms total choreography (300ms pill exit overlapping with 400ms seal in).

7. **AC7 — `prefers-reduced-motion` respect.**

    All animations honor `motion-reduce`:
    * Decision Zone's `motion.section` variants → no transform; instant state.
    * Body opacity flash → no transition; stays at 1.
    * Seal stamp → fades in/out only (no scale/rotate); 0ms duration.
    * UndoPill exit → instant unmount.

    Framer Motion's `useReducedMotion` hook drives the variant override:

    ```typescript
    import { useReducedMotion } from 'framer-motion';
    const reduce = useReducedMotion();
    const sealVariants = reduce ? { idle: {}, sealing: {} } : { idle: {...}, sealing: {...} };
    ```

8. **AC8 — Tests at `apps/cockpit-ui/src/hooks/useSealAnimation.test.tsx`.**

    * Returns `idle` initially.
    * On SSE `decision.sealed` event with matching case_id → flips to `sealing`.
    * After 400ms → flips to `sealed` (use `vi.useFakeTimers`).
    * Non-matching case_id is ignored.
    * Returns to `idle` on case state changing to non-committed (defensive).

9. **AC9 — Tests at `apps/cockpit-ui/src/components/cockpit/DecisionZone/DecisionZone.test.tsx` (extend).**

    * Default state: no seal stamp, no SealedIndicator.
    * `useSealAnimation` returns `sealing` → seal stamp renders, body opacity animation prop set.
    * `useSealAnimation` returns `sealed` AND `case.state === 'committed'` → SealedIndicator renders with truncated ledger ID.
    * Click on SealedIndicator → custom event `cockpit:open-trace` dispatched with the full ledger entry id.
    * `prefers-reduced-motion` → variant collapses to no-op (assert via mock).

10. **AC10 — Tests at `apps/cockpit-ui/src/components/cockpit/DecisionZone/SealedIndicator.test.tsx`.**

    * Renders truncated ledger ID + "Sealed" label.
    * Click dispatches custom event.
    * Keyboard: Tab focuses; Enter/Space activates.

11. **AC11 — Tests at `apps/cockpit-api/tests/test_cases_router.py` (extend).**

    * `GET /v1/cases/{committed_case_id}` includes `latest_decision: {decision_id, outcome, sealed_ledger_entry_id}`.
    * `GET /v1/cases/{pending_seal_case_id}` includes `latest_decision` with `sealed_ledger_entry_id: null`.
    * `GET /v1/cases/{decision_ready_case_id}` (no decision yet) → `latest_decision: null`.

12. **AC12 — `make lint && make test` clean.** Net new test count: ≥ 5 in `useSealAnimation.test.tsx`, ≥ 5 in `DecisionZone.test.tsx` (extend), ≥ 3 in `SealedIndicator.test.tsx`, ≥ 3 in `test_cases_router.py` (extend).

13. **AC13 — End-to-end manual demo.**

    1. Open Vora's case, commit decision per Story 7-5's flow steps 1-4.
    2. UndoPill visible, countdown ticking.
    3. Wait 120 seconds (or use the dev shortcut: a temporary env `DECISION_TIMER_WINDOW=10` that overrides `UNDO_WINDOW_SECONDS` from Story 7-4 — verify if this exists; if not, add a comment that demo can set it for testing without waiting 2 minutes).
    4. At 0s:
       * UndoPill fades out (300 ms exit).
       * Decision Zone executes the seal animation (400 ms): body lifts 2px, opacity flashes to 70% then back, scale squeezes to 0.998 then 1.0.
       * Wax-seal stamp appears bottom-right of Decision Zone (overshoot ease, ~400 ms).
       * After 400ms, the stamp is replaced (smooth crossfade) by the inline SealedIndicator: "● Sealed led_01HXY3…".
    5. Click on the SealedIndicator → Story 6-6's reasoning trace slide-out opens for the seal ledger entry.
    6. Reload the page. Decision Zone renders read-only with the sealed rationale and the SealedIndicator visible (no animation; the stamp doesn't replay on reload — it's the "sealed" steady state).
    7. macOS Reduce Motion ON → repeat steps 1-4. The animations are absent: pill disappears instantly; Decision Zone doesn't lift/flash; stamp appears without overshoot. The SealedIndicator still renders correctly.

## Tasks / Subtasks

- [x] **Task 1 — `useSealAnimation` hook** (AC: #1, #8)
  - [x] Subtask 1.1 — `apps/cockpit-ui/src/hooks/useSealAnimation.ts`.
  - [x] Subtask 1.2 — `useSealAnimation.test.tsx` (≥ 5 cases).

- [x] **Task 2 — Decision Zone seal animation** (AC: #2, #3, #7, #9)
  - [x] Subtask 2.1 — Extend `DecisionZone.tsx` with `motion.section` + body flash variants.
  - [x] Subtask 2.2 — `SealIcon` SVG component.
  - [x] Subtask 2.3 — `prefers-reduced-motion` collapse via `useReducedMotion`.
  - [x] Subtask 2.4 — Extend `DecisionZone.test.tsx` (≥ 5 cases).

- [x] **Task 3 — `SealedIndicator`** (AC: #4, #10)
  - [x] Subtask 3.1 — `apps/cockpit-ui/src/components/cockpit/DecisionZone/SealedIndicator.tsx`.
  - [x] Subtask 3.2 — `SealedIndicator.test.tsx` (≥ 3 cases).

- [x] **Task 4 — Backend `latest_decision` envelope** (AC: #5, #11)
  - [x] Subtask 4.1 — `CaseLatestDecision` Pydantic in contracts.
  - [x] Subtask 4.2 — `case_service.fetch_case_envelope` helper joins case + latest decision + seal ledger id.
  - [x] Subtask 4.3 — Extend `GET /v1/cases/{case_id}` response model.
  - [x] Subtask 4.4 — Extend `test_cases_router.py` (≥ 3 cases).
  - [x] Subtask 4.5 — `make contracts`.

- [x] **Task 5 — UndoPill exit choreography** (AC: #6)
  - [x] Subtask 5.1 — Wrap UndoPill mount in `<AnimatePresence>` at route level.
  - [x] Subtask 5.2 — Verify visual choreography on demo machine.

- [x] **Task 6 — Verification** (AC: #12, #13)
  - [x] Subtask 6.1 — `make lint && make test` green.
  - [x] Subtask 6.2 — Manual demo per AC13.

## Dev Notes

### Architectural context (binding)

* [Source: `architecture.md#Frontend Architecture`] Framer Motion is the motion library; `AnimatePresence` for mount/unmount choreography.
* [Source: `architecture.md#Project-Specific Patterns` § P6 SSE] `decision.sealed` event drives the trigger.
* [Source: `ux-design-specification.md` § Seal animation (line 1290)] "weighted, not celebratory" — keep the motion subtle.
* [Source: `prd.md#Functional Requirements` FR24] commit decision is the surface this story polishes.
* [Source: `4-4-three-motion-flavors-as-framer-motion-utilities.md`] motion presets — this story uses ad-hoc variants, not a named preset, since the seal animation is unique.

### Critical pitfalls

1. **The seal stamp is purely decorative.** It's not a button; click events shouldn't open anything. Add `aria-hidden="true"` and `pointer-events-none` so the stamp doesn't trap focus or interfere with click-to-open on the SealedIndicator that takes its place.

2. **`AnimatePresence` requires a unique `key`.** The seal stamp's `key="seal-stamp"` and the SealedIndicator's `key="seal-indicator"` differ — that's how AnimatePresence knows to crossfade instead of replace. Tests AC9 verify both render at appropriate phases.

3. **`useSealAnimation` SSE subscription must be deduped.** If `<DecisionZone>` and `<UndoPill>` both subscribe to the same case's stream (they do, indirectly via different hooks), the cockpit's existing SSE setup should single-source via Story 4-6's stream registry. Verify no double-subscription side effects.

4. **The 400 ms duration is fixed**, not derived from a token. UX-spec says 400ms verbatim. Don't make it configurable.

5. **Don't replay the seal animation on every page reload.** `useSealAnimation` initializes to `idle`. Even if the case is in `committed` state, the hook stays idle until an SSE event arrives — which won't happen for an already-sealed case. SealedIndicator renders the "steady state" indicator; the animation doesn't replay. Tests verify reload behavior.

6. **The `latest_decision` envelope addition is a small surface — keep it small.** Don't bake decision details (rationale_html etc.) into the case envelope — that's persistent payload bloat for pages that don't need it. Only the IDs + outcome + sealed_ledger_entry_id. Story 7-1's Decision Zone fetches the full draft separately.

7. **`SealIcon` is purely SVG.** Don't pull in Lucide for a "stamp" icon — Lucide doesn't have a wax-seal glyph that fits, and a custom SVG is ~10 lines. The aesthetic intent is bespoke; iconography matches.

8. **Click on SealedIndicator opens slide-out via `window.dispatchEvent(new CustomEvent('cockpit:open-trace', ...))`.** This matches Story 7-1 § AC10's pattern. The route-level handler is owned by `cases.$caseId.tsx` — verify it exists and routes to Story 6-6's slide-out.

9. **Overshoot ease for the stamp** — `cubic-bezier(0.34, 1.56, 0.64, 1)` is the "spring-like" curve. Subtle scale overshoot ~5%. Don't use a heavier overshoot (>10%) — reads as "celebratory" which UX-DR28 explicitly avoids.

10. **The body opacity flash is on the editor body, NOT the entire Decision Zone.** Flashing the whole zone (header / footer / editor) feels jarring. Just the rationale text — the sacred content. Verify in DOM.

11. **`prefers-reduced-motion` is non-negotiable.** A user with vestibular sensitivity must not see the lift/squeeze. AC7 mandates the variant collapse. Test by mocking `useReducedMotion` to return true and asserting the animate prop is empty/no-op.

12. **The seal animation doesn't gate state transitions.** The case is already `committed` when the SSE event fires. The animation is purely visual; no functional dependency on its completion. Tests verify the state is `committed` even before the `useSealAnimation` returns 'sealed'.

### Story dependencies

* **Strict prereqs:** Story 7-4 (`decision.sealed` SSE event + PENDING_SEAL → COMMITTED transition), Story 7-5 (UndoPill — this story coordinates its exit), Story 7-1 (Decision Zone host component), Story 7-7 (POST /decisions creates the decision row), Story 6-6 (reasoning trace slide-out — opened by the SealedIndicator click), Story 4-4 (motion patterns reference).
* **Read by:** None directly. This is the demo's commit-flow finale.

### Project Structure Notes

This story creates:
- `apps/cockpit-ui/src/hooks/useSealAnimation.ts`
- `apps/cockpit-ui/src/hooks/useSealAnimation.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/DecisionZone/SealedIndicator.tsx`
- `apps/cockpit-ui/src/components/cockpit/DecisionZone/SealedIndicator.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/DecisionZone/SealIcon.tsx`

This story modifies:
- `packages/contracts/src/contracts/cases.py` — adds `CaseLatestDecision`
- `apps/cockpit-api/src/cockpit_api/services/case_service.py` — adds `fetch_case_envelope`
- `apps/cockpit-api/src/cockpit_api/routers/cases.py` — `GET /v1/cases/{case_id}` response model gains `latest_decision`
- `apps/cockpit-ui/src/components/cockpit/DecisionZone/DecisionZone.tsx` — adds motion variants + seal stamp + SealedIndicator render
- `apps/cockpit-ui/src/components/cockpit/DecisionZone/DecisionZone.test.tsx` — extend
- `apps/cockpit-ui/src/routes/cases.$caseId.tsx` — wraps UndoPill in AnimatePresence
- `apps/cockpit-api/tests/test_cases_router.py` — extend
- `apps/cockpit-ui/src/api-types.ts` — regenerated by `make contracts`

This story does NOT create:
- The decision_id or seal SSE event (Story 7-4 / 7-7)
- The decision row schema (Story 7-7)
- A new motion preset (uses ad-hoc Framer variants)
- Sound effects (UX-DR28 explicitly silent — no audio cues)

### References

- [Source: `epics.md#Epic 7` § Story 7.10] verbatim
- [Source: `architecture.md#Frontend Architecture`]
- [Source: `architecture.md#Project-Specific Patterns`] § P6 SSE
- [Source: `ux-design-specification.md` § Seal animation (line 1290)]
- [Source: `prd.md#Functional Requirements` FR24]
- [Source: `7-4-120-second-undo-timer-in-memory.md`] decision.sealed SSE event
- [Source: `7-5-undopill-with-countdown-ring-and-reason-capture-modal.md`] UndoPill exit coordination
- [Source: `6-6-reasoning-trace-slide-out-component.md`] click target

### Demo verification protocol

Per AC13. The 120s wait is the slow step — the optional `DECISION_TIMER_WINDOW=10` env shortcut speeds verification.

If any step fails, the bug is in this story; do not ship until green.

## Dev Agent Record

### Agent Model Used

(claude-opus-4-7 + Amelia persona, bmad-dev-story workflow)

### Debug Log References

### Completion Notes List

### File List

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-05-08 | Story 7.6 drafted. Seal animation on commit: 400ms ease-out lift+flash on Decision Zone body, wax-seal SVG stamp with overshoot ease, fade to inline SealedIndicator with truncated ledger ID; UndoPill exit choreographed via AnimatePresence; backend `latest_decision` envelope addition surfaces seal ledger id; prefers-reduced-motion respect throughout. |
