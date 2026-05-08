# Story 7.4: 120-second undo timer (in-memory)

Status: review

## Story

As the platform,
I want a `DecisionTimerService` that — when an officer commits a decision via Story 7-7's POST endpoint — schedules a process-local 120-second `asyncio.create_task` per case, transitions the case to `committed` state and writes a `decision.sealed` ledger entry + SSE event when the timer elapses, supports immediate cancellation when the officer hits Undo (Story 7-5), and exposes a `remaining_seconds(case_id)` query for the UndoPill to read,
So that Story 7-5's countdown ring has a server-authoritative source for the remaining window, the seal animation (Story 7-6) fires deterministically on timer expiry, and the demo's J1 commit beat ("she presses ⌘+Enter, sees the countdown, watches it seal") completes without external infrastructure (NFR-T1, demo simplification of bank-buyer Story 7.8's Redis fail-closed timer).

## Scope note (2026-04-29 demo re-scope)

This story is the demo-equivalent of the bank-buyer Story 7.8. The bank-buyer scope used Redis with a 120s TTL key + Arq job queue + fail-closed policy on Redis unavailability. Demo replaces it with a process-local `asyncio.Task` per pending decision.

| Bank-buyer scope (original 7.8) | Demo replacement in this story |
|---|---|
| Redis key `decision:{case_id}:undo` with 120s TTL | **`asyncio.Task` per case, kept in a process-local `dict[CaseId, _PendingTimer]`.** No Redis. |
| Arq background job seals on TTL expiry | **The `asyncio.Task` itself seals on `await asyncio.sleep(120)`** — no separate worker. |
| Redis unavailable → decision held in `pending_seal` indefinitely; auto-cancel after 1h | **Cockpit-api restart → in-flight timers are lost.** Document the trade-off; demo runs are short, so this is acceptable. **No 1h auto-cancel** (no failure mode triggers it). |
| Tenant-scoped key | **Single-tenant** — case_id is the key. |
| Fires SSE + webhook on seal | **Fires SSE only** (no outbound webhooks in demo per Epic 2 cuts). |
| Tracks `pending_seal` state across cluster | **Single-process; cluster N/A.** |

What survives: **the 120s window, `pending_seal → committed` transition driven by the timer, `decision.sealed` SSE event, immediate cancel-and-revert on undo, the `DecisionTimerService` API surface (start / cancel / remaining), proper cleanup on cancel, the seal-time ledger entry.**

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md`, `architecture.md#Demo Scope Addendum (2026-04-29)` § Caching/Pub-Sub (no Redis), `architecture.md#Demo Scope Addendum` § Background work (FastAPI background tasks).

## Acceptance Criteria

1. **AC1 — `DecisionTimerService` at `apps/cockpit-api/src/cockpit_api/services/decision_timer.py`.**

    ```python
    """In-memory 120-second decision undo timer — Story 7-4.

    Demo simplification of bank-buyer Story 7.8 (Redis-backed). Process-local
    asyncio task per pending decision; seals on timer expiry; cancels on
    officer undo. Cockpit-api restart loses in-flight timers — acceptable
    for demo.
    """

    from __future__ import annotations

    import asyncio
    import logging
    import time
    from contextlib import asynccontextmanager
    from dataclasses import dataclass
    from typing import Awaitable, Callable

    from contracts.cases import CaseId

    logger = logging.getLogger(__name__)

    UNDO_WINDOW_SECONDS: int = 120


    @dataclass
    class _PendingTimer:
        case_id: CaseId
        decision_id: str            # the decision row's id
        scheduled_at: float         # monotonic seconds
        seal_at: float              # monotonic seconds; scheduled_at + UNDO_WINDOW_SECONDS
        task: asyncio.Task[None]


    class DecisionTimerService:
        """Process-local timer registry. One instance per cockpit-api process.

        Construct via dependency injection (see Story 7-7's POST endpoint).
        """

        def __init__(
            self,
            *,
            on_seal: Callable[[CaseId, str], Awaitable[None]],
            window_seconds: int = UNDO_WINDOW_SECONDS,
        ) -> None:
            self._on_seal = on_seal
            self._window = window_seconds
            self._timers: dict[CaseId, _PendingTimer] = {}

        def schedule(self, case_id: CaseId, decision_id: str) -> None:
            """Start a 120s timer. Idempotent: re-scheduling on the same case
            cancels and replaces the prior timer."""
            existing = self._timers.pop(case_id, None)
            if existing is not None:
                existing.task.cancel()
                logger.info("decision_timer.replaced", extra={"case_id": case_id})

            now = time.monotonic()
            seal_at = now + self._window
            task = asyncio.create_task(self._run_timer(case_id, decision_id, seal_at))
            self._timers[case_id] = _PendingTimer(
                case_id=case_id, decision_id=decision_id,
                scheduled_at=now, seal_at=seal_at, task=task,
            )

        def cancel(self, case_id: CaseId) -> bool:
            """Cancel the timer for ``case_id``. Return True iff one was active."""
            existing = self._timers.pop(case_id, None)
            if existing is None:
                return False
            existing.task.cancel()
            return True

        def remaining_seconds(self, case_id: CaseId) -> float | None:
            """Seconds remaining; None if no active timer."""
            t = self._timers.get(case_id)
            if t is None:
                return None
            return max(0.0, t.seal_at - time.monotonic())

        async def shutdown(self) -> None:
            """Cancel all pending timers. Called on app shutdown."""
            for t in list(self._timers.values()):
                t.task.cancel()
            self._timers.clear()

        async def _run_timer(self, case_id: CaseId, decision_id: str, seal_at: float) -> None:
            try:
                wait = max(0.0, seal_at - time.monotonic())
                await asyncio.sleep(wait)
                # Re-check we still own this slot — defensive if cancellation raced.
                if self._timers.get(case_id) is None or self._timers[case_id].decision_id != decision_id:
                    return
                self._timers.pop(case_id, None)
                await self._on_seal(case_id, decision_id)
            except asyncio.CancelledError:
                logger.info("decision_timer.cancelled", extra={"case_id": case_id})
                raise
            except Exception:
                logger.exception("decision_timer.seal_failed", extra={"case_id": case_id})
    ```

2. **AC2 — `on_seal` callback contract.**

    The `on_seal(case_id, decision_id)` callback is invoked by `_run_timer` when 120s elapses. Its responsibilities:
    1. **Transition case state** `pending_seal → committed`. Use `case_repo` + `assert_transition`.
    2. **Update decision row** — set `sealed_at = now()` on the decision.
    3. **Write `decision.sealed` ledger entry** — actor_type=`SYSTEM`, actor_id=`platform`, event_type=`decision.sealed`, payload includes `decision_id` + `outcome`. **Note**: this is a SYSTEM entry, not an officer-signed entry (signing was cut from demo per re-scope). The bank-buyer scope's officer-signed `officer.decision_committed` was Story 7-7's responsibility; this story only writes the seal.
    4. **Fire SSE event** — `decision.sealed` (new event name added to `SseEvent.event` literal in this story; AC4).

    The callback is wired by Story 7-7's POST endpoint (the endpoint constructs the `DecisionTimerService` with a closure that has access to repos + ledger + sse_registry). This story provides the service; Story 7-7 wires the callback.

    **Demo simplification**: the callback runs synchronously inside `_run_timer`. If it fails (DB exception, ledger write failure), the case stays in `pending_seal` and a log line records the failure. There's no retry. For a demo, that's tolerable; document.

3. **AC3 — Integration into FastAPI app lifecycle.**

    `apps/cockpit-api/src/cockpit_api/main.py` (or wherever the FastAPI app is constructed) needs:

    ```python
    from contextlib import asynccontextmanager
    from cockpit_api.services.decision_timer import DecisionTimerService

    @asynccontextmanager
    async def lifespan(app):
        # Construct singleton timer service; on_seal callback wired by Story 7-7's
        # decision_service module — bind here:
        from cockpit_api.services.decision_service import seal_decision
        timer = DecisionTimerService(on_seal=seal_decision)
        app.state.decision_timer = timer
        try:
            yield
        finally:
            await timer.shutdown()

    app = FastAPI(lifespan=lifespan, ...)
    ```

    Dependency injection helper:

    ```python
    def get_decision_timer(request: Request) -> DecisionTimerService:
        return request.app.state.decision_timer
    ```

    Story 7-7's POST endpoint and Story 7-5's undo endpoint both consume `Depends(get_decision_timer)`.

4. **AC4 — `decision.sealed` SSE event added to contract.**

    `packages/contracts/src/contracts/sse.py` — extend the `event` Literal:

    ```python
    event: Literal[
        "agent.state_changed",
        "case.state_changed",
        "case.documents_changed",
        "case.ubo_corrected",
        "cockpit_chat.token",
        "cockpit_chat.message_complete",
        "cockpit_chat.error",
        # NEW
        "decision.sealed",            # data: {case_id, decision_id, ledger_entry_id}
        "decision.committed",         # data: {case_id, decision_id} — fired on POST (pending_seal entry)
        "decision.undone",            # data: {case_id, decision_id, reason} — fired on undo
    ]
    ```

    Story 7-7 fires `decision.committed`; this story's `seal_decision` callback fires `decision.sealed`; Story 7-5's undo endpoint fires `decision.undone`. All three are added in this story's contract change so cockpit-ui's TS types regenerate correctly.

    Update `packages/contracts/tests/test_sse.py` with three new cases.

5. **AC5 — `pending_seal` case state.**

    `packages/contracts/src/contracts/cases.py` — extend `CaseState` enum:

    ```python
    class CaseState(StrEnum):
        INTAKE_SCHEDULED = "intake_scheduled"
        DECISION_READY = "decision_ready"
        PENDING_SEAL = "pending_seal"          # NEW — Story 7-4
        COMMITTED = "committed"
        ESCALATED = "escalated"
        CLOSED = "closed"
    ```

    And `ALLOWED_TRANSITIONS`:

    ```python
    ALLOWED_TRANSITIONS = {
        CaseState.INTAKE_SCHEDULED: {CaseState.DECISION_READY, CaseState.ESCALATED, CaseState.CLOSED},
        CaseState.DECISION_READY: {CaseState.PENDING_SEAL, CaseState.ESCALATED, CaseState.CLOSED},   # was: COMMITTED
        CaseState.PENDING_SEAL: {CaseState.COMMITTED, CaseState.DECISION_READY},                       # NEW
        CaseState.COMMITTED: {CaseState.CLOSED},
        CaseState.ESCALATED: {CaseState.COMMITTED, CaseState.DECISION_READY, CaseState.CLOSED},        # added DECISION_READY for re-eval after officer correction
        CaseState.CLOSED: set(),
    }
    ```

    Note: `DECISION_READY → COMMITTED` is **removed** — all commits now go through `PENDING_SEAL`. `PENDING_SEAL → DECISION_READY` is the undo path (Story 7-5).

    **Backward compat regression**: any existing tests / fixtures that call `assert_transition(DECISION_READY, COMMITTED)` will fail. Audit the codebase for these patterns at implementation time; update the call sites or add a migration note. Likely call sites: nowhere yet (Epic 7 hasn't been implemented; existing tests on Story 2-1 only verify the transition table, not specific transitions). Verify via grep.

6. **AC6 — Tests at `apps/cockpit-api/tests/services/test_decision_timer.py`.**

    Use `pytest-asyncio` with a small `window_seconds=2` (or even 0.5) override for fast tests:

    * **Happy path: `schedule(case, decision)` + 2s wait → `on_seal` invoked exactly once with `(case, decision)`.**
    * **`cancel(case)` returns True when timer active; on_seal NOT invoked.**
    * **`cancel(case)` returns False when no timer.**
    * **`remaining_seconds(case)` near `window_seconds` immediately after schedule, near 0 just before seal, None after seal.**
    * **`schedule` twice on same case** — first timer cancelled, second runs to completion, on_seal invoked once.
    * **`shutdown()` cancels all pending; on_seal NOT invoked for any cancelled.**
    * **`on_seal` raising → logged but doesn't crash the loop; subsequent timers still run.**
    * **Concurrent timers for different cases** — both fire, on_seal invoked twice with correct (case_id, decision_id) pairs.
    * **`window_seconds=0` (instant seal)** — on_seal fires immediately on next loop tick.

7. **AC7 — Tests at `packages/contracts/tests/test_cases.py` (extend).**

    * `CaseState.PENDING_SEAL` enum member exists with value `"pending_seal"`.
    * `ALLOWED_TRANSITIONS[CaseState.DECISION_READY]` contains `PENDING_SEAL` and does NOT contain `COMMITTED`.
    * `ALLOWED_TRANSITIONS[CaseState.PENDING_SEAL]` is exactly `{CaseState.COMMITTED, CaseState.DECISION_READY}`.
    * `assert_transition(PENDING_SEAL, COMMITTED)` succeeds.
    * `assert_transition(PENDING_SEAL, ESCALATED)` raises `CaseStateTransitionError`.
    * `assert_transition(DECISION_READY, COMMITTED)` raises (regression — was allowed).

8. **AC8 — Tests at `packages/contracts/tests/test_sse.py` (extend).**

    * Each new event name (`decision.sealed`, `decision.committed`, `decision.undone`) round-trips via JSON.
    * `SseEvent(event="decision.sealed", data={"case_id":"...", "decision_id":"...", "ledger_entry_id":"..."})` validates.

9. **AC9 — TS types regenerate.**

    `make contracts` regenerates `apps/cockpit-ui/src/api-types.ts`. Verify via grep that `decision.sealed`, `decision.committed`, `decision.undone`, and `pending_seal` appear in the generated types.

10. **AC10 — `make lint && make test` clean.** Net new test count: ≥ 9 in `test_decision_timer.py`, ≥ 6 in `test_cases.py` (extend), ≥ 3 in `test_sse.py` (extend).

11. **AC11 — End-to-end smoke test (synthetic).**

    Without Stories 7-5 / 7-7 wired, simulate the timer end-to-end:

    ```python
    # apps/cockpit-api/tests/services/test_decision_timer.py — integration-shaped
    @pytest.mark.asyncio
    async def test_seal_callback_writes_ledger_and_fires_sse(monkeypatch, ...):
        seal_calls = []
        async def fake_on_seal(case_id, decision_id):
            seal_calls.append((case_id, decision_id))
        timer = DecisionTimerService(on_seal=fake_on_seal, window_seconds=0.5)
        timer.schedule(VORA_CAPITAL_ID, "dec_test_123")
        await asyncio.sleep(0.7)
        assert seal_calls == [(VORA_CAPITAL_ID, "dec_test_123")]
    ```

    Full integration with `seal_decision` callback (Story 7-7's responsibility) is verified there, not here.

## Tasks / Subtasks

- [x] **Task 1 — Case state + transitions** (AC: #5, #7)
  - [x] Subtask 1.1 — Extend `CaseState` enum.
  - [x] Subtask 1.2 — Update `ALLOWED_TRANSITIONS`.
  - [x] Subtask 1.3 — Audit codebase for `assert_transition(DECISION_READY, COMMITTED)` callers.
  - [x] Subtask 1.4 — Extend `test_cases.py` (≥ 6 cases).

- [x] **Task 2 — SSE event extension** (AC: #4, #8, #9)
  - [x] Subtask 2.1 — Extend `SseEvent.event` literal with `decision.sealed`, `decision.committed`, `decision.undone`.
  - [x] Subtask 2.2 — Extend `test_sse.py` (≥ 3 cases).
  - [x] Subtask 2.3 — `make contracts`.

- [x] **Task 3 — `DecisionTimerService`** (AC: #1, #2, #6, #11)
  - [x] Subtask 3.1 — `apps/cockpit-api/src/cockpit_api/services/decision_timer.py`.
  - [x] Subtask 3.2 — `apps/cockpit-api/tests/services/test_decision_timer.py` (≥ 9 cases).

- [x] **Task 4 — App lifecycle integration** (AC: #3)
  - [x] Subtask 4.1 — `lifespan` context manager wires the singleton.
  - [x] Subtask 4.2 — `get_decision_timer` dependency.
  - [x] Subtask 4.3 — On-shutdown `await timer.shutdown()`.

- [x] **Task 5 — Verification** (AC: #10)
  - [x] Subtask 5.1 — `make lint && make test` green.

## Dev Notes

### Architectural context (binding)

* [Source: `architecture.md#Demo Scope Addendum (2026-04-29)` § Caching/Pub-Sub] "In-memory state, single worker. No Redis."
* [Source: `architecture.md#Demo Scope Addendum (2026-04-29)` § Background work] "FastAPI background tasks."
* [Source: `architecture.md#Demo Scope Addendum (2026-04-29)` § Stack changes] timer is in-process per the cluster simplification.
* [Source: `architecture.md#Project-Specific Patterns` § P6 SSE Event Pattern] event names dot-delimited snake_case past-tense.
* [Source: `prd.md#Non-Functional Requirements` NFR-T1] 120s undo window is a product invariant; the impl approach (Redis vs in-process) is implementation detail.
* [Source: `apps/cockpit-api/src/cockpit_api/services/sse_registry.py`] `publish_safe` for SSE fan-out; the `seal_decision` callback (Story 7-7) consumes it.

### Critical pitfalls

1. **In-memory state is process-local.** Multi-worker uvicorn (`--workers 4`) would lose timers across workers. Demo runs with `--workers 1` (Story 1-2's `make dev` config). Verify the dev config; if multi-worker is enabled, document the mitigation: switch to Redis OR pin to single-worker.

2. **Cockpit-api restart loses in-flight timers.** Stories `pending_seal` cases remain in that state across restart, never seal, can't be undone via the timer. Recovery options:
   * Log every `schedule` call so an operator can manually seal.
   * On startup, scan for `pending_seal` cases and either auto-seal (assume timer would have elapsed during downtime) or revert to `decision_ready` (safer).
   * **For demo: do nothing** — restarts are rare, demo runs are short, dev can `make demo-reset` if it happens.
   Document the trade-off in a top-of-file docstring; a comment in this story's change log.

3. **`asyncio.create_task` reference must be retained.** Without the dict reference, the task could be GC'd before completing. The `_PendingTimer` dataclass is the retention. Don't refactor away the dict.

4. **`asyncio.CancelledError` MUST re-raise.** Python 3.11+ requires it. The except block in `_run_timer` re-raises explicitly. Without it, the task graph's cancellation propagation breaks.

5. **`time.monotonic()` not `time.time()`.** Wall-clock can jump backward (NTP); monotonic cannot. Timer correctness depends on monotonic.

6. **`schedule` is idempotent — re-scheduling cancels prior.** This handles the edge case of an officer who clicks Commit twice in rapid succession. Tests AC6 verify.

7. **`on_seal` callback runs INSIDE the timer task.** If it does heavy DB work, it can block the event loop briefly. For the demo's small scale this is fine; for a real platform it would be a queue dispatch.

8. **Don't write the `decision.sealed` ledger entry from inside `_run_timer`.** That mixes service-layer concerns. The `on_seal` callback (Story 7-7's `seal_decision`) is the right home — it has access to ledger/repo/sse infrastructure via dependency injection.

9. **Tests use `window_seconds=0.5` to keep pytest fast.** Don't actually sleep 120s in tests — that's 9 hours of CI burn for the full suite. Override the window via constructor parameter.

10. **`shutdown()` cancellation does NOT invoke `on_seal`** — pending decisions stay in `pending_seal` across restart. By design.

11. **Concurrent schedules race-safety**: the dict mutation is not under a lock, but Python's GIL guarantees `dict.pop` and `dict.setitem` are atomic. The `_run_timer`'s self-check (`if self._timers.get(case_id) is None or ...decision_id != decision_id`) handles the race where a new schedule cancels the old one mid-await. Tests AC6's "schedule twice" verifies.

12. **The case state transition `PENDING_SEAL → DECISION_READY` is the undo path.** Story 7-5 owns the undo endpoint that triggers this transition. This story only adds the transition to `ALLOWED_TRANSITIONS`.

13. **Removing `DECISION_READY → COMMITTED` is the breaking change.** Story 7-7's POST endpoint now writes `pending_seal`. If any older story's tests assert the direct transition, they break. Audit before editing.

### Story dependencies

* **Strict prereqs:** Story 2-1 (CaseState enum + ALLOWED_TRANSITIONS), Story 4-6 (`sse_registry.publish_safe`), Story 3-1 (LedgerWriter — used by Story 7-7's `seal_decision` callback that consumes this service).
* **Read by:** Story 7-7 (POST endpoint schedules timer + provides `seal_decision` callback), Story 7-5 (UndoPill reads `remaining_seconds`; undo endpoint calls `cancel`), Story 7-6 (seal animation listens for `decision.sealed` SSE event).

### Project Structure Notes

This story creates:
- `apps/cockpit-api/src/cockpit_api/services/decision_timer.py`
- `apps/cockpit-api/tests/services/test_decision_timer.py`

This story modifies:
- `packages/contracts/src/contracts/cases.py` — adds `PENDING_SEAL` state + transitions
- `packages/contracts/src/contracts/sse.py` — adds three event names
- `packages/contracts/tests/test_cases.py` — extend
- `packages/contracts/tests/test_sse.py` — extend
- `apps/cockpit-api/src/cockpit_api/main.py` (or app construction site) — lifespan timer wiring
- `apps/cockpit-ui/src/api-types.ts` — regenerated by `make contracts`

This story does NOT create:
- The POST /decisions endpoint (Story 7-7)
- The undo endpoint (Story 7-5)
- The `seal_decision` callback impl (Story 7-7's `decision_service.py`)
- The seal animation (Story 7-6)
- A Redis dependency (cut from demo)
- A persistence layer for in-flight timers (cut — accept restart loss)

### References

- [Source: `epics.md#Epic 7` § Story 7.8] original AC (Redis fail-closed cut → in-memory)
- [Source: `architecture.md#Demo Scope Addendum (2026-04-29)`] § Caching/Pub-Sub, § Background work
- [Source: `architecture.md#Project-Specific Patterns`] § P6 SSE
- [Source: `prd.md#Non-Functional Requirements` NFR-T1]
- [Source: `apps/cockpit-api/src/cockpit_api/services/sse_registry.py`] SSE publish surface
- [Source: `2-1-case-schema-and-state-machine.md`] CaseState + ALLOWED_TRANSITIONS to extend

### Demo verification protocol

Per AC11. Full end-to-end with Story 7-7's POST + 7-5's undo + 7-6's seal animation arrives only after those stories ship; this story ships the service in isolation with synthetic tests.

## Dev Agent Record

### Agent Model Used

(claude-opus-4-7 + Amelia persona, bmad-dev-story workflow)

### Debug Log References

### Completion Notes List

### File List

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-05-08 | Story 7.4 drafted. Demo replacement for bank-buyer Story 7.8: in-process asyncio.Task per pending decision; PENDING_SEAL case state added; three new SSE events (decision.sealed/.committed/.undone); restart loss documented as accepted demo limitation; Redis fail-closed policy + 1h auto-cancel + Arq queue all cut. |
