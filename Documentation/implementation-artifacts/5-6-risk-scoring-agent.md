# Story 5.6: Risk Scoring agent

Status: review

## Story

As the platform,
I want a Risk Scoring agent that — given a case where Document Intelligence (Story 3.4), Entity Verification (Story 5.1), and UBO Graph (Story 5.3) have all run — decomposes risk into named contributing components (country, entity_type, ownership_clarity, screening_placeholder, adverse_media_placeholder) with a final 0–100 total + low/medium/high band, writes a typed `RiskScore` to `IntakeRepo`, denormalizes the band onto the `Case.risk_band` column, and writes its full invocation as an `agent.completed` ledger entry,
So that Story 5.7's Risk Score stacked-bar UI can render the decomposition with hover detail, Story 5.8's auto-recalc on officer correction has an idempotent re-runnable agent, the analyst sees not just a number but a stacked explanation of risk drivers, and the case's `risk_band` shifts in the queue rail per Story 4.1 (FR20, FR21, NFR-RI1 ADK pattern showcase, P3, P4, P7).

## Scope note (2026-04-29 demo re-scope)

This story is the demo-equivalent of the bank-buyer Story 5.7. The bank-buyer scope folded in screening + adverse_media as load-bearing components; the demo retains them as **placeholder components with deterministic baseline values** (Story 6.x will fill them in). The risk weights are demo-calibrated to produce visible band variation across the three demo cases.

| Bank-buyer scope (original 5.7) | Demo replacement in this story |
|---|---|
| `model_id` + `prompt_template_id` from a real LLM-driven scoring model | **Deterministic Python rule-based scoring.** `model_id="deterministic"`, `prompt_template_id=None`. No LLM call. The "model" is the weighted sum of components. |
| Screening + adverse media components live and read by the agent | **Placeholder components** — for the demo, both contribute zero unless the case fixture's `customer_metadata.extra` carries a `screening_hit_hint` (Ananya's case) or an `adverse_media_hint`. When present, they bump risk modestly but never dominate. |
| Per-jurisdiction risk weights from `apps/agents/src/agents/jurisdictions/india/risk_weights.yaml` | **Hard-coded Python constants** at the top of the agent module. Document the move; revival is trivial. |
| Calibration study; thresholds tuned over a corpus | **Pinned thresholds** — band derivation `low: 0–34`, `medium: 35–69`, `high: 70–100`. Three components: `country=10`, `entity_type=15-30`, `ownership_clarity=0-40`. Sum is in [25, 80] across the demo cases. |
| Tenant-scoped | Single-tenant. |

What survives: **`RiskScore` Pydantic contract with `total`, `band`, `components: list[RiskComponent]`, each component has `name`, `value`, `weight`, `contribution`, `rationale`. Provenance on the total. Supervisor fan-out integration. ADK registry entry. agent_slug `risk-scoring`.**

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md` § Stories simplified, `architecture.md#Demo Scope Addendum (2026-04-29)`, `epics.md#Epic 5` § Story 5.7.

## Acceptance Criteria

