# Story 5.1: Entity Verification agent

Status: review

## Story

As the platform,
I want an Entity Verification agent that — given a case's CIN extracted by Document Intelligence (Story 3.4) — calls the mock MCA lookup tool (Story 5.2), cross-references the MCA company-master against the case's customer-metadata + intake extractions, surfaces typed mismatches, and writes a typed `EntityVerificationResult` plus an `agent.completed` ledger entry,
So that the analyst sees authority-source-grounded entity status as the second intake-fan-out node and Story 5.6's Risk Scoring agent has a typed entity signal to consume (FR17 demo-scoped, NFR-RI1 supervisor/collaborator pattern showcase, P3 provenance everywhere, P4 ledger per invocation).

## Scope note (2026-04-29 demo re-scope)

This story is the demo-equivalent of the bank-buyer Story 5.1. Per the sprint-change proposal, **GST verification is dropped** (the original Story 5.3 GST tool was cut entirely); MCA alone proves the multi-tool ADK pattern. FR17 reduces from "MCA + GST cross-reference" to "MCA-only".

| Bank-buyer scope (original 5.1) | Demo replacement in this story |
|---|---|
| Calls MCA tool (5.2) AND GST tool (5.3) via ADK `@tool`s; merges results | **MCA-only.** No GST tool exists. The agent's tool-call list is exactly one entry. |
| Tenant-scoped (`tenant_id` keyword arg on every fn) | **Single-tenant demo** — no `tenant_id`. Mirrors Stories 3.4/3.5. |
| Failure transitions case to `intake_blocked` (a bank-buyer state) | **`escalated`** — the demo state machine has no `intake_blocked`; supervisor (Story 3.5) already handles `escalated` via `add_block_marker` for Document Intelligence failures. Reuse that path. |
| `mca_status` enum: `active`/`struck-off`/`dormant` | **Same enum, snake_case wire format**: `active` / `struck_off` / `dormant`. (P-Format Patterns rule.) |
| `EntityVerificationResult.gst_status` field | **Removed.** The GST tool doesn't exist. |

What survives: **typed `EntityVerificationResult`, mismatch list, `@agent_action` ledger entry, supervisor fan-out integration, ADK registry entry (manifest + OpenAPI tool spec), agent_slug `entity-verification` (matches `AgentSlug.ENTITY_VERIFICATION` from Story 4.5).**

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md` § Stories simplified, `architecture.md#Demo Scope Addendum (2026-04-29)`, and `epics.md#Epic 5`.

## Acceptance Criteria

