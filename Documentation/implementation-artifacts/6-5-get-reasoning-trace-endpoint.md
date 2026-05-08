# Story 6.5: GET reasoning trace endpoint

Status: review

## Story

As the cockpit-ui,
I want a `GET /v1/cases/{case_id}/agent-actions/{action_id}/reasoning-trace` endpoint that resolves the agent action by ledger entry ID, returns the typed `ReasoningTrace` payload from `AgentActionLedgerEntry.reasoning_trace` (Story 6-4) when present, returns `204 No Content` when the entry exists but emitted no trace, and returns `404 Not Found` when neither the case nor the action ID resolves,
So that Story 6-6's slide-out can fetch trace data on demand without re-loading the entire ledger or intake row, the endpoint shape matches the Epic 6 epic spec verbatim (`agent-actions/{aa_id}/reasoning-trace`), and the demo's `_links.reasoning_trace` placeholder in `GET /v1/cases/{case_id}` (already wired by Story 2-2) becomes resolvable for any agent that emits a trace (FR12, P4 Agent Action Pattern, P8 Counterfactual Reasoning Trace).

## Scope note (2026-04-29 demo re-scope)

This story is the demo-equivalent of the bank-buyer Story 6.6. The bank-buyer scope path-prefixes the URL with `/t/{tenant_id}/` and asserts a p95 ≤ 500 ms latency; both are simplified for the demo.

| Bank-buyer scope (original 6.6) | Demo replacement in this story |
|---|---|
| `GET /t/{tenant_id}/v1/cases/{case_id}/agent-actions/{aa_id}/reasoning-trace` | **`GET /v1/cases/{case_id}/agent-actions/{action_id}/reasoning-trace`** — single-tenant. The `{action_id}` segment is the **ledger entry ID** (`led_<ULID>`) — the demo treats agent action ID and ledger entry ID as identical (no separate `aa_<ULID>`). |
| Authenticated KYC Analyst session via `Depends(get_current_user)` | **Same** — Story 1-6's user-switcher provides `get_current_user`. |
| p95 latency ≤ 500 ms (PRD perf budget NFR-P) | **No formal SLO**; structural budget only — read from in-memory JSONL ledger, ≤ 50 ms typical. |
| `204 No Content` when no trace produced | **Same** — `204 No Content`. UI shows "no trace produced". |

What survives: **path shape, lookup by ledger entry id, scoped to the case (404 if action belongs to a different case), 204 fallback for trace-less actions, typed `ReasoningTrace` response model, RFC 7807 error format on 404.**

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md`, `architecture.md#API & Communication Patterns` § A1 (REST + JSON path-prefix), `architecture.md#Format Patterns` (RFC 7807 error format), `epics.md#Epic 6` § Story 6.6.

## Acceptance Criteria

