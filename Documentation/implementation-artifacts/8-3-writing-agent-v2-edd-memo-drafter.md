# Story 8.3: Writing Agent v2 — EDD memo drafter

Status: backlog

## Story

As the platform,
I want a Writing agent that drafts a structured EDD narrative memo,
So that the analyst doesn't author from scratch on EDD outcomes (FR26).

## Scope note

This is **v2** of the Writing agent. Story 7-3 ships v1 — a single-call rationale drafter for routine decisions. v2 produces a longer, structured EDD memo with five named sections and citations to ledger entry IDs.

**Demo scope:** the agent is a **real ADK agent** (per the scope addendum's preservation note about agent fidelity), invoked through the existing case-supervisor / agent-action-decorator pipeline (Story 3-2). The model is whatever the demo's ADK config points at; no special model selection.

**Dependencies:**
- Story 7-3 (Writing Agent v1 — establishes the agent module, the prompt-template directory layout, and the output schema base class)
- Story 7-9 (Decision outcomes — produces the `escalate_to_edd` outcome that triggers v2)
- Story 3-2 (agent action decorator — wraps the call for ledger persistence)
- Story 3-3 (Pydantic contracts — output schema lives here)

## Acceptance Criteria

1. **AC1 — Agent invocation trigger.** When a case decision is committed with `outcome == 'escalate_to_edd'` (per Story 7-9), the Case Supervisor (Story 3-5) invokes the Writing agent with `mode='edd_memo'`. The trigger is wired in `apps/cockpit-api/src/cockpit_api/services/decision_service.py` post-commit.

2. **AC2 — Prompt template.** New file `apps/agents/src/agents/prompts/writing/edd_memo_v1.j2`. Jinja2 template that renders:
   - Case summary (entity name, type, country)
   - The full ledger for this case (filtered to agent-action and officer-action entries)
   - Named instruction that output must be in five sections, each citing ledger entry IDs
   - Token budget guideline (~1500 words target)

3. **AC3 — Five-section output structure.** The Writing agent's output Pydantic model `EddMemoOutput` (extending the existing `WritingOutput` from Story 7-3) lives at `packages/contracts/src/contracts/writing.py`. Fields:
   - `executive_summary: str`
   - `findings: str`
   - `risk_factors: str`
   - `mitigating_factors: str`
   - `recommendation: str`
   - `citations: list[str]` — flat list of ledger entry ULIDs cited anywhere in the memo

4. **AC4 — Inline citation format.** The five string fields support inline citation tokens of the form `{{led_<ULID>}}` (e.g., `{{led_01HFA8...}}`). The Pydantic validator extracts every token from every section's text and asserts each one is in the `citations` list. Mismatch raises a `CitationStructureError`. (Validation that tokens reference *real* ledger entries is Story 8-4's job; this story only enforces structural consistency.)

5. **AC5 — Agent registry entry.** Update `apps/agents/src/agents/registry/writing/agent.yaml` to declare a second mode `edd_memo` alongside the existing `rationale_draft`. The mode dispatch happens in the agent's main module; one prompt template per mode.

6. **AC6 — Agent action decorator wraps the call.** The agent's main entry function is wrapped by `@agent_action(agent_id='writing', mode='edd_memo')` from Story 3-2. The resulting ledger entry includes the input case_id, the output schema (with citations), and a `prompt_hash` of the rendered template.

7. **AC7 — Memo renders into Tiptap.** The cockpit-ui consumes the agent output via the existing case-detail query and seeds the Tiptap editor (Story 7-1) with the five sections rendered as Tiptap headings + paragraphs. Inline citations render as Tiptap inline marks (chip-styled). Story 7-5's auto-save flow continues to apply.

8. **AC8 — Golden inputs validate structure.** `apps/agents/tests/test_writing_edd_memo.py`:
   - **Golden 1:** A small fixture case with 6 ledger entries → assert agent output validates against `EddMemoOutput` and contains at least 3 citation tokens that match real ledger IDs
   - **Golden 2:** A larger fixture case with 18 ledger entries → assert all 5 sections are non-empty
   - **Golden 3 (negative):** Inject a stub LLM that emits a citation token for a fabricated ULID → assert `CitationStructureError` raises

9. **AC9 — `make lint` + `make test` clean.**

## Tasks / Subtasks

- [ ] **Task 1 — Pydantic schema + validator** (AC: #3, #4)
  - [ ] Add `EddMemoOutput` to `packages/contracts/src/contracts/writing.py`
  - [ ] Write the citation-token extraction validator
  - [ ] Unit-test the validator
- [ ] **Task 2 — Prompt template** (AC: #2)
- [ ] **Task 3 — Mode dispatch in Writing agent** (AC: #5)
  - [ ] Extend `apps/agents/src/agents/registry/writing/agent.yaml`
  - [ ] Update agent main module to dispatch by `mode`
- [ ] **Task 4 — Decision-service trigger** (AC: #1)
  - [ ] In `decision_service.py`, fire `Writing(mode='edd_memo')` when outcome matches
- [ ] **Task 5 — Action decorator wrap** (AC: #6)
- [ ] **Task 6 — Cockpit-ui rendering** (AC: #7)
- [ ] **Task 7 — Golden tests** (AC: #8)
- [ ] **Task 8 — `make lint` + `make test` clean** (AC: #9)
- [ ] **Task 9 — Update sprint-status.yaml to `review`**

## Dev Notes

- **v1 vs v2.** v1 is a single-call rationale drafter (~150 words). v2 is a structured memo (~1500 words) with named sections and stricter citation discipline. They share the agent module, registry entry, output base class, and decorator wrapping — only the prompt template + output schema differ.
- **Citation tokens are inline strings, not separate fields.** The `{{led_<ULID>}}` tokens live inside each section's text. The validator extracts them. This keeps the writing-agent output natural for the LLM while giving us programmatic verification.
- **Why `prompt_hash` in the ledger entry.** The agent action decorator (Story 3-2) records the hash so audit can reconstruct exactly which template version produced a given memo. EDD memos are high-stakes; prompt versioning matters.
- **Story 8-4 is the runtime enforcement** of citations referencing real ledger entries. This story only ensures the citations declared in the `citations` list match the inline tokens present in the text — internal consistency.

### File List

**To create**
- `apps/agents/src/agents/prompts/writing/edd_memo_v1.j2`
- `apps/agents/tests/test_writing_edd_memo.py`

**To modify**
- `packages/contracts/src/contracts/writing.py` (add `EddMemoOutput` + validator)
- `packages/contracts/tests/test_writing.py`
- `apps/agents/src/agents/registry/writing/agent.yaml`
- `apps/agents/src/agents/writing/agent.py` (or main module — dispatch by mode)
- `apps/cockpit-api/src/cockpit_api/services/decision_service.py` (trigger v2 on `escalate_to_edd`)
- `apps/cockpit-ui/src/routes/cases.$caseId.tsx` (seed Tiptap with EDD memo when present)
- `apps/cockpit-ui/src/components/cockpit/DecisionZone/` (or wherever Tiptap lives — render citations as inline marks)
- `Documentation/implementation-artifacts/sprint-status.yaml`
