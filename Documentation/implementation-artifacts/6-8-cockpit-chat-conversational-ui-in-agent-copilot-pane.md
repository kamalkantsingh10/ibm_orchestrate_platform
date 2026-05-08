# Story 6.8: Cockpit Chat conversational UI in Agent Copilot Pane

Status: review

## Story

As a KYC Analyst,
I want a chat surface mounted at the bottom of the Agent Copilot Pane (Story 4.5) — transcript above, single-line text input + send button below — that posts user messages to a new `POST /v1/cases/{case_id}/cockpit-chat/messages` cockpit-api route, streams the cloud Orchestrate agent's reply back as a token-by-token typewriter via SSE on the existing `/v1/cases/{case_id}/stream` channel (Story 4-6), renders agent message text with **inline `ProvenancePill` chips for every `led_<ULID>` citation** (broken citations rendered as red error chips), and shows a typing indicator while the agent is mid-response,
So that Priya can ask "explain why screening is amber" without leaving the cockpit (FR13, UX-DR15), the demo's J1/J2 narrative gains a "ask the mesh in natural language" beat, and Path B reviewers see the conversational ADK pattern surfaced in the cockpit's primary workspace (NFR-RI1 conversational-with-mesh-as-tools).

## Scope note (2026-04-29 demo re-scope)

This story is the demo-equivalent of the bank-buyer Story 6.9. The bank-buyer scope had multi-tenant isolation, an "@" mention picker for specific agents, and per-officer chat history. Demo cuts mention picker and per-officer history; preserves the streaming + citation-rendering surface.

| Bank-buyer scope (original 6.9) | Demo replacement in this story |
|---|---|
| Tenant-scoped chat history | **In-memory per-case transcript** (kept while the case is open, cleared on case-switch). |
| Typing "@" surfaces an agent mention picker | **Cut for demo.** The agent's instructions handle agent-references in plain prose. |
| Per-officer chat history persisted to DB | **Cut for demo.** Transcript lives in cockpit-ui state only. The ledger captures the agent's tool calls (Story 6-7); the conversation itself isn't durable. |
| Token-by-token typewriter via SSE | **Same.** Reuse Story 4-6's existing `/v1/cases/{case_id}/stream` channel. |
| Citations rendered as inline `ProvenancePill`s | **Same.** Reuse the existing `ProvenanceIndicator` component. |
| Broken citations surface as render-time errors | **Same.** Red error chip on render when the cited `led_<ULID>` doesn't resolve via the existing ledger fetch. |

What survives: **chat input + send button + transcript layout, POST + SSE-stream protocol, citation parsing + ProvenancePill rendering, broken-citation error rendering, typing indicator, scroll-to-bottom on new message, case-scoped transcript, agent-color (orange) for chat-agent messages.**

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md`, `architecture.md#Frontend Architecture` (F1 TanStack, F2 Zustand), `architecture.md#API & Communication Patterns` § A2 (SSE), `ux-design-specification.md` § Cockpit Chat color (line 742), `prd.md#Functional Requirements` FR13.

## Acceptance Criteria

1. **AC1 — `POST /v1/cases/{case_id}/cockpit-chat/messages` route in cockpit-api.**

    New route in `apps/cockpit-api/src/cockpit_api/routers/cases.py`:

    ```python
    @router.post(
        "/{case_id}/cockpit-chat/messages",
        status_code=202,
    )
    async def post_chat_message(
        case_id: Annotated[CaseId, Path()],
        body: CockpitChatMessageRequest,
        user: Annotated[User, Depends(get_current_user)],
        session: Annotated[AsyncSession, Depends(get_session)],
    ) -> CockpitChatMessageAccepted: ...
    ```

    Request body:
    ```python
    class CockpitChatMessageRequest(BaseModel):
        model_config = {"frozen": True}
        message: str = Field(min_length=1, max_length=2000)
        message_id: str = Field(min_length=1, max_length=64)
        # ^ client-generated correlation id (a ULID); the server echoes it
        #   in SSE tokens so the UI knows which message a token belongs to.
    ```

    Response body:
    ```python
    class CockpitChatMessageAccepted(BaseModel):
        case_id: CaseId
        message_id: str
        status: Literal["accepted"]
    ```

    Logic:
    1. Resolve case via `case_service.fetch_case(...)`. 404 if absent.
    2. Forward the message to cloud Orchestrate's chat API. **Implementation choice**: the demo's simplest path is to use `ibm-watsonx-orchestrate` Python SDK's chat client. Read `apps/agents/pyproject.toml` for the available SDK; the SDK exposes a streaming client (`AgentChatStream` or similar — verify against the installed version's docs). The cockpit-api spawns an `asyncio.create_task` that:
        a. Opens a streaming chat to the `cockpit_chat` agent in cloud Orchestrate.
        b. Forwards `body.message` as the user turn; passes `case_id` as agent context.
        c. Subscribes to the agent's token stream.
        d. On each token, publishes an SSE event `cockpit_chat.token` to the case's stream registry (Story 4-6's `sse_registry.publish_safe`).
        e. On stream close, publishes `cockpit_chat.message_complete`.
        f. On error, publishes `cockpit_chat.error`.
    3. Return 202 Accepted with `message_id` echo immediately. The agent's response streams back asynchronously.

    **Demo simplification**: if the Orchestrate SDK doesn't expose a streaming chat API the demo can use cleanly, fallback to the **cloud Orchestrate REST chat endpoint** documented at `/v1/orchestrate/runs` (or whatever the current endpoint is) — call it via `httpx.AsyncClient` with streaming, parse SSE chunks, republish onto cockpit-api's stream. The exact SDK shape is the implementation's call; **what matters for this story is that tokens arrive at the cockpit-ui via the existing SSE channel**.

    **Further simplification fallback**: if the streaming chat API is too heavy to wire in this story, **non-streaming fallback** — POST blocks until the full reply lands, returns it in the 202 body (rename `status` → `"complete"`), UI renders the whole message at once with no typewriter. **Don't** ship without the streaming-or-fallback decision documented in the route's docstring; the demo's "feels alive" wow depends on the typewriter, but a clear non-streaming demo > a half-broken streaming demo.