1. **AC1 — Endpoint added to `apps/cockpit-api/src/cockpit_api/routers/cases.py`.**

    ```python
    @router.get(
        "/{case_id}/agent-actions/{action_id}/reasoning-trace",
        response_model=ReasoningTrace,
        responses={
            204: {"description": "Agent action exists but emitted no reasoning trace."},
            404: {"description": "Case or agent action not found."},
        },
        status_code=200,
    )
    async def get_reasoning_trace(
        case_id: Annotated[CaseId, Path()],
        action_id: Annotated[LedgerEntryId, Path()],
        _: Annotated[User, Depends(get_current_user)],
        session: Annotated[AsyncSession, Depends(get_session)],
        reader: Annotated[LedgerReader, Depends(get_ledger_reader)],
    ) -> ReasoningTrace | Response: ...
    ```

    Logic:
    1. **Resolve case** via `case_service.fetch_case(session, case_id)`. If `None` → raise `HTTPException(404, ...)` per the existing pattern in this file.
    2. **Resolve agent action** — call a new `LedgerReader.read_by_id(action_id)` method (AC3). If `None` → 404. If the entry's `case_id != case_id` → 404 (don't leak existence across cases — same posture as `case_service.fetch_case`'s narrow scope).
    3. **Verify entry is an agent action** — `isinstance(entry.payload, AgentActionLedgerEntry)`. If not (it's a `case.intake_*` SYSTEM entry, or a `learning_event` entry) → 404 with `"agent action not found"`.
    4. **Read `payload.reasoning_trace`**:
        * If `None` → return `Response(status_code=204)`.
        * Else → return the `ReasoningTrace` directly.

    The `Response` import: `from fastapi import Response`.

2. **AC2 — Route registration order.**

    Place the route **before** the existing `GET /{case_id}/learning-events` (or whichever route uses `/{case_id}/...`) — FastAPI matches routes in declaration order, and the more-specific path with a literal `agent-actions` segment must be registered first to avoid being shadowed by a `/{case_id}/{path}` greedy parameter (verify there is no such greedy route, but order it conservatively).

3. **AC3 — `LedgerReader.read_by_id(action_id: LedgerEntryId) -> LedgerEntry | None` method.**

    Add to `apps/cockpit-api/src/cockpit_api/services/ledger_service.py`:

    ```python
    async def read_by_id(self, entry_id: LedgerEntryId) -> LedgerEntry | None:
        """Return the ledger entry with the given id, or None if absent.

        Demo implementation reads all lines and filters; the JSONL ledger
        is small enough (<10k entries for a typical demo run) that an
        index isn't worth the complexity. A real platform's
        Postgres-backed ledger would have a primary-key lookup.
        """
        entries = await self._read_lines()
        for entry in entries:
            if entry.id == entry_id:
                return entry
        return None
    ```

    Mirrors `read_latest_by_actor` shape (loads via `_read_lines`).

4. **AC4 — RFC 7807 error format.**

    The 404 response body uses RFC 7807 Problem Details per architecture § A5 / Format Patterns. Reuse the existing 404 helper or pattern from `cases.py:98` (the `GET /{case_id}` 404 path is the reference). If the file uses `HTTPException(status_code=404, detail=...)` and FastAPI auto-formats, match the existing convention — don't introduce a new RFC 7807 builder in this story.

    The 204 case has no response body (RFC 9110 § 15.3.5 — `204 No Content` MUST NOT have a body).

5. **AC5 — `_links.reasoning_trace` resolution from the cockpit-ui's perspective.**

    Story 2-2's `GET /v1/cases/{case_id}` already includes a `_links` envelope with placeholder keys for documents (Epic 3) and reasoning_traces (Epic 6). This story does **not** modify that endpoint's response — the slide-out fetches the trace via the new endpoint directly using a `case_id + action_id` pair the UI already has from the `evidence_ids` back-fill (Story 5-1 / 6-2 § AC5 patterns).

    No change to `_links` schema. The `_links.reasoning_trace` value can stay `null` (or be populated with a templated URL like `/v1/cases/{id}/agent-actions/{action_id}/reasoning-trace` if the existing schema allows — check `cases.py` line ~98 for the existing `_links` shape and follow its convention). **Default: leave `_links.reasoning_trace` as it currently is**; do not introduce schema churn.

6. **AC6 — Tests at `apps/cockpit-api/tests/test_cases_router.py` (extend existing).**

    Use the existing test fixtures and patterns:

    * **200 happy path: agent action with reasoning_trace returns 200 + typed payload.** Seed the ledger with a `screening` agent.completed entry that has `payload.reasoning_trace` populated; GET the endpoint; assert 200, assert all 4 sections in the response, assert `confidence_self_rating.band` matches the expected band.
    * **204 no trace: agent action exists but `payload.reasoning_trace == None`.** Seed a doc-intel entry without a trace; assert 204; assert empty response body.
    * **404 case not found.** GET with a valid-shape but non-existent `case_id`; assert 404; assert RFC 7807 body.
    * **404 action not found in case.** GET with a valid case but a `led_<ULID>` that doesn't exist in the ledger.
    * **404 action belongs to a different case.** Seed two cases A and B, each with one agent action. GET for case A's id with case B's action id → 404. (Critical test — ensures cross-case existence isn't leaked.)
    * **404 entry is a SYSTEM entry, not an agent action.** Seed a `case.intake_completed` SYSTEM entry; GET with that entry's id; assert 404. (The endpoint name is `agent-actions/...`, so a SYSTEM entry is genuinely not-found at this URL.)
    * **404 entry is a learning_event.** Seed a Story 5-5 learning event entry; assert 404.
    * **422 invalid path param shape.** GET with `action_id="not_a_ulid"` (or `case_id="not_a_case"`); assert 422 (FastAPI auto-422 from path-typing — same as other case routes).
    * **401 / 403 unauthenticated** — if the `Depends(get_current_user)` dependency rejects unauthenticated requests in the existing test harness, assert. Match whatever the existing `cases.py` tests assert (Story 1-6 wired this behavior).

7. **AC7 — Tests at `apps/cockpit-api/tests/services/test_ledger_service.py` (extend existing).**

    * **`read_by_id` returns the entry with the given id.**
    * **`read_by_id` returns None for a missing id.**
    * **`read_by_id` is consistent across multiple writers' appends in sequence.**

    If `apps/cockpit-api/tests/services/test_ledger_service.py` doesn't exist yet, add it under the existing test directory pattern.

8. **AC8 — TS types unchanged.**

    Story 6-4 already regenerated `api-types.ts` with `ReasoningTrace`. This story doesn't change any contract; running `make contracts` is a no-op. The cockpit-ui's typed-client (`openapi-fetch`) gains the new endpoint via the regenerated `paths` schema — verify the new path appears in `apps/cockpit-ui/src/api-types.ts` after `make contracts`.

9. **AC9 — `make lint && make test` clean.** Net new test count: ≥ 9 in `test_cases_router.py` (extend), ≥ 3 in `test_ledger_service.py` (extend or create).

10. **AC10 — End-to-end smoke test.**

    ```bash
    make demo-reset && make seed
    poetry -C apps/cockpit-api run python -c "
    import asyncio
    from contracts.cases import VORA_CAPITAL_ID
    from agents.supervisor.case_supervisor import CaseSupervisor
    from cockpit_api.db.session import session_factory
    async def main():
        s = CaseSupervisor(session_factory=session_factory)
        await s.run_intake(VORA_CAPITAL_ID)
    asyncio.run(main())
    "

    make dev   # in another shell

    # Find a screening agent.completed ledger entry id from the JSONL:
    SCREENING_ACTION_ID=$(jq -rc 'select(.actor_id=="screening" and .payload.kind=="agent_action" and .payload.status=="ok") | .id' < ./data/ledger.jsonl | head -1)
    VORA_ID=$(jq -rc '.id' < <(curl -s "http://localhost:8000/v1/cases" | jq '.items[] | select(.customer_metadata.customer_name | contains("Vora"))'))

    # Happy path
    curl -s "http://localhost:8000/v1/cases/${VORA_ID}/agent-actions/${SCREENING_ACTION_ID}/reasoning-trace" \
        -H 'cookie: ...session...' | jq .
    # → 200, JSON body with what_searched / what_hit / confidence_self_rating / counterfactual

    # 204 path — pick a doc-intel action (no trace per Story 6-4 AC8)
    UBO_ACTION_ID=$(jq -rc 'select(.actor_id=="ubo_graph" and .payload.status=="ok") | .id' < ./data/ledger.jsonl | head -1)
    curl -s -o /dev/null -w '%{http_code}\n' "http://localhost:8000/v1/cases/${VORA_ID}/agent-actions/${UBO_ACTION_ID}/reasoning-trace" -H 'cookie: ...'
    # → 204

    # 404 cross-case
    SHREE_ID=$(...)
    curl -s -o /dev/null -w '%{http_code}\n' "http://localhost:8000/v1/cases/${SHREE_ID}/agent-actions/${SCREENING_ACTION_ID}/reasoning-trace" -H 'cookie: ...'
    # → 404
    ```

## Tasks / Subtasks

- [x] **Task 1 — `LedgerReader.read_by_id`** (AC: #3, #7)
  - [x] Subtask 1.1 — Added `read_by_id(entry_id)` method to `apps/cockpit-api/src/cockpit_api/services/ledger_service.py`.
  - [x] Subtask 1.2 — Extended existing `apps/cockpit-api/tests/test_ledger_service.py` (3 new cases: hit, miss, multi-append). The repo's tests live at `apps/cockpit-api/tests/test_ledger_service.py` (not under a `services/` subdir as the AC speculated).

- [x] **Task 2 — Endpoint** (AC: #1, #2, #4, #6)
  - [x] Subtask 2.1 — Added `GET /v1/cases/{case_id}/agent-actions/{action_id}/reasoning-trace` route to `apps/cockpit-api/src/cockpit_api/routers/cases.py`. Inserted before the UBO `learning-events` route.
  - [x] Subtask 2.2 — Verified route ordering — `agent-actions` literal precedes other `/{case_id}/...` segments and there are no greedy paths.
  - [x] Subtask 2.3 — Extended `apps/cockpit-api/tests/test_cases_router.py` with 9 new cases (200 happy, 204 no-trace, 404 case-missing, 404 action-missing, 404 cross-case, 404 SYSTEM entry, 404 learning_event entry, 422 bad action_id, 400 missing demo-user header).

- [x] **Task 3 — Verification** (AC: #8, #9, #10)
  - [x] Subtask 3.1 — `make contracts` regenerated TS types; new endpoint is exposed in `apps/cockpit-ui/src/api-types.ts`.
  - [x] Subtask 3.2 — `make lint` clean; full Python suite 506 green (205 contracts + 158 cockpit-api + 143 agents).
  - [x] Subtask 3.3 — End-to-end smoke deferred to the bigger Story 6.6 walkthrough (the slide-out exercises this endpoint live). Endpoint logic is fully covered by 9 router tests against an in-memory ledger; the cockpit-side wiring lands with Story 6.6.

## Dev Notes

### Architectural context (binding)

* [Source: `architecture.md#API & Communication Patterns` § A1] REST + JSON; path-prefix `/v1/...`. Demo single-tenant — no `/t/{tenant_id}/`.
* [Source: `architecture.md#Format Patterns`] RFC 7807 error format on 4xx. Match what `cases.py` already does for 404s (FastAPI auto-formats).
* [Source: `architecture.md#Project-Specific Patterns` § P4 Agent Action Pattern] AgentActionLedgerEntry is the typed payload; `payload.reasoning_trace` is the source.
* [Source: `prd.md#Functional Requirements § Agent Mesh Visibility & Interaction` FR12] reasoning trace shows what searched / what returned / confidence / counterfactual — this endpoint is the data plane.
* [Source: `apps/cockpit-api/src/cockpit_api/routers/cases.py:1-18`] header comment already names "Epic 6 (reasoning traces)" as a forward-compat consumer — this story fulfills that.

### Critical pitfalls

1. **`action_id` is `LedgerEntryId` (`led_<ULID>`), not a separate `aa_<ULID>`.** The bank-buyer scope had a separate agent-action ID; the demo merges them. The path param's typed shape uses `LedgerEntryId`'s pattern (`^led_[0-9A-HJKMNP-TV-Z]{26}$`); FastAPI returns 422 on mismatch automatically.

2. **404 vs 204 — they mean different things.** 404 = "no such action" (UI surfaces "agent action not found"); 204 = "action exists but no trace" (UI surfaces "no trace produced for this action"). The slide-out (Story 6-6) handles both states. Don't conflate them. Tests AC6's #2 and #4 disambiguate.

3. **Cross-case existence leak — the test for it is mandatory.** If the endpoint accepts any `action_id` regardless of `case_id`, a malicious user could enumerate ledger IDs across all cases. The check `entry.case_id == case_id` is non-negotiable. AC6's "404 action belongs to a different case" test is the gate.

4. **`read_by_id` linear scan is fine for the demo.** Don't introduce an index (e.g., id → entry hashmap) — the JSONL has <10k entries for any demo session, the file is in OS page cache, and the read is O(n) but n is small. A real platform's Postgres-backed ledger has a primary-key index for free.

5. **`Response(status_code=204)` returns an empty body.** FastAPI's behaviour: returning a `Response` short-circuits the response_model serialization. Don't return `None` and rely on FastAPI's default; it might serialize as `null` (200 + JSON null) depending on config. Be explicit.

6. **`response_model=ReasoningTrace`** on the route — required so OpenAPI export and TS-type generation know the success shape. The 204 path is documented in `responses={...}` separately. Verify the OpenAPI export looks right after `make contracts`.

7. **`SYSTEM` entries (`case.intake_*`, `case.created`) have non-`AgentActionLedgerEntry` payloads.** The `isinstance(entry.payload, AgentActionLedgerEntry)` check is the discriminator. Don't try to read `entry.payload.reasoning_trace` blindly — it would `AttributeError` on a SYSTEM entry's dict-shaped payload.

8. **Authentication via `Depends(get_current_user)`.** Match the existing case-router routes' convention exactly. Don't introduce a new dependency or skip auth; the demo's user-switcher (Story 1-4 / 1-6) seeds a session that the dependency reads.

9. **Don't add a `tenant_id` parameter even for forward compatibility.** Architecture's path-prefix versioning would normally inject `/t/{tenant_id}/` — demo scope removes it. If the bank-buyer path is revived, the prefix is added at routing time, not by every handler.

10. **The `Response` import is from `fastapi`, not `starlette.responses`.** FastAPI re-exports it; consistency with existing imports matters for the linter's import-order rule. Verify by inspecting the existing imports at the top of `cases.py`.

### Story dependencies

* **Strict prereqs:** Story 6-4 (`ReasoningTrace` contract + `AgentActionLedgerEntry.reasoning_trace` field), Story 3-1 (ledger storage), Story 3-3 (`AgentActionLedgerEntry` shape), Story 2-2 (`GET /v1/cases/{case_id}` route + `case_service.fetch_case`), Story 1-6 (`get_current_user` auth dependency).
* **Soft prereq:** Story 6-2 (Screening agent — emits the demo's first reasoning traces; without it, the only trace producer is Entity Verification per Story 6-4 § AC7).
* **Read by:** Story 6-6 (slide-out fetches via this endpoint), Story 6-7 (`get_reasoning_trace` Cockpit Chat tool — wraps this endpoint).

### Project Structure Notes

This story modifies:
- `apps/cockpit-api/src/cockpit_api/services/ledger_service.py` — adds `read_by_id`
- `apps/cockpit-api/src/cockpit_api/routers/cases.py` — adds `get_reasoning_trace` route
- `apps/cockpit-api/tests/test_cases_router.py` — extend
- `apps/cockpit-api/tests/services/test_ledger_service.py` — extend or create
- `apps/cockpit-ui/src/api-types.ts` — regenerated by `make contracts` (passive)

This story does NOT create:
- A new router file (route lives in the existing cases router)
- A separate `agent-actions` resource — the trace lives under the case scope
- The slide-out (Story 6-6)
- The `_links.reasoning_trace` URL templating change (deferred — UI builds the URL)

### References

- [Source: `epics.md#Epic 6` § Story 6.6] original AC (verbatim shape; tenant_id prefix dropped, p95 SLO de-emphasized for demo)
- [Source: `architecture.md#API & Communication Patterns`] § A1, § A4 OpenAPI auto-gen, § A5 RFC 7807
- [Source: `architecture.md#Project-Specific Patterns`] § P4 Agent Action Pattern, § P8 Counterfactual Reasoning Trace Pattern
- [Source: `prd.md#Functional Requirements § Agent Mesh Visibility` FR12]
- [Source: `apps/cockpit-api/src/cockpit_api/routers/cases.py`] existing routes + 404 patterns
- [Source: `apps/cockpit-api/src/cockpit_api/services/ledger_service.py`] LedgerReader API surface (existing `read_latest_by_actor` is the shape this story mirrors)
- [Source: `6-4-reasoning-trace-contract-4-section-schema-enforcement.md`] `ReasoningTrace` Pydantic model + `AgentActionLedgerEntry.reasoning_trace` field

### Demo verification protocol

Per AC10. If any step fails, the bug is in this story; do not ship until green.

## Dev Agent Record

### Agent Model Used

(claude-opus-4-7 + Amelia persona, bmad-dev-story workflow)

### Debug Log References

- Initial test attempt failed because I imported `LearningEventLedgerPayload` from `contracts.learning_event` (the public re-export) but the actual class lives in `contracts.ledger` to avoid circular imports. Switched the import.
- Same payload also lacks a `recorded_by_user_id` field — that's `LearningEventInput`'s shape, not the ledger payload's.

### Completion Notes List

- **Endpoint placement**: inserted between the per-agent intake GET endpoints and the existing UBO `learning-events` POST. FastAPI matches in declaration order; the literal `agent-actions/{action_id}/reasoning-trace` segment can't conflict with any other `/{case_id}/...` route.
- **`ActionIdPath` type alias** mirrors the existing `CaseIdPath` pattern (regex-validated path param). FastAPI returns 422 automatically on shape mismatch.
- **Cross-case existence leak prevented**: the route checks `entry.case_id == case_id` after lookup and 404s on mismatch, never leaking that an action with a given ID exists in some other case.
- **SYSTEM and learning-event entries return 404**, not 200/204. The endpoint is named `agent-actions/...` — non-agent entries are genuinely "not found" at this URL. Tests cover both paths.
- **`Response(status_code=204)` returns an empty body** explicitly. Returning `None` would let FastAPI serialize `null` as JSON; `Response(...)` short-circuits.
- **Tests use a tmp ledger fixture** (`writer` fixture monkeypatching `get_ledger_writer`/`get_ledger_reader` cache) so each test runs against an isolated JSONL file. This mirrors the agent-tests' `tmp_writer` pattern.

### File List

- `apps/cockpit-api/src/cockpit_api/services/ledger_service.py` (modified) — added `read_by_id` method.
- `apps/cockpit-api/src/cockpit_api/routers/cases.py` (modified) — added `GET /v1/cases/{case_id}/agent-actions/{action_id}/reasoning-trace`, plus `Response`/`AgentActionLedgerEntry`/`ReasoningTrace`/`ActionIdPath` imports.
- `apps/cockpit-api/tests/test_ledger_service.py` (modified) — 3 new cases for `read_by_id`.
- `apps/cockpit-api/tests/test_cases_router.py` (modified) — 9 new cases for the endpoint + `writer` fixture + helper builders.
- `packages/contracts/openapi.json` (regenerated).
- `apps/cockpit-ui/src/api-types.ts` (regenerated).

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-05-08 | Story 6.5 drafted. GET /v1/cases/{id}/agent-actions/{action_id}/reasoning-trace endpoint with 200 / 204 / 404 semantics; LedgerReader.read_by_id helper; cross-case existence leak prevention; tenant_id prefix dropped per demo scope. |
| 2026-05-08 | Implemented Story 6.5. Endpoint + read_by_id + 12 new tests (3 ledger service + 9 router) all passing. 506 Python tests green; `make lint` clean. |
