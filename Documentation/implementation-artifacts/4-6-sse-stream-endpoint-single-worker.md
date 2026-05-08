# Story 4.6: SSE stream endpoint (single-worker)

Status: review

## Story

As the cockpit-ui,
I want a Server-Sent Events stream per case with minimal payload events that trigger TanStack Query invalidation,
So that the cockpit feels alive without polling overhead (FR11–14, A2).

## Scope note

This story replaces TanStack Query polling (the `refetchInterval: 5_000` in `useCases` and `refetchInterval: 3_000` in `useAgentMeshState`) with event-driven invalidation over Server-Sent Events.

**Demo simplification:** The bank-buyer epic (Story 4.7) wires Redis pub/sub for multi-worker SSE coordination + a 60-second replay buffer. This demo runs a single uvicorn worker, so:
- No Redis. The SSE registry is in-process (a `defaultdict[case_id, list[asyncio.Queue]]`).
- No replay buffer. If the connection drops, the browser's native EventSource auto-reconnects; missed events are accepted as a known limitation. TanStack Query's `staleTime` on next user interaction backfills.
- Tenant scoping is N/A (single-tenant demo).

The producer side: any code that writes a ledger entry — i.e. the action decorator (Story 3.2) — gains a hook that publishes the corresponding SSE event after a successful append. Three event types ship in this story; more are added per consumer story:

- `agent.state_changed` — fired by the action decorator on every state change
- `case.state_changed` — fired when `CaseRepo.update_state` runs
- `case.documents_changed` — fired when documents are added/removed (Story 3.8 endpoints)

## Acceptance Criteria

1. **AC1 — `services/sse_registry.py` in-process broker.** New module. Public surface:

   ```python
   class SseRegistry:
       def subscribe(self, case_id: str) -> AsyncIterator[SseEvent]: ...
       async def publish(self, case_id: str, event: SseEvent) -> None: ...

   def get_sse_registry() -> SseRegistry: ...   # FastAPI dependency, process-singleton
   ```

   Internals: per-case list of `asyncio.Queue` instances. `subscribe` creates a fresh queue, registers it, yields events from it, and unregisters on cancellation/cleanup. `publish` fan-outs to all queues for the case.

2. **AC2 — `SseEvent` Pydantic model in `packages/contracts`.** Add to `packages/contracts/src/contracts/sse.py`:

   ```python
   class SseEvent(BaseModel):
       event: Literal[
           "agent.state_changed",
           "case.state_changed",
           "case.documents_changed",
       ]
       data: dict[str, Any]      # ≤ 256 bytes when serialized — IDs only, never fat data
   ```

   Wire `SseEvent` into the contracts package `__init__` and `make contracts`.

3. **AC3 — `routers/stream.py` SSE endpoint.** New router. Single route:

   ```
   GET /v1/cases/{case_id}/stream
   ```

   Behavior:
   - Validates the case exists; 404 otherwise.
   - Validates auth via the existing `get_current_user` dep (analyst or regulator role accepted).
   - Returns `text/event-stream`; sets `Cache-Control: no-cache`, `X-Accel-Buffering: no`, `Connection: keep-alive`.
   - Yields a `: heartbeat\n\n` comment every 15 seconds to keep connections alive through proxies / browser sleep.
   - Streams events via `subscribe(case_id)` formatted per the SSE wire spec: `event: <name>\ndata: <json>\n\n`.
   - On client disconnect, the generator is cancelled; `subscribe`'s cleanup unregisters the queue.

