# Story 7.8: Basic Evidence shelf (read-only) for context

Status: review

## Story

As a KYC Analyst,
I want a side-rail "Evidence" toggle in the Decision Zone header that opens a read-only `EvidenceShelf` panel listing the case's documents (filename, page count if available) and per-document extracted-fields summary (top fields by confidence) — sourced from the existing intake row's `document_intelligence` payload — so I can reference the case's evidentiary base while drafting the rationale, without leaving the Decision Zone or opening a separate route,
So that Priya doesn't have to scroll up to the DocumentsPanel to recall a CIN value mid-rationale, the demo's J1 narrative ("she writes referencing what she sees") has a tactile UI surface, and Story 8-5's full attachment-ingest UI has a host shelf to extend (FR9 partial — view evidence on the side; cut from bank-buyer Story 7.14: full attachment upload, SHA-256 verification — those land in Epic 8).

## Scope note (2026-04-29 demo re-scope)

This story is the demo-equivalent of the bank-buyer Story 7.14 (which was a candidate cut at item #9 in the re-scope's ranked cut list but **kept**). Read-only is the load-bearing constraint here.

| Bank-buyer scope (original 7.14) | Demo replacement |
|---|---|
| Read-only evidence shelf alongside Decision Zone | **Same** — a Radix Dialog Sheet (right-side drawer) toggled by an "Evidence" button in the Decision Zone header. |
| Lists each document + extracted-fields summary | **Same** — uses Story 3-4's `DocumentIntelligenceOutput` from the intake row. |
| Tenant-scoped query | **Single-tenant.** |
| Full attachment-ingest UI lands in Epic 8 (Story 8.5) | **Same.** Out of scope here. |
| SHA-256 hash visible | **Cut for demo** (Demo Scope Addendum drops document SHA-256 hashing). |

What survives: **the entire toggle + drawer + read-only listing primitive.**

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md`, `architecture.md#Frontend Architecture`, `ux-design-specification.md` § EvidenceBundleShelf (line 1517–1521), `prd.md#Functional Requirements` FR9.

## Acceptance Criteria

1. **AC1 — `EvidenceShelf` component at `apps/cockpit-ui/src/components/cockpit/EvidenceShelf/EvidenceShelf.tsx`.**

    ```typescript
    export interface EvidenceShelfProps {
        caseId: string;
        open: boolean;
        onOpenChange: (open: boolean) => void;
    }

    export function EvidenceShelf({ caseId, open, onOpenChange }: EvidenceShelfProps): JSX.Element {
        const { data: docIntel, isPending } = useDocumentIntelligence(caseId);   // existing Story 3-4 hook
        // ... render Radix Dialog as a right-side drawer
    }
    ```

    Layout (320 px wide drawer from right):
    * **Header** (`flex items-center justify-between px-4 py-3 border-b`):
        * Title: "Evidence" (text-base font-semibold).
        * Close button (Lucide `<X />` icon).
    * **Body** (`flex-1 overflow-y-auto px-4 py-3 space-y-4`):
        * Empty state when no docs: "No documents on this case." (text-zinc-500 text-sm).
        * Loading state: 3 skeleton rows.
        * Per-document section: filename (text-sm font-medium), small "n fields extracted" subtitle, then a `<dl>` listing the top 3 fields by `value.provenance.confidence` (descending). Each field: `<dt>` field name (text-xs uppercase tracking-wide text-zinc-500); `<dd>` value (text-sm font-mono text-zinc-900) + `<ConfidencePill>` (existing Story 3-7 component) with `variant="inline"`.
    * **Motion**: Radix Dialog's default slide-in-from-right; `motion-reduce:transition-none` honored.

    Use Radix Dialog (not a custom drawer). Mirrors Story 6-6's slide-out style at smaller width.

2. **AC2 — Decision Zone header "Evidence" toggle button.**

    Extend Story 7-1's `DecisionZone.tsx` header bar with an evidence toggle:

    ```tsx
    <header className="flex items-center justify-between px-5 py-3 border-b border-zinc-200">
        <div className="flex items-center gap-3">
            <h2>Decision Zone</h2>
            <StatePill state={caseData?.state} />
        </div>
        <div className="flex items-center gap-2">
            <button
                type="button"
                onClick={() => setEvidenceOpen((v) => !v)}
                aria-pressed={evidenceOpen}
                className="px-2.5 py-1 rounded text-xs font-medium text-zinc-700 ring-1 ring-zinc-200 hover:bg-zinc-50 focus-visible:ring-2 focus-visible:ring-blue-500"
            >
                Evidence{docCount ? ` (${docCount})` : ''}
            </button>
            <OutcomeSelector ... />
        </div>
    </header>
    ```

    `docCount` = `docIntel?.extracted_fields.length` grouped by `document_ref`, or simpler: `new Set(docIntel?.extracted_fields.map(f => f.document_ref)).size`.

    The toggle button is keyboard-accessible (Tab from outcome selector). Pressing Enter / Space toggles. The `aria-pressed` reflects the open state.

3. **AC3 — Mount the shelf at the route level (not nested inside Decision Zone).**

    Radix Dialog should be mounted near the page root to portal correctly. In `apps/cockpit-ui/src/routes/cases.$caseId.tsx`:

    ```tsx
    const [evidenceOpen, setEvidenceOpen] = useState(false);
    // ... pass setEvidenceOpen down to DecisionZone via prop OR via a Zustand store
    // ...
    <DecisionZone caseId={caseId} onToggleEvidence={() => setEvidenceOpen(v => !v)} evidenceOpen={evidenceOpen} />
    <EvidenceShelf caseId={caseId} open={evidenceOpen} onOpenChange={setEvidenceOpen} />
    ```

    Or use a small Zustand slice (`useEvidenceShelfStore`) to avoid the prop-drill. **Pick the prop approach** for simplicity — only two consumers, no widening surface.

4. **AC4 — Group extracted fields by `document_ref`.**

    `DocumentIntelligenceOutput.extracted_fields` is a flat list of `ExtractedField` objects with a `document_ref` attribute. The shelf groups them per document and shows top-N by confidence.

    Helper `apps/cockpit-ui/src/components/cockpit/EvidenceShelf/groupFields.ts`:

    ```typescript
    export function groupByDocument(fields: ExtractedField[]): Map<string, ExtractedField[]> {
        const out = new Map<string, ExtractedField[]>();
        for (const f of fields) {
            const list = out.get(f.document_ref) ?? [];
            list.push(f);
            out.set(f.document_ref, list);
        }
        return out;
    }

    export function topByConfidence(fields: ExtractedField[], n: number = 3): ExtractedField[] {
        return [...fields].sort((a, b) => b.value.provenance.confidence - a.value.provenance.confidence).slice(0, n);
    }
    ```

    Tests for this helper at `groupFields.test.ts`: empty input → empty map; single doc → grouped; sort stable; n bound respected.

5. **AC5 — `Esc` closes; focus returns to the toggle button.**

    Radix Dialog handles Esc + focus restoration automatically. Verify in tests by triggering Esc while shelf is open and asserting `document.activeElement === toggleButton`.

6. **AC6 — `motion-reduce` respect.**

    Radix Dialog's overlay + content transitions honor `prefers-reduced-motion` via Radix's built-in classes. **No custom motion in this story.** Verify by mocking `matchMedia`.

7. **AC7 — Click on extracted field → open Story 6-6's reasoning trace slide-out (optional polish).**

    Each extracted field's value chip is wrapped in a button that dispatches `cockpit:open-trace` with the field's `value.provenance.evidence_ids[0]` (the Doc Intel agent's ledger entry id, back-filled by Story 3-4's supervisor). **Optional**: this is polish; if Story 6-6's slide-out doesn't gracefully handle the EvidenceShelf being open simultaneously (z-index stacking), defer the click handler. **For the demo**, ship without the click; the shelf is read-only context. Tests AC8 cover both modes — verify via spec.

    **Recommendation**: ship without the click handler in this story; visual context only. Add a polish task if time permits.

8. **AC8 — Tests at `apps/cockpit-ui/src/components/cockpit/EvidenceShelf/EvidenceShelf.test.tsx`.**

    * Renders nothing visible when `open=false`.
    * When `open=true` + intake data present → shelf visible with N document sections.
    * Empty state when `docIntel?.extracted_fields` is empty.
    * Loading state when `isPending`.
    * Per-document: top 3 fields by confidence shown.
    * Each field shows `ConfidencePill` with the right confidence value.
    * Esc closes (assert `onOpenChange(false)` fired).
    * Reduced motion: animation classes absent.

9. **AC9 — Tests at `groupFields.test.ts`.**

    * `groupByDocument` empty input → empty map.
    * Multiple docs grouped correctly; field order within group preserved.
    * `topByConfidence` returns top N; ties broken consistently.
    * `topByConfidence(fields, 0)` returns empty array.

10. **AC10 — Tests at `DecisionZone.test.tsx` (extend).**

    * Evidence toggle button rendered in header.
    * Click → `onToggleEvidence` callback fires.
    * Toggle button shows doc count when `docCount > 0` ("Evidence (3)").
    * Toggle button shows "Evidence" alone when `docCount` is 0 or null.
    * `aria-pressed` reflects shelf open state.

11. **AC11 — Tests at `cases.$caseId.test.tsx` (extend).**

    * EvidenceShelf mounted; default closed.
    * DecisionZone toggle click → shelf opens.
    * Clicking the shelf's close button → shelf closes.

12. **AC12 — `make lint && make test` clean.** Net new test count: ≥ 8 in `EvidenceShelf.test.tsx`, ≥ 4 in `groupFields.test.ts`, ≥ 5 in `DecisionZone.test.tsx` (extend), ≥ 2 in `cases.$caseId.test.tsx` (extend).

13. **AC13 — End-to-end manual demo.**

    1. Open Vora's case after intake completes.
    2. Decision Zone header shows "Evidence (4)" toggle (Vora has 4 documents per seed).
    3. Click toggle → shelf slides in from right (~300 ms).
    4. Shelf shows 4 document sections; each lists top 3 fields by confidence (e.g., for incorporation_certificate.pdf: "CIN U24232MH1995PLC089123 [HIGH]", "Company Name VORA CAPITAL PVT LTD [HIGH]", "Registered Address ... [MEDIUM_HIGH]").
    5. Press Esc → shelf closes; focus returns to the Evidence toggle button.
    6. Click toggle again → shelf reopens.
    7. With Decision Zone in focus (per Story 7-2's tonal shift), the shelf opens over the dimmed canvas without ambiguity.
    8. macOS Reduce Motion ON → shelf appears instantly (no slide animation).

## Tasks / Subtasks

- [x] **Task 1 — `EvidenceShelf` component + helper** (AC: #1, #4, #5, #8, #9)
  - [x] Subtask 1.1 — `EvidenceShelf.tsx`.
  - [x] Subtask 1.2 — `groupFields.ts` helper.
  - [x] Subtask 1.3 — `index.ts` re-export.
  - [x] Subtask 1.4 — `EvidenceShelf.test.tsx` (≥ 8 cases).
  - [x] Subtask 1.5 — `groupFields.test.ts` (≥ 4 cases).

- [x] **Task 2 — DecisionZone header toggle** (AC: #2, #10)
  - [x] Subtask 2.1 — Add Evidence button to DecisionZone header bar.
  - [x] Subtask 2.2 — Wire `onToggleEvidence` + `evidenceOpen` props.
  - [x] Subtask 2.3 — Extend `DecisionZone.test.tsx` (≥ 5 cases).

- [x] **Task 3 — Route mounting** (AC: #3, #11)
  - [x] Subtask 3.1 — Mount `<EvidenceShelf>` in `cases.$caseId.tsx`.
  - [x] Subtask 3.2 — Local useState + prop wiring to DecisionZone.
  - [x] Subtask 3.3 — Extend `cases.$caseId.test.tsx` (≥ 2 cases).

- [x] **Task 4 — Verification** (AC: #12, #13)
  - [x] Subtask 4.1 — `make lint && make test` green.
  - [x] Subtask 4.2 — Manual demo per AC13.

## Dev Notes

### Architectural context (binding)

* [Source: `architecture.md#Frontend Architecture`] Radix UI primitives, Tailwind 4, Lucide icons.
* [Source: `architecture.md#Frontend Architecture` § F1] TanStack Query — reuses Story 3-4's `useDocumentIntelligence` hook; no new fetch.
* [Source: `architecture.md#Project-Specific Patterns` § P3 Provenance] each `ExtractedField.value` carries a `Provenance.confidence` for sorting.
* [Source: `architecture.md#Demo Scope Addendum` § Stack changes] no SHA-256 hashing of documents in demo.
* [Source: `ux-design-specification.md` § EvidenceBundleShelf (line 1517-1521)] 320 px width, slide from right.
* [Source: `prd.md#Functional Requirements` FR9] view attached evidence.

### Critical pitfalls

1. **Don't refetch.** `useDocumentIntelligence(caseId)` is already in TanStack cache from when DocumentsPanel rendered. Reuse the same query key; no new endpoint.

2. **No upload, no edit, no SHA-256.** All three are Epic 8 territory (Story 8-5). The shelf is purely read-only listing. Don't accidentally add file inputs or hash displays.

3. **The shelf's z-index sits above Decision Zone but below modal-style overlays.** Radix Dialog's default z-index handling works; verify by opening the shelf simultaneously with Story 7-5's UndoPill modal — the modal should win (it's a focused interaction). If z-stacking misbehaves, leave the shelf at default and the modal's higher index will dominate.

4. **Top-3 by confidence is heuristic, not guaranteed visible to demo viewers.** If a document has fewer than 3 fields extracted, show all of them. If it has more than 3, "View all" link → expanded inline list. **Demo simplification**: just show top 3; no "View all". Tests AC8 verify the cap.

5. **Field grouping by `document_ref` may produce one section** (single-document case) — render that as one section, no special-case. Tests AC8 verify single-doc rendering.

6. **The toggle button's text is "Evidence (N)" or just "Evidence"** — keep concise. Don't expand to "View Evidence (3 documents)" — clutter.

7. **`aria-pressed` is the right ARIA for a toggle button.** Don't use `aria-expanded` (that's for disclosures of inline content). Tests AC10 verify.

8. **No "Add evidence" call-to-action.** Cut from demo. The shelf header has only "Evidence" + close button.

9. **Radix Dialog is the right primitive even for a non-modal drawer.** It provides focus trap, Esc, focus restoration, ARIA. Don't roll a custom Sheet.

### Story dependencies

* **Strict prereqs:** Story 7-1 (DecisionZone host), Story 3-4 (`useDocumentIntelligence` hook + `DocumentIntelligenceOutput`), Story 3-7 (`ConfidencePill`), Story 3-6 (DocumentsPanel — same data source).
* **Read by:** Story 8-5 (full attachment-ingest UI extends this shelf).

### Project Structure Notes

This story creates:
- `apps/cockpit-ui/src/components/cockpit/EvidenceShelf/EvidenceShelf.tsx`
- `apps/cockpit-ui/src/components/cockpit/EvidenceShelf/EvidenceShelf.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/EvidenceShelf/groupFields.ts`
- `apps/cockpit-ui/src/components/cockpit/EvidenceShelf/groupFields.test.ts`
- `apps/cockpit-ui/src/components/cockpit/EvidenceShelf/index.ts`

This story modifies:
- `apps/cockpit-ui/src/components/cockpit/DecisionZone/DecisionZone.tsx` — adds Evidence toggle button + props
- `apps/cockpit-ui/src/components/cockpit/DecisionZone/DecisionZone.test.tsx` — extend
- `apps/cockpit-ui/src/routes/cases.$caseId.tsx` — mounts `<EvidenceShelf>`
- `apps/cockpit-ui/src/routes/cases.$caseId.test.tsx` — extend

This story does NOT create:
- File upload UI (Story 8-5)
- Document SHA-256 hashing (cut from demo)
- A new endpoint (reuses Story 3-4's intake fetch)
- A new motion preset (uses Radix Dialog defaults)

### References

- [Source: `epics.md#Epic 7` § Story 7.14] verbatim shape preserved
- [Source: `architecture.md#Frontend Architecture`]
- [Source: `architecture.md#Project-Specific Patterns`] § P3
- [Source: `ux-design-specification.md` § EvidenceBundleShelf]
- [Source: `prd.md#Functional Requirements`] FR9
- [Source: `7-1-decision-zone-component-with-tiptap-editor.md`] host component
- [Source: `apps/cockpit-ui/src/hooks/useDocumentIntelligence.ts`] data source
- [Source: `apps/cockpit-ui/src/components/cockpit/DocumentsPanel/`] sibling rendering reference

### Demo verification protocol

Per AC13.

If any step fails, the bug is in this story; do not ship until green.

## Dev Agent Record

### Agent Model Used

(claude-opus-4-7 + Amelia persona, bmad-dev-story workflow)

### Debug Log References

### Completion Notes List

### File List

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-05-08 | Story 7.8 drafted. Read-only EvidenceShelf as right-side Radix Dialog drawer toggled from DecisionZone header; lists each document with top-3-by-confidence extracted fields; reuses Story 3-4's intake query (no new fetch); upload + SHA-256 deferred to Epic 8. |
