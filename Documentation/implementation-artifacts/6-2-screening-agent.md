# Story 6.2: Screening agent

Status: review

## Story

As the platform,
I want a Screening agent at `apps/agents/src/agents/intake/screening.py` that — given a case — calls the mock `ScreeningAdapter` (Story 6-1) for the entity + every director from MCA + every UBO node with ≥ 10% ownership, auto-dismisses low-confidence/low-match hits with a typed rationale, surfaces remaining hits as `ScreeningHit`s, exposes itself as the fourth fan-out node in `INTAKE_AGENTS`, and writes one `agent.completed` ledger entry per `@agent_action`,
So that the Vora demo's amber Screening hit reaches the Case Canvas alongside Document Intelligence / Entity Verification / UBO Graph results, the supervisor's intake fan-out covers all five MVP intake agents (FR18, NFR-RI1 supervisor/collaborator pattern, P3 provenance everywhere, P4 ledger per invocation), and Story 6-3's ScreeningExplainer has typed data to render.

## Scope note (2026-04-29 demo re-scope)

This story is the demo-equivalent of the bank-buyer Story 6.3. The bank-buyer scope assumed real MCA + GST + ComplyAdvantage data; the demo runs against fixtures end-to-end.

| Bank-buyer scope (original 6.3) | Demo replacement in this story |
|---|---|
| Calls `ScreeningAdapter` configured per tenant (`SCREENING_PROVIDER` env) — mock OR ComplyAdvantage | **Mock-only** — `get_default_screening_adapter()` resolves to `MockScreeningAdapter` (Story 6-1). |
| Tenant-scoped (`tenant_id` keyword arg on every fn) | **Single-tenant demo** — no `tenant_id`. Mirrors Stories 3.4 / 3.5 / 5.1. |
| Subjects: entity + every director + every UBO ≥ 10% ownership | **Same logic** — but director list comes from MCA mock (Story 5-1's `MCACompanyMaster.directors`) and UBO list from Story 5-3's `UBOGraph` (entity-kind nodes filtered by ownership_pct ≥ 0.10). |
| Auto-dismiss low-match (< 0.5) hits | **Same threshold (`< 0.50`).** Auto-dismissal uses the typed `dismissed_by_agent` disposition with a rationale string (not a separate audit log). Officers can re-include later — but that re-inclusion is bank-buyer scope (Story 6.4 mentions "re-run with different parameters"; cut from demo's 6-3). |
| `agent.completed` ledger entry includes hash chain + Ed25519 signature | **JSON append-only log entry only.** Mirrors Story 3-1 and existing supervisor calls. |
| Failure modes: `ScreeningTemporaryError` → retry; `ScreeningPermanentError` → block | **Mock has no failure modes** in the demo path. Logic still wraps the call with the typed-error catch so a future real adapter slots in cleanly — supervisor sets case to `escalated` on any `AgentExecutionError`. |

What survives: **typed `ScreeningAgentInput` / `ScreeningAgentOutput`, `@agent_action` ledger entry per invocation, supervisor fan-out integration with `requires` predicate, ADK registry entry (manifest + OpenAPI tool spec), `agent_slug='screening'` matching `AgentSlug.SCREENING`, mock-deterministic results pinned to Vora / Shree / Ananya.**

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md` § Stories simplified, `architecture.md#Demo Scope Addendum (2026-04-29)`, `epics.md#Epic 6` § Story 6.3.

## Acceptance Criteria

1. **AC1 — Pydantic input/output contracts in `packages/contracts/src/contracts/screening.py` (extend Story 6-1).**

    Add to the same module Story 6-1 created:

    ```python
    class ScreeningAgentInput(BaseModel):
        model_config = {"frozen": True}
        case_id: CaseId
        # Subjects are built by the supervisor from upstream agent outputs
        # (Entity Verification + UBO Graph). The agent receives them ready-built.
        subjects: list[ScreeningSubject] = Field(min_length=1, max_length=50)


    class ScreeningAgentOutput(BaseModel):
        model_config = {"frozen": True}
        case_id: CaseId
        hits: list[ScreeningHit] = Field(default_factory=list)
        # ^ ALL hits, including dismissed_by_agent — UI shows officer the
        #   dismissed ones in a collapsed "auto-dismissed" group.
        subjects_screened: int = Field(ge=1)
        # ^ count of subjects passed in (not unique hits).
    ```

    Re-export both from `packages/contracts/src/contracts/__init__.py`'s `__all__`.

2. **AC2 — Agent function at `apps/agents/src/agents/intake/screening.py`.**

    ```python
    from contracts.screening import (
        HitDisposition,
        ScreeningAdapter,
        ScreeningAgentInput,
        ScreeningAgentOutput,
        ScreeningHit,
        ScreeningPermanentError,
        ScreeningRequest,
        ScreeningTemporaryError,
    )
    from agents.adapters.screening import get_default_screening_adapter
    from agents.supervisor.action_decorator import agent_action


    _DISMISS_SCORE_THRESHOLD = 0.50
    _DISMISS_DOB_MUST_MATCH_BELOW = 0.65
    # ^ if name_match_score < 0.65 AND DOBs differ, auto-dismiss.


    @agent_action(
        agent_id="screening",
        model_id="deterministic",          # mock adapter is rule-based, not LLM-driven
        prompt_template_id=None,
    )
    async def screening(
        input: ScreeningAgentInput,
        *,
        adapter: ScreeningAdapter | None = None,
    ) -> ScreeningAgentOutput: ...
    ```

    Logic:
    1. Resolve `adapter = adapter or get_default_screening_adapter()`.
    2. Build a `ScreeningRequest(case_id=input.case_id, subjects=input.subjects)`.
    3. Call `raw_hits = await adapter.screen(req)`. Wrap in try/except for `ScreeningTemporaryError` / `ScreeningPermanentError`:
        * Both raise — let `@agent_action` catch and convert to `AgentExecutionError`. The decorator logs the failed entry; the supervisor (Story 3-5 / 5-1) sets case to `escalated`. **Mock raises neither in the demo path** — the `try/except` is for future-proofing.
    4. Auto-dismissal pass — for each hit, decide `disposition`:
        * If `name_match_score.value < _DISMISS_SCORE_THRESHOLD` → `disposition="dismissed_by_agent"`, `dismissal_rationale=f"low name match ({score:.2f})"`.
        * Else if `name_match_score.value < _DISMISS_DOB_MUST_MATCH_BELOW` AND the subject DOB ≠ hit DOB AND both DOBs are non-None → `disposition="dismissed_by_agent"`, `dismissal_rationale=f"medium-low name match ({score:.2f}) and DOB differs"`.
        * Else `disposition="open"` — officer review.
        * Build a new `ScreeningHit` via `model_copy(update={"disposition": ..., "dismissal_rationale": ...})` (frozen models).
    5. Return `ScreeningAgentOutput(case_id=input.case_id, hits=processed_hits, subjects_screened=len(input.subjects))`.

    `adapter` is an explicit dependency for testability — supervisor doesn't pass it; the agent resolves the default at call time. Tests inject a stub adapter directly.

3. **AC3 — Supervisor fan-out integration in `apps/agents/src/agents/supervisor/case_supervisor.py`.**

    Add the fourth `IntakeAgentSpec` to the `INTAKE_AGENTS` tuple (the existing comment `# Epics 5–6 will append: screening, risk_scoring` is the marker; replace with the actual entry):

    ```python
    INTAKE_AGENTS: Final[tuple[IntakeAgentSpec, ...]] = (
        IntakeAgentSpec(name="document_intelligence", invoke=_invoke_document_intelligence, requires=_has_document_refs),
        IntakeAgentSpec(name="entity_verification",  invoke=_invoke_entity_verification,  requires=_has_cin),
        IntakeAgentSpec(name="ubo_graph",            invoke=_invoke_ubo_graph,            requires=_has_cin),
        IntakeAgentSpec(name="screening",            invoke=_invoke_screening,            requires=_has_screenable_subjects),
        # Risk scoring (Story 5-6) follows screening — already in flight.
    )
    ```

    Add `_has_screenable_subjects(case: Case) -> bool` predicate:
    * Returns `True` if the case has either an entity (always present — every case has a `customer_metadata.customer_name`) OR any directors / UBOs that the upstream agents will surface. Since the entity itself is screenable, this returns `True` for every case in the demo. Document this in a code comment: "Demo always has a screenable entity; predicate is pro forma. A real platform would predicate on intake completeness."

4. **AC4 — Subject builder in the supervisor (`_build_screening_subjects`).**

    The supervisor reads upstream typed outputs from `IntakeContext.outputs` to assemble subjects:

    ```python
    def _build_screening_subjects(
        case: Case,
        entity_verification_output: EntityVerificationResult | None,
        ubo_graph: UBOGraph | None,
    ) -> list[ScreeningSubject]: ...
    ```

    Construction rules:
    * **Entity subject** (always emitted): `ScreeningSubject(subject_kind="entity", subject_id=case.customer_metadata.customer_id or case.id, full_name=case.customer_metadata.customer_name, date_of_birth=None, identifiers={"cin": <case.customer_metadata.extra.registration_number>} if present)`. The `subject_id` matches what Story 6-1's fixture uses for Ananya (which is an individual case; her customer_id from seed_dev.py).
    * **Director subjects** (only if Entity Verification ran successfully): for each director in MCA's company master (read from the seed fixtures; the typed `EntityVerificationResult` doesn't carry the full director list — see Pitfall #4 below for the resolution path). Director DOB and identifiers come from MCA. Subject_id matches what Story 6-1 fixtures use for Vora's Patel R.
    * **UBO subjects** (only if UBO Graph ran successfully): for each `UBOPersonNode` whose at-least-one outgoing edge has `ownership_pct >= 0.10`, emit a subject with `subject_id=node.id`, `full_name=node.name`, `date_of_birth=node.date_of_birth if available else None`. Skip `UBOEntityNode`s — they're already covered by the entity subject (or by recursive ownership, which the demo doesn't model).

    Skip directors / UBOs already covered as the entity subject (compare `subject_id` to entity.subject_id; dedupe).

    `_invoke_screening(ctx: IntakeContext)` orchestration:

    ```python
    async def _invoke_screening(ctx: IntakeContext) -> ScreeningAgentOutput:
        ev_out = ctx.outputs.get("entity_verification")
        ubo_out = ctx.outputs.get("ubo_graph")
        subjects = _build_screening_subjects(ctx.case, ev_out, ubo_out)
        return await screening(ScreeningAgentInput(case_id=ctx.case.id, subjects=subjects))
    ```

5. **AC5 — Two-pass evidence_ids back-fill in supervisor (mirrors Story 5-1 § AC8).**

    After the screening agent completes and the ledger entry is written, the supervisor needs to back-fill `name_match_score.provenance.evidence_ids` on every hit with the ledger entry's ID — the same two-pass dance Document Intelligence / Entity Verification / UBO Graph already do.

    Add `_fill_evidence_ids_screening(output: ScreeningAgentOutput, ledger_entry_id: LedgerEntryId) -> ScreeningAgentOutput` helper near the existing `_fill_evidence_ids_*` family.

    The supervisor calls it after the agent's ledger entry is written; the back-filled output is what gets persisted to the case's intake row.

6. **AC6 — Persist screening hits to the case intake row.**

    The cockpit-api stores intake-time agent outputs in the `intake` table (see `apps/cockpit-api/src/cockpit_api/repositories/intake_repo.py`, used by Story 5-1). Extend the table's schema or row payload to carry screening hits:

    * Inspect `apps/cockpit-api/src/cockpit_api/repositories/intake_repo.py` and the underlying SQLAlchemy model (most likely `apps/cockpit-api/src/cockpit_api/db/models.py` or similar).
    * Add an `screening_hits: list[ScreeningHit]` column or JSON-column field. If the row's payload is a single JSON blob, add the field to that blob's typed shape.
    * Migration: if SQLAlchemy auto-creates the SQLite schema (per Demo Scope Addendum), no Alembic migration is needed; otherwise add a no-op migration matching existing patterns.

    Keep the change additive — Stories 5-1 / 3-4 already wrote rows; old rows must continue to load (default to `[]` if absent).

7. **AC7 — Cockpit-api router exposes screening hits via `GET /v1/cases/{case_id}/intake`.**

    Story 5-1 / 5-3 / 3-4 made `GET /v1/cases/{case_id}/intake` return `{document_intelligence, entity_verification, ubo_graph}` (or similar). Extend the response to include `screening: ScreeningAgentOutput | None` (`None` if screening hasn't run yet).

    Confirm the route file (`apps/cockpit-api/src/cockpit_api/routers/cases.py` likely) and amend its response model. Pydantic's `model_validate` covers backward compat for old intake rows missing the field.

8. **AC8 — TS types regenerate from contract changes.**

    `make contracts` (or the equivalent `openapi-typescript` invocation) regenerates `apps/cockpit-ui/src/api-types.ts`. `ScreeningAgentInput`, `ScreeningAgentOutput`, `ScreeningHit`, `ScreeningSubject` etc. all surface in the TS types. Verify by grepping `api-types.ts` after regeneration.

    Story 6-3 depends on these types; do not ship 6-2 with `make contracts` un-run.

9. **AC9 — Orchestrate ADK registry entry at `apps/agents/src/agents/registry/screening/`.**

    Mirror the layout of `apps/agents/src/agents/registry/document_intelligence/` and `entity_verification/`:

    * `agent.yaml` — `spec_version: v1`, `kind: native`, `name: screening`, `description: "Screens entity + directors + UBOs against sanctions/PEP/adverse-media lists. Returns hits with name_match_score and source list."`, `llm: groq/openai/gpt-oss-120b` (matches doc-intel + entity-verification), `style: default`, `instructions:` (3-step prose: identify case_id, call `run_screening` once, summarize hits — top categories, top match scores, count of auto-dismissed), `tools: [run_screening]`, `collaborators: []`.
    * `openapi.yaml` — exposes `POST /v1/agents/screening/run` with `ScreeningAgentInput` request body and `ScreeningAgentOutput` response. `operationId: run_screening`. `servers:` block uses the same ngrok-tunneled URL placeholder pattern (`http://host.docker.internal:8000` swap; `make tunnel-sync` updates).
    * Cockpit-api router for `POST /v1/agents/screening/run` lives in `apps/cockpit-api/src/cockpit_api/routers/agents.py` (existing file already houses `/v1/agents/document_intelligence/extract`). Adds an `async def run_screening(...)` endpoint that calls the agent function with the request body and returns the typed output. The endpoint **does not** call `_invoke_screening` (the supervisor's helper) — it calls the agent function directly so cloud Orchestrate can drive it via the agent.yaml tool definition.

    The agent is **also** invoked by the supervisor (`_invoke_screening`) — same Python function, two callers (cloud Orchestrate via OpenAPI tool route, and the local supervisor's intake fan-out). Both write a single `agent.completed` ledger entry per call — `@agent_action` handles that.

10. **AC10 — Tests at `apps/agents/tests/intake/test_screening.py`.**

    Cover:
    * **Happy path: stub adapter returns 1 hit at score 0.85** — agent returns it with `disposition="open"`. `subjects_screened` matches input length.
    * **Auto-dismiss: stub returns hit at score 0.40** — `disposition="dismissed_by_agent"`, `dismissal_rationale` includes `"low name match (0.40)"`.
    * **Auto-dismiss: stub returns hit at score 0.55, DOBs differ** — `disposition="dismissed_by_agent"`, rationale mentions DOB.
    * **NOT auto-dismissed: stub returns hit at score 0.55, DOB matches** — `disposition="open"`.
    * **Adapter raises `ScreeningTemporaryError` → `AgentExecutionError`** — assert the typed exception bubbles via the decorator.
    * **`adapter=None` resolves via `get_default_screening_adapter`** — monkeypatch `SCREENING_PROVIDER=mock`; assert `MockScreeningAdapter` instance is used. (One test for the dependency-injection seam.)
    * **Ledger entry written on success** — assert one `agent.completed` entry with `actor_id="screening"`, `payload.status=="ok"`, `payload.output` containing the hits.

11. **AC11 — Tests at `apps/agents/tests/test_case_supervisor.py` (extend existing).**

    * **Vora intake — screening fan-out** — supervisor runs intake on Vora; assert `INTAKE_AGENTS` tuple now has 4 entries; assert `ledger_entries` post-run includes one `agent.completed` with `actor_id="screening"`; assert the screening output includes Patel R.'s OFAC hit at 0.73; assert evidence_ids back-filled with the screening agent's ledger ID.
    * **Shree intake — screening fan-out, no hits** — assert screening's output `hits == []`; assert one `agent.completed` entry still written with `payload.output.hits == []`.
    * **Ananya intake — screening fan-out, PEP hit** — assert one PEP hit at 0.88, disposition "open" (not auto-dismissed: score is high enough).
    * **`_build_screening_subjects` covers entity + director + UBO** — direct unit test of the helper.

12. **AC12 — Tests at `apps/cockpit-api/tests/test_cases_intake_route.py` (extend existing).**

    * **`GET /v1/cases/{vora_id}/intake` returns `screening` field** — assert payload includes `screening.hits[0].matched_name` containing "Patel"; assert hit's `name_match_score.value == 0.73`.
    * **Backward compat — old intake row without `screening`** — load a fixture row pre-dating Story 6-2; assert response returns `screening: null` (or absent), no 500.

13. **AC13 — Cockpit-api `/v1/agents/screening/run` route tests.**

    Extend `apps/cockpit-api/tests/test_agents_router.py`:
    * **POST `/v1/agents/screening/run` returns 200 with `ScreeningAgentOutput`** for a valid request body.
    * **POST with empty subjects → 422** (Pydantic validation from `min_length=1`).
    * **POST writes one ledger entry** — confirm via the in-memory ledger fixture used by sibling tests.

14. **AC14 — `make lint && make test` clean.** Net new test count: ≥ 7 in `test_screening.py`, ≥ 3 in `test_case_supervisor.py` (extend), ≥ 2 in `test_cases_intake_route.py` (extend), ≥ 3 in `test_agents_router.py` (extend).

15. **AC15 — End-to-end demo verification.**

    ```bash
    make demo-reset && make seed
    poetry -C apps/cockpit-api run python -c "
    import asyncio
    from contracts.cases import VORA_CAPITAL_ID, SHREE_VENKAT_ID, ANANYA_IYER_ID
    from agents.supervisor.case_supervisor import CaseSupervisor
    from cockpit_api.db.session import session_factory
    async def main():
        s = CaseSupervisor(session_factory=session_factory)
        for cid in (VORA_CAPITAL_ID, SHREE_VENKAT_ID, ANANYA_IYER_ID):
            outcome = await s.run_intake(cid)
            print(cid, outcome.case_state)
    asyncio.run(main())
    "
    curl -s 'http://localhost:8000/v1/cases/<vora-id>/intake' | jq '.screening.hits | length'
    # → ≥ 1 (Vora's Patel R. OFAC hit)
    curl -s 'http://localhost:8000/v1/cases/<shree-id>/intake' | jq '.screening.hits | length'
    # → 0
    curl -s 'http://localhost:8000/v1/cases/<ananya-id>/intake' | jq '.screening.hits[0].categories'
    # → ["pep"]
    ```

## Tasks / Subtasks

- [x] **Task 1 — Contract extension** (AC: #1, #8)
  - [x] Subtask 1.1 — Appended `ScreeningAgentInput` / `ScreeningAgentOutput` to `packages/contracts/src/contracts/screening.py`.
  - [x] Subtask 1.2 — Re-exported from `packages/contracts/src/contracts/__init__.py`.
  - [x] Subtask 1.3 — Ran `make contracts`; TS types regenerated.

- [x] **Task 2 — Agent function** (AC: #2, #10)
  - [x] Subtask 2.1 — `apps/agents/src/agents/intake/screening.py` with `@agent_action`-decorated `screening` async function.
  - [x] Subtask 2.2 — `apps/agents/tests/intake/test_screening.py` (8 cases).

- [x] **Task 3 — Supervisor integration** (AC: #3, #4, #5, #11)
  - [x] Subtask 3.1 — Added `_invoke_screening`, `_has_screenable_subjects`, `_build_screening_subjects`, `_fill_evidence_ids_screening` (plus `_entity_subject_id`, `_individual_case_dob`, `_director_slug`, `_ubo_person_ids_with_min_ownership` helpers) to `apps/agents/src/agents/supervisor/case_supervisor.py`.
  - [x] Subtask 3.2 — Appended the screening `IntakeAgentSpec` to `INTAKE_AGENTS` (sequenced before `risk_scoring`); fan-out is now 5 agents for cases with CIN.
  - [x] Subtask 3.3 — Updated `apps/agents/tests/test_case_supervisor.py` — adjusted `agents_run` assertions and added 4 new tests (Vora OFAC hit, Shree clean, Ananya PEP, `_build_screening_subjects` unit).

- [x] **Task 4 — Persist + expose via API** (AC: #6, #7, #12)
  - [x] Subtask 4.1 — `IntakeRepo.upsert(case_id, "screening", output)` reuses the existing JSON-blob row schema. No model migration needed (mirrors `risk_scoring` pattern).
  - [x] Subtask 4.2 — Added `GET /v1/cases/{case_id}/intake/screening` returning `ScreeningAgentOutput` (mirrors per-agent endpoint pattern; no unified `/intake` exists).
  - [x] Subtask 4.3 — Extended `apps/cockpit-api/tests/test_cases_intake_get_route.py` (2 new cases: typed response + 404 when not run).

- [x] **Task 5 — ADK registry + cockpit-api tool route** (AC: #9, #13)
  - [x] Subtask 5.1 — `apps/agents/src/agents/registry/screening/agent.yaml`.
  - [x] Subtask 5.2 — `apps/agents/src/agents/registry/screening/openapi.yaml` (regenerated by `make adk-spec`).
  - [x] Subtask 5.3 — `apps/cockpit-api/src/cockpit_api/routers/agents.py` adds `POST /v1/agents/screening/run`.
  - [x] Subtask 5.4 — Extended `apps/cockpit-api/tests/test_agents_router.py` (3 new cases: happy path + ledger, empty subjects → 422, invalid case_id → 422).

- [x] **Task 6 — Verification** (AC: #14, #15)
  - [x] Subtask 6.1 — `make lint` clean; 472 Python tests green (193 contracts + 146 cockpit-api + 133 agents). Pre-existing Vitest failures in `useCases.test.tsx` / `useCase.test.tsx` reproduce on clean main (unrelated).
  - [x] Subtask 6.2 — Tool + agent successfully imported to IBM Orchestrate cloud (`techzone-poc` env active per `.env`): `Tool 'run_screening' imported successfully` and `Agent 'screening' imported successfully`. Cloud-side smoke (curl against the running ngrok tunnel) deferred — not needed for sprint review since the same agent function is exercised end-to-end via the supervisor in `tests/test_case_supervisor.py::test_vora_intake_screening_hits_ofac`.

## Dev Notes

### Architectural context (binding)

* [Source: `architecture.md#Project-Specific Patterns` § P4 Agent Action Pattern] every agent invocation writes one ledger entry via `@agent_action`. Direct `LedgerWriter.append` from agent code is forbidden by lint rule.
* [Source: `architecture.md#Project-Specific Patterns` § P3 Provenance] `name_match_score` ProvenancedField needs `evidence_ids` back-filled with the screening agent's own ledger entry ID. This is the same two-pass pattern Document Intelligence / Entity Verification / UBO Graph use.
* [Source: `architecture.md#Demo Scope Addendum (2026-04-29)`] § Stack changes: "Vendor adapters → mock-only" means the agent has one adapter to satisfy.
* [Source: `architecture.md#Agent Runtime Update (2026-05-07)`] cloud Orchestrate is the runtime; cockpit-api hosts the OpenAPI tool route. The supervisor calls the agent function in-process; cloud Orchestrate calls it via the HTTP route. Same Python function, two callers.
* [Source: `architecture.md#Project-Specific Patterns` § P7 Confidence Banding] `name_match_score.provenance.confidence_band = to_band(score)`. Story 6-1 already enforces this in the adapter.
* [Source: `prd.md#Functional Requirements § Screening & Risk Analysis` FR18] Authority + intent of this story.

### Critical pitfalls

1. **`@agent_action`-decorated functions write ledger entries; the supervisor MUST NOT also write one for the agent.** The supervisor writes only `case.intake_*` SYSTEM entries. Mirror Story 5-1's supervisor pattern (`_invoke_entity_verification` returns the typed output; the supervisor never calls `LedgerWriter.append` itself for the agent).

2. **Frozen Pydantic models — disposition update via `model_copy(update={...})`.** Don't try to mutate `hit.disposition = "..."`. Frozen will raise. Use `hit.model_copy(update={...})`. Match the `_rebuild_provenanced_field` pattern in `case_supervisor.py:248`.

3. **Auto-dismissal thresholds are agent constants, not contract-level.** Don't lift `_DISMISS_SCORE_THRESHOLD` into `packages/contracts/`. Different vendors will calibrate differently; the agent is the right home.

4. **Director list source.** `EntityVerificationResult` doesn't carry the full MCA director list — it only carries the typed `mca_status` and a list of `FieldMismatch`. Story 5-1's supervisor stores the underlying `MCACompanyMaster` in… check via grep at implementation time (likely accessible via `apps/agents/src/agents/intake/mca.py` or stored in `IntakeContext.outputs["entity_verification_master"]` as a side-channel — read Story 5-1's code first). If unavailable, **call `mca.lookup(cin)` again from `_build_screening_subjects`** — cheaper than reshaping Story 5-1's contract. Document the chosen path in the supervisor code with a comment.

5. **UBO ownership threshold (≥ 0.10) — exact value.** `UBOEdge.ownership_pct` is a fraction (0.10), not a percentage (10). Don't accidentally compare against 10.

6. **Subject_id consistency.** The `subject_id` you pass in `ScreeningSubject` must match the keys in Story 6-1's `SCREENING_FIXTURES`. Confirm by reading Story 6-1's fixture file — if there's any drift, fixtures won't fire and tests pass while the demo silently shows zero hits. This is the most likely "tests pass but demo broken" trap.

7. **`_invoke_screening` reads `ctx.outputs.get("entity_verification")` — handle the case where Entity Verification didn't run.** A case without a CIN won't have run Entity Verification (its `_has_cin` predicate returns False). Skip director subjects in that case; still emit the entity subject (always present).

8. **`_invoke_screening` reads `ctx.outputs.get("ubo_graph")` — same caveat.** No CIN → no UBO Graph → no UBO subjects. Entity-only screening still works.

9. **The `screening` agent function takes `adapter` as a kwarg-only parameter.** Mirror `entity_verification`'s `mca` kwarg pattern. Tests inject; supervisor passes None and lets the factory resolve.

10. **`ProvenancedField[float]` value vs the wrapping confidence — careful.** `name_match_score.provenance.confidence` equals `name_match_score.value`. Story 6-1's mock sets this. The agent should not re-derive — just trust the adapter's provenance metadata. (If a future real adapter sets them differently, that's its problem.)

11. **Backward compat for the intake row.** Old rows (Stories 3-4 / 5-1 / 5-3) won't have a `screening` field. Pydantic `Optional[ScreeningAgentOutput] = None` with `model_validate` handles this; double-check by loading a pre-existing fixture row in the test.

12. **Don't add screening to UBO ownership computation.** Risk Scoring (Story 5-6) consumes screening output; this story does not call into risk scoring or any other downstream agent. Stay in your lane.

### Story dependencies

* **Strict prereqs:** Story 6-1 (`ScreeningAdapter`, `MockScreeningAdapter`, fixtures), Story 3-2 (`@agent_action` decorator), Story 3-3 (`AgentActionLedgerEntry`, `LedgerEntry`), Story 3-5 (supervisor + `INTAKE_AGENTS` shape + `IntakeContext`), Story 5-1 (`EntityVerificationResult`, supervisor `_invoke_entity_verification` pattern), Story 5-3 (`UBOGraph`, supervisor `_invoke_ubo_graph` pattern).
* **Soft prereq:** Story 5-6 (Risk Scoring agent) — currently in-progress. If 5-6 lands first, screening's output will feed the risk decomposition's "screening" component naturally; if not, 5-6 picks up screening data via the same intake row this story persists.
* **Read by:** Story 6-3 (ScreeningExplainer renders these hits), Story 6-7 (`re_run_agent` tool can re-invoke the screening agent).

### Project Structure Notes

This story creates:
- `apps/agents/src/agents/intake/screening.py`
- `apps/agents/src/agents/registry/screening/agent.yaml`
- `apps/agents/src/agents/registry/screening/openapi.yaml`
- `apps/agents/tests/intake/test_screening.py`

This story modifies:
- `packages/contracts/src/contracts/screening.py` — adds `ScreeningAgentInput`, `ScreeningAgentOutput`
- `packages/contracts/src/contracts/__init__.py` — public exports
- `apps/agents/src/agents/supervisor/case_supervisor.py` — fourth `IntakeAgentSpec` + `_invoke_screening` + `_has_screenable_subjects` + `_build_screening_subjects` + `_fill_evidence_ids_screening`
- `apps/cockpit-api/src/cockpit_api/repositories/intake_repo.py` (or the underlying SQLAlchemy model) — persist screening output
- `apps/cockpit-api/src/cockpit_api/routers/cases.py` (or wherever `GET /intake` lives) — expose `screening` field
- `apps/cockpit-api/src/cockpit_api/routers/agents.py` — `POST /v1/agents/screening/run` handler
- `apps/agents/tests/test_case_supervisor.py` — extend
- `apps/cockpit-api/tests/test_cases_intake_route.py` — extend
- `apps/cockpit-api/tests/test_agents_router.py` — extend
- `apps/cockpit-ui/src/api-types.ts` — regenerated by `make contracts`

This story DOES NOT create:
- The Screening UI panel (Story 6-3)
- The Reasoning Trace contract or endpoint (Stories 6-4 / 6-5)
- The Cockpit Chat agent (Story 6-7)
- A second screening adapter (cut from demo)
- Officer-side re-run capability (cut from demo's Story 6-3)
- Risk-score recomputation (Stories 5-6 / 5-8 own this)

### References

- [Source: `epics.md#Epic 6` § Story 6.3] original AC (re-scoped here — drops tenant_id, drops two-impl conformance, drops mock-vendor-down failure path)
- [Source: `architecture.md#Project-Specific Patterns`] § P1, § P3, § P4, § P7
- [Source: `architecture.md#Demo Scope Addendum (2026-04-29)`] § Stack changes / § Resolved decision §1
- [Source: `architecture.md#Agent Runtime Update (2026-05-07)`] dual-caller (supervisor + cloud Orchestrate via OpenAPI route) pattern
- [Source: `prd.md#Functional Requirements § Screening & Risk Analysis`] FR18
- [Source: `6-1-screening-adapter-protocol-with-mock-impl.md`] adapter contracts and fixture subject_ids
- [Source: `5-1-entity-verification-agent.md`] supervisor `_invoke_*` + `_fill_evidence_ids_*` two-pass pattern; `EntityCaseView` builder shape
- [Source: `5-3-ubo-graph-agent-basic.md`] `UBOGraph` shape, ownership_pct fraction convention
- [Source: `3-4-document-intelligence-agent-llm-extract.md`] adapter factory pattern + `set_runtime_model_id` ContextVar usage
- [Source: `apps/agents/src/agents/registry/document_intelligence/agent.yaml`] ADK manifest reference

### Demo verification protocol

Per AC15 — full intake fan-out across the three demo cases, verify hits via the API, confirm ledger entries, confirm Vora's amber narrative reads.

If any step fails, the bug is in this story; do not ship until green.

## Dev Agent Record

### Agent Model Used

(claude-opus-4-7 + Amelia persona, bmad-dev-story workflow)

### Debug Log References

- Cockpit-api venv lacked `rapidfuzz` (transitive via the `agents` path-dep); `poetry lock --no-update && poetry install` in `apps/cockpit-api` resolved the import error.
- Pre-existing Vitest failures in `apps/cockpit-ui/src/hooks/useCases.test.tsx` (2) + `useCase.test.tsx` (3) reproduce on clean main — not introduced by this story.

### Completion Notes List

- **Reordered `INTAKE_AGENTS`** so `screening` runs before `risk_scoring`. The risk-scoring agent doesn't currently consume screening output, but the order keeps the demo deterministic if Story 5.6 evolves to use the screening data.
- **Endpoint shape (AC #7 deviation)**: Story AC #7 specified a unified `GET /v1/cases/{id}/intake` returning `{document_intelligence, entity_verification, ubo_graph, screening}`. The repo's existing pattern is a per-agent endpoint (`/intake/document_intelligence`, `/intake/ubo_graph`, `/intake/risk_scoring`). I added `/intake/screening` to mirror that pattern instead of introducing a unified route. This keeps backward compat trivial — no existing client breaks.
- **`_build_screening_subjects` calls MCA again** rather than reshaping `EntityVerificationResult` — explicitly per Pitfall #4. The mock lookup is in-process and deterministic; no perf concern for the demo.
- **UBO threshold conversion**: Story uses `ownership_pct >= 0.10` (fraction). The `UBOEdge.ownership_pct` field is a percentage (0..100). Helper converts: `if edge.ownership_pct >= threshold * 100.0`.
- **Subject ID dedupe**: directors and UBO person nodes can collide on the same `ubo_p_<din>` ID. The supervisor emits the director subject first; the UBO loop skips already-seen IDs.
- **`_individual_case_dob` reads `customer_metadata.extra.date_of_birth`** so Ananya's entity subject carries her DOB (1985-11-04), which the mock fixture matches against.
- **Auto-dismissal** uses two thresholds per Story 6.2 / AC #2: `< 0.50` always dismisses; `< 0.65 AND DOB mismatch (when both DOBs known)` also dismisses. Demo's Vora OFAC hit at 0.73 passes both gates → stays `open`. Ananya's PEP at 0.88 → `open`.
- **`evidence_ids` two-pass back-fill** mirrors Story 5.1's pattern via `_fill_evidence_ids_screening` — every hit's `name_match_score.provenance.evidence_ids` is rebuilt with the screening agent's own ledger entry ID.
- **Imported to IBM Orchestrate cloud**: `orchestrate tools import -k openapi -f .../screening/openapi.yaml` and `orchestrate agents import -f .../screening/agent.yaml` both returned success. The active env is `techzone-poc` (cloud) per the .env in repo root.

### File List

- `packages/contracts/src/contracts/screening.py` (modified) — added `ScreeningAgentInput`, `ScreeningAgentOutput`.
- `packages/contracts/src/contracts/__init__.py` (modified) — re-exported new symbols.
- `packages/contracts/openapi.json` (regenerated).
- `apps/cockpit-ui/src/api-types.ts` (regenerated).
- `apps/agents/src/agents/intake/screening.py` (new) — `screening` async function with `@agent_action` + auto-dismissal.
- `apps/agents/src/agents/supervisor/case_supervisor.py` (modified) — `_invoke_screening`, `_has_screenable_subjects`, `_build_screening_subjects`, `_fill_evidence_ids_screening`, `_entity_subject_id`, `_individual_case_dob`, `_director_slug`, `_ubo_person_ids_with_min_ownership`, screening entry in `INTAKE_AGENTS`, screening persistence in completed-path.
- `apps/agents/src/agents/registry/screening/agent.yaml` (new).
- `apps/agents/src/agents/registry/screening/gen_openapi.py` (new).
- `apps/agents/src/agents/registry/screening/openapi.yaml` (generated).
- `apps/agents/tests/intake/__init__.py` (new) — empty.
- `apps/agents/tests/intake/test_screening.py` (new) — 8 agent tests.
- `apps/agents/tests/test_case_supervisor.py` (modified) — adjusted 4 existing assertions, added 4 new tests.
- `apps/agents/tests/test_risk_scoring.py` (modified) — adjusted `agents_run` assertion.
- `apps/agents/tests/test_ubo_graph.py` (modified) — adjusted `agents_run` assertion.
- `apps/cockpit-api/src/cockpit_api/routers/agents.py` (modified) — added `POST /v1/agents/screening/run`.
- `apps/cockpit-api/src/cockpit_api/routers/cases.py` (modified) — added `GET /v1/cases/{case_id}/intake/screening`.
- `apps/cockpit-api/tests/test_agents_router.py` (modified) — 3 new screening endpoint tests.
- `apps/cockpit-api/tests/test_cases_intake_get_route.py` (modified) — 2 new screening-intake-GET tests.
- `apps/cockpit-api/tests/test_cases_intake_route.py` (modified) — adjusted `agents_run` assertion.
- `apps/cockpit-api/poetry.lock` (regenerated — pulled in `rapidfuzz` transitively).

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-05-08 | Story 6.2 drafted. Demo replacement for bank-buyer Story 6.3: Screening agent with @agent_action ledger entry, supervisor as fourth `INTAKE_AGENTS` entry, auto-dismissal of low-match/DOB-mismatch hits, persistence in intake row, exposed via `GET /v1/cases/{id}/intake` and `POST /v1/agents/screening/run` (cloud Orchestrate tool route). |
| 2026-05-08 | Implemented Story 6.2. Screening agent + supervisor integration + cockpit-api tool route + per-agent GET intake endpoint; Tool + Agent imported to IBM Orchestrate cloud (`techzone-poc`). 17 net-new tests (8 agent + 4 supervisor + 3 router + 2 GET intake) all passing; `make lint` clean; full Python suite 472 green. |
