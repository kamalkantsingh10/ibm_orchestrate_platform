# Story 5.5: Drag-correct interaction with learning-event ledger entry

Status: review

## Story

As a KYC Analyst on a case where the UBO Graph agent flagged edges as `nominee_suspected` (Story 5.3) and Story 5.4's UBOCanvas is rendering them,
I want to drag a flagged edge to a different target node, tag the relationship via a small modal (`real_ubo` / `nominee` / `director` / `removed`), attach an evidence note, and have my correction land as an officer-attributed `learning_event` ledger entry that flips the edge's `nominee_flag` to `officer_corrected`,
So that I can disagree with the agent without typing free text, the corpus of corrections accumulates as labeled signal for a future retraining cycle (out of MVP scope), the audit trail records the disagreement immutably, and Story 5.8's auto-recalc on officer correction has a typed event to subscribe to (FR16, UX-DR19, NFR-T6 reasoned-correction-rate floor).

## Scope note (2026-04-29 demo re-scope)

This story is the demo-equivalent of the bank-buyer Story 5.6. The bank-buyer scope required officer Ed25519 signing; the demo simplifies to **logged-in user identity only** (Story 7.4 Ed25519 verification was cut from Epic 7 per re-scope).

| Bank-buyer scope (original 5.6) | Demo replacement in this story |
|---|---|
| Officer Ed25519 signature attached via Story 7.4's `lib/crypto.ts` | **No signature.** The ledger entry's `actor_id` records the user-switcher's current user ID (`X-Cockpit-Demo-User` header from Story 1.4). The acceptance criterion on the original Story 5.6 explicitly allowed "a temporary platform sig acceptable in Epic 5" — the demo removes the signature concept entirely. |
| Tenant-scoped writes | Single-tenant. |
| Corrections opt-in for retraining via "Teach?" prompt → captured as opt-in flag | **Same prompt** — the boolean lands on the ledger entry as `payload.opt_in_for_retraining: bool`. No retraining pipeline, but the flag is recorded for future use. |
| Atomic multi-entry commit (UBO correction + evidence + learning_event together) | **Single ledger entry.** The drag-correct produces ONE `learning_event` entry; the evidence-attachment-with-hash flow lands separately in Epic 8 (Story 8.6). |

What survives: **drag-correct UI + tag modal + evidence-note free-text field + opt-in checkbox + typed `learning_event` ledger payload + Pydantic-validated POST endpoint + UBO graph mutation + officer attribution.**

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md` § Stories simplified, `architecture.md#Demo Scope Addendum (2026-04-29)`, `epics.md#Epic 5` § Story 5.6.

## Acceptance Criteria

1. **AC1 — Pydantic contracts at `packages/contracts/src/contracts/learning_event.py`.**

    ```python
    from typing import Literal
    from pydantic import BaseModel, Field

    CorrectionTag = Literal["real_ubo", "nominee", "director", "removed"]

    class LearningEventInput(BaseModel):
        """POST body for /v1/cases/{case_id}/ubo/learning-events."""
        model_config = {"frozen": True}
        edge_kind: Literal["owns", "director", "beneficial"]
        from_id: UBONodeId
        original_to_id: UBONodeId           # the original target (root entity, usually)
        new_to_id: UBONodeId                # the target after officer drag — may equal original if officer only re-tagged
        correction_tag: CorrectionTag
        evidence_note: str = Field(min_length=1, max_length=500)
        opt_in_for_retraining: bool = False

    class LearningEventResponse(BaseModel):
        """Server-side response after persisting + writing the ledger entry."""
        model_config = {"frozen": True}
        ledger_entry_id: LedgerEntryId      # the resulting led_<ULID>
        case_id: CaseId
        recorded_at: datetime
    ```

    Re-export from `__init__.py`. Names to add to `__all__`: `CorrectionTag`, `LearningEventInput`, `LearningEventResponse`.

