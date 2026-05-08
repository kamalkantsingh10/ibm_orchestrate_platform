# Story 7.3: Writing agent v1 — rationale draft

Status: review

## Story

As the platform,
I want a Writing agent at `apps/agents/src/agents/decision/writing.py` that — given a case in `decision_ready` state — synthesizes a 2-4 paragraph rationale draft from the case state (Document Intelligence extractions, Entity Verification result, UBO graph, Screening hits, Risk score), cites every load-bearing claim by ledger entry ID, uses a Jinja-templated prompt at `apps/agents/src/agents/prompts/writing/rationale_draft_v1.j2`, returns a typed `DraftedRationale` with HTML-shaped citation tokens (`<span data-ledger-id="led_…">…</span>`), opts-in to Story 6-4's reasoning trace, and exposes the result via the case's intake row so Story 7-1's Decision Zone can pre-load it,
So that Priya never starts from a blank page (FR26 partial), the demo's "edit, don't author" Innovation #5 has a real LLM-generated artifact to edit, and the Writing agent shows up as the 8th agent in the Orchestrate tenant alongside the seven existing intake/chat agents (NFR-RI1 ADK pattern coverage — agent-as-tool with Pydantic-contracted IO).

## Scope note (2026-04-29 demo re-scope)

This story is the demo-equivalent of the bank-buyer Story 7.7. The bank-buyer scope had the agent's draft persisted to a server-side `decision_drafts` table; the demo writes it to the case's existing intake row.

| Bank-buyer scope (original 7.7) | Demo replacement in this story |
|---|---|
| Tenant-scoped agent invocation | **Single-tenant.** |
| Persist draft to `decision_drafts` table (versioned) | **Persist to `intake.writing` field** alongside other agent outputs (Stories 5-1 / 5-3 / 6-2 added theirs the same way). |
| Citations rendered client-side as inline tokens in Tiptap | **Same** — Story 7-1 consumes the HTML-shape. |
| Broken citations surface as render-time errors in Tiptap | **Same** — Story 7-1 owns the validator; this story produces the citations. |
| Jinja prompt template + golden inputs (NFR-RI7) | **Same.** Template at `apps/agents/src/agents/prompts/writing/rationale_draft_v1.j2`. |
| Edit-rate metric tracked at commit | **Cut for demo.** Story 7-13 (bank-buyer) is gone. The Writing agent's draft is recorded in the agent.completed entry; Story 7-7's POST records the officer's final HTML; comparison is achievable later via SQL / scripts but not surfaced. |

What survives: **Pydantic-typed IO (`WritingAgentInput`, `DraftedRationale`), Jinja template with golden inputs, real LLM call via `WritingLLM` adapter (mirrors `DocAILLM` shape), `@agent_action` ledger entry, citation extraction from the model's output, `agent_slug='writing'` matching `AgentSlug.WRITING`, registration to cloud Orchestrate, supervisor extension to invoke the Writing agent post-intake.**

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md`, `architecture.md#Project-Specific Patterns` § P4, `prd.md#Functional Requirements` FR26, `prd.md#Innovation & Novel Patterns` Innovation #5.

## Acceptance Criteria

1. **AC1 — Pydantic contracts in `packages/contracts/src/contracts/writing.py`.**

    ```python
    from typing import Literal

    from pydantic import BaseModel, Field

    from contracts.cases import CaseId
    from contracts.ledger import LedgerEntryId


    class CitedClaim(BaseModel):
        """One factual claim in the drafted rationale, paired with the ledger
        entry that backs it. The LLM is asked to emit (claim_text, ledger_id)
        pairs in a structured response; the agent assembles them into HTML.
        """

        model_config = {"frozen": True}

        text: str = Field(min_length=1, max_length=400)
        evidence_ledger_id: LedgerEntryId


    class DraftedRationale(BaseModel):
        """The Writing agent's output — a structured rationale with citations.

        ``html`` is the renderable form for Tiptap (citation tokens already
        wrapped in <span data-ledger-id="…">…</span>). ``paragraphs`` and
        ``cited_claims`` carry the structured signal for downstream
        analytics (edit-rate, citation density) — bank-buyer additions
        cut for the demo's surface but cheap to keep on the contract.
        """

        model_config = {"frozen": True}

        case_id: CaseId
        html: str = Field(min_length=20)
        paragraphs: list[str] = Field(min_length=2, max_length=4)
        cited_claims: list[CitedClaim] = Field(default_factory=list)
        model_id: str = Field(min_length=1)
        prompt_template_id: Literal["rationale_draft_v1"] = "rationale_draft_v1"


    class WritingAgentInput(BaseModel):
        model_config = {"frozen": True}
        case_id: CaseId
        # Upstream typed outputs are NOT in the input — the agent reads them
        # via the supervisor's IntakeContext at call time. Mirrors Story 6-2
        # (screening agent reads ev_out + ubo_out via _build_screening_subjects).
    ```

    Re-export from `packages/contracts/src/contracts/__init__.py`. Public symbols: `CitedClaim`, `DraftedRationale`, `WritingAgentInput`. Alphabetical `__all__`.

