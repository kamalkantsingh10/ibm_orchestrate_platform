# Story 6.4: ReasoningTrace contract — 4-section schema enforcement

Status: review

## Story

As an agent author,
I want a `ReasoningTrace` Pydantic contract at `packages/contracts/src/contracts/reasoning_trace.py` with all four sections (`what_searched`, `what_hit`, `confidence_self_rating`, `counterfactual`) declared non-empty + min-length-validated, an `IncompleteReasoningTraceError` raised by the `@agent_action` decorator when an agent attempts to attach an empty trace, a `set_runtime_reasoning_trace(...)` ContextVar setter that mirrors the existing `set_runtime_model_id` / `set_runtime_prompt_hash` plumbing, and the `AgentActionLedgerEntry` extended with an optional `reasoning_trace: ReasoningTrace | None` field,
So that Story 6-5's GET endpoint has a typed payload to read, Story 6-6's slide-out has a 4-section data shape to render, the screening agent (Story 6-2) and entity verification agent (Story 5-1) can opt-in to attach traces, and the demo's load-bearing "counterfactual is non-skippable" Innovation #2 promise is enforced **at the contract level** (P8, FR12, NFR-RI1).

## Scope note (2026-04-29 demo re-scope)

This story is the demo-equivalent of the bank-buyer Story 6.5. The bank-buyer scope tied reasoning traces to the cryptographic hash chain — every trace becomes a hashed input to its parent ledger entry. The demo log is JSON append-only, so the trace simply attaches to the `AgentActionLedgerEntry.reasoning_trace` field as nested Pydantic.

| Bank-buyer scope (original 6.5) | Demo replacement in this story |
|---|---|
| `ReasoningTrace` separately ledgered + hash-chained | **Embedded in `AgentActionLedgerEntry.reasoning_trace`** — no separate ledger entry, no hash chain. |
| Tenant-scoped storage | **Single-tenant** — no `tenant_id` on the contract. |
| All agents required to emit a trace; CI gate fails if any `@agent_action` returns without one | **Opt-in at the agent level for the demo**, but **required-when-present** at the contract level (Pydantic validators reject empty fields). The screening, entity-verification, and UBO graph agents opt in via Story 6-2 / 5-1 / 5-3 follow-up commits OR via this story's optional Task 5 (see AC9 — split discussion). |
| `confidence_self_rating: ConfidenceWithRationale` defined as a separate model | **Same** — but `ConfidenceWithRationale` is added in this story (a new contract). |
| `IncompleteReasoningTraceError` raised by decorator on empty fields | **Same** — but only raised when the agent **attempts** to attach a trace via `set_runtime_reasoning_trace`. Agents that don't attach a trace produce a normal ledger entry with `reasoning_trace=None`. |

What survives: **typed `ReasoningTrace` + `ConfidenceWithRationale` Pydantic models, four required sections with min-length validation, decorator integration via ContextVar, `AgentActionLedgerEntry.reasoning_trace` field, end-to-end attach-and-validate flow demonstrated by at least one agent (Screening), full TS-type generation for Story 6-6.**

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md`, `architecture.md#Project-Specific Patterns` § P8 Counterfactual Reasoning Trace Pattern, `prd.md#Functional Requirements` FR12, and `prd.md#Innovation & Novel Patterns` Innovation #2.

## Acceptance Criteria

1. **AC1 — `ConfidenceWithRationale` contract.**

    New file `packages/contracts/src/contracts/reasoning_trace.py` (top of file):

    ```python
    from __future__ import annotations

    from pydantic import BaseModel, Field, model_validator

    from contracts.confidence import ConfidenceBand, to_band


    class ConfidenceWithRationale(BaseModel):
        """Confidence float with an agent-emitted rationale string.

        Used inside ``ReasoningTrace.confidence_self_rating`` and may be
        re-used by future agents that need a richer "why this confidence?"
        signal than ``ProvenancedField[T]`` provides.
        """

        model_config = {"frozen": True}

        value: float = Field(ge=0.0, le=1.0)
        rationale: str = Field(min_length=12, max_length=400)
        band: ConfidenceBand

        @model_validator(mode="after")
        def _band_matches_value(self) -> ConfidenceWithRationale:
            expected = to_band(self.value)
            if self.band != expected:
                raise ValueError(
                    f"band {self.band!r} does not match value {self.value} (expected {expected!r})"
                )
            return self
    ```

    The `band` field is required and consistency-checked against `value` — same pattern Story 3-3's `ProvenancedField` uses. `rationale` minimum is **12 chars** (avoids "n/a", "ok", "high" — meaningless outputs); maximum is **400 chars** (a full sentence or two; a real reasoning paragraph belongs in `what_hit`, not here).