2. **AC2 — `learning_event` ledger payload kind.**

    Extend the ledger payload taxonomy: previously the `LedgerEntry.payload` is `AgentActionLedgerEntry | dict[str, Any]`. Add a typed payload class for officer-originated corrections:

    ```python
    # packages/contracts/src/contracts/learning_event.py
    class LearningEventLedgerPayload(BaseModel):
        model_config = {"frozen": True}
        kind: Literal["learning_event"] = "learning_event"
        edge_kind: Literal["owns", "director", "beneficial"]
        from_id: UBONodeId
        original_to_id: UBONodeId
        new_to_id: UBONodeId
        correction_tag: CorrectionTag
        evidence_note: str
        opt_in_for_retraining: bool
    ```

    Update `packages/contracts/src/contracts/ledger.py`:
    ```python
    LedgerEntry.payload: AgentActionLedgerEntry | LearningEventLedgerPayload | dict[str, Any]
    ```

    Pydantic resolves the union left-to-right by `kind` discriminator; agent_action wins for `kind="agent_action"`, learning_event wins for `kind="learning_event"`, plain dict otherwise. **Migration check:** every existing `dict`-shaped payload in `./data/ledger.jsonl` must continue validating — assert via the existing payload-roundtrip test in `packages/contracts/tests/test_ledger.py`.

3. **AC3 — POST endpoint at `/v1/cases/{case_id}/ubo/learning-events`.**

    New router file or extension of `apps/cockpit-api/src/cockpit_api/routers/cases.py` (decision: extend `cases.py` — it already owns case-scoped sub-resources):

    ```python
    @router.post(
        "/{case_id}/ubo/learning-events",
        response_model=LearningEventResponse,
        status_code=201,
        summary="Officer correction to the UBO graph (drag-correct flow)",
    )
    async def create_learning_event(
        case_id: CaseId,
        payload: LearningEventInput,
        current_user: User = Depends(current_user_dep),     # Story 1.4 user-switcher
        session: AsyncSession = Depends(get_session),
    ) -> LearningEventResponse:
        ...
    ```

    Logic:
    1. Validate the case exists; 404 RFC 7807 if not.
    2. Load the persisted `UBOGraph` from `IntakeRepo.get_one(session, case_id, "ubo_graph")`. If absent → 409 `"UBO graph not built; run intake first"`.
    3. Validate `payload.from_id` and `payload.original_to_id` reference real nodes in the graph. 422 if not.
    4. Mutate the graph: find the edge `(payload.edge_kind, payload.from_id, payload.original_to_id)`; copy-on-write a new edge with `to_id = payload.new_to_id`, `nominee_flag = "officer_corrected"`, `rationale = f"Officer correction by {current_user.id}: {payload.correction_tag}"`. If the new target node doesn't exist (officer dragged to empty space — out of scope for the demo's pinned graphs but possible), 422.
    5. Upsert the mutated graph back to `IntakeRepo`.
    6. Append a `learning_event` ledger entry via `LedgerWriter.append`:
       ```python
       entry = LedgerEntry(
           id=_placeholder_ledger_id(),
           actor_type=ActorType.OFFICER,
           actor_id=current_user.id,
           case_id=case_id,
           action="ubo.edge_corrected",
           payload=LearningEventLedgerPayload(...),
           recorded_at=datetime.now(UTC),
       )
       ```
       The writer handles `id` regeneration (Story 3.1 invariant).
    7. **Fire SSE event** `case.documents_changed`-style — actually a NEW event: `case.ubo_corrected`. See AC4.
    8. **Trigger Story 5.8's risk recalc** — for now, just a comment in this story's code; Story 5.8 wires the actual recalc. Don't call risk_scoring inline.
    9. Return `LearningEventResponse(ledger_entry_id=..., case_id=case_id, recorded_at=...)`.