2. **AC2 — `WritingLLM` Protocol + adapters at `apps/agents/src/agents/adapters/writing/`.**

    Folder layout (mirrors `apps/agents/src/agents/adapters/doc_ai/`):

    ```
    apps/agents/src/agents/adapters/writing/
    ├── __init__.py        # exports WritingLLM, get_default_writing_llm
    ├── base.py            # Protocol + WritingLLMError
    ├── fixture.py         # FixtureWritingLLM — deterministic golden output
    └── watsonx.py         # WatsonxWritingLLM — real LLM via httpx
    ```

    Protocol:

    ```python
    from typing import Protocol, runtime_checkable

    class WritingLLMError(RuntimeError):
        """Raised by a ``WritingLLM`` impl on transient failure."""


    @runtime_checkable
    class WritingLLM(Protocol):
        model_id: str

        async def draft_rationale(
            self,
            *,
            rendered_prompt: str,
        ) -> "RawRationaleDraft": ...
    ```

    `RawRationaleDraft` is an internal Pydantic model returned by the LLM call, before citation HTML wrapping:

    ```python
    class RawRationaleDraft(BaseModel):
        model_config = {"frozen": True}
        paragraphs: list[str]
        cited_claims: list[CitedClaim]   # parallel-rebuilt from prompt-instructed JSON output
    ```

    The adapter prompts the LLM to return structured JSON (paragraphs + claims with ledger_ids) — the agent, not the adapter, assembles the final HTML with citation marks.

    **`FixtureWritingLLM`** — returns a deterministic 3-paragraph rationale pinned to the demo case (Vora / Shree / Ananya). Reads the case_id (or, more robustly, a content-hash of the rendered prompt) and returns a fixed `RawRationaleDraft` from a static dict in `fixture.py`. Used in CI; doesn't make a network call.

    **`WatsonxWritingLLM`** — real httpx call to watsonx.ai's text-generation endpoint, mirrors `WatsonxDocAILLM`'s pattern. Reads `WATSONX_API_KEY` env. Uses the same prompt-hash + ContextVar plumbing (`set_runtime_model_id`, `set_runtime_prompt_hash`) the doc-AI adapter uses.

    Factory `get_default_writing_llm()` in `__init__.py`:

    ```python
    import os
    from agents.adapters.writing.base import WritingLLM
    from agents.adapters.writing.fixture import FixtureWritingLLM

    def get_default_writing_llm() -> WritingLLM:
        provider = os.getenv("WRITING_LLM_PROVIDER", "fixture").lower()
        if provider == "fixture":
            return FixtureWritingLLM()
        if provider == "watsonx":
            from agents.adapters.writing.watsonx import WatsonxWritingLLM
            return WatsonxWritingLLM()
        raise ValueError(
            f"Unknown WRITING_LLM_PROVIDER={provider!r}. "
            f"Demo supports 'fixture' (default) or 'watsonx'."
        )
    ```

    Default is `fixture` — keeps `make seed` and CI offline-safe. Dev sets `WRITING_LLM_PROVIDER=watsonx` for the demo run.

3. **AC3 — Jinja prompt template at `apps/agents/src/agents/prompts/writing/rationale_draft_v1.j2`.**

    Template inputs (all typed, passed by the agent to `Environment.get_template().render(...)`):

    | Variable | Type | Source |
    |---|---|---|
    | `case` | `Case` | from intake context |
    | `extracted_fields` | `list[ExtractedField]` | Doc Intel output |
    | `entity_status` | `MCAStatus \| None` + mismatches summary string | Entity Verification output |
    | `ubo_summary` | string (e.g., "6 nodes, 3 nominee-suspected edges") | UBO Graph output |
    | `screening_summary` | string + open hits + dismissed hits | Screening output |
    | `risk_summary` | string + total + band + components | Risk Scoring output |
    | `ledger_ids` | `dict[str, str]` mapping `agent_slug → led_<ULID>` | Latest agent.completed per agent |

    Template structure:

    ```
    You are the Writing Agent. Produce a 2–4 paragraph KYC decision rationale
    for the case below. Each load-bearing factual claim MUST cite a ledger
    entry by its full id (format `led_<26-char Crockford-Base32>`), drawn
    only from the ledger_ids map below — do not invent ids.

    Case: {{ case.customer_metadata.customer_name }}
    State: {{ case.state }}
    Document Intelligence: {{ extracted_fields | length }} fields extracted (cite as {{ ledger_ids.document_intelligence }}).
    Entity Verification: MCA status {{ entity_status }} (cite as {{ ledger_ids.entity_verification }}).
    UBO Graph: {{ ubo_summary }} (cite as {{ ledger_ids.ubo_graph }}).
    Screening: {{ screening_summary }} (cite as {{ ledger_ids.screening }}).
    Risk Scoring: {{ risk_summary }} (cite as {{ ledger_ids.risk_scoring }}).

    Respond with strict JSON matching this schema:
    {
      "paragraphs": ["<paragraph text>", ...],
      "cited_claims": [
        {"text": "<sentence asserting one fact>", "evidence_ledger_id": "led_..."}
      ]
    }

    Rules:
    - 2 to 4 paragraphs.
    - Each paragraph must reference at least one cited_claim.
    - Use only ledger_ids from the map above; do not invent ids.
    - Tone is professional, evidence-grounded; avoid hedging language ("may", "perhaps").
    - End with a one-sentence recommendation framed as a draft, not a verdict — the officer commits.
    ```

    The Jinja env config matches doc_ai's exactly: `autoescape=select_autoescape(default=False)`, `trim_blocks=False`, `lstrip_blocks=False`, `keep_trailing_newline=True`.

    Add a sibling **golden inputs** file at `apps/agents/src/agents/prompts/writing/golden/vora_rationale_v1.json` (and `shree_*.json`, `ananya_*.json`) — JSON dicts matching the template inputs for each demo case. Tests render the template against each golden input + assert the rendered prompt's SHA-256 is stable (NFR-RI7).

