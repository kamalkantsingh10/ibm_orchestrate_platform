# Story 5.3: UBO Graph agent (basic)

Status: review

## Story

As the platform,
I want a UBO Graph agent that — given a case where Entity Verification has resolved an MCA company-master — constructs a `UBOGraph` Pydantic model with typed nodes (Person | Entity) and edges (Owns | Director | Beneficial), each edge carrying a `ProvenancedField` and a `nominee_suspected` flag derived from a small set of demo heuristics, and writes the typed output via `@agent_action`,
So that Story 5.4's UBO Canvas component can render the force-directed graph visually, Story 5.5's drag-correct interaction has typed edges to mutate, and Story 5.6's Risk Scoring agent has an "ownership_clarity" signal to consume (FR15, FR16, NFR-RI1, NFR-T5 ≥ 95% structural — relaxed for demo, P3, P4).

## Scope note (2026-04-29 demo re-scope)

This story is the demo-equivalent of the bank-buyer Story 5.4. The bank-buyer scope mandated ≥ 95% structural accuracy on a 50-graph corpus; the demo retains the **typed Pydantic UBOGraph + nominee heuristic + provenance per edge** and ships against the deterministic MCA mock (Story 5.2) — there is no benchmark.

| Bank-buyer scope (original 5.4) | Demo replacement in this story |
|---|---|
| ML-augmented graph extraction across MCA + GST + adverse-media corpora | **Deterministic graph-from-MCA-master.** No ML. Construction is `MCACompanyMaster → UBOGraph` over a small typed builder. |
| 50-graph corpus benchmark with ≥ 95% structural accuracy | **Cut.** Tests assert exact graph shape against the two demo CINs (Vora, Shree) and three failure paths. |
| Heuristic for nominee detection includes shared-address + filing-agent registry + ML similarity | **Three deterministic rules** per AC4. No external registry, no similarity. |
| Tenant-scoped | Single-tenant. |

What survives: **typed `UBOGraph`, typed `UBONode` discriminated union (`Person` vs `Entity`), typed `UBOEdge` discriminated union (`Owns` vs `Director` vs `Beneficial`), `ProvenancedField` on every edge confidence, deterministic three-rule nominee heuristic, supervisor fan-out, ADK registry entry, agent_slug `ubo-graph`.**

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md` § Stories simplified, `architecture.md#Demo Scope Addendum (2026-04-29)`, `epics.md#Epic 5`.

## Acceptance Criteria