4. **AC4 — SSE event for the correction.**

    Extend `packages/contracts/src/contracts/sse.py`:
    ```python
    SseEvent.event: Literal[
        "agent.state_changed",
        "case.state_changed",
        "case.documents_changed",
        "case.ubo_corrected",        # NEW
    ]
    ```

    Fire after a successful POST. Payload (≤ 256 bytes per architecture.md § P6): `{"case_id": case_id, "edge_kind": kind, "from_id": from_id, "new_to_id": new_to_id}`. Story 5.4's UBOCanvas in the cockpit-ui subscribes to this via the existing SSE infra (Story 4.6) and refetches `useUboGraph(caseId)` on receipt.

5. **AC5 — UBO graph mutation helper at `apps/cockpit-api/src/cockpit_api/services/ubo_correction_service.py`.**

    Pure function:
    ```python
    def apply_officer_correction(
        graph: UBOGraph,
        *,
        edge_kind: Literal["owns", "director", "beneficial"],
        from_id: UBONodeId,
        original_to_id: UBONodeId,
        new_to_id: UBONodeId,
        correction_tag: CorrectionTag,
        actor_id: str,
    ) -> UBOGraph:
        """Return a new UBOGraph with the corrected edge.

        Raises:
            EdgeNotFoundError: if (edge_kind, from_id, original_to_id) doesn't exist.
            NodeNotFoundError: if new_to_id isn't in the graph's nodes.
        """
    ```

    The new edge:
    * `nominee_flag="officer_corrected"`
    * `confidence: ProvenancedField[float](value=0.99, provenance=Provenance(source_agent="officer", source_system=actor_id, confidence=0.99, confidence_band=HIGH, evidence_ids=[], captured_at=now))` — the officer's correction is HIGH confidence by definition.
    * `rationale = f"Officer correction (tag: {correction_tag})"`.

    If `correction_tag == "removed"`: the helper removes the edge entirely from the graph (do not insert a new edge). The ledger entry still records the action.

    Tests for this helper live in `apps/cockpit-api/tests/test_ubo_correction_service.py`: success paths for each correction_tag, EdgeNotFoundError, NodeNotFoundError, removal flow.