4. **AC4 — Agent function at `apps/agents/src/agents/decision/writing.py`.**

    ```python
    from cockpit_api.services.ledger_service import LedgerReader

    from contracts.writing import (
        CitedClaim, DraftedRationale, WritingAgentInput,
    )
    from contracts.cases import Case
    from contracts.document_intelligence import DocumentIntelligenceOutput
    from contracts.entity_verification import EntityVerificationResult
    from contracts.ubo import UBOGraph
    from contracts.screening import ScreeningAgentOutput
    from contracts.risk import RiskScore   # Story 5-6

    from agents.adapters.writing import get_default_writing_llm, WritingLLM
    from agents.adapters.writing.base import RawRationaleDraft
    from agents.supervisor.action_decorator import (
        agent_action, set_runtime_reasoning_trace,
    )


    @agent_action(
        agent_id="writing",
        model_id="placeholder",     # overwritten via set_runtime_model_id inside the adapter
        prompt_template_id="rationale_draft_v1",
    )
    async def writing(
        input: WritingAgentInput,
        *,
        case: Case,                                               # supervisor passes
        doc_intel: DocumentIntelligenceOutput,
        entity_verification: EntityVerificationResult | None,
        ubo: UBOGraph | None,
        screening: ScreeningAgentOutput | None,
        risk: RiskScore | None,
        ledger_ids: dict[str, str],                              # latest agent.completed per slug
        llm: WritingLLM | None = None,
    ) -> DraftedRationale:
        resolved = llm or get_default_writing_llm()
        rendered_prompt = _render_prompt_v1(case, doc_intel, entity_verification, ubo, screening, risk, ledger_ids)
        raw: RawRationaleDraft = await resolved.draft_rationale(rendered_prompt=rendered_prompt)
        html = _wrap_html_with_citations(raw)
        # Optional reasoning trace (Story 6-4):
        set_runtime_reasoning_trace(_build_trace(raw, ledger_ids))
        return DraftedRationale(
            case_id=input.case_id,
            html=html,
            paragraphs=raw.paragraphs,
            cited_claims=raw.cited_claims,
            model_id=resolved.model_id,
            prompt_template_id="rationale_draft_v1",
        )
    ```

    Helpers:
    * `_render_prompt_v1(...)` — Jinja render call, returns the rendered string.
    * `_wrap_html_with_citations(raw)` — assembles the final HTML. For each paragraph, walks `cited_claims` and wraps each claim's text in `<span data-ledger-id="led_…" class="citation-token">…</span>`. Joins paragraphs with `</p><p>`. Wraps in `<p>…</p>`. Tests assert the citation spans are well-formed and reference real ledger IDs from the input.
    * `_build_trace(raw, ledger_ids)` — builds a `ReasoningTrace`:
        * `what_searched`: "Synthesized a rationale from the latest case agent outputs (Document Intelligence, Entity Verification, UBO Graph, Screening, Risk Scoring)."
        * `what_hit`: "Generated {n} paragraphs citing {m} ledger entries: {comma-separated ids}."
        * `confidence_self_rating`: confidence based on coverage — fraction of available ledger_ids that the draft actually cites; rationale "Confidence reflects how many available agent outputs the rationale cites — full coverage is high; partial is lower."
        * `counterfactual`: "Draft would change if the officer corrects an upstream agent output (e.g., UBO drag-correct) and the case re-enters decision_ready, or if the writing template is updated."

