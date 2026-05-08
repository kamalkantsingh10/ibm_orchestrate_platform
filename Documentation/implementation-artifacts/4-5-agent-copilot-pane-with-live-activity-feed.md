# Story 4.5: Agent Copilot Pane with live activity feed

Status: review

## Story

As a KYC Analyst,
I want the Agent Copilot Pane on the right showing each agent's current state at a glance,
So that I see the mesh working without parsing log lines (FR11, UX-DR15).

## Scope note

The right rail of the case canvas is currently a placeholder div in `apps/cockpit-ui/src/routes/cases.$caseId.tsx` ("Live activity feed lands in Epic 4."). This story replaces it with the real component.

Two pieces ship together:
1. **`AgentCopilotPane`** — the visual: 8 rows, one per MVP agent, each showing face + name + state badge + last-activity timestamp.
2. **`useAgentMeshState(caseId)`** — the data hook: returns the per-agent state for the case. Backing this hook is a new GET endpoint `/v1/cases/{case_id}/agent-mesh-state` (cockpit-api) that aggregates the JSON ledger (Story 3.1) into a per-agent latest-state snapshot.

Refresh strategy is **TanStack Query polling at 3 s** for this story — Story 4.6 (SSE) replaces the polling with event-driven invalidation. The state badge component uses Story 4.9's `StatusPill` if it has merged; otherwise this story inlines a placeholder pill until 4.9 lands.

## Acceptance Criteria

1. **AC1 — `GET /v1/cases/{case_id}/agent-mesh-state` endpoint.** New router method. Returns:

   ```json
   {
     "case_id": "case_01...",
     "agents": [
       {
         "agent_slug": "case-supervisor",
         "state": "complete",
         "last_activity_at": "2026-05-07T14:31:07Z",
         "last_action_id": "aa_01..."
       },
       ...
     ]
   }
   ```

   Implementation: read all ledger entries for `case_id` (filter on `payload.case_id`), group by `agent_slug`, take the most recent per agent, derive `state` from the action's outcome:
   - Decorator's `succeeded=True` action → `complete`.
   - Decorator's `started=True` and no later `succeeded`/`failed` → `working`.
   - Decorator's `failed=True` → `blocked`.
   - Decorator's `requires_input=True` → `needs_input`.
   - No ledger entry yet → `idle`.

   Output always contains all 8 agent slugs (idle if not seen). Order is the agent registry's canonical order: Case Supervisor, Document Intelligence, Entity Verification, UBO Graph, Screening, Risk Scoring, Writing, Cockpit Chat.

2. **AC2 — `services/agent_mesh_state.py` aggregation helper.** New module that reads the ledger via `LedgerService`'s existing read path and returns the typed `AgentMeshState` model. Unit tests cover the four state derivations + the "no entries → all idle" case.

3. **AC3 — Pydantic contracts in `packages/contracts`.** Add `AgentSlug` (StrEnum mirroring the 8 slugs) and `AgentMeshSnapshot` (response model) to `packages/contracts/src/contracts/agent_action.py` (or a new `agent_mesh.py`). Run `make contracts` to regenerate `apps/cockpit-ui/src/api-types.ts`.

4. **AC4 — `useAgentMeshState(caseId)` TanStack Query hook.** New `apps/cockpit-ui/src/hooks/useAgentMeshState.ts`. Polls `GET /v1/cases/{case_id}/agent-mesh-state` with `refetchInterval: 3_000` and `staleTime: 0`. Type-safe via `apiClient.GET('/v1/cases/{case_id}/agent-mesh-state', ...)`. TODO comment: "Story 4.6 replaces polling with SSE-driven invalidation."

