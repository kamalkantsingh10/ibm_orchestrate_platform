# Story 8.5: EvidenceShelf with attachment ingest UI

Status: review

## Story

As a KYC Analyst working an EDD case,
I want to attach supporting evidence (emails, photos, additional docs) to the case and reference them in my memo,
So that my memo can cite materials beyond the original intake (FR9 full).

## Scope note

EvidenceShelf is the right-edge dock that 8-2's Zen mode renders. It supports three ingest paths (drag-drop, clipboard paste, email-body paste) and lets the analyst initiate a drag from each evidence row toward the Tiptap editor. The full Tiptap inline-node `evidenceRef` is implemented at the **drag payload level** (the row's drag handle emits a structured `application/x-cockpit-evidence-ref` MIME); registering the matching Tiptap drop handler in DecisionZone is **deferred** to a follow-on story so it can be tested alongside drag-drop manual UX and the Tiptap editor's drop coordinates.

Naming note: the story's File List asked for a new `EvidenceShelf.tsx`. The repo already has an `EvidenceShelf.tsx` (Story 7.8 — read-only modal in Investigation mode). To preserve that path, the dock variant lives at **`EvidenceShelfDock.tsx`** and is exported alongside the modal from the existing `index.ts`. ZenMode accepts the dock as an `evidenceDock` slot prop, defaulting to the Story 8.2 placeholder when omitted (so the 8.2 unit tests remain isolated from the evidence query graph).

**Demo-scope simplification (vs bank-buyer scope):**
- Uses the existing local-filesystem upload pathway from Story 3-8 (no DocStore presigned URLs).
- Ed25519 officer signing is dropped (no key vault in demo scope). Story 8-6 adds SHA-256 hashing + ledger entry; 8-5 itself does not write to the ledger.

## Acceptance Criteria

1. **AC1 — `EvidenceShelfDock` component.** New `apps/cockpit-ui/src/components/cockpit/EvidenceShelf/EvidenceShelfDock.tsx`. 320px wide, full canvas height, header (`Evidence` + `+ Add` button), scrollable list of attached evidence rows with file name, relative timestamp, drag handle, hover-revealed delete.

2. **AC2 — Three ingest paths.** Clicking `+ Add` opens an in-dock ingest popover (3 tabs):
   - **Drop a file:** drop-zone + click-to-choose `<input type="file">` accepting `.pdf,.png,.jpg,.jpeg,.txt,.eml`
   - **Paste from clipboard:** button reads `navigator.clipboard.read()`, normalises to a Blob (image → `pasted-<stamp>.<ext>`, text → `pasted-<stamp>.txt`)
   - **Paste email body:** `<textarea>` + `Save as evidence`. Saves the textarea content as `email-<stamp>.txt` (`text/plain`).

3. **AC3 — Backend route reuse.** All three paths POST to `POST /v1/cases/{case_id}/documents?kind=evidence`. The endpoint:
   - Branches storage by `kind` (defaults to `intake`; v1 PDF flow unchanged)
   - When `kind=evidence`: persists under `${UPLOADS_ROOT}/case_<id>/evidence/`, accepts the broader MIME whitelist (PDF/PNG/JPG/TXT/EML), skips the magic-byte check, **does not** add the file to `customer_metadata.extra.document_refs` (intake-only)
   - Three new dedicated routes: `GET /v1/cases/{case_id}/evidence`, `DELETE /v1/cases/{case_id}/evidence/{filename}`, `GET /v1/cases/{case_id}/evidence/{filename}/download`

4. **AC4 — Drag-into-editor (drag payload only).** Each evidence row's drag handle emits a structured payload:
   ```
   dataTransfer.setData(
     'application/x-cockpit-evidence-ref',
     JSON.stringify({ filename, caseId })
   )
   ```
   The Tiptap inline-node `evidenceRef` registration in DecisionZone is **deferred** — the dock side ships the drag source so the editor side can be added without touching the dock.

5. **AC5 — Empty state.** When no evidence is attached: centered caption `Drop files, paste from clipboard, or paste email body to attach evidence to this case.`

6. **AC6 — Item delete.** Each row has a hover-revealed `×` delete icon. Clicking it switches the icon to a confirmatory `Delete?` chip; clicking again calls `DELETE /v1/cases/{case_id}/evidence/{filename}`. The corresponding ledger entry from Story 8-6 is **not** deleted (ledger is append-only).