1. **AC1 — Pydantic contracts at `packages/contracts/src/contracts/risk.py`.**

    ```python
    from typing import Literal
    from pydantic import BaseModel, Field

    RiskBand = Literal["low", "medium", "high"]
    RiskComponentName = Literal["country", "entity_type", "ownership_clarity", "screening", "adverse_media"]

    class RiskComponent(BaseModel):
        model_config = {"frozen": True}
        name: RiskComponentName
        value: float = Field(ge=0.0, le=100.0)        # raw component score before weighting
        weight: float = Field(ge=0.0, le=1.0)         # contribution weight (sums to 1.0 across components)
        contribution: float = Field(ge=0.0, le=100.0) # value * weight (precomputed to keep wire format self-contained)
        rationale: str = Field(min_length=1, max_length=200)

    class RiskScore(BaseModel):
        model_config = {"frozen": True}
        case_id: CaseId
        total: int = Field(ge=0, le=100)              # 0–100, integer (UI renders as a stacked bar; rounding to int once is friendlier)
        band: RiskBand
        components: list[RiskComponent] = Field(default_factory=list)
        score_provenance: ProvenancedField[float]     # the total as a float [0.0, 1.0] for P3 compliance

    class RiskScoringInput(BaseModel):
        model_config = {"frozen": True}
        case_id: CaseId
    ```

    **Validators on `RiskScore`:**
    * `@model_validator(mode="after")` — assert `sum(c.weight for c in components)` is 1.0 ± 0.01 (rounding tolerance).
    * `@model_validator(mode="after")` — assert `total == round(sum(c.contribution for c in components))` ± 1 (rounding tolerance for the integer total vs floating contributions).
    * `@model_validator(mode="after")` — assert `band` matches `total`: `band="low"` requires `total ≤ 34`; `band="medium"` requires `35 ≤ total ≤ 69`; `band="high"` requires `total ≥ 70`. Use a small `_band_for_total(total) -> RiskBand` helper.
    * `@model_validator(mode="after")` — assert `score_provenance.value == total / 100.0` (within 0.01 tolerance) and `score_provenance.provenance.confidence == 0.85` (deterministic high confidence; the score is an exact computation of inputs).

    Re-export from `__init__.py`. Names to add to `__all__`: `RiskBand`, `RiskComponent`, `RiskComponentName`, `RiskScore`, `RiskScoringInput`.

2. **AC2 — Agent function at `apps/agents/src/agents/intake/risk_scoring.py`.**

    ```python
    @agent_action(
        agent_id="risk_scoring",
        model_id="deterministic",
        prompt_template_id=None,
    )
    async def risk_scoring(
        input: RiskScoringInput,
        *,
        case_view: RiskCaseView | None = None,
    ) -> RiskScore: ...
    ```

    `case_view` is a typed bundle the supervisor builds from intake state:

    ```python
    @dataclass(frozen=True)
    class RiskCaseView:
        case: Case
        entity_verification: EntityVerificationResult | None
        ubo_graph: UBOGraph | None
        # screening + adverse_media: optional hints from customer_metadata.extra (demo placeholders)
        screening_hit_hint: dict | None
        adverse_media_hint: dict | None
    ```

    Logic:
    1. The agent fails fast with `RuntimeError("RiskCaseView is required at call time")` if `case_view is None` — supervisor always passes one, but defensive.
    2. Compute each component (AC3).
    3. Sum contributions; round to int total; derive band.
    4. Build `score_provenance: ProvenancedField[float](value=total/100.0, provenance=Provenance(source_agent="risk_scoring", source_system="deterministic", confidence=0.85, confidence_band=HIGH, evidence_ids=[], captured_at=now))`.
    5. Return `RiskScore(case_id=..., total=..., band=..., components=[...], score_provenance=...)`.