1. **AC1 — Pydantic contracts at `packages/contracts/src/contracts/ubo.py`.**

    ```python
    from typing import Annotated, Literal
    from pydantic import BaseModel, Field, StringConstraints

    # ───── identifiers ─────
    _UBO_NODE_ID_PATTERN = r"^ubo_(p|e)_[A-Za-z0-9_-]{1,64}$"   # ubo_p_<slug> for person, ubo_e_<slug> for entity
    UBONodeId = Annotated[str, StringConstraints(pattern=_UBO_NODE_ID_PATTERN, min_length=7, max_length=72)]

    # ───── nodes (discriminated union on `kind`) ─────
    class UBOPersonNode(BaseModel):
        model_config = {"frozen": True}
        kind: Literal["person"] = "person"
        id: UBONodeId
        name: str = Field(min_length=1)
        din: str | None = Field(default=None, pattern=r"^\d{8}$")
        country: str | None = None

    class UBOEntityNode(BaseModel):
        model_config = {"frozen": True}
        kind: Literal["entity"] = "entity"
        id: UBONodeId
        name: str = Field(min_length=1)
        cin: str | None = None
        country: str | None = None
        is_corporate: bool = True       # for entity nodes; redundant but explicit

    UBONode = UBOPersonNode | UBOEntityNode

    # ───── edges (discriminated union on `kind`) ─────
    EdgeKind = Literal["owns", "director", "beneficial"]
    NomineeFlag = Literal["clear", "nominee_suspected", "officer_corrected"]

    class UBOEdge(BaseModel):
        model_config = {"frozen": True}
        kind: EdgeKind
        from_id: UBONodeId             # source node (the holder / appointer)
        to_id: UBONodeId               # target node (the held / appointee)
        ownership_pct: float | None = Field(default=None, ge=0.0, le=100.0)  # only for kind="owns" / "beneficial"
        designation: Literal["director", "managing_director", "additional_director", "nominee_director"] | None = None  # only for kind="director"
        confidence: ProvenancedField[float]    # the edge's confidence + provenance
        nominee_flag: NomineeFlag = "clear"
        rationale: str | None = None    # short reason when nominee_flag != "clear"

    # ───── graph aggregate ─────
    class UBOGraph(BaseModel):
        model_config = {"frozen": True}
        case_id: CaseId
        root_entity_id: UBONodeId      # the case's primary entity — must be present in `nodes`
        nodes: list[UBONode] = Field(default_factory=list)
        edges: list[UBOEdge] = Field(default_factory=list)

    class UBOGraphInput(BaseModel):
        model_config = {"frozen": True}
        case_id: CaseId
        cin: str = Field(min_length=21, max_length=21)
    ```

    **Validators:**
    * On `UBOGraph`: `@model_validator(mode="after")` checks (a) `root_entity_id` is in `{n.id for n in nodes}`; (b) every edge's `from_id` and `to_id` exist in `nodes`; (c) no duplicate edges (same `(kind, from_id, to_id)`); (d) sum of `ownership_pct` over `kind="owns"` edges sharing a `to_id` is ≤ 100.0 (within 0.5 tolerance for rounding); raise `ValueError` with a descriptive message on any violation.
    * On `UBOEdge`: `@model_validator(mode="after")`: `kind="owns"` and `kind="beneficial"` require `ownership_pct` non-None; `kind="director"` requires `designation` non-None and `ownership_pct` None.

    Re-export from `packages/contracts/src/contracts/__init__.py`. Names to add to `__all__`: `EdgeKind`, `NomineeFlag`, `UBOEdge`, `UBOEntityNode`, `UBOGraph`, `UBOGraphInput`, `UBONode`, `UBONodeId`, `UBOPersonNode`.

2. **AC2 — Node ID conventions.** Stable, deterministic, **derivable from MCA data**:

    * **Entity (root):** `ubo_e_<lowercase-slug-of-cin>` — e.g., `ubo_e_u67120mh2024ptc444789`.
    * **Entity (shareholder corporate):** `ubo_e_<lowercase-slug-of-name>` — slugify by lowercasing, replacing whitespace + non-alphanumeric with `_`, collapsing runs of `_`, trimming leading/trailing `_`. E.g., `Coastal Equity Partners Pte Ltd` → `ubo_e_coastal_equity_partners_pte_ltd`.
    * **Person (director):** `ubo_p_<din>` if DIN is present; otherwise `ubo_p_<lowercase-slug-of-name>`.
    * **Person (individual shareholder):** same rule.

    Build a small `_slugify(s: str) -> str` helper in the agent module. Test cases: `"Devansh Vora"` → `"devansh_vora"`; `"A K Filing Services"` → `"a_k_filing_services"`; `"Anchor Trust Services (BVI)"` → `"anchor_trust_services_bvi"` (parentheses stripped, not preserved).

    The `id` regex `^ubo_(p|e)_[A-Za-z0-9_-]{1,64}$` is case-insensitive on `[A-Za-z]` but the slugifier always lowercases. Don't break this when adding a director with a DIN that has letters (DINs are 8 digits — pure numeric — but the regex permits letters for future-proofing).

