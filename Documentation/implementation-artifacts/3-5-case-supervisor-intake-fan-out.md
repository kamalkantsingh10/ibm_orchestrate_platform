# Story 3.5: Case Supervisor (intake fan-out)

Status: review

## Story

As the platform,
I want a Case Supervisor agent that — when triggered for a case in `intake_scheduled` state — fans out the intake mesh (Document Intelligence today; Entity Verification, UBO, Risk, Screening land in later epics), waits for results, fills the agent's `evidence_ids` from the just-written ledger entries, persists the typed intake outcomes for the API/UI, transitions the case to `decision_ready` on full success or `escalated` on agent failure, and emits a `case.intake_completed` (or `case.intake_blocked`) ledger event,
So that on case open the analyst sees structured intake data with full provenance and the demo's "instant canvas" UX promise (FR3, FR14) holds, and any agent failure is named, blocked, and surfaced to the analyst rather than silenced (FR55, NFR-A5).

## Scope note (2026-04-29 demo re-scope)

This story is the demo-equivalent of the bank-buyer Story 3.10. The supervisor is real; the fan-out is a single agent for now (Document Intelligence — Story 3-4); subsequent agents land in later epics and will plug in via the same supervisor pattern.

| Bank-buyer scope (original 3.10) | Demo replacement in this story |
|---|---|
| Triggered automatically on `POST /v1/cases` (Story 2.2) which is followed by an Arq worker that calls the supervisor | **Triggered manually:** by `make seed` post-step (the seeder runs intake for each fresh fixture case) and by a new `POST /v1/cases/{case_id}/intake` endpoint for ad-hoc re-runs during demo. No Arq, no queue. |
| Fans out: Document Intelligence → Entity Verification → UBO → Screening → Risk → Writing | **Fans out: Document Intelligence only.** Entity Verification + UBO + Risk + Screening agents land in Epics 5–6 and will be added to the supervisor's fan-out list at that time. Writing agent lands in Epic 7. The supervisor's design accommodates additions via a single registry list. |
| Multi-tenant (`tenant_id` enforced) | Single-tenant demo; no `tenant_id` parameter. |
| Webhook + SSE event on `decision_ready` transition | **In-memory pub/sub stub:** the supervisor calls a `notify(case_id, event_name, payload)` hook; for the demo this hook logs to stdout. The real SSE wiring lands in Story 4-6 (single-worker SSE). Webhooks were cut. |
| Agent failure → `intake_blocked` state with the failed agent named | **Same semantics, simplified state name:** the demo uses the existing `escalated` state from Story 2-1's state machine (no new state; `escalated` is the catch-all for "needs human attention"). The case's `customer_metadata.extra` gains a `blocked_agent: <name>` and `block_reason: <message>` pair that the UI will render. The bank-buyer scope's distinct `intake_blocked` state is deferred — adding it would require a Story 2-1 amendment to the state-machine ALLOWED_TRANSITIONS, which is out of scope here. |