3. **AC3 — Component computation rules (deterministic, demo-pinned).**

    Five components. Each has a fixed `weight`; the `value` is computed from inputs.

    | Component | Weight | Value rule (0–100 raw) |
    |---|---|---|
    | `country` | `0.15` | `case.customer_metadata.country == "IN"` → 10. Otherwise 60 (single high-risk country bucket; the demo doesn't carry non-IN cases). Customer is individual (no country) → 20. |
    | `entity_type` | `0.20` | `customer_type == "company"` AND no UBO graph yet → 50; AND UBO graph has corporate shareholders in non-IN jurisdictions → 70; AND no foreign exposure → 30. `customer_type == "individual"` → 25. |
    | `ownership_clarity` | `0.30` | Largest contributor. Computed as: `40 + 20 * fraction_nominee_suspected_or_corrected`, where the fraction is `(count of edges with nominee_flag == "nominee_suspected" OR "officer_corrected") / max(1, total non-clear edges)`. Clear UBO graph → 40. All edges officer-corrected → 60. UBO graph absent → 50 (treat as opaque). For Story 5.5 officer corrections, **`officer_corrected` reduces the value** by 30 — i.e., when the officer has corrected a nominee_suspected edge, the rationale-recorded ownership becomes clearer. Final formula: `base + (count_nominee_suspected * 6) - (count_officer_corrected * 3)`, clamped to [0, 100]. **Pin the formula in tests; demo expectation: Vora pre-correction = 40 + 18 = 58 (3 nominee_suspected); Vora post-correction (Coastal flipped to officer_corrected) = 40 + 12 - 3 = 49.** |
    | `screening` | `0.20` | Placeholder for Epic 6. `screening_hit_hint != None` → 60. Absent → 0. |
    | `adverse_media` | `0.15` | Placeholder for Epic 6+. `adverse_media_hint != None` → 50. Absent → 0. |

    `contribution = round(value * weight, 1)` per component (one decimal).
    `total = round(sum(contributions))`.
    `band = _band_for_total(total)`.

    **Demo-pinned expected outputs:**

    * **Shree (clean SME):** country=10, entity_type=30, ownership_clarity=40, screening=0, adverse_media=0.
      Contributions: `[1.5, 6.0, 12.0, 0.0, 0.0]` → total ≈ 20 → band `low`.
    * **Vora (hairy UBO, pre-correction):** country=10, entity_type=70, ownership_clarity=58, screening=0, adverse_media=0.
      Contributions: `[1.5, 14.0, 17.4, 0.0, 0.0]` → total ≈ 33 → band `low` (just barely; the hairy UBO is the dominant driver but band threshold is 34). Actually: 1.5 + 14.0 + 17.4 = 32.9, rounds to 33, band `low`.
      **Wait — that's not the demo arc.** The demo wants Vora to land in `medium` or `high` to drive escalation. **Adjust the weights or thresholds:** raise `entity_type=85` for foreign-corporate-majority cases, OR raise `ownership_clarity` value formula's nominee penalty. **Pin: `ownership_clarity = base + (count_nominee_suspected * 10) - (count_officer_corrected * 4)`**. Re-compute Vora: `40 + 30 - 0 = 70`. Contributions: `[1.5, 14.0, 21.0, 0.0, 0.0]` → total ≈ 37 → band `medium`. Vora post-correction (Coastal officer_corrected): `40 + 20 - 4 = 56`. Contributions: `[1.5, 14.0, 16.8, 0.0, 0.0]` → total ≈ 32 → band `low`. **This is the arc.** Pin these numbers in the tests.
    * **Ananya (individual + screening hit):** country=20, entity_type=25, ownership_clarity=50 (no UBO graph, opaque), screening=60, adverse_media=0.
      Contributions: `[3.0, 5.0, 15.0, 12.0, 0.0]` → total ≈ 35 → band `medium`.

    Document the calibration in the agent module's docstring. Stable strings for rationale (used by the UI tooltip in Story 5.7):

    * `country.rationale = f"Customer country: {country!r} ({_country_band(country)})"`
    * `entity_type.rationale = f"{customer_type} with {n_foreign_corporate_holders} foreign-corporate UBO holder(s)"`
    * `ownership_clarity.rationale = f"{n_nominee_suspected} nominee-suspected edge(s); {n_officer_corrected} officer-corrected edge(s)"`
    * `screening.rationale = "Screening hit hint present" if hit else "No screening signal"`
    * `adverse_media.rationale = "Adverse media hint present" if hint else "No adverse-media signal"`

4. **AC4 — Supervisor wires `risk_scoring` into `INTAKE_AGENTS`.** Order: doc_intel → entity_verification → ubo_graph → risk_scoring.

    ```python
    IntakeAgentSpec(
        name="risk_scoring",
        invoke=_invoke_risk_scoring,
        requires=lambda case: True,    # always run; degrades gracefully when prior outputs missing
    )
    ```

    `_invoke_risk_scoring(ctx)` builds `RiskCaseView` from `ctx.outputs.get("entity_verification")` and `ctx.outputs.get("ubo_graph")`, plus reads `screening_hit_hint` and `adverse_media_hint` from `ctx.case.customer_metadata.extra`. Calls `risk_scoring(RiskScoringInput(case_id=ctx.case.id), case_view=view)`.

5. **AC5 — Denormalize `band` onto `cases.risk_band`.**

    After successful Risk Scoring, the supervisor updates the case row:
    ```python
    await CaseRepo.update_risk_band(session, case_id, score.band)
    ```

    Add the new method to `CaseRepo`:
    ```python
    @staticmethod
    async def update_risk_band(session: AsyncSession, case_id: CaseId, band: RiskBand) -> None:
        await session.execute(
            update(CaseRow).where(CaseRow.id == case_id).values(risk_band=band, updated_at=datetime.now(UTC))
        )
        await session.flush()
    ```

    The `Case.risk_band` column already exists (Story 2.1 § Schema). Map `RiskBand` (`"low" | "medium" | "high"`) onto the existing 4-tier `risk_band` column (`"low" | "medium_low" | "medium_high" | "high"`) via:
    * `low` → `low`
    * `medium` → `medium_high` (the demo's three-tier risk band collapses into the four-tier UI band; medium maps to medium_high to keep the queue rail's risk-driven sort stable for Vora pre-correction)
    * `high` → `high`

    **Decision:** keep the 3-tier `RiskBand` on the wire; widen the column at the boundary. Don't try to rename the column — it's already used by Story 4.1's queue ordering.

6. **AC6 — Persistence + evidence_ids back-fill.**

    Supervisor's pattern: persist the `RiskScore` to `IntakeRepo.upsert(session, case_id, "risk_scoring", filled_score)`. Back-fill `score_provenance.evidence_ids = [agent_completed_entry.id]` using the same `_rebuild_provenanced_field` helper from Story 5.1's AC6.

    Add `_fill_evidence_ids_risk_scoring(score, ledger_entry_id)` to the supervisor.

7. **AC7 — HTTP boundary at `POST /v1/agents/risk_scoring/score`.**

    ```python
    @router.post(
        "/risk_scoring/score",
        response_model=RiskScore,
        summary="Run the Risk Scoring agent against a case",
        description=(
            "Calls the Risk Scoring agent. Reads prior intake outputs "
            "(entity_verification, ubo_graph) and customer_metadata to "
            "compute a 5-component decomposed risk score. Every "
            "invocation writes one ledger entry."
        ),
    )
    async def score_risk(payload: RiskScoringInput, session: AsyncSession = Depends(get_session)) -> RiskScore:
        # Build the case_view from persisted state
        case = await CaseRepo.get(session, payload.case_id)
        if case is None: raise HTTPException(404, ...)
        ev = await IntakeRepo.get_one(session, payload.case_id, "entity_verification")
        ub = await IntakeRepo.get_one(session, payload.case_id, "ubo_graph")
        view = RiskCaseView(
            case=case,
            entity_verification=EntityVerificationResult.model_validate(ev) if ev else None,
            ubo_graph=UBOGraph.model_validate(ub) if ub else None,
            screening_hit_hint=case.customer_metadata.extra.get("screening_hit_hint"),
            adverse_media_hint=case.customer_metadata.extra.get("adverse_media_hint"),
        )
        try:
            return await risk_scoring(payload, case_view=view)
        except AgentExecutionError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
    ```

    Test in `test_agents_router.py`: 200 happy path on Vora (after intake); 404 on unknown case; 502 on agent error (mock `risk_scoring` to raise).

    **Note:** This endpoint runs the agent **without** updating `Case.risk_band` or persisting to `IntakeRepo` — those are supervisor responsibilities. The endpoint is for ad-hoc / chat-driven recomputation. Story 5.8's auto-recalc may bypass it and call the supervisor directly, OR call this endpoint with a `?persist=true` query param. **Decision:** the endpoint persists (to keep things simple) — i.e., the endpoint does the upsert + risk_band update + evidence_ids back-fill itself. Document this divergence from doc_intel's endpoint.

    Wait — the document_intelligence endpoint *doesn't* persist (it's the supervisor's job). To stay consistent: this endpoint also doesn't persist. Story 5.8 will call the supervisor's intake or a dedicated `/recalc` flow.

    **Final decision: this endpoint is read-only computation; no persistence side effects.** Document it as such.

8. **AC8 — ADK registry entry at `apps/agents/src/agents/registry/risk_scoring/`.**

    Mirror prior. `agent.yaml` instructions explain the 5-component decomposition; `tools: [score_risk]`; `gen_openapi.py` filters to `/v1/agents/risk_scoring/score`.

9. **AC9 — TypeScript hook at `apps/cockpit-ui/src/hooks/useRiskScore.ts`.**

    ```typescript
    export function useRiskScore(caseId: string) {
        return useQuery<RiskScore>({
            queryKey: ['cases', caseId, 'intake', 'risk_scoring'],
            queryFn: async () => { /* GET /v1/cases/{case_id}/intake/risk_scoring */ },
        });
    }
    ```

    Used by Story 5.7's RiskScoreBar component.

10. **AC10 — Tests at `apps/agents/tests/test_risk_scoring.py`.** Cover:

    * **Shree happy path (clean SME):** assert pinned outputs from AC3 (low band, total ≈ 20).
    * **Vora pre-correction:** assert pinned outputs (medium band, total ≈ 37, ownership_clarity contribution dominant).
    * **Vora post-correction:** mutate the UBO graph to flip Coastal to `officer_corrected`; assert total ≈ 32, band drops to `low`. **This is the demo arc — don't change the threshold without re-pinning.**
    * **Ananya:** screening_hit_hint present; assert `screening` component contributes 12.0; total ≈ 35; band `medium`.
    * **No UBO graph:** call against a case with no UBO graph in `case_view`; assert `ownership_clarity.value=50`, rationale `"UBO graph absent; treating as opaque"`.
    * **Validator catches mismatched band:** construct `RiskScore` with `total=10, band="medium"` directly; assert `ValidationError`.
    * **Validator catches sum-of-weights ≠ 1.0:** assert `ValidationError`.
    * **Provenance band consistency:** `score_provenance.provenance.confidence_band == HIGH`.
    * **Ledger entry shape:** invoke through `@agent_action`; assert `payload.agent_id="risk_scoring"`, `payload.model_id="deterministic"`, `payload.output.total in [0, 100]`.
    * **Evidence ID back-fill via supervisor:** assert `score_provenance.evidence_ids == [agent_completed.id]`.
    * **Idempotency:** call the agent twice with the same `case_view`; assert identical output (deterministic).
    * **Customer-metadata mutation between calls:** mutate `screening_hit_hint`; reinvoke; assert score updates.
    * **`risk_band` denormalized on case row:** end-to-end through supervisor; assert `Case.risk_band` post-intake matches the score's mapped 4-tier value.

11. **AC11 — Supervisor tests in `apps/agents/tests/test_case_supervisor.py`.** Cover:

    * Four-agent fan-out (doc_intel + entity_verification + ubo_graph + risk_scoring); all succeed; case `decision_ready`; ledger has 5 entries (4 agent.completed + 1 case.intake_completed).
    * Risk scoring fails after upstream succeed: case `escalated`; `failed_agent="risk_scoring"`.
    * Risk scoring runs even when entity_verification was skipped (case has no CIN — Ananya): `_invoke_risk_scoring` builds a `RiskCaseView` with `entity_verification=None`; the agent computes against the available signal; case lands `decision_ready`.

12. **AC12 — Contract tests in `packages/contracts/tests/test_risk.py`.** Round-trip; each validator rejection.

13. **AC13 — `make demo-reset && make seed && make test` clean.** Net new test count: ≥ 12 in `test_risk_scoring.py`, ≥ 3 in supervisor, ≥ 5 in `test_risk.py`. `make adk-spec && make adk-register` succeed.

14. **AC14 — Agent-mesh-state derivation maps the slug.** `actor_id="risk_scoring"` ↔ `AgentSlug.RISK_SCORING = "risk-scoring"`. Add the mapping if absent.

## Tasks / Subtasks

- [x] **Task 1 — Pydantic contracts** (AC: #1, #12)
  - [x] Subtask 1.1 — `packages/contracts/src/contracts/risk.py`.
  - [x] Subtask 1.2 — Re-export from `__init__.py`.
  - [x] Subtask 1.3 — `packages/contracts/tests/test_risk.py`.

- [x] **Task 2 — Agent function** (AC: #2, #3, #10)
  - [x] Subtask 2.1 — `apps/agents/src/agents/intake/risk_scoring.py` with `risk_scoring` agent + `_compute_*` helpers.
  - [x] Subtask 2.2 — Each component's value rule per AC3 in a separate small helper.
  - [x] Subtask 2.3 — Pin demo expected outputs in tests.

- [x] **Task 3 — Supervisor wiring + denormalize** (AC: #4, #5, #6, #11)
  - [x] Subtask 3.1 — `RiskCaseView` dataclass.
  - [x] Subtask 3.2 — `_build_risk_case_view(ctx)`.
  - [x] Subtask 3.3 — `_invoke_risk_scoring(ctx)`.
  - [x] Subtask 3.4 — Append spec to `INTAKE_AGENTS` after `ubo_graph`.
  - [x] Subtask 3.5 — `_fill_evidence_ids_risk_scoring(score, ledger_entry_id)`.
  - [x] Subtask 3.6 — `CaseRepo.update_risk_band(session, case_id, band)` + 3-tier-to-4-tier mapping.
  - [x] Subtask 3.7 — Supervisor calls `update_risk_band` after persist.

- [x] **Task 4 — HTTP boundary + ADK registry** (AC: #7, #8)
  - [x] Subtask 4.1 — `apps/cockpit-api/src/cockpit_api/routers/agents.py` adds `/risk_scoring/score`.
  - [x] Subtask 4.2 — Router test.
  - [x] Subtask 4.3 — `apps/agents/src/agents/registry/risk_scoring/agent.yaml`.
  - [x] Subtask 4.4 — `apps/agents/src/agents/registry/risk_scoring/gen_openapi.py`.
  - [x] Subtask 4.5 — `make adk-spec` regenerates openapi.yaml; commit.

- [x] **Task 5 — TypeScript hook** (AC: #9)
  - [x] Subtask 5.1 — Run `make contracts` to refresh api-types.ts.
  - [x] Subtask 5.2 — `apps/cockpit-ui/src/hooks/useRiskScore.ts`.

- [x] **Task 6 — Tests + verification** (AC: #10, #11, #13, #14)
  - [x] Subtask 6.1 — `test_risk_scoring.py` covers 12+ cases.
  - [x] Subtask 6.2 — Supervisor tests extend.
  - [x] Subtask 6.3 — agent-mesh-state mapping test.
  - [x] Subtask 6.4 — `make demo-reset && make seed && make test` green; `make lint` green.

## Dev Notes

### Architectural context (binding)

* [Source: `architecture.md#Demo Scope Addendum (2026-04-29)`] No LLM in scoring; deterministic Python.
* [Source: `architecture.md#Project-Specific Patterns` P3] `score_provenance` wraps the float total. The component-list rationales are NOT individually `ProvenancedField` — they're metadata on a derived score. Compromise: the agent's typed output is an aggregate; provenance is at the aggregate level.
* [Source: `architecture.md#Project-Specific Patterns` P4] `@agent_action` writes the ledger entry. Story 3.2 decorator already in place.
* [Source: `architecture.md#Project-Specific Patterns` P7] Confidence banding — `band` here is the **risk band** (low/medium/high), distinct from `ConfidenceBand` (low/medium_low/medium_high/high). Don't conflate.
* [Source: `ux-design-specification.md` § 985] UBO panel preview shows ownership decomposition + confidence-banded subheads. Story 5.7 mirrors this for risk components.

### Critical pitfalls

1. **Risk band ≠ Confidence band.** The codebase already has `ConfidenceBand` (4-tier, lowercase: `low`, `medium_low`, `medium_high`, `high`). Risk Score's `band` is a NEW 3-tier `RiskBand` (`low`, `medium`, `high`). Don't try to reuse the `ConfidenceBand` enum — they have different semantics.

2. **The 3-tier `RiskBand` on the wire vs the 4-tier `cases.risk_band` column.** The column was sized for the bank-buyer scope's 4-tier risk model. Demo collapses to 3 tiers. The mapping from 3 to 4 (per AC5) is one-way; don't reverse-derive.

3. **Component weights MUST sum to 1.0.** Pydantic validator enforces ±0.01. With weights `[0.15, 0.20, 0.30, 0.20, 0.15]`, sum is exactly 1.0. **Don't accidentally float-corrupt by not using `Decimal`** — the tests' `pytest.approx` check confirms.

4. **Vora pre-correction MUST land in `medium` band.** Demo arc requires it. The threshold and weights pinned here produce that outcome (total ≈ 37). If you change any weight or value rule, re-run the AC3 demo-pinned table calculations and adjust thresholds — but do NOT ship Vora pre-correction in `low` band.

5. **`officer_corrected` edges drop the score** but don't drop it below `low`. Vora post-correction = total ≈ 32, band `low`. The arc: pre-correction Vora is `medium` (officer attention required); post-correction Vora is `low` (officer accepted the disclosure as true UBO). Confirm this with the Vora post-correction test.

6. **Ananya's screening_hit_hint is the only hit-hint in the demo fixtures.** The component handler uses `dict-truthiness` (`hint is not None and bool(hint)`). Empty dict `{}` → no hit. Vora's case has no `screening_hit_hint`; Shree's case has no hints.

7. **`country` is None for individual customers.** The country-component rule: "individual customer → country=20" handles this. Don't break for `country = None and customer_type == "company"` (no demo case has this, but defensive).

8. **`risk_scoring` runs even when entity_verification was skipped.** `requires=lambda case: True`. The agent's `case_view.entity_verification` may be `None` — that's fine; the components only need it for fine-grained `entity_type` weighting.

9. **The agent function doesn't `await` anything that fails.** Synchronous business logic — the `async def` is only there so `@agent_action` (which expects an async fn) can wrap it. Tests can use `asyncio.run` or `pytest-asyncio`.

10. **`score_provenance.value` is `total / 100.0`, NOT `band` mapped to a float.** The provenance's float represents the same risk total in [0.0, 1.0]. The validator enforces consistency.

11. **`update_risk_band` updates `updated_at`** to surface the recalc to the queue rail's sort. Story 4.1 sorts by `(risk DESC, sla ASC, updated_at DESC)`. The `updated_at` change ensures recalcs nudge the case to the top of the rail.

### Story dependencies

* **Strict prereqs:** Story 5.1 (Entity Verification — supervisor `IntakeContext` + `EntityVerificationResult`), Story 5.3 (UBO Graph — `UBOGraph`).
* **Reads from:** Story 3.5 (Case Supervisor), Story 4.1 (queue rail risk-band ordering — already lives), Story 2.1 (Case schema with `risk_band` column).
* **Read by:** Story 5.7 (Risk Score stacked-bar), Story 5.8 (auto-recalc — invokes this agent on officer correction).

### Project Structure Notes

This story creates:
- `packages/contracts/src/contracts/risk.py`
- `packages/contracts/tests/test_risk.py`
- `apps/agents/src/agents/intake/risk_scoring.py`
- `apps/agents/tests/test_risk_scoring.py`
- `apps/agents/src/agents/registry/risk_scoring/agent.yaml`
- `apps/agents/src/agents/registry/risk_scoring/gen_openapi.py`
- `apps/agents/src/agents/registry/risk_scoring/openapi.yaml` (generated)
- `apps/cockpit-ui/src/hooks/useRiskScore.ts`

This story modifies:
- `packages/contracts/src/contracts/__init__.py` — re-exports
- `apps/agents/src/agents/supervisor/case_supervisor.py` — `RiskCaseView`, `_build_risk_case_view`, `_invoke_risk_scoring`, `_fill_evidence_ids_risk_scoring`, `INTAKE_AGENTS` extension; supervisor's success path now calls `CaseRepo.update_risk_band`
- `apps/cockpit-api/src/cockpit_api/repositories/case_repo.py` — `update_risk_band`
- `apps/cockpit-api/src/cockpit_api/routers/agents.py` — `/risk_scoring/score` endpoint
- `apps/cockpit-api/src/cockpit_api/services/agent_mesh_state.py` — slug mapping (if absent)

This story DOES NOT create:
- The Risk Score stacked-bar UI (Story 5.7)
- The auto-recalc trigger on officer correction (Story 5.8)
- A real screening adapter (Epic 6)
- Per-jurisdiction risk weights YAML (deferred; constants live in Python module)

### References

- [Source: `architecture.md#Demo Scope Addendum (2026-04-29)`] no LLM, no per-jurisdiction YAML
- [Source: `architecture.md#Project-Specific Patterns` P3 / P4 / P7] provenance, agent-action, banding
- [Source: `epics.md#Epic 5` § Story 5.7] original AC (re-scoped here)
- [Source: `prd.md#FR20, FR21`] decomposed risk + auto-recalc
- [Source: `2-1-case-schema-and-state-machine.md`] `Case.risk_band` 4-tier column
- [Source: `4-1-risk-sla-continuity-ordering-for-queue-rail.md`] queue rail sort by risk band
- [Source: `5-1-entity-verification-agent.md`] `IntakeContext`, `EntityVerificationResult`
- [Source: `5-3-ubo-graph-agent-basic.md`] `UBOGraph`, `nominee_flag` enum
- [Source: `5-5-drag-correct-interaction-with-learning-event-ledger-entry.md`] `officer_corrected` flag

### Demo verification protocol

```bash
make demo-reset && make seed
poetry -C apps/cockpit-api run python -c "
import asyncio
from contracts.cases import VORA_CAPITAL_ID, SHREE_VENKAT_ID, ANANYA_IYER_ID
from agents.supervisor.case_supervisor import CaseSupervisor
from cockpit_api.db.session import session_factory

async def main():
    s = CaseSupervisor(session_factory=session_factory)
    for cid in (SHREE_VENKAT_ID, VORA_CAPITAL_ID, ANANYA_IYER_ID):
        out = await s.run_intake(cid)
        print(cid[:18], 'agents:', len(out.agents_run), 'status:', out.status)
asyncio.run(main())
"

# Inspect risk scores:
sqlite3 ./data/cockpit.db "SELECT id, risk_band, json_extract(output_json, '\$.total') FROM cases JOIN intake_results ON cases.id = intake_results.case_id WHERE intake_results.agent_id='risk_scoring';"
# Expected:
#   shree → low, total ≈ 20
#   vora → medium_high (3-tier 'medium' mapped), total ≈ 37
#   ananya → medium_high, total ≈ 35

# Trigger Vora correction (Story 5.5) and re-score:
ANALYST_ID=$(jq -r '.[] | select(.role=="analyst") | .id' apps/cockpit-api/fixtures/users.json)
curl -s -X POST "http://localhost:8000/v1/cases/${VORA_CAPITAL_ID}/ubo/learning-events" \
  -H 'Content-Type: application/json' \
  -H "X-Cockpit-Demo-User: ${ANALYST_ID}" \
  -d '{"edge_kind": "owns", "from_id": "ubo_e_coastal_equity_partners_pte_ltd", "original_to_id": "ubo_e_u67120mh2024ptc444789", "new_to_id": "ubo_e_u67120mh2024ptc444789", "correction_tag": "real_ubo", "evidence_note": "RM email", "opt_in_for_retraining": true}'

# Re-run risk scoring against Vora:
curl -s -X POST "http://localhost:8000/v1/agents/risk_scoring/score" \
  -H 'Content-Type: application/json' \
  -d "{\"case_id\":\"${VORA_CAPITAL_ID}\"}" | python -m json.tool
# Expected: total ≈ 32, band "low" (post-correction arc)

make lint && make test
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
| 2026-05-08 | Story 5.6 drafted. Demo replacement for the bank-buyer Story 5.7: deterministic 5-component decomposition, demo-pinned weights producing Vora pre/post-correction band arc (medium → low), risk_band denormalized to case row for queue rail. |