3. **AC3 — Construction algorithm at `apps/agents/src/agents/intake/ubo_graph.py`.**

    ```python
    @agent_action(
        agent_id="ubo_graph",
        model_id="deterministic",
        prompt_template_id=None,
    )
    async def ubo_graph(
        input: UBOGraphInput,
        *,
        mca: MCALookup | None = None,
    ) -> UBOGraph: ...
    ```

    Algorithm:
    1. Resolve `mca = mca or get_default_mca_lookup()` (Story 5.2's resolver).
    2. Call `master = await mca.lookup(cin=input.cin)`. Same typed-error semantics as Story 5.1 — `MCANotFoundError` and `MCATemporaryError` propagate; `@agent_action` wraps as `AgentExecutionError`; supervisor handles.
    3. Build the **root entity node** from `master`:
       ```python
       root = UBOEntityNode(
           id=_entity_id_from_cin(master.cin),
           name=master.company_name,
           cin=master.cin,
           country="IN",  # all demo MCAs are IN
           is_corporate=True,
       )
       nodes = [root]
       edges: list[UBOEdge] = []
       ```
    4. **Append director nodes + director edges** for each `MCADirector`:
       * Person node with `id` per AC2; `din` and `name` from MCA; `country=None` (MCA records don't carry directors' nationality).
       * Director edge `(from_id=person.id, to_id=root.id, kind="director", designation=master_director.designation, confidence=ProvenancedField(value=0.95, provenance=...HIGH...))`.
    5. **Append shareholder nodes + ownership edges** for each `MCAShareholder`:
       * If `is_corporate=True`: emit a `UBOEntityNode`; if False: emit a `UBOPersonNode`.
       * Owns edge `(from_id=shareholder.id, to_id=root.id, kind="owns", ownership_pct=master_sh.ownership_pct, confidence=ProvenancedField(value=0.92, provenance=...HIGH...))`.
    6. **Apply nominee heuristics** per AC4 — mutate the just-built edges' `nominee_flag` and `rationale`.
    7. Return `UBOGraph(case_id=input.case_id, root_entity_id=root.id, nodes=nodes, edges=edges)`.

    **Confidence on edges:** `0.95` for director edges (DIN-backed, MCA-authoritative) and `0.92` for shareholder edges (MCA-authoritative but pre-nominee-correction). When the nominee heuristic flips the edge to `nominee_suspected`, **drop the confidence to `0.55`** (MEDIUM_LOW band) on that edge. The `confidence_band` is recomputed via `to_band(confidence)` at construction (Pydantic invariant from `Provenance` — Story 3.3 § AC3).

4. **AC4 — Nominee-suspected heuristics (three deterministic rules).**

    Apply post-construction. For each edge of `kind="owns"` or `kind="director"`:

    * **R1 — Foreign corporate majority holder.** If edge is `kind="owns"` AND `from` is `UBOEntityNode` AND `from.country` is non-`None` AND `from.country != "IN"` AND `ownership_pct >= 25.0`:
      `edge.nominee_flag = "nominee_suspected"`, `rationale = f"Foreign corporate holder ({from.country}) with {ownership_pct}% ownership; structure suggests nominee/shell"`.
    * **R2 — Nominee-director designation.** If edge is `kind="director"` AND `designation == "nominee_director"`:
      `edge.nominee_flag = "nominee_suspected"`, `rationale = "MCA explicitly designates appointment as nominee_director"`.
    * **R3 — Trust-services entity name.** If `from` is `UBOEntityNode` AND `"trust" in from.name.lower() or "nominee" in from.name.lower()`:
      `edge.nominee_flag = "nominee_suspected"`, `rationale = f"Holder name '{from.name}' contains nominee/trust signal"`.

    **Rules compose** — an edge can be flagged by multiple rules; the first-matching rule's rationale wins. Document the precedence order (R1 → R2 → R3) inline in the agent file.

    **Demo expected nominee_suspected edges on Vora's graph:**
    * `Coastal Equity Partners Pte Ltd → Vora Capital` (owns, 70.0%) — flagged by R1 (SG, ≥25%).
    * `Anchor Trust Services (BVI) → Vora Capital` (owns, 25.0%) — flagged by R1 (VG, ≥25%) AND R3 (trust). R1 fires first.
    * `A K Filing Services → Vora Capital` (director, nominee_director) — flagged by R2.

    **Demo expected nominee_suspected edges on Shree's graph:** none. Both directors and both shareholders are IN individuals; no foreign corporates; no trust-services names.

    Build a `_apply_nominee_heuristics(edges, nodes) -> list[UBOEdge]` pure helper that returns a new list (frozen-Pydantic-friendly). Tests assert against the exact pinned list.

5. **AC5 — Supervisor wires `ubo_graph` into `INTAKE_AGENTS`.** Order: doc_intel → entity_verification → ubo_graph → (Story 5.6 risk_scoring will append after).

    ```python
    IntakeAgentSpec(
        name="ubo_graph",
        invoke=_invoke_ubo_graph,
        requires=_has_cin,        # same predicate as Story 5.1
    )
    ```

    `_invoke_ubo_graph(ctx)` reads `ctx.outputs["entity_verification"]` for the resolved CIN — fall back to the case's `customer_metadata.extra.registration_number` if entity_verification was skipped (e.g., individual customer with no CIN — but `_has_cin=False` already filters). Build `UBOGraphInput(case_id=ctx.case.id, cin=cin)` and call `ubo_graph(input)`.

    Persist via `IntakeRepo.upsert(session, case_id, "ubo_graph", graph_output)`.

6. **AC6 — Evidence_id back-fill on every edge.**

    Each edge has its own `confidence: ProvenancedField[float]` with empty `evidence_ids` at agent-return time. Supervisor's back-fill (Story 3.5 pattern + Story 5.1's generic helper) iterates the edges and rebuilds each `confidence` with `evidence_ids=[entry.id]`.

    Add to supervisor:
    ```python
    def _fill_evidence_ids_ubo_graph(graph: UBOGraph, ledger_entry_id: LedgerEntryId) -> UBOGraph:
        new_edges = [
            edge.model_copy(update={"confidence": _rebuild_provenanced_field(edge.confidence, [ledger_entry_id])})
            for edge in graph.edges
        ]
        return graph.model_copy(update={"edges": new_edges})
    ```