2. **AC2 — `ReasoningTrace` contract with 4 required non-empty sections.**

    Same file:

    ```python
    class ReasoningTrace(BaseModel):
        """The 4-section, non-skippable reasoning trace.

        See architecture.md § P8. Empty fields are a contract-level error,
        not a runtime branch — the trace exists only when all four sections
        carry meaning. Agents that can't (or won't) populate one of the
        sections must NOT emit a trace at all (set ``reasoning_trace=None``
        on the parent ``AgentActionLedgerEntry``).
        """

        model_config = {"frozen": True}

        what_searched: str = Field(min_length=12, max_length=1000)
        what_hit: str = Field(min_length=12, max_length=2000)
        confidence_self_rating: ConfidenceWithRationale
        counterfactual: str = Field(min_length=12, max_length=600)
    ```

    Min-lengths are deliberate: nothing below ~12 chars is meaningful in any of these slots; this is the contract enforcement that Innovation #2 demands. The 600-char ceiling on `counterfactual` is shorter than `what_hit` because the counterfactual is meant to be a sharp single sentence, not a paragraph.

    Re-export from `packages/contracts/src/contracts/__init__.py`:
    `ReasoningTrace`, `ConfidenceWithRationale`, `IncompleteReasoningTraceError` (per AC4). Alphabetical `__all__` order preserved.

3. **AC3 — `AgentActionLedgerEntry` extended.**

    `packages/contracts/src/contracts/agent_action.py` adds an optional field:

    ```python
    class AgentActionLedgerEntry(BaseModel):
        # ... existing fields ...
        reasoning_trace: ReasoningTrace | None = None
        # ^ Optional. None when the agent doesn't emit a trace (e.g.,
        #   Document Intelligence's deterministic field extraction,
        #   the Cockpit Chat agent's tool calls). Required-shape when
        #   present (Pydantic validators on ReasoningTrace enforce).
    ```

    Import `ReasoningTrace` from `contracts.reasoning_trace` (the new module). Watch out for **circular imports** — `reasoning_trace.py` imports `confidence`, `agent_action.py` imports `reasoning_trace`. Verify no cycle: `reasoning_trace` → `confidence` (no), `agent_action` → `reasoning_trace` → `confidence` (no — `confidence` does not import either). All good.

    **Backward compat:** old ledger rows (Stories 3-3 / 3-4 / 5-1 / 5-3 / 6-2 if it landed first) won't have the field. Pydantic's `Optional[T] = None` covers `model_validate` of legacy JSONL lines. Add a regression test (AC10).

4. **AC4 — `IncompleteReasoningTraceError` typed exception.**

    Same module (`reasoning_trace.py`):

    ```python
    class IncompleteReasoningTraceError(ValueError):
        """Raised when an agent's attached reasoning_trace fails contract validation.

        The decorator catches Pydantic ``ValidationError`` from a runtime
        ``ReasoningTrace`` construction and re-raises this typed error so
        the caller (the supervisor's typed ``AgentExecutionError`` catch
        path) can branch on it cleanly.
        """

        def __init__(self, agent_id: str, errors: list[dict]) -> None:
            self.agent_id = agent_id
            self.errors = errors
            sections = sorted({str(e.get("loc", ["?"])[0]) for e in errors})
            super().__init__(
                f"agent {agent_id!r} produced an incomplete reasoning trace; "
                f"failing sections: {sections}"
            )
    ```