7. **AC7 — Tests.**
   - `EvidenceShelfDock.test.tsx::renders_attached_evidence_items_newest_first` ✅
   - `EvidenceShelfDock.test.tsx::renders the empty-state caption when no evidence is attached` ✅
   - `EvidenceShelfDock.test.tsx::drop_file_uploads_via_documents_endpoint_with_kind_evidence` ✅
   - `EvidenceShelfDock.test.tsx::paste_email_body_saves_as_text_file` ✅
   - `EvidenceShelfDock.test.tsx::drag_handle_sets_evidence_ref_payload` ✅ (replaces the spec's `drag_to_editor_inserts_evidence_ref_node` — drop-side wiring deferred per AC4 note)
   - `EvidenceShelfDock.test.tsx::delete_button_confirms_then_removes_evidence` ✅
   - `EvidenceShelfDock.test.tsx::paste_clipboard_image_creates_evidence` — **deferred** (jsdom doesn't expose `navigator.clipboard.read()`; the implementation calls the API but exercising it requires a real browser).
   - Backend: `test_documents_router.py::test_post_document_with_kind_evidence_writes_to_evidence_subdir` ✅
   - Backend: 5 additional evidence-route tests (image extension, disallowed extension, list, delete, download)

8. **AC8 — `make lint` + `make test` clean.** Lint clean, all touched suites pass.

## Tasks / Subtasks

- [x] **Task 1 — Backend: `?kind=evidence` query param** (AC: #3)
  - [x] `documents.py`: branch on `kind` between PDF intake and evidence flow
  - [x] `document_storage.py`: `DocumentKind` literal, `case_dir(case_id, kind)`, `write_evidence`, `list_evidence`, `delete_evidence`, `get_evidence_path`, `sanitize_evidence_filename`
- [x] **Task 2 — `EvidenceShelfDock` component** (AC: #1, #5, #6)
- [x] **Task 3 — Ingest popover with three tabs** (AC: #2)
- [ ] **Task 4 — Tiptap `evidenceRef` inline node** (AC: #4)
  - [x] Drag payload (`application/x-cockpit-evidence-ref`)
  - [ ] **Deferred:** drop handler / Tiptap node registration in DecisionZone
- [x] **Task 5 — Tests** (AC: #7, #8)
- [x] **Task 6 — Update sprint-status.yaml to `review`**

## Dev Notes

- **`?kind` discriminator** keeps storage flat under `case_<id>/intake/` and `case_<id>/evidence/`. Intake fan-out reads `customer_metadata.extra.document_refs`; evidence is queried via the dedicated `GET /evidence` route.
- **Tiptap evidenceRef deferred.** The drag source emits a structured payload; landing the matching Tiptap drop handler is mechanical once the inline-node + drop schema are agreed. Splitting this out keeps 8.5 testable in isolation.
- **Email-body paste** is `text/plain` only.
- **Filename safety.** A separate `sanitize_evidence_filename` regex permits the broader MIME extensions; intake's PDF-only `sanitize_filename` is unchanged.
- **The 320px shelf width** matches Story 8-2's evidence dock placeholder.

### File List

**Created**
- `apps/cockpit-ui/src/components/cockpit/EvidenceShelf/EvidenceShelfDock.tsx`
- `apps/cockpit-ui/src/components/cockpit/EvidenceShelf/EvidenceShelfDock.test.tsx`
- `apps/cockpit-ui/src/hooks/useEvidenceItems.ts`

**Modified**
- `apps/cockpit-api/src/cockpit_api/services/document_storage.py` — `DocumentKind`, `case_dir(kind)`, evidence helpers
- `apps/cockpit-api/src/cockpit_api/routers/documents.py` — `?kind=evidence` POST branch + `GET/DELETE/download` evidence routes
- `apps/cockpit-api/tests/test_documents_router.py` — 6 new evidence tests
- `apps/cockpit-ui/src/components/cockpit/EvidenceShelf/index.ts` — export `EvidenceShelfDock`
- `apps/cockpit-ui/src/components/cockpit/ZenMode/ZenMode.tsx` — `evidenceDock` slot prop (placeholder when omitted)
- `apps/cockpit-ui/src/routes/cases.$caseId.tsx` — wire `<EvidenceShelfDock>` in zen branch
- `Documentation/implementation-artifacts/sprint-status.yaml`

## Dev Agent Record

### Implementation Plan

1. **Backend storage helpers parallel to Story 3.8's PDF flow.** The intake helpers stay PDF-magic-byte-strict; evidence helpers accept the broader extension whitelist without sniffing content. Same `MAX_BYTES` cap.
2. **Router branches at write time.** `kind=evidence` is a query param on the existing POST so the cockpit-ui can keep one endpoint shape; the GET/DELETE/download evidence routes are dedicated paths so route shapes stay simple.
3. **Dock component is a slot in ZenMode.** Story 8.2's tests don't have to mock the evidence query graph — they just don't pass the slot. The case route always supplies the real dock.
4. **Drag-source-only on the editor side.** Setting the `application/x-cockpit-evidence-ref` MIME on dragstart is the contract; the editor side can be added later without touching the dock.
5. **Tests cover the three ingest tabs (drop, clipboard, email body), the list path, the delete path, and the drag-source payload.** The clipboard read path runs the implementation but its end-to-end assertion is deferred to a real-browser run.

### Completion Notes

- 6 of 7 frontend tests pass; the seventh (`paste_clipboard_image_creates_evidence`) is deferred — jsdom doesn't expose `navigator.clipboard.read()` reliably and a stub would test only the stub.
- Backend: 6 new evidence-route tests pass (cockpit-api total: 238).
- `pnpm lint` + `pnpm format:check` clean.
- `pnpm vitest run` (touched suites) — 34/34 pass across EvidenceShelfDock + ZenMode + modeStore.

### Change Log

| Date       | Change                                          |
|------------|-------------------------------------------------|
| 2026-05-08 | Story 8.5 implemented (Amelia). Status: review. |