7. **AC7 — HTTP boundary at `POST /v1/agents/ubo_graph/build`.**

    ```python
    @router.post(
        "/ubo_graph/build",
        response_model=UBOGraph,
        summary="Build the UBO graph for a case",
        description=(
            "Calls the UBO Graph agent. Looks the CIN up via the mca_lookup "
            "tool, builds typed nodes + edges with the nominee heuristic, "
            "returns the graph. Every invocation writes one ledger entry."
        ),
    )
    async def build_ubo_graph(payload: UBOGraphInput) -> UBOGraph:
        try:
            return await ubo_graph(payload)
        except AgentExecutionError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
    ```

    Test in `apps/cockpit-api/tests/test_agents_router.py`: 200 happy path on Vora; 502 on a magic-temporary CIN; 422 on malformed input.

8. **AC8 — ADK registry entry at `apps/agents/src/agents/registry/ubo_graph/`.**

    Mirror Story 5.1 § AC9. Three files: `agent.yaml`, `gen_openapi.py`, `openapi.yaml` (generated). The agent's `instructions:` should briefly describe what UBO graphs are and direct the LLM to call `build_ubo_graph` with `case_id` + `cin`. `tools: [build_ubo_graph]`. No collaborators.

9. **AC9 — TypeScript hook at `apps/cockpit-ui/src/hooks/useUboGraph.ts`.**

    ```typescript
    import { useQuery } from '@tanstack/react-query';
    import { apiClient } from '@/lib/api';
    import type { components } from '@/api-types';

    type UBOGraph = components['schemas']['UBOGraph'];

    export function useUboGraph(caseId: string) {
        return useQuery<UBOGraph>({
            queryKey: ['cases', caseId, 'intake', 'ubo_graph'],
            queryFn: async () => {
                const { data, error } = await apiClient.GET('/v1/cases/{case_id}/intake/{agent_id}', {
                    params: { path: { case_id: caseId, agent_id: 'ubo_graph' } },
                });
                if (error) throw new Error(typeof error === 'object' ? JSON.stringify(error) : String(error));
                return data as UBOGraph;
            },
        });
    }
    ```

    **Prerequisite:** `GET /v1/cases/{case_id}/intake/{agent_id}` must already exist (Story 3.6 added it for document_intelligence; verify the route is generic). If not generic, extend its handler to accept any agent_id and return the persisted IntakeRepo blob — this is a single-line change in `apps/cockpit-api/src/cockpit_api/routers/cases.py`.

    Add `useUboGraph` to the route component so `cases.$caseId.tsx` can pass the graph into the (future) `UBOPanel`. The UI rendering itself is Story 5.4; this story ships only the typed hook.

