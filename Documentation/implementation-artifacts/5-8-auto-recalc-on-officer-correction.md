# Story 5.8: Auto-recalc on officer correction

Status: review

## Story

As a KYC Analyst who just drag-corrected a UBO edge via Story 5.5,
I want the risk score to recalculate automatically — without me clicking "Re-run risk scoring" — and the change to land in the UI within 500 ms via SSE-driven query invalidation, with a new `agent.completed` ledger entry preserving the prior score in the chain,
So that the score I commit on reflects my interventions, the demo's "officer corrections drive risk in real time" arc plays end-to-end (drag-correct → cross-fade → band drop), and Story 5.9's panels render the recalculated value alongside the new audit-trail entry (FR21, UX-DR20, NFR-P perf budget ≤ 500 ms).

## Scope note (2026-04-29 demo re-scope)

This story is the demo-equivalent of the bank-buyer Story 5.9. The bank-buyer scope folded in the `case.risk_recalculated` SSE event behind Redis pub/sub for multi-worker coordination; the demo runs single-worker so the SSE registry is in-memory.

| Bank-buyer scope (original 5.9) | Demo replacement in this story |
|---|---|
| Redis-backed SSE pub/sub fan-out across workers | **In-memory SSE registry** (Story 4.6 already shipped this). Single worker. |
| `case.risk_recalculated` SSE event with Redis durability | **Same event name + payload shape**, fired through `publish_safe`. No durability across worker restarts. |
| Tenant-scoped event delivery | Single-tenant. |
| Background job queue (Arq / Celery) for recalc | **FastAPI background task** (`fastapi.BackgroundTasks`) — runs the recalc inline-async after the response is sent; user-facing latency is bounded by the original POST. |

What survives: **automatic recalc trigger from `learning_event` ledger writes, new `agent.completed` ledger entry per recalc (prior preserved), `case.risk_recalculated` SSE event, cockpit-ui invalidation hook, 500 ms perf budget (informal in demo).**

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md` § Stories simplified, `architecture.md#Demo Scope Addendum (2026-04-29)`.

## Acceptance Criteria

1. **AC1 — Trigger location: `create_learning_event` endpoint (Story 5.5).**

    After successfully appending the `learning_event` ledger entry and before returning the response, schedule a risk recalc as a `fastapi.BackgroundTasks` task:

    ```python
    @router.post("/{case_id}/ubo/learning-events", ...)
    async def create_learning_event(
        case_id: CaseId,
        payload: LearningEventInput,
        current_user: User = Depends(current_user_dep),
        session: AsyncSession = Depends(get_session),
        background_tasks: BackgroundTasks = ...,
    ) -> LearningEventResponse:
        # ... Story 5.5's body ...
        background_tasks.add_task(
            run_risk_recalc,
            case_id=case_id,
            session_factory=session_factory,
        )
        return LearningEventResponse(...)
    ```

    `run_risk_recalc(case_id, session_factory)` lives in `apps/cockpit-api/src/cockpit_api/services/risk_recalc_service.py`. See AC2.