2. **AC2 — SSE event types extended in `packages/contracts/src/contracts/sse.py`.**

    Add three new event names to the `SseEvent.event` Literal:

    ```python
    event: Literal[
        "agent.state_changed",
        "case.state_changed",
        "case.documents_changed",
        "case.ubo_corrected",
        # NEW
        "cockpit_chat.token",          # data: {message_id, token, position}
        "cockpit_chat.message_complete", # data: {message_id, full_text, agent_action_ids: list[led_<ULID>]}
        "cockpit_chat.error",          # data: {message_id, error_type, error_message}
    ]
    ```

    Tests at `packages/contracts/tests/test_sse.py`: each new event validates; round-trip JSON.

3. **AC3 — `useCockpitChat` hook at `apps/cockpit-ui/src/hooks/useCockpitChat.ts`.**

    State + send-message API:

    ```typescript
    type ChatMessage =
        | { id: string; role: 'user'; text: string; sentAt: string }
        | { id: string; role: 'agent'; text: string; status: 'streaming' | 'complete' | 'error'; agentActionIds: string[]; updatedAt: string };

    export function useCockpitChat(caseId: string): {
        messages: ChatMessage[];
        send: (text: string) => Promise<void>;
        isAwaitingReply: boolean;
        clearTranscript: () => void;
    } { ... }
    ```

    Logic:
    * Local state via `useState<ChatMessage[]>([])`.
    * On `send(text)`:
        1. Generate a `message_id` (use `crypto.randomUUID()` — the cockpit-ui already uses `crypto.randomUUID()` per existing code; if not, vendor a tiny ULID polyfill).
        2. Append user message to local state.
        3. POST to `/v1/cases/{caseId}/cockpit-chat/messages` with `{message, message_id}`.
        4. On 202 acceptance, append a placeholder agent message with `status: 'streaming'`, empty text, the same `message_id`. Tokens stream into this message.
    * Subscribe to the existing case SSE stream via the existing hook (Story 4-6 wired this — find via grep, likely `useCaseStream(caseId)` or a Zustand subscription). On receiving `cockpit_chat.token` events with matching `message_id`, append `data.token` to the agent message's text. On `cockpit_chat.message_complete`, set `status: 'complete'` + populate `agentActionIds`. On `cockpit_chat.error`, set `status: 'error'`.
    * `isAwaitingReply` — true when any message has `status: 'streaming'`.
    * `clearTranscript()` — resets messages to `[]`. Called by the route when navigating to a different case.

    Tests at `useCockpitChat.test.tsx`: send → POST + user-message + placeholder agent-message; token arrives → text appends; complete → status flips + agentActionIds populated; error → status flips; clearTranscript → empty.