5. **AC5 — Supervisor extension in `apps/agents/src/agents/supervisor/case_supervisor.py`.**

    The Writing agent is **not** part of the intake fan-out (`INTAKE_AGENTS`) because it depends on every intake agent's output. Add a separate supervisor method `run_writing(case_id)`:

    ```python
    async def run_writing(self, case_id: CaseId) -> DraftedRationale:
        async with self._session_factory() as session:
            case = await self._case_repo.fetch_by_id(session, case_id)
            if case is None:
                raise CaseNotFoundError(case_id)
            if case.state not in (CaseState.DECISION_READY, CaseState.PENDING_SEAL, CaseState.COMMITTED):
                # Allow re-running on already-committed cases for re-drafts (officer asks chat agent to rewrite)
                raise CaseNotInDecisionReadyError(case_id, case.state)

            # Load latest agent outputs from intake row (already-typed by 5-1, 5-3, 6-2, etc.)
            intake = await self._intake_repo.fetch_by_case(session, case_id)
            doc_intel = intake.document_intelligence if intake else None
            ev = intake.entity_verification if intake else None
            ubo_out = intake.ubo_graph if intake else None
            screening = intake.screening if intake else None
            risk = intake.risk_scoring if intake else None

            if doc_intel is None:
                raise WritingPrerequisitesMissingError(case_id, "document_intelligence")

            # Resolve latest agent.completed ledger ids per slug
            reader = self._ledger_reader
            ledger_ids: dict[str, str] = {}
            for slug in ("document_intelligence", "entity_verification", "ubo_graph", "screening", "risk_scoring"):
                entry = await reader.read_latest_by_actor(case_id, slug)
                if entry: ledger_ids[slug] = entry.id

            output = await writing(
                WritingAgentInput(case_id=case_id),
                case=case, doc_intel=doc_intel, entity_verification=ev,
                ubo=ubo_out, screening=screening, risk=risk,
                ledger_ids=ledger_ids,
            )

            # Two-pass evidence_ids back-fill is not applicable here — writing's
            # output doesn't carry ProvenancedField. Skip the helper; just persist.
            await self._intake_repo.update_writing(session, case_id, output)
            return output
    ```

    This method is invoked when:
    * **Automatic** — at the end of `run_intake`, after all intake agents complete and case state transitions to `DECISION_READY`. **Add a hook** at the end of `_run_intake` that calls `await self.run_writing(case_id)` if the case is now in `DECISION_READY`. Wrapping in a try/except that logs but doesn't fail intake — Writing failures should not roll back intake.
    * **Manual / re-run** — exposed via `POST /v1/cases/{case_id}/agents/writing/run` (extend Story 6-7's `re_run_agent` route's literal to include `"writing"`; logic invokes `run_writing`).

6. **AC6 — Persist `DraftedRationale` to intake row.**

    Extend `apps/cockpit-api/src/cockpit_api/repositories/intake_repo.py` (or the underlying SQLAlchemy model) to add a `writing: DraftedRationale | None = None` field, mirroring the screening field added by Story 6-2 § AC6. SQLite + SQLAlchemy auto-creates schema; no migration. Backward compat: pre-existing rows have `writing == None`.

    `intake_repo.update_writing(session, case_id, output)` — upserts the row's `writing` field.

7. **AC7 — Expose via existing `GET /v1/cases/{case_id}/intake`.**

    The route from Story 6-2 already returns the intake envelope; add `writing: DraftedRationale | None` to the response model. Pydantic backward-compat covers old rows.

    Story 7-1's `useWritingAgentDraft(caseId)` reads from this endpoint.

8. **AC8 — ADK registry at `apps/agents/src/agents/registry/writing/`.**

    `agent.yaml`:

    ```yaml
    spec_version: v1
    kind: native
    name: writing
    description: >-
      Drafts the KYC decision rationale for a case in decision_ready state,
      synthesizing findings from Document Intelligence, Entity Verification,
      UBO Graph, Screening, and Risk Scoring. Cites every load-bearing
      claim by ledger entry id; output is the officer's editable starting point.

    llm: groq/openai/gpt-oss-120b
    style: default

    instructions: |
      You are the Writing Agent. Your only job is to invoke the
      `draft_rationale` tool with the supplied case_id and return the result.

      When the user asks you to draft a rationale:
      1. Identify the case_id (looks like `case_<26-char ULID>`).
      2. Call `draft_rationale` exactly once with that case_id.
      3. Read the response and produce a short summary: number of paragraphs,
         number of citations, the model_id used, and a one-line preview of
         the rationale's first paragraph.

      Never invent rationale content. If the tool fails, surface the error
      verbatim and suggest the user re-run after intake completes.

    tools:
      - draft_rationale

    collaborators: []
    ```

    `openapi.yaml` — exposes `POST /v1/agents/writing/draft` with `WritingAgentInput` request body and `DraftedRationale` response. `operationId: draft_rationale`. Same `servers:` tunnel-URL pattern as the other agents.