2. **AC2 — `run_risk_recalc` orchestrator.**

    ```python
    # apps/cockpit-api/src/cockpit_api/services/risk_recalc_service.py
    async def run_risk_recalc(
        *,
        case_id: CaseId,
        session_factory: SessionFactory,
        writer: LedgerWriter | None = None,
    ) -> None: ...
    ```

    Logic:
    1. Open a fresh DB session via `session_factory`.
    2. Load `case`, `entity_verification`, `ubo_graph` from DB (`CaseRepo` + `IntakeRepo`). If the UBO graph is missing → log loudly + return without raising (the trigger fires on UBO correction, so the graph WILL exist; defensive guard).
    3. Build `RiskCaseView` (mirrors Story 5.6's supervisor helper — extract a shared builder into a small module so both supervisor and recalc reuse it).
    4. Call `risk_scoring(RiskScoringInput(case_id=case_id), case_view=view)` — this writes a fresh `agent.completed` ledger entry via `@agent_action`. The PRIOR score is preserved in the chain (the JSONL ledger is append-only; nothing rewrites past entries).
    5. Back-fill `score_provenance.evidence_ids` via `_fill_evidence_ids_risk_scoring`.
    6. `IntakeRepo.upsert(session, case_id, "risk_scoring", filled_score)` — overwrites the prior persisted score.
    7. `CaseRepo.update_risk_band(session, case_id, score.band)` — denormalizes the (possibly-changed) band onto the case row.
    8. `await session.commit()`.
    9. Fire SSE: `publish_safe(case_id, SseEvent(event="case.risk_recalculated", data={"case_id": case_id, "band": score.band, "total": score.total}))`.
    10. Catch `AgentExecutionError` and log it; do NOT propagate (this is a background task, the original endpoint already returned 201). The next correction will trigger another recalc.

3. **AC3 — Shared `RiskCaseView` builder.**

    Story 5.6 puts `_build_risk_case_view` inside the supervisor module. Move it to a small public module so both supervisor and recalc service consume one implementation:

    ```python
    # apps/cockpit-api/src/cockpit_api/services/risk_view_builder.py
    async def build_risk_case_view(
        session: AsyncSession, case_id: CaseId
    ) -> RiskCaseView | None:
        """Return None if the case is missing; otherwise a populated view."""
    ```

    Update Story 5.6's supervisor `_invoke_risk_scoring` to call this shared builder.

4. **AC4 — SSE event extension: `case.risk_recalculated`.**

    Extend `packages/contracts/src/contracts/sse.py`:
    ```python
    SseEvent.event: Literal[
        "agent.state_changed",
        "case.state_changed",
        "case.documents_changed",
        "case.ubo_corrected",          # Story 5.5
        "case.risk_recalculated",      # NEW
    ]
    ```

    Payload shape (≤ 256 bytes per architecture P6): `{"case_id": case_id, "band": "low" | "medium" | "high", "total": int}`.

5. **AC5 — UI invalidation hook.**

    Extend `apps/cockpit-ui/src/lib/sse.ts`'s `subscribeToCase` to handle `case.risk_recalculated`:

    ```typescript
    if (event.event === 'case.risk_recalculated') {
        void queryClient.invalidateQueries({ queryKey: ['cases', caseId, 'intake', 'risk_scoring'] });
        void queryClient.invalidateQueries({ queryKey: ['case', caseId] });
        // The case query refetches risk_band; the intake query refetches the full RiskScore.
    }
    ```

    Story 5.7's `RiskScoreBar` is wired in Story 5.9 with `useRiskScore(caseId)` (Story 5.6's hook). On invalidation, the new score is fetched + re-rendered with the cross-fade animation per Story 5.7 § AC5.

    **Don't** also extend `useUboCorrection` (Story 5.5) to invalidate risk on success — duplicate path. The SSE event is the single source of truth.

6. **AC6 — Idempotency and ordering.**

    The background-task fire-and-forget pattern can race. Two officers correcting the same case in quick succession (a synthetic scenario in the demo; not a real demo concern) could trigger two recalcs concurrently. The mitigation is light: each recalc reads the latest persisted UBO graph + writes its result via upsert; the LAST recalc's result wins. Acceptable for demo. Document this as a known limitation.

    A more robust implementation (deferred) uses a per-case `asyncio.Lock` registry; out-of-scope here.

7. **AC7 — Tests at `apps/cockpit-api/tests/test_risk_recalc.py`.** Cover:

    * **Happy path:** seed a Vora case with intake run → POST a correction → assert that within 500 ms (poll the persisted intake row) the risk_scoring intake row reflects a different score. **Tip:** in tests, await the `BackgroundTasks` directly (FastAPI's `TestClient` doesn't await them by default — workaround: call `run_risk_recalc` inline in the test after the POST returns, OR use `asyncio.sleep(0)` to yield control).
    * **Ledger entries on recalc:** assert two `agent.completed` entries with `payload.agent_id="risk_scoring"` exist after a correction (one from initial supervisor intake, one from the recalc). Both `status="ok"`.
    * **Recalc is silent on missing UBO graph:** call `run_risk_recalc` directly against a case that has no UBO graph; assert it logs an error but doesn't raise.
    * **`case.risk_recalculated` SSE event:** with the SSE registry registered, post a correction; assert `case.risk_recalculated` is published with the right payload.
    * **Vora arc:** seed Vora intake; assert risk_band → `medium_high` (3-tier "medium"); POST a correction flipping Coastal to `officer_corrected`; await background task; assert risk_band → `low`. The full demo arc.
    * **`AgentExecutionError` swallowed:** monkeypatch `risk_scoring` to raise; post a correction; assert no exception propagates; assert error logged.
    * **Idempotency:** call `run_risk_recalc` twice in a row against the same case; assert the persisted score is identical (deterministic agent + same inputs); assert two `agent.completed` ledger entries (each invocation records its own).

