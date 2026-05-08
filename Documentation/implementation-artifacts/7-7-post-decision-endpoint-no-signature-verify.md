# Story 7.7: POST decision endpoint (no signature verify)

Status: review

## Story

As the cockpit-ui (Story 7-1's Decision Zone),
I want a `POST /v1/cases/{case_id}/decisions` endpoint that — given a body of `{outcome, conditions, rationale_html}` — validates the body against typed Pydantic, transitions the case from `decision_ready` to `pending_seal` (Story 7-4), persists the decision row to a new `decisions` table, writes an `officer.decision_committed` ledger entry capturing the officer's identity from the session (no Ed25519 signature — cut from demo), schedules Story 7-4's `DecisionTimerService.schedule(case_id, decision_id)`, fires a `decision.committed` SSE event, and returns the decision_id + the seal-at timestamp,
plus a `decision_service.seal_decision(case_id, decision_id)` callback function that Story 7-4's timer invokes on expiry — performing the `pending_seal → committed` transition, writing the `decision.sealed` ledger entry, and firing the matching SSE event,
So that Story 7-1's Commit button has a real backend to call, Story 7-5's UndoPill has a decision_id to undo, Story 7-6's seal animation has a deterministic SSE trigger, and the demo's commit-and-seal flow works end-to-end (FR24 — commit; FR29 — record officer decision-maker identity; demo simplification of bank-buyer Story 7.11 cryptographic signing).

## Scope note (2026-04-29 demo re-scope)

This story is the demo-equivalent of the bank-buyer Story 7.11. The bank-buyer scope had Ed25519 signature headers + canonical-JSON verification + signed ledger entries; demo cuts all of it.

| Bank-buyer scope (original 7.11) | Demo replacement |
|---|---|
| Body + `signature` + `signing_key_id` headers | **Body only** — no headers. Officer identity from session via `Depends(get_current_user)`. |
| Server-side verifies Ed25519 against stored public key (Story 7.4 verification) | **Cut.** No verification step. |
| `officer-signed` ledger entry includes Ed25519 signature | **`OfficerDecisionCommittedPayload` typed payload** with officer user_id; no signature field. |
| Tenant-scoped path | **Single-tenant.** |
| 403 on signature mismatch | **N/A** (no signature). |
| `case.state` transitions `decision_ready → pending_seal` (Story 7-4 adds the new state) | **Same.** |
| Outcomes: `approve`, `decline`, `approve_with_conditions`, `escalate_to_edd` | **Same** — Story 7-9 owns the contract. |
| Returns the new decision row + `pending_seal` time | **Same.** |

What survives: **the entire commit-flow shape — POST endpoint, typed body, state transition, decision row persistence, ledger entry, timer scheduling, SSE fan-out, the `seal_decision` callback that Story 7-4's timer invokes.**

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md`, `architecture.md#Project-Specific Patterns` § P5 (officer action — sign cut), `architecture.md#API & Communication Patterns` § A5 (RFC 7807), `prd.md#Functional Requirements` FR24 / FR29.

## Acceptance Criteria

1. **AC1 — `Decision` Pydantic + outcome contracts in `packages/contracts/src/contracts/decision.py`.**

    Story 7-9 owns the `DecisionOutcome` enum + body shape; this story consumes it. If 7-9 hasn't landed, **draft the contracts in this story** and document so 7-9 can re-export / refine when it merges. Recommended split: this story creates the persistence-shaped `Decision` model + typed ledger payloads; Story 7-9 creates the user-facing `DecisionOutcome` Literal and the form-level `DecisionDraftInput`.

    For this story (assuming 7-9 has not merged):

    ```python
    from typing import Literal

    from pydantic import BaseModel, Field

    from contracts.cases import CaseId
    from contracts.users import UserId   # if exists; otherwise plain str


    DecisionOutcome = Literal["approve", "decline", "approve_with_conditions", "escalate_to_edd"]


    class CommitDecisionRequest(BaseModel):
        model_config = {"frozen": True}
        outcome: DecisionOutcome
        conditions: list[str] = Field(default_factory=list, max_length=10)
        rationale_html: str = Field(min_length=20, max_length=20_000)

        @model_validator(mode="after")
        def _conditions_required_for_with_conditions(self):
            if self.outcome == "approve_with_conditions" and not self.conditions:
                raise ValueError("approve_with_conditions requires at least one condition")
            for c in self.conditions:
                if not c.strip() or len(c) > 200:
                    raise ValueError("each condition must be 1-200 non-blank chars")
            return self


    class CommitDecisionResponse(BaseModel):
        model_config = {"frozen": True}
        case_id: CaseId
        decision_id: str
        case_state: CaseState   # pending_seal
        seal_at: datetime        # UTC timestamp 120s from now
        ledger_entry_id: LedgerEntryId


    class Decision(BaseModel):
        """Persistence-shaped record. One row per (case_id, commit attempt)."""
        model_config = {"frozen": True}

        decision_id: str = Field(min_length=1)            # `dec_<ULID>`
        case_id: CaseId
        outcome: DecisionOutcome
        conditions: list[str]
        rationale_html: str
        committed_by_user_id: str
        committed_at: datetime
        sealed_at: datetime | None = None
        sealed_ledger_entry_id: LedgerEntryId | None = None
        committed_ledger_entry_id: LedgerEntryId
    ```

    Re-export from `__init__.py`. When Story 7-9 ships, it MAY refine `DecisionOutcome` to a StrEnum (the Pydantic Literal works either way; keep this story's signature stable).

2. **AC2 — `OfficerDecisionCommittedPayload` typed ledger arm.**

    `packages/contracts/src/contracts/ledger.py`:

    ```python
    class OfficerDecisionCommittedPayload(BaseModel):
        """Typed LedgerEntry.payload for officer-committed decisions (no signature)."""

        model_config = {"frozen": True}

        kind: Literal["officer_decision_committed"] = "officer_decision_committed"
        decision_id: str = Field(min_length=1)
        outcome: DecisionOutcome
        conditions: list[str] = Field(default_factory=list)
        rationale_hash: str = Field(min_length=64, max_length=64)   # SHA-256 hex of rationale_html
        # NOTE: no Ed25519 signature; demo simplification per architecture.md § Demo Scope Addendum.


    class DecisionSealedPayload(BaseModel):
        """SYSTEM-emitted typed ledger payload when DecisionTimerService seals."""

        model_config = {"frozen": True}

        kind: Literal["decision_sealed"] = "decision_sealed"
        decision_id: str
        outcome: DecisionOutcome
    ```

    Add both to the `LedgerEntry.payload` union (alongside Story 5-5's `LearningEventLedgerPayload`, Story 6-7's `CockpitChatToolLedgerPayload`, Story 7-5's `OfficerDecisionUndonePayload`).

    Re-export.

3. **AC3 — `decisions` SQLAlchemy table.**

    New table in `apps/cockpit-api/src/cockpit_api/db/models.py` (or wherever the SQLAlchemy declarative models live; verify path at impl time):

    ```python
    class DecisionRow(Base):
        __tablename__ = "decisions"
        decision_id: Mapped[str] = mapped_column(String, primary_key=True)
        case_id: Mapped[str] = mapped_column(String, ForeignKey("cases.case_id"), index=True)
        outcome: Mapped[str] = mapped_column(String, nullable=False)
        conditions_json: Mapped[str] = mapped_column(Text, default="[]")    # JSON array
        rationale_html: Mapped[str] = mapped_column(Text, nullable=False)
        committed_by_user_id: Mapped[str] = mapped_column(String, nullable=False)
        committed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
        sealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
        sealed_ledger_entry_id: Mapped[str | None] = mapped_column(String, nullable=True)
        committed_ledger_entry_id: Mapped[str] = mapped_column(String, nullable=False)
    ```

    SQLite + SQLAlchemy auto-creates schema (Demo Scope Addendum); no migration. Backward compat: pre-existing rows don't exist (new table).

4. **AC4 — `DecisionRepo` at `apps/cockpit-api/src/cockpit_api/repositories/decision_repo.py`.**

    ```python
    class DecisionRepo:
        async def insert(self, session: AsyncSession, decision: Decision) -> None: ...
        async def fetch_by_id(self, session: AsyncSession, decision_id: str) -> Decision | None: ...
        async def fetch_latest_by_case(self, session: AsyncSession, case_id: CaseId) -> Decision | None: ...
        async def update_sealed(self, session: AsyncSession, decision_id: str, sealed_at: datetime, sealed_ledger_entry_id: str) -> None: ...
        async def revert_unseal(self, session: AsyncSession, decision_id: str) -> None: ...   # for Story 7-5 undo path
    ```

    Patterns mirror existing repos (`case_repo.py`, `intake_repo.py`).

5. **AC5 — `DecisionService` at `apps/cockpit-api/src/cockpit_api/services/decision_service.py`.**

    ```python
    """Decision commit + seal orchestration — Story 7-7."""

    import hashlib
    import json
    from datetime import UTC, datetime, timedelta
    from ulid import ULID

    from contracts.decision import (
        CommitDecisionRequest, CommitDecisionResponse, Decision, DecisionOutcome,
    )
    from contracts.cases import Case, CaseId, CaseState, assert_transition
    from contracts.ledger import (
        ActorType, LedgerEntry, OfficerDecisionCommittedPayload, DecisionSealedPayload,
    )

    UNDO_WINDOW = timedelta(seconds=120)


    class DecisionConflictError(RuntimeError):
        """Raised when commit is attempted on a case not in decision_ready state."""


    async def commit_decision(
        *,
        session: AsyncSession,
        case_id: CaseId,
        body: CommitDecisionRequest,
        user_id: str,
        case_repo: CaseRepo,
        decision_repo: DecisionRepo,
        writer: LedgerWriter,
        sse_publish: Callable,
        timer: DecisionTimerService,
    ) -> CommitDecisionResponse:
        case = await case_repo.fetch_by_id(session, case_id)
        if case is None:
            raise CaseNotFoundError(case_id)
        if case.state != CaseState.DECISION_READY:
            raise DecisionConflictError(case_id, case.state)

        now = datetime.now(UTC)
        decision_id = f"dec_{ULID()!s}"
        rationale_hash = hashlib.sha256(body.rationale_html.encode("utf-8")).hexdigest()

        # 1. Write ledger entry (BEFORE state transition so timer doesn't race)
        committed_entry = await writer.append(LedgerEntry(
            id=f"led_{ULID()!s}",
            case_id=case_id,
            actor_type=ActorType.OFFICER,
            actor_id=user_id,
            event_type="officer.decision_committed",
            created_at=now,
            payload=OfficerDecisionCommittedPayload(
                decision_id=decision_id,
                outcome=body.outcome,
                conditions=body.conditions,
                rationale_hash=rationale_hash,
            ),
        ))

        # 2. Persist decision row
        decision = Decision(
            decision_id=decision_id, case_id=case_id, outcome=body.outcome,
            conditions=body.conditions, rationale_html=body.rationale_html,
            committed_by_user_id=user_id, committed_at=now,
            committed_ledger_entry_id=committed_entry.id,
        )
        await decision_repo.insert(session, decision)

        # 3. State transition
        assert_transition(case.state, CaseState.PENDING_SEAL)
        await case_repo.update_state(session, case_id, CaseState.PENDING_SEAL)
        await session.commit()

        # 4. Schedule timer (post-commit so a DB rollback doesn't leave a phantom timer)
        timer.schedule(case_id, decision_id)

        # 5. SSE
        await sse_publish(case_id, SseEvent(event="decision.committed",
            data={"case_id": case_id, "decision_id": decision_id}))

        return CommitDecisionResponse(
            case_id=case_id, decision_id=decision_id,
            case_state=CaseState.PENDING_SEAL,
            seal_at=now + UNDO_WINDOW,
            ledger_entry_id=committed_entry.id,
        )


    async def seal_decision(case_id: CaseId, decision_id: str) -> None:
        """Callback bound by Story 7-4's lifespan — invoked when timer expires.

        Resolves dependencies via app.state at call time (the timer service
        was constructed at app startup; we need the same singletons).
        """
        # ... see AC6 for resolution strategy
    ```

    The `commit_decision` function is the route handler's logic — pure, testable, no FastAPI imports.

6. **AC6 — `seal_decision` callback dependency resolution.**

    Story 7-4's `DecisionTimerService` takes an `on_seal` callback at construction time. The callback needs `case_repo`, `decision_repo`, `writer`, `sse_publish` to do its job — but these are typically injected via FastAPI `Depends`, not available outside a request context.

    **Solution**: provide a lightweight dependency container. In `apps/cockpit-api/src/cockpit_api/main.py`'s `lifespan`:

    ```python
    @asynccontextmanager
    async def lifespan(app):
        # Singletons used by both request paths and background tasks
        session_factory = make_session_factory(...)
        ledger_writer = LedgerWriter(LEDGER_PATH)
        sse_registry = SseRegistry()
        case_repo = CaseRepo()
        decision_repo = DecisionRepo()
        # Curry the seal callback with these deps:
        async def on_seal(case_id, decision_id):
            await decision_service.seal_decision(
                case_id=case_id, decision_id=decision_id,
                session_factory=session_factory,
                case_repo=case_repo, decision_repo=decision_repo,
                writer=ledger_writer, sse_publish=sse_registry.publish_safe,
            )
        timer = DecisionTimerService(on_seal=on_seal)
        # Stash on app.state so request handlers can grab the same instances
        app.state.session_factory = session_factory
        app.state.ledger_writer = ledger_writer
        app.state.case_repo = case_repo
        app.state.decision_repo = decision_repo
        app.state.decision_timer = timer
        try: yield
        finally: await timer.shutdown()
    ```

    The `seal_decision` function (in `decision_service.py`) accepts these as keyword args:

    ```python
    async def seal_decision(*, case_id, decision_id, session_factory, case_repo, decision_repo, writer, sse_publish):
        async with session_factory() as session:
            decision = await decision_repo.fetch_by_id(session, decision_id)
            if decision is None or decision.sealed_at is not None:
                return  # idempotency: undo already happened, or seal already done

            now = datetime.now(UTC)
            seal_entry = await writer.append(LedgerEntry(
                id=f"led_{ULID()!s}", case_id=case_id,
                actor_type=ActorType.SYSTEM, actor_id="platform",
                event_type="decision.sealed", created_at=now,
                payload=DecisionSealedPayload(decision_id=decision_id, outcome=decision.outcome),
            ))
            await decision_repo.update_sealed(session, decision_id, now, seal_entry.id)
            await case_repo.update_state(session, case_id, CaseState.COMMITTED)
            await session.commit()

        await sse_publish(case_id, SseEvent(event="decision.sealed",
            data={"case_id": case_id, "decision_id": decision_id, "ledger_entry_id": seal_entry.id}))
    ```

    `ActorType.SYSTEM` — verify the enum has it; if not, add it (Story 3-1 may have only defined `AGENT` and `OFFICER`). The seal is platform-emitted, distinct from officer/agent action.

7. **AC7 — POST route in `apps/cockpit-api/src/cockpit_api/routers/cases.py`.**

    ```python
    @router.post("/{case_id}/decisions", response_model=CommitDecisionResponse, status_code=201)
    async def post_decision(
        case_id: Annotated[CaseId, Path()],
        body: CommitDecisionRequest,
        user: Annotated[User, Depends(get_current_user)],
        session: Annotated[AsyncSession, Depends(get_session)],
        case_repo: Annotated[CaseRepo, Depends(...)],
        decision_repo: Annotated[DecisionRepo, Depends(...)],
        writer: Annotated[LedgerWriter, Depends(get_ledger_writer)],
        timer: Annotated[DecisionTimerService, Depends(get_decision_timer)],
        registry: Annotated[SseRegistry, Depends(get_sse_registry)],
    ) -> CommitDecisionResponse:
        try:
            return await commit_decision(
                session=session, case_id=case_id, body=body, user_id=user.id,
                case_repo=case_repo, decision_repo=decision_repo,
                writer=writer, sse_publish=registry.publish_safe, timer=timer,
            )
        except CaseNotFoundError:
            raise HTTPException(status_code=404, detail="case not found")
        except DecisionConflictError as exc:
            raise HTTPException(status_code=409, detail=f"case is in {exc.case_state.value!r}; commit allowed only from decision_ready")
    ```

    Place above the existing `/{case_id}/decisions/active/timer` and `/{case_id}/decisions/{decision_id}/undo` routes from Story 7-5 (FastAPI matches by declaration order; this generic POST is fine after, since the others have more-specific paths).

8. **AC8 — Backward incompatibility: existing `DECISION_READY → COMMITTED` transition is REMOVED.**

    Story 7-4 already removed it. This story confirms by introspecting `ALLOWED_TRANSITIONS` in tests. Any old test that called `assert_transition(DECISION_READY, COMMITTED)` directly will fail; update or delete those tests.

9. **AC9 — Tests at `apps/cockpit-api/tests/services/test_decision_service.py`.**

    `commit_decision`:
    * **Happy path** — `decision_ready` case → returns response with `case_state=pending_seal`, `seal_at` ~120s away, `decision_id` shape `dec_<ULID>`; case state in DB is `pending_seal`; one decision row inserted; one `officer.decision_committed` ledger entry written; timer.schedule was called with the right `(case_id, decision_id)`; SSE `decision.committed` published.
    * **`approve_with_conditions` requires conditions** — empty conditions → ValidationError before reaching service.
    * **Conflict: case in `intake_scheduled`** → `DecisionConflictError`.
    * **Conflict: case already `pending_seal`** → `DecisionConflictError` (no double-commit).
    * **Conflict: case `committed`** → `DecisionConflictError`.
    * **Case not found** → `CaseNotFoundError`.
    * **Rationale hash matches SHA-256 of body** — assert ledger payload's `rationale_hash` value.
    * **Timer.schedule fires AFTER db commit** — use a stub timer that records call time; assert it's after the session.commit().

    `seal_decision`:
    * **Happy path** — fetches decision, writes `decision.sealed` entry, updates decision row, transitions case → `committed`, fires SSE.
    * **Idempotent: decision already sealed** → no-op, no second ledger entry, no SSE.
    * **Idempotent: decision not found (e.g., undone before seal callback fires)** → no-op.

10. **AC10 — Tests at `apps/cockpit-api/tests/test_cases_router.py` (extend).**

    * `POST /v1/cases/{id}/decisions` with valid body → 201 + response.
    * `POST` without auth (no session cookie) → 401 (per existing convention from `get_current_user`).
    * `POST` with `outcome=approve_with_conditions` + empty conditions → 422.
    * `POST` with `rationale_html` < 20 chars → 422.
    * `POST` to a case in `intake_scheduled` → 409.
    * `POST` to a case in `pending_seal` → 409 (no double-commit).
    * `POST` to a case in `committed` → 409.
    * `POST` to a non-existent case → 404.
    * Decision row written; ledger entry written; timer scheduled; SSE fired.

11. **AC11 — Tests at `apps/cockpit-api/tests/repositories/test_decision_repo.py`.**

    * `insert` + `fetch_by_id` round-trip.
    * `fetch_latest_by_case` returns most recent.
    * `update_sealed` populates `sealed_at` + `sealed_ledger_entry_id`.
    * `revert_unseal` clears `sealed_at` + `sealed_ledger_entry_id`. (Used by Story 7-5's undo when re-vibing — actually undo doesn't unseal because seal hasn't happened. Re-think this method's use case. **Option**: drop `revert_unseal`; Story 7-5's undo doesn't touch the decision row's sealed fields. The decision row stays as-is during pending_seal, undo deletes it. **Decision**: replace `revert_unseal` with `delete_by_id(session, decision_id)` — Story 7-5's undo deletes the decision row entirely, since it was never sealed. Tests verify.

12. **AC12 — Tests at `packages/contracts/tests/test_decision.py`.**

    * `CommitDecisionRequest` validation: outcome required, conditions list ≤ 10, conditions strings ≤ 200 chars + non-blank, rationale_html length 20-20_000, approve_with_conditions requires conditions.
    * `Decision` round-trip via JSON.
    * `DecisionOutcome` Literal (or Story 7-9's enum) accepts the four values; rejects others.

13. **AC13 — Tests at `packages/contracts/tests/test_ledger.py` (extend).**

    * `OfficerDecisionCommittedPayload` round-trips. `rationale_hash` exactly 64 hex chars.
    * `DecisionSealedPayload` round-trips.

14. **AC14 — `make contracts` regenerates TS types.**

    `apps/cockpit-ui/src/api-types.ts` includes `CommitDecisionRequest`, `CommitDecisionResponse`, `Decision`, `OfficerDecisionCommittedPayload`, `DecisionSealedPayload`. Story 7-1's POST consumes these.

15. **AC15 — `make lint && make test` clean.** Net new test count: ≥ 11 in `test_decision_service.py`, ≥ 9 in `test_cases_router.py` (extend), ≥ 4 in `test_decision_repo.py`, ≥ 6 in `test_decision.py`, ≥ 2 in `test_ledger.py` (extend).

16. **AC16 — End-to-end demo verification.**

    ```bash
    make demo-reset && make seed && <run intake on Vora>
    # Vora is now in decision_ready

    curl -s -X POST "http://localhost:8000/v1/cases/${VORA_ID}/decisions" \
      -H 'Content-Type: application/json' \
      -H 'cookie: session=...' \
      -d '{
        "outcome": "approve_with_conditions",
        "conditions": ["enhanced monitoring 6mo"],
        "rationale_html": "<p>The case shows...</p>"
      }' | jq .
    # → {"case_id":"...","decision_id":"dec_...","case_state":"pending_seal","seal_at":"...","ledger_entry_id":"led_..."}

    # Verify case state:
    curl -s "http://localhost:8000/v1/cases/${VORA_ID}" | jq '.state'
    # → "pending_seal"

    # Verify ledger:
    grep '"event_type":"officer.decision_committed"' ./data/ledger.jsonl | tail -1 | jq .
    # → entry with rationale_hash

    # Wait 120 seconds (or set DECISION_TIMER_WINDOW=10 env if available):
    sleep 121

    # Verify case sealed:
    curl -s "http://localhost:8000/v1/cases/${VORA_ID}" | jq '.state'
    # → "committed"

    grep '"event_type":"decision.sealed"' ./data/ledger.jsonl | tail -1 | jq .
    # → SYSTEM entry
    ```

## Tasks / Subtasks

- [x] **Task 1 — Pydantic contracts** (AC: #1, #2, #12, #13, #14)
  - [x] Subtask 1.1 — `packages/contracts/src/contracts/decision.py`.
  - [x] Subtask 1.2 — Extend `contracts/ledger.py` with `OfficerDecisionCommittedPayload` + `DecisionSealedPayload`; add to `LedgerEntry.payload` union.
  - [x] Subtask 1.3 — Re-export from `__init__.py`.
  - [x] Subtask 1.4 — `make contracts`.
  - [x] Subtask 1.5 — Tests (≥ 6 in `test_decision.py`, ≥ 2 in `test_ledger.py`).

- [x] **Task 2 — Persistence** (AC: #3, #4, #11)
  - [x] Subtask 2.1 — `DecisionRow` SQLAlchemy model.
  - [x] Subtask 2.2 — `DecisionRepo` with insert / fetch_by_id / fetch_latest_by_case / update_sealed / delete_by_id.
  - [x] Subtask 2.3 — `apps/cockpit-api/tests/repositories/test_decision_repo.py` (≥ 4 cases).

- [x] **Task 3 — `DecisionService`** (AC: #5, #6, #9)
  - [x] Subtask 3.1 — `apps/cockpit-api/src/cockpit_api/services/decision_service.py` with `commit_decision` + `seal_decision` + `DecisionConflictError`.
  - [x] Subtask 3.2 — Add `ActorType.SYSTEM` if not already present.
  - [x] Subtask 3.3 — `apps/cockpit-api/tests/services/test_decision_service.py` (≥ 11 cases).

- [x] **Task 4 — App lifecycle wiring** (AC: #6)
  - [x] Subtask 4.1 — Update `lifespan` in `main.py` to construct singletons + curry `on_seal`.
  - [x] Subtask 4.2 — Stash repos + writer on `app.state` for cross-context access.

- [x] **Task 5 — POST route** (AC: #7, #10)
  - [x] Subtask 5.1 — Add `post_decision` route to `routers/cases.py`.
  - [x] Subtask 5.2 — Tests in `test_cases_router.py` (≥ 9 cases).

- [x] **Task 6 — Verification** (AC: #15, #16)
  - [x] Subtask 6.1 — `make lint && make test` green.
  - [x] Subtask 6.2 — Manual demo per AC16.

## Dev Notes

### Architectural context (binding)

* [Source: `architecture.md#API & Communication Patterns` § A1] REST + JSON path-prefix; no tenant_id in demo.
* [Source: `architecture.md#API & Communication Patterns` § A5] RFC 7807 errors.
* [Source: `architecture.md#Project-Specific Patterns` § P5 Officer Action Pattern] **bank-buyer**: client-side WebCrypto sign + server verify. **Demo**: cut. Officer identity from session.
* [Source: `architecture.md#Demo Scope Addendum (2026-04-29)` § HSM/signing] "None. Audit log is a JSON append-only file."
* [Source: `architecture.md#Demo Scope Addendum (2026-04-29)` § Auth] user-switcher provides session-bound officer identity.
* [Source: `prd.md#Functional Requirements` FR24] commit decision.
* [Source: `prd.md#Functional Requirements` FR29] officer-signed actions — **simplified to log entry without signature** per re-scope.

### Critical pitfalls

1. **Order of operations matters.** Ledger entry → decision row → case state → DB commit → timer.schedule → SSE. The timer must NOT be scheduled before the DB commit — if the commit fails (FK violation, etc.), a phantom timer would fire `seal_decision` with a non-existent decision_id. AC9's "timer.schedule fires AFTER db commit" test verifies.

2. **`seal_decision` is idempotent.** When Story 7-5's undo cancels the timer, the timer task gets `asyncio.CancelledError` and does NOT call `seal_decision`. But there's a race: if the cancel arrives just as `_run_timer` is about to invoke `on_seal`, the timer's `_timers.get(case_id) is None or decision_id mismatch` check (Story 7-4's AC1) prevents double-seal. AC9's idempotency tests are the second line of defense — even if the check leaks, `seal_decision` short-circuits if the decision is already sealed.

3. **`undo` deletes the decision row, NOT marks it as undone.** A decision that was committed and then undone leaves no `Decision` row — the audit trail is in the ledger (`officer.decision_committed` + `officer.decision_undone` entries). Story 7-5's undo path calls `decision_repo.delete_by_id(decision_id)`. This story names that method; Story 7-5 calls it. **Document the choice**: an alternative would be marking the decision as `status=undone`. Deleting is simpler for the demo; the ledger is the auditable record.

4. **`seal_decision` runs OUTSIDE a request context** — there's no FastAPI `Depends` available. The lifespan-curried callback (AC6) is the workaround. Don't try to import a `get_session` dependency inside `seal_decision` — it would crash because there's no request scope.

5. **`session_factory` is the right primitive for `seal_decision`** — it creates a fresh AsyncSession just for this background task. Don't reuse a session across the request boundary; SQLAlchemy's session lifecycle gets ugly fast.

6. **`rationale_hash` is SHA-256 of the raw `rationale_html` bytes (UTF-8).** Don't normalize whitespace, don't strip tags. The hash is the audit anchor — changing it after-the-fact breaks the chain. Tests AC9 verify the exact byte sequence's hash.

7. **`outcome` enum / Literal alignment with Story 7-9**: this story declares the Literal in `decision.py`. When Story 7-9 ships, it MAY refine to `StrEnum`. Either form serializes identically over the wire. Keep this story's contract surface stable — Story 7-9's PR can update the type alias without churning consumers.

8. **`approve_with_conditions` requires non-empty conditions** — Pydantic `model_validator` enforces. Mirror Story 7-9 § AC.

9. **`escalate_to_edd` is a valid outcome but doesn't auto-enqueue for Lead approval in Story 7-7.** That auto-enqueue is Epic 8 (Story 8-7) or Epic 10. For this story, just persist the outcome. Document the deferred work.

10. **`ActorType.SYSTEM`** — check `contracts/ledger.py` ActorType enum members. The current set is `AGENT` and `OFFICER` (per Story 3-1). Add `SYSTEM` as a new member; ensure no existing tests assume the enum is closed at two values.

11. **Session usage in `commit_decision` vs `seal_decision`** — `commit_decision` receives a session via FastAPI's `Depends(get_session)` (request-scoped); `seal_decision` opens its own via `session_factory`. Don't accidentally cross-contaminate.

12. **`timer.schedule` is sync; lifespan-curried `on_seal` is async.** Story 7-4's `_run_timer` `await`s `on_seal`. Verify the type signature matches.

### Story dependencies

* **Strict prereqs:** Story 7-4 (DecisionTimerService + PENDING_SEAL state + SSE events), Story 1-6 (`get_current_user`), Story 3-1 (LedgerWriter + LedgerEntry shape), Story 4-6 (`SseRegistry.publish_safe`), Story 2-1 (CaseState + assert_transition), Story 2-2 (CaseRepo).
* **Soft prereq:** Story 7-9 (DecisionOutcome contract refinement). If 7-9 lands first, this story uses its enum; if not, this story declares the Literal and 7-9 refines.
* **Read by:** Story 7-1 (POST consumer), Story 7-5 (undo path consumes `decision_repo.delete_by_id` + the decision_id), Story 7-6 (consumes `latest_decision` envelope addition — Story 7-6 owns that piece, but the data path runs through this story's tables), Story 9-1 (audit timeline reads decision-related ledger entries).

### Project Structure Notes

This story creates:
- `packages/contracts/src/contracts/decision.py`
- `packages/contracts/tests/test_decision.py`
- `apps/cockpit-api/src/cockpit_api/services/decision_service.py`
- `apps/cockpit-api/src/cockpit_api/repositories/decision_repo.py`
- `apps/cockpit-api/tests/services/test_decision_service.py`
- `apps/cockpit-api/tests/repositories/test_decision_repo.py`
- `DecisionRow` SQLAlchemy model in `db/models.py`

This story modifies:
- `packages/contracts/src/contracts/ledger.py` — adds `OfficerDecisionCommittedPayload` + `DecisionSealedPayload`; extends payload union; adds `ActorType.SYSTEM` if absent
- `packages/contracts/src/contracts/__init__.py` — public exports
- `packages/contracts/tests/test_ledger.py` — extend
- `apps/cockpit-api/src/cockpit_api/main.py` — extends `lifespan` to construct singletons + curry `on_seal`
- `apps/cockpit-api/src/cockpit_api/routers/cases.py` — adds POST `/decisions` route
- `apps/cockpit-api/tests/test_cases_router.py` — extend
- `apps/cockpit-ui/src/api-types.ts` — regenerated by `make contracts`

This story does NOT create:
- The DecisionZone UI (Story 7-1)
- The undo endpoint (Story 7-5)
- The `decisions/active/timer` endpoint (Story 7-5)
- The seal animation (Story 7-6)
- The `latest_decision` envelope addition on `GET /v1/cases/{id}` (Story 7-6 owns that)
- Cryptographic signing infrastructure (cut from demo)
- A Lead-approval auto-enqueue for `escalate_to_edd` (deferred to Epic 8/10)

### References

- [Source: `epics.md#Epic 7` § Story 7.11] original AC (signature ceremony cut)
- [Source: `architecture.md#API & Communication Patterns`] § A1, § A5
- [Source: `architecture.md#Project-Specific Patterns`] § P4, § P5
- [Source: `architecture.md#Demo Scope Addendum (2026-04-29)`]
- [Source: `prd.md#Functional Requirements`] FR24, FR29
- [Source: `7-4-120-second-undo-timer-in-memory.md`] timer service + PENDING_SEAL state
- [Source: `7-1-decision-zone-component-with-tiptap-editor.md`] consumer
- [Source: `7-5-undopill-with-countdown-ring-and-reason-capture-modal.md`] undo path consumer
- [Source: `apps/cockpit-api/src/cockpit_api/services/ledger_service.py`] LedgerWriter API

### Demo verification protocol

Per AC16. The 120s wait is the slow loop step — set `DECISION_TIMER_WINDOW=10` (Story 7-4's testing override env, if available) for fast iteration.

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
| 2026-05-08 | Story 7.7 drafted. Demo replacement for bank-buyer Story 7.11: POST /decisions endpoint, decisions table + repo, DecisionService.commit_decision + seal_decision callback (curried by lifespan), OfficerDecisionCommittedPayload + DecisionSealedPayload typed ledger arms with rationale_hash. Ed25519 signing entirely cut; officer identity from session. |
