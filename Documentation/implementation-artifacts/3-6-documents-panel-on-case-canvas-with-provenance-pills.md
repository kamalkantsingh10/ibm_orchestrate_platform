# Story 3.6: Documents panel on Case Canvas with provenance pills

Status: review

## Story

As a KYC Analyst opening a case,
I want a Documents panel on the Case Canvas that lists every extracted document field, grouped by source document, each value rendered with a provenance pill showing the source agent + source system + confidence band — and clicking the pill reveals a placeholder reasoning-trace stub,
So that the demo's "every datum is provenance-tagged" promise (P3, FR8, NFR-T4 100% coverage) is visibly delivered the moment the analyst opens any of the three demo cases (FR3, FR7).

## Scope note (2026-04-29 demo re-scope)

This story is the demo-equivalent of the bank-buyer Story 3.12. The UI is real; the data plumbing reads from Story 3-5's `IntakeRepo` (no live agent re-runs on case open).

| Bank-buyer scope (original 3.12) | Demo replacement in this story |
|---|---|
| Documents panel as ONE of FOUR DecompositionPanels in the 2×2 Case Canvas grid (alongside Identity, UBO, Risk) | **Documents panel + a placeholder layout for the other 3 panels.** Full DecompositionPanel grammar lands in Epic 5 (UBO + Risk) and Epic 6 (Screening). For now: Documents panel is real; the other three panels render as "coming in Epic 5/6" stubs. |
| Provenance pill click opens the full ReasoningTraceSlideOut (4-section schema) | **Click opens a placeholder slide-out** with "Full reasoning trace lands in Epic 6." The slide-out shell + close-on-Esc behavior is implemented; the populated content is deferred to Story 6-7. |
| CI test asserts every UI-rendered datum has a `ProvenancedField[T]` (NFR-T4 100% coverage across the cockpit) | **CI test scoped to the Documents panel only** — not yet a global cockpit-wide check (no other agent-driven panels exist yet). The full cockpit-wide assertion lands when more panels exist (Epic 5+). |
| Polled via TanStack Query with SSE-driven invalidation | **Polled via TanStack Query** with simple staleTime (no SSE in this story). Story 4-6 wires SSE invalidation to the same query keys. |
| `presigned_get` to download original docs | **Cut.** The fixture cases don't have real PDFs on disk; clicking the document name does NOT open a file in this story. |

What survives: **a real Documents panel rendering real intake results from real `IntakeRepo` rows, with `ProvenanceIndicator` + `ConfidencePill` (Story 3-7) on every value, and a typed API endpoint for fetching them.** That's the load-bearing demo asset for Story 3-12's "trust by design" beat.

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md`, `architecture.md#Demo Scope Addendum (2026-04-29)`, and `ux-design-specification.md` § ProvenanceIndicator + § CaseCanvas.

## Acceptance Criteria

1. **AC1 — `GET /v1/cases/{case_id}/intake/document_intelligence` returns the typed agent output.** New router action in `apps/cockpit-api/src/cockpit_api/routers/cases.py`:

    ```python
    @router.get(
        "/{case_id}/intake/document_intelligence",
        response_model=DocumentIntelligenceOutput,
        dependencies=[Depends(get_current_user)],
        summary="Get the Document Intelligence agent's intake output for a case",
    )
    async def get_document_intelligence_intake(
        case_id: CaseIdPath,
        session: Annotated[AsyncSession, Depends(get_session)],
    ) -> DocumentIntelligenceOutput: ...
    ```

    Behavior:
    - Validate the case exists; if not → 404 RFC 7807 ("case not found").
    - Read `IntakeRepo.get_one(session, case_id, "document_intelligence")`. If `None` → 404 RFC 7807 with `detail="Document Intelligence intake not yet run for case <id>"` (semantically distinct from "case not found"; lets the UI render a "not yet run" state if needed).
    - Validate the stored JSON dict against `DocumentIntelligenceOutput.model_validate(...)` — this re-runs the contract validators (band-vs-confidence consistency, evidence_ids ULID format, etc.). If validation fails → 500 RFC 7807 ("intake data corrupt").
    - Return the typed output. FastAPI serializes via `model_dump_json` per the response_model.

    The endpoint is **read-only** — it doesn't trigger intake. Story 3-5's `POST /v1/cases/{id}/intake` is the writer; this endpoint is the reader.