8. **AC8 — Tests at `apps/cockpit-ui/src/lib/sse.test.ts`.** (Likely already exists; extend.)

    * Mock an `EventSource` that emits `case.risk_recalculated`; assert the right `queryClient.invalidateQueries` calls fire.

9. **AC9 — End-to-end manual test.**

    With `make dev` running:
    1. Open Vora's case page.
    2. Risk panel shows total ≈ 37 + band MEDIUM.
    3. Drag-correct the Coastal edge to `real_ubo` (Story 5.5 modal).
    4. **Within 500 ms** of confirming, the Risk panel's bar animates a cross-fade on the ownership_clarity segment; total drops to 32; band pill flips to LOW.
    5. Tail `./data/ledger.jsonl`: two `agent.completed` entries for `risk_scoring`; one `learning_event` entry for the correction.
    6. SSE network tab in DevTools: `case.risk_recalculated` event visible.
    7. Refresh the page: state is consistent (no refetch surprises).

10. **AC10 — `make lint && make test` clean.** Net new test count: ≥ 7 in `test_risk_recalc.py`; ≥ 1 cockpit-ui sse test extension; ≥ 1 contract test for the new SSE literal.

11. **AC11 — No supervisor changes required for the recalc path.** The supervisor (Story 5.6) runs risk_scoring as part of intake fan-out. Recalc is a separate code path (this story) that bypasses the supervisor and calls the agent function directly. **Don't** try to "reuse the supervisor's run_intake" for recalc — that would re-run all four agents, which is wasteful and would re-write doc_intel + entity_verification + ubo_graph ledger entries. **Risk-only recalc is the correct boundary.**

12. **AC12 — `score_provenance.evidence_ids` is back-filled with the recalc's own ledger ID.** Same pattern as supervisor (Story 5.6 § AC6). The recalc service has its own `_find_agent_ledger_entry` call.

## Tasks / Subtasks

