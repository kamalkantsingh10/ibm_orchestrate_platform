# Story 7.5: UndoPill with countdown ring + reason capture modal

Status: review

## Story

As a KYC Analyst,
I want an `UndoPill` that — while the case is in `pending_seal` state — pins to the bottom-center of the screen showing a 120 → 0 SVG countdown ring, an "Undo" button that opens a Radix Dialog requiring a reason ≥ 40 characters, a "Confirm Undo" button enabled only when the reason validates, and a `POST /v1/cases/{case_id}/decisions/{decision_id}/undo` call that flips the case back to `decision_ready` + cancels Story 7-4's timer + writes an `officer.decision_undone` ledger entry,
So that the demo's "120-second undo" beat lands tactilely (NFR-T1, NFR-T6 reason ≥ 40 chars), Priya's mistakes are correctable while the undo itself becomes audit evidence, and Story 7-6's seal animation has a clean fall-through path when the officer doesn't undo (UX-DR27, UX-spec § UndoPill).

## Scope note (2026-04-29 demo re-scope)

This story is the demo-equivalent of the bank-buyer Story 7.9. Cuts: officer keypair signing on the undo entry (Story 7-4's bank-buyer scope had it).

| Bank-buyer scope (original 7.9) | Demo replacement |
|---|---|
| Visible 120s countdown ring + Undo button | **Same.** SVG circle with stroke-dasharray. |
| `snap` motion preset for tick | **Same** — Story 4-4 preset reused. |
| Reason ≥ 40 chars in modal | **Same** — `NFR-T6` carried into demo. |
| `officer.decision_undone` ledger entry includes officer signature (Story 7.4) | **No signature.** Officer identity from session; `actor_type=officer`, `actor_id=user_id`. |
| Tenant-scoped endpoint | **Single-tenant.** |

What survives: **the entire visual + interaction primitive — countdown ring, modal, reason validation, undo POST, ledger entry, SSE event, fall-back to seal-on-timeout.**

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md`, `architecture.md#Frontend Architecture`, `ux-design-specification.md` § UndoPill (line 1268-1273), `prd.md#Non-Functional Requirements` NFR-T1 / NFR-T6.

## Acceptance Criteria

1. **AC1 — `GET /v1/cases/{case_id}/decisions/active/timer` route in cockpit-api.**

    Returns the remaining-seconds for the active timer (Story 7-4's `DecisionTimerService.remaining_seconds`):

    ```python
    @router.get("/{case_id}/decisions/active/timer", response_model=DecisionTimerView)
    async def get_active_decision_timer(
        case_id: Annotated[CaseId, Path()],
        _: Annotated[User, Depends(get_current_user)],
        timer: Annotated[DecisionTimerService, Depends(get_decision_timer)],
    ) -> DecisionTimerView | Response: ...

    class DecisionTimerView(BaseModel):
        case_id: CaseId
        decision_id: str
        remaining_seconds: float
        window_seconds: int = UNDO_WINDOW_SECONDS
    ```

    Returns 200 with the view when a timer is active; **204 No Content** when no timer (case not in pending_seal). The decision_id comes from the timer service's internal state — extend `DecisionTimerService` with a `view(case_id) -> DecisionTimerView | None` helper for clean route impl.

    Used by the cockpit-ui on initial mount to seed the countdown (the SSE event ordering can race the UI mount; this endpoint resolves the race deterministically).

2. **AC2 — `POST /v1/cases/{case_id}/decisions/{decision_id}/undo` route.**

    ```python
    class UndoDecisionRequest(BaseModel):
        model_config = {"frozen": True}
        reason: str = Field(min_length=40, max_length=2000)

    class UndoDecisionResponse(BaseModel):
        case_id: CaseId
        decision_id: str
        case_state: CaseState   # decision_ready after undo
        ledger_entry_id: LedgerEntryId

    @router.post("/{case_id}/decisions/{decision_id}/undo", response_model=UndoDecisionResponse)
    async def undo_decision(
        case_id: Annotated[CaseId, Path()],
        decision_id: Annotated[str, Path()],
        body: UndoDecisionRequest,
        user: Annotated[User, Depends(get_current_user)],
        session: Annotated[AsyncSession, Depends(get_session)],
        timer: Annotated[DecisionTimerService, Depends(get_decision_timer)],
        writer: Annotated[LedgerWriter, Depends(get_ledger_writer)],
    ) -> UndoDecisionResponse: ...
    ```

    Logic:
    1. **Resolve case** via `case_service.fetch_case(...)`. 404 if absent.
    2. **Verify state** — must be `pending_seal`. If `decision_ready` (timer already expired or already undone) → 409 Conflict with RFC 7807 body `"decision is no longer pending seal"`. If `committed` → 409 `"decision already sealed"`.
    3. **Verify decision id matches the active timer** — `timer.view(case_id).decision_id == decision_id`. Defense-in-depth against a stale decision_id from a prior commit. Mismatch → 409.
    4. **Cancel the timer** — `timer.cancel(case_id)`. If returns False (no active timer) — log + still proceed with state reversion (the case must be reverted regardless).
    5. **Transition case** — `pending_seal → decision_ready`.
    6. **Write `officer.decision_undone` ledger entry** — actor_type=`OFFICER`, actor_id=`user.id`, event_type=`officer.decision_undone`, payload = `{"decision_id": decision_id, "reason": body.reason}`. Use a typed payload; add `OfficerDecisionUndonePayload` to `packages/contracts/src/contracts/ledger.py`:

       ```python
       class OfficerDecisionUndonePayload(BaseModel):
           model_config = {"frozen": True}
           kind: Literal["officer_decision_undone"] = "officer_decision_undone"
           decision_id: str = Field(min_length=1)
           reason: str = Field(min_length=40, max_length=2000)
       ```

       Add to the `LedgerEntry.payload` union (alongside Story 6-7's `CockpitChatToolLedgerPayload`).
    7. **Fire SSE event** — `decision.undone` (event already added in Story 7-4 § AC4) with payload `{case_id, decision_id, reason}`.
    8. **Return** `UndoDecisionResponse`.

3. **AC3 — `useDecisionTimer(caseId)` hook at `apps/cockpit-ui/src/hooks/useDecisionTimer.ts`.**

    ```typescript
    type DecisionTimerState =
        | { status: 'no-timer' }
        | { status: 'active'; decisionId: string; remainingSeconds: number; windowSeconds: number };

    export function useDecisionTimer(caseId: string): DecisionTimerState { ... }
    ```

    Logic:
    * On mount, fetch `GET /v1/cases/{caseId}/decisions/active/timer`. 204 → `no-timer`; 200 → `active` with the response payload.
    * Locally count down via `setInterval(100ms)` ticking `remainingSeconds`. When it hits 0 → state stays `active` until the SSE event arrives (or a re-fetch).
    * Subscribe to the case's SSE stream (existing Story 4-6 hook):
        * `decision.committed` → re-fetch; transition to `active`.
        * `decision.sealed` → flip to `no-timer`.
        * `decision.undone` → flip to `no-timer`.
    * On case state change to anything other than `pending_seal` → flip to `no-timer` (defensive).

    Tests at `useDecisionTimer.test.tsx`: 204 → `no-timer`; 200 → `active` with countdown; tick decrements; SSE seal → `no-timer`; SSE undone → `no-timer`.

4. **AC4 — `UndoPill` component at `apps/cockpit-ui/src/components/cockpit/UndoPill/UndoPill.tsx`.**

    ```typescript
    export interface UndoPillProps {
        caseId: string;
    }

    export function UndoPill({ caseId }: UndoPillProps): JSX.Element | null {
        const timer = useDecisionTimer(caseId);
        if (timer.status !== 'active') return null;
        // ... render pinned to bottom-center
    }
    ```

    Layout:
    * **Position**: `fixed bottom-6 left-1/2 -translate-x-1/2 z-50`.
    * **Container**: rounded-full, white bg, shadow-lg, `flex items-center gap-3 px-4 py-2.5 ring-1 ring-zinc-200`.
    * **Countdown ring** (left): SVG `<circle>` with `stroke-dasharray` + `stroke-dashoffset` driven by `remainingSeconds / windowSeconds`. Diameter ~28px. Color: `stroke-amber-500` while > 30s; `stroke-rose-500` when ≤ 30s (urgency cue). Inside the ring: bold numeric `Math.ceil(remainingSeconds)` in `text-xs font-mono`.
    * **Label** (middle): `<span className="text-sm font-medium text-zinc-900">Decision committed · sealing in {n}s</span>`.
    * **Undo button** (right): `<button>Undo</button>` styled as a secondary chip.
    * **Motion**: `snap` preset (Story 4-4) on the ring's tick — every 1s, the ring "snaps" to the next position with a subtle ease-out (≤ 100ms). For the demo's 100ms-tick countdown, this means a hint of motion every full second; smooth in-between. Confirm Story 4-4's snap preset semantics before coding; if `snap` is per-tick rather than per-second, render two layers (smooth fill + snap heartbeat).

5. **AC5 — Countdown ring SVG.**

    ```tsx
    function CountdownRing({ remaining, total }: { remaining: number; total: number }) {
        const radius = 13;
        const circumference = 2 * Math.PI * radius;
        const offset = circumference * (1 - remaining / total);
        const isUrgent = remaining <= 30;
        return (
            <svg width="28" height="28" viewBox="0 0 28 28" className="motion-reduce:transition-none">
                <circle cx="14" cy="14" r={radius} className="fill-none stroke-zinc-200 stroke-2" />
                <circle
                    cx="14" cy="14" r={radius}
                    className={cn(
                        'fill-none stroke-2 transition-[stroke-dashoffset] duration-100 ease-linear',
                        'motion-reduce:transition-none',
                        isUrgent ? 'stroke-rose-500' : 'stroke-amber-500',
                    )}
                    strokeDasharray={circumference}
                    strokeDashoffset={offset}
                    transform="rotate(-90 14 14)"
                />
                <text x="14" y="14" textAnchor="middle" dominantBaseline="central"
                      className="text-[10px] font-mono fill-zinc-900">
                    {Math.ceil(remaining)}
                </text>
            </svg>
        );
    }
    ```

    `transform="rotate(-90 14 14)"` starts the ring from the top. `transition-[stroke-dashoffset] duration-100` smooths the ring during the 100ms tick interval — the ring appears to fill smoothly. Reduced-motion suppresses the transition; the ring snaps to each position.

6. **AC6 — Reason capture modal.**

    Click on Undo button → opens a Radix Dialog modal:

    ```tsx
    <Dialog.Root open={open} onOpenChange={setOpen}>
        <Dialog.Portal>
            <Dialog.Overlay className="fixed inset-0 bg-black/30" />
            <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[480px] bg-white rounded-lg shadow-2xl p-6">
                <Dialog.Title className="text-base font-semibold text-zinc-900">Undo this decision</Dialog.Title>
                <Dialog.Description className="mt-1 text-sm text-zinc-600">
                    Tell me why — at least 40 characters. The undo + reason become part of the audit ledger.
                </Dialog.Description>
                <textarea
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    rows={4}
                    className="mt-4 w-full rounded border border-zinc-300 p-2 text-sm font-sans"
                    autoFocus
                    aria-label="Reason for undo"
                />
                <div className="mt-2 flex justify-between text-xs text-zinc-500">
                    <span>{reason.length}/40 minimum</span>
                </div>
                <div className="mt-5 flex justify-end gap-2">
                    <button onClick={() => setOpen(false)} className="px-3 py-1.5 rounded text-sm">Cancel</button>
                    <button
                        disabled={reason.length < 40 || isSubmitting}
                        onClick={handleConfirm}
                        className="px-3 py-1.5 rounded bg-rose-600 text-white text-sm disabled:opacity-50">
                        {isSubmitting ? 'Reverting…' : 'Confirm Undo'}
                    </button>
                </div>
            </Dialog.Content>
        </Dialog.Portal>
    </Dialog.Root>
    ```

    On confirm:
    * Disable the button (isSubmitting = true).
    * `POST /v1/cases/{caseId}/decisions/{decisionId}/undo` with `{reason}`.
    * On 200 → close modal; toast "Decision reverted." (or just rely on the case state SSE event); the UndoPill itself unmounts because `useDecisionTimer` flips to `no-timer`.
    * On 409 (timer already expired) → close modal; toast "Decision already sealed; cannot undo." Don't crash.
    * On other error → keep modal open; show inline error.

7. **AC7 — Mount inside `cases.$caseId.tsx` (route-level).**

    ```tsx
    <DecisionZone caseId={caseId} />
    <UndoPill caseId={caseId} />
    ```

    The pill renders only when its hook is `active` — null otherwise. No prop dependency on Decision Zone state; pure side-effect mount.

8. **AC8 — Race conditions: UI mount AFTER timer expiry.**

    If the user navigates to a `pending_seal` case after the 120s timer has already expired and the seal SSE event was missed, the GET endpoint returns 204; the pill correctly stays unmounted. Once the cockpit-ui's case-state query refetches, the case will appear in `committed` state. Tests verify this corner.

9. **AC9 — Tests at `apps/cockpit-api/tests/test_cases_router.py` (extend).**

    * **GET timer when active** → 200 + payload.
    * **GET timer when no active timer** → 204.
    * **POST undo with reason ≥ 40 chars + state pending_seal** → 200; case flips to `decision_ready`; ledger entry written; SSE `decision.undone` fires.
    * **POST undo with reason < 40 chars** → 422.
    * **POST undo when state is `decision_ready`** → 409 "no longer pending seal".
    * **POST undo when state is `committed`** → 409 "already sealed".
    * **POST undo with mismatched decision_id** → 409.
    * **POST undo cancels the timer** — assert `timer.remaining_seconds(case_id) is None` after.
    * **POST undo writes ledger entry with typed `OfficerDecisionUndonePayload`** — assert payload kind + reason.

10. **AC10 — Tests at `apps/cockpit-ui/src/components/cockpit/UndoPill/UndoPill.test.tsx`.**

    * Renders nothing when timer status is `no-timer`.
    * Renders pill with countdown when status is `active` (mock `useDecisionTimer`).
    * Countdown text shows `Math.ceil(remainingSeconds)`.
    * Ring color flips from amber to rose at 30s threshold.
    * Click Undo → modal opens.
    * Modal Confirm disabled when reason < 40 chars.
    * Modal Confirm enabled when reason ≥ 40 chars.
    * Confirm → POST fires with the right body.
    * 200 response → modal closes.
    * 409 response → modal closes + toast (mock toaster).
    * `motion-reduce` → ring transition class absent.

11. **AC11 — Tests at `apps/cockpit-ui/src/hooks/useDecisionTimer.test.tsx`.**

    * 204 on mount → `no-timer`.
    * 200 on mount → `active` with countdown.
    * `setInterval` tick decrements `remainingSeconds`.
    * SSE `decision.sealed` → `no-timer`.
    * SSE `decision.undone` → `no-timer`.
    * Cleanup on unmount cancels the interval (assert via `vi.useFakeTimers`).

12. **AC12 — Tests at `packages/contracts/tests/test_ledger.py` (extend Story 6-7's tests).**

    * `OfficerDecisionUndonePayload` round-trips.
    * Reason < 40 chars → ValidationError.

13. **AC13 — `make lint && make test` clean.** Net new test count: ≥ 9 in `test_cases_router.py` (extend), ≥ 11 in `UndoPill.test.tsx`, ≥ 6 in `useDecisionTimer.test.tsx`, ≥ 2 in `test_ledger.py` (extend).

14. **AC14 — End-to-end manual demo.**

    1. Open Vora's case (state `decision_ready` after intake).
    2. Decision Zone has Writing agent's draft (Story 7-3) + outcome stub.
    3. Select outcome `approve`, press `⌘+Enter` → Decision Zone becomes read-only; UndoPill appears bottom-center.
    4. Pill shows "Decision committed · sealing in 119s" + amber countdown ring + "Undo" button.
    5. Wait 90 seconds. Ring color flips to rose at 30s remaining.
    6. Click Undo → modal opens.
    7. Type a 30-char reason → Confirm Undo button is disabled.
    8. Type a 50-char reason ("Misread Patel R.'s OFAC hit; need to review more carefully.") → button enabled.
    9. Click Confirm Undo → modal closes; UndoPill disappears; case state SSE-flips to `decision_ready`; Decision Zone becomes editable again with the same rationale.
    10. Verify ledger via `cat ./data/ledger.jsonl | jq 'select(.event_type=="officer.decision_undone")'` — entry present with reason.
    11. Repeat 3-5 with a fresh decision but DON'T click Undo → at 0s, Story 7-6's seal animation fires, UndoPill disappears, "Sealed (`led_<ULID>`)" indicator replaces it.

## Tasks / Subtasks

- [x] **Task 1 — Endpoints** (AC: #1, #2, #9)
  - [x] Subtask 1.1 — `OfficerDecisionUndonePayload` in `contracts/ledger.py` + union extension.
  - [x] Subtask 1.2 — Extend `DecisionTimerService` with `view(case_id)` helper.
  - [x] Subtask 1.3 — `GET /v1/cases/{id}/decisions/active/timer` route.
  - [x] Subtask 1.4 — `POST /v1/cases/{id}/decisions/{decision_id}/undo` route.
  - [x] Subtask 1.5 — Extend `test_cases_router.py` (≥ 9 cases).
  - [x] Subtask 1.6 — Extend `test_ledger.py` (≥ 2 cases).

- [x] **Task 2 — `useDecisionTimer` hook** (AC: #3, #11)
  - [x] Subtask 2.1 — `apps/cockpit-ui/src/hooks/useDecisionTimer.ts`.
  - [x] Subtask 2.2 — `useDecisionTimer.test.tsx` (≥ 6 cases).

- [x] **Task 3 — `UndoPill` component** (AC: #4, #5, #6, #10)
  - [x] Subtask 3.1 — `UndoPill.tsx` + `CountdownRing` subcomponent.
  - [x] Subtask 3.2 — Reason capture modal via Radix Dialog.
  - [x] Subtask 3.3 — `index.ts` re-export.
  - [x] Subtask 3.4 — `UndoPill.test.tsx` (≥ 11 cases).

- [x] **Task 4 — Wire into route** (AC: #7, #14)
  - [x] Subtask 4.1 — Mount `<UndoPill caseId={caseId} />` in `cases.$caseId.tsx`.

- [x] **Task 5 — Verification** (AC: #13, #14)
  - [x] Subtask 5.1 — `make lint && make test` green.
  - [x] Subtask 5.2 — Manual demo per AC14.

## Dev Notes

### Architectural context (binding)

* [Source: `architecture.md#Frontend Architecture` § F1] TanStack Query for the timer fetch.
* [Source: `architecture.md#Project-Specific Patterns` § P6 SSE] events drive UI invalidation.
* [Source: `architecture.md#Format Patterns`] RFC 7807 on errors (409 conflicts).
* [Source: `prd.md#Non-Functional Requirements` NFR-T1] 120s undo window.
* [Source: `prd.md#Non-Functional Requirements` NFR-T6] reason ≥ 40 chars.
* [Source: `ux-design-specification.md` § UndoPill] visual primitive — countdown ring, undo button, modal.
* [Source: `4-4-three-motion-flavors-as-framer-motion-utilities.md`] `snap` preset.

### Critical pitfalls

1. **Don't trust the client clock for seal time.** The countdown is visual; the seal happens on the server (Story 7-4's timer task). When `remainingSeconds` reaches 0 client-side, the pill stays mounted until the SSE event arrives — typically <1s drift. Don't auto-flip to "Sealed" client-side.

2. **`setInterval(100ms)` cleanup is mandatory.** A leaked interval after the case unmounts produces phantom POSTs and console errors. Tests AC11 verify cleanup.

3. **The undo POST must cancel the timer BEFORE writing the ledger entry.** If the order reversed (ledger first, cancel later), the seal task could fire between them and write a `decision.sealed` entry — followed by a `decision.undone` entry. Both would exist; both would be valid; auditing becomes ambiguous. Order: `cancel → state transition → ledger entry → SSE`.

4. **The 409 on mismatched `decision_id` is defense-in-depth.** A user with two browser tabs open on the same case could click Undo in tab A while tab B has an outdated decision_id from a prior commit + undo cycle. The check prevents the wrong undo from firing.

5. **`reason` minimum 40 is on BOTH client and server.** Client disables the button; server validates via Pydantic. Don't skip either — adversarial client can bypass; un-validated server is the AC8 audit gate.

6. **The countdown ring uses `stroke-dashoffset`, NOT `stroke-dasharray` animation.** Both could work; offset is the boring 2026 idiom (well-supported, GPU-friendly). Don't use a JS animation library.

7. **`motion-reduce` respect** — both the ring's transition and the modal's open/close animation. Tailwind's `motion-reduce:transition-none` covers the ring; Radix Dialog's animations should respect the system preference (verify via Radix docs).

8. **Pinned position `bottom-6 left-1/2 -translate-x-1/2 z-50`** — verify nothing else uses `z-50`. If the slide-out (Story 6-6) is open, it has higher z-index (it's a Dialog overlay). The pill should NOT stack on top of an open slide-out — it stays underneath the overlay (z-50 is below Radix Dialog's internal z-index ~100). Verify visually.

9. **The pill mounts even when Decision Zone is hidden** (case scrolled off, narrow viewport). The pill is a global UI element — pins to viewport, not to Decision Zone. Verify on mobile-narrow viewports (out of demo scope but cheap to verify).

10. **The undo POST writes `actor_type=OFFICER`, NOT `AGENT`.** Story 3-1's `ActorType` enum has `OFFICER` (verify; if not, add it). Distinct from agent-written entries.

11. **`OfficerDecisionUndonePayload` lives in `contracts/ledger.py`, NOT a new module.** Mirrors the pattern of `LearningEventLedgerPayload` (Story 5-5) and `CockpitChatToolLedgerPayload` (Story 6-7). Co-located.

12. **The toast on 409 — "decision already sealed; cannot undo"** — is a UX hint that the timer expired faster than the click. Verify behavior: the modal closes; the pill is already gone (since `useDecisionTimer` flipped to `no-timer` from the SSE event). The toast is the only feedback; without it, the user might wonder if their click registered.

### Story dependencies

* **Strict prereqs:** Story 7-4 (DecisionTimerService + PENDING_SEAL state + decision.sealed/.undone SSE events), Story 7-7 (POST /decisions creates the decision row + transitions to pending_seal), Story 4-6 (SSE channel), Story 4-4 (`snap` motion preset), Story 1-6 (`get_current_user`).
* **Read by:** Story 7-6 (seal animation fires when this story's timer falls through — i.e., the user doesn't undo).

### Project Structure Notes

This story creates:
- `apps/cockpit-ui/src/hooks/useDecisionTimer.ts`
- `apps/cockpit-ui/src/hooks/useDecisionTimer.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/UndoPill/UndoPill.tsx`
- `apps/cockpit-ui/src/components/cockpit/UndoPill/UndoPill.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/UndoPill/index.ts`

This story modifies:
- `packages/contracts/src/contracts/ledger.py` — adds `OfficerDecisionUndonePayload` + union extension
- `packages/contracts/tests/test_ledger.py` — extend
- `apps/cockpit-api/src/cockpit_api/services/decision_timer.py` — adds `view(case_id)` helper
- `apps/cockpit-api/src/cockpit_api/routers/cases.py` — adds two routes (GET timer, POST undo)
- `apps/cockpit-api/tests/test_cases_router.py` — extend
- `apps/cockpit-ui/src/routes/cases.$caseId.tsx` — mounts `<UndoPill>`
- `apps/cockpit-ui/src/api-types.ts` — regenerated by `make contracts`

This story does NOT create:
- The decision row / POST /decisions endpoint (Story 7-7)
- The seal animation (Story 7-6)
- The Decision Zone editable-on-undo behavior (Story 7-1 already conditions on case state; works automatically)

### References

- [Source: `epics.md#Epic 7` § Story 7.9] verbatim shape, signing cut
- [Source: `architecture.md#Frontend Architecture`] § F1
- [Source: `architecture.md#Format Patterns`]
- [Source: `prd.md#Non-Functional Requirements` NFR-T1, NFR-T6]
- [Source: `ux-design-specification.md` § UndoPill]
- [Source: `4-4-three-motion-flavors-as-framer-motion-utilities.md`] `snap` preset
- [Source: `7-4-120-second-undo-timer-in-memory.md`] DecisionTimerService API + SSE events

### Demo verification protocol

Per AC14. If any step fails, the bug is in this story; do not ship until green.

## Dev Agent Record

### Agent Model Used

(claude-opus-4-7 + Amelia persona, bmad-dev-story workflow)

### Debug Log References

### Completion Notes List

### File List

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-05-08 | Story 7.5 drafted. UndoPill with SVG countdown ring (amber→rose at 30s) + reason capture modal (≥ 40 chars), GET timer view + POST undo endpoints, OfficerDecisionUndonePayload typed ledger arm. Officer signing cut per demo scope. |