10. **AC10 — Tests in `apps/agents/tests/test_ubo_graph.py`.** Cover:

    * **Vora — happy path:** call against Vora's CIN; assert 6 nodes (1 root + 3 directors + 2 shareholders that aren't already a director — Devansh appears as both, dedupe by `id`); assert 5 edges (3 director + 3 owns) — wait, Devansh is both a director and a 5% shareholder. **Dedupe rule:** if a person appears as both director and shareholder, emit ONE node + TWO edges (one director, one owns). Pin the test to the exact node-and-edge count: **6 nodes**, **5 edges**, **3 nominee_suspected**.

    Restated counts for Vora:
    * Nodes: 1 root entity + 3 directors (`Devansh Vora`, `Rohan Mehta`, `A K Filing Services`) + 2 corporate shareholders (`Coastal Equity Partners Pte Ltd`, `Anchor Trust Services (BVI)`) — total 6. (Devansh appears as a 5% shareholder and a director; he gets ONE person node, TWO edges.)
    * Edges: 3 director (one per director) + 3 owns (Devansh + Coastal + Anchor) — total 6. *Correction from above: 6 edges, not 5.*
    * Nominee suspected: 3 (Coastal R1, Anchor R1, A K Filing R2).

    * **Shree — happy path:** 5 nodes (1 root + 2 directors + 2 individual shareholders, both directors are also shareholders so dedupe to 2 person nodes), 4 edges (2 director + 2 owns), 0 nominee_suspected.

    * **CIN-not-in-MCA:** stub `MockMCALookup.lookup` to raise `MCANotFoundError`; assert `AgentExecutionError`.
    * **Tool unavailable:** stub to raise `MCATemporaryError`; assert `AgentExecutionError`.
    * **Validator catches dangling edge:** construct a `UBOGraph` directly with an edge whose `from_id` points to a non-existent node; assert `ValidationError`.
    * **Validator catches duplicate edge:** assert `ValidationError`.
    * **Validator catches ownership > 100%:** assert `ValidationError`.
    * **Slugify helper:** assert each of the table cases from AC2.
    * **Heuristic R1 / R2 / R3 isolation:** craft three minimal MCAs that each trigger only one rule; assert the rationale text.
    * **Heuristic precedence:** craft an MCA where R1 and R3 both apply; assert R1's rationale wins.
    * **Confidence drop on flagging:** assert that flagged edges have `confidence.value == 0.55` and `confidence_band == MEDIUM_LOW`.
    * **Ledger entry shape:** assert the ledger entry has `payload.agent_id == "ubo_graph"`, `payload.output.root_entity_id == ubo_e_<vora-cin-slug>`.
    * **Evidence ID back-fill:** end-to-end via supervisor; assert every edge's `confidence.provenance.evidence_ids == [agent_completed_id]`.
    * **Supervisor: three-agent fan-out** (doc_intel + entity_verification + ubo_graph): all three succeed; case transitions to `decision_ready`; ledger has 4 entries (3 agent.completed + 1 case.intake_completed).
    * **Supervisor: ubo_graph fails after entity_verification succeeded:** `agents_run = ["document_intelligence", "entity_verification", "ubo_graph"]`, `failed_agent = "ubo_graph"`, case transitions to `escalated`.

11. **AC11 — Contract tests in `packages/contracts/tests/test_ubo.py`.** Round-trip the typed graph; assert each `@model_validator` rejection case from AC1.

12. **AC12 — `make demo-reset && make seed && make test` clean.** Net new test count: ≥ 14 in `test_ubo_graph.py`, ≥ 5 in `test_ubo.py`, ≥ 1 supervisor test. `make adk-spec && make adk-register` succeed against the activated cloud env.