What survives: **the supervisor IS the only path that invokes agents (per architecture's Agent boundary), it fills `evidence_ids` from ledger entries, it catches `AgentExecutionError` and surfaces it as a typed escalation, and it transitions case state atomically.** Those are load-bearing for the demo's "instant canvas" + "no silent failures" UX.

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md`, `architecture.md#Demo Scope Addendum (2026-04-29)`, and `architecture.md#Architectural Boundaries` (Agent boundary).

## Acceptance Criteria

1. **AC1 — `CaseSupervisor` lives at `apps/agents/src/agents/supervisor/case_supervisor.py`.** Public surface:

    ```python
    class CaseSupervisor:
        def __init__(self, *, session_factory: SessionFactory, intake_repo: IntakeRepo, notify: NotifyHook | None = None) -> None: ...
        async def run_intake(self, case_id: CaseId) -> CaseIntakeOutcome: ...
    ```

    `SessionFactory` is `Callable[[], AsyncContextManager[AsyncSession]]` — typically `cockpit_api.db.session.get_session` wrapped, or for tests a direct factory bound to the test engine. `IntakeRepo` is the new repo introduced in this story (AC4) for storing per-agent intake results. `NotifyHook` is `Callable[[CaseId, str, dict[str, Any]], Awaitable[None]] | None` — the in-memory pub/sub stub from the scope note.

    `run_intake(case_id)` returns a `CaseIntakeOutcome` (AC5) describing the run's full result. The function does NOT raise on agent failure; it returns an outcome with `status="blocked"` and the supervisor records the escalation. **Caller-visible exceptions only escape on infrastructure failures** (DB connection, ledger writer disk full) — those bubble naturally.

2. **AC2 — Supervisor flow.** When `run_intake(case_id)` is called:
    1. Load the case via `CaseRepo.get`. If `None` → raise `CaseNotFoundError(case_id)` (a custom subclass of `RuntimeError`; defined in this story's module).
    2. Validate the case is in `intake_scheduled` state. If not → raise `CaseNotIntakeReadyError(case_id, current_state)` so callers can decide whether to retry. The seed script tolerates this error (idempotent re-runs); the API endpoint surfaces it as 409 Conflict.
    3. Resolve `document_refs` from `case.customer_metadata.extra.get("document_refs", [])`. If empty list, skip Document Intelligence and proceed to step 5 with an empty intake.
    4. **Fan out:** call `await document_intelligence(DocumentIntelligenceInput(case_id=case_id, document_refs=document_refs))` wrapped in a `try/except AgentExecutionError`:
        - On success: capture the returned `DocumentIntelligenceOutput`. **Read back the just-written ledger entry** for the agent — see AC6 — and fill `evidence_ids` on each `ExtractedField.value.provenance` with the agent's ledger entry ID. This produces the "post-fill" output. Persist via `IntakeRepo.upsert(case_id, agent_id="document_intelligence", output=post_fill_output)`.
        - On `AgentExecutionError`: capture `err.original` and `err.agent_id`. Build a `CaseIntakeOutcome(status="blocked", failed_agent=err.agent_id, error_message=str(err.original)[:500], ...)`. Persist nothing for this agent's intake. Skip step 5; go to step 7.
    5. **Transition the case:** `await CaseRepo.transition(case_id, CaseState.DECISION_READY)`. Inside the same DB session as the persistence above (transactional — see AC7).
    6. **Append a `case.intake_completed` ledger entry** (`actor_type=ActorType.SYSTEM`, `actor_id="case_supervisor"`, `case_id=case_id`, `action="case.intake_completed"`, `payload={"agents": ["document_intelligence"], "fields_extracted": <count>}`). Then call `notify(case_id, "case.intake_completed", payload)` if a hook is configured. Build and return `CaseIntakeOutcome(status="completed", ...)`.
    7. **Block path:** transition the case to `CaseState.ESCALATED` via `CaseRepo.transition`. Patch `case.customer_metadata.extra` to merge in `{"blocked_agent": <name>, "block_reason": <message>}`. (Story 2-1's `Case` is `frozen=True`; the patch must rebuild the case via `CaseRepo` — see AC4 for an `add_block_marker` helper.) Append `case.intake_blocked` ledger entry. Notify. Return `CaseIntakeOutcome(status="blocked", ...)`.

3. **AC3 — Fan-out registry.** The list of intake agents to call is **not** hardcoded inline in `run_intake`. It lives in a module-level constant:

    ```python
    INTAKE_AGENTS: Final[tuple[IntakeAgentSpec, ...]] = (
        IntakeAgentSpec(
            name="document_intelligence",
            invoke=_invoke_document_intelligence,  # async wrapper that builds the input and calls the agent
            requires=lambda case: bool(case.customer_metadata.extra.get("document_refs")),
        ),
        # Epics 5–6 will append: entity_verification, ubo_graph, screening, risk_scoring
    )
    ```

    `class IntakeAgentSpec(BaseModel, frozen=True)`: `name: str`, `invoke: Callable[..., Awaitable[Any]]` (Pydantic accepts non-validated callables via `arbitrary_types_allowed=True` or just store as a raw attribute outside the BaseModel — the dev picks the cleaner pattern), `requires: Callable[[Case], bool]`. The supervisor iterates the registry in order; for each spec, if `requires(case)` is True, it invokes; otherwise it skips with a "skipped: missing inputs" log line.

    **Why a registry:** when Epic 5 lands Entity Verification, the dev for that story appends one `IntakeAgentSpec` to the tuple. No supervisor logic changes. This is the demo's expression of the bank-buyer scope's "fan-out" architecture, scaled down.

4. **AC4 — `IntakeRepo` lives at `apps/cockpit-api/src/cockpit_api/repositories/intake_repo.py`.** Persists per-agent intake results so the API/UI can read them after intake completes.

    Schema — new SQLAlchemy ORM model `IntakeRow` in `apps/cockpit-api/src/cockpit_api/db/models.py`:
    - `case_id: Mapped[str]` — `String(32)`, FK-style reference to `cases.id` (no actual FK constraint, matching Story 2-1's discipline)
    - `agent_id: Mapped[str]` — `String(64)`, e.g., `"document_intelligence"`
    - `output_json: Mapped[dict[str, Any]]` — `JSON`, full `model_dump(mode="json")` of the agent's typed output
    - `recorded_at: Mapped[datetime]` — `DateTime(timezone=True)`, `server_default=func.now()`
    - **Composite primary key:** `(case_id, agent_id)`. Upsert semantics: re-running intake for a case overwrites the previous row. Add an index `ix_intake_results_case_id` on `case_id` for the per-case query.

    A new Alembic migration `<rev>_create_intake_results.py` lands the table. Same dialect-portability discipline as Story 2-1 (use `sa.JSON()` not `JSONB`, `sa.String(N)` not native UUID).

    `CaseRepo` gains one new method: `async def add_block_marker(session, case_id, blocked_agent, block_reason) -> Case` — loads the row, mutates `customer_metadata` JSON column to merge the two new keys, commits, returns the updated `Case`. Tested in Story 3-5's tests.

    Repo public surface for `IntakeRepo`:
    - `async def upsert(session, case_id, agent_id, output: BaseModel) -> None` — INSERT OR REPLACE; serializes via `output.model_dump(mode="json")`
    - `async def get_by_case(session, case_id) -> dict[str, dict]` — returns `{agent_id: output_json}` for all rows matching `case_id`
    - `async def get_one(session, case_id, agent_id) -> dict | None` — returns the JSON dict or `None`

    Consumer-side typing happens at the API boundary (Story 3-6 will validate the dict against `DocumentIntelligenceOutput.model_validate`).

5. **AC5 — `CaseIntakeOutcome` contract.** Lives in `packages/contracts/src/contracts/case_supervisor.py`:

    ```python
    class CaseIntakeOutcome(BaseModel):
        model_config = {"frozen": True}
        case_id: CaseId
        status: Literal["completed", "blocked"]
        agents_run: list[str]                    # names of agents that ran (success or fail)
        failed_agent: str | None = None          # set when status == "blocked"
        error_message: str | None = None         # truncated to 500 chars
        fields_extracted: int = 0                # rolled up across all successful agents
        completed_at: datetime
    ```

    Re-export from `__init__.py`. Used as the return type of `run_intake` and the body of the `POST /v1/cases/{case_id}/intake` response.

6. **AC6 — `evidence_ids` post-fill from the just-written ledger entry.** After `document_intelligence(...)` returns successfully, the agent's `agent.completed` ledger entry has been appended (by `@agent_action`). The supervisor must:
    1. `entries = await LedgerReader(...).read_for_case(case_id)`
    2. Find the most recent entry where `actor_id == "document_intelligence"` and `payload.kind == "agent_action"` and `payload.status == "ok"` — call this `agent_entry`
    3. For each `ExtractedField` in the agent's output, replace `evidence_ids=[]` with `evidence_ids=[agent_entry.id]`
    4. Persist the post-fill output via `IntakeRepo.upsert`

    **Edge case:** if the read finds no matching entry (impossible in practice, since the decorator just wrote it — but defensive), log an ERROR and proceed with empty `evidence_ids`. The intake is still considered successful — the missing evidence link is a known soft-failure mode, not a hard error.

    **Helper function:** `_fill_evidence_ids(output: DocumentIntelligenceOutput, ledger_entry_id: LedgerEntryId) -> DocumentIntelligenceOutput` — pure function that returns a new output with filled IDs (frozen models require copy-on-write via `model_copy(update=...)`). Unit-tested separately.

7. **AC7 — Atomic transition + persistence.** The case state transition AND the `IntakeRepo.upsert` happen inside the same DB session/transaction. If the transition fails (illegal transition → `CaseStateTransitionError`), the upsert rolls back. If the upsert fails (DB error), the transition rolls back. The ledger entry is written AFTER the DB transaction commits — if the ledger write fails, the DB state is already durable, but the ledger is missing one entry. **Decision (binding):** log the ledger write failure at ERROR; do NOT roll back the DB. The audit trail will be incomplete but the user-visible state is correct. Story 9-1 (Audit Trail Timeline) will surface "ledger write failure" gaps when it lands.

8. **AC8 — Triggering: `make seed` post-step.** Edit `apps/cockpit-api/scripts/seed_dev.py`. After the existing `_seed` returns, AND after the bootstrap ledger entry from Story 3-1 is written, run intake for each freshly-inserted case:

    ```python
    if cases_seeded:  # only if the cases_seeded boolean from Story 3-1 was True
        from agents.supervisor.case_supervisor import CaseSupervisor
        supervisor = CaseSupervisor(session_factory=..., intake_repo=IntakeRepo, notify=None)
        for case in fixtures:
            try:
                outcome = await supervisor.run_intake(case.id)
                print(f"  intake {case.id} → {outcome.status} ({outcome.fields_extracted} fields)")
            except (CaseNotFoundError, CaseNotIntakeReadyError) as e:
                print(f"  intake {case.id} → skipped ({e})")
    ```

    **Idempotency:** re-running `make seed` against an already-seeded DB → `cases_seeded` is False → intake is skipped. `make demo-reset && make seed` → `cases_seeded` True → intake runs.

9. **AC9 — Triggering: `POST /v1/cases/{case_id}/intake` endpoint.** New router action at `apps/cockpit-api/src/cockpit_api/routers/cases.py`:

    ```python
    @router.post("/{case_id}/intake", response_model=CaseIntakeOutcome, dependencies=[Depends(get_current_user)])
    async def run_intake(case_id: CaseIdPath, session: AsyncSession = Depends(get_session)) -> CaseIntakeOutcome:
        ...
    ```

    Returns the typed `CaseIntakeOutcome`. Maps internal exceptions to HTTP per the existing RFC 7807 handler:
    - `CaseNotFoundError` → 404
    - `CaseNotIntakeReadyError` → 409 Conflict
    - Any other exception → 500 (existing handler)

    Wires the supervisor with `intake_repo=IntakeRepo`, `session_factory` bound to the request's session, and `notify=None` (single-worker stdout for now).

    **Decision point for the dev:** the supervisor was specified as a class with a constructor; one might be tempted to make it a singleton instantiated at app startup. **Bind: instantiate per-request inside the route handler** — the cost is negligible (constructor is no-op), and it keeps dependency injection simple. If a future story needs singleton semantics (e.g., to share connection pools across requests), refactor then.

10. **AC10 — Tests cover happy path, agent failure, idempotency, missing case, wrong state, post-fill.** Pytest specs:

    `apps/agents/tests/test_case_supervisor.py`:
    - **Happy path:** seed an in-memory DB with one case in `intake_scheduled`, run `supervisor.run_intake(case_id)`; assert outcome `status="completed"`, `agents_run=["document_intelligence"]`, `fields_extracted > 0`; assert `IntakeRepo.get_one(case_id, "document_intelligence")` returns a non-None dict that round-trips into `DocumentIntelligenceOutput`; assert each `ExtractedField.value.provenance.evidence_ids` is `[<agent_entry_id>]` (not empty); assert case state is now `decision_ready`.
    - **Agent failure:** monkeypatch `document_intelligence` to raise `AgentExecutionError`; run intake; assert outcome `status="blocked"`, `failed_agent="document_intelligence"`, `error_message` contains the original error's message; assert case state is now `escalated`; assert `case.customer_metadata.extra["blocked_agent"] == "document_intelligence"` after `CaseRepo.get`.
    - **Empty document_refs:** seed a case with `document_refs=[]`; run intake; assert `outcome.agents_run == []` (or `["document_intelligence"]` with `fields_extracted=0` — the dev picks; document choice); assert case still transitions to `decision_ready` (no agent ran, no failure, intake is trivially complete).
    - **Missing case:** call `run_intake("case_01_does_not_exist...")`; assert `CaseNotFoundError` is raised.
    - **Wrong state:** seed a case in `decision_ready` (i.e., already past intake); call `run_intake`; assert `CaseNotIntakeReadyError` is raised.
    - **Idempotency on re-run:** run intake twice on the same fresh case. **Decision point:** the second run will fail with `CaseNotIntakeReadyError` because the first run transitioned to `decision_ready`. That's the correct semantics — intake is a one-time operation per case. The seeder's idempotency check prevents the issue. Test asserts the second call raises `CaseNotIntakeReadyError`.
    - **Post-fill helper unit test:** `_fill_evidence_ids(output, "led_TESTID...")` — assert all `evidence_ids` lists are exactly `["led_TESTID..."]`.
    - **Ledger entry on success:** assert exactly two `actor_type=system` ledger entries were written by the supervisor: `case.intake_completed`. (The agent's `agent.completed` is separate — written by the decorator, not the supervisor.)
    - **Ledger entry on failure:** assert one `case.intake_blocked` entry written.
    - **Notify hook called:** pass a stub async `notify` that records calls; run intake; assert it was called once with `(case_id, "case.intake_completed", {...})`.

    `apps/cockpit-api/tests/test_intake_repo.py`:
    - `upsert` then `get_one` round-trip
    - `upsert` twice with same `(case_id, agent_id)` → `get_one` returns the second value (replace semantics)
    - `get_by_case` with two agents → returns dict with both keys

    `apps/cockpit-api/tests/test_cases_intake_route.py`:
    - `POST /v1/cases/{id}/intake` happy path against a TestClient → 200 + outcome JSON matching `CaseIntakeOutcome` schema
    - Same against a non-existent case → 404 RFC 7807
    - Same against a case already in `decision_ready` → 409 RFC 7807

11. **AC11 — `make demo-reset && make seed` runs intake automatically.** End-to-end smoke. After `make seed` returns 0:
    - `./data/cockpit.db` has 3 cases, all in `decision_ready` state
    - `intake_results` table has 3 rows (one per case, all with `agent_id="document_intelligence"`)
    - `./data/ledger.jsonl` has at minimum 11 lines: 1 `ledger.initialized` + 3 `case.seeded` + 3 `agent.completed` (Doc Intelligence) + 3 `case.intake_completed` (supervisor) + (optional intermediate logs depending on impl). Minimum required entries are precisely 1 + 3 + 3 + 3 = 10 lines.

12. **AC12 — `make migrate` + `make seed` + `make test` + `make lint` clean.** New Alembic migration applies cleanly to fresh SQLite. New test count adds at least: 10+ in `test_case_supervisor.py`, 3+ in `test_intake_repo.py`, 3+ in `test_cases_intake_route.py`, 2+ in updated `test_seed_dev.py`. mypy strict passes. `make lint-agents-p4` (Story 3-2) passes — supervisor calls the agent (which the decorator wraps), not `LedgerWriter.append` directly.

## Tasks / Subtasks

- [x] **Task 1 — Author the `CaseIntakeOutcome` contract** (AC: #5)
  - [x] Subtask 1.1 — Create `packages/contracts/src/contracts/case_supervisor.py` with `class CaseIntakeOutcome` per AC5. Add the `tzinfo is not None` validator on `completed_at`.
  - [x] Subtask 1.2 — Re-export from `__init__.py` (alphabetical order).
  - [x] Subtask 1.3 — Author `packages/contracts/tests/test_case_supervisor.py` with happy-path round-trip + `status="blocked"` requires `failed_agent` (use a `@model_validator` to enforce; document in AC5 if you change AC5).

- [x] **Task 2 — Author `IntakeRepo` + Alembic migration + `CaseRepo.add_block_marker`** (AC: #4)
  - [x] Subtask 2.1 — Edit `apps/cockpit-api/src/cockpit_api/db/models.py`: add `class IntakeRow(Base)` with the columns from AC4. Composite PK via `__table_args__ = (PrimaryKeyConstraint("case_id", "agent_id"),)` or via `mapped_column(primary_key=True)` on each.
  - [x] Subtask 2.2 — Generate the migration: `cd apps/cockpit-api && DATABASE_URL=... poetry run alembic revision --autogenerate -m "create intake_results"`. Hand-inspect for SQLite-portability per Story 2-1 Pitfall #1. Run `make migrate` to apply.
  - [x] Subtask 2.3 — Create `apps/cockpit-api/src/cockpit_api/repositories/intake_repo.py` with `class IntakeRepo` and the three methods from AC4. Use SQLite's `INSERT OR REPLACE` (raw SQL — Story 2-1 sets the precedent for raw `INSERT OR IGNORE`); or use SQLAlchemy's `insert(IntakeRow).on_conflict_do_update(...)` if portability to Postgres matters (it does for revival). Prefer `on_conflict_do_update` keyed to the composite PK.
  - [x] Subtask 2.4 — Edit `case_repo.py`: add `async def add_block_marker(session, case_id, blocked_agent, block_reason) -> Case`. Loads, merges into `customer_metadata.extra` (preserve existing keys), commits, returns the updated `Case`.
  - [x] Subtask 2.5 — Author `apps/cockpit-api/tests/test_intake_repo.py` with the AC10 cases.

- [x] **Task 3 — Author the `CaseSupervisor`** (AC: #1, #2, #3, #6, #7)
  - [x] Subtask 3.1 — Create `apps/agents/src/agents/supervisor/case_supervisor.py`. Define `CaseNotFoundError(RuntimeError)` and `CaseNotIntakeReadyError(RuntimeError)`. Both store `case_id` (and `current_state` for the latter).
  - [x] Subtask 3.2 — Define `class IntakeAgentSpec` (TypedDict or dataclass — Pydantic struggles with raw callables; **bind: dataclass with frozen=True**). Define `INTAKE_AGENTS: Final[tuple[IntakeAgentSpec, ...]]` per AC3 with one entry for Document Intelligence.
  - [x] Subtask 3.3 — Implement `_invoke_document_intelligence(case: Case) -> DocumentIntelligenceOutput`: builds `DocumentIntelligenceInput(case_id=case.id, document_refs=case.customer_metadata.extra.get("document_refs", []))`, calls `await document_intelligence(input)`, returns the output. Wraps no exceptions — the decorator already raises `AgentExecutionError`.
  - [x] Subtask 3.4 — Implement `class CaseSupervisor` with the constructor + `run_intake` method per AC1, AC2. Uses `session_factory` to acquire a session inside the method. Atomic transaction per AC7.
  - [x] Subtask 3.5 — Implement `_fill_evidence_ids(output, ledger_entry_id) -> DocumentIntelligenceOutput` — pure function. Use `output.model_copy(update=...)` recursively to rebuild frozen models with new `evidence_ids` lists.
  - [x] Subtask 3.6 — Inside `run_intake`, instantiate a `LedgerReader` to find the just-written agent entry. Use the `get_ledger_reader()` singleton from Story 3-1. Implement the AC6 read-back logic.
  - [x] Subtask 3.7 — Append the `case.intake_completed` / `case.intake_blocked` ledger entries via the writer. The supervisor IS allowed to call `LedgerWriter.append` directly because it's not in the agent's call path — the P4 lint check (Story 3-2 AC6) excludes the supervisor file? **Check:** the grep in Story 3-2 AC6 covers `apps/agents/src/agents/` and excludes only `action_decorator.py`. The supervisor would trip the rule. **Decision (binding for this story):** edit the lint rule to also exclude `case_supervisor.py`. Document in the lint rule's comment: "supervisor writes system-level case lifecycle entries (intake_completed/intake_blocked); only agent invocations are forbidden from direct ledger writes." Update the Makefile target's grep to add a second `grep -v` for the supervisor file.

- [x] **Task 4 — Wire seed-time intake** (AC: #8)
  - [x] Subtask 4.1 — Edit `apps/cockpit-api/scripts/seed_dev.py`. After the bootstrap ledger entry, if `cases_seeded`, instantiate the supervisor and run intake for each fixture case. Print one line per case with the outcome.
  - [x] Subtask 4.2 — Update `apps/cockpit-api/tests/test_seed_dev.py`: add at least 2 tests — (a) `make seed` on a fresh DB runs intake and the cases end in `decision_ready`; (b) re-running `make seed` is a no-op (cases_seeded=False, intake skipped).

- [x] **Task 5 — Wire `POST /v1/cases/{case_id}/intake`** (AC: #9)
  - [x] Subtask 5.1 — Edit `apps/cockpit-api/src/cockpit_api/routers/cases.py`: add the `run_intake` route per AC9. Translate `CaseNotFoundError` → 404, `CaseNotIntakeReadyError` → 409 via the existing exception handlers in `main.py` (extend if needed).
  - [x] Subtask 5.2 — Author `apps/cockpit-api/tests/test_cases_intake_route.py` with the AC10 route tests using FastAPI's `TestClient` (or `httpx.AsyncClient` per the existing route-test convention from Story 2-2).

- [x] **Task 6 — Tests for the supervisor** (AC: #10)
  - [x] Subtask 6.1 — Create `apps/agents/tests/test_case_supervisor.py`. Use a `tmp_path`-bound `LedgerWriter`/`LedgerReader` pair + an in-memory SQLite engine fixture (per Story 2-1's pattern) so each test gets a clean DB.
  - [x] Subtask 6.2 — Implement the 10+ test cases from AC10. The "agent failure" test monkeypatches `document_intelligence` to raise — use `pytest.MonkeyPatch.setattr` against the imported symbol in `case_supervisor`.
  - [x] Subtask 6.3 — For the "notify hook called" test, define an inline `async def stub_notify(case_id, event, payload): calls.append(...)` and pass it into the constructor.

- [x] **Task 7 — Lint extension for supervisor's ledger writes** (AC: #3 footnote, AC12)
  - [x] Subtask 7.1 — Edit `Makefile`'s `lint-agents-p4` target: add a second `grep -v` for `apps/agents/src/agents/supervisor/case_supervisor.py` so the supervisor's direct `LedgerWriter.append` calls don't trip the P4 rule. Keep the original exclusion for `action_decorator.py`.
  - [x] Subtask 7.2 — Update the rule's comment block in the Makefile to document the rationale (per the Task 3.7 binding).

- [x] **Task 8 — End-to-end smoke + lint pass** (AC: #11, #12)
  - [x] Subtask 8.1 — Run `make demo-reset && make seed`. Assert via shell:
      ```bash
      sqlite3 ./data/cockpit.db "SELECT id, state FROM cases;"
      # Expected: 3 rows, all decision_ready
      sqlite3 ./data/cockpit.db "SELECT case_id, agent_id FROM intake_results;"
      # Expected: 3 rows, all agent_id=document_intelligence
      wc -l ./data/ledger.jsonl
      # Expected: at least 10 lines
      ```
  - [x] Subtask 8.2 — Run `make lint` from repo root; clean across all five subprojects.
  - [x] Subtask 8.3 — Run `make test`. Confirm:
      - `apps/agents` test count up by ≥10
      - `apps/cockpit-api` test count up by ≥6 (intake repo + intake route + seed update)
      - `packages/contracts` test count up by ≥1
      - No regressions in existing tests

## Dev Notes

### Architectural context (binding)

[Source: `architecture.md#Architectural Boundaries`] — **Agent boundary** (load-bearing): "Agents are invoked *only* through `agents/supervisor/case_supervisor.py`. The Case Supervisor is invoked *only* through `cockpit-api/services/case_service.py`. No router calls an agent directly." This story is the canonical implementation of that boundary. The new POST route delegates to `case_service.run_intake`, which delegates to the supervisor. **Don't shortcut** by having the route directly call `document_intelligence` — that would violate the boundary and start a precedent that erodes the architecture.

[Source: `architecture.md#Cross-Cutting Flow Examples`] — Case ingest → decision-ready flow shows: `services/case_service.py.create()` → `workers/ledger_writer enqueue (Arq)` → `triggers agents/supervisor/case_supervisor.py` → fans out. **Demo simplification:** the Arq enqueue is replaced by a direct synchronous call from the seed script and from the new POST route. The fan-out itself is preserved exactly.

[Source: `architecture.md#Project-Specific Patterns` P4 Agent Action] — "Supervisor pattern enforces via decorator wrap; new agents follow this template — there is no other way to write an agent." This story is the supervisor that wraps. Agents that the supervisor invokes inherit P4 enforcement automatically.

[Source: `architecture.md#Demo Scope Addendum (2026-04-29)` § Cross-cutting concerns demoted] — "Real-time tenant-partitioned streaming — replaced with single-worker SSE." The supervisor's `notify` hook is the integration point for SSE; Story 4-6 will provide the real impl. For now, the hook is `None` or a stdout stub.

[Source: `architecture.md#Anti-Patterns to Refuse`] — relevant subset:
- ❌ **Silent agent failure** — the supervisor catches `AgentExecutionError`, names the agent, transitions the case to `escalated`, writes a `case.intake_blocked` ledger entry, and returns a typed `CaseIntakeOutcome` — no silent swallow
- ❌ **Stale data shown as fresh** — `IntakeRepo.upsert` overwrites; the API/UI always sees the latest run

### Critical pitfalls to avoid

1. **The supervisor is allowed to write system ledger entries.** The P4 lint check (Story 3-2 AC6) is restrictive by design — only `@agent_action`-wrapped agent invocations write to the ledger from `apps/agents/`. The supervisor writes `case.intake_completed`/`case.intake_blocked` entries which are NOT agent invocations — they're system events. Task 7 extends the lint rule's exclusion list. **Document the rationale** in the Makefile rule's comment so future contributors understand the carve-out.

2. **Frozen models require copy-on-write.** `Case`, `Provenance`, `ExtractedField`, `DocumentIntelligenceOutput` are all `frozen=True`. The post-fill helper (AC6) MUST use `model_copy(update={...})` — direct assignment raises `ValidationError: Instance is frozen`. The `update` argument supports nested replacement only at the top level; deeper replacements require recursive `model_copy`. The cleanest pattern:

    ```python
    def _fill_evidence_ids(output: DocumentIntelligenceOutput, ledger_id: LedgerEntryId) -> DocumentIntelligenceOutput:
        new_fields = [
            f.model_copy(update={
                "value": f.value.model_copy(update={
                    "provenance": f.value.provenance.model_copy(update={"evidence_ids": [ledger_id]})
                })
            })
            for f in output.extracted_fields
        ]
        return output.model_copy(update={"extracted_fields": new_fields})
    ```

3. **`Provenance.confidence_band` validator runs on every copy.** Story 3-3 AC3's consistency check fires when `model_copy` rebuilds the Provenance with a new `evidence_ids`. Since `confidence` and `confidence_band` are unchanged, the check passes. But: if someone in a future story accidentally mutates `confidence` via the same `model_copy` path, the check catches it. Defensive — good.

4. **`CaseRepo.add_block_marker` mutates `customer_metadata.extra`.** The Story 2-1 ORM model's `customer_metadata` column is `JSON`. Reading the JSON into a dict, merging in two keys, dumping back, and committing is the right pattern. **Don't try to JSON-patch via raw SQL** — it's not portable to Postgres (which has `jsonb_set` but a different syntax than SQLite's `json_set`).

5. **The supervisor instantiates per-request, not per-process.** A common temptation is to make `CaseSupervisor` a singleton at app startup. Don't — the DI plumbing (session factory, repo) varies per request. Constructor cost is zero; instantiate inline.

6. **`LedgerReader.read_for_case` is a linear file scan.** For the demo's small ledger, fine. For the supervisor's post-fill step (AC6), the read happens immediately after the agent's `agent.completed` write — so the entry is at the tail of the file. **Optimization (optional):** read the file from the end and stop at the first matching `actor_id` + `payload.kind == "agent_action"` entry. Not required for the demo's volume.

7. **`AgentExecutionError` is the only exception the supervisor catches.** Other exceptions (DB errors, ledger write errors, `LedgerCorruptionError` from Story 3-1) bubble. The route handler returns 500 RFC 7807. The seed script crashes loudly. **This is correct** — those are infrastructure-level failures, not domain-level "intake blocked."

8. **`@agent_action` preserves `case_id` from input.** The Document Intelligence agent's input has `case_id` as a field; the decorator picks it up via Story 3-2 AC2's first-step. No additional plumbing needed in the supervisor.

9. **Empty `document_refs` is not a failure.** A case might genuinely have no documents (e.g., a future story that triggers intake before documents are uploaded). The `IntakeAgentSpec.requires` callable returns False, the agent is skipped, and the case still transitions to `decision_ready`. Story 4-1's queue-rail will render the case as "ready for triage" with no extracted fields — which is honest UX.

10. **Atomic transaction boundaries.** The DB transaction wraps `IntakeRepo.upsert` + `CaseRepo.transition` (AC7). The ledger write is OUTSIDE the transaction — appending to a JSONL file is not part of the SQLite session. If the ledger write fails after the DB commit, you have an audit gap but a correct user state. The reverse (DB failure after a successful ledger write) is impossible because the DB ops happen first inside the supervisor's flow.

11. **Idempotency vs append-only ledger.** The ledger is append-only by design. Re-running intake (which can't actually happen because of the state-machine guard, but in case the dev removes it) would append duplicate `case.intake_completed` entries. **The state-machine guard is the intended idempotency mechanism** — `decision_ready` doesn't transition back to `intake_scheduled`, so re-running `run_intake` raises `CaseNotIntakeReadyError`. Don't try to add ledger-level dedup.

12. **The supervisor does NOT itself wrap with `@agent_action`.** It's not an agent — it's an orchestrator. Its system-level ledger entries (`case.intake_completed`, `case.intake_blocked`) use `actor_type=ActorType.SYSTEM, actor_id="case_supervisor"`, NOT `actor_type=ActorType.AGENT`. The Audit Trail Timeline (9-1) will style system events differently from agent events.

13. **The new POST route is auth-gated via `Depends(get_current_user)`.** Same pattern as Story 2-2's GET routes. The current-user dep just reads `X-Cockpit-Demo-User` — no real auth in the demo.

14. **Concurrent intake calls for the same case.** If two clients hit the POST route simultaneously, both pass the state-machine guard (both see `intake_scheduled`), both try to transition. SQLite's `BEGIN IMMEDIATE` semantics serialize them — the second commit will hit the row lock. **Reasonable demo answer:** the second one fails with a generic 500 (or `CaseStateTransitionError` if it loses the race). Not a perfect demo, but the case is rare enough to defer. If the dev wants to harden, add a row-level advisory lock — but that's bank-buyer scope (`P2 tenant scoping pattern`'s Postgres advisory lock idiom).

15. **Don't add per-agent retries.** Story 3-2's decorator catches and re-raises; the supervisor catches and escalates. **Retries are deferred** — they're a Story 4+ NFR concern. Adding them here over-scopes.

### Architecture patterns relevant here

[Source: `architecture.md#Architectural Boundaries`] — Agent boundary, Data boundary, Adapter boundary all touched here. The supervisor is the canonical violator of the simple "data goes through repos" rule because it must read the ledger AND mutate the DB AND write the ledger AND call agents. That's the supervisor's whole job — orchestration. The boundaries are preserved for the lower layers.

[Source: `architecture.md#Project-Specific Patterns` P4 Agent Action Pattern] — Each agent invocation produces a ledger entry. The supervisor's role is to USE those entries for downstream provenance (`evidence_ids`) — not to bypass them.

[Source: `architecture.md#Cross-Cutting Flow Examples`] — The "case ingest → decision-ready" flow names the supervisor as the orchestrator of fan-out. This story implements the demo's simplified version of that flow.

### Project Structure Notes

This story creates:

- `packages/contracts/src/contracts/case_supervisor.py`
- `packages/contracts/tests/test_case_supervisor.py`
- `apps/cockpit-api/src/cockpit_api/repositories/intake_repo.py`
- `apps/cockpit-api/migrations/versions/<rev>_create_intake_results.py`
- `apps/cockpit-api/tests/test_intake_repo.py`
- `apps/cockpit-api/tests/test_cases_intake_route.py`
- `apps/agents/src/agents/supervisor/case_supervisor.py`
- `apps/agents/tests/test_case_supervisor.py`

This story modifies:

- `packages/contracts/src/contracts/__init__.py` — re-export `CaseIntakeOutcome`
- `apps/cockpit-api/src/cockpit_api/db/models.py` — add `IntakeRow`
- `apps/cockpit-api/src/cockpit_api/repositories/case_repo.py` — add `add_block_marker`
- `apps/cockpit-api/src/cockpit_api/routers/cases.py` — add `POST /v1/cases/{id}/intake`
- `apps/cockpit-api/scripts/seed_dev.py` — run intake post-seed
- `apps/cockpit-api/tests/test_seed_dev.py` — assert intake ran post-seed
- `Makefile` — extend `lint-agents-p4` rule's exclusion list

This story DOES NOT create:

- The Documents panel UI (Story 3-6)
- The ConfidencePill component (Story 3-7)
- An SSE endpoint or real notify impl (Story 4-6)
- Webhook dispatch (cut from demo)
- Additional intake agents (Epic 5+ extends `INTAKE_AGENTS`)
- A new case state (`escalated` is reused; bank-buyer's `intake_blocked` is deferred)

### References

- [Source: `architecture.md#Architectural Boundaries`] — agent boundary
- [Source: `architecture.md#Cross-Cutting Flow Examples`] — case ingest fan-out flow
- [Source: `architecture.md#Project-Specific Patterns` P4] — agent action ledger
- [Source: `architecture.md#Demo Scope Addendum (2026-04-29)`] — single-tenant, no Arq, no SSE for now
- [Source: `architecture.md#Anti-Patterns to Refuse`] — silent failure, stale data
- [Source: `epics.md#Epic 3` § Story 3.10] — original AC (re-scoped here)
- [Source: `prd.md#FR3, FR14, FR55, NFR-A5`] — instant canvas, intake automation, agent failure surfacing
- [Source: `2-1-case-schema-and-state-machine.md`] — `CaseRepo`, `Case`, state machine, `CaseStateTransitionError`
- [Source: `3-1-append-only-ledger-schema-with-insert-only-writer.md`] — `LedgerWriter`, `LedgerReader`
- [Source: `3-2-agent-action-decorator.md`] — `@agent_action`, `AgentExecutionError`
- [Source: `3-3-pydantic-contracts-for-ledger-provenance-confidence.md`] — `Provenance`, `ProvenancedField`, `ConfidenceBand`
- [Source: `3-4-document-intelligence-agent-llm-extract.md`] — `DocumentIntelligenceInput/Output`, `ExtractedField`

### Previous Story Intelligence

[Source: `2-1-case-schema-and-state-machine.md`]
- `CaseState.INTAKE_SCHEDULED → DECISION_READY` and `INTAKE_SCHEDULED → ESCALATED` are both in `ALLOWED_TRANSITIONS`. The supervisor uses both edges per the success/failure paths.
- `CaseRepo.transition(case_id, target)` is the only path to mutate state. Use it; don't go around with raw SQL.
- `customer_metadata.extra` is a free-form `dict[str, Any]` field on `CustomerMetadata`. Adding `blocked_agent`/`block_reason` keys requires no schema change. The Pydantic model accepts the extension via `extra: dict[str, Any]`.
- Repo methods take an explicit `AsyncSession` arg. The supervisor's `session_factory` returns a session via `async with`; the supervisor passes it to `CaseRepo` calls.

[Source: `2-2-get-case-retrieval-api-consumer.md`]
- The router pattern for `GET /v1/cases/{id}` is the template for the new `POST /v1/cases/{id}/intake`. Use `Depends(get_session)`, `Depends(get_current_user)`, and `CaseIdPath`.
- RFC 7807 error handling is wired in `main.py`. Adding two new exception → status mappings requires extending the `@app.exception_handler` chain in `main.py`. Pattern: add a new handler for `CaseNotFoundError` → 404 and `CaseNotIntakeReadyError` → 409.

[Source: `2-3-case-appears-in-queue-rail-basic-ordering.md`]
- The queue-rail UI (Story 2-3) renders cases sorted by `created_at DESC`. Cases in `decision_ready` state are styled identically to `intake_scheduled` for now. Story 4-1 will introduce status pills.

[Source: `2-4-fixture-case-loader-with-three-seeded-cases.md`]
- Pinned demo case IDs are `SHREE_VENKAT_ID`, `VORA_CAPITAL_ID`, `ANANYA_IYER_ID`. Each has `document_refs` in `customer_metadata.extra`. The seeder calls `get_demo_case_fixtures(now)`.
- `INSERT OR IGNORE` is the existing seed idempotency pattern. The intake-post-step uses the `cases_seeded` boolean to gate execution.

[Source: `3-1-append-only-ledger-schema-with-insert-only-writer.md`]
- `LedgerReader.read_for_case(case_id)` returns entries in append order. The most recent matching entry is the LAST in the returned list (not the first).
- `LedgerWriter.append` returns the canonicalized entry. The supervisor's `case.intake_completed` write captures the returned entry's ID for logging if needed.

[Source: `3-2-agent-action-decorator.md`]
- The decorator catches all exceptions and re-raises as `AgentExecutionError(agent_id=..., case_id=..., original=exc)`. The supervisor's `try/except AgentExecutionError` is the canonical handler — `err.original` is the underlying cause.
- Lint rule `lint-agents-p4` restricts `apps/agents/src/agents/` to only `action_decorator.py` for direct ledger writes. **This story extends the exclusion** to include `case_supervisor.py` since the supervisor needs to write system-level entries.

[Source: `3-3-pydantic-contracts-for-ledger-provenance-confidence.md`]
- `Provenance.evidence_ids` validates each element against `LedgerEntryId` regex. Empty list `[]` is allowed. After the supervisor's post-fill, exactly one ID is in the list.
- `Provenance` has a band-vs-confidence consistency validator. `model_copy(update={"evidence_ids": ...})` runs the validator; since neither `confidence` nor `confidence_band` change, validation passes.

[Source: `3-4-document-intelligence-agent-llm-extract.md`]
- `document_intelligence(input: DocumentIntelligenceInput) -> DocumentIntelligenceOutput` is the agent's signature. The supervisor calls it directly (no special invocation harness needed — `@agent_action` is on the function itself).
- The agent returns `extracted_fields: list[ExtractedField]` with `evidence_ids=[]` per its AC8. The supervisor fills them in.
- The agent reads `document_refs` from `customer_metadata.extra`. The supervisor builds the input with this field per AC3's `_invoke_document_intelligence` helper.

### Demo verification protocol (operator hand-off)

```bash
# After implementing, the dev must verify:

# 1. Reset and seed runs intake automatically:
make demo-reset && make seed
# Expected output includes lines like:
#   intake case_01... → completed (15 fields)
#   intake case_01... → completed (12 fields)
#   intake case_01... → completed (8 fields)

# 2. All cases in decision_ready post-seed:
sqlite3 ./data/cockpit.db "SELECT id, state FROM cases ORDER BY created_at DESC;"
# Expected: 3 rows, all decision_ready

# 3. intake_results table populated:
sqlite3 ./data/cockpit.db "SELECT case_id, agent_id FROM intake_results;"
# Expected: 3 rows, all agent_id=document_intelligence

# 4. Ledger has the expected events:
wc -l ./data/ledger.jsonl
# Expected: at least 10 lines
grep -c "case.intake_completed" ./data/ledger.jsonl
# Expected: 3
grep -c "agent.completed" ./data/ledger.jsonl
# Expected: 3 (Doc Intelligence per case)

# 5. Provenance evidence_ids are filled:
poetry -C apps/cockpit-api run python -c "
import asyncio, json
from cockpit_api.config import get_settings
from cockpit_api.db.session import get_session
from cockpit_api.repositories.intake_repo import IntakeRepo
from contracts.cases import VORA_CAPITAL_ID
from contracts.document_intelligence import DocumentIntelligenceOutput

async def main():
    async for session in get_session():
        row = await IntakeRepo.get_one(session, VORA_CAPITAL_ID, 'document_intelligence')
        out = DocumentIntelligenceOutput.model_validate(row)
        for f in out.extracted_fields[:3]:
            print(f.field_name, '->', f.value.provenance.evidence_ids)
        break
asyncio.run(main())
"
# Expected: each line shows ['led_<ULID>'] (a single ledger ID).

# 6. POST /v1/cases/{id}/intake on a case already in decision_ready returns 409:
poetry -C apps/cockpit-api run python -c "
import httpx, asyncio
from cockpit_api.main import app
from contracts.cases import VORA_CAPITAL_ID
async def main():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url='http://test') as c:
        r = await c.post(f'/v1/cases/{VORA_CAPITAL_ID}/intake', headers={'X-Cockpit-Demo-User': 'analyst'})
        print('status:', r.status_code, 'body:', r.json())
asyncio.run(main())
"
# Expected: 409 with RFC 7807 problem detail.

# 7. Force a failure to confirm the escalated path works:
poetry -C apps/agents run python -c "
import asyncio, os
os.environ['DOC_AI_PROVIDER'] = 'invalid_provider'  # forces _get_default_llm to raise
# ... or monkeypatch document_intelligence to raise
"
# Expected: case transitions to escalated; ledger has case.intake_blocked entry.

# 8. Lint + test green:
make lint
make test
# Expected: all subprojects pass; new tests visible.
```

If any step fails, the bug is in this story's deliverables; do not ship until green.

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (Amelia persona, bmad-dev-story workflow)

### Debug Log References

* End-to-end smoke output:
    ```
    Running case intake...
      intake case_01KQC7EWM0GYHP15CZ8JB5ZT69 → completed (9 fields)
      intake case_01KQC7GQ70GYHP15CZ8JB5ZT6A → completed (10 fields)
      intake case_01KQC7JHT0GYHP15CZ8JB5ZT6B → completed (6 fields)
    Intake: completed for 3 case(s).
    ```
  Ledger has 10 lines (1 ledger.initialized + 3 case.seeded + 3 agent.completed + 3 case.intake_completed). All 3 cases land in `decision_ready`. `intake_results` table has 3 rows.
* Initial test failure: `test_happy_path_completes_and_persists` returned `evidence_ids=[]` because `_find_agent_ledger_entry` couldn't find the agent entry. Root cause: the supervisor imports `get_ledger_reader` by name, so the test fixture's monkeypatch of `ledger_service.get_ledger_reader` didn't reach the supervisor's binding. Fix: also `monkeypatch.setattr(supervisor_mod, "get_ledger_reader", ...)`. Same for the writer.
* Initial code used `from collections.abc import AsyncContextManager` — that lives in `contextlib` in Python 3.12. Switched to `from contextlib import AbstractAsyncContextManager`.

### Completion Notes List

* **Hybrid supervisor architecture (decided post-Story-3.4 ADK pivot):** Python `CaseSupervisor` class owns the deterministic orchestration; an ADK agent at `registry/case_supervisor/` exposes the supervisor's HTTP endpoint as a `run_case_intake` tool AND lists `document_intelligence` as a collaborator. The ADK agent uses `style: react` so its LLM routes between the deterministic tool (for "process case X" requests) and the collaborator (for ad-hoc document questions). This satisfies NFR-RI1 (ADK pattern showcase) without sacrificing determinism for the intake fan-out.
* **`_invoke_document_intelligence` calls the agent function directly.** The `@agent_action` decorator wraps the agent and writes the ledger entry; the supervisor catches `AgentExecutionError` and translates to a typed `CaseIntakeOutcome(status="blocked", ...)`.
* **Atomic transaction:** `IntakeRepo.upsert` + `CaseRepo.transition` happen in the same DB session, committed together. The ledger entry is written AFTER commit — if the ledger write fails, the audit trail has a gap but the user-visible state is correct (logged at ERROR; Story 9.1 will surface gaps).
* **Frozen-model copy-on-write for `evidence_ids`:** `_fill_evidence_ids` rebuilds each `ExtractedField → ProvenancedField → Provenance` via `model_copy(update=...)`. The band-vs-confidence consistency validator runs on the new `Provenance` and passes (confidence + band unchanged).
* **P4 lint extension:** the `lint-agents-p4` Makefile rule's `grep -v` now also excludes `case_supervisor.py`. The supervisor writes SYSTEM-level `case.intake_completed`/`case.intake_blocked` entries — those aren't agent invocations, so the P4 carve-out is correct. Documented in the Makefile rule's comment block.
* **Reciprocal Poetry path-dep (already from Story 3.4):** `apps/cockpit-api` path-deps `apps/agents` so the new `POST /v1/cases/{case_id}/intake` route can import the supervisor. No new install-time changes needed.
* **Sequencing for downstream stories:** Story 3.6's GET endpoint (`/v1/cases/{id}/intake/document_intelligence`) reads from `IntakeRepo.get_one`. Story 3.8's upload UI will trigger `POST /v1/cases/{id}/intake` after upload to refresh extractions.

### File List

**Created**
* `packages/contracts/src/contracts/case_supervisor.py` — `CaseIntakeOutcome` contract
* `packages/contracts/tests/test_case_supervisor.py`
* `apps/cockpit-api/src/cockpit_api/repositories/intake_repo.py` — `IntakeRepo`
* `apps/cockpit-api/migrations/versions/01197671c9e2_create_intake_results.py`
* `apps/cockpit-api/tests/test_intake_repo.py`
* `apps/cockpit-api/tests/test_cases_intake_route.py`
* `apps/agents/src/agents/supervisor/case_supervisor.py` — `CaseSupervisor`, `CaseNotFoundError`, `CaseNotIntakeReadyError`, `INTAKE_AGENTS`, `_fill_evidence_ids`
* `apps/agents/tests/test_case_supervisor.py` — 10 tests
* `apps/agents/src/agents/registry/case_supervisor/agent.yaml` — ADK agent manifest (style: react, tools: [run_case_intake], collaborators: [document_intelligence])
* `apps/agents/src/agents/registry/case_supervisor/openapi.yaml` — generated tool spec
* `apps/agents/src/agents/registry/case_supervisor/gen_openapi.py` — generator shim

**Modified**
* `packages/contracts/src/contracts/__init__.py` — re-export `CaseIntakeOutcome`
* `apps/cockpit-api/src/cockpit_api/db/models.py` — add `IntakeRow`
* `apps/cockpit-api/src/cockpit_api/db/session.py` — expose `get_sessionmaker()` accessor
* `apps/cockpit-api/src/cockpit_api/repositories/case_repo.py` — add `add_block_marker` helper
* `apps/cockpit-api/src/cockpit_api/routers/cases.py` — add `POST /v1/cases/{case_id}/intake` route + 404/409 mapping
* `apps/cockpit-api/scripts/seed_dev.py` — runs intake post-seed for fresh fixture cases
* `Makefile` — `lint-agents-p4` rule excludes `case_supervisor.py` for system-level ledger entries
* `Documentation/implementation-artifacts/sprint-status.yaml` — story marked `review`

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-04-30 | Story 3.5 drafted. Demo replacement for the bank-buyer Story 3.10. Real Case Supervisor that fans out (Doc Intelligence today, Epics 5–6 will extend), fills `evidence_ids` from ledger entries, persists via new `IntakeRepo`, transitions case state atomically, and surfaces agent failures as typed escalations (no silent failures, FR55, NFR-A5). Establishes the canonical supervisor pattern that Epics 4–8 will build on. |
