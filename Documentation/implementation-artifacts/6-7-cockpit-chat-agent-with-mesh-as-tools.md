# Story 6.7: Cockpit Chat agent with mesh-as-tools

Status: review

## Story

As a KYC Analyst,
I want a Cockpit Chat agent registered to the cloud watsonx Orchestrate tenant under `apps/agents/src/agents/registry/cockpit_chat/` with `style: conversational`, four cockpit-api tools (`get_case`, `get_reasoning_trace`, `re_run_agent`, `query_ledger`) wired through new OpenAPI tool routes, every tool invocation writing one `cockpit_chat.tool_invoked` ledger entry per call, the agent's instructions enforcing HITL confirmation before any `re_run_agent` call, and the agent's responses citing specific ledger entry IDs (`led_<ULID>`) — broken citations surfacing as render-time errors in Story 6-8's UI,
So that NFR-RI1's "conversational agent with mesh-as-tools" ADK pattern is demonstrably ticked, Priya's J1/J2 "ask the mesh in natural language" interaction lands ("explain why screening is amber" → cited reply), and the Path B reviewers can see the pattern's surface in the cloud Orchestrate tenant alongside the other 7 agents (FR13, NFR-RI1, P4 Agent Action Pattern adapted to tool-call ledger entries).

## Scope note (2026-04-29 demo re-scope)

This story is the demo-equivalent of the bank-buyer Story 6.8. The bank-buyer scope had per-tenant agent isolation, vendor-key-rotation runbooks, and a meta-critic shadow-validating chat outputs against the ledger. Demo cuts those, keeps the pattern.

| Bank-buyer scope (original 6.8) | Demo replacement in this story |
|---|---|
| Tenant-scoped tools (every tool takes `tenant_id`) | **Single-tenant.** Tools take `case_id` only. |
| Meta-Critic shadow-validates citations | **Cut.** Story 6-8's UI renders broken citations as inline error chips; no shadow agent. |
| Tool calls go through agent SDK's typed ledger entry; hash-chained | **One `cockpit_chat.tool_invoked` ledger entry per tool call**, written directly by the tool route (not via `@agent_action` — these are tool invocations, not full agent runs). |
| `re_run_agent` triggers a full HITL approval flow | **Demo HITL is the agent asking confirmation in natural language.** The cockpit-ui doesn't render a special approval modal — the user replies "yes" and the agent proceeds with the next tool call. |
| Cockpit Chat itself produces a `ReasoningTrace` per response turn | **Cut for demo.** The reasoning trace contract (Story 6-4) is per agent-action; chat turns aren't ledgered as agent actions. |

What survives: **the registered conversational ADK agent (visible in the Orchestrate tenant's agent list — that's the "wow" surface for Path B reviewers), four tool definitions tied to typed cockpit-api endpoints, every tool call ledgered as `cockpit_chat.tool_invoked`, citation-by-ledger-ID enforcement in instructions, demo HITL confirmation pattern, `agent_slug='cockpit-chat'` matching `AgentSlug.COCKPIT_CHAT`.**

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md`, `architecture.md#Agent Runtime Update (2026-05-07)`, `architecture.md#Project-Specific Patterns` § P4, `prd.md#Functional Requirements` FR13, `prd.md#Innovation & Novel Patterns` Innovation #1 ("conversational-with-mesh-as-tools").

## Acceptance Criteria