13. **AC13 — agent-mesh-state derivation already maps the slug.** `actor_id="ubo_graph"` ↔ `AgentSlug.UBO_GRAPH = "ubo-graph"`. Add the mapping to the helper in `apps/cockpit-api/src/cockpit_api/services/agent_mesh_state.py` if absent (single-line change, mirrors Story 5.1 § AC14).

14. **AC14 — `Vora` ⇒ `nominee_flag="nominee_suspected"` is load-bearing for Story 5.5's drag-correct demo.** The Coastal edge MUST land as `nominee_suspected` because Story 5.5's narrative is "officer drag-corrects the Coastal edge to `real_ubo`" — that's the demo arc. Don't relax R1's threshold below 25%.

## Tasks / Subtasks

- [x] **Task 1 — Author Pydantic contracts** (AC: #1, #2)
  - [x] Subtask 1.1 — `packages/contracts/src/contracts/ubo.py` with all types + validators.
  - [x] Subtask 1.2 — Re-export from `__init__.py`.
  - [x] Subtask 1.3 — `packages/contracts/tests/test_ubo.py` covers AC11.

- [x] **Task 2 — Author the agent function** (AC: #3, #4)
  - [x] Subtask 2.1 — `apps/agents/src/agents/intake/ubo_graph.py` with `_slugify`, `_entity_id_from_cin`, `_apply_nominee_heuristics`, `ubo_graph` decorated function.
  - [x] Subtask 2.2 — Three rules R1/R2/R3 implemented per AC4 with documented precedence.
  - [x] Subtask 2.3 — Confidence drop to `0.55` on flagged edges.

- [x] **Task 3 — Wire the supervisor** (AC: #5, #6)
  - [x] Subtask 3.1 — `_invoke_ubo_graph(ctx)`; reads CIN from prior outputs.
  - [x] Subtask 3.2 — Append spec to `INTAKE_AGENTS` after `entity_verification`.
  - [x] Subtask 3.3 — `_fill_evidence_ids_ubo_graph(graph, ledger_entry_id)` using the generic helper from Story 5.1.
  - [x] Subtask 3.4 — Persist via `IntakeRepo.upsert(session, case_id, "ubo_graph", filled_graph)`.

- [x] **Task 4 — HTTP boundary + ADK registry** (AC: #7, #8)
  - [x] Subtask 4.1 — `apps/cockpit-api/src/cockpit_api/routers/agents.py`: `/ubo_graph/build` endpoint.
  - [x] Subtask 4.2 — Test in `test_agents_router.py`.
  - [x] Subtask 4.3 — `apps/agents/src/agents/registry/ubo_graph/agent.yaml`.
  - [x] Subtask 4.4 — `apps/agents/src/agents/registry/ubo_graph/gen_openapi.py`.
  - [x] Subtask 4.5 — `make adk-spec` regenerates the openapi.yaml; commit.

- [x] **Task 5 — TypeScript hook** (AC: #9)
  - [x] Subtask 5.1 — Run `make contracts` (or equivalent) to regenerate `apps/cockpit-ui/src/api-types.ts` so `UBOGraph` appears.
  - [x] Subtask 5.2 — `apps/cockpit-ui/src/hooks/useUboGraph.ts`.
  - [x] Subtask 5.3 — Verify `GET /v1/cases/{case_id}/intake/{agent_id}` is generic (Story 3.6); extend if the route is hardcoded to `document_intelligence`.

- [x] **Task 6 — Tests** (AC: #10, #11, #12, #13)
  - [x] Subtask 6.1 — `test_ubo_graph.py` covers all 14 cases from AC10.
  - [x] Subtask 6.2 — Extend `test_case_supervisor.py` for the four-agent path (or three, since risk_scoring lands in Story 5.6).
  - [x] Subtask 6.3 — Extend `test_agent_mesh_state.py` for the `ubo_graph` slug.

## Dev Notes

### Architectural context (binding)

* [Source: `architecture.md#Demo Scope Addendum (2026-04-29)`] mock-only adapters, single-tenant, deterministic.
* [Source: `architecture.md#Project-Specific Patterns` P3] every confidence is a `ProvenancedField`. Each edge carries one. `to_band(c)` enforces the band invariant.
* [Source: `architecture.md#Project-Specific Patterns` P4] `@agent_action` is the only path to the ledger. The agent function emits a single `agent.completed` entry per call.
* [Source: `ux-design-specification.md` § UBOCanvas] UI uses react-flow. The `UBOGraph` Pydantic model shape is **NOT** react-flow's native shape — Story 5.4 will adapt at the rendering boundary. Don't pre-empt that here.
* [Source: `ux-design-specification.md` § Confidence bands never rely on color alone] each edge's `nominee_flag` carries a typed value (`clear` / `nominee_suspected` / `officer_corrected`); the UI uses both color and dashing pattern (Story 5.4 AC).

### Critical pitfalls

1. **Discriminated unions in Pydantic 2 require explicit `Literal` discriminator.** `kind: Literal["person"]` on `UBOPersonNode` and `kind: Literal["entity"]` on `UBOEntityNode`, and the type alias `UBONode = UBOPersonNode | UBOEntityNode` — Pydantic resolves left-to-right by `kind`. Same for `UBOEdge.kind`. **Don't** add a `Field(..., discriminator="kind")` — that's only required when the union is wrapped in a parent BaseModel; here the union is the direct list element type.

2. **Dedupe by `id`, not by name.** A person can appear as both a director and a shareholder. Build the node list as a `dict[UBONodeId, UBONode]` keyed by `id`; the `id` derivation (DIN-or-slug) makes Devansh deterministically appear once.

3. **`country` is None for directors.** MCA records don't carry director nationality. Don't fabricate `"IN"`. The R1 heuristic only fires on shareholder edges, so this is fine.

4. **Vora's nominee count is exactly 3.** If your test count comes back at 2 or 4, the heuristic has a bug — debug before relaxing the assertion.

5. **`UBOGraph` validators are strict — write the agent to construct nodes-then-edges in that order.** A naive construction that adds edges first would fail validation. Build a `dict[UBONodeId, UBONode]` first, then iterate it to emit edges; the validator passes because all edge endpoints are already in the dict.

6. **Don't import `MCALookup` from `apps/agents/src/agents/intake/`** — keep agent-internal imports clean. Import from `agents.tools.mca_lookup` (the Protocol module).

7. **`UBOGraphInput.cin` regex is intentionally less strict than `EntityVerificationInput.cin`** — UBO Graph might in the future accept LLP CINs (different prefix). For now keep both at the same regex but document the intent. Don't over-tighten.

8. **`@model_validator(mode="after")` on `UBOGraph` runs once at construction.** Because Pydantic validators on frozen models can't mutate, **return self unchanged**; raise on violation. Don't try to "fix" the graph in the validator.

9. **The graph must be deterministic across runs.** Sort directors and shareholders by name (or by DIN, then name) before emitting nodes/edges, so the test assertions can pin the exact list. Don't rely on dict insertion order across Python implementations.

10. **`_apply_nominee_heuristics` mutates the rationale text.** Pin the rationale strings exactly in tests — they show up in the UI tooltip (Story 5.4) and downstream Risk Scoring rationale (Story 5.6). Stable strings = stable tests.

### Story dependencies

* **Strict prereqs:** Story 5.2 (MCA mock) for `MCALookup`, `MCACompanyMaster`, typed errors. Story 5.1 (Entity Verification) for the supervisor refactor (`IntakeContext`, `IntakeAgentSpec.invoke` signature).
* **Reads from:** Story 3.5 (Case Supervisor), Story 4.5 (AgentSlug), Story 3.6 (intake API endpoint pattern).
* **Read by:** Story 5.4 (UBO Canvas), Story 5.5 (drag-correct), Story 5.6 (Risk Scoring — uses UBO graph for ownership_clarity component).

### Project Structure Notes

This story creates:
- `packages/contracts/src/contracts/ubo.py`
- `packages/contracts/tests/test_ubo.py`
- `apps/agents/src/agents/intake/ubo_graph.py`
- `apps/agents/tests/test_ubo_graph.py`
- `apps/agents/src/agents/registry/ubo_graph/agent.yaml`
- `apps/agents/src/agents/registry/ubo_graph/gen_openapi.py`
- `apps/agents/src/agents/registry/ubo_graph/openapi.yaml` (generated)
- `apps/cockpit-ui/src/hooks/useUboGraph.ts`

This story modifies:
- `packages/contracts/src/contracts/__init__.py` — re-exports
- `apps/agents/src/agents/supervisor/case_supervisor.py` — `_invoke_ubo_graph`, `_fill_evidence_ids_ubo_graph`, `INTAKE_AGENTS` extension
- `apps/cockpit-api/src/cockpit_api/routers/agents.py` — `/ubo_graph/build` endpoint
- `apps/cockpit-api/src/cockpit_api/services/agent_mesh_state.py` — slug mapping (if absent)
- `apps/cockpit-api/src/cockpit_api/routers/cases.py` — generic `intake/{agent_id}` route (if hardcoded today)

This story DOES NOT create:
- The UBO Canvas component (Story 5.4)
- The drag-correct interaction (Story 5.5)
- A second-impl conformance suite

### References

- [Source: `architecture.md#Demo Scope Addendum (2026-04-29)`] mock-only, single-tenant
- [Source: `architecture.md#Project-Specific Patterns` P3 / P4] provenance + agent-action
- [Source: `architecture.md#Cross-Cutting Flow Examples`] case ingest fan-out
- [Source: `ux-design-specification.md` § UBOCanvas] target UI shape — informs but does not constrain the Pydantic model
- [Source: `epics.md#Epic 5` § Story 5.4] original AC (re-scoped here)
- [Source: `prd.md#FR15, FR16`] UBO graph + drag-correct
- [Source: `5-2-mca-lookup-tool-mock.md`] Vora's pinned shareholder pattern (load-bearing for AC4)
- [Source: `5-1-entity-verification-agent.md`] supervisor `IntakeContext` refactor; `_rebuild_provenanced_field` helper
- [Source: `3-5-case-supervisor-intake-fan-out.md`] supervisor fan-out + ledger back-fill pattern
- [Source: `4-5-agent-copilot-pane-with-live-activity-feed.md`] AgentSlug, mesh-state derivation

### Demo verification protocol

```bash
make demo-reset && make seed
poetry -C apps/cockpit-api run python -c "
import asyncio
from contracts.cases import VORA_CAPITAL_ID
from agents.supervisor.case_supervisor import CaseSupervisor
from cockpit_api.db.session import session_factory

async def main():
    out = await CaseSupervisor(session_factory=session_factory).run_intake(VORA_CAPITAL_ID)
    print('outcome:', out.status, 'agents_run:', out.agents_run)
asyncio.run(main())
"
# Expected: outcome=completed, agents_run=['document_intelligence', 'entity_verification', 'ubo_graph']

# Inspect the persisted UBO graph:
sqlite3 ./data/cockpit.db "SELECT json_extract(output_json, '\$.edges') FROM intake_results WHERE case_id='${VORA_CAPITAL_ID}' AND agent_id='ubo_graph';" | python -m json.tool | grep -c nominee_suspected
# Expected: 3

# HTTP endpoint:
curl -s -X POST http://localhost:8000/v1/agents/ubo_graph/build \
  -H 'Content-Type: application/json' \
  -d "{\"case_id\":\"${VORA_CAPITAL_ID}\",\"cin\":\"U67120MH2024PTC444789\"}" | python -m json.tool | head -50

# ADK register:
make adk-spec && make adk-register
```

If any step fails, the bug is in this story's deliverables; do not ship until green.

## Dev Agent Record

### Agent Model Used

(claude-opus-4-7 + Amelia persona, bmad-dev-story workflow)

### Debug Log References

### Completion Notes List

### File List

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-05-08 | Story 5.3 drafted. Demo replacement for the bank-buyer Story 5.4: deterministic graph-from-MCA-master, three nominee-detection rules, single-tenant, evidence_id back-fill on every edge, ADK registry entry. |