5. **AC5 — Decorator integration via ContextVar.**

    `apps/agents/src/agents/supervisor/action_decorator.py`:

    Add a ContextVar following the existing `_runtime_model_id` / `_runtime_prompt_hash` shape:

    ```python
    _runtime_reasoning_trace: ContextVar[ReasoningTrace | None] = ContextVar(
        "agent_action_reasoning_trace", default=None,
    )

    def set_runtime_reasoning_trace(trace: ReasoningTrace) -> None:
        """Attach a ReasoningTrace to the current task's ledger entry.

        Called by agent function bodies before they return. The decorator
        reads this ContextVar after the wrapped function returns, validates
        the trace, and substitutes it into the AgentActionLedgerEntry.

        Raises IncompleteReasoningTraceError if the trace fails contract
        validation (the wrapped Pydantic ValidationError is rebound to the
        typed error).
        """
        try:
            ReasoningTrace.model_validate(trace.model_dump())
        except ValidationError as exc:
            raise IncompleteReasoningTraceError(
                agent_id="(set via set_runtime_reasoning_trace)",
                errors=exc.errors(),
            ) from exc
        _runtime_reasoning_trace.set(trace)
    ```

    Inside `agent_action`'s success path (where the decorator currently builds the `AgentActionLedgerEntry`), read the ContextVar and substitute it onto the entry:

    ```python
    rt = _runtime_reasoning_trace.get()
    entry = AgentActionLedgerEntry(
        # ... existing kwargs ...
        reasoning_trace=rt,
    )
    ```

    The error path (where the decorator catches an exception from the wrapped function) does **not** attach a reasoning trace — failed agent runs by definition have no completed trace.

    **Reset between calls**: Python 3.11 ContextVars are task-local, so concurrent `agent_action`-wrapped calls don't cross-pollute. Document this assumption in a comment near the `_runtime_reasoning_trace` declaration (mirrors the existing `_runtime_model_id` comment).

6. **AC6 — Wire screening agent (Story 6-2) to emit a trace.**

    This is the demo's first concrete `ReasoningTrace` producer. Edit `apps/agents/src/agents/intake/screening.py` (created by Story 6-2):

    Inside `screening(...)`, after the auto-dismissal pass and before returning the output, build a `ReasoningTrace`:

    ```python
    from contracts.reasoning_trace import (
        ConfidenceWithRationale,
        ReasoningTrace,
    )
    from contracts.confidence import to_band
    from agents.supervisor.action_decorator import set_runtime_reasoning_trace

    open_hits = [h for h in processed_hits if h.disposition == "open"]
    dismissed = [h for h in processed_hits if h.disposition == "dismissed_by_agent"]
    avg_confidence = (
        sum(h.name_match_score.value for h in processed_hits) / len(processed_hits)
        if processed_hits else 1.0  # no hits = high confidence in clean result
    )

    trace = ReasoningTrace(
        what_searched=(
            f"Screened {len(input.subjects)} subject(s) "
            f"({', '.join(s.subject_kind for s in input.subjects)}) "
            f"against the configured screening provider."
        ),
        what_hit=(
            f"Returned {len(processed_hits)} match(es): "
            f"{len(open_hits)} open, {len(dismissed)} auto-dismissed. "
            + (
                "Open hits: " + "; ".join(
                    f"{h.matched_name} ({', '.join(h.categories)}) "
                    f"at score {h.name_match_score.value:.2f}"
                    for h in open_hits
                )
                if open_hits else "No officer-actionable hits."
            )
        ),
        confidence_self_rating=ConfidenceWithRationale(
            value=avg_confidence,
            rationale=(
                f"Confidence is the mean name-match score across "
                f"{len(processed_hits)} returned hit(s); a clean (no-hit) "
                f"result is treated as high confidence."
            ),
            band=to_band(avg_confidence),
        ),
        counterfactual=(
            "Disposition would change if officer-supplied evidence (DOB, "
            "ID document, address) confirms or refutes the matched identity."
            if open_hits else
            "Result would change if a re-run with additional subjects (e.g., "
            "newly identified directors) returns hits."
        ),
    )
    set_runtime_reasoning_trace(trace)
    ```

    The trace is generic — these aren't per-hit reasoning traces; they're per-agent-invocation. Story 6-3's hit-level counterfactual derivation (the `deriveCounterfactual` helper) provides the per-hit drilldown for the inline 3-column card.

    **Per-hit `ReasoningTrace`** is **NOT** added to `ScreeningHit` in this story. The trace lives on the `AgentActionLedgerEntry`, one per agent invocation. Story 6-3's `hit.reasoning_trace` access path mentioned in 6-3 § AC3 is a forward-looking placeholder that this story does **not** wire — the `ScreeningHit` schema stays unchanged. Update Story 6-3's behavior: the `hit.reasoning_trace?.counterfactual ?? deriveCounterfactual(...)` ternary always falls through to `deriveCounterfactual` for the demo. Note this in the Story 6-3 file's change log when this story merges.