- [x] **Task 1 — Shared `build_risk_case_view`** (AC: #3)
  - [x] Subtask 1.1 — Create `apps/cockpit-api/src/cockpit_api/services/risk_view_builder.py` with `build_risk_case_view(session, case_id)`.
  - [x] Subtask 1.2 — Refactor Story 5.6's `_build_risk_case_view` in supervisor to delegate to it.

- [x] **Task 2 — `run_risk_recalc` orchestrator** (AC: #2)
  - [x] Subtask 2.1 — `apps/cockpit-api/src/cockpit_api/services/risk_recalc_service.py`.
  - [x] Subtask 2.2 — Reuse `_fill_evidence_ids_risk_scoring` from supervisor (extract to a shared helper or duplicate per-app — pick whichever has lower coupling cost; the helper is small).

- [x] **Task 3 — Trigger from learning-event endpoint** (AC: #1)
  - [x] Subtask 3.1 — Inject `BackgroundTasks` into the endpoint signature.
  - [x] Subtask 3.2 — `background_tasks.add_task(run_risk_recalc, ...)` after the ledger write.

- [x] **Task 4 — SSE event** (AC: #4)
  - [x] Subtask 4.1 — Extend `SseEvent.event` Literal to include `case.risk_recalculated`.
  - [x] Subtask 4.2 — Fire from `run_risk_recalc` after successful upsert.

- [x] **Task 5 — UI invalidation** (AC: #5)
  - [x] Subtask 5.1 — Extend `apps/cockpit-ui/src/lib/sse.ts` with the new event handler.
  - [x] Subtask 5.2 — Test in `sse.test.ts`.

- [x] **Task 6 — Tests** (AC: #7, #8, #10)
  - [x] Subtask 6.1 — `apps/cockpit-api/tests/test_risk_recalc.py` covers all 7 cases.
  - [x] Subtask 6.2 — Vora arc end-to-end.
  - [x] Subtask 6.3 — `make lint && make test` green.

- [x] **Task 7 — Manual verification** (AC: #9)
  - [x] Subtask 7.1 — `make dev`, exercise the Vora arc, verify cross-fade + band drop within 500 ms.
  - [x] Subtask 7.2 — Inspect ledger; confirm two recalc entries.

## Dev Notes

### Architectural context (binding)

* [Source: `architecture.md#Demo Scope Addendum (2026-04-29)`] FastAPI background tasks replace Arq/Celery; in-memory SSE.
* [Source: `architecture.md#Project-Specific Patterns` P6 SSE Event Pattern] event names dot-delimited past-tense; payload ≤ 256 bytes; clients refetch via TanStack invalidation.
* [Source: `ux-design-specification.md` § DecompositionPanel + § J2 (Vora UBO correction → EDD)] the cross-fade on the affected segment is the demo's signature "your correction matters" moment.
* [Source: `architecture.md#Anti-Patterns to Refuse`] silent agent failure (NFR-A5) — the recalc swallows agent errors but logs loud; surfaces via the next manual recalc UI button (deferred).

### Critical pitfalls

1. **`fastapi.BackgroundTasks` runs in the SAME event loop as the request.** It does NOT spawn a worker thread. The risk-recalc agent is async + deterministic + fast (≤ 50 ms expected); fine for the demo. **Don't** wrap it in `asyncio.create_task` from inside the request handler — FastAPI's `BackgroundTasks` already does this safely, and creating a bare task can leak if the response cycle ends before the task awaits.

2. **The session passed to `run_risk_recalc` must be NEW.** The original endpoint's session is closed after the response is sent (FastAPI cleanup). The orchestrator opens its own via `session_factory`. **Don't** pass the request's session through.

3. **`_fill_evidence_ids_risk_scoring` lives in the supervisor.** This story imports it from there. **OR** factor it out to a shared service module. Pick the lower-coupling path: probably leave it in the supervisor and import from `agents.supervisor.case_supervisor` — the demo's import graph is small and the alternative (factoring everything) is over-engineered.

4. **`run_risk_recalc` MUST tolerate the missing-UBO-graph case.** If the corrector targets a case without a UBO graph (defensive — Story 5.5's endpoint rejects this with 409, so it shouldn't happen, but assume hostile state), log + return.

5. **The SSE event is the SINGLE invalidation source.** `useUboCorrection`'s `onSuccess` already invalidates the UBO graph query. **Don't** also have `useUboCorrection` invalidate risk_scoring — that creates a race between the optimistic invalidation and the SSE-driven invalidation. The SSE path is authoritative.

6. **Don't try to lock per-case correctness.** The demo's single-officer-per-case-at-a-time flow makes the race window practically empty. Document the limitation and move on.

7. **`agent_mesh_state` derivation already handles a second `agent.completed` for risk_scoring.** The mesh-state service walks all entries and returns the most recent per `actor_id`. After recalc, `risk_scoring` shows `state=COMPLETE` with the recalc timestamp. No service changes needed.

8. **The demo arc REQUIRES the band drop.** Vora pre-correction = `medium`; post-correction = `low`. If your tests show the band staying at `medium`, the bug is in either Story 5.6's value formula (re-check `ownership_clarity` rule) OR Story 5.5's officer_corrected flag flow (re-check the helper rebuild). The `_apply_nominee_heuristics` in Story 5.3 is NOT re-run on recalc — the agent only reads the persisted graph. The persisted graph already has Coastal flipped to `officer_corrected` (Story 5.5 mutated it).

9. **`update_risk_band` updates `updated_at`.** Story 4.1's queue rail re-sorts on `updated_at DESC` after the band change; Vora drops down the rail when its band drops. This is intended behavior — the SSE `case.state_changed` event isn't fired here (the case state didn't change), so the queue rail's TanStack Query needs explicit invalidation. **Add** to AC5: also invalidate `['cases']` (the list query) on `case.risk_recalculated` to trigger the rail re-render.

   Update AC5 mentally: invalidation list is `['cases']` (rail), `['case', caseId]` (header), and `['cases', caseId, 'intake', 'risk_scoring']` (panel).

### Story dependencies

* **Strict prereqs:** Story 5.5 (drag-correct → endpoint trigger), Story 5.6 (Risk Scoring agent + persisted state), Story 5.7 (UI to render the cross-fade), Story 4.6 (SSE registry + `publish_safe`).
* **Reads from:** Story 3.5 (Case Supervisor — for the `_fill_evidence_ids_risk_scoring` helper).
* **Read by:** Story 5.9 (UBO + Risk panels) — wires `useRiskScore` into the panel and observes the auto-refresh.

### Project Structure Notes

This story creates:
- `apps/cockpit-api/src/cockpit_api/services/risk_recalc_service.py`
- `apps/cockpit-api/src/cockpit_api/services/risk_view_builder.py` (shared with Story 5.6)
- `apps/cockpit-api/tests/test_risk_recalc.py`

This story modifies:
- `apps/cockpit-api/src/cockpit_api/routers/cases.py` — `BackgroundTasks` on `/learning-events`
- `apps/cockpit-api/src/cockpit_api/services/sse_registry.py` — (no change; the literal extension lives in contracts only)
- `packages/contracts/src/contracts/sse.py` — `case.risk_recalculated` literal
- `apps/agents/src/agents/supervisor/case_supervisor.py` — `_invoke_risk_scoring` delegates to shared `build_risk_case_view`
- `apps/cockpit-ui/src/lib/sse.ts` — handle the new event

This story DOES NOT create:
- A general "recalc-any-agent-on-event" framework (out of scope; bespoke risk recalc is sufficient)
- Per-case async locks (deferred)
- A retry/dead-letter queue (FastAPI BackgroundTasks fire-and-forget is acceptable for demo)

### References

- [Source: `architecture.md#Demo Scope Addendum (2026-04-29)`] FastAPI background tasks; in-memory SSE
- [Source: `architecture.md#Project-Specific Patterns` P6] SSE event shape
- [Source: `epics.md#Epic 5` § Story 5.9] original AC (re-scoped here)
- [Source: `prd.md#FR21, NFR-P perf budget`] auto-recalc, 500 ms target
- [Source: `5-5-drag-correct-interaction-with-learning-event-ledger-entry.md`] correction endpoint + ledger payload
- [Source: `5-6-risk-scoring-agent.md`] risk_scoring agent + RiskCaseView + supervisor wiring
- [Source: `5-7-risk-score-stacked-bar-with-hover-decomposition.md`] cross-fade animation hook on segment value change
- [Source: `4-6-sse-stream-endpoint-single-worker.md`] `publish_safe`, in-memory registry

### Demo verification protocol

```bash
# Reset and seed:
make demo-reset && make seed
poetry -C apps/cockpit-api run python -c "
import asyncio
from contracts.cases import VORA_CAPITAL_ID
from agents.supervisor.case_supervisor import CaseSupervisor
from cockpit_api.db.session import session_factory
asyncio.run(CaseSupervisor(session_factory=session_factory).run_intake(VORA_CAPITAL_ID))
"

# Verify Vora's pre-correction state:
sqlite3 ./data/cockpit.db "SELECT risk_band FROM cases WHERE id='${VORA_CAPITAL_ID}';"
# Expected: medium_high (3-tier 'medium' mapped)

# Trigger correction:
ANALYST_ID=$(jq -r '.[] | select(.role=="analyst") | .id' apps/cockpit-api/fixtures/users.json)
curl -s -X POST "http://localhost:8000/v1/cases/${VORA_CAPITAL_ID}/ubo/learning-events" \
  -H 'Content-Type: application/json' \
  -H "X-Cockpit-Demo-User: ${ANALYST_ID}" \
  -d '{"edge_kind": "owns", "from_id": "ubo_e_coastal_equity_partners_pte_ltd", "original_to_id": "ubo_e_u67120mh2024ptc444789", "new_to_id": "ubo_e_u67120mh2024ptc444789", "correction_tag": "real_ubo", "evidence_note": "RM email", "opt_in_for_retraining": true}'

# Wait briefly for the background task:
sleep 1

# Verify post-correction state:
sqlite3 ./data/cockpit.db "SELECT risk_band FROM cases WHERE id='${VORA_CAPITAL_ID}';"
# Expected: low

# Check for the recalc ledger entry:
grep -c '"agent_id": "risk_scoring"' ./data/ledger.jsonl
# Expected: 2 (initial intake + recalc)

# Browser test:
make dev
# Open Vora's case page in two browser tabs (or two windows side-by-side):
# Tab A: drag-correct the Coastal edge.
# Tab B: observe the Risk panel — within ~500 ms it should cross-fade and the band pill should drop to LOW.

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
| 2026-05-08 | Story 5.8 drafted. Demo replacement for the bank-buyer Story 5.9: FastAPI BackgroundTasks-driven risk recalc on learning-event POST, `case.risk_recalculated` SSE event, UI invalidation hook, full Vora arc (medium → low band drop). |