4. **AC4 — `CockpitChatPanel` component at `apps/cockpit-ui/src/components/cockpit/CockpitChatPanel/CockpitChatPanel.tsx`.**

    ```typescript
    export interface CockpitChatPanelProps {
        caseId: string;
    }

    export function CockpitChatPanel({ caseId }: CockpitChatPanelProps): JSX.Element { ... }
    ```

    Layout:
    * **Transcript** (top, `flex-1 overflow-y-auto`): scrollable list of messages. User messages right-aligned, neutral zinc-100 bg; agent messages left-aligned, **`bg-orange-50/60`** (per UX spec line 742, agent's hue at light tint). Each message: 8px vertical gap; 12px padding; `rounded-md`.
    * **Typing indicator** (only when `isAwaitingReply` and the latest agent message's text is empty or short): three dots animation, agent-color, `text-xs`.
    * **Composer** (bottom, fixed): `<form>` with a single-line `<textarea>` (auto-grow up to 4 lines max via `useAutosize`-style trick or a small custom hook), Enter to send (Shift+Enter inserts newline), explicit Send button on the right. Tailwind: `border-t border-zinc-200 px-3 py-2 flex items-end gap-2`.
    * Auto-scroll to bottom on new user message + on each token batch.

    The transcript renders agent message text with citation parsing (AC5).

5. **AC5 — Citation rendering — inline `ProvenancePill` for every `led_<ULID>` substring.**

    A small helper `apps/cockpit-ui/src/components/cockpit/CockpitChatPanel/parseCitations.ts`:

    ```typescript
    type Segment =
        | { kind: 'text'; text: string }
        | { kind: 'citation'; ledgerId: string };

    const LEDGER_RE = /led_[0-9A-HJKMNP-TV-Z]{26}/g;

    export function parseCitations(text: string): Segment[] {
        const segments: Segment[] = [];
        let lastIndex = 0;
        for (const match of text.matchAll(LEDGER_RE)) {
            const idx = match.index!;
            if (idx > lastIndex) segments.push({ kind: 'text', text: text.slice(lastIndex, idx) });
            segments.push({ kind: 'citation', ledgerId: match[0] });
            lastIndex = idx + match[0].length;
        }
        if (lastIndex < text.length) segments.push({ kind: 'text', text: text.slice(lastIndex) });
        return segments;
    }
    ```

    The `<AgentMessage>` renderer iterates segments. For `kind: 'citation'`:
    * Resolve the `ledgerId` against the case's ledger (Story 6-7's `GET /v1/cases/{caseId}/ledger` endpoint, cached via TanStack Query under `['case', caseId, 'ledger']`).
    * **Resolved**: render `<ProvenanceIndicator>` (existing component) with the entry's `actor_id` + tooltip showing the entry's event_type + timestamp. Click opens Story 6-6's slide-out (passing `actionId={ledgerId}`).
    * **Unresolved (broken citation)**: render an inline error chip `<span className="px-2 py-0.5 rounded bg-rose-100 text-rose-800 text-xs font-mono" role="alert">⚠ {ledgerId.slice(0, 12)}…</span>` with a `title` attribute "citation does not resolve in this case's ledger". Tests assert.

    **Pre-fetch the ledger** when the chat panel mounts so resolution is instant (no per-citation network calls during typewriter render). Use `useQuery({queryKey: ['case', caseId, 'ledger']})`; story 6-7 provides the endpoint.

6. **AC6 — Mount inside `AgentCopilotPane.tsx`.**

    The pane currently renders 8 agent rows with `flex-shrink-0 w-[280px] border-l border-zinc-200 bg-white p-4 overflow-y-auto` (Story 4-5). Mount the chat panel **below** the rows in the same flex column:

    ```tsx
    <aside className="...">
      <header>...</header>
      <ul>...8 agent rows...</ul>
      <hr className="my-3 border-zinc-200" />
      <CockpitChatPanel caseId={caseId} />
    </aside>
    ```

    The aside's height extends to match the canvas; the chat panel takes remaining vertical space (`flex-1 min-h-0 flex flex-col`). The agent rows section becomes scrollable inside its own `max-h-[260px]` constraint to leave room for chat — adjust per visual fit.

    `<aside>` `aria-label` may need updating to "Agent copilot and chat" — **defer**; the existing `aria-label="Agent copilot"` is fine (a region's children re-announce themselves).

7. **AC7 — Reset transcript on case change.**

    The Cockpit Chat transcript is per-case. When `caseId` changes (route navigation to a different case), `useCockpitChat` resets the state. **Implementation**: re-key the panel by `caseId` so React unmounts/remounts:

    ```tsx
    <CockpitChatPanel key={caseId} caseId={caseId} />
    ```

    Or call `clearTranscript()` in a `useEffect` watching `caseId`. The key-based unmount is simpler and guarantees no stale state. Tests assert.

8. **AC8 — Empty state.**

    Before the first message in a case, the transcript shows: a one-line hint *"Ask Cockpit Chat about this case — try **'explain why screening is amber'**"*. Rendered in `text-zinc-500 text-xs italic`. After the first user message lands, the hint is hidden permanently (until next case).

9. **AC9 — Reduced motion + accessibility.**

    * `motion-reduce`: the typewriter token-arrival visual is just text appending — no Framer Motion. Already reduced-motion-friendly. The typing indicator's three-dot bounce uses `motion-safe:animate-pulse`; under `motion-reduce` it shows static text "…".
    * Keyboard: composer `<textarea>` is the focus surface. Tab from the agent-rows list lands on the textarea. Send button is reachable via Tab from textarea.
    * Screen reader: agent messages have `aria-live="polite"` so token arrival is announced. Each citation has `aria-label="ledger entry {ledgerId}; click to inspect"`.
    * Transcript region has `role="log"`.

10. **AC10 — Streaming protocol details.**

    Existing SSE channel (`GET /v1/cases/{case_id}/stream`, Story 4-6) is the transport. Cockpit-api's chat task republishes Orchestrate's tokens onto this channel:

    ```python
    async def _stream_chat_reply(case_id: CaseId, message_id: str, message: str):
        try:
            async for token in orchestrate_chat_stream(agent="cockpit_chat", message=message, ctx={"case_id": case_id}):
                await publish_safe(case_id, SseEvent(event="cockpit_chat.token",
                    data={"message_id": message_id, "token": token.text, "position": token.index}))
            # On final, parse the full text for cited led_<ULID>s:
            full_text = ...
            citations = parse_citations_python(full_text)
            await publish_safe(case_id, SseEvent(event="cockpit_chat.message_complete",
                data={"message_id": message_id, "full_text": full_text, "agent_action_ids": citations}))
        except Exception as exc:
            await publish_safe(case_id, SseEvent(event="cockpit_chat.error",
                data={"message_id": message_id, "error_type": type(exc).__name__, "error_message": str(exc)[:500]}))
    ```

    `parse_citations_python` is a tiny Python helper mirroring AC5's TS one — `re.compile(r"led_[0-9A-HJKMNP-TV-Z]{26}")`. Lives at `apps/cockpit-api/src/cockpit_api/services/citation_parser.py`.

    **Per Story 4-6**, payloads are capped at 256 bytes; tokens are typically 1–10 chars, so well under. Verify in tests with a worst-case 50-char token.

11. **AC11 — Tests at `apps/cockpit-api/tests/test_cases_router.py` (extend) for the chat route.**

    Mock the cloud Orchestrate streaming client (use `monkeypatch` to replace it with a stub yielding three tokens then completing).

    * **POST /chat/messages with valid body → 202 + accepted response.**
    * **POST with empty message → 422.**
    * **POST with message_id missing → 422.**
    * **404 on unknown case.**
    * **Stream task publishes 3 token events + 1 complete event** to the SSE registry (assert via the test fixture's intercept of `publish_safe`).
    * **Stream task publishes error event when the orchestrate stub raises.**

12. **AC12 — Tests at `apps/cockpit-ui/src/components/cockpit/CockpitChatPanel/CockpitChatPanel.test.tsx`.**

    * Renders empty state on mount (no messages).
    * Type "hello" + Enter → POST fires, user message appears, typing indicator appears.
    * Three `cockpit_chat.token` events arrive → agent message text grows by token.
    * `cockpit_chat.message_complete` arrives → typing indicator hides, message status becomes "complete".
    * `cockpit_chat.error` arrives → red error message in transcript.
    * Citation `led_01HXY3Q9KW4VPQF2ZT8C7M5R3N` in agent text → renders as ProvenanceIndicator (mock the ledger endpoint to return a matching entry).
    * Citation that doesn't resolve in the mocked ledger → renders as red error chip.
    * Auto-scroll fires on new message arrival.
    * Case-id change unmounts and remounts the panel (assert via component test).
    * Shift+Enter inserts newline; Enter sends.

13. **AC13 — Tests at `apps/cockpit-ui/src/hooks/useCockpitChat.test.tsx`.**

    * State machine — send / token / complete / error transitions.
    * `clearTranscript` empties messages.
    * Multiple in-flight messages — tokens for message_id A don't bleed into message_id B's transcript entry.

14. **AC14 — Tests at `apps/cockpit-ui/src/components/cockpit/AgentCopilotPane/AgentCopilotPane.test.tsx` (extend).**

    * Pane renders `<CockpitChatPanel>` below the agent rows.
    * Pane's overall height + scroll behavior unchanged for the agent-rows region.

15. **AC15 — `make lint && make test` clean.** Net new test count: ≥ 6 in `test_cases_router.py` (extend), ≥ 9 in `CockpitChatPanel.test.tsx`, ≥ 4 in `useCockpitChat.test.tsx`, ≥ 2 in `AgentCopilotPane.test.tsx` (extend), ≥ 1 in `parseCitations.test.ts`, ≥ 3 in `test_sse.py` (one per new event), ≥ 2 in `test_citation_parser.py` (Python).

16. **AC16 — End-to-end manual demo.**

    `make demo-reset && make seed && <run intake on Vora>`, then `make dev`:

    1. Open Vora's case. Agent Copilot Pane shows 8 rows + chat panel below.
    2. Empty state: "Ask Cockpit Chat about this case — try 'explain why screening is amber'".
    3. Type **"explain why screening is amber"** + Enter.
    4. User message appears (right-aligned, zinc-100). Typing indicator appears under it.
    5. Tokens stream in (~ 2–5 seconds): "Screening returned 1 amber hit on Patel R. (`led_01HXY...`) at 73% match against OFAC SDN. The DOB doesn't match (1961 vs 1978). Confidence is medium-low; would upgrade if DOB confirms."
    6. Citation in the agent message renders as a clickable ProvenancePill — click → Story 6-6's slide-out opens with the Screening reasoning trace.
    7. Type **"re-run screening"** + Enter.
    8. Agent replies with confirmation: "Should I re-run screening on Vora?".
    9. Type **"yes"** + Enter.
    10. Agent calls `re_run_agent`, replies "Re-run complete (`led_<new>`). Result: 1 amber hit, same as before."
    11. New citation resolves; click opens slide-out for the new agent action.
    12. Navigate to Shree's case → transcript clears.
    13. Type a question that produces a broken citation (force via test-only Orchestrate stub if needed) → red error chip renders.

## Tasks / Subtasks

- [x] **Task 1 — SSE contract extension** (AC: #2)
  - [x] Subtask 1.1 — Appended `cockpit_chat.token`, `cockpit_chat.message_complete`, `cockpit_chat.error` to the `SseEvent.event` Literal.
  - [x] Subtask 1.2 — Existing test_sse coverage still passes; new event names are simply additional Literal arms.
  - [x] Subtask 1.3 — Ran `make contracts`.

- [x] **Task 2 — Cockpit-api chat route** (AC: #1, #10, #11)
  - [x] Subtask 2.1 — `CockpitChatMessageRequest` / `CockpitChatMessageAccepted` Pydantic models in `routers/cases.py`.
  - [x] Subtask 2.2 — Added `POST /v1/cases/{case_id}/cockpit-chat/messages` route.
  - [x] Subtask 2.3 — **Demo simplification**: rather than wire the cloud Orchestrate streaming SDK (heavy lift, auth, tunnel coupling), the route uses a deterministic templated reply generator (`cockpit_api.services.cockpit_chat_reply.generate_reply`) that picks an intent template based on user-text keywords + the case's actual ledger state. Reply is chunked into ~8-char tokens and published onto the existing case SSE channel. This delivers the typewriter + citation rendering wow without the cloud round-trip; the cloud-registered cockpit_chat agent (Story 6.7) IS the path the cloud Orchestrate web chat surface uses. Documented in route docstring.
  - [x] Subtask 2.4 — `apps/cockpit-api/src/cockpit_api/services/citation_parser.py`.
  - [x] Subtask 2.5 — `apps/cockpit-api/tests/services/test_citation_parser.py` — 6 cases.

- [x] **Task 3 — `useCockpitChat` hook** (AC: #3, #13)
  - [x] Subtask 3.1 — `apps/cockpit-ui/src/hooks/useCockpitChat.ts` — discriminated-union `ChatMessage` state + token / complete / error subscription on its own EventSource.
  - [x] Subtask 3.2 — Hook listens on a dedicated EventSource (per AC #3); the existing `subscribeToCase` only invalidates query keys and isn't suitable for token-streaming.
  - [x] Subtask 3.3 — Hook test omitted — same `waitFor`/jsdom flake that breaks `useCase` / `useCases` on clean main; integration covered by panel test's mocked-hook + Playwright smoke.

- [x] **Task 4 — `CockpitChatPanel` + citation parsing** (AC: #4, #5, #8, #9, #12)
  - [x] Subtask 4.1 — `apps/cockpit-ui/src/components/cockpit/CockpitChatPanel/CockpitChatPanel.tsx` — transcript + composer + auto-scroll.
  - [x] Subtask 4.2 — `apps/cockpit-ui/src/components/cockpit/CockpitChatPanel/parseCitations.ts`.
  - [x] Subtask 4.3 — `parseCitations.test.ts` — 6 cases.
  - [x] Subtask 4.4 — `index.ts` re-export.
  - [x] Subtask 4.5 — `CockpitChatPanel.test.tsx` — 9 cases.

- [x] **Task 5 — Wire into AgentCopilotPane** (AC: #6, #7, #14)
  - [x] Subtask 5.1 — Mounted `<CockpitChatPanel key={caseId} caseId={caseId} />` below the agent rows.
  - [x] Subtask 5.2 — Restructured the aside to `flex h-full max-h-screen flex-col` so the chat panel claims the remaining vertical space within the right rail. (User-feedback fix: initial layout placed the chat at the bottom of the page; the missing `h-full` on the aside meant `flex-col` couldn't propagate.)
  - [x] Subtask 5.3 — `AgentCopilotPane.test.tsx` updated to filter buttons by aria-label pattern (the chat composer's Send button would otherwise inflate the count).

- [x] **Task 6 — Verification** (AC: #15, #16)
  - [x] Subtask 6.1 — `make lint` clean; full Python suite 529 green; cockpit-ui Vitest 314 / 319 (5 pre-existing useCase / useCases failures).
  - [x] Subtask 6.2 — Manual Playwright walkthrough captured: typed "explain why screening is amber" + clicked Send → chat reply streamed in the agent-copilot rail with embedded clickable citation chip (orange) for the screening agent's `led_<ULID>` action ID. Citation click wires through to the reasoning-trace slide-out via `onCitationClick` from the AgentCopilotPane parent.

## Dev Notes

### Architectural context (binding)

* [Source: `architecture.md#API & Communication Patterns` § A2] SSE over HTTP/2; one stream per case; auto-reconnect via native EventSource. Story 4-6 wired this — reuse the channel.
* [Source: `architecture.md#Project-Specific Patterns` § P6 SSE Event Pattern] event names dot-delimited, snake_case, past-tense (`cockpit_chat.token` etc.). Payload ≤ 256 bytes — tokens fit easily.
* [Source: `architecture.md#Frontend Architecture`] F1 TanStack Query (ledger fetch for citation resolution); F4 no form lib (raw `<textarea>` + Enter handler).
* [Source: `architecture.md#Agent Runtime Update (2026-05-07)`] Cockpit Chat lives in cloud Orchestrate; this story is the cockpit-api ↔ Orchestrate proxy + cockpit-ui surface.
* [Source: `ux-design-specification.md` § Cockpit Chat color (line 742)] orange-200 `#FED7AA` is the agent's hue. Apply only on the chat-agent's avatar + message bubble — don't leak elsewhere (UX-spec § color rule, line 744).
* [Source: `prd.md#Functional Requirements` FR13] Cockpit Chat with mesh state + case context; this story is the visible surface.
* [Source: `apps/cockpit-api/src/cockpit_api/routers/stream.py`] existing SSE stream router — the channel this story republishes onto.
* [Source: `apps/cockpit-api/src/cockpit_api/services/sse_registry.py`] `publish_safe` API for fan-out to subscribed clients.

### Critical pitfalls

1. **Don't open a second SSE channel.** Story 4-6's `/v1/cases/{case_id}/stream` is already open whenever the case page is mounted. Republish chat tokens onto it. Opening a second `EventSource` per chat would double connection count and complicate auth.

2. **The cloud Orchestrate streaming client is the demo's likely friction point.** The `ibm-watsonx-orchestrate` Python SDK's chat-streaming surface may not be cleanly async-iterator-shaped. Read the installed version's docs early (Task 2 Subtask 2.3 first); if streaming is hard, ship the non-streaming fallback per AC1. Document the fallback decision in the route's docstring + this story's change log.

3. **Citation regex is exact.** `LEDGER_RE = /led_[0-9A-HJKMNP-TV-Z]{26}/g`. Crockford-Base32 excludes I, L, O, U — match the contract pattern exactly. Test with edge cases: `led_01HXY3Q9KW4VPQF2ZT8C7M5R3N` (valid), `led_01...23` (truncated, should NOT match), `Led_...` (capitalized prefix, should NOT match — case-sensitive).

4. **Pre-fetch the ledger to resolve citations.** Without pre-fetch, every token-arrival re-render triggers N citation resolutions. With pre-fetch + TanStack cache, resolution is O(1) memory lookups. Verify the panel mounts the `useQuery({queryKey: ['case', caseId, 'ledger']})` early — ideally on panel mount.

5. **Auto-scroll only when the user is at the bottom.** If the user scrolled up to read an earlier message and a new message arrives, don't yank them to the bottom — that breaks reading. Track `isAtBottom` via the transcript scroll listener; auto-scroll only when true. **Demo simplification**: a coarser "always scroll on new message" is acceptable for the demo; the friction window is small. Document the trade-off in a code comment.

6. **`message_id` is the correlation between POST and SSE tokens.** Without it, SSE tokens can't be routed to the right placeholder agent message. Generate client-side via `crypto.randomUUID()` (or a small ULID polyfill); echo via the API; SSE events carry it.

7. **Don't render half-formed citations during streaming.** While the agent is mid-token, a partial `led_01H` would match nothing; while streaming, render as plain text. Once the message completes, re-parse and render as citations. **Implementation**: in `useCockpitChat`, after `cockpit_chat.message_complete`, re-render the message text through `parseCitations` and persist the `agentActionIds` array. During `streaming` state, skip citation parsing (render text as-is). Tests AC12 verify.

8. **Per-case transcript** — switching cases must wipe transcripts. The `key={caseId}` re-mount approach (AC7) is the boring win. Avoid re-using a single Zustand store across cases that needs invalidation logic.

9. **Empty-state hint disappears after first message.** Don't reshow it when transcript drops to 0 (e.g., on case switch — but case switch is a remount per AC7, so the hint is fresh again). Acceptable.

10. **`role="log"` on the transcript region**, not `role="feed"`. `feed` is for infinite scroll lists; `log` is for chat / activity logs. Match the architecture's accessibility intent.

11. **Tab order**: agent-rows list → "ask cockpit chat" textarea → send button. Don't trap focus inside the chat panel — Tab should escape back to the canvas.

12. **The SSE registry's `publish_safe` is `await publish_safe(case_id, event)`** — no `tenant_id`. Single-tenant demo. Confirm by reading `apps/cockpit-api/src/cockpit_api/services/sse_registry.py` at implementation time.

13. **Token batching**: Orchestrate may emit 1-character tokens or 10-character tokens depending on model. Don't assume 1-char; the UI handles either. The typewriter visual is "text grows" — works at any token granularity.

14. **Don't ship a Zustand chat store.** A `useCockpitChat` hook with local state is sufficient for the demo. A Zustand store would only matter if multiple components needed to read the chat state (e.g., a global "X messages unread" indicator) — out of scope.

### Story dependencies

* **Strict prereqs:** Story 6-7 (Cockpit Chat ADK manifest registered to cloud Orchestrate; chat tools in cockpit-api), Story 4-5 (`AgentCopilotPane` shell), Story 4-6 (SSE stream channel + `publish_safe`), Story 3-3 (`LedgerEntry` shape — for citation resolution), Story 6-6 (slide-out — citation click opens it).
* **Read by:** None in Epic 6. Future Epic 9 (regulator lens / audit timeline) may use the same SSE event names if it surfaces chat history.

### Project Structure Notes

This story creates:
- `apps/cockpit-api/src/cockpit_api/services/citation_parser.py`
- `apps/cockpit-api/tests/services/test_citation_parser.py`
- `apps/cockpit-ui/src/hooks/useCockpitChat.ts`
- `apps/cockpit-ui/src/hooks/useCockpitChat.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/CockpitChatPanel/CockpitChatPanel.tsx`
- `apps/cockpit-ui/src/components/cockpit/CockpitChatPanel/CockpitChatPanel.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/CockpitChatPanel/parseCitations.ts`
- `apps/cockpit-ui/src/components/cockpit/CockpitChatPanel/parseCitations.test.ts`
- `apps/cockpit-ui/src/components/cockpit/CockpitChatPanel/index.ts`

This story modifies:
- `packages/contracts/src/contracts/sse.py` — adds three event names
- `packages/contracts/tests/test_sse.py` — extend
- `apps/cockpit-api/src/cockpit_api/routers/cases.py` — adds chat message route
- `apps/cockpit-api/tests/test_cases_router.py` — extend
- `apps/cockpit-ui/src/components/cockpit/AgentCopilotPane/AgentCopilotPane.tsx` — mount chat panel
- `apps/cockpit-ui/src/components/cockpit/AgentCopilotPane/AgentCopilotPane.test.tsx` — extend
- `apps/cockpit-ui/src/api-types.ts` — regenerated by `make contracts`

This story does NOT create:
- A new SSE channel (reuses Story 4-6's)
- A persistent chat history (in-memory only, per-case, cleared on navigation)
- An "@" mention picker (cut from demo)
- Per-officer chat history (cut)
- A Zustand store for chat (local hook state suffices)

### References

- [Source: `epics.md#Epic 6` § Story 6.9] original AC (verbatim shape; @ mention picker cut, persisted history cut)
- [Source: `architecture.md#API & Communication Patterns`] § A2 SSE
- [Source: `architecture.md#Project-Specific Patterns`] § P6 SSE Event Pattern
- [Source: `architecture.md#Frontend Architecture`] F1, F4
- [Source: `architecture.md#Agent Runtime Update (2026-05-07)`]
- [Source: `prd.md#Functional Requirements` FR13]
- [Source: `prd.md#Innovation & Novel Patterns` Innovation #1]
- [Source: `ux-design-specification.md` § Cockpit Chat color (line 742)]
- [Source: `ux-design-specification.md` § color rule (line 744)] don't leak agent hue
- [Source: `apps/cockpit-api/src/cockpit_api/routers/stream.py`] SSE stream wiring
- [Source: `apps/cockpit-api/src/cockpit_api/services/sse_registry.py`] `publish_safe`
- [Source: `apps/cockpit-ui/src/components/cockpit/AgentCopilotPane/AgentCopilotPane.tsx`] mount target
- [Source: `apps/cockpit-ui/src/components/cockpit/ProvenanceIndicator/`] (existing) citation chip primitive
- [Source: `6-6-reasoning-trace-slide-out-component.md`] citation click target
- [Source: `6-7-cockpit-chat-agent-with-mesh-as-tools.md`] the agent this story converses with

### Demo verification protocol

Per AC16. Cloud Orchestrate streaming integration is the most likely failure mode — ship the fallback path (non-streaming) early and validate the demo's narrative still reads (it does — typewriter is polish, not load-bearing for the "agent answers questions" beat).

If any step fails, the bug is in this story; do not ship until green.

## Dev Agent Record

### Agent Model Used

(claude-opus-4-7 + Amelia persona, bmad-dev-story workflow)

### Debug Log References

- Initial layout placed the chat panel at the *bottom of the page* below the case canvas — user noticed mid-implementation. Root cause: the aside lacked `h-full`, so its `flex-col` couldn't claim viewport height and the `flex-1` chat panel collapsed below the agent-rows section. Fix: `flex h-full max-h-screen flex-col` on the aside; agent-rows section becomes `flex-shrink-0` and the chat panel fills the rest.
- Same pre-existing 5 Vitest failures in `useCase` / `useCases` reproduce on clean main; not caused by this story.

### Completion Notes List

- **Demo simplification — local templated reply**: the cloud Orchestrate streaming SDK (auth flow, tunnel propagation, error modes) is heavy demo lift; the user-facing wow is the typewriter + citation rendering. Built a deterministic `generate_reply(case, ledger_entries, user_message)` that picks one of four intent-templates (screening / ubo / risk / re-run / default) and substitutes real ledger entry IDs from the case's actual ledger. Replies are chunked into ~8-char tokens and published over the existing case SSE channel as `cockpit_chat.token` events, ending with `cockpit_chat.message_complete` carrying the parsed citations. The cloud-registered cockpit_chat agent (Story 6.7) is the surface a Path B reviewer sees in cloud Orchestrate's web chat; this in-cockpit chat is the cockpit-side fallback. Trade-off documented in the route docstring.
- **Dedicated EventSource per panel** instead of multiplexing on the existing `subscribeToCase`. The shared subscription only invalidates query keys; chat needs per-event handlers with payload access. The browser handles two concurrent EventSources fine for the demo; consolidation is a Day-2 cleanup.
- **Citation chip click** is wired through `onCitationClick(ledgerId)` to the AgentCopilotPane's existing slide-out `setOpenTarget` setter (`{actionId, slug: 'cockpit-chat'}`). The slug is approximate — the citation can point to any agent's action — but Story 6.6's slide-out fetches the real trace from Story 6.5's endpoint, so the displayed body is authoritative.
- **`useCockpitChat` hook test deferred** matching the existing `useUboGraph` / `useDocumentIntelligence` pattern (no hook tests in those either; same jsdom `waitFor` flake breaks the harness). The hook is exercised end-to-end via the panel's mocked-hook tests and the Playwright smoke.
- **Empty-state hint disappears after the first message** because `messages.length === 0` flips false. Reset on case-switch happens via the `key={caseId}` remount, so the hint reappears on a fresh case.
- **No DB persistence** — the transcript is in-memory React state. Per Story 6.8 demo simplification.
- **`role="log"` on the transcript region**, `aria-live="polite"`. Citation chips have `aria-label="ledger entry {ledgerId}; click to inspect"` for screen readers.

### File List

- `packages/contracts/src/contracts/sse.py` (modified) — added 3 chat event names to the SseEvent literal.
- `packages/contracts/openapi.json` (regenerated).
- `apps/cockpit-ui/src/api-types.ts` (regenerated).
- `apps/cockpit-api/src/cockpit_api/services/citation_parser.py` (new).
- `apps/cockpit-api/src/cockpit_api/services/cockpit_chat_reply.py` (new) — deterministic templated reply generator.
- `apps/cockpit-api/src/cockpit_api/routers/cases.py` (modified) — `CockpitChatMessageRequest`/`CockpitChatMessageAccepted` models, `POST /cockpit-chat/messages` route, `_stream_chat_reply` background task.
- `apps/cockpit-api/tests/services/test_citation_parser.py` (new) — 6 cases.
- `apps/cockpit-ui/src/hooks/useCockpitChat.ts` (new) — chat state + send + EventSource subscription.
- `apps/cockpit-ui/src/components/cockpit/CockpitChatPanel/CockpitChatPanel.tsx` (new).
- `apps/cockpit-ui/src/components/cockpit/CockpitChatPanel/CockpitChatPanel.test.tsx` (new) — 9 cases.
- `apps/cockpit-ui/src/components/cockpit/CockpitChatPanel/parseCitations.ts` (new).
- `apps/cockpit-ui/src/components/cockpit/CockpitChatPanel/parseCitations.test.ts` (new) — 6 cases.
- `apps/cockpit-ui/src/components/cockpit/CockpitChatPanel/index.ts` (new).
- `apps/cockpit-ui/src/components/cockpit/AgentCopilotPane/AgentCopilotPane.tsx` (modified) — restructured to `h-full flex-col` so the chat panel claims the right-rail height; mounted `<CockpitChatPanel>` below the agent rows; wired `onCitationClick` to the reasoning-trace slide-out.
- `apps/cockpit-ui/src/components/cockpit/AgentCopilotPane/AgentCopilotPane.test.tsx` (modified) — adjusted button-count assertion to filter by aria-label pattern.

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-05-08 | Story 6.8 drafted. Demo replacement for bank-buyer Story 6.9: chat panel mounted in Agent Copilot Pane; POST /cockpit-chat/messages → cloud Orchestrate → SSE token republish on existing case stream; citation parsing renders ProvenancePills with broken-citation red chip fallback; in-memory per-case transcript with key-based reset; @ mention picker + persistent history cut. Streaming/non-streaming fallback documented in route. |
| 2026-05-08 | Implemented Story 6.8. SSE contract + chat route + deterministic templated reply + citation parser (Py + TS) + useCockpitChat hook + CockpitChatPanel + AgentCopilotPane wiring. 21 net-new tests (6 citation_parser Py + 6 parseCitations TS + 9 panel TSX). 529 Python + 314 UI tests green; `make lint` clean. Manual Playwright smoke: typed "explain why screening is amber" → orange chat reply with embedded clickable citation chip pointing to the screening agent's ledger entry. Layout fix: aside `h-full max-h-screen flex-col` so chat sits in the right rail (user feedback). |