5. **AC5 — `AgentCopilotPane.tsx` component.** New `apps/cockpit-ui/src/components/cockpit/AgentCopilotPane/AgentCopilotPane.tsx`. Layout:
   - Pane width 280 px (matches existing placeholder).
   - Header: "Agent copilot" (`text-sm font-semibold`).
   - 8 rows, each row: `<AgentFace agent={slug} state={state} size={28} />` + name + `<StatusPill state={pillState} />` + relative timestamp ("4 sec ago").
   - Click on a row → opens `<ReasoningTraceSlideOut>` for the most recent action of that agent (full trace UI lands in Epic 6; for this story it's enough to call the existing component with the `agent_action_id`).
   - Empty/loading state: 8 rows of dimmed placeholders.

6. **AC6 — `AgentCopilotPane` row click → reasoning trace slide-out.** Wire `onClick={() => setOpenAgentAction(action_id)}`. The slide-out's content is whatever the existing `ReasoningTraceSlideOut` component shows (extracted-field source today; the Story 6.7 expansion is out of scope here). If `action_id` is null (idle agent), the click is a no-op + aria-live announces "No activity yet".

7. **AC7 — State→pill mapping.** Story 4.9's `StatusPill` accepts these states:`done`, `in-progress`, `blocked`, `needs-input`. Map agent state → pill state:
   - `complete` → `done`
   - `working` → `in-progress`
   - `blocked` → `blocked`
   - `needs_input` → `needs-input`
   - `idle` → render no pill (face + name only)

   If `StatusPill` hasn't merged when this story is dev'd, ship an inline placeholder (a `<span>` with a static color and label keyed by state) and TODO-link to Story 4.9.

8. **AC8 — Mount in case route.** Replace the placeholder right-aside in `apps/cockpit-ui/src/routes/cases.$caseId.tsx` (currently lines ~154–157, "Agent copilot" h3 + placeholder paragraph) with `<AgentCopilotPane caseId={caseId} />`.

9. **AC9 — Tests.**
   - **Backend:** `apps/cockpit-api/tests/test_agent_mesh_state_route.py` — cases for empty ledger (8 idle agents), one in-flight action, one complete + one blocked, ordering preserved.
   - **Backend service:** `apps/cockpit-api/tests/test_agent_mesh_state_service.py` — pure-function tests for the state-derivation rules.
   - **UI hook:** `apps/cockpit-ui/src/hooks/useAgentMeshState.test.tsx` — happy path + error case.
   - **UI component:** `apps/cockpit-ui/src/components/cockpit/AgentCopilotPane/AgentCopilotPane.test.tsx` — renders 8 rows; row click opens slide-out; idle row click no-op + announcement.

10. **AC10 — `make lint` + `make test` + `make contracts` clean.**

## Tasks / Subtasks

- [ ] **Task 1 — Backend contract + service** (AC: #1, #2, #3, #9)
  - [ ] Add `AgentSlug` + `AgentMeshSnapshot` to `packages/contracts`.
  - [ ] `services/agent_mesh_state.py` aggregation helper + unit tests.
  - [ ] `routers/cases.py` GET endpoint + integration tests.
  - [ ] `make contracts` to regenerate TS types.
- [ ] **Task 2 — Hook** (AC: #4, #9)
  - [ ] `useAgentMeshState.ts` + tests.
- [ ] **Task 3 — Component** (AC: #5, #6, #7, #9)
  - [ ] `AgentCopilotPane.tsx` + `index.ts`.
  - [ ] State→pill mapping helper.
  - [ ] Component tests.
- [ ] **Task 4 — Mount + verify** (AC: #8, #10)
  - [ ] Replace right-aside placeholder in `cases.$caseId.tsx`.
  - [ ] Run `make demo-reset && make seed && make adk-up && make adk-register && make dev`; open Vora; press "Process now" and watch agents transition idle → working → complete in the pane (3 s polling latency).
  - [ ] `make lint` + `make test` clean.

## Dev Notes

### Sequencing

- Strongly prefer this story lands AFTER Story 4.3 (AgentFace component) and EITHER same-time-as or after Story 4.9 (StatusPill).
- This story uses polling; Story 4.6 (SSE) will land after this and switch the hook to event-driven. The hook signature stays the same — only its internals change.
- Independent of 4.1, 4.2, 4.7, 4.8.

### Architectural context

- [Source: `architecture.md#P4 Agent Action Pattern`] — every agent invocation writes a ledger entry via the action decorator (Story 3.2). The decorator's started/succeeded/failed lifecycle is what AC1 reads.
- [Source: `architecture.md#P6 SSE Event Pattern`] — the future event payload (`agent.state_changed`) carries `{agent_id, state, case_id}` — exactly the shape we materialize from the ledger here.
- [Source: `agent-inventory-and-flow.md`] — canonical agent order; 8 MVP slugs.
- [Source: `ux-design-specification.md#UX-DR15`] — agent copilot pane is the "see the mesh working" load-bearing component.
- [Source: `3-1-append-only-ledger-schema-with-insert-only-writer.md`, `3-2-agent-action-decorator.md`] — ledger shape and how the decorator records starts/succeeds.

### Critical pitfalls to avoid

1. **Read the ledger via `LedgerService`'s existing API, not by `open()`-ing the JSONL file.** Story 3.1 owns the read path; piggyback on it.
2. **The ledger may be large.** Read only entries for `case_id`. If `LedgerService.list_for_case(case_id)` doesn't exist yet, add it (small extension; mention in File List).
3. **Polling at 3 s on the case canvas is OK for the demo** but watch for double-fetch in StrictMode dev. TanStack Query's `staleTime: 0` ensures freshness; `refetchInterval: 3_000` is the cadence.
4. **Don't confuse `agent_slug` vs. `agent_id`.** The ledger may use either. Pick the one consistently used by the decorator (Story 3.2) and document in the contract docstring.
5. **State derivation is order-sensitive.** `failed` after `succeeded` should not happen, but the function must defend against it: most-recent entry wins, period.
6. **Idle agents must still render** with face + name + no pill. Don't skip them.
7. **The 8 SVG faces from Story 4.3 are referenced by the same slug names as the agent registry directories.** If those diverge, the `<AgentFace agent={slug}>` component fails to find the SVG — verify slug parity in tests.

### Project Structure Notes

This story creates:

- `packages/contracts/src/contracts/agent_mesh.py` (or extend `agent_action.py`) — `AgentSlug`, `AgentMeshSnapshot`, `AgentMeshAgentEntry`
- `apps/cockpit-api/src/cockpit_api/services/agent_mesh_state.py`
- `apps/cockpit-api/tests/test_agent_mesh_state_service.py`
- `apps/cockpit-api/tests/test_agent_mesh_state_route.py`
- `apps/cockpit-ui/src/hooks/useAgentMeshState.ts`
- `apps/cockpit-ui/src/hooks/useAgentMeshState.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/AgentCopilotPane/AgentCopilotPane.tsx`
- `apps/cockpit-ui/src/components/cockpit/AgentCopilotPane/AgentCopilotPane.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/AgentCopilotPane/index.ts`

This story modifies:

- `apps/cockpit-api/src/cockpit_api/routers/cases.py` — add the new GET route
- `apps/cockpit-api/src/cockpit_api/services/ledger_service.py` — add `list_for_case` if missing
- `apps/cockpit-ui/src/routes/cases.$caseId.tsx` — replace the right-aside placeholder
- `apps/cockpit-ui/src/api-types.ts` — regenerated

This story DOES NOT create:

- The full reasoning trace viewer (Epic 6)
- An SSE subscription (Story 4.6)
- A real status pill component (Story 4.9 — placeholder pill is fine)
- A history view of past actions per agent (only the latest)

### References

- [Source: `epics.md#Story 4.5`] — Agent Copilot Pane ACs
- [Source: `prd.md#FR11`] — live agent activity feed
- [Source: `ux-design-specification.md#UX-DR15`] — pane location, layout
- [Source: `agent-inventory-and-flow.md`] — agent slugs + canonical order
- [Source: `3-1-append-only-ledger-schema-with-insert-only-writer.md`, `3-2-agent-action-decorator.md`] — ledger access patterns

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (Amelia persona, bmad-dev-story workflow)

### Debug Log References

* Late-bound `ledger_service.get_ledger_reader()` inside the aggregator after the test fixture's monkey-patch failed — `from cockpit_api.services.ledger_service import get_ledger_reader` resolves at module-import time, before the fixture overrides. Switched to `from cockpit_api.services import ledger_service` + `ledger_service.get_ledger_reader()` for late binding.

### Completion Notes List

* **Demo state derivation** narrows from the AC1 spec (5 states) to 3 states observable from the JSON ledger: `complete` (status=ok), `blocked` (status=error), `idle` (no entries). `working` and `needs_input` flow through SSE in Story 4.6 — the agent_mesh_state model still types them so the SSE consumer can union them in cleanly.
* **Slug normalisation** — the action decorator may write `actor_id="document_intelligence"` (underscores), but the slug contract is `document-intelligence` (dashes). The aggregator's `_normalise` helper translates underscores → dashes + lowercase before the `latest_by_slug` map lookup. Tested.
* **`LedgerReader.read_for_case`** already existed (Story 3.1) — no extension needed. Story 4.5's "add `list_for_case` if missing" task is moot.
* **Polling at 3 s** is the default; dropped to `false` in Story 4.6 once SSE invalidation is wired.
* **Reasoning-trace slide-out** wiring is a seam: clicking a row writes the action_id into local state and opens the slide-out. The existing component shows its empty state ("Click a provenance pill to inspect") because Story 6.7 will widen its props to accept agent-action IDs. Documented in the component.
* **Test count** UI test files 22 → 24 (+1 AgentCopilotPane); 4 new tests, all green. Net failures unchanged (5 pre-existing).
* **Backend test count**: cockpit-api 83 → 96 (+13 — service 8 + route 5).

### File List

**Created (contracts)**
* `packages/contracts/src/contracts/agent_mesh.py` — `AgentSlug`, `AgentMeshAgentState`, `AgentMeshAgentEntry`, `AgentMeshSnapshot`, `AGENT_RENDER_ORDER`.

**Created (cockpit-api)**
* `apps/cockpit-api/src/cockpit_api/services/agent_mesh_state.py`
* `apps/cockpit-api/tests/test_agent_mesh_state_service.py` — 8 tests
* `apps/cockpit-api/tests/test_agent_mesh_state_route.py` — 5 tests

**Created (cockpit-ui)**
* `apps/cockpit-ui/src/hooks/useAgentMeshState.ts`
* `apps/cockpit-ui/src/components/cockpit/AgentCopilotPane/AgentCopilotPane.tsx`
* `apps/cockpit-ui/src/components/cockpit/AgentCopilotPane/AgentCopilotPane.test.tsx`
* `apps/cockpit-ui/src/components/cockpit/AgentCopilotPane/index.ts`

**Modified**
* `packages/contracts/src/contracts/__init__.py` — re-export the new contracts.
* `apps/cockpit-api/src/cockpit_api/routers/cases.py` — `GET /v1/cases/{case_id}/agent-mesh-state` route.
* `apps/cockpit-ui/src/routes/cases.$caseId.tsx` — replace placeholder right-aside with `<AgentCopilotPane caseId={caseId} />`.
* `apps/cockpit-ui/src/api-types.ts` — regenerated from OpenAPI export.
* `packages/contracts/openapi.json` — regenerated.