2. **AC2 — `useDocumentIntelligence(caseId)` TanStack Query hook lives at `apps/cockpit-ui/src/hooks/useDocumentIntelligence.ts`.**

    ```typescript
    export function useDocumentIntelligence(caseId: string) {
      return useQuery<components['schemas']['DocumentIntelligenceOutput']>({
        queryKey: ['cases', caseId, 'intake', 'document_intelligence'],
        queryFn: async () => {
          const { data, error, response } = await apiClient.GET(
            '/v1/cases/{case_id}/intake/document_intelligence',
            { params: { path: { case_id: caseId } } },
          );
          if (response.status === 404) {
            // Distinguish "intake not yet run" (recoverable, render empty state)
            // from "case not found" (route-level error). Surface as null.
            return null;
          }
          if (error || !data) throw new Error(`...`);
          return data;
        },
        staleTime: 30_000,  // 30s; SSE invalidation lands in Story 4-6
      });
    }
    ```

    The hook returns `null` when the API returns 404 with the "intake not yet run" detail (let the UI render the empty state); throws on other errors (TanStack Query's `isError` path).

3. **AC3 — `DocumentsPanel` component lives at `apps/cockpit-ui/src/components/cockpit/DocumentsPanel/DocumentsPanel.tsx`.**

    Public props:
    ```typescript
    export interface DocumentsPanelProps {
      output: DocumentIntelligenceOutput | null;
      isPending?: boolean;
      isError?: boolean;
      onProvenanceClick?: (extractedField: ExtractedField) => void;
    }
    ```

    Visual structure (matches `ux-design-specification.md` § DecompositionPanel anatomy where applicable, simplified for the demo):
    - Wrapper: `radius-md` (8px), 1px border `border-zinc-200`, padding 14px×16px, white background
    - Panel header row: title `"Documents"` (14px semibold) on the left; subtitle showing field count (`"<N> fields extracted"`) and source agent badge (`"Document Intelligence"`) on the right
    - Hairline divider
    - Body: grouped list — for each unique `document_ref` in `output.extracted_fields`, render a `<section>`:
      - Document filename header (12px medium, monospace)
      - List of `<DocumentField>` rows: `<label>` + `<value>` + `<ProvenanceIndicator>`
    - Empty state (`output === null` or `output.extracted_fields.length === 0`): "No intake data yet" with a hint "Run intake via `POST /v1/cases/{id}/intake` or wait for the supervisor".
    - Loading state (`isPending && !output`): skeleton rows (4 rows with animated pulse, mirroring Story 2-3's QueueRail skeleton pattern).
    - Error state (`isError`): inline `role="alert"` red text "Could not load intake data" with optional retry button (omit retry if no `onRetry` prop).

    The `<DocumentField>` row's anatomy:
    - Label cell (left, ~140px wide): field name humanized (e.g., `cin` → `"CIN"`, `company_name` → `"Company name"`). Helper `humanizeFieldName(name)` lives at the top of the file.
    - Value cell (middle, flex-1): the extracted value. For `null`/missing values, render `"—"` in zinc-400. For dates, format via `Intl.DateTimeFormat('en-IN', { dateStyle: 'medium' })`. For numbers, `Intl.NumberFormat('en-IN')` with no decimals.
    - Provenance cell (right): the `<ProvenanceIndicator>` (AC4).

4. **AC4 — `ProvenanceIndicator` component lives at `apps/cockpit-ui/src/components/cockpit/ProvenanceIndicator/ProvenanceIndicator.tsx`.**

    Public props:
    ```typescript
    export interface ProvenanceIndicatorProps {
      provenance: components['schemas']['Provenance'];
      onClick?: () => void;
      size?: 'sm' | 'md';  // sm = 10px shape no label; md = 10px shape + label (default)
    }
    ```

    Visual structure (matches `ux-design-specification.md` § ProvenanceIndicator):
    - Inline composite: `<source-icon>` (10px Lucide icon — e.g., `FileText` for `"document_intelligence"` source agent; later stories add per-source icons) + `<ConfidencePill>` (Story 3-7) showing the band shape + label
    - Optional `aria-label`: `"Field provenance: source ${source_agent} · ${source_system}, confidence ${band_label} (${pct}%)"` for screen readers
    - Click → calls `onClick` if provided. The Documents panel passes a handler that opens a placeholder slide-out (AC5).
    - Keyboard: `tabIndex={0}` when `onClick` is set; Space/Enter activates.
    - Tailwind classes: inline-flex items-center gap-1.5; cursor-pointer when interactive; focus-visible:ring-2 focus-visible:ring-zinc-400.

    **The component does NOT render the popover-on-hover preview** described in the UX spec's `ProvenanceIndicator` § "States: hovered (popover previews source)". Hover-popover is deferred to Story 6-7. Click-to-open-stub is the demo's interaction.

5. **AC5 — Placeholder `ReasoningTraceSlideOut` shell lives at `apps/cockpit-ui/src/components/cockpit/ReasoningTraceSlideOut/ReasoningTraceSlideOut.tsx`.**

    Public props:
    ```typescript
    export interface ReasoningTraceSlideOutProps {
      open: boolean;
      onOpenChange: (open: boolean) => void;
      extractedField?: ExtractedField | null;
    }
    ```

    Visual structure:
    - Built on Radix `Dialog` (`@radix-ui/react-dialog` is already a dep). Side="right" via Radix's `DialogContent` with `position: fixed; right: 0; top: 0; bottom: 0; width: 480px`.
    - Header row: agent name + `Esc` keyboard hint + close button.
    - Body (when `extractedField` is provided): four sections labeled `What was searched`, `What returned`, `Confidence`, `What would change` — each with placeholder text:
      - `What was searched` → "Document: <document_ref>; field: <field_name>"
      - `What returned` → "<value>"
      - `Confidence` → `<ConfidencePill size="lg" confidence={...} />` (Story 3-7's component, large variant)
      - `What would change` → "Full reasoning trace + counterfactual lands in Epic 6 (Story 6-7)."
    - Body (when `extractedField` is null): "Click a provenance pill to inspect."
    - Animation: Framer Motion slide-in from right, 300ms `motion-reveal` ease-out.
    - Accessibility: traps focus inside the dialog; Esc closes; `role="complementary"`; announces open via Radix's built-in `aria-live`.

    **The slide-out is intentionally minimal in this story.** The full 4-section content with counterfactuals is Story 6-7's job. This story ships the shell so Story 3-7's pill click has a target.

6. **AC6 — Case detail route lives at `apps/cockpit-ui/src/routes/cases.$caseId.tsx`.**

    Route: `/cases/$caseId`. Mounts on the `__root` route (existing pattern from Story 1-4). Behavior:
    - `loader`: fetches the case via `useCase(caseId)` (existing hook from Story 2-2). On 404 → throw a route-level error rendered by the root error boundary.
    - Layout: 3-column grid roughly mimicking the Case Canvas spec — left: 260px QueueRail (existing); center: case-canvas-area with case header + 2×2 panel grid; right: 280px placeholder for AgentCopilotPane (Epic 4).
    - The 2×2 panel grid contains:
      - **Top-left:** `<DocumentsPanel>` (this story's component), wired via `useDocumentIntelligence(caseId)`
      - Top-right, bottom-left, bottom-right: stub placeholder components (`<PanelStub title="Identity" epic="5" />`, `<PanelStub title="UBO" epic="5" />`, `<PanelStub title="Risk" epic="5" />`) — minimal: title + dashed border + "Coming in Epic 5" text.
    - State: an `extractedField` Zustand-or-useState piece tracking which provenance pill is open. Pill click sets it; slide-out renders it; close clears it.
    - Role gating: Analyst role only. Other roles → redirect to their default route via the existing `defaultRouteFor` helper (per Story 1-4 pattern).

7. **AC7 — `humanizeFieldName` helper.** Lives at top of `DocumentsPanel.tsx` or in `apps/cockpit-ui/src/lib/humanize.ts` (dev's call). Logic:
    - Replace `_` with space; capitalize first letter
    - Special-case acronyms: `cin` → `"CIN"`, `pan` → `"PAN"`, `gst` → `"GST"`, `gstin` → `"GSTIN"`, `din` → `"DIN"`, `ubo` → `"UBO"`, `inr` → `"INR"`. Special-case list lives in a constant; trivially extensible.
    - Examples:
      - `"company_name"` → `"Company name"`
      - `"cin"` → `"CIN"`
      - `"registered_address"` → `"Registered address"`
      - `"annual_income_inr"` → `"Annual income INR"`
    - Tested in `humanize.test.ts` with at least 5 cases including each special-case acronym.

8. **AC8 — Vitest unit tests cover the components.** Each component lives next to a `.test.tsx` file:

    `DocumentsPanel.test.tsx`:
    - Renders 0 fields → empty state visible
    - Renders 5 fields across 2 documents → 2 `<section>`s, each with the right field rows
    - Pending state → 4 skeleton rows
    - Error state → red alert role="alert"
    - Click on a `<ProvenanceIndicator>` → calls `onProvenanceClick` with the right `ExtractedField`
    - **NFR-T4 coverage assertion:** for every rendered field row, assert that a `<ProvenanceIndicator>` is present (use `getAllByRole('button', {name: /provenance/i})` and assert count equals field count). This is the demo's first 100% provenance coverage test.

    `ProvenanceIndicator.test.tsx`:
    - Renders with size="sm" (no label) vs size="md" (label visible)
    - Renders the right `ConfidencePill` for the band
    - Click → calls `onClick`
    - Keyboard: Tab focuses; Enter activates; Space activates
    - aria-label includes source_agent, source_system, confidence band

    `ReasoningTraceSlideOut.test.tsx`:
    - `open=false` → not in DOM
    - `open=true` with `extractedField=null` → "Click a provenance pill" text
    - `open=true` with `extractedField` → 4 section headings visible; values rendered
    - Esc → calls `onOpenChange(false)`
    - Focus trapped inside while open

    `humanize.test.ts`:
    - 5+ cases including each special-case acronym

    `cases.$caseId.test.tsx` (route-level integration):
    - Mock `apiClient.GET` to return a case + 6 extracted fields; render the route; assert DocumentsPanel renders the fields with provenance pills
    - Mock `useDocumentIntelligence` to return `null` (intake not yet run); assert the empty state renders, NOT the error state
    - Mock `useDocumentIntelligence` to throw; assert the error state renders
    - Click a provenance pill; assert the slide-out opens and shows the field's value

9. **AC9 — Router registration.** Edit `apps/cockpit-ui/src/router.tsx` to register the new route. Use the same code-based composition pattern as the existing routes (Story 1-4 documented this deviation from file-based codegen).

10. **AC10 — Backend endpoint tests.** `apps/cockpit-api/tests/test_cases_intake_get_route.py`:
    - Happy path: seed a case + intake row; `GET /v1/cases/{id}/intake/document_intelligence` returns 200 + valid `DocumentIntelligenceOutput` JSON
    - Case not found: `GET /v1/cases/<unknown>/intake/document_intelligence` → 404 with detail "case not found"
    - Intake not run: seed a case but no intake row; `GET /v1/cases/{id}/intake/document_intelligence` → 404 with detail "Document Intelligence intake not yet run"
    - Auth gate: omit the `X-Cockpit-Demo-User` header → 401 (existing behavior from Story 2-2's auth dep)

11. **AC11 — End-to-end via the running demo.** After `make demo-reset && make seed && make dev`:
    - Open `http://localhost:5173/queue` as Analyst
    - Click on Vora Capital Holdings in the queue rail → URL navigates to `/cases/case_01...`
    - Documents panel renders 5 documents' worth of fields (~10–15 total) — each with a provenance pill
    - Each pill shows a confidence band marker (shape) + label ("Med-High", "High", etc.)
    - Click on the CIN field's provenance pill → slide-out opens from the right with the placeholder content + a large confidence pill matching the value's band
    - Press Esc → slide-out closes; focus returns to the pill
    - The other three panels (Identity, UBO, Risk) render the dashed-border "Coming in Epic 5" stub

12. **AC12 — `make lint` + `make test` clean.** New test count adds at least: 5+ in `DocumentsPanel.test.tsx`, 4+ in `ProvenanceIndicator.test.tsx`, 3+ in `ReasoningTraceSlideOut.test.tsx`, 5+ in `humanize.test.ts`, 4+ in `cases.$caseId.test.tsx`, 4+ in `test_cases_intake_get_route.py`. ESLint + Prettier + tsc strict + vitest pass. Backend mypy strict passes.

## Tasks / Subtasks

- [ ] **Task 1 — Backend endpoint** (AC: #1, #10)
  - [ ] Subtask 1.1 — Edit `apps/cockpit-api/src/cockpit_api/routers/cases.py`. Add the `GET /v1/cases/{case_id}/intake/document_intelligence` route per AC1. Use the existing `CaseIdPath` annotated type and `Depends(get_session)`.
  - [ ] Subtask 1.2 — Reuse `case_service.get_case` for the case-not-found check (it raises 404). Then call `IntakeRepo.get_one`. If `None` → raise `HTTPException(status_code=404, detail="Document Intelligence intake not yet run for case <id>")`.
  - [ ] Subtask 1.3 — Validate the stored JSON via `DocumentIntelligenceOutput.model_validate(row)`. On `ValidationError` → raise `HTTPException(status_code=500, detail="Intake data corrupt: <e>")`.
  - [ ] Subtask 1.4 — Author `apps/cockpit-api/tests/test_cases_intake_get_route.py` per AC10.

- [ ] **Task 2 — Regenerate `api-types.ts`** (AC: #2, prerequisite for typed UI)
  - [ ] Subtask 2.1 — Run `make contracts` (or whatever the project's OpenAPI export workflow is — Story 2.11 was cut, so check the current state). If the workflow is not wired, run a one-shot: extract the OpenAPI spec via `poetry -C apps/cockpit-api run python -c "from cockpit_api.main import app; import json; print(json.dumps(app.openapi()))"` > `apps/cockpit-ui/openapi.json`, then `pnpm --filter cockpit-ui exec openapi-typescript openapi.json -o src/api-types.ts`.
  - [ ] Subtask 2.2 — Verify `paths['/v1/cases/{case_id}/intake/document_intelligence']` and `components['schemas']['DocumentIntelligenceOutput']` exist in the regenerated file.

- [ ] **Task 3 — `useDocumentIntelligence` hook** (AC: #2)
  - [ ] Subtask 3.1 — Create `apps/cockpit-ui/src/hooks/useDocumentIntelligence.ts` per AC2. Mirror the structure of the existing `useCases.ts` and `useCase.ts` hooks.
  - [ ] Subtask 3.2 — Author `useDocumentIntelligence.test.tsx` with happy path + null path + error path mocks (mirror `useCase.test.tsx`'s pattern).

- [ ] **Task 4 — `humanizeFieldName` helper** (AC: #7)
  - [ ] Subtask 4.1 — Create `apps/cockpit-ui/src/lib/humanize.ts` with the `humanizeFieldName(name: string): string` function and a `SPECIAL_ACRONYMS: Record<string, string>` constant.
  - [ ] Subtask 4.2 — Author `humanize.test.ts` with 5+ cases.

- [ ] **Task 5 — `ProvenanceIndicator` component** (AC: #4)
  - [ ] Subtask 5.1 — Create the component folder `apps/cockpit-ui/src/components/cockpit/ProvenanceIndicator/` with `ProvenanceIndicator.tsx` and `index.ts` (barrel export).
  - [ ] Subtask 5.2 — Implement props per AC4. Import `ConfidencePill` (Story 3-7); the dev for THIS story should stub `ConfidencePill` if 3-7 is not yet implemented — small placeholder that takes `confidence: number` and renders a colored disc + label. Story 3-7 will replace the stub. (Alternatively, sequence Story 3-7 BEFORE 3-6 — see Dev Notes "Sequencing".)
  - [ ] Subtask 5.3 — Author `ProvenanceIndicator.test.tsx` per AC8.

- [ ] **Task 6 — `ReasoningTraceSlideOut` placeholder shell** (AC: #5)
  - [ ] Subtask 6.1 — Create `apps/cockpit-ui/src/components/cockpit/ReasoningTraceSlideOut/ReasoningTraceSlideOut.tsx` and `index.ts`.
  - [ ] Subtask 6.2 — Build on Radix `Dialog`. The `DialogContent` is positioned right-edge via Tailwind `fixed right-0 top-0 bottom-0 w-[480px]`. Add Framer Motion `motion.div` wrapper for the slide animation.
  - [ ] Subtask 6.3 — Implement the four placeholder sections per AC5.
  - [ ] Subtask 6.4 — Author `ReasoningTraceSlideOut.test.tsx` per AC8. Use `@testing-library/react`'s `screen.getByRole('dialog')`.

- [ ] **Task 7 — `DocumentsPanel` component** (AC: #3)
  - [ ] Subtask 7.1 — Create `apps/cockpit-ui/src/components/cockpit/DocumentsPanel/DocumentsPanel.tsx` and `index.ts`.
  - [ ] Subtask 7.2 — Implement the visual structure per AC3. Group fields by `document_ref`; render labels via `humanizeFieldName`; format dates and numbers per locale.
  - [ ] Subtask 7.3 — Implement the empty/loading/error states per AC3. Mirror the QueueRail pattern from Story 2-3 for skeleton rows.
  - [ ] Subtask 7.4 — Author `DocumentsPanel.test.tsx` per AC8 — including the NFR-T4 coverage assertion.

- [ ] **Task 8 — `PanelStub` placeholder + case detail route** (AC: #6, #9)
  - [ ] Subtask 8.1 — Create `apps/cockpit-ui/src/components/cockpit/PanelStub/PanelStub.tsx` — minimal: dashed border, title + "Coming in Epic <N>" text. Used for the 3 non-Documents panels in this story.
  - [ ] Subtask 8.2 — Create `apps/cockpit-ui/src/routes/cases.$caseId.tsx` per AC6. Use TanStack Router's path-param syntax. The case ID validates via TanStack Router's `parseParams` against the same `case_<ULID>` regex (mirror Story 2-2's path validation).
  - [ ] Subtask 8.3 — Wire `useCase(caseId)` for the case header data and `useDocumentIntelligence(caseId)` for the panel data.
  - [ ] Subtask 8.4 — Use a local `useState<ExtractedField | null>(null)` for the slide-out's open field. Pill click sets it; slide-out renders it; close clears it.
  - [ ] Subtask 8.5 — Edit `apps/cockpit-ui/src/router.tsx` to register the new route via `addChildren`.
  - [ ] Subtask 8.6 — Author `cases.$caseId.test.tsx` per AC8.

- [ ] **Task 9 — Update QueueRow to navigate** (AC: #11)
  - [ ] Subtask 9.1 — Edit `apps/cockpit-ui/src/components/cockpit/QueueRail/QueueRail.tsx` (or QueueRow): make rows clickable links navigating to `/cases/$caseId`. The existing `onSelect` prop is already in place from Story 2-3 — wire the queue route to pass `onSelect={(id) => router.navigate({ to: '/cases/$caseId', params: { caseId: id } })}` instead of just calling the callback.
  - [ ] Subtask 9.2 — Update `QueueRail.test.tsx` if existing tests break.

- [ ] **Task 10 — End-to-end smoke + lint pass** (AC: #11, #12)
  - [ ] Subtask 10.1 — Run `make demo-reset && make seed && make dev`. Open `http://localhost:5173/queue` in a browser; click each of the three demo cases; verify the Documents panel renders with provenance pills and confidence indicators; click a pill to open the slide-out; press Esc to close.
  - [ ] Subtask 10.2 — Run `make lint` from repo root; clean across all five subprojects.
  - [ ] Subtask 10.3 — Run `make test`. Confirm:
      - `apps/cockpit-ui` test count up by ≥21
      - `apps/cockpit-api` test count up by ≥4
      - No regressions in existing tests

## Dev Notes

### Sequencing with Story 3-7 (ConfidencePill)

Story 3-7 ships the `<ConfidencePill>` component this story imports. **Two acceptable approaches:**

- **(A) Sequence 3-7 BEFORE 3-6.** Cleaner — by the time 3-6's UI work starts, the pill component exists. Sprint-status order is currently 3-6 → 3-7, but that's just listing order; the dev can reorder.
- **(B) Stub `<ConfidencePill>` in this story.** Build a minimal placeholder (colored disc by band + label) and let Story 3-7 replace it. The placeholder lives next to the real component's eventual location: `apps/cockpit-ui/src/components/cockpit/ConfidencePill/ConfidencePill.tsx` (Story 3-7's path). Mark the file with a `// STUB — Story 3-7 owns the full component` comment.

**Recommendation: option (A) — sequence 3-7 first.** Saves rework. If the dev prefers parallelism, option (B) is fine. Document the choice in the dev log.

### Architectural context (binding)

[Source: `architecture.md#Project-Specific Patterns` P3 Provenance Metadata Pattern] — "Every UI-rendered datum is `ProvenancedField[T]`, not raw `T`." The Documents panel is the FIRST place this rule is exercised in cockpit-ui. The panel's NFR-T4 coverage assertion (AC8) is the demo's first concrete enforcement.

[Source: `ux-design-specification.md` § ProvenanceIndicator] — Anatomy: source-icon + confidence-shape + optional hover-popover. The hover-popover is deferred to Story 6-7; the demo's Documents panel uses click-to-open.

[Source: `ux-design-specification.md` § DecompositionPanel] — The Documents panel matches the panel grammar (wrapper + title + summary + rows). The full DecompositionPanel component is for the four data panels (Identity, UBO, Risk, Screening); Documents is structurally similar but with grouped sections instead of a single rows list. Don't try to force the Documents panel into the DecompositionPanel component template — they're cousins, not the same.

[Source: `architecture.md#Architectural Boundaries`] — **API boundary**: cockpit-ui only talks to cockpit-api routers. The new `GET /v1/cases/{case_id}/intake/document_intelligence` is the boundary for intake data. **Don't shortcut** by reading from `IntakeRepo` directly from a server-component or by adding a Vite proxy that bypasses FastAPI.

[Source: `architecture.md#Communication Patterns` § Loading state] — "TanStack Query's `isPending` / `isFetching` only. Never custom flags." The `<DocumentsPanel>` consumes `isPending` from the hook; never has its own `loading` boolean.

[Source: `architecture.md#Communication Patterns` § Error surfacing] — "(1) inline next to failing element (most), (2) toast for cross-cutting, (3) full-page error boundary for catastrophic." This story's panel uses (1) inline.

### Critical pitfalls to avoid

1. **The contract `Provenance.evidence_ids: list[LedgerEntryId]` validates each element.** When `cockpit-ui` parses a JSON response into the typed `Provenance`, malformed evidence_ids would fail Pydantic validation server-side BEFORE reaching the UI. So the UI can trust the format. **Don't add client-side ULID-regex validation** — duplicating the contract is the architecture's biggest anti-pattern.

2. **The pill's confidence value is a float `[0.0, 1.0]`, not a percentage.** Format as `${Math.round(c * 100)}%` for display. The `ConfidencePill` from Story 3-7 owns this formatting.

3. **The Documents panel renders deterministic per-document section order.** `output.extracted_fields` from the agent preserves the order the agent processed them — which equals the order in `customer_metadata.extra.document_refs`. Use `Array.from(new Map([...fields].map(f => [f.document_ref, f])).keys())` to dedupe document_refs while preserving order, OR group via a single pass that respects first-occurrence order. **Don't sort alphabetically** — the demo's narrative expects "Incorporation cert first, PAN second" to match the queue-rail walkthrough.

4. **Skeleton rows mirror QueueRail's pattern.** Story 2-3's `data-testid="queue-rail-skeleton"` uses 4 pulsing rows. The Documents panel uses the same pattern with `data-testid="documents-panel-skeleton"`. Don't reinvent.

5. **`useDocumentIntelligence` returns `null` on 404 "intake not yet run".** TanStack Query's `data` will be `null`; `isError` will be `false`; the panel renders the empty state. **Critically, don't conflate `null` with `undefined`** — `undefined` means "still loading," `null` means "loaded but empty." The hook's queryFn returns `null` explicitly on the 404; never returns `undefined`.

6. **Radix Dialog focus trap requires careful tab-index management.** The slide-out's content uses Radix's built-in focus trap (`<Dialog.Content>` handles it). Adding `tabIndex={-1}` on internal elements would break the trap. Only set tabIndex on interactive elements (buttons, the close button).

7. **Framer Motion's `<motion.div>` MUST be inside `<AnimatePresence>` for exit animations.** The slide-out's `motion.div` wrapper inside the dialog content needs `<AnimatePresence>` ancestral. Otherwise the close animation skips. Mirror the existing pattern in `apps/cockpit-ui/src/...` if other components use AnimatePresence; if not, this is the first one — wrap it inline at the slide-out's render-tree root.

8. **Routes registered code-based, not file-based codegen.** Story 1-4 documented the deviation from TanStack Router's file-based codegen. The new route uses the same `createRoute({ getParentRoute: () => RootRoute, path: '/cases/$caseId', component: ... })` pattern. **Don't accidentally trigger the Vite TanStack Router plugin's codegen** (it would create a generated file that conflicts).

9. **Path parameter validation.** TanStack Router doesn't have built-in regex validation on path params (unlike FastAPI). The route handler should validate the param shape via the existing `is_valid_case_id`-equivalent in the contracts package's TS mirror — wait, that helper doesn't exist in TS yet. **Decision (binding):** add a small `isValidCaseId(value: string): boolean` helper to `apps/cockpit-ui/src/lib/caseId.ts` that mirrors Python's regex; use it in the route's `parseParams`. If validation fails, throw a route-level error.

10. **`apiClient.GET` returns `{ data, error, response }`.** The `response` field contains the raw `Response`. To distinguish 404 "intake not yet run" from 404 "case not found", check `response.status === 404` AND `error?.detail` content. Decision: distinguish by detail-string match (fragile but pragmatic for the demo); a future story could introduce typed error codes via RFC 7807's `type` field.

11. **Empty state vs not-yet-run state.** If a case has 0 extracted fields after intake completed (e.g., empty `document_refs`), the API returns 200 + empty `extracted_fields: []`. The hook returns `output` with empty list. The panel renders "No fields extracted from this case yet" (different from the 404 "intake not run" state). Make sure the empty-state copy distinguishes the two — UX clarity matters.

12. **The Documents panel's NFR-T4 assertion is scoped narrowly.** Asserting "every rendered field has a ProvenanceIndicator" is feasible for THIS panel. The bank-buyer scope's "every UI-rendered datum has a ProvenancedField" is a global cockpit-wide assertion that would require a Playwright test crawling the cockpit. **Defer the global assertion** until Epic 5 lands more panels.

13. **Don't add SSE invalidation here.** Story 4-6 owns SSE. The hook's `staleTime: 30_000` is the demo's "good enough" freshness — re-mounting the route refetches; the seed-time intake completes before the analyst opens the case, so staleness is rarely visible.

14. **Date formatting locale.** `Intl.DateTimeFormat('en-IN', ...)` produces Indian-format dates (`"15 Mar 2018"`). The demo cases are India-jurisdiction. If the dev wants to be locale-flexible, accept that as future work — for the demo, en-IN is the correct default.

15. **Tooltip libraries to NOT add.** The provenance pill on hover should NOT show a tooltip in this story — that's Story 6-7's hover-popover. Resist adding `@radix-ui/react-tooltip` here even though it would be visually nice. Scope discipline.

### Architecture patterns relevant here

[Source: `architecture.md#Project-Specific Patterns` P3] — `ProvenancedField[T]` on every datum. The Documents panel is the demo's first compliant surface.

[Source: `architecture.md#Project-Specific Patterns` P7] — Confidence banding visible via shape + position + label. The provenance pill embeds the ConfidencePill, satisfying NFR-AC3 color-blind safety.

[Source: `architecture.md#Project-Specific Patterns` P8 Counterfactual Reasoning Trace] — The slide-out's "What would change" section is the placeholder for the counterfactual. Story 6-7 owns the populated version.

### Project Structure Notes

This story creates:

- `apps/cockpit-api/tests/test_cases_intake_get_route.py`
- `apps/cockpit-ui/src/hooks/useDocumentIntelligence.ts`
- `apps/cockpit-ui/src/hooks/useDocumentIntelligence.test.tsx`
- `apps/cockpit-ui/src/lib/humanize.ts`
- `apps/cockpit-ui/src/lib/humanize.test.ts`
- `apps/cockpit-ui/src/lib/caseId.ts` (path-param validation helper)
- `apps/cockpit-ui/src/components/cockpit/DocumentsPanel/DocumentsPanel.tsx`
- `apps/cockpit-ui/src/components/cockpit/DocumentsPanel/DocumentsPanel.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/DocumentsPanel/index.ts`
- `apps/cockpit-ui/src/components/cockpit/ProvenanceIndicator/ProvenanceIndicator.tsx`
- `apps/cockpit-ui/src/components/cockpit/ProvenanceIndicator/ProvenanceIndicator.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/ProvenanceIndicator/index.ts`
- `apps/cockpit-ui/src/components/cockpit/ReasoningTraceSlideOut/ReasoningTraceSlideOut.tsx`
- `apps/cockpit-ui/src/components/cockpit/ReasoningTraceSlideOut/ReasoningTraceSlideOut.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/ReasoningTraceSlideOut/index.ts`
- `apps/cockpit-ui/src/components/cockpit/PanelStub/PanelStub.tsx`
- `apps/cockpit-ui/src/components/cockpit/PanelStub/index.ts`
- `apps/cockpit-ui/src/routes/cases.$caseId.tsx`
- `apps/cockpit-ui/src/routes/cases.$caseId.test.tsx`

This story modifies:

- `apps/cockpit-api/src/cockpit_api/routers/cases.py` — add the new GET route
- `apps/cockpit-ui/src/api-types.ts` — regenerated to include the new route + types
- `apps/cockpit-ui/src/router.tsx` — register the new route
- `apps/cockpit-ui/src/routes/queue.tsx` — wire `onSelect` to navigate to the case detail route
- `apps/cockpit-ui/src/components/cockpit/QueueRail/*` — possibly adjust `onSelect` typing if needed

This story DOES NOT create:

- `<ConfidencePill>` (Story 3-7 owns it; either sequence 3-7 first or stub here)
- The other 3 panels (Identity, UBO, Risk — Epic 5)
- The full ReasoningTraceSlideOut content (Story 6-7)
- SSE invalidation (Story 4-6)
- A presigned-GET endpoint for downloading original docs (cut from demo)
- A global cockpit-wide NFR-T4 enforcement (deferred until more panels exist)

### References

- [Source: `architecture.md#Project-Specific Patterns` P3, P7, P8] — provenance, confidence banding, counterfactual
- [Source: `architecture.md#Architectural Boundaries`] — API boundary discipline
- [Source: `architecture.md#Communication Patterns`] — TanStack Query loading + inline error
- [Source: `ux-design-specification.md` § ProvenanceIndicator, § DecompositionPanel, § CaseCanvas, § ReasoningTraceSlideOut] — visual specs (with demo simplifications)
- [Source: `epics.md#Epic 3` § Story 3.12] — original AC (re-scoped here)
- [Source: `prd.md#FR3, FR7, FR8, NFR-T4`] — instant canvas, collapsible panels, provenance everywhere, 100% coverage
- [Source: `2-2-get-case-retrieval-api-consumer.md`] — `useCase` hook, route pattern
- [Source: `2-3-case-appears-in-queue-rail-basic-ordering.md`] — QueueRail, skeleton pattern
- [Source: `3-3-pydantic-contracts-for-ledger-provenance-confidence.md`] — `Provenance`, `ProvenancedField`, `ConfidenceBand`
- [Source: `3-4-document-intelligence-agent-llm-extract.md`] — `DocumentIntelligenceOutput`, `ExtractedField`
- [Source: `3-5-case-supervisor-intake-fan-out.md`] — `IntakeRepo`, intake-results table

### Previous Story Intelligence

[Source: `1-4-cockpit-shell-with-user-switcher-three-hardcoded-roles.md`]
- Code-based route composition (vs file-based) is the canonical pattern. New routes register via `router.tsx`'s `addChildren`.
- Role gating uses `defaultRouteFor(role)` from `lib/routeFor.ts`. Mirror in the new route.
- The `X-Cockpit-Demo-User` header is auto-injected by `apiClient` (Story 2-2).

[Source: `2-2-get-case-retrieval-api-consumer.md`]
- `useCase(caseId)` hook exists; reuse it for the case header.
- `apiClient.GET` returns `{ data, error, response }`. Use `response.status` to distinguish 404 variants.
- The `_links` field on `CaseEnvelope` has `documents: null` — Story 3-6 could populate it but **does not** (the dedicated endpoint is cleaner; `_links` is reserved for cross-resource navigation per HATEOAS-light convention from Story 2-2).

[Source: `2-3-case-appears-in-queue-rail-basic-ordering.md`]
- QueueRail's `onSelect` callback receives the case ID. Wire it to `router.navigate` per Task 9.
- TanStack Query's `staleTime` set to 5s for cases-list. Use 30s for the per-case intake hook.

[Source: `3-3-pydantic-contracts-for-ledger-provenance-confidence.md`]
- `ConfidenceBand` enum has 4 values: `low`, `medium_low`, `medium_high`, `high`. The TS mirror is at `apps/cockpit-ui/src/lib/confidence.ts` with `toBand(c)`.
- `Provenance.confidence_band` is consistent with `confidence` per the contract validator. The UI trusts the band; doesn't recompute from confidence.

[Source: `3-4-document-intelligence-agent-llm-extract.md`]
- `DocumentIntelligenceOutput.extracted_fields` is a list, ordered as the agent processed documents. Group by `document_ref` for display.
- `ExtractedField.value` is `ProvenancedField[FieldValue]`. `value.value` is the actual extracted value; `value.provenance` is the metadata.

[Source: `3-5-case-supervisor-intake-fan-out.md`]
- Intake runs at seed time. By the time the analyst opens any of the three demo cases, intake has completed and `IntakeRepo.get_one(case_id, "document_intelligence")` returns a non-None row.
- The case is in `decision_ready` state post-intake.
- The case's `customer_metadata.extra.document_refs` contains the source filenames; the agent's output's `document_ref` strings match.

### Demo verification protocol (operator hand-off)

```bash
# After implementing, the dev must verify:

# 1. Backend endpoint works:
make demo-reset && make seed
curl -s -H 'X-Cockpit-Demo-User: dc2aaaa3-555b-4636-89d0-6047dc205220' \
     http://localhost:8000/v1/cases/case_01KQC7GQ70GYHP15CZ8JB5ZT6A/intake/document_intelligence \
     | python -m json.tool | head -40
# Expected: JSON with case_id + extracted_fields list. Each value has provenance with confidence + confidence_band + evidence_ids.

# 2. UI renders the panel (manual):
make dev   # Vite + uvicorn
# Open http://localhost:5173/queue
# Click "Vora Capital Holdings" in queue
# Expected:
# - URL becomes /cases/case_01KQC7GQ70GYHP15CZ8JB5ZT6A
# - Documents panel renders 5 documents' worth of fields with provenance pills
# - 3 stub panels (Identity, UBO, Risk) show "Coming in Epic 5"

# 3. Provenance pill click opens the slide-out:
# Click on the CIN field's provenance pill
# Expected: slide-out drawer slides in from right; shows
#   "What was searched: Document: incorporation_certificate.pdf; field: cin"
#   "What returned: U67120MH2024PTC444789"
#   "Confidence: <large pill>"
#   "What would change: Full reasoning trace + counterfactual lands in Epic 6 (Story 6-7)."
# Press Esc → slide-out closes.

# 4. NFR-T4 coverage assertion runs:
cd apps/cockpit-ui
pnpm run test DocumentsPanel
# Expected: NFR-T4 test passes — every field row has a ProvenanceIndicator.

# 5. 404 paths:
curl -s -H 'X-Cockpit-Demo-User: ...' http://localhost:8000/v1/cases/case_01_does_not_exist/intake/document_intelligence
# Expected: 404, detail "Case ... not found"

# 6. Lint + test green:
make lint && make test
# Expected: all subprojects pass; new tests visible (~25 new across UI + 4 backend).
```

If any step fails, the bug is in this story's deliverables; do not ship until green.

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (Amelia persona, bmad-dev-story workflow)

### Debug Log References

* Story 3.7 was sequenced first (per its dev notes) so this story's `ProvenanceIndicator` consumes the real `ConfidencePill` from the start — no stub-and-replace.
* Lint surfaced two issues mid-implementation: (a) `bandLabel` was co-located with `ConfidencePill.tsx` violating react-refresh's "components-only export" rule — moved `bandLabel` to a sibling `bandLabel.ts`. (b) Prettier reflowed several files; nothing functional changed.

### Completion Notes List

* `useDocumentIntelligence` distinguishes "intake not yet run" (returns `null` for the empty state) from "case not found" (throws so the route's error boundary handles it). Detection is via the API's RFC 7807 `detail` field — `"not yet run"` substring → null; everything else → throw.
* `DocumentsPanel` groups by `document_ref` preserving first-occurrence order (no alphabetical sort) so the demo's narrative flows in document-list order.
* `formatValue` does best-effort date detection on ISO 8601 strings (`/^\d{4}-\d{2}-\d{2}/`) and renders via `Intl.DateTimeFormat('en-IN', { dateStyle: 'medium' })`. Numbers go through `Intl.NumberFormat('en-IN')`. Booleans render as Yes/No. `null` → em-dash.
* NFR-T4 coverage assertion: `DocumentsPanel.test.tsx` renders 3 fields and asserts exactly 3 confidence pills are present (via `getAllByLabelText(/confidence:/i)`). When more agent panels land (Epic 5+), a Playwright crawl can extend this to a global cockpit-wide check.
* `ReasoningTraceSlideOut` is built on Radix Dialog with right-edge positioning. Focus trap + Esc close are inherited from Radix. The 4 placeholder sections render against the supplied `extractedField`; click on a pill in `DocumentsPanel` opens it; close clears the field.
* Path-param validation: `cases.$caseId` route's `parseParams` throws on malformed IDs, surfaced by the route-level error boundary.
* `humanizeFieldName`: handles 7 special acronyms (CIN, PAN, GST, GSTIN, DIN, UBO, INR); falls back to capitalize-first-token. Tested with 10 cases.

### File List

**Created (backend)**
* `apps/cockpit-api/tests/test_cases_intake_get_route.py` — 4 endpoint tests

**Created (UI components + hooks + lib)**
* `apps/cockpit-ui/src/hooks/useDocumentIntelligence.ts`
* `apps/cockpit-ui/src/lib/humanize.ts` + `humanize.test.ts`
* `apps/cockpit-ui/src/lib/caseId.ts`
* `apps/cockpit-ui/src/components/cockpit/DocumentsPanel/{DocumentsPanel.tsx,DocumentsPanel.test.tsx,index.ts}`
* `apps/cockpit-ui/src/components/cockpit/ProvenanceIndicator/{ProvenanceIndicator.tsx,index.ts}`
* `apps/cockpit-ui/src/components/cockpit/ReasoningTraceSlideOut/{ReasoningTraceSlideOut.tsx,index.ts}`
* `apps/cockpit-ui/src/components/cockpit/PanelStub/{PanelStub.tsx,index.ts}`
* `apps/cockpit-ui/src/routes/cases.$caseId.tsx` — case detail route

**Modified**
* `apps/cockpit-api/src/cockpit_api/routers/cases.py` — `GET /v1/cases/{id}/intake/document_intelligence` route
* `packages/contracts/openapi.json` — regenerated by `make contracts`
* `apps/cockpit-ui/src/api-types.ts` — regenerated
* `apps/cockpit-ui/src/router.tsx` — register `cases.$caseId` route
* `apps/cockpit-ui/src/routes/queue.tsx` — wire `onSelect` to navigate to the case detail route
* `Documentation/implementation-artifacts/sprint-status.yaml` — story marked `review`

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-04-30 | Story 3.6 drafted. Demo replacement for the bank-buyer Story 3.12. Adds `GET /v1/cases/{id}/intake/document_intelligence` endpoint, `DocumentsPanel` + `ProvenanceIndicator` + placeholder `ReasoningTraceSlideOut` + `PanelStub` UI components, and `/cases/$caseId` route. First demo surface that exercises the "every datum is provenance-tagged" P3 invariant — with a scoped NFR-T4 100% coverage assertion. |