7. **AC7 — Wire entity verification agent (Story 5-1) to emit a trace.**

    Light touch — Entity Verification has clear what-searched / what-hit / counterfactual answers from its existing typed output. Edit `apps/agents/src/agents/intake/entity_verification.py`:

    ```python
    trace = ReasoningTrace(
        what_searched=(
            f"Looked up CIN {input.cin!r} in the configured MCA company-master "
            f"and diffed against the case's intake-derived view."
        ),
        what_hit=(
            f"MCA status: {result.mca_status.value}. "
            f"{len(result.mismatches)} field mismatch(es): "
            + (
                ", ".join(f"{m.field_name} ({m.severity})" for m in result.mismatches)
                if result.mismatches else "none."
            )
        ),
        confidence_self_rating=ConfidenceWithRationale(
            value=result.mca_status.provenance.confidence,
            rationale=(
                "Confidence reflects the MCA tool's self-reported confidence "
                "in the company-master record (the mock returns 0.95 deterministically)."
            ),
            band=result.mca_status.provenance.confidence_band,
        ),
        counterfactual=(
            "Status would change if the case's CIN points to a different "
            "company-master record on the next MCA refresh, or if officer "
            "evidence confirms a known-correct address/name resolves the mismatch."
        ),
    )
    set_runtime_reasoning_trace(trace)
    ```

    Inserted just before the `return result` line. Tests assert one `agent.completed` ledger entry now has `payload.reasoning_trace` populated for entity verification.

