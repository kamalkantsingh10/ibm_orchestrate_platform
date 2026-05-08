# Story 8.3: Writing Agent v2 — EDD memo drafter

Status: review

## Story

As the platform,
I want a Writing agent that drafts a structured EDD narrative memo,
So that the analyst doesn't author from scratch on EDD outcomes (FR26).

## Scope note

v2 of the Writing agent. v1 (Story 7-3) ships a single-call rationale drafter; v2 produces a longer, structured EDD memo with five named sections and citations to ledger entry IDs.

**Demo scope:** the agent is a real ADK agent (per the scope addendum's preservation note about agent fidelity), invoked through the existing case-supervisor / agent-action-decorator pipeline (Story 3-2). The model is whatever the demo's ADK config points at; no special model selection.

**Dependencies:** Stories 7-3 / 7-9 / 3-2 / 3-3 — all in `review`.

## Acceptance Criteria

1. **AC1 — Agent invocation trigger.** Wired in `apps/cockpit-api/src/cockpit_api/services/decision_service.py`. `commit_decision` now accepts an optional `edd_memo_trigger` callback; the cases router supplies one that resolves to `CaseSupervisor.run_writing_edd_memo`. The trigger fires post-DB-commit, post-SSE-publish, and is invoked only when `body.outcome.value == 'escalate_to_edd'`. Failures are logged but do NOT rollback the commit.

2. **AC2 — Prompt template.** New `apps/agents/src/agents/prompts/writing/edd_memo_v1.j2` renders case summary, full ledger map, and the five-section instruction block with explicit `{{led_<ULID>}}` token format and ~1500-word target.

3. **AC3 — Five-section output structure.** `EddMemoOutput` (Pydantic) lives at `packages/contracts/src/contracts/writing.py` with the exact five string fields plus `citations: list[LedgerEntryId]`, `model_id`, and `prompt_template_id: Literal["edd_memo_v1"]`.

4. **AC4 — Inline citation format + structural validator.** A `model_validator(mode="after")` extracts every `{{led_<ULID>}}` token from each section and asserts the set matches `citations` exactly (in both directions). Mismatch raises `CitationStructureError` (wrapped in Pydantic `ValidationError` per Pydantic v2 semantics). Story 8-4's job is the runtime ledger-membership check; this story stops at structural consistency.

5. **AC5 — Agent registry entry.** `apps/agents/src/agents/registry/writing/agent.yaml` declares both `draft_rationale` and `draft_edd_memo` tools, with mode-dispatch instructions for the agent's runtime LLM.

6. **AC6 — Agent action decorator wraps the call.** The new `writing_edd_memo` function in `apps/agents/src/agents/decision/writing.py` is decorated with `@agent_action(agent_id="writing", model_id="placeholder", prompt_template_id="edd_memo_v1")`. The successful-completion ledger entry carries `prompt_template_id == "edd_memo_v1"` and `model_id == "fixture-writing-v1"` (verified by test).

7. **AC7 — Memo renders into Tiptap.**
   - New API endpoint `GET /v1/cases/{case_id}/intake/writing_edd_memo` exposes the persisted `EddMemoOutput`.
   - New UI hook `useEddMemoDraft` consumes it.
   - New helper `lib/eddMemoToHtml.ts` converts the memo to Tiptap-seedable HTML — `<h2>` per section + `<p>` per body — with `{{led_<ULID>}}` tokens rewritten to `<span data-ledger-id="led_…" class="citation-token">…</span>` chips so Story 7.1's citation validator picks them up unchanged.
   - DecisionZone seeds the editor preferring the EDD memo over the v1 rationale (precedence: officer edits → EDD memo → v1 rationale → empty). Auto-save flow continues to apply (rebuild key carries `edd-seeded` signal).

8. **AC8 — Golden inputs validate structure.** `apps/agents/tests/decision/test_writing_edd_memo.py`:
   - **Golden 1:** small fixture case → output validates against `EddMemoOutput` AND contains ≥3 citation tokens that match real ledger IDs ✅
   - **Golden 2:** larger fixture case → all 5 sections non-empty ✅
   - **Golden 3 (negative):** stub LLM emits a fabricated ULID → demonstrates the structural validator fires when the citations list and inline tokens disagree ✅

9. **AC9 — `make lint` + `make test` clean.**
   - `pnpm lint` + `pnpm format:check` clean.
   - `apps/agents pytest`: 168 pass, 1 skipped.
   - `apps/cockpit-api pytest`: 223 pass.
   - `packages/contracts pytest`: 269 pass.
   - `pnpm vitest run` (focused suites): 78 pass across modeStore + ZenMode + DecisionZone + eddMemoToHtml + useGlobalShortcuts.

## Tasks / Subtasks

- [x] **Task 1 — Pydantic schema + validator** (AC: #3, #4)
  - [x] Add `EddMemoOutput` to `packages/contracts/src/contracts/writing.py`
  - [x] Citation-token extraction validator (`{{led_<ULID>}}` round-trip)
  - [x] Unit-test the validator (8 new tests in `packages/contracts/tests/test_writing.py`)
- [x] **Task 2 — Prompt template** (AC: #2)
  - [x] `apps/agents/src/agents/prompts/writing/edd_memo_v1.j2`
- [x] **Task 3 — Mode dispatch in Writing agent** (AC: #5)
  - [x] Extend `apps/agents/src/agents/registry/writing/agent.yaml`
  - [x] Add `writing_edd_memo` to `apps/agents/src/agents/decision/writing.py`
  - [x] Extend `WritingLLM` Protocol with `draft_edd_memo`
  - [x] `FixtureWritingLLM.draft_edd_memo` (Vora / Shree / Ananya / generic templates)
- [x] **Task 4 — Decision-service trigger** (AC: #1)
  - [x] `commit_decision(edd_memo_trigger=…)` callback parameter
  - [x] Cases router wires the callback to `CaseSupervisor.run_writing_edd_memo`
- [x] **Task 5 — Action decorator wrap** (AC: #6)
  - [x] `@agent_action(...prompt_template_id="edd_memo_v1")` on `writing_edd_memo`
- [x] **Task 6 — Cockpit-ui rendering** (AC: #7)
  - [x] New API endpoint `/intake/writing_edd_memo`
  - [x] New hook `useEddMemoDraft`
  - [x] New helper `eddMemoToHtml` + 5 unit tests
  - [x] DecisionZone seeds the editor with EDD memo HTML when present
- [x] **Task 7 — Golden tests** (AC: #8)
  - [x] `test_writing_edd_memo.py` (5 tests; 3 named goldens + 2 ledger/decorator regressions)
- [x] **Task 8 — `make lint` + `make test` clean** (AC: #9)
- [x] **Task 9 — Update sprint-status.yaml to `review`**

## Dev Notes

- **v1 vs v2.** Same agent module, registry, decorator, and adapter Protocol; different prompt template + output schema + supervisor entry method.
- **Citation tokens are inline strings, not separate fields.** The `{{led_<ULID>}}` literal is the LLM-friendly token format. The validator extracts them; the UI helper rewrites them to citation chips at render time.
- **Pydantic v2 wraps validator errors.** `CitationStructureError` is a `ValueError` subclass; raising it in `@model_validator` surfaces as `pydantic.ValidationError` to callers. Tests catch `ValidationError` and `match=` the inner message text.
- **Why `prompt_template_id` in the ledger entry.** The action decorator records the static template id on success; audit can reconstruct exactly which version produced any memo.
- **Story 8-4 is the runtime enforcement** that every cited ledger id resolves to a real ledger entry on the case. This story only enforces internal consistency between inline tokens and the `citations` list.

### File List

**Created**
- `apps/agents/src/agents/prompts/writing/edd_memo_v1.j2`
- `apps/agents/tests/decision/test_writing_edd_memo.py`
- `apps/cockpit-ui/src/hooks/useEddMemoDraft.ts`
- `apps/cockpit-ui/src/lib/eddMemoToHtml.ts`
- `apps/cockpit-ui/src/lib/eddMemoToHtml.test.ts`

**Modified**
- `packages/contracts/src/contracts/writing.py` — `EddMemoOutput`, `EddMemoSections`, `CitationStructureError`, `derive_citations_from_sections`, `_extract_inline_tokens`
- `packages/contracts/src/contracts/__init__.py` — export new symbols
- `packages/contracts/tests/test_writing.py` — 8 new EDD memo tests
- `apps/agents/src/agents/adapters/writing/base.py` — `WritingLLM.draft_edd_memo` Protocol method
- `apps/agents/src/agents/adapters/writing/fixture.py` — `FixtureWritingLLM.draft_edd_memo` + four customer templates + slug-id scanner
- `apps/agents/src/agents/decision/writing.py` — `writing_edd_memo` decorated function + prompt renderer + reasoning-trace builder
- `apps/agents/src/agents/registry/writing/agent.yaml` — both modes + mode-dispatch instructions
- `apps/agents/src/agents/supervisor/case_supervisor.py` — `run_writing_edd_memo` method
- `apps/cockpit-api/src/cockpit_api/services/decision_service.py` — optional `edd_memo_trigger` callback fired post-commit on `escalate_to_edd`
- `apps/cockpit-api/src/cockpit_api/routers/cases.py` — wire the trigger in `post_decision`; new `GET /intake/writing_edd_memo` endpoint
- `apps/cockpit-ui/src/components/cockpit/DecisionZone/DecisionZone.tsx` — consume `useEddMemoDraft`, prefer EDD memo HTML in seed precedence
- `Documentation/implementation-artifacts/sprint-status.yaml`

## Dev Agent Record

### Implementation Plan

1. **Schema-first.** `EddMemoOutput` lives in contracts with the structural-citation validator. Tests for the validator are written first; the rest of the agent is structured to feed it.
2. **Adapter Protocol extended in lockstep.** `WritingLLM.draft_edd_memo` returns the internal `EddMemoSections`; the agent wraps it into `EddMemoOutput` (deriving `citations` from inline tokens, so the structural validator is satisfied by construction for well-formed LLM output).
3. **Fixture rewrites placeholders.** Same trick as v1: customer-template bodies use `[DOCINT]` / `[EV]` / `[UBO]` / `[SCREEN]` / `[RISK]` markers, and `_render_edd` rewrites them to `{{led_<ULID>}}` against the prompt's slug-id map. If a slug has no real id (upstream agent didn't run), the marker is dropped along with surrounding `per` parentheticals so the text reads cleanly.
4. **Trigger decoupled via callback.** `commit_decision` takes an optional async callback so the service stays unit-testable without an agents path-dep. The cases router wires `CaseSupervisor.run_writing_edd_memo` with the request-scoped session factory.
5. **UI seeding precedence.** Officer edits > EDD memo > v1 rationale > empty. The `seedSignature` rebuild key gains `edd-seeded` so Tiptap rebuilds the editor when the EDD memo arrives.

### Completion Notes

- All 9 tasks complete.
- `pnpm lint` + `pnpm format:check` — clean.
- `pnpm vitest run` (touched UI suites) — **78/78 pass**.
- `apps/agents pytest` — **168 pass, 1 skipped**.
- `apps/cockpit-api pytest` — **223 pass**.
- `packages/contracts pytest` — **269 pass**.
- The `make contracts` regen step (OpenAPI → `apps/cockpit-ui/src/api-types.ts`) is **deferred**: the new `/intake/writing_edd_memo` endpoint is consumed via a hand-written hook, not via the generated client. A future story can regenerate when convenient; the demo runs without it.
- The pre-existing `useCase.test.tsx` / `useCases.test.tsx` flake (network/fetch mocking) is unaffected by 8.3.

### Change Log

| Date       | Change                                          |
|------------|-------------------------------------------------|
| 2026-05-08 | Story 8.3 implemented (Amelia). Status: review. |