9. **AC9 — Cockpit-api router for `POST /v1/agents/writing/draft`.**

    Extend `apps/cockpit-api/src/cockpit_api/routers/agents.py` with `async def draft_rationale(...)`. Calls `CaseSupervisor.run_writing(case_id)` (or the `writing(...)` agent function directly with the appropriate inputs — pick whichever cleanly fits the existing pattern in `agents.py`). Returns the typed `DraftedRationale`.

    The `re_run_agent` route in `cases.py` (Story 6-7's `POST /v1/cases/{case_id}/agents/{agent_slug}/run`) extends its `agent_slug` literal to include `"writing"` and calls `supervisor.run_writing(case_id)`.

10. **AC10 — Tests at `packages/contracts/tests/test_writing.py`.**

    * `DraftedRationale` round-trips through JSON.
    * Empty `paragraphs` rejected (`min_length=2`).
    * `paragraphs` with > 4 entries rejected (`max_length=4`).
    * `CitedClaim.text` length bounds (1–400) enforced.
    * `CitedClaim.evidence_ledger_id` shape validated (Crockford-Base32 ULID with `led_` prefix).
    * `WritingAgentInput` round-trips.

11. **AC11 — Tests at `apps/agents/tests/decision/test_writing.py`.**

    * **Happy path with FixtureWritingLLM** — invoke writing agent with Vora's pinned inputs; assert output's `html` contains 3 `<span data-ledger-id="led_…">` tokens; assert paragraph count is 2–4; assert cited_claims length matches HTML span count.
    * **`get_default_writing_llm` returns FixtureWritingLLM by default** — env unset → fixture.
    * **`WRITING_LLM_PROVIDER=watsonx`** + missing `WATSONX_API_KEY` → `WritingLLMError` (or whatever the watsonx adapter raises).
    * **Reasoning trace populated** — assert ledger entry's `payload.reasoning_trace.what_searched` mentions the upstream agents.
    * **Citation HTML well-formed** — parse output with `lxml`/`html5lib`; assert no orphan tags.
    * **All cited ledger_ids appear in the input's ledger_ids map** — no hallucination by the wrapper helper. (LLM hallucination is the LLM's problem; the wrapper is the gate.)