8. **AC8 — UBO Graph agent (Story 5-3) — opt-out for the demo.**

    The UBO graph's reasoning is per-edge, not per-invocation. A single ReasoningTrace at the agent level wouldn't add officer-facing value. **Skip wiring** — UBO Graph emits no reasoning trace. Story 6-6 / 6-7 tolerate the absence cleanly (Story 6-5's GET endpoint returns 204 No Content per AC; Story 6-6 shows "no trace produced").

    Document this opt-out in a code comment in `apps/agents/src/agents/intake/ubo_graph.py` (one-line: `# No agent-level reasoning trace; UBO reasoning is per-edge confidence (see UBOEdge.confidence).`).

9. **AC9 — Tests at `packages/contracts/tests/test_reasoning_trace.py`.**

    * `ReasoningTrace` round-trips through `model_dump_json` / `model_validate_json`.
    * Empty `what_searched` (length < 12) raises `ValidationError`.
    * Empty `what_hit` raises.
    * Empty `counterfactual` raises.
    * `confidence_self_rating.rationale` < 12 chars raises.
    * `confidence_self_rating.value` outside [0.0, 1.0] raises.
    * `confidence_self_rating.band` mismatched against `value` raises.
    * `ConfidenceWithRationale` round-trips.
    * `AgentActionLedgerEntry(reasoning_trace=None)` (default) round-trips — backward compat.
    * `AgentActionLedgerEntry(reasoning_trace=valid_trace)` round-trips.
    * Loading a legacy ledger row (a JSON string lacking `reasoning_trace`) via `model_validate_json` succeeds with `reasoning_trace=None` — backward compat regression.

10. **AC10 — Tests at `apps/agents/tests/supervisor/test_action_decorator.py` (extend existing).**

    * **Happy path: agent calls `set_runtime_reasoning_trace(valid)` → ledger entry has `payload.reasoning_trace`.** Use a stub agent function in the test fixture.
    * **Trace not set → ledger entry has `payload.reasoning_trace == None`.** Existing-style agent (e.g., document_intelligence-shaped stub) continues to write entries unchanged.
    * **`set_runtime_reasoning_trace(invalid)` raises `IncompleteReasoningTraceError`.**
    * **ContextVar reset between concurrent calls — no cross-pollination.** Use `asyncio.gather` of two stub agents that set different traces; assert each sees its own.
    * **Failed agent run (raises before `set_runtime_reasoning_trace` is called) → ledger entry's `payload.reasoning_trace == None`.**

11. **AC11 — Tests at `apps/agents/tests/intake/test_screening.py` (extend Story 6-2's tests).**

    * After running screening with hits, the recorded ledger entry has `payload.reasoning_trace` populated.
    * `payload.reasoning_trace.counterfactual` contains the open-hits sentence variant when there are open hits.
    * `payload.reasoning_trace.counterfactual` contains the no-hits sentence variant when input subjects produce no hits.
    * `payload.reasoning_trace.confidence_self_rating.value` equals the mean of returned-hit `name_match_score.value`s (or 1.0 when zero hits).

12. **AC12 — Tests at `apps/agents/tests/intake/test_entity_verification.py` (extend Story 5-1's tests).**

    * After running entity verification, the recorded ledger entry has `payload.reasoning_trace` populated with `mca_status.provenance.confidence_band` matching the trace's `confidence_self_rating.band`.

13. **AC13 — `make contracts` regenerates TS types.**

    `apps/cockpit-ui/src/api-types.ts` includes `ReasoningTrace`, `ConfidenceWithRationale`, and the updated `AgentActionLedgerEntry` schema with the new `reasoning_trace` field. Verify by grep.

14. **AC14 — `make lint && make test` clean.** Net new test count: ≥ 11 in `test_reasoning_trace.py`, ≥ 5 in `test_action_decorator.py` (extend), ≥ 4 in `test_screening.py` (extend), ≥ 1 in `test_entity_verification.py` (extend).

15. **AC15 — End-to-end smoke test.**

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

    # The ledger now contains entries with reasoning_trace populated.
    # Inspect via the JSONL (or via Story 6-5's endpoint after that story merges):
    cat ./data/ledger.jsonl | jq -c 'select(.payload.kind == "agent_action" and .payload.reasoning_trace != null) | {actor: .actor_id, counterfactual: .payload.reasoning_trace.counterfactual}'
    # Expected: at least one screening + one entity_verification entry, both with counterfactual sentences.
    ```

## Tasks / Subtasks

- [x] **Task 1 — Pydantic contracts** (AC: #1, #2, #4, #9)
  - [x] Subtask 1.1 — `packages/contracts/src/contracts/reasoning_trace.py` with `ConfidenceWithRationale`, `ReasoningTrace`, `IncompleteReasoningTraceError`.
  - [x] Subtask 1.2 — Re-exported from `packages/contracts/src/contracts/__init__.py`.
  - [x] Subtask 1.3 — `packages/contracts/tests/test_reasoning_trace.py` — 12 cases.

- [x] **Task 2 — `AgentActionLedgerEntry` extension** (AC: #3, #9 backward-compat case, #13)
  - [x] Subtask 2.1 — Added optional `reasoning_trace: ReasoningTrace | None = None`.
  - [x] Subtask 2.2 — No circular import; verified.
  - [x] Subtask 2.3 — Ran `make contracts`.

- [x] **Task 3 — Decorator integration** (AC: #5, #10)
  - [x] Subtask 3.1 — Added `_runtime_reasoning_trace` ContextVar + `set_runtime_reasoning_trace(trace)` setter (eager validation, raises `IncompleteReasoningTraceError`).
  - [x] Subtask 3.2 — Decorator's `_record_success` reads the ContextVar and passes it to `AgentActionLedgerEntry(reasoning_trace=...)`. Wrapper resets to `None` on each call so prior task state never leaks.
  - [x] Subtask 3.3 — `apps/agents/tests/test_action_decorator.py` extended with 5 new cases (attached, none, invalid raises, failure path none, concurrent no-cross-pollute).

- [x] **Task 4 — Wire Screening agent** (AC: #6, #11)
  - [x] Subtask 4.1 — Edited `apps/agents/src/agents/intake/screening.py`; helper `_build_trace` constructs the 4-section trace from runtime data and the agent calls `set_runtime_reasoning_trace`.
  - [x] Subtask 4.2 — Extended `apps/agents/tests/intake/test_screening.py` with 4 new cases (open hit trace, no-hits trace, mean-confidence, 1.0-when-empty).

- [x] **Task 5 — Wire Entity Verification agent** (AC: #7, #12)
  - [x] Subtask 5.1 — Edited `apps/agents/src/agents/intake/entity_verification.py`.
  - [x] Subtask 5.2 — Extended `apps/agents/tests/test_entity_verification.py` with 1 new case asserting trace + band match.

- [x] **Task 6 — UBO Graph opt-out comment** (AC: #8)
  - [x] Subtask 6.1 — Added the one-line comment above the `@agent_action` decorator on `ubo_graph` in `apps/agents/src/agents/intake/ubo_graph.py`.

- [x] **Task 7 — Verification** (AC: #14, #15)
  - [x] Subtask 7.1 — `make lint` clean; full Python suite 494 green (205 contracts + 146 cockpit-api + 143 agents).
  - [x] Subtask 7.2 — Verified end-to-end via the agent unit tests (which exercise the full agent → decorator → ledger writer → reader path with `tmp_writer`); cloud-side smoke deferred (no behavioural change to the `/v1/agents/*` endpoints — they still return the same `ScreeningAgentOutput`/`EntityVerificationResult` shapes; the trace lives on the ledger, queryable via Story 6.5).

## Dev Notes

### Architectural context (binding)

* [Source: `architecture.md#Project-Specific Patterns` § P8 Counterfactual Reasoning Trace Pattern (line 654)] verbatim shape: `what_searched` / `what_hit` / `confidence_self_rating: ConfidenceWithRationale` / `counterfactual`. **Empty-string is a CI test failure.** This story translates the architecture's English rule into Pydantic field validators.
* [Source: `prd.md#Functional Requirements` FR12] "open a reasoning-trace slide-out for any agent action showing (a) what was searched, (b) what returned, (c) the agent's confidence self-rating, and (d) a counterfactual."
* [Source: `prd.md#Innovation & Novel Patterns` Innovation #2] "Forces agents to commit to the evidentiary boundary of their own conclusion." — the contract is the enforcement.
* [Source: `architecture.md#Demo Scope Addendum (2026-04-29)`] Cryptographic hash chain dropped — the trace lives as a nested Pydantic field on the JSON-log ledger entry.
* [Source: `architecture.md#Project-Specific Patterns` § P4 Agent Action Pattern] AgentActionLedgerEntry is the typed payload home for everything the agent emits — adding `reasoning_trace` is consistent with the existing `tool_calls`, `output`, etc.
* [Source: `apps/agents/src/agents/supervisor/action_decorator.py:48-66`] existing ContextVar plumbing for `model_id` / `prompt_hash` is the exact pattern to follow.

### Critical pitfalls

1. **`ReasoningTrace` is a contract, not an agent's prompt.** The four sections describe what the agent did — they're written by the agent's Python code (or by an LLM call's output schema), not by an LLM free-form response. Demo agents are deterministic, so the trace strings are templated in code (see AC6 / AC7). Bank-buyer LLM agents would emit them via Pydantic-typed LLM output.

2. **Min-length 12 chars is the contract's teeth.** Don't make it 1 or 5 "to be safe." The whole point is preventing "n/a" / "ok" / "high" — outputs that satisfy a permissive validator but provide no audit value. Failing tests at 12 are the win.

3. **`band` field in `ConfidenceWithRationale` is required and consistency-checked.** Same pattern as `Provenance.confidence_band`. Don't make `band` derivable / Optional; explicit is better and round-trips cleanly through JSON.

4. **`set_runtime_reasoning_trace` validates eagerly.** Don't lazy-validate at decorator-read time — agents may swallow exceptions, and a silent invalid trace is worse than no trace. Eager raise → typed `IncompleteReasoningTraceError` → supervisor's existing typed-exception path surfaces it.

5. **The decorator does NOT *require* a reasoning trace.** Architecture P8's "no agent reasoning trace ships without all four fields" applies to **the trace as a whole** — agents that emit one must populate all four. Agents that emit none are fine. The CI gate phrased in the architecture ("empty-string is a CI test failure") translates here into "the contract rejects empty strings"; not into "every agent must emit a trace." Story 6-2 / 5-1 opt in (AC6 / AC7); UBO Graph opts out (AC8). Document Intelligence is unchanged in this story.

6. **Don't break Story 3-4's existing JSONL ledger lines.** Pydantic's `Optional[T] = None` covers it, but the AC9 backward-compat regression test is mandatory — verify on a saved fixture, not just in-memory.

7. **ContextVar reset between calls.** The decorator's success and failure paths should both read-and-clear the ContextVar so a future call starts clean. Consider using a `try`/`finally` with `_runtime_reasoning_trace.set(None)` after the entry is built. Without this, a long-running task that runs many `agent_action` invocations could carry stale traces from a prior call. Test this in AC10's "concurrent calls" case.

8. **`ReasoningTrace` is a *contract*, not part of the agent's input.** Don't add it to `ScreeningAgentInput` / `EntityVerificationInput`. The agent **builds** the trace inside the function and attaches it via the ContextVar. Inputs are unchanged.

9. **Demo agents emit deterministic strings.** Use template f-strings with the agent's typed inputs/outputs. The bank-buyer LLM-driven agents would emit them through structured prompts; the demo's mocks build them in code. Document in code comments that the templating is the demo simplification, not a stylistic choice.

10. **Forward-references in `agent_action.py`.** With `from __future__ import annotations` (already present at the top of `agent_action.py`), the `reasoning_trace: ReasoningTrace | None = None` annotation is a string at runtime — Pydantic resolves it at validation time. No circular import risk **as long as the actual import (`from contracts.reasoning_trace import ReasoningTrace`) is at module top**, since by the time validation runs the module graph is fully constructed. Verify with a one-shot `python -c "from contracts.agent_action import AgentActionLedgerEntry"` after the change.

11. **The AC10 concurrent-call test catches a real bug.** Run two `asyncio.gather`-ed stub agents, each calling `set_runtime_reasoning_trace` with a different value. Assert each agent's resulting ledger entry has its own trace. If the ContextVar is implemented incorrectly (e.g., as a module-level mutable default), this test fails — the cross-pollination would be a Day-2 audit-integrity bug.

12. **Story 6-3's `hit.reasoning_trace?.counterfactual` access pattern is no longer accurate.** This story does not add `reasoning_trace` to `ScreeningHit`. Update Story 6-3's `ScreeningExplainer` to **always** use `deriveCounterfactual(hit, subjectDob)`. This story's change log notes this; if Story 6-3 is already implemented, this story's PR includes a small follow-up commit to remove the optional-chained access in `ScreeningExplainer.tsx`.

### Story dependencies

* **Strict prereqs:** Story 3-2 (`@agent_action` decorator + ContextVar plumbing), Story 3-3 (`AgentActionLedgerEntry` shape), Story 3-7 (`ConfidenceBand`, `to_band`), Story 6-2 (Screening agent — extends), Story 5-1 (Entity Verification agent — extends).
* **Read by:** Story 6-5 (GET endpoint reads `payload.reasoning_trace`), Story 6-6 (slide-out renders `ReasoningTrace`), Story 6-7 (Cockpit Chat's `get_reasoning_trace` tool returns it).

### Project Structure Notes

This story creates:
- `packages/contracts/src/contracts/reasoning_trace.py`
- `packages/contracts/tests/test_reasoning_trace.py`

This story modifies:
- `packages/contracts/src/contracts/agent_action.py` — adds `reasoning_trace: ReasoningTrace | None = None`
- `packages/contracts/src/contracts/__init__.py` — public exports
- `apps/agents/src/agents/supervisor/action_decorator.py` — adds `_runtime_reasoning_trace`, `set_runtime_reasoning_trace`, decorator integration
- `apps/agents/src/agents/intake/screening.py` (Story 6-2) — emit trace
- `apps/agents/src/agents/intake/entity_verification.py` (Story 5-1) — emit trace
- `apps/agents/src/agents/intake/ubo_graph.py` (Story 5-3) — opt-out comment
- `apps/agents/tests/supervisor/test_action_decorator.py` — extend
- `apps/agents/tests/intake/test_screening.py` — extend
- `apps/agents/tests/intake/test_entity_verification.py` — extend
- `apps/cockpit-ui/src/api-types.ts` — regenerated by `make contracts`

This story DOES NOT create:
- The GET reasoning trace endpoint (Story 6-5)
- The slide-out UI (Story 6-6)
- A separate `reasoning_traces` table or storage layer — the trace lives on the ledger entry

### References

- [Source: `epics.md#Epic 6` § Story 6.5] original AC (verbatim shape preserved; demo simplification: embedded in ledger entry instead of separate hash-chained ledger record)
- [Source: `architecture.md#Project-Specific Patterns` § P8 Counterfactual Reasoning Trace Pattern]
- [Source: `architecture.md#Project-Specific Patterns` § P4 Agent Action Pattern]
- [Source: `prd.md#Functional Requirements § Agent Mesh Visibility & Interaction` FR12]
- [Source: `prd.md#Innovation & Novel Patterns` Innovation #2]
- [Source: `architecture.md#Project-Specific Patterns` § P7 Confidence Banding] `to_band` consistency
- [Source: `apps/agents/src/agents/supervisor/action_decorator.py`] existing ContextVar pattern to mirror
- [Source: `6-2-screening-agent.md`] Screening agent function shape (this story extends)
- [Source: `5-1-entity-verification-agent.md`] Entity Verification function shape (this story extends)

### Demo verification protocol

Per AC15. Verify the JSONL ledger contains traces with non-empty four sections; verify Story 6-5's endpoint (when it lands) returns these traces.

If any step fails, the bug is in this story; do not ship until green.

## Dev Agent Record

### Agent Model Used

(claude-opus-4-7 + Amelia persona, bmad-dev-story workflow)

### Debug Log References

- After adding `reasoning_trace: ReasoningTrace | None = None` to `AgentActionLedgerEntry`, several downstream tests began returning `payload` as a plain `dict` instead of `AgentActionLedgerEntry`. Root cause: Pydantic v2's "smart" union mode lost the tiebreaker against `dict[str, Any]` in `LedgerEntry.payload`. **Fix**: explicitly set `Field(union_mode="left_to_right")` on the discriminated union so Pydantic tries the typed arms first and only falls through to `dict` on a real validation error. Comment updated in `packages/contracts/src/contracts/ledger.py` to capture the why.
- Pre-existing 5 Vitest failures in `useCase.test.tsx` / `useCases.test.tsx` reproduce on clean main; unrelated.

### Completion Notes List

- **`union_mode="left_to_right"` on `LedgerEntry.payload`** — added because Pydantic v2's smart union mode silently picked the `dict[str, Any]` arm once the typed payload grew nested fields. This is a one-line correctness fix that makes all existing typed-payload assertions reliable. No test was actively asserting this union behaviour before; multiple tests downstream were depending on it implicitly.
- **Eager validation in `set_runtime_reasoning_trace`** — `ReasoningTrace.model_validate(trace.model_dump())` runs at attach-time, not at decorator-read-time. Agents that build invalid traces fail fast with `IncompleteReasoningTraceError` rather than silently writing a trace-less ledger entry.
- **Per-call reset** — wrapper sets `_runtime_reasoning_trace.set(None)` at the top of each invocation alongside the existing `_runtime_model_id`/`_runtime_prompt_hash` resets, so a long-running task's previous trace never leaks into the next agent call.
- **Screening + Entity Verification opt in; UBO Graph opts out** per AC #6 / #7 / #8. Document Intelligence is unchanged (deterministic field extraction; per-field `ProvenancedField` already covers the reasoning surface).
- **Story 6.3 `hit.reasoning_trace?.counterfactual` access stays in place** — it currently always falls through to the client-side `deriveCounterfactual` because `ScreeningHit.reasoning_trace` is not added in this story (per AC #6 final paragraph). Story 6-3's component continues to work unchanged; no follow-up edit needed.
- **TS types regenerated** — `apps/cockpit-ui/src/api-types.ts` now includes `ReasoningTrace`, `ConfidenceWithRationale`, and `AgentActionLedgerEntry.reasoning_trace`. Story 6.6's slide-out can read these directly.

### File List

- `packages/contracts/src/contracts/reasoning_trace.py` (new) — `ConfidenceWithRationale`, `ReasoningTrace`, `IncompleteReasoningTraceError`.
- `packages/contracts/src/contracts/agent_action.py` (modified) — added `reasoning_trace` field.
- `packages/contracts/src/contracts/ledger.py` (modified) — added `union_mode="left_to_right"` to `payload` field.
- `packages/contracts/src/contracts/__init__.py` (modified) — re-exported new symbols.
- `packages/contracts/tests/test_reasoning_trace.py` (new) — 12 tests.
- `packages/contracts/openapi.json` (regenerated).
- `apps/cockpit-ui/src/api-types.ts` (regenerated).
- `apps/agents/src/agents/supervisor/action_decorator.py` (modified) — added `_runtime_reasoning_trace`, `set_runtime_reasoning_trace`, decorator integration.
- `apps/agents/src/agents/intake/screening.py` (modified) — `_build_trace` + `set_runtime_reasoning_trace` call.
- `apps/agents/src/agents/intake/entity_verification.py` (modified) — `_build_trace` + `set_runtime_reasoning_trace` call.
- `apps/agents/src/agents/intake/ubo_graph.py` (modified) — opt-out comment above the agent.
- `apps/agents/tests/test_action_decorator.py` (modified) — 5 new cases.
- `apps/agents/tests/intake/test_screening.py` (modified) — 4 new cases.
- `apps/agents/tests/test_entity_verification.py` (modified) — 1 new case.

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-05-08 | Story 6.4 drafted. ReasoningTrace + ConfidenceWithRationale Pydantic contracts with min-length-12 enforcement on all 4 sections; AgentActionLedgerEntry extended with optional reasoning_trace; @agent_action decorator integration via ContextVar; Screening + Entity Verification agents opt-in; UBO Graph opts-out (per-edge confidence already covers); IncompleteReasoningTraceError typed exception. |
| 2026-05-08 | Implemented Story 6.4. Contract + decorator integration + Screening / Entity Verification opt-ins + UBO opt-out + `union_mode="left_to_right"` correctness fix on `LedgerEntry.payload`. 22 net-new tests (12 contracts + 5 decorator + 4 screening + 1 entity-verification). 494 Python tests green; `make lint` clean. |