6. **AC6 — UBOCanvas wires the drag interaction.**

    Extend Story 5.4's `apps/cockpit-ui/src/components/cockpit/UBOCanvas/UBOCanvas.tsx`:

    1. Set `<ReactFlow>` props: `nodesDraggable={false}`, `edgesUpdatable={true}`, `elementsSelectable={true}`. Edges become draggable at their endpoints (the standard react-flow update interaction).
    2. Wire `onEdgeUpdate(oldEdge, newConnection)`:
       * Open a modal dialog (Radix `Dialog`) with the `CorrectionTagModal` component (AC7).
       * On confirm, call `onEdgeCorrect?.(oldEdge, newConnection.target)` (already a prop on UBOCanvas from Story 5.4).
       * On cancel, the optimistic edge update reverts.
    3. Wire `onEdgeUpdateStart` / `onEdgeUpdateEnd` to set a `data-canvas-state` on the wrapper for cursor styling (`cursor-grabbing` while dragging).
    4. Disable drag on edges that are `nominee_flag="officer_corrected"` AND `correction_tag="removed"` (these don't render in the first place; the second guard is defensive).

7. **AC7 — `CorrectionTagModal` at `apps/cockpit-ui/src/components/cockpit/UBOCanvas/CorrectionTagModal.tsx`.**

    Props:
    ```typescript
    export interface CorrectionTagModalProps {
        open: boolean;
        onOpenChange: (open: boolean) => void;
        edge: UBOEdge;
        newTargetId: string;
        onConfirm: (tag: CorrectionTag, evidenceNote: string, optInForRetraining: boolean) => Promise<void>;
    }
    ```

    Content (using shadcn `Dialog`):
    * **Title:** "Tag this correction"
    * **Subtitle (smaller):** Shows the original edge: `<source name> → <target name> (<edge_kind>, <ownership_pct>%)` and the proposed new target.
    * **Tag selector:** four large-tap radio buttons:
      * "Real UBO" — value `real_ubo` — primary positive option
      * "Nominee" — value `nominee`
      * "Director" — value `director` (only enabled when edge_kind is `director`)
      * "Remove this edge" — value `removed` — destructive style (red border)
    * **Evidence note:** `<textarea>` with placeholder `e.g., "RM email Nov 2024 — disclosed real UBO is offshore family trust"`. Required, ≥1 char, ≤500.
    * **Teach checkbox:** `<input type="checkbox">` with label `"Use this correction as labeled training signal (opt-in)"`. Default unchecked.
    * **Buttons:** `Cancel` (secondary) and `Confirm correction` (primary, disabled until tag + note are both filled).

    On confirm: call `onConfirm(tag, note, optIn)`. The parent (`UBOCanvas` or its caller) handles the API call; this modal just passes data up.

8. **AC8 — TanStack Query mutation hook at `apps/cockpit-ui/src/hooks/useUboCorrection.ts`.**

    ```typescript
    export function useUboCorrection(caseId: string) {
        const queryClient = useQueryClient();
        return useMutation({
            mutationFn: async (input: LearningEventInput) => {
                const { data, error } = await apiClient.POST('/v1/cases/{case_id}/ubo/learning-events', {
                    params: { path: { case_id: caseId } },
                    body: input,
                });
                if (error) throw new Error(typeof error === 'object' ? JSON.stringify(error) : String(error));
                return data as LearningEventResponse;
            },
            onSuccess: () => {
                void queryClient.invalidateQueries({ queryKey: ['cases', caseId, 'intake', 'ubo_graph'] });
                // Story 5.8 will add: void queryClient.invalidateQueries({ queryKey: ['cases', caseId, 'intake', 'risk_scoring'] });
            },
        });
    }
    ```

    Test: `useUboCorrection.test.ts` mocks the API client; assert the mutation fires the right body; assert success invalidates the right query key.

9. **AC9 — Tests in `apps/cockpit-api/tests/test_ubo_correction.py`.** Cover:

    * **Happy path — tag as real_ubo:** POST with valid body referencing a Vora edge; assert 201; response body matches the response model; ledger entry written with `actor_type=OFFICER`, `actor_id=<analyst_id>`, `action="ubo.edge_corrected"`, `payload.kind="learning_event"`; persisted UBO graph has the edge's `nominee_flag` flipped to `officer_corrected`.
    * **Tag as removed:** POST with `correction_tag="removed"`; assert the edge is gone from the persisted graph; ledger entry still recorded.
    * **Case not found:** POST against unknown `case_id`; assert 404 RFC 7807.
    * **UBO graph not built:** POST against a case where intake hasn't run; assert 409 RFC 7807 with detail `"UBO graph not built; run intake first"`.
    * **Edge not in graph:** POST with `from_id="ubo_p_nonexistent"`; assert 422 RFC 7807.
    * **New target not in graph:** POST with `new_to_id="ubo_p_nonexistent"`; assert 422.
    * **Empty evidence note:** POST with `evidence_note=""`; assert 422 (Pydantic validates `min_length=1`).
    * **Evidence note > 500 chars:** assert 422.
    * **`X-Cockpit-Demo-User` missing:** demo's `current_user_dep` falls back to default analyst (per Story 1.4); assert the ledger entry's `actor_id` is the default analyst's ID.
    * **`X-Cockpit-Demo-User` set to team_lead:** assert the ledger entry's `actor_id` is `TEAM_LEAD_ID`. (Demo allows team-lead to drag-correct in this story; if the role gate is tighter — analyst-only — the test asserts a 403; pick **analyst-only** and document.)
    * **SSE fires:** with the SSE registry registered, post a correction; assert `case.ubo_corrected` is published with the right payload.

    Use `apps/cockpit-api/tests/conftest.py`'s existing `make_test_session` and `tmp_writer` fixtures.

10. **AC10 — Tests in `apps/cockpit-api/tests/test_ubo_correction_service.py`.** Cover the pure helper:
    * Success for each `correction_tag`.
    * `EdgeNotFoundError` raised on missing edge.
    * `NodeNotFoundError` raised on missing new target.
    * `correction_tag="removed"` returns a graph with the edge stripped.
    * Provenance on the new edge: `source_agent="officer"`, `confidence=0.99`, `confidence_band=HIGH`.
    * The original `UBOGraph` is unchanged (frozen Pydantic invariant; helper returns a new instance).

11. **AC11 — Tests in `apps/cockpit-ui/src/components/cockpit/UBOCanvas/CorrectionTagModal.test.tsx`.** Cover:
    * Renders with the four tags as radio buttons.
    * "Director" radio is disabled when `edge.kind != "director"`.
    * Confirm button disabled until tag + evidence note both populated.
    * Confirm button calls `onConfirm` with the captured values.
    * Cancel button calls `onOpenChange(false)`.
    * Removed-tag triggers a destructive confirm style (red).

12. **AC12 — Tests in `apps/cockpit-ui/src/hooks/useUboCorrection.test.ts`.** Cover:
    * Mutation calls the right endpoint with the right body.
    * Success invalidates `['cases', caseId, 'intake', 'ubo_graph']`.
    * Error is propagated to the caller.

13. **AC13 — Update Story 5.4's UBOCanvas test fixture/snapshot to handle `officer_corrected` edges.** Add a fixture variant `vora-ubo-graph-after-correction.json` showing the Coastal edge with `nominee_flag="officer_corrected"`, `confidence.value=0.99`. Update the visual style snapshot per AC5 of Story 5.4 (emerald-600 stroke for officer-corrected).

14. **AC14 — `make demo-reset && make seed && make test` clean.** Net new test count: ≥ 11 in `test_ubo_correction.py`, ≥ 6 in `test_ubo_correction_service.py`, ≥ 6 UI tests, ≥ 4 contract tests for `LearningEventInput`/`LearningEventResponse`/`LearningEventLedgerPayload`.

15. **AC15 — End-to-end demo verification.** With `make dev` running and a Vora case:
    1. Open the case page; UBO panel renders with Coastal Equity Partners → Vora as a dashed-red edge.
    2. Drag the Coastal edge's right endpoint to a different node (or just drop on the same node); modal appears.
    3. Select `real_ubo`; type "RM email 2024-11 disclosed offshore family trust"; check the "Use as training signal" box; click Confirm.
    4. Modal closes; canvas refetches; Coastal edge is now solid emerald-600 (officer_corrected).
    5. Open `./data/ledger.jsonl`; tail to the last entry; assert `action="ubo.edge_corrected"`, `actor_type="officer"`, `payload.correction_tag="real_ubo"`, `payload.opt_in_for_retraining=true`, `payload.evidence_note="RM email 2024-11 disclosed offshore family trust"`.
    6. Confirm SSE event fired (browser DevTools network tab or server stdout `sse.publish event=case.ubo_corrected`).

## Tasks / Subtasks

- [x] **Task 1 — Pydantic contracts** (AC: #1, #2)
  - [x] Subtask 1.1 — `packages/contracts/src/contracts/learning_event.py`.
  - [x] Subtask 1.2 — Extend `LedgerEntry.payload` union with `LearningEventLedgerPayload`.
  - [x] Subtask 1.3 — Re-export from `__init__.py`.
  - [x] Subtask 1.4 — Contract tests + payload-union round-trip test.

- [x] **Task 2 — UBO correction service** (AC: #5, #10)
  - [x] Subtask 2.1 — `apps/cockpit-api/src/cockpit_api/services/ubo_correction_service.py` with `apply_officer_correction`, `EdgeNotFoundError`, `NodeNotFoundError`.
  - [x] Subtask 2.2 — `test_ubo_correction_service.py`.

- [x] **Task 3 — POST endpoint** (AC: #3, #9)
  - [x] Subtask 3.1 — Extend `apps/cockpit-api/src/cockpit_api/routers/cases.py` with `/{case_id}/ubo/learning-events`.
  - [x] Subtask 3.2 — Wire `current_user_dep` (Story 1.4); use `X-Cockpit-Demo-User` header for actor_id.
  - [x] Subtask 3.3 — Append ledger entry; persist mutated graph via `IntakeRepo.upsert`.
  - [x] Subtask 3.4 — Fire SSE `case.ubo_corrected`.
  - [x] Subtask 3.5 — `test_ubo_correction.py` covers AC9.

- [x] **Task 4 — SSE event extension** (AC: #4)
  - [x] Subtask 4.1 — Extend `packages/contracts/src/contracts/sse.py` Literal.
  - [x] Subtask 4.2 — Update `apps/cockpit-ui/src/lib/sse.ts` to invalidate `['cases', caseId, 'intake', 'ubo_graph']` on `case.ubo_corrected`.

- [x] **Task 5 — UI: modal + canvas wiring** (AC: #6, #7, #11)
  - [x] Subtask 5.1 — `CorrectionTagModal.tsx` with shadcn `Dialog`.
  - [x] Subtask 5.2 — Extend `UBOCanvas.tsx` with `onEdgeUpdate`/`onEdgeUpdateStart`/`onEdgeUpdateEnd` wiring.
  - [x] Subtask 5.3 — `CorrectionTagModal.test.tsx`.

- [x] **Task 6 — TanStack mutation hook** (AC: #8, #12)
  - [x] Subtask 6.1 — `useUboCorrection.ts`.
  - [x] Subtask 6.2 — `useUboCorrection.test.ts`.

- [x] **Task 7 — Story 5.4 fixture update** (AC: #13)
  - [x] Subtask 7.1 — Add `vora-ubo-graph-after-correction.json` fixture.
  - [x] Subtask 7.2 — Visual snapshot test for officer_corrected style.

- [x] **Task 8 — End-to-end verification** (AC: #14, #15)
  - [x] Subtask 8.1 — `make demo-reset && make seed && make test` green.
  - [x] Subtask 8.2 — Manual demo per AC15.
  - [x] Subtask 8.3 — `make adk-spec` regenerates openapi.yaml; commit changes.

## Dev Notes

### Architectural context (binding)

* [Source: `architecture.md#Demo Scope Addendum (2026-04-29)`] No Ed25519 signing in the demo. Officer attribution is via `actor_id` only.
* [Source: `architecture.md#Project-Specific Patterns` P5 Officer Action Pattern] Bank-buyer scope mandates client-side WebCrypto sig + server verify. Demo replaces with logged-in-user attribution. Document this as a deliberate simplification in the new ledger payload's docstring.
* [Source: `architecture.md#Project-Specific Patterns` P6 SSE Event Pattern] Payload ≤ 256 bytes; ID-only; clients refetch via TanStack invalidation.
* [Source: `architecture.md#Validation timing`] Pydantic at the boundary. The endpoint validates `LearningEventInput`; the service's pure helper trusts the Pydantic types; the ledger writer validates the entry shape.
* [Source: `ux-design-specification.md` § Innovations 6 — Drag-correct-and-teach] Direct spatial correction with the agent asking permission. The "ask permission" surfaces as the opt-in checkbox in the modal.

### Critical pitfalls

1. **Don't try to compose multiple atomic ledger entries in this story.** The bank-buyer scope's "atomic UBO + evidence + learning_event commit" requires the evidence-attachment-with-hash flow that lands in Epic 8. The demo's "atomic" boundary is just the SQLite transaction inside `create_learning_event` — DB write + ledger append are NOT atomic across processes; if the ledger write fails after the DB commit, log loud and surface 500 (mirror Story 3.5's pattern). Document this as a known limitation.

2. **`X-Cockpit-Demo-User` header is the actor source of truth.** Story 1.4 wired the user-switcher; the API's `current_user_dep` reads the header (or falls back to the default analyst). **Don't** introduce a new auth mechanism for this story.

3. **`UBOEdge.confidence` is a `ProvenancedField`, not raw float.** When the helper rebuilds the corrected edge, the new `Provenance` must satisfy the band-vs-confidence consistency validator (Story 3.3 § AC3). Use `to_band(0.99)` → `HIGH`.

4. **`evidence_ids=[]` on the officer-corrected edge.** In bank-buyer scope, this would point to the evidence-attachment ledger entry (Story 8.6). Demo: empty list is fine. Don't try to back-fill with the just-written `learning_event` ledger entry's ID — that's a different shape (it's an officer-action entry, not an agent-action entry).

5. **`Literal` discriminator on `LedgerEntry.payload` union.** Pydantic 2 resolves left-to-right by `kind` literal. **Order matters in the union declaration:** `AgentActionLedgerEntry | LearningEventLedgerPayload | dict[str, Any]`. The dict fallback MUST be last; otherwise it always wins.

6. **`correction_tag="removed"` is the only path that mutates `nodes`.** All other tags only flip the edge's `nominee_flag`. If the officer dragged the edge to a different `to_id`, the helper has already updated `to_id`; the original target node may now be orphaned (has no incoming edges). Don't strip orphan nodes from the graph in this story — the canvas's empty rendering is fine. Story 5.9 may revisit.

7. **Tests must construct `LearningEventInput` without Story 5.4 fixture coupling.** The test fixture for `UBOGraph` should live in `apps/cockpit-api/tests/fixtures/ubo_graph_vora.py` (a plain Python module returning a frozen `UBOGraph`) — not the cockpit-ui fixture file. Avoids cross-app coupling.

8. **The endpoint's response is 201, not 200.** Resource-creation semantics. The spec lives on the `@router.post(... status_code=201)` decorator. RFC-pedantic.

9. **`captured_at` timestamps are tz-aware.** Per `Provenance` validator. Use `datetime.now(UTC)`, never naive `datetime.now()`.

10. **The opt-in flag is currently a no-op functionally.** Document it in the file as: "captured for future retraining loop; no current downstream consumer." Don't add a fake "training-data" pipeline. The flag's value is in the audit trail.

11. **`useUboCorrection` invalidates the UBO graph query.** It does NOT invalidate the risk_scoring query — Story 5.8 owns that wiring. Don't pre-empt.

### Story dependencies

* **Strict prereqs:** Story 5.3 (UBO Graph agent) for `UBOGraph`, `IntakeRepo`. Story 5.4 (UBOCanvas) for the canvas component to wire into. Story 1.4 (user-switcher) for `current_user_dep`. Story 3.1 (LedgerWriter) for `LedgerWriter.append`. Story 4.6 (SSE) for `publish_safe`.
* **Read by:** Story 5.8 (auto-recalc) — subscribes to `case.ubo_corrected` and triggers risk_scoring.

### Project Structure Notes

This story creates:
- `packages/contracts/src/contracts/learning_event.py`
- `packages/contracts/tests/test_learning_event.py`
- `apps/cockpit-api/src/cockpit_api/services/ubo_correction_service.py`
- `apps/cockpit-api/tests/test_ubo_correction_service.py`
- `apps/cockpit-api/tests/test_ubo_correction.py`
- `apps/cockpit-api/tests/fixtures/ubo_graph_vora.py`
- `apps/cockpit-ui/src/components/cockpit/UBOCanvas/CorrectionTagModal.tsx`
- `apps/cockpit-ui/src/components/cockpit/UBOCanvas/CorrectionTagModal.test.tsx`
- `apps/cockpit-ui/src/hooks/useUboCorrection.ts`
- `apps/cockpit-ui/src/hooks/useUboCorrection.test.ts`
- `apps/cockpit-ui/src/components/cockpit/UBOCanvas/__fixtures__/vora-ubo-graph-after-correction.json`

This story modifies:
- `packages/contracts/src/contracts/__init__.py` — re-exports
- `packages/contracts/src/contracts/ledger.py` — payload union extension
- `packages/contracts/src/contracts/sse.py` — `case.ubo_corrected` event literal
- `apps/cockpit-api/src/cockpit_api/routers/cases.py` — POST `/learning-events` route
- `apps/cockpit-ui/src/components/cockpit/UBOCanvas/UBOCanvas.tsx` — drag wiring
- `apps/cockpit-ui/src/lib/sse.ts` — invalidate UBO query on `case.ubo_corrected`

This story DOES NOT create:
- An evidence-attachment-with-hash flow (Story 8.6)
- A risk-recalc trigger (Story 5.8)
- A retraining pipeline (out of MVP scope)
- A signature verification flow (cut from demo)

### References

- [Source: `architecture.md#Demo Scope Addendum (2026-04-29)`] No Ed25519
- [Source: `architecture.md#Project-Specific Patterns` P5 / P6] Officer action; SSE event pattern
- [Source: `ux-design-specification.md` § UBOCanvas; § Innovation 6] drag-correct-and-teach contract
- [Source: `epics.md#Epic 5` § Story 5.6] original AC (re-scoped here)
- [Source: `prd.md#FR16, NFR-T6`] drag-correct learning event; reasoned correction floor
- [Source: `5-3-ubo-graph-agent-basic.md`] UBOGraph + nominee_flag values
- [Source: `5-4-ubo-canvas-component.md`] UBOCanvas drag-update wiring point
- [Source: `1-4-cockpit-shell-with-user-switcher-three-hardcoded-roles.md`] user-switcher + `current_user_dep`
- [Source: `4-6-sse-stream-endpoint-single-worker.md`] `publish_safe` + invalidation hook
- [Source: `3-1-append-only-ledger-schema-with-insert-only-writer.md`] `LedgerWriter` + payload union

### Demo verification protocol

```bash
make demo-reset && make seed
poetry -C apps/cockpit-api run python -c "
import asyncio
from contracts.cases import VORA_CAPITAL_ID
from agents.supervisor.case_supervisor import CaseSupervisor
from cockpit_api.db.session import session_factory
asyncio.run(CaseSupervisor(session_factory=session_factory).run_intake(VORA_CAPITAL_ID))
"

# Inspect Vora's UBO graph (3 nominee_suspected edges expected):
sqlite3 ./data/cockpit.db "SELECT json_extract(output_json, '\$.edges') FROM intake_results WHERE case_id='${VORA_CAPITAL_ID}' AND agent_id='ubo_graph';" | python -m json.tool | grep -c nominee_suspected
# Expected: 3

# Submit a correction:
ANALYST_ID=$(jq -r '.[] | select(.role=="analyst") | .id' apps/cockpit-api/fixtures/users.json)
curl -s -X POST "http://localhost:8000/v1/cases/${VORA_CAPITAL_ID}/ubo/learning-events" \
  -H 'Content-Type: application/json' \
  -H "X-Cockpit-Demo-User: ${ANALYST_ID}" \
  -d '{
    "edge_kind": "owns",
    "from_id": "ubo_e_coastal_equity_partners_pte_ltd",
    "original_to_id": "ubo_e_u67120mh2024ptc444789",
    "new_to_id": "ubo_e_u67120mh2024ptc444789",
    "correction_tag": "real_ubo",
    "evidence_note": "RM email 2024-11 disclosed offshore family trust",
    "opt_in_for_retraining": true
  }' | python -m json.tool

# Verify the ledger entry:
tail -n 1 ./data/ledger.jsonl | python -m json.tool
# Expected: actor_type=officer, action=ubo.edge_corrected, payload.kind=learning_event,
# payload.correction_tag=real_ubo, payload.opt_in_for_retraining=true

# Verify the UBO graph mutated:
sqlite3 ./data/cockpit.db "SELECT json_extract(output_json, '\$.edges') FROM intake_results WHERE case_id='${VORA_CAPITAL_ID}' AND agent_id='ubo_graph';" | python -m json.tool | grep -c nominee_suspected
# Expected: 2 (Coastal flipped to officer_corrected; Anchor + A K Filing still flagged)

# Lint + test:
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
| 2026-05-08 | Story 5.5 drafted. Demo replacement for the bank-buyer Story 5.6: drag-correct UI + tag modal + opt-in checkbox + officer-attributed `learning_event` ledger entry (no Ed25519 sig per re-scope). |