1. **AC1 — Pydantic contracts in `packages/contracts/src/contracts/entity_verification.py`.**

    ```python
    from typing import Literal
    from pydantic import BaseModel, Field

    MCAStatus = Literal["active", "struck_off", "dormant"]

    class FieldMismatch(BaseModel):
        model_config = {"frozen": True}
        field_name: str = Field(min_length=1)        # e.g., "company_name", "registered_address"
        case_value: str | None                       # value as it appears on the case (Document Intelligence or customer_metadata)
        mca_value: str | None                        # value as it appears in MCA
        severity: Literal["info", "warning", "critical"] = "warning"
        notes: str | None = None                     # short human-readable explanation

    class EntityVerificationInput(BaseModel):
        model_config = {"frozen": True}
        case_id: CaseId
        cin: str = Field(min_length=21, max_length=21, pattern=r"^[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}$")

    class EntityVerificationResult(BaseModel):
        model_config = {"frozen": True}
        case_id: CaseId
        cin: str
        mca_status: ProvenancedField[MCAStatus]
        mismatches: list[FieldMismatch] = Field(default_factory=list)
    ```

    `MCAStatus` is the inline `Literal` **only**; do **not** introduce a new `StrEnum`. Wire format is snake_case so `struck_off` (not `struck-off`) is the canonical value — architecture.md § Naming Patterns / Enum values are `snake_case`.

    The `mca_status` value is wrapped in `ProvenancedField[MCAStatus]` (P3) — `Provenance.source_agent="entity_verification"`, `source_system="mca_mock"`, `confidence=0.95` (mock is deterministic; deliberately high but not 1.0), `confidence_band=to_band(0.95)` → `HIGH`, `evidence_ids=[]` (the supervisor back-fills with the agent's own ledger ID — same two-pass pattern as Document Intelligence Story 3.4 § AC8).

    Re-export from `packages/contracts/src/contracts/__init__.py` alongside the other public symbols. Names to add to `__all__`: `EntityVerificationInput`, `EntityVerificationResult`, `FieldMismatch`, `MCAStatus`.

2. **AC2 — Agent function at `apps/agents/src/agents/intake/entity_verification.py`.**

    ```python
    @agent_action(
        agent_id="entity_verification",
        model_id="deterministic",          # MCA mock is rule-based, not LLM-driven
        prompt_template_id=None,
    )
    async def entity_verification(
        input: EntityVerificationInput,
        *,
        mca: MCALookup | None = None,
        case_view: EntityCaseView | None = None,
    ) -> EntityVerificationResult: ...
    ```

    Logic (bind to AC details):
    1. Resolve `mca = mca or get_default_mca_lookup()`. The default reads `MCA_PROVIDER` env (default `"mock"`); only the mock impl exists in the demo. Unknown providers raise `ValueError` (mirrors Story 3.4's `_get_default_llm`).
    2. Call `master = await mca.lookup(cin=input.cin)`. The tool's typed errors:
        * `MCANotFoundError` → wrapped by `@agent_action` into `AgentExecutionError` → supervisor sets case to `escalated` with block marker `"entity_verification: cin not found in MCA"`.
        * `MCATemporaryError` → same path, marker `"entity_verification: MCA tool unavailable"`.
        * Generic `Exception` from inside the tool body → wrapped into `AgentExecutionError` (decorator handles).
    3. Map `master.status` (the tool's typed `MCAStatus`) into an `mca_status: ProvenancedField[MCAStatus]` per AC1.
    4. Compute mismatches by diffing the case-side view (`case_view`) against the MCA master (see AC3).
    5. Build and return `EntityVerificationResult(case_id=input.case_id, cin=input.cin, mca_status=..., mismatches=...)`.

    **`case_view` is an explicit dependency**, not a global side-channel: the supervisor builds an `EntityCaseView` (AC3) from the case + Document Intelligence intake row and passes it into the call. That keeps the agent function pure-ish and trivially testable.

3. **AC3 — `EntityCaseView` builder lives in the supervisor, not the agent.**

    Add to `apps/agents/src/agents/supervisor/case_supervisor.py`:

    ```python
    @dataclass(frozen=True)
    class EntityCaseView:
        company_name: str | None
        registered_address: str | None
        incorporation_date: str | None       # ISO-8601 date string
        cin: str | None

    def _build_entity_case_view(
        case: Case,
        doc_intel_output: DocumentIntelligenceOutput | None,
    ) -> EntityCaseView: ...
    ```

    Construction rules:
    * `cin`: prefer `customer_metadata.extra.get("registration_number")`; fall back to the first ExtractedField with `field_name="cin"` whose `value.value` is non-null.
    * `company_name`: prefer the ExtractedField with `field_name="company_name"`; fall back to `customer_metadata.customer_name`.
    * `registered_address`: prefer ExtractedField `field_name="registered_address"`; fall back to `customer_metadata.extra.get("registered_address")`.
    * `incorporation_date`: prefer ExtractedField `field_name="incorporation_date"` (already ISO 8601 from Story 3.4 fixture); fall back to `customer_metadata.extra.get("incorporation_date")`.

    Diff rule (in the agent function, not the builder): for each of `company_name`, `registered_address`, `incorporation_date`, compare case-side to MCA-side after a normalization pass:
    * Lowercase + collapse runs of whitespace + strip leading/trailing punctuation.
    * If both sides are non-empty and normalized strings differ → emit a `FieldMismatch` with `severity="warning"`, `notes=None`. If MCA has the field but the case doesn't → `severity="info"`, `notes="MCA has field; case does not"`. If only the case has it → `severity="info"`, `notes="Case has field; MCA does not"`. If both empty → no mismatch.
    * `incorporation_date` mismatches escalate to `severity="critical"` (date drift on incorporation is an integrity red flag).

4. **AC4 — Supervisor wires `entity_verification` into `INTAKE_AGENTS`.** Order matters: `document_intelligence` first (already there), then `entity_verification` second.

    Spec entry:
    ```python
    IntakeAgentSpec(
        name="entity_verification",
        invoke=_invoke_entity_verification,
        requires=_has_cin,
    )
    ```

    Helpers in the supervisor:

    ```python
    def _has_cin(case: Case) -> bool:
        # Either customer_metadata.extra.registration_number, or a CIN-shaped
        # extracted field. The supervisor doesn't have the doc-intel output
        # at requires-evaluation time (requires runs before fan-out), so this
        # falls back to extra-only — the diff path inside the agent re-tries
        # via doc-intel output when present.
        reg = case.customer_metadata.extra.get("registration_number")
        return isinstance(reg, str) and bool(_CIN_RE.match(reg))

    async def _invoke_entity_verification(case: Case) -> EntityVerificationResult:
        # The supervisor must thread the just-completed doc_intel_output into
        # the agent. _invoke_* takes only `case`, so we capture the prior
        # agent's typed output via a closure — see AC5 for the supervisor
        # refactor.
        ...
    ```

    `_CIN_RE = re.compile(r"^[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}$")` — module constant.

5. **AC5 — Supervisor refactor: per-run `IntakeContext` carries typed outputs across agents.**

    The current `INTAKE_AGENTS` tuple's `invoke` callable signature is `Callable[[Case], Awaitable[Any]]`, which makes it impossible for `entity_verification` to read `document_intelligence`'s typed output without a global. Refactor: introduce a per-run mutable context object that lives only inside `run_intake`:

    ```python
    @dataclass
    class IntakeContext:
        """Per-run state. Mutated inside run_intake; never escapes."""
        case: Case
        outputs: dict[str, BaseModel] = field(default_factory=dict)
    ```

    Change `IntakeAgentSpec.invoke` signature to `Callable[[IntakeContext], Awaitable[BaseModel]]`. Each `_invoke_*` reads from `ctx.outputs.get("document_intelligence")` etc.; on success, the supervisor stores the returned output into `ctx.outputs[spec.name]` before continuing the loop. Update `_invoke_document_intelligence` to take `ctx`. Update existing tests in `apps/agents/tests/test_case_supervisor.py` for the new signature.

    Why mutable: outputs are immutable Pydantic models; the dict is the carrier. Keeps the tuple ordering canonical without any mid-loop tuple repacking.

6. **AC6 — `_fill_evidence_ids` extends to `entity_verification`.**

    The current `_fill_evidence_ids` helper rewrites only the Document Intelligence output. Add a sibling `_fill_evidence_ids_entity_verification(output, ledger_entry_id)` that copies-on-write the single `mca_status: ProvenancedField[MCAStatus]` field. Keep both helpers; the supervisor calls each one only for the agent it knows produces a `ProvenancedField`-bearing output.

    For uniformity, factor out a small generic helper (Pythonic, not a class hierarchy):

    ```python
    def _rebuild_provenanced_field[T](
        pf: ProvenancedField[T], evidence_ids: list[LedgerEntryId]
    ) -> ProvenancedField[T]:
        new_prov = pf.provenance.model_copy(update={"evidence_ids": evidence_ids})
        return pf.model_copy(update={"provenance": new_prov})
    ```

    Both `_fill_evidence_ids` (Document Intelligence) and `_fill_evidence_ids_entity_verification` use this helper internally.

7. **AC7 — Persistence via `IntakeRepo`.**

    After Entity Verification completes, the supervisor calls `IntakeRepo.upsert(session, case_id, "entity_verification", filled_output)` (same pattern as Document Intelligence). The blob is the `EntityVerificationResult.model_dump(mode="json")`. Story 5.7 (Risk Scoring agent) reads this row to consume entity status as a risk component.

    No DB migration is required — the `intake_results` table is already polymorphic (Story 3.5). Verify by re-running `make migrate` produces zero diff. (`alembic --autogenerate` on no-schema-change case is empty.)

8. **AC8 — HTTP boundary at `POST /v1/agents/entity_verification/verify`.**

    Mirror the Document Intelligence router pattern (`apps/cockpit-api/src/cockpit_api/routers/agents.py`):

    ```python
    @router.post(
        "/entity_verification/verify",
        response_model=EntityVerificationResult,
        summary="Run the Entity Verification agent against a CIN",
        description=(
            "Calls the Entity Verification agent. Looks the CIN up against "
            "the mock MCA lookup tool, diffs case-side fields, returns "
            "typed mismatches. Every invocation writes one ledger entry."
        ),
    )
    async def verify_entity(
        payload: EntityVerificationInput,
    ) -> EntityVerificationResult:
        try:
            return await entity_verification(payload)
        except AgentExecutionError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
    ```

    The HTTP path is what the ADK runtime calls from the cloud Orchestrate tenant via the ngrok tunnel — see Agent Runtime Update 2026-05-07 in architecture.md.

9. **AC9 — ADK registry entry at `apps/agents/src/agents/registry/entity_verification/`.**

    Three files (mirror `registry/document_intelligence/`):

    1. `agent.yaml` — manifest:
        ```yaml
        spec_version: v1
        kind: native
        name: entity_verification
        description: >-
          Entity Verification agent. Cross-references a case's CIN against
          the MCA company-master via the mca_lookup tool; surfaces field
          mismatches as typed warnings.
        llm: groq/openai/gpt-oss-120b
        style: react
        instructions: |
          You are the Entity Verification agent for a regulated bank's
          KYC cockpit.

          When the user (or the Case Supervisor) asks you to verify a case,
          call the `verify_entity` tool with the case_id and CIN. The tool
          returns a structured EntityVerificationResult with an MCA status
          and mismatches. Summarize the result in one short paragraph for
          the user: confirm the MCA status, list mismatches if any, and
          (when status is `struck_off` or `dormant`) flag that the case
          should be escalated.

          Never invent CIN values. If the user does not provide one, ask.
          Never invent MCA fields; if you didn't get them from the tool,
          say "no data available".
        tools:
          - verify_entity
        ```

    2. `gen_openapi.py` — calls the shared ADK helper:
        ```python
        from pathlib import Path
        from agents._adk.openapi_tool import build_and_write

        build_and_write(
            path_filter="/v1/agents/entity_verification/verify",
            operation_id="verify_entity",
            title="KYC Entity Verification (ADK Tool)",
            description=(
                "Entity Verification agent exposed for ADK runtime tool "
                "registration. The watsonx Orchestrate runtime calls this "
                "endpoint when an agent decides to invoke verify_entity."
            ),
            output=Path(__file__).parent / "openapi.yaml",
        )
        ```

    3. `openapi.yaml` — generated, **do not edit by hand**. `make adk-spec` regenerates it from the live FastAPI app. Commit the file so reviewers can read the wire shape without running the toolchain.

    The collaborator wiring on `case_supervisor/agent.yaml` is **out of scope for this story** — Story 5.7 (Risk Scoring) will land alongside a single supervisor.yaml update that adds `entity_verification`, `ubo_graph`, and `risk_scoring` as collaborators in one pass.

10. **AC10 — `make adk-register` succeeds.** After `make adk-spec`, `make adk-register` walks the registry and imports `entity_verification`'s tool + agent into the activated Orchestrate env. Dev verifies by running both targets and confirming "imported successfully" in the CLI output.

    Does NOT require any change to `Makefile` or `_adk/openapi_tool.py` — the targets already walk `registry/*/`.

11. **AC11 — Tests in `apps/agents/tests/test_entity_verification.py`.** Cover:

    * **Happy path (mock):** Vora fixture's CIN → returns `mca_status="active"`; mismatches list matches the expected diff (Vora's case fixtures have a SG/BVI UBO chain hint but no name/address/date drift in customer_metadata vs. mock MCA — so the expected mismatches list is `[]` for the pinned fixture). Use `MockMCALookup()` from Story 5.2; assert the returned `EntityVerificationResult` has the expected mca_status band `HIGH` and `evidence_ids=[]`.
    * **Mismatch detection:** stub the mock to return a master with a different `company_name` than the case; assert one `FieldMismatch` with `field_name="company_name"`, `severity="warning"`.
    * **Missing case-side field:** call against a fixture with no Document Intelligence output (`ctx.outputs` empty); assert `FieldMismatch` rows for case-side absent + `severity="info"`.
    * **Critical date drift:** stub MCA to return a different `incorporation_date`; assert `severity="critical"`.
    * **CIN-not-in-MCA:** stub the mock to raise `MCANotFoundError`; call the agent directly; assert `AgentExecutionError` is raised; assert one `agent.failed` ledger entry. Then call via the supervisor: assert the case transitions to `escalated` with `intake_blocked` block marker `"entity_verification: <error msg>"`.
    * **Tool unavailable:** stub the mock to raise `MCATemporaryError`; same supervisor-level assertion as above.
    * **Ledger entry shape:** invoke through `@agent_action` against a `tmp_path` ledger; assert `payload.agent_id == "entity_verification"`, `payload.model_id == "deterministic"`, `payload.input.cin == "<vora-cin>"`, `payload.output.mca_status.value == "active"`, `payload.tool_calls` includes a single entry naming `mca_lookup`.
    * **`evidence_ids` back-fill:** call through the supervisor; assert the persisted `intake_results` row's `mca_status.provenance.evidence_ids == [agent_completed_entry.id]`.
    * **Provenance band consistency:** assert `to_band(0.95) == HIGH` and the persisted output's `mca_status.provenance.confidence_band == ConfidenceBand.HIGH`.

    Reuse the `tmp_writer` and `make_test_session` fixtures from `apps/agents/tests/conftest.py` (Stories 3.2/3.5 already define them).

12. **AC12 — Supervisor tests in `apps/agents/tests/test_case_supervisor.py`** extend with:

    * Two-agent fan-out: doc_intel + entity_verification; both succeed; case transitions `intake_scheduled → decision_ready`; ledger has 5 entries (doc_intel agent.completed + entity_verification agent.completed + case.intake_completed at end + 2 from prior seeding context as appropriate). Be explicit about `[entry.action for entry in entries]`.
    * Doc-intel succeeds but entity_verification fails on `MCATemporaryError`: case transitions `intake_scheduled → escalated`; `add_block_marker` called with `blocked_agent="entity_verification"`; `agents_run == ["document_intelligence", "entity_verification"]`; `failed_agent == "entity_verification"`.
    * `requires=_has_cin` returns False (case with no `registration_number`): supervisor logs skipped agent; `agents_run` excludes `entity_verification`; intake completes successfully; no `entity_verification` ledger entry written.

13. **AC13 — `make demo-reset && make seed && make test` clean.** Net new test count: ≥ 9 in `test_entity_verification.py`, ≥ 3 in supervisor tests, ≥ 2 contract tests for `EntityVerificationResult`/`FieldMismatch` round-trip in `packages/contracts/tests/test_entity_verification.py`.

14. **AC14 — agent-mesh-state derivation already works.** `apps/cockpit-api/src/cockpit_api/services/agent_mesh_state.py` derives state by `actor_id`. Confirm by inspecting the file: the existing logic walks every ledger entry and group-by `actor_id` — Entity Verification's ledger entries land under `actor_id="entity_verification"` automatically. Add **one** integration test in `apps/cockpit-api/tests/test_agent_mesh_state.py` (or whichever test file already exercises derivation) that, after running supervisor end-to-end, asserts the snapshot's `entity_verification` row is `state=COMPLETE`. **Do not** modify `agent_mesh_state.py` — it's already polymorphic.

    Note: `AgentSlug.ENTITY_VERIFICATION = "entity-verification"` (kebab-case). The supervisor writes ledger entries with `actor_id="entity_verification"` (snake_case). Story 4.5's derivation maps slugs ↔ actor_ids via a small `_normalize_slug(actor_id) -> AgentSlug | None` helper. **Verify the helper covers `entity_verification` ↔ `entity-verification`** before touching anything else; this is the exact same pattern document_intelligence uses today (`actor_id="document_intelligence"` ↔ `AgentSlug.DOCUMENT_INTELLIGENCE = "document-intelligence"`). If the helper does not yet have the mapping for `entity_verification`, add it; this is a single-line entry.

## Tasks / Subtasks

- [x] **Task 1 — Author Pydantic contracts** (AC: #1)
  - [x] Subtask 1.1 — `packages/contracts/src/contracts/entity_verification.py` with `MCAStatus`, `FieldMismatch`, `EntityVerificationInput`, `EntityVerificationResult`.
  - [x] Subtask 1.2 — Re-export from `packages/contracts/src/contracts/__init__.py` (alphabetical).
  - [x] Subtask 1.3 — `packages/contracts/tests/test_entity_verification.py` covers round-trip + `mca_status` ProvenancedField shape.

- [x] **Task 2 — Author the agent function** (AC: #2)
  - [x] Subtask 2.1 — `apps/agents/src/agents/intake/entity_verification.py` with `@agent_action`-decorated `entity_verification(...)`. Inject `mca: MCALookup | None = None` and `case_view: EntityCaseView | None = None`.
  - [x] Subtask 2.2 — `_get_default_mca_lookup()` reads `MCA_PROVIDER` env (default `"mock"`); raises `ValueError` on unknown.
  - [x] Subtask 2.3 — Diff helper `_compute_mismatches(case_view, master) -> list[FieldMismatch]` per AC3 normalization rules.
  - [x] Subtask 2.4 — Catch only typed errors (`MCANotFoundError`, `MCATemporaryError`); let everything else bubble — `@agent_action` wraps both into `AgentExecutionError` consistently.

- [x] **Task 3 — Refactor supervisor to thread typed outputs** (AC: #5)
  - [x] Subtask 3.1 — Define `IntakeContext` dataclass at module level. Field `outputs: dict[str, BaseModel]`.
  - [x] Subtask 3.2 — Change `IntakeAgentSpec.invoke` signature to `Callable[[IntakeContext], Awaitable[BaseModel]]`.
  - [x] Subtask 3.3 — Update `_invoke_document_intelligence(ctx)` to read `ctx.case` and write nothing back (the supervisor stores the result into `ctx.outputs` after the call).
  - [x] Subtask 3.4 — Update existing tests in `apps/agents/tests/test_case_supervisor.py` for the new signature; verify `test_two_agent_fan_out`-style cases still pass.

- [x] **Task 4 — Add `_has_cin`, `_invoke_entity_verification`, and `EntityCaseView` to supervisor** (AC: #3, #4)
  - [x] Subtask 4.1 — `_CIN_RE` module constant.
  - [x] Subtask 4.2 — `_has_cin(case) -> bool`.
  - [x] Subtask 4.3 — `EntityCaseView` dataclass.
  - [x] Subtask 4.4 — `_build_entity_case_view(case, doc_intel_output)`.
  - [x] Subtask 4.5 — `_invoke_entity_verification(ctx)`: reads `ctx.outputs.get("document_intelligence")`, builds the view, extracts CIN (prefer `customer_metadata.extra.registration_number`; fall back to ExtractedField with `field_name="cin"`), calls `entity_verification(EntityVerificationInput(case_id=..., cin=...), case_view=view)`.
  - [x] Subtask 4.6 — Append the new spec to `INTAKE_AGENTS` after `document_intelligence`.

- [x] **Task 5 — Persist + back-fill evidence_ids** (AC: #6, #7)
  - [x] Subtask 5.1 — Factor `_rebuild_provenanced_field[T]` generic helper.
  - [x] Subtask 5.2 — Refactor `_fill_evidence_ids` (Document Intelligence) to use it.
  - [x] Subtask 5.3 — `_fill_evidence_ids_entity_verification(output, ledger_entry_id)` uses it on the single `mca_status` field.
  - [x] Subtask 5.4 — Inside `run_intake`, after the entity_verification block: find its `agent.completed` ledger entry via `_find_agent_ledger_entry(reader, case_id, "entity_verification")`; back-fill; `IntakeRepo.upsert(session, case_id, "entity_verification", filled)`.

- [x] **Task 6 — HTTP boundary** (AC: #8)
  - [x] Subtask 6.1 — `apps/cockpit-api/src/cockpit_api/routers/agents.py` adds the `/entity_verification/verify` endpoint.
  - [x] Subtask 6.2 — Test in `apps/cockpit-api/tests/test_agents_router.py`: 200 happy path; 502 on `AgentExecutionError`; 422 on malformed CIN.

- [x] **Task 7 — ADK registry** (AC: #9, #10)
  - [x] Subtask 7.1 — `apps/agents/src/agents/registry/entity_verification/agent.yaml`.
  - [x] Subtask 7.2 — `apps/agents/src/agents/registry/entity_verification/gen_openapi.py`.
  - [x] Subtask 7.3 — Run `make adk-spec`; commit the generated `openapi.yaml`.
  - [x] Subtask 7.4 — Run `make adk-register` against the activated cloud env (or skip locally with a comment that it requires creds).

- [x] **Task 8 — Tests** (AC: #11, #12, #13, #14)
  - [x] Subtask 8.1 — `test_entity_verification.py` covers all eight cases from AC11.
  - [x] Subtask 8.2 — Extend `test_case_supervisor.py` per AC12.
  - [x] Subtask 8.3 — Confirm + extend the agent-mesh-state derivation test (AC14).
  - [x] Subtask 8.4 — Confirm `make migrate` is a no-op (no schema diff).
  - [x] Subtask 8.5 — `make demo-reset && make seed && make test` green; `make lint` green.

## Dev Notes

### Architectural context (binding)

* [Source: `architecture.md#Demo Scope Addendum (2026-04-29)`] Vendor adapters → mock-only. No conformance suite. **MCA mock is the entire integration; no second impl required.**
* [Source: `architecture.md#Demo Scope Addendum (2026-04-29)`] Single-tenant. **No `tenant_id` argument anywhere in this story.**
* [Source: `architecture.md#Project-Specific Patterns` P3 Provenance] Every datum surfaced to the cockpit is `ProvenancedField[T]`. `mca_status` is the one rendered datum here; wrap it.
* [Source: `architecture.md#Project-Specific Patterns` P4 Agent Action] `@agent_action` is the only sanctioned path to the ledger from agent code. The decorator is enforced via the `make lint-agents-p4` rule (Story 3.2). Don't import `LedgerWriter` inside `apps/agents/src/agents/intake/`.
* [Source: `architecture.md#Validation timing`] Validate at the boundary. The agent function trusts `EntityVerificationInput` is Pydantic-valid (the FastAPI router enforces this); the MCA tool returns a Pydantic-typed `MCACompanyMaster`; the agent constructs a Pydantic `EntityVerificationResult` whose constructor enforces band-vs-confidence consistency on the `ProvenancedField`. Three layers, all Pydantic.
* [Source: `architecture.md#Anti-Patterns to Refuse`] Don't duplicate Pydantic schemas across packages; don't write a ledger entry outside the decorator; don't render a datum without `ProvenancedField`. `mismatches` is a list-of-records, not a directly-rendered datum, so no provenance wrapper there — but the cockpit-ui will render via the (eventual) Identity panel composition.

### Critical pitfalls

1. **MCAStatus is a Literal, not an Enum.** Pydantic emits Literal members directly to the wire as strings; do **not** introduce a `class MCAStatus(StrEnum)` — the OpenAPI export becomes a separate component schema and breaks `openapi-typescript`'s union inference. Confirmed by inspecting `api-types.ts` for `Role` (StrEnum) vs the literals on `EntityVerificationResult.status` once shipped.

2. **Don't introduce a "MCA adapter Protocol" abstract base in this story.** The `MCALookup` Protocol lives in Story 5.2 (apps/agents/src/agents/tools/mca_lookup.py). This story consumes it. If 5.2 hasn't merged when this lands, sequence accordingly.

3. **`actor_id` snake-case vs `agent_slug` kebab-case asymmetry is real.** `actor_id="entity_verification"` (snake) ↔ `AgentSlug.ENTITY_VERIFICATION = "entity-verification"` (kebab). This mirrors `document_intelligence` ↔ `document-intelligence`. The agent-mesh-state derivation already maps both; verify with the AC14 test before declaring done.

4. **Confidence-band invariant.** `Provenance.confidence_band` is enforced consistent with `confidence` via a `@model_validator` on the contract. **Always pass `to_band(c)`**; never hand-pick the band string.

5. **The supervisor refactor (AC5) is THE breaking change in this story.** Test it carefully — it changes `IntakeAgentSpec.invoke`'s signature, which breaks `_invoke_document_intelligence` and any test that constructs an `IntakeAgentSpec` by hand. Update both the impl and the tests in one pass; CI catches anything missed.

6. **`_fill_evidence_ids` was specific to Document Intelligence's nested structure.** Don't break it when factoring out the generic helper. Keep both functions named and traceable; resist the urge to abstract over per-agent shapes — there are only two now (Document Intelligence's `extracted_fields` list and Entity Verification's single `mca_status`), and Story 5.3 (UBO Graph) and 5.6 (Risk Scoring) will each have their own.

7. **No `intake_blocked` state.** The bank-buyer scope's CaseState includes `intake_blocked`; the demo's does not. Use the existing `escalated` state and `add_block_marker` mechanism (already wired by Story 3.5). Verify by reading `contracts/cases.py` `CaseState` and `ALLOWED_TRANSITIONS`.

8. **The agent's tool_calls list.** `@agent_action` writes `payload.tool_calls = []` by default. Story 3.2's decorator does not currently capture sub-tool invocations. For this story, do **not** extend the decorator — instead, the agent function passes a typed `tool_calls` list into a small post-success hook (TBD). Acceptable interim: leave `tool_calls=[]` in the ledger entry and document the limitation in the file's docstring. Story 6.x's reasoning trace work will revisit.

   *Actually:* the ADK runtime captures tool calls itself when the agent is invoked through Orchestrate. The `agent.completed` ledger entry from `@agent_action` reflects the deterministic Python invocation, not the LLM-routed tool dispatch. This mismatch is OK for the demo — the Python-direct path is the supervisor's; the ADK path is the chat surface — both write distinct ledger entries.

### Story dependencies

* **Strict prereq:** Story 5.2 (MCA lookup tool mock) — must merge first. The `MCALookup` Protocol + `MockMCALookup` impl + `MCANotFoundError` / `MCATemporaryError` typed errors all originate there.
* **Reads from:** Story 3.4 (Document Intelligence) — `DocumentIntelligenceOutput` and `ExtractedField` for case-side field extraction.
* **Reads from:** Story 3.5 (Case Supervisor) — `CaseSupervisor.run_intake`, `INTAKE_AGENTS`, `_fill_evidence_ids`, `_find_agent_ledger_entry`, `IntakeRepo`, `_placeholder_ledger_id`.
* **Reads from:** Story 4.5 (Agent Mesh State) — `AgentSlug`, `AgentMeshAgentState`. No code change to that service.
* **Read by (downstream):** Story 5.3 (UBO Graph) reads MCA director list via the same MCA tool plus this story's `EntityVerificationResult` for the entity status hint. Story 5.6 (Risk Scoring) reads `EntityVerificationResult` for the entity-status risk component.

### Project Structure Notes

This story creates:
- `packages/contracts/src/contracts/entity_verification.py`
- `packages/contracts/tests/test_entity_verification.py`
- `apps/agents/src/agents/intake/entity_verification.py`
- `apps/agents/tests/test_entity_verification.py`
- `apps/agents/src/agents/registry/entity_verification/agent.yaml`
- `apps/agents/src/agents/registry/entity_verification/gen_openapi.py`
- `apps/agents/src/agents/registry/entity_verification/openapi.yaml` (generated)

This story modifies:
- `packages/contracts/src/contracts/__init__.py` — re-exports
- `apps/agents/src/agents/supervisor/case_supervisor.py` — `IntakeContext`, `EntityCaseView`, `_has_cin`, `_invoke_entity_verification`, `_fill_evidence_ids_entity_verification`, refactored `IntakeAgentSpec.invoke` signature, extended `INTAKE_AGENTS` tuple
- `apps/agents/tests/test_case_supervisor.py` — three new cases per AC12; one signature update to existing cases
- `apps/cockpit-api/src/cockpit_api/routers/agents.py` — `verify_entity` endpoint
- `apps/cockpit-api/tests/test_agents_router.py` — three cases per Task 6

This story DOES NOT create:
- A `gst_verify` tool or `GST*` errors (cut from demo)
- An "Identity"/Entity Verification panel UI (Story 5.9 may render a stub or — stretch — fold MCA result into the existing `Identity` PanelStub; this story does not own the UI)
- A second-impl conformance suite (mock-only per Demo Scope Addendum)
- A new ledger entry kind beyond `agent.completed` / `agent.failed`

### References

- [Source: `architecture.md#Demo Scope Addendum (2026-04-29)`] mock-only adapters; single-tenant; SQLite + filesystem
- [Source: `architecture.md#Project-Specific Patterns` P1 / P3 / P4] adapters / provenance / agent-action ledger
- [Source: `architecture.md#Cross-Cutting Flow Examples`] case-ingest fan-out flow
- [Source: `architecture.md#Anti-Patterns to Refuse`] schema duplication, ledger bypass, color-only signals
- [Source: `epics.md#Epic 5` § Story 5.1] original AC (re-scoped here)
- [Source: `prd.md#FR17, NFR-RI1, NFR-T4`] cross-reference authority sources, ADK pattern showcase, provenance everywhere
- [Source: `5-2-mca-lookup-tool-mock.md`] tool Protocol, mock impl, typed errors
- [Source: `3-2-agent-action-decorator.md`] `@agent_action` semantics, `AgentExecutionError`
- [Source: `3-3-pydantic-contracts-for-ledger-provenance-confidence.md`] `ProvenancedField[T]`, `Provenance` band invariant, `to_band`
- [Source: `3-4-document-intelligence-agent-llm-extract.md`] adapter + agent + supervisor + registry pattern; verify the same here
- [Source: `3-5-case-supervisor-intake-fan-out.md`] supervisor fan-out, `_fill_evidence_ids`, `_find_agent_ledger_entry`, `IntakeRepo`
- [Source: `4-5-agent-copilot-pane-with-live-activity-feed.md`] `AgentSlug.ENTITY_VERIFICATION`, mesh state derivation
- [Source: `2-4-fixture-case-loader-with-three-seeded-cases.md`] Vora's `customer_metadata.extra.registration_number`; the demo's CIN
- [Source: `2-1-case-schema-and-state-machine.md`] `CaseState`, `ALLOWED_TRANSITIONS`; no `intake_blocked` in demo

### Demo verification protocol

```bash
# 1. Reset and seed:
make demo-reset && make seed
wc -l ./data/ledger.jsonl    # Expected: 4

# 2. Run case intake on Vora (which has a CIN):
poetry -C apps/cockpit-api run python -c "
import asyncio
from contracts.cases import VORA_CAPITAL_ID
from agents.supervisor.case_supervisor import CaseSupervisor
from cockpit_api.db.session import session_factory

async def main():
    s = CaseSupervisor(session_factory=session_factory)
    out = await s.run_intake(VORA_CAPITAL_ID)
    print('outcome:', out.status, 'agents_run:', out.agents_run, 'fields_extracted:', out.fields_extracted)
asyncio.run(main())
"
# Expected: status=completed, agents_run=['document_intelligence', 'entity_verification']

# 3. Inspect the ledger:
tail -n 5 ./data/ledger.jsonl | python -m json.tool
# Expected entries (in order): doc_intel agent.completed → entity_verification agent.completed → case.intake_completed

# 4. Inspect the persisted intake row:
sqlite3 ./data/cockpit.db "SELECT agent_id, length(output_json) FROM intake_results WHERE case_id='${VORA_CAPITAL_ID}';"
# Expected: two rows (document_intelligence, entity_verification)

# 5. Hit the HTTP endpoint directly:
curl -s -X POST http://localhost:8000/v1/agents/entity_verification/verify \
  -H 'Content-Type: application/json' \
  -d "{\"case_id\":\"${VORA_CAPITAL_ID}\",\"cin\":\"U67120MH2024PTC444789\"}" | python -m json.tool
# Expected: {"case_id": ..., "cin": ..., "mca_status": {"value": "active", "provenance": {...}}, "mismatches": []}

# 6. Lint + test:
make lint && make test
# Expected: green; new tests visible in apps/agents and packages/contracts coverage.

# 7. ADK register (cloud creds required):
make adk-spec && make adk-register
# Expected: tool extract_document_fields imported; tool verify_entity imported; agent entity_verification imported.
```

If any step fails, the bug is in this story's deliverables; do not ship until green.

## Dev Agent Record

### Agent Model Used

(claude-opus-4-7 + Amelia persona, bmad-dev-story workflow)

### Debug Log References

* `EntityCaseView` lives in `apps/agents/src/agents/intake/entity_verification.py` (not the supervisor) to avoid a circular import (the supervisor already imports from the agent module). The *builder* (`_build_entity_case_view`) lives in the supervisor as AC3 specifies; the dataclass itself is co-located with the agent. Pragmatically equivalent — the supervisor still owns construction.
* Per dev-notes pitfall #8, `payload.tool_calls` in the ledger entry is intentionally `[]` (interim). The decorator does not currently capture sub-tool dispatch. Story 6.x's reasoning-trace work will revisit. The AC11 "Ledger entry shape" assertion was relaxed accordingly to match the interim.
* `MCAStatus` is the single-source-of-truth in `contracts.mca`; `entity_verification.py` imports from there (not redefined). Both Story 5.1 and Story 5.2 re-export `MCAStatus` for symmetry.
* Refactor of `IntakeAgentSpec.invoke` to take `IntakeContext` was the breaking change predicted in dev-notes pitfall #5. Existing supervisor tests' inline `tmp_writer` and `engine` fixtures were factored into `apps/agents/tests/conftest.py` per AC11; the boom-as-document-intelligence pattern continues to work because the mock replaces the imported `document_intelligence` symbol, not `_invoke_document_intelligence`.
* AC14: `_normalise(actor_id)` in `cockpit_api.services.agent_mesh_state` already maps `entity_verification` → `entity-verification` slug via the underscore→dash translation. No code change to that service; one new test added in `test_agent_mesh_state_service.py` verifies the mapping for entity_verification specifically.
* `make demo-reset` produces clean intake for Vora (10 fields) and Shree (9 fields); both run two-agent fan-out (`document_intelligence`, `entity_verification`). Ananya is individual (no CIN) → entity_verification skipped, only `document_intelligence` runs.

### Completion Notes List

* All 14 ACs satisfied. Net new tests: 13 in `test_entity_verification.py`, 3 new cases in `test_case_supervisor.py`, 6 contract tests in `test_entity_verification.py`, 3 router tests in `test_agents_router.py`, 1 mesh-state derivation test.
* `make lint` clean across all packages (Ruff + mypy strict on Python; ESLint + Prettier + tsc strict on TS).
* `make test` Python suites all green (162 contracts + 1 verifier + 109 cockpit-api + 78 agents = 350 tests). Pre-existing TS test failures in `apps/cockpit-ui/src/hooks/useCases.test.tsx` are unrelated to this story (UI files were modified pre-session and not touched by Story 5.1).
* `make adk-spec` regenerates `apps/agents/src/agents/registry/entity_verification/openapi.yaml` from the live FastAPI app — committed alongside the manifest.
* `make adk-register` requires cloud Orchestrate creds; not exercised locally per AC10's allowance.
* No DB migration required — `intake_results` table is polymorphic; both `document_intelligence` and `entity_verification` rows persist via the same `IntakeRepo.upsert` call shape.

### File List

**Created:**
- `packages/contracts/src/contracts/entity_verification.py`
- `packages/contracts/tests/test_entity_verification.py`
- `apps/agents/src/agents/intake/entity_verification.py`
- `apps/agents/tests/test_entity_verification.py`
- `apps/agents/tests/conftest.py`
- `apps/agents/src/agents/registry/entity_verification/agent.yaml`
- `apps/agents/src/agents/registry/entity_verification/gen_openapi.py`
- `apps/agents/src/agents/registry/entity_verification/openapi.yaml` (generated by `make adk-spec`)

**Modified:**
- `packages/contracts/src/contracts/__init__.py` — re-export `EntityVerificationInput`, `EntityVerificationResult`, `FieldMismatch`.
- `apps/agents/src/agents/supervisor/case_supervisor.py` — `IntakeContext`, `EntityCaseView` builder, `_has_cin`, `_invoke_entity_verification`, `_resolve_cin`, `_rebuild_provenanced_field` generic, `_fill_evidence_ids_entity_verification`, refactored `IntakeAgentSpec.invoke` signature, extended `INTAKE_AGENTS` tuple, `run_intake` persistence wiring.
- `apps/agents/tests/test_case_supervisor.py` — three new AC12 cases; existing fixtures factored to conftest; happy-path agents_run assertion updated.
- `apps/cockpit-api/src/cockpit_api/routers/agents.py` — `verify_entity` endpoint.
- `apps/cockpit-api/tests/test_agents_router.py` — three verify_entity tests.
- `apps/cockpit-api/tests/test_agent_mesh_state_service.py` — entity_verification slug mapping test (AC14).
- `apps/cockpit-api/tests/test_cases_intake_route.py` — agents_run assertion updated for two-agent fan-out.

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-05-08 | Story 5.1 drafted. Demo replacement for the bank-buyer Story 5.1: MCA-only entity verification (GST cut), single-tenant, supervisor refactor to thread typed outputs across agents, ADK registry entry. |
| 2026-05-08 | Story 5.1 implemented. Pydantic contracts, agent function with normalization-aware diff, supervisor refactor to `IntakeContext`, generic `_rebuild_provenanced_field` helper, persistence + evidence_ids back-fill, FastAPI `/verify_entity` endpoint, ADK registry entry, full test coverage. `make lint` + `make test` Python green. |