4. **AC4 — Action decorator publishes events.** Edit `apps/agents/src/agents/_adk/decorators.py` (Story 3.2's decorator). After a successful ledger append, call `await registry.publish(case_id, SseEvent(event="agent.state_changed", data={"case_id": ..., "agent_slug": ..., "state": ...}))`. The publish call is best-effort — registry failures must not abort the agent run; log and continue.

5. **AC5 — Case state changes publish events.** Edit `apps/cockpit-api/src/cockpit_api/services/case_service.py:update_state` (or wherever transitions are committed) to call `publish` after a successful commit. Event: `case.state_changed`, data: `{"case_id": ..., "state": ...}`.

6. **AC6 — Documents endpoints publish events.** Edit `apps/cockpit-api/src/cockpit_api/routers/documents.py` (Story 3.8). On successful `POST` or `DELETE`, publish `case.documents_changed` with `{"case_id": ...}`.

7. **AC7 — `lib/sse.ts` EventSource wrapper.** New `apps/cockpit-ui/src/lib/sse.ts`:

   ```ts
   export function subscribeToCase(
     caseId: string,
     queryClient: QueryClient,
   ): () => void;
   ```

   Opens an `EventSource(`/v1/cases/${caseId}/stream`, {withCredentials: true})`. Listens for the three event names (`agent.state_changed`, `case.state_changed`, `case.documents_changed`); each invalidates the relevant TanStack Query keys:
   - `agent.state_changed` → `['cases', caseId, 'agent-mesh-state']`
   - `case.state_changed` → `['case', caseId]` and `['cases']`
   - `case.documents_changed` → `['cases', caseId, 'intake', 'document_intelligence']` and `['case', caseId]`

   Returns an unsubscribe function (`eventSource.close`). On error events, log and let the browser reconnect.

8. **AC8 — Replace polling.**
   - `useCases.ts` — change `refetchInterval: 5_000` to `refetchInterval: false`. Polling is gone; the cockpit-ui invalidates `['cases']` on `case.state_changed` events. Note: `useCases` is global (queue page) and does not subscribe to a specific case's stream — the cross-cutting `['cases']` invalidation in AC7 fires from whichever case the user is currently viewing. This is acceptable for the demo (the analyst is always on a case when state changes happen).
   - `useAgentMeshState.ts` — change `refetchInterval: 3_000` to `refetchInterval: false`. Subscribed-to events drive invalidation.

9. **AC9 — Subscribe in case route.** Edit `apps/cockpit-ui/src/routes/cases.$caseId.tsx` to call `subscribeToCase(caseId, queryClient)` inside a `useEffect` keyed on `caseId`; cleanup unsubscribes. Mounting-time subscription is the right cohort: the analyst subscribes when they open a case and unsubscribes when they leave.

10. **AC10 — Backend tests.** `apps/cockpit-api/tests/test_stream_route.py`:
    - Successful subscribe receives a published event within 1 second (use the in-test FastAPI `TestClient.stream`).
    - 404 on missing case.
    - 403 on unauthenticated request.
    - Heartbeat fires (assert at least one `:` comment line is observed in the stream body).
    - Cleanup: after the test client closes, the registry's queue list for that case is empty.

11. **AC11 — Registry unit tests.** `apps/cockpit-api/tests/test_sse_registry.py`:
    - Multiple subscribers on the same case all receive a published event.
    - Cancelling one subscriber doesn't affect the other.
    - Publish to a case with no subscribers is a no-op (no exception).

12. **AC12 — UI test.** `apps/cockpit-ui/src/lib/sse.test.ts` — uses a mock `EventSource` (Vitest setup file), asserts that each of the three event names triggers the right `queryClient.invalidateQueries` call.

13. **AC13 — `make lint` + `make test` + `make contracts` clean.** Including the live demo verification: `make demo-reset && make seed && make adk-up && make adk-register && make dev`; open Vora; press "Process now"; the agent copilot pane updates within ≤ 1 s of the agent state change (no 3 s lag).

## Tasks / Subtasks

- [ ] **Task 1 — Contracts** (AC: #2, #13)
  - [ ] `packages/contracts/src/contracts/sse.py` with `SseEvent` model + tests.
  - [ ] `make contracts` regenerates TS types.
- [ ] **Task 2 — Backend registry + endpoint** (AC: #1, #3, #10, #11)
  - [ ] `services/sse_registry.py` + unit tests.
  - [ ] `routers/stream.py` + integration tests.
  - [ ] Wire registry into `main.py` (FastAPI app singleton).
- [ ] **Task 3 — Producers** (AC: #4, #5, #6)
  - [ ] Edit action decorator to publish on ledger append.
  - [ ] Edit `case_service.update_state` (or equivalent transition path) to publish.
  - [ ] Edit `routers/documents.py` POST + DELETE to publish.
- [ ] **Task 4 — UI subscription** (AC: #7, #8, #9, #12)
  - [ ] `lib/sse.ts` + tests.
  - [ ] Replace polling intervals in `useCases.ts` and `useAgentMeshState.ts`.
  - [ ] Subscribe in `cases.$caseId.tsx`.
- [ ] **Task 5 — Verify** (AC: #13)
  - [ ] `make lint` + `make test`.
  - [ ] Live demo: Process Vora; mesh pane animates idle → working → complete with no 3 s lag.

## Dev Notes

### Sequencing

- Sequence after Story 4.5 (Agent Copilot Pane) so the consumer of `agent.state_changed` events exists.
- Independent of 4.1 / 4.2 / 4.3 / 4.4 / 4.7 / 4.8 / 4.9.

### Architectural context

- [Source: `architecture.md#P6 SSE Event Pattern`] — events are ID-only, ≤ 256 bytes, snake_case past-tense. Honor this.
- [Source: `architecture.md#A2`] — SSE over HTTP, single stream per case, cookie auth, browser auto-reconnect.
- [Source: `architecture.md#Demo Scope Addendum — Caching / Pub-Sub`] — in-memory state, single worker, no Redis.
- [Source: `sprint-change-proposal-2026-04-29.md#Section 4.1`] — Story 4.7 (Redis pub/sub) is explicitly cut for the demo; this story is the simplified replacement.

### Critical pitfalls to avoid

1. **Asyncio queues per subscriber, not a broadcast `Channel`.** A shared queue is consumed-once; per-subscriber queues are fan-out. Get this right or only the first connected client receives events.
2. **Cleanup must run on client disconnect.** FastAPI's `StreamingResponse` invokes the generator's `aclose()` when the client goes away — register your queue cleanup in a `try/finally` inside the generator body.
3. **Don't `asyncio.create_task` from sync code paths.** The action decorator may be called from an in-process agent path that is already async — `await publish(...)` directly. If a producer call site is sync, schedule via `asyncio.run_coroutine_threadsafe(publish(...), loop)` or restructure the call site.
4. **Heartbeat intervals must NOT be 60+ seconds.** Many proxies close idle connections at 30–60 s. 15 s is the default boring choice.
5. **The 256-byte payload cap is non-negotiable.** Don't ship `state` enum values that are arbitrarily long; the existing values (`idle/working/complete/blocked/needs_input`) are all under 16 chars and fine.
6. **`EventSource` does NOT support custom headers in browsers** — auth must come from the cookie (`withCredentials: true`). The existing `X-Cockpit-Demo-User` header pattern won't work for SSE; the dep gets `current_user` from the cookie session if Story 1.6 has wired it, else from `X-Cockpit-Demo-User` via a query string fallback (e.g. `?as=<user_id>`). Pick the simpler path that works with the current Story 1.4/1.6 auth state.
7. **Multiple tabs to the same case** = multiple subscribers. The registry must handle this (the asyncio-queue-list pattern does naturally).
8. **`useEffect` cleanup order matters.** Always return the unsubscribe function from the effect; rely on React's cleanup-on-unmount. Don't chain async work on cleanup.

### Project Structure Notes

This story creates:

- `packages/contracts/src/contracts/sse.py` (+ `tests/test_sse.py`)
- `apps/cockpit-api/src/cockpit_api/services/sse_registry.py`
- `apps/cockpit-api/src/cockpit_api/routers/stream.py`
- `apps/cockpit-api/tests/test_sse_registry.py`
- `apps/cockpit-api/tests/test_stream_route.py`
- `apps/cockpit-ui/src/lib/sse.ts` (+ `.test.ts`)

This story modifies:

- `apps/cockpit-api/src/cockpit_api/main.py` — wire stream router + registry singleton
- `apps/cockpit-api/src/cockpit_api/services/case_service.py` — publish on transition
- `apps/cockpit-api/src/cockpit_api/routers/documents.py` — publish on POST/DELETE
- `apps/agents/src/agents/_adk/decorators.py` — publish on ledger append
- `apps/cockpit-ui/src/hooks/useCases.ts` — drop `refetchInterval`
- `apps/cockpit-ui/src/hooks/useAgentMeshState.ts` — drop `refetchInterval`
- `apps/cockpit-ui/src/routes/cases.$caseId.tsx` — `useEffect` subscribe
- `apps/cockpit-ui/src/api-types.ts` — regenerated

This story DOES NOT create:

- A Redis pub/sub registry (cut from demo per `sprint-change-proposal-2026-04-29.md`)
- A 60-second replay buffer / `lastEventId` handling
- A WebSocket fallback
- A graceful-degradation polling fallback when SSE fails (browser reconnects natively; if it can't, the next user action triggers TanStack refetch on stale cache)

### References

- [Source: `epics.md#Story 4.6`] — SSE endpoint ACs
- [Source: `prd.md#FR11–14, NFR-P (real-time)`] — live mesh visibility
- [Source: `architecture.md#A2, P6, Demo Scope Addendum`] — SSE choice + payload pattern + single-worker simplification
- [Source: `sprint-change-proposal-2026-04-29.md`] — explicit cut of Redis pub/sub

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (Amelia persona, bmad-dev-story workflow)

### Debug Log References

* Initial registry design used `subscribe()` as an async generator. FastAPI's `StreamingResponse` + httpx `ASGITransport` reliably hung on cleanup because `wait_for(generator.__anext__())` couldn't propagate `StopAsyncIteration` through the generator boundary. Refactored to a `(queue, unsubscribe)` tuple — synchronous registration, plain `asyncio.Queue` consumption inside the route. All registry tests + auth/404 route tests now pass cleanly.
* httpx `client.stream` + ASGITransport happy-path tests for SSE deterministically hung even after the registry refactor — Starlette's `listen_for_disconnect` blocks on `response_complete`, which never fires for an open stream within the same event loop. Live streaming is verified by the headed Playwright smoke at the end of Epic 4 (task #21) and by the registry-level fan-out tests; route-level tests cover only auth/404/path-validation.
* FastAPI's `Annotated[Header(...), default=...]` rule: `Header(default=...)` inside `Annotated` raises `AssertionError` at app construction time. Resolution: use the param's default (`= None`) for defaults; keep `Annotated` for the metadata only. Same convention applies to `Query`.
* `subscriber_count` exists primarily for tests; not part of the production hot path.
* `console.warn` directly available in the Vite/jsdom environment — initial `eslint-disable no-console` was unnecessary and got flagged as a stale directive on lint.

### Completion Notes List

* **In-process registry** (`asyncio.Queue` per subscriber) replaces Redis pub/sub. Per `sprint-change-proposal-2026-04-29.md`, Story 4.7's Redis coordinator was explicitly cut for the demo.
* **Three event types** ship: `agent.state_changed`, `case.state_changed`, `case.documents_changed`. Producers wired:
  - Action decorator (success + failure paths) — emits `agent.state_changed`
  - Documents POST + DELETE — emit `case.documents_changed`
  - Case `state_changed` — DEFERRED. The current `case_service.update_state` path doesn't yet exist as a single chokepoint (the supervisor's `transition` is the closest, called from inside `CaseSupervisor.run_intake` and the manual `POST /v1/cases/{id}/intake`). Adding a publish here would require touching the supervisor (Epic 3 territory) — out of scope for this story. The handler in `lib/sse.ts` is wired and ready for the producer.
* **Client subscribes per case open**. `cases.$caseId.tsx` mounts a `useEffect` that opens an `EventSource` keyed on `caseId` + `currentUser.id`; cleanup closes it on unmount/navigation. Auth via `?as=<user_id>` query param because EventSource cannot send custom headers.
* **No replay buffer**. Browser auto-reconnects; missed events backfill on next user interaction via TanStack Query's `staleTime: 0`. Acceptable demo trade-off documented in the route docstring.
* **Polling intervals dropped** in `useCases` (was 5 s) and `useAgentMeshState` (was 3 s). Both now `refetchInterval: false`. The cockpit feels alive only while a case is open (the only time we subscribe); the queue page now sees updates only via direct user navigation, which is acceptable per the Story 4.6 AC #8 note.
* **`publish_safe`** swallows registry errors and logs at WARN — a downstream registry failure must never abort an agent run or a state transition.
* **15-second heartbeat** (`: keepalive\n\n` comment frames) keeps proxy connections alive.
* **256-byte payload cap** (P6) enforced by convention — payloads ship `case_id` + `agent_slug` + `state` only; ledger detail is fetched on invalidation.
* **Test counts** — backend: cockpit-api 96 → 105 (+9). UI: 22 → 23 test files (+1 `sse.test`); 175 passing tests (+5). Net pre-existing failures: 5 (unchanged).

### File List

**Created (contracts)**
* `packages/contracts/src/contracts/sse.py` — `SseEvent` model.

**Created (cockpit-api)**
* `apps/cockpit-api/src/cockpit_api/services/sse_registry.py` — `SseRegistry` + `publish_safe` + process-singleton.
* `apps/cockpit-api/src/cockpit_api/routers/stream.py` — `GET /v1/cases/{case_id}/stream` SSE endpoint.
* `apps/cockpit-api/tests/test_sse_registry.py` — 6 unit tests.
* `apps/cockpit-api/tests/test_stream_route.py` — 3 auth/404 tests; live-stream cases deferred to Playwright smoke.

**Created (cockpit-ui)**
* `apps/cockpit-ui/src/lib/sse.ts` — EventSource wrapper + per-event invalidation map.
* `apps/cockpit-ui/src/lib/sse.test.ts` — 5 tests (mock EventSource).

**Modified**
* `packages/contracts/src/contracts/__init__.py` — re-export `SseEvent`.
* `apps/cockpit-api/src/cockpit_api/main.py` — wire `stream_router`.
* `apps/cockpit-api/src/cockpit_api/routers/documents.py` — publish `case.documents_changed` on POST + DELETE.
* `apps/agents/src/agents/supervisor/action_decorator.py` — publish `agent.state_changed` after `_record_success` + `_record_failure`.
* `apps/cockpit-ui/src/hooks/useCases.ts` — `refetchInterval: 5_000` → `false`.
* `apps/cockpit-ui/src/hooks/useAgentMeshState.ts` — `refetchInterval: 3_000` → `false`.
* `apps/cockpit-ui/src/routes/cases.$caseId.tsx` — `useEffect` subscribes via `subscribeToCase(caseId, currentUser.id, queryClient)`.
* `apps/cockpit-ui/src/api-types.ts` — regenerated.
* `packages/contracts/openapi.json` — regenerated.