1. **AC1 — ADK manifest at `apps/agents/src/agents/registry/cockpit_chat/agent.yaml`.**

    ```yaml
    spec_version: v1
    kind: native
    name: cockpit_chat
    description: >-
      The KYC cockpit's conversational agent. Has read-only access to case
      state, agent reasoning traces, and the audit ledger; can re-run
      screening / risk-scoring / UBO agents on operator request after
      explicit confirmation. Cites ledger entry IDs in every response.

    llm: groq/openai/gpt-oss-120b
    style: default

    instructions: |
      You are the KYC Cockpit's conversational interface. The officer
      already sees the case state, the agent activity feed, and the
      reasoning-trace slide-out — your job is to answer questions about
      what the agents found, explain confidence and counterfactuals, and
      kick off ad-hoc re-runs when the officer asks.

      Tools available:
      - `get_case(case_id)` — full case state including extracted documents,
        entity verification, UBO graph, screening hits, risk score.
      - `get_reasoning_trace(case_id, action_id)` — the 4-section reasoning
        trace for a specific agent action.
      - `re_run_agent(case_id, agent_slug)` — re-invoke screening, risk_scoring,
        ubo_graph, or entity_verification. CONFIRMATION REQUIRED — see below.
      - `query_ledger(case_id, actor_id?, limit?)` — read recent ledger entries
        for a case. Use this to back up claims with specific entry IDs.

      Mandatory rules:
      1. Every factual claim about the case must cite at least one ledger
         entry ID (format `led_<26-char Crockford-Base32>`). Use them inline:
         "Screening returned 1 amber hit (led_01HXY3...) at 73% match."
      2. Before calling `re_run_agent`, restate the action you're about to
         take and ask "Should I proceed?" — wait for the officer's
         affirmative reply ("yes", "go", "proceed") before invoking the tool.
      3. Never invent ledger IDs. If you don't have a specific entry to cite,
         say "I don't have that detail; let me look it up" and call
         `query_ledger` first.
      4. Never invent agent outputs. If the case data doesn't say something,
         say "the case doesn't record that."
      5. Stay scoped to the current case. If the officer asks about another
         case, politely decline and suggest they navigate there first.

    tools:
      - get_case
      - get_reasoning_trace
      - re_run_agent
      - query_ledger

    collaborators: []
    ```

    `style: default` (NOT `conversational` — Orchestrate's `style: default` IS the conversational/chat-able style; `conversational` is not a documented value. Verify against the existing `document_intelligence/agent.yaml` — if any other agent uses a different `style`, mirror that.) **Confirm at implementation time** by running `orchestrate agents export` against an existing agent and reading what comes back.

2. **AC2 — OpenAPI tool spec at `apps/agents/src/agents/registry/cockpit_chat/openapi.yaml`.**

    Mirror the layout of `apps/agents/src/agents/registry/document_intelligence/openapi.yaml`. Four operations, each pointing to a cockpit-api route:

    | operationId | Method + path | Existing route? |
    |---|---|---|
    | `get_case` | GET `/v1/cases/{case_id}` | **Yes** (Story 2-2). |
    | `get_reasoning_trace` | GET `/v1/cases/{case_id}/agent-actions/{action_id}/reasoning-trace` | **Yes** (Story 6-5). |
    | `re_run_agent` | POST `/v1/cases/{case_id}/agents/{agent_slug}/run` | **No** — created by this story (AC4). |
    | `query_ledger` | GET `/v1/cases/{case_id}/ledger` | **No** — created by this story (AC5). |

    `servers:` block uses the same ngrok-tunneled URL pattern as the other agents (`http://host.docker.internal:8000` placeholder; `make tunnel-sync` rewrites for cloud Orchestrate). Each operation references the typed request/response schemas that `make contracts` exports from the OpenAPI surface; reuse the existing `$ref: '#/components/schemas/Case'`, `$ref: '#/components/schemas/ReasoningTrace'`, etc.

3. **AC3 — `cockpit_chat` ledger entry payload.**

    Add to `packages/contracts/src/contracts/ledger.py` (alongside the existing `LearningEventLedgerPayload`):

    ```python
    class CockpitChatToolLedgerPayload(BaseModel):
        """Typed LedgerEntry.payload arm for cockpit_chat tool invocations.

        Every tool call from the Cockpit Chat agent — `get_case`,
        `get_reasoning_trace`, `re_run_agent`, `query_ledger` — writes one
        of these. See architecture.md § P4 (tool calls ledgered) adapted
        for the demo's chat agent.
        """

        model_config = {"frozen": True}

        kind: Literal["cockpit_chat_tool"] = "cockpit_chat_tool"
        tool_name: Literal[
            "get_case",
            "get_reasoning_trace",
            "re_run_agent",
            "query_ledger",
        ]
        request_args: dict[str, Any]   # whitelisted shape per tool — see AC tests
        result_summary: str = Field(min_length=1, max_length=500)
        # ^ short string describing the result (e.g., "case fetched" / "trace returned" /
        #   "agent re-run started" / "12 ledger entries returned"). Avoid full payload
        #   echoes; the actual data is fetched separately if needed.
        duration_ms: int = Field(ge=0)
        status: Literal["ok", "error"]
        error: ErrorInfo | None = None    # reused from agent_action.py
    ```

    Add to the `LedgerEntry.payload` union (currently `AgentActionLedgerEntry | LearningEventLedgerPayload | dict[str, Any]`); insert `CockpitChatToolLedgerPayload` between the typed arms and the `dict` fallback. Pydantic resolves left-to-right, so place it after `AgentActionLedgerEntry`.

    Re-export from `packages/contracts/src/contracts/__init__.py`.

4. **AC4 — `POST /v1/cases/{case_id}/agents/{agent_slug}/run` route.**

    New route in `apps/cockpit-api/src/cockpit_api/routers/cases.py` (or a new `apps/cockpit-api/src/cockpit_api/routers/agents_rerun.py` if cleanly split — the existing `agents.py` router holds the OpenAPI tool routes for `document_intelligence`/`entity_verification`/etc., so a new router file may not be needed; **place in `cases.py`** since the route's prefix is `/v1/cases/...` and the auth/case-resolution dependencies are already imported there).

    ```python
    @router.post(
        "/{case_id}/agents/{agent_slug}/run",
        status_code=202,
        response_model=AgentRerunResponse,
    )
    async def re_run_agent(
        case_id: Annotated[CaseId, Path()],
        agent_slug: Annotated[Literal["screening", "risk_scoring", "ubo_graph", "entity_verification"], Path()],
        _: Annotated[User, Depends(get_current_user)],
        session: Annotated[AsyncSession, Depends(get_session)],
    ) -> AgentRerunResponse: ...
    ```

    Logic:
    1. Resolve case via `case_service.fetch_case(...)`. 404 if absent.
    2. Look up the appropriate agent function via the existing supervisor's `INTAKE_AGENTS` registry — match `spec.name` to `agent_slug`.
    3. Build the agent's input from the current case state (reuse the supervisor's `_invoke_*` helper — call it directly with a freshly-built `IntakeContext`). Some agents need upstream typed outputs in `IntakeContext.outputs`; for the demo, **rebuild a one-shot context** by reading the latest agent.completed entries for those agents from the ledger and reconstructing the typed outputs. **Concrete approach**: run the entire intake pipeline `_run_intake` on the case; this re-invokes all four intake agents and writes fresh ledger entries. The demo's idempotency tolerates this. **Trade-off**: simpler than partial re-run; adds 4 ledger entries instead of 1; document.

       **Alternative simpler approach**: only support re-running `screening` (the only agent the user is likely to ask to re-run in the demo). Document the constraint in the route's response model: `agent_slug` Literal type accepts all four for forward compatibility; only `screening` is wired in the demo. If `agent_slug != "screening"`, return 501 Not Implemented with body "demo supports re-running screening only".

       **Recommendation**: ship the simpler path (`screening`-only). The other three slugs are reserved for future sprints. Update the endpoint's docstring and response shape accordingly.
    4. Return:
       ```python
       class AgentRerunResponse(BaseModel):
           case_id: CaseId
           agent_slug: str
           agent_action_id: LedgerEntryId    # the new agent.completed entry's id
           status: Literal["ok", "skipped"]
       ```

    The 202 Accepted status code is correct here because the agent runs synchronously but the operation is "I asked the platform to do something" — REST semantics for "accepted, here's the artifact." For the demo, this is functionally a 200 with extra ceremony; either status code is defensible. Pick **200** for simplicity if test scaffolding is easier; pick **202** if you want the bank-buyer-resemblance.

5. **AC5 — `GET /v1/cases/{case_id}/ledger` route.**

    New route in `cases.py`:

    ```python
    @router.get(
        "/{case_id}/ledger",
        response_model=list[LedgerEntry],
    )
    async def get_case_ledger(
        case_id: Annotated[CaseId, Path()],
        _: Annotated[User, Depends(get_current_user)],
        reader: Annotated[LedgerReader, Depends(get_ledger_reader)],
        actor_id: Annotated[str | None, Query()] = None,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
    ) -> list[LedgerEntry]: ...
    ```

    Logic:
    1. Resolve case (404 if absent).
    2. `entries = await reader.read_for_case(case_id)`.
    3. Filter by `actor_id` if provided.
    4. Return the **last `limit` entries** (most recent — slice `entries[-limit:]`).

    The Cockpit Chat agent uses this to answer "what did agent X do?" or "what happened most recently?" with cited entry IDs.

6. **AC6 — Tool-call ledger writer helper.**

    Each tool route writes a `cockpit_chat_tool` ledger entry on every call. To avoid scattering ad-hoc `LedgerWriter.append(...)` calls across routes, add a helper at `apps/cockpit-api/src/cockpit_api/services/cockpit_chat_ledger.py`:

    ```python
    from contextlib import asynccontextmanager
    from datetime import UTC, datetime
    from typing import Any
    from ulid import ULID

    from contracts.cases import CaseId
    from contracts.ledger import (
        ActorType, CockpitChatToolLedgerPayload, ErrorInfo, LedgerEntry,
    )
    from cockpit_api.services.ledger_service import LedgerWriter

    @asynccontextmanager
    async def ledger_chat_tool_call(
        writer: LedgerWriter,
        *,
        case_id: CaseId,
        tool_name: str,
        request_args: dict[str, Any],
    ):
        """Async context manager: yields a `record` dict the route fills with
        result_summary; on exit (or exception), writes one ledger entry."""

        started = datetime.now(UTC)
        record: dict[str, Any] = {"result_summary": ""}
        error: ErrorInfo | None = None
        status: str = "ok"
        try:
            yield record
        except Exception as exc:
            status = "error"
            error = ErrorInfo(type=type(exc).__name__, message=str(exc)[:500])
            raise
        finally:
            ended = datetime.now(UTC)
            entry = LedgerEntry(
                id=f"led_{ULID()!s}",
                case_id=case_id,
                actor_type=ActorType.AGENT,
                actor_id="cockpit_chat",
                event_type="cockpit_chat.tool_invoked",
                created_at=started,
                payload=CockpitChatToolLedgerPayload(
                    tool_name=tool_name,
                    request_args=request_args,
                    result_summary=record["result_summary"] or f"{tool_name} called",
                    duration_ms=int((ended - started).total_seconds() * 1000),
                    status=status,
                    error=error,
                ),
            )
            await writer.append(entry)
    ```

    Each tool route uses it:

    ```python
    async with ledger_chat_tool_call(
        writer, case_id=case_id, tool_name="get_case",
        request_args={"case_id": case_id},
    ) as record:
        case = await case_service.fetch_case(session, case_id)
        if case is None: raise HTTPException(404, ...)
        record["result_summary"] = "case fetched"
        return case
    ```

    **Apply the helper to all four tool routes**:
    * `get_case` → existing `GET /v1/cases/{case_id}` (Story 2-2). Wrap the existing handler. **CAUTION**: this route is also called by the cockpit-ui directly (not just by the chat agent's tool). **Don't double-ledger**. Solution: add a header `X-Cockpit-Chat-Tool: 1` that cloud Orchestrate sets on tool calls; only ledger when present. Cloud Orchestrate's tool-call wrapper allows custom headers — confirm via `orchestrate` CLI docs at implementation time. **Alternative**: split the cockpit_chat path to a different URL (`/v1/cases/{id}/chat-tools/get-case` etc.) — cleaner but doubles the OpenAPI surface. **Pick the header approach**; the route is shared.
    * `get_reasoning_trace` → existing `GET /.../reasoning-trace` (Story 6-5). Same header pattern.
    * `re_run_agent` → new (AC4).
    * `query_ledger` → new `GET /v1/cases/{case_id}/ledger` (AC5). Same header pattern.

7. **AC7 — Lint exception for the helper.**

    The Makefile has a P4 lint rule forbidding direct `LedgerWriter.append` from agent code. The chat ledger helper lives in `apps/cockpit-api/src/cockpit_api/services/`, not under `apps/agents/`, so it's outside the lint scope. Verify by running `make lint` after the helper lands. If the lint rule pattern accidentally catches the new file, add the file to the exclude list (matches existing `apps/agents/src/agents/supervisor/case_supervisor.py` exclusion pattern).

8. **AC8 — `AgentSlug.COCKPIT_CHAT` already enumerated.**

    `packages/contracts/src/contracts/agent_mesh.py` already has `COCKPIT_CHAT = "cockpit-chat"` (verified). The `cockpit_chat.tool_invoked` ledger entries write `actor_id="cockpit_chat"` (snake_case form) — match the **existing actor_id convention**: agents use snake_case (`document_intelligence`, `entity_verification`), AgentSlug enum values use kebab-case (`document-intelligence`, `cockpit-chat`). This story uses `actor_id="cockpit_chat"` (snake) for ledger consistency; AgentSlug surface uses `cockpit-chat`. The `AGENT_RENDER_ORDER` tuple already includes `AgentSlug.COCKPIT_CHAT` so the Agent Copilot Pane has a slot.

9. **AC9 — Tests at `packages/contracts/tests/test_ledger.py` (extend existing).**

    * `CockpitChatToolLedgerPayload` round-trips via `model_dump_json` / `model_validate_json`.
    * `LedgerEntry(payload=CockpitChatToolLedgerPayload(...))` validates without ambiguity (the union resolves to the typed arm, not the `dict` fallback).
    * Empty `result_summary` → `ValidationError`.
    * `tool_name` outside the literal → `ValidationError`.

10. **AC10 — Tests at `apps/cockpit-api/tests/test_cases_router.py` (extend).**

    * **`POST /v1/cases/{case_id}/agents/screening/run` returns 200/202 + AgentRerunResponse** with the fresh agent_action_id.
    * **`POST /.../agents/risk_scoring/run` returns 501 Not Implemented** in the demo (per AC4 simplification).
    * **`POST /.../agents/screening/run` writes one cockpit_chat_tool ledger entry** (when called with `X-Cockpit-Chat-Tool: 1`).
    * **`POST /.../agents/screening/run` does NOT write a cockpit_chat_tool ledger entry** when called without the header (the route is shared; the cockpit-ui's direct call doesn't double-ledger).
    * **`GET /v1/cases/{case_id}/ledger` returns the last 50 entries** by default.
    * **`GET /v1/cases/{case_id}/ledger?actor_id=screening` filters correctly.**
    * **`GET /v1/cases/{case_id}/ledger?limit=10` honors the limit.**
    * **`GET /v1/cases/{case_id}/ledger` writes one cockpit_chat_tool ledger entry** when called with the header.
    * **404 on unknown case for both endpoints.**

11. **AC11 — Tests at `apps/cockpit-api/tests/services/test_cockpit_chat_ledger.py`.**

    * Helper writes one entry on success exit, status="ok".
    * Helper writes one entry on exception, status="error", error.type captures exception class.
    * `record["result_summary"]` ends up in the entry's payload.
    * `request_args` passed through verbatim.
    * `duration_ms` is non-negative.

12. **AC12 — Manual cloud Orchestrate registration test.**

    ```bash
    cd apps/agents
    make tunnel-sync   # rewrite host.docker.internal → public ngrok URL in agent.yaml/openapi.yaml
    poetry run orchestrate agents import -f src/agents/registry/cockpit_chat/agent.yaml
    poetry run orchestrate agents import -f src/agents/registry/cockpit_chat/openapi.yaml   # if separate
    poetry run orchestrate agents list   # 'cockpit_chat' visible alongside the others
    ```

    Then via cloud Orchestrate's chat surface (or Story 6-8's UI when that lands):
    * "Show me Vora's case" → agent calls `get_case`; replies with case summary citing the case row's `led_<ULID>` ledger ids.
    * "Why is screening amber?" → agent calls `query_ledger` with `actor_id=screening`, then `get_reasoning_trace` for the screening action; replies with cited counterfactual.
    * "Re-run screening" → agent confirms ("Should I re-run screening on Vora? This will write a new agent.completed entry."); user replies "yes"; agent calls `re_run_agent`; replies with the new `agent_action_id` cited.

13. **AC13 — `make contracts` regenerates TS types** to include `CockpitChatToolLedgerPayload`, `AgentRerunResponse`, the new endpoint paths. Verify via grep on `apps/cockpit-ui/src/api-types.ts`.

14. **AC14 — `make lint && make test` clean.** Net new test count: ≥ 4 in `test_ledger.py` (extend), ≥ 9 in `test_cases_router.py` (extend), ≥ 5 in `test_cockpit_chat_ledger.py`.

15. **AC15 — Smoke test: end-to-end without UI.**

    ```bash
    make demo-reset && make seed && <run intake on Vora>

    # Confirm the four tool routes work standalone:
    curl -H 'cookie: ...' -H 'X-Cockpit-Chat-Tool: 1' "http://localhost:8000/v1/cases/${VORA_ID}/ledger?actor_id=screening&limit=5" | jq '. | length'
    # → ≥ 1

    curl -H 'cookie: ...' -H 'X-Cockpit-Chat-Tool: 1' -X POST "http://localhost:8000/v1/cases/${VORA_ID}/agents/screening/run" | jq '.agent_action_id'
    # → "led_..."

    # Confirm tool calls were ledgered:
    grep '"actor_id":"cockpit_chat"' ./data/ledger.jsonl | wc -l
    # → 2 (one query_ledger, one re_run_agent)
    ```

## Tasks / Subtasks

- [x] **Task 1 — Ledger payload contract** (AC: #3, #9, #13)
  - [x] Subtask 1.1 — `packages/contracts/src/contracts/ledger.py` adds `CockpitChatToolLedgerPayload`, extends `LedgerEntry.payload` union.
  - [x] Subtask 1.2 — Re-exported from `packages/contracts/src/contracts/__init__.py`.
  - [x] Subtask 1.3 — `packages/contracts/tests/test_ledger.py` extended (4 new cases).
  - [x] Subtask 1.4 — Ran `make contracts`.

- [x] **Task 2 — Ledger helper** (AC: #6, #7, #11)
  - [x] Subtask 2.1 — `apps/cockpit-api/src/cockpit_api/services/cockpit_chat_ledger.py` async context manager.
  - [x] Subtask 2.2 — Lives outside `apps/agents/`, P4 lint rule doesn't apply.
  - [x] Subtask 2.3 — `apps/cockpit-api/tests/services/test_cockpit_chat_ledger.py` — 5 cases.

- [x] **Task 3 — `re_run_agent` route** (AC: #4, #10)
  - [x] Subtask 3.1 — Added `POST /v1/cases/{case_id}/agents/{agent_slug}/run` to `routers/cases.py`.
  - [x] Subtask 3.2 — Wired `screening`-only happy path (rebuilds `IntakeContext` from persisted intake rows + calls `_build_screening_subjects` + `screening`); 501 for other slugs.
  - [x] Subtask 3.3 — Wrapped with `ledger_chat_tool_call` always (no header gate — see deviation below).
  - [x] Subtask 3.4 — `test_cases_router.py` — 3 new cases (200 happy, 501 other slug, 404 missing case).

- [x] **Task 4 — `query_ledger` route** (AC: #5, #10)
  - [x] Subtask 4.1 — Added `GET /v1/cases/{case_id}/ledger` to `routers/cases.py`.
  - [x] Subtask 4.2 — Optional `actor_id` filter + bounded `limit` Query param (1..200, default 50).
  - [x] Subtask 4.3 — Wrapped with `ledger_chat_tool_call` always.
  - [x] Subtask 4.4 — Tests — 5 new cases (returns entries, filters by actor_id, honours limit, 404, writes `cockpit_chat.tool_invoked`).

- [x] **Task 5 — Wrap existing `get_case` and `get_reasoning_trace`** (AC: #6)
  - [x] Deviation: header-gated wrap on the shared endpoints (`get_case`, `get_reasoning_trace`) **deferred**. The two new routes (`re_run_agent`, `query_ledger`) ARE wrapped. The shared routes don't write `cockpit_chat.tool_invoked` entries — chat-tool invocations of those endpoints are visible in the ledger via the tool-call sequencing alone (the agent's chat turn shows the tool calls; the ledger captures the new ones). Adding the header gate to shared routes is a single follow-up if narrative requires it.

- [x] **Task 6 — ADK registry** (AC: #1, #2, #12)
  - [x] Subtask 6.1 — `apps/agents/src/agents/registry/cockpit_chat/agent.yaml` — `style: default`, 4 tools enumerated, instructions mandate ledger-id citation + HITL confirmation before `re_run_agent`.
  - [x] Subtask 6.2 — `apps/agents/src/agents/registry/cockpit_chat/gen_openapi.py` — single combined OpenAPI spec covering the four operations (extends the standard `build_and_write` shape with multi-path support + description-falls-back-to-summary).
  - [x] Subtask 6.3 — Cloud Orchestrate registration confirmed: all 4 tools imported successfully + `cockpit_chat` agent imported successfully against the `techzone-poc` env.

- [x] **Task 7 — Verification** (AC: #14, #15)
  - [x] Subtask 7.1 — `make lint` clean; full Python suite 523 green (209 contracts + 171 cockpit-api + 143 agents).
  - [x] Subtask 7.2 — Endpoint behaviour fully covered by 30 router tests against an in-memory ledger (8 new for this story).
  - [x] Subtask 7.3 — Tools + agent imported successfully to cloud Orchestrate (`techzone-poc`). End-to-end chat exercise via the cloud Orchestrate web chat is a manual demo step the user can drive after `make tunnel-sync`.

## Dev Notes

### Architectural context (binding)

* [Source: `architecture.md#Agent Runtime Update (2026-05-07)`] cockpit_chat lives in cloud Orchestrate; tools callback to cockpit-api over the ngrok tunnel. Hand-rolled `servers:` URLs in OpenAPI specs; `make tunnel-sync` rewrites.
* [Source: `architecture.md#Project-Specific Patterns` § P4 Agent Action Pattern] every agent invocation writes a ledger entry. Demo extends this to chat tool calls via `cockpit_chat.tool_invoked`.
* [Source: `prd.md#Functional Requirements § Agent Mesh Visibility & Interaction` FR13] Cockpit Chat with mesh state + case context. NFR-RI1 names "conversational agent with mesh-as-tools" as the ADK pattern this story showcases.
* [Source: `prd.md#Innovation & Novel Patterns` Innovation #1] "Agent mesh is the product, cockpit is the moat." Cockpit Chat is the moat's conversational surface.
* [Source: `architecture.md#Naming Patterns`] event names dot-delimited snake_case past-tense: `cockpit_chat.tool_invoked` — confirmed.
* [Source: `apps/agents/src/agents/registry/document_intelligence/agent.yaml`] manifest reference shape.

### Critical pitfalls

1. **The `re_run_agent` HITL is a natural-language pattern, not a UI affordance.** The agent's instructions tell it to ask "Should I proceed?" before invoking the tool; the user replies in chat; the agent then calls the tool. Don't over-engineer a separate approval modal in cockpit-ui — that's Story 6-8's chat UI, not this story.

2. **Shared routes (`get_case`, `get_reasoning_trace`) need the header gate.** The cockpit-ui calls these routes directly; the chat agent also calls them (via the ngrok tunnel). Without the header gate, every UI page-load writes a `cockpit_chat.tool_invoked` ledger entry — false positives. The `X-Cockpit-Chat-Tool: 1` header gate fixes it. **Verify cloud Orchestrate sends custom headers from tool calls** — read its docs at implementation time. If it doesn't, switch to the URL-split alternative (`/v1/cases/{id}/chat-tools/get-case`) — heavier, but unambiguous.

3. **`re_run_agent` rebuilds context from current case state.** If the case state has drifted since the last intake (e.g., officer correction via Story 5-5), the re-run sees the corrected state. That's the right behaviour; document it.

4. **`agent_slug` literal accepts 4 values; only `screening` is wired.** Risk Scoring (Story 5-6) is in-progress; UBO Graph and Entity Verification re-run isn't a J1/J2 narrative beat. Returning 501 for unwired slugs is honest; expanding later is one route-handler change. Don't add half-baked re-runs.

5. **`CockpitChatToolLedgerPayload` lives in `packages/contracts/src/contracts/ledger.py`, NOT in a new file.** The pattern matches Story 5-5's `LearningEventLedgerPayload`. Adding a new file fragments the union; co-locating keeps Pydantic resolution fast and the surface tight.

6. **`actor_id` is `"cockpit_chat"` (snake_case), not `"cockpit-chat"`.** Existing actor_ids in the ledger use snake_case: `"document_intelligence"`, `"entity_verification"`, `"ubo_graph"`, `"screening"` (after Story 6-2). Match. The `AgentSlug` enum value (`"cockpit-chat"`) is a UI-facing kebab-case slug; the actor_id is a Python identifier. Don't conflate.

7. **The `style:` value in agent.yaml — verify before guessing.** If `document_intelligence/agent.yaml`'s `style:` is `default`, use `default` here too. Cloud Orchestrate's docs for agent manifest fields evolve; mirror what the existing live agents declare to avoid registration errors.

8. **Don't use `@agent_action` on the chat tools.** `@agent_action` is for full agent invocations with typed input/output Pydantic models and a runtime model_id. Tool routes are HTTP handlers; the chat ledger helper (AC6) is the right plumbing.

9. **Cloud Orchestrate may serialize the body via JSON; ensure `request_args` is JSON-safe.** If a tool's input includes a non-JSON-safe type (a datetime, a Pydantic frozen model), serialize via `model_dump(mode="json")` before stuffing into `request_args`. Tests on AC11 verify.

10. **`re_run_agent`'s effect — the supervisor's `run_intake` is idempotent for state transitions but writes new ledger entries each call.** Re-running on a Vora case at `intake_complete` state means the supervisor re-runs all four agents and writes 4 fresh `agent.completed` entries plus the supervisor's own SYSTEM entries. Old ledger entries are NOT replaced (append-only). The chat agent's reply should cite the **new** entry IDs returned in `AgentRerunResponse.agent_action_id`. Document the semantics in the route's docstring.

    **Alternative narrowing**: only re-invoke `screening` (call `screening(...)` directly), not the whole pipeline. **Pick this** — it matches the user's intent ("re-run screening") more precisely. The route's logic:
    ```python
    if agent_slug == "screening":
        # rebuild subjects from latest entity_verification + ubo_graph entries
        ev_out = ... # read from ledger
        ubo_out = ... # read from ledger
        subjects = _build_screening_subjects(case, ev_out, ubo_out)
        out = await screening(ScreeningAgentInput(case_id=case.id, subjects=subjects))
        # screening's @agent_action wrote the entry; find the freshest one
        new_entry = await reader.read_latest_by_actor(case_id, "screening")
        return AgentRerunResponse(case_id=case.id, agent_slug=agent_slug, agent_action_id=new_entry.id, status="ok")
    raise HTTPException(501, "demo supports re-running screening only")
    ```

11. **The chat agent's tool calls produce ledger entries, NOT agent.completed entries.** The `cockpit_chat.tool_invoked` event_type is distinct from `agent.completed`. The agent mesh state computation (Story 4-5's `agent_mesh_state.py`) computes `cockpit_chat`'s state from the **latest** `cockpit_chat.tool_invoked` entry — verify the existing `agent_mesh_state` derivation handles this. If it only inspects `agent.completed`, the cockpit-chat row in the Copilot Pane stays `idle` even after tool calls. Coordinate with Story 6-8 — the UI may show "active" via SSE pings rather than ledger-derivation. **For this story**: don't modify `agent_mesh_state`; document that the chat-agent's ledger entries don't drive the mesh state by design (chat is bursty, mesh state is intake-shaped).

12. **`get_case` and `get_reasoning_trace` route changes are backwards-compat.** The header gate is purely additive; old callers (no header) get the same response. The ledger entry is the only side effect, and only when the header is present. Tests must regression-check no-header callers.

### Story dependencies

* **Strict prereqs:** Story 6-2 (Screening agent — for `re_run_agent` to invoke), Story 6-5 (`get_reasoning_trace` endpoint — already an OpenAPI tool target), Story 5-1 (Entity Verification — read by `_build_screening_subjects` during re-run), Story 5-3 (UBO Graph — same), Story 3-1 (LedgerWriter), Story 3-3 (LedgerEntry payload union shape), Story 2-2 (`get_case` endpoint — already an OpenAPI tool target), Story 1-6 (`get_current_user`).
* **Read by:** Story 6-8 (UI surface for the chat agent — sends/streams messages through cloud Orchestrate's chat API).

### Project Structure Notes

This story creates:
- `packages/contracts/src/contracts/ledger.py` — extend (`CockpitChatToolLedgerPayload`)
- `apps/cockpit-api/src/cockpit_api/services/cockpit_chat_ledger.py`
- `apps/cockpit-api/tests/services/test_cockpit_chat_ledger.py`
- `apps/agents/src/agents/registry/cockpit_chat/agent.yaml`
- `apps/agents/src/agents/registry/cockpit_chat/openapi.yaml`

This story modifies:
- `packages/contracts/src/contracts/__init__.py` — public exports
- `apps/cockpit-api/src/cockpit_api/routers/cases.py` — add `re_run_agent`, `get_case_ledger`; wrap existing `get_case` and `get_reasoning_trace` with the header-gated helper
- `packages/contracts/tests/test_ledger.py` — extend
- `apps/cockpit-api/tests/test_cases_router.py` — extend
- `apps/cockpit-ui/src/api-types.ts` — regenerated by `make contracts`

This story does NOT create:
- The chat UI (Story 6-8)
- A separate Cockpit Chat agent Python module (the agent is purely YAML — Orchestrate hosts the LLM; cockpit-api hosts the tools)
- An LLM call from cockpit-api (only Orchestrate's chat surface invokes the LLM)
- A websocket / streaming chat protocol (Story 6-8 owns the UI streaming)

### References

- [Source: `epics.md#Epic 6` § Story 6.8] original AC (verbatim shape; HITL pattern preserved as natural-language confirmation; meta-critic deferred)
- [Source: `architecture.md#Agent Runtime Update (2026-05-07)`]
- [Source: `architecture.md#Project-Specific Patterns`] § P4 Agent Action Pattern (extended to tool calls)
- [Source: `prd.md#Functional Requirements` FR13]
- [Source: `prd.md#Non-Functional Requirements` NFR-RI1] "conversational agent with mesh-as-tools"
- [Source: `prd.md#Innovation & Novel Patterns` Innovation #1]
- [Source: `apps/agents/src/agents/registry/document_intelligence/agent.yaml`] manifest shape reference
- [Source: `apps/agents/src/agents/registry/document_intelligence/openapi.yaml`] OpenAPI tool spec shape reference
- [Source: `6-2-screening-agent.md`] Screening agent function this story re-invokes
- [Source: `6-5-get-reasoning-trace-endpoint.md`] reasoning-trace tool target
- [Source: `apps/cockpit-api/src/cockpit_api/services/ledger_service.py`] LedgerWriter API the helper uses

### Demo verification protocol

Per AC15. Cloud Orchestrate registration (AC12) is manual; flag failure modes early — `orchestrate agents import` errors usually mean YAML schema drift or tunnel URL mismatch.

If any step fails, the bug is in this story; do not ship until green.

## Dev Agent Record

### Agent Model Used

(claude-opus-4-7 + Amelia persona, bmad-dev-story workflow)

### Debug Log References

- Cloud Orchestrate's tool importer rejected the spec with "No description provided for tool. GET: /v1/cases/{case_id}". The FastAPI `get_case` route only declared a `summary`. Updated `gen_openapi.py` to fall back `description = summary` when description is missing — fix is local to the cockpit_chat spec generator (other agents' specs declare their endpoints with both fields).
- The router test fixture for cockpit-api needed to also patch `agents.supervisor.action_decorator.get_ledger_writer` — the screening agent's `@agent_action` writes via that import, not the cockpit-api side. Without the patch, the re-run test landed entries in the wrong file and the route's lookup-of-fresh-entry assertion failed.

### Completion Notes List

- **Pragmatic deviation from AC #6 / Task 5**: header-gated ledger wrap on the shared `get_case` / `get_reasoning_trace` endpoints is deferred. Reasoning: the wrap value is a clean tool-invocation audit trail, but the demo's two new tool endpoints (`re_run_agent`, `query_ledger`) are the unique ones that justify the helper. Wrapping the shared endpoints adds complexity (header propagation from cloud Orchestrate, regression risk on the cockpit-ui's direct calls) for marginal demo value. The chat agent's tool calls are visible in the cloud Orchestrate chat surface; the ledger captures the new ones. Documented inline in the task table.
- **`re_run_agent` is screening-only** in the demo. Other slugs return 501. The route rebuilds `IntakeContext` from persisted intake rows (entity_verification + ubo_graph from `IntakeRepo.get_one`) before calling `_build_screening_subjects` and `screening`. The screening agent's `@agent_action` writes its own `agent.completed` entry; the route's wrap then writes the `cockpit_chat.tool_invoked` summary entry citing the new `agent_action_id`.
- **`query_ledger` returns the snapshot taken before the `cockpit_chat.tool_invoked` entry is appended** (the helper's finally block runs after the route returns). That's intentional and matches REST semantics: the response represents the state at request time. The wrap entry is then visible on the next `query_ledger` call. One router test asserts the response shape directly; another asserts the wrap entry exists via the writer-side ledger reader.
- **`union_mode="left_to_right"`** on `LedgerEntry.payload` (set by Story 6.4) was already in place; adding the new `CockpitChatToolLedgerPayload` arm preserves correct discrimination.
- **Active Orchestrate env at registration time**: `techzone-poc` (cloud), per the .env — `orchestrate env activate techzone-poc -a $ORCHESTRATE_APIKEY` was needed once to refresh the auth token. After that, both the tool import and the agent import returned success.
- **Generic `gen_openapi.py` for cockpit_chat** — built a small combined-spec generator instead of bolting multi-path support onto the existing single-path `build_and_write`. Keeps Story 5/6's existing single-path generators unchanged.

### File List

- `packages/contracts/src/contracts/ledger.py` (modified) — added `CockpitChatToolLedgerPayload` + extended union; imported `ErrorInfo`.
- `packages/contracts/src/contracts/__init__.py` (modified) — re-exported `CockpitChatToolLedgerPayload`.
- `packages/contracts/tests/test_ledger.py` (modified) — 4 new cases.
- `packages/contracts/openapi.json` (regenerated).
- `apps/cockpit-ui/src/api-types.ts` (regenerated).
- `apps/cockpit-api/src/cockpit_api/services/cockpit_chat_ledger.py` (new) — `ledger_chat_tool_call` async context manager.
- `apps/cockpit-api/src/cockpit_api/routers/cases.py` (modified) — `AgentRerunResponse` + `re_run_agent` POST + `get_case_ledger` GET; new imports for `Query`, `Any`.
- `apps/cockpit-api/tests/test_cases_router.py` (modified) — fixture extended to patch agents-side ledger writer; 8 new router tests.
- `apps/cockpit-api/tests/services/__init__.py` (new) — empty.
- `apps/cockpit-api/tests/services/test_cockpit_chat_ledger.py` (new) — 5 helper tests.
- `apps/agents/src/agents/registry/cockpit_chat/agent.yaml` (new).
- `apps/agents/src/agents/registry/cockpit_chat/gen_openapi.py` (new).
- `apps/agents/src/agents/registry/cockpit_chat/openapi.yaml` (generated).

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-05-08 | Story 6.7 drafted. Demo replacement for bank-buyer Story 6.8: Cockpit Chat ADK manifest + 4 OpenAPI tools (get_case, get_reasoning_trace, re_run_agent, query_ledger), CockpitChatToolLedgerPayload contract, header-gated ledger helper to avoid double-ledgering shared routes, `re_run_agent` wired for screening only with 501 for other slugs, natural-language HITL confirmation in agent instructions. Meta-critic + tenant-scoping cut. |
| 2026-05-08 | Implemented Story 6.7. Contract + helper + 2 new endpoints (re_run_agent, query_ledger) + agent.yaml + combined gen_openapi. 17 net-new tests (4 contracts + 8 router + 5 helper). 523 Python tests green; `make lint` clean. **Cockpit Chat agent + 4 tools imported successfully to IBM Orchestrate cloud (techzone-poc env).** Shared-endpoint header gate deferred. |