12. **AC12 — Tests at `apps/agents/tests/test_case_supervisor.py` (extend Story 5-1's tests).**

    * **Vora intake → writing runs automatically post-intake** — assert `run_intake` triggers `run_writing`; assert one `agent.completed` entry with `actor_id="writing"`; assert intake row's `writing` field populated.
    * **Writing failure does not roll back intake** — stub `WritingLLM` to raise; assert intake completes; assert `agent.failed` entry written; assert `intake.writing` remains None.
    * **`run_writing` rejects when state is `intake_scheduled`** (case hasn't completed intake).
    * **`run_writing` rejects when `document_intelligence` output is missing** (e.g., a case with no documents — defensive).
    * **`run_writing` succeeds on a `committed` case** (re-draft path).

13. **AC13 — Tests at `apps/cockpit-api/tests/test_cases_intake_route.py` (extend).**

    * `GET /v1/cases/{vora_id}/intake` returns `writing.html` and `writing.cited_claims`.
    * Backward compat: old intake row without `writing` returns `writing: null`.

14. **AC14 — Tests at `apps/cockpit-api/tests/test_agents_router.py` (extend).**

    * `POST /v1/agents/writing/draft` with valid body → 200 + `DraftedRationale`.
    * `POST /v1/cases/{id}/agents/writing/run` (Story 6-7's route extended) → 200 + `AgentRerunResponse`.

15. **AC15 — Golden prompt fixture tests at `apps/agents/tests/decision/test_prompts_writing.py`.**

    * Render `rationale_draft_v1.j2` against the `golden/vora_rationale_v1.json` input; assert the rendered prompt's SHA-256 matches the recorded golden hash. **Lock the golden** — change requires updating the hash + a code review.
    * Same for Shree and Ananya goldens.
    * The rendered prompt does NOT contain any case PII not in the inputs (basic safety check — assert no occurrences of "test_secret_*" or similar test sentinel strings).

16. **AC16 — TS types regenerate.**

    `make contracts` regenerates `apps/cockpit-ui/src/api-types.ts` to include `DraftedRationale`, `CitedClaim`, `WritingAgentInput`. Story 7-1's `useWritingAgentDraft` consumes these types.

17. **AC17 — `make lint && make test` clean.** Net new test count: ≥ 6 in `test_writing.py` (contracts), ≥ 6 in `test_writing.py` (agent), ≥ 5 in `test_case_supervisor.py` (extend), ≥ 2 in `test_cases_intake_route.py` (extend), ≥ 2 in `test_agents_router.py` (extend), ≥ 3 in `test_prompts_writing.py`.

18. **AC18 — End-to-end demo verification.**

    ```bash
    make demo-reset && make seed
    poetry -C apps/cockpit-api run python -c "
    import asyncio
    from contracts.cases import VORA_CAPITAL_ID
    from agents.supervisor.case_supervisor import CaseSupervisor
    from cockpit_api.db.session import session_factory
    async def main():
        s = CaseSupervisor(session_factory=session_factory)
        outcome = await s.run_intake(VORA_CAPITAL_ID)
        print('intake:', outcome.case_state)
    asyncio.run(main())
    "

    curl -s "http://localhost:8000/v1/cases/${VORA_ID}/intake" | jq '.writing.paragraphs | length'
    # → 2 (or 3 — within [2,4])

    curl -s "http://localhost:8000/v1/cases/${VORA_ID}/intake" | jq '.writing.html'
    # → "<p>...<span data-ledger-id=\"led_...\" class=\"citation-token\">...</span>...</p>"

    # In the cockpit-ui (Story 7-1), open Vora's case → Decision Zone preloaded with this draft.
    ```

## Tasks / Subtasks

- [x] **Task 1 — Pydantic contracts** (AC: #1, #10, #16)
  - [ ] Subtask 1.1 — `packages/contracts/src/contracts/writing.py` with `CitedClaim`, `DraftedRationale`, `WritingAgentInput`.
  - [ ] Subtask 1.2 — Re-export from `__init__.py`.
  - [ ] Subtask 1.3 — `packages/contracts/tests/test_writing.py` (≥ 6 cases).
  - [ ] Subtask 1.4 — `make contracts`.

- [x] **Task 2 — `WritingLLM` adapter family** (AC: #2)
  - [ ] Subtask 2.1 — `apps/agents/src/agents/adapters/writing/base.py`.
  - [ ] Subtask 2.2 — `fixture.py` with deterministic Vora/Shree/Ananya outputs.
  - [ ] Subtask 2.3 — `watsonx.py` mirroring `WatsonxDocAILLM`.
  - [ ] Subtask 2.4 — `__init__.py` with `get_default_writing_llm`.

- [x] **Task 3 — Jinja prompt template + goldens** (AC: #3, #15)
  - [ ] Subtask 3.1 — `apps/agents/src/agents/prompts/writing/rationale_draft_v1.j2`.
  - [ ] Subtask 3.2 — `prompts/writing/golden/vora_rationale_v1.json` + Shree + Ananya.
  - [ ] Subtask 3.3 — `apps/agents/tests/decision/test_prompts_writing.py` (≥ 3 cases).

- [x] **Task 4 — Agent function** (AC: #4, #11)
  - [ ] Subtask 4.1 — `apps/agents/src/agents/decision/__init__.py` (new module).
  - [ ] Subtask 4.2 — `apps/agents/src/agents/decision/writing.py` with `writing` agent.
  - [ ] Subtask 4.3 — `_render_prompt_v1`, `_wrap_html_with_citations`, `_build_trace` helpers.
  - [ ] Subtask 4.4 — `apps/agents/tests/decision/test_writing.py` (≥ 6 cases).

- [x] **Task 5 — Supervisor `run_writing`** (AC: #5, #12)
  - [ ] Subtask 5.1 — Add `run_writing` method to `CaseSupervisor`.
  - [ ] Subtask 5.2 — Hook into `_run_intake`'s post-success path (try/except).
  - [ ] Subtask 5.3 — Add `WritingPrerequisitesMissingError` typed exception.
  - [ ] Subtask 5.4 — Extend `apps/agents/tests/test_case_supervisor.py` (≥ 5 cases).

- [x] **Task 6 — Persist + expose via API** (AC: #6, #7, #13)
  - [ ] Subtask 6.1 — Add `writing` field to intake_repo / SQLAlchemy model.
  - [ ] Subtask 6.2 — `intake_repo.update_writing` method.
  - [ ] Subtask 6.3 — Update `GET /v1/cases/{id}/intake` response model.
  - [ ] Subtask 6.4 — Extend `test_cases_intake_route.py` (≥ 2 cases).

- [x] **Task 7 — ADK registry + cockpit-api tool route** (AC: #8, #9, #14)
  - [ ] Subtask 7.1 — `apps/agents/src/agents/registry/writing/agent.yaml`.
  - [ ] Subtask 7.2 — `apps/agents/src/agents/registry/writing/openapi.yaml`.
  - [ ] Subtask 7.3 — `POST /v1/agents/writing/draft` route in `routers/agents.py`.
  - [ ] Subtask 7.4 — Extend `re_run_agent` literal in `routers/cases.py` to include `"writing"`.
  - [ ] Subtask 7.5 — Extend `test_agents_router.py` (≥ 2 cases).

- [x] **Task 8 — Verification** (AC: #17, #18)
  - [ ] Subtask 8.1 — `make lint && make test` green.
  - [ ] Subtask 8.2 — Manual demo per AC18.

## Dev Notes

### Architectural context (binding)

* [Source: `architecture.md#Project-Specific Patterns` § P4 Agent Action Pattern] every agent invocation writes one ledger entry via `@agent_action`.
* [Source: `architecture.md#Project-Specific Patterns` § P1 Pluggable Adapter Pattern] WritingLLM Protocol with fixture + watsonx implementations mirrors DocAILLM.
* [Source: `architecture.md#Non-Functional Requirements` NFR-RI7] Jinja templates with golden inputs — hash-locked at AC15.
* [Source: `architecture.md#Demo Scope Addendum (2026-04-29)`] LLM provider keys live in cockpit-api's env (the architecture's S8 aspirational "live in Orchestrate runtime config" diverged in implementation; this story follows the existing pattern).
* [Source: `architecture.md#Project-Specific Patterns` § P8 Counterfactual Reasoning Trace Pattern] Writing opts in to Story 6-4's reasoning trace via `set_runtime_reasoning_trace`.
* [Source: `prd.md#Functional Requirements` FR26] writing agent provides draft.
* [Source: `prd.md#Innovation & Novel Patterns` Innovation #5] "Edit, Don't Author" — the draft is the substrate for officer editing.

### Critical pitfalls

1. **Writing is NOT an intake-fan-out agent.** Don't add it to `INTAKE_AGENTS`. Its inputs are every other agent's outputs — so it runs after intake, not alongside.

2. **Writing failure must not fail intake.** If the LLM is unreachable or the prompt fails, the case still reaches `decision_ready`; the officer can write the rationale from scratch in the Decision Zone. Wrap `run_writing` in try/except inside `_run_intake`'s success path.

3. **Citation hallucination is the LLM's failure mode, not ours.** The `_wrap_html_with_citations` helper trusts `raw.cited_claims` as-is. The LLM is instructed to cite only from `ledger_ids` (in the prompt). The defense-in-depth check is **client-side at commit time** (Story 7-1's `findBrokenCitations`). Don't add a server-side validator that strips bad citations — the demo's narrative needs the broken-citation render-time error to be visible.

4. **Fixture LLM must be deterministic.** Use the case_id (or content-hash of rendered prompt) as the dispatch key; return the same `RawRationaleDraft` every time. Tests AC11 verify byte-stability across runs.

5. **`set_runtime_reasoning_trace` must fire BEFORE the agent function returns.** Pattern matches Stories 5-1 / 6-2 / 6-4. The decorator reads the ContextVar after the wrapped function returns; setting it after would be a no-op. Tests assert.

6. **The Writing agent's `cited_claims` are CLAIMS, not paragraph chunks.** A claim is one sentence asserting one fact. A paragraph contains multiple sentences and may have multiple cited_claims (or zero — narrative connective tissue). The HTML wrapping inserts citation spans only around claim text, not whole paragraphs. Tests verify span placement.

7. **Two-pass evidence_ids back-fill is N/A here.** Stories 5-1 / 6-2 use it because their outputs carry `ProvenancedField` with `evidence_ids` referencing the agent's own ledger entry. The Writing agent's output has no `ProvenancedField`. Don't add the helper.

8. **ledger_ids map's keys are agent slugs (snake_case)** — `document_intelligence`, `entity_verification`, `ubo_graph`, `screening`, `risk_scoring`. NOT `AgentSlug` enum values (which are kebab-case). Match `actor_id` convention from existing ledger entries.

9. **Prompt template SHA-256 is the NFR-RI7 lock.** Test AC15 records the hash; updating the prompt requires updating the hash + code review. This is the discipline that prevents silent prompt drift.

10. **Persist draft HTML, not just paragraphs.** Story 7-1's Tiptap editor consumes HTML; reconstructing HTML from `paragraphs + cited_claims` on the client is needless work and surface area for drift. Persist `html` as the source of truth.

11. **`run_writing` is callable on `committed` cases for re-draft.** Officer asks Cockpit Chat "rewrite the rationale" — the chat agent invokes `re_run_agent(writing)`. The new draft replaces the old in `intake.writing` (and writes a new `agent.completed` entry); the officer's local committed rationale is unchanged (the ledger preserves history). Tests AC12 verify.

12. **The Writing agent needs upstream typed outputs from the intake row.** If Story 5-6 (Risk Scoring) hasn't landed yet — it's currently in `review` — the supervisor's `run_writing` may get `risk=None`. The prompt template uses `{% if risk_summary %}…{% endif %}` to skip risk-related sentences. Ensure the template gracefully handles partial inputs. Tests cover the partial case.

13. **HTML escaping in `_wrap_html_with_citations`** — paragraph text from the LLM may contain HTML special chars (`<`, `&`). Escape via `html.escape(text)` before wrapping. The citation span is the only HTML the helper introduces. Tests verify with a malicious-input case.

### Story dependencies

* **Strict prereqs:** Story 3-2 (`@agent_action`), Story 3-3 (`AgentActionLedgerEntry`), Story 3-4 (Jinja env + adapter pattern reference), Story 3-5 (supervisor + intake_repo pattern), Story 5-1 / 5-3 / 6-2 (intake row schema for upstream typed outputs), Story 6-4 (`ReasoningTrace` contract — opt-in), Story 6-7 (`re_run_agent` route to extend).
* **Soft prereq:** Story 5-6 (Risk Scoring agent — its output is one of the prompt inputs; falls back gracefully if absent).
* **Read by:** Story 7-1 (`useWritingAgentDraft` consumes the intake row's `writing` field), Story 8-3 (Writing v2 EDD memo extends this pattern).

### Project Structure Notes

This story creates:
- `packages/contracts/src/contracts/writing.py`
- `packages/contracts/tests/test_writing.py`
- `apps/agents/src/agents/decision/__init__.py`
- `apps/agents/src/agents/decision/writing.py`
- `apps/agents/src/agents/adapters/writing/__init__.py`
- `apps/agents/src/agents/adapters/writing/base.py`
- `apps/agents/src/agents/adapters/writing/fixture.py`
- `apps/agents/src/agents/adapters/writing/watsonx.py`
- `apps/agents/src/agents/prompts/writing/rationale_draft_v1.j2`
- `apps/agents/src/agents/prompts/writing/golden/{vora,shree,ananya}_rationale_v1.json`
- `apps/agents/src/agents/registry/writing/agent.yaml`
- `apps/agents/src/agents/registry/writing/openapi.yaml`
- `apps/agents/tests/decision/__init__.py` (empty)
- `apps/agents/tests/decision/test_writing.py`
- `apps/agents/tests/decision/test_prompts_writing.py`

This story modifies:
- `packages/contracts/src/contracts/__init__.py` — public exports
- `apps/agents/src/agents/supervisor/case_supervisor.py` — adds `run_writing` + intake post-hook
- `apps/cockpit-api/src/cockpit_api/repositories/intake_repo.py` — adds `writing` field + `update_writing`
- `apps/cockpit-api/src/cockpit_api/routers/cases.py` — `GET /intake` includes `writing`; `re_run_agent` literal extended
- `apps/cockpit-api/src/cockpit_api/routers/agents.py` — adds `POST /v1/agents/writing/draft`
- `apps/agents/tests/test_case_supervisor.py` — extend
- `apps/cockpit-api/tests/test_cases_intake_route.py` — extend
- `apps/cockpit-api/tests/test_agents_router.py` — extend
- `apps/cockpit-ui/src/api-types.ts` — regenerated by `make contracts`

This story does NOT create:
- The Decision Zone UI (Story 7-1)
- POST /decisions endpoint (Story 7-7)
- Edit-rate metric (cut from demo)
- A separate `decision_drafts` SQLAlchemy table (cut — uses intake row)

### References

- [Source: `epics.md#Epic 7` § Story 7.7] original AC (verbatim shape; tenant_id and decision_drafts table cut)
- [Source: `architecture.md#Project-Specific Patterns`] § P1, § P4, § P8
- [Source: `architecture.md#Non-Functional Requirements`] NFR-RI7
- [Source: `prd.md#Functional Requirements` FR26]
- [Source: `prd.md#Innovation & Novel Patterns`] Innovation #5
- [Source: `apps/agents/src/agents/intake/document_intelligence.py`] adapter factory + agent function pattern reference
- [Source: `apps/agents/src/agents/adapters/doc_ai/watsonx.py`] watsonx httpx adapter shape reference
- [Source: `apps/agents/src/agents/registry/document_intelligence/agent.yaml`] manifest reference
- [Source: `6-4-reasoning-trace-contract-4-section-schema-enforcement.md`] ReasoningTrace + ContextVar setter
- [Source: `7-1-decision-zone-component-with-tiptap-editor.md`] consumer of this story's output

### Demo verification protocol

Per AC18. If any step fails, the bug is in this story; do not ship until green.

## Dev Agent Record

### Agent Model Used

(claude-opus-4-7 + Amelia persona, bmad-dev-story workflow)

### Debug Log References

### Completion Notes List

### File List

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-05-08 | Story 7.3 drafted. Demo replacement for bank-buyer Story 7.7: Writing agent v1 with WritingLLM Protocol (fixture+watsonx adapters), Jinja-templated prompt with golden inputs (NFR-RI7), DraftedRationale Pydantic with HTML+cited_claims output, supervisor.run_writing hook post-intake (failure does not roll back intake), persisted to intake row, Orchestrate registration. Edit-rate metric and decision_drafts table cut. |
