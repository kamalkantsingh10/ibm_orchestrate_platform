# Story 8.5: EvidenceShelf with attachment ingest UI

Status: backlog

## Story

As a KYC Analyst working an EDD case,
I want to attach supporting evidence (emails, photos, additional docs) to the case and reference them in my memo,
So that my memo can cite materials beyond the original intake (FR9 full).

## Scope note

EvidenceShelf is the right-edge dock that 8-2's Zen mode renders. It supports three ingest paths (drag-drop, clipboard paste, email-body paste) and lets the analyst drag an evidence item into the Tiptap editor to insert an inline reference chip.

**Demo-scope simplification (vs bank-buyer scope):**

- The bank-buyer story called for the **DocStore presigned-URL flow** (Story 2.4). That story is **cut** in the demo scope. This story uses the existing **local-filesystem upload pathway** from Story 3-8 (`apps/cockpit-api/src/cockpit_api/services/document_storage.py`) — the same code path the original Documents panel uses. Files land under `${UPLOADS_ROOT}/case_<id>/evidence/`.
- **Ed25519 officer signing is dropped** (no key vault in demo scope). The ledger entry from Story 8-6 records the user_id, not a signature.

**Dependencies:**
- Story 3-8 (local-filesystem upload pathway)
- Story 7-1 (Tiptap editor — receives the inline reference chip)
- Story 8-2 (Zen mode — hosts the dock)
- Story 8-6 (SHA-256 hashing + ledger entry — paired story; 8.5 ships the UI ingest, 8.6 ships the hash + ledger persistence)

## Acceptance Criteria

1. **AC1 — `EvidenceShelf` component.** New `apps/cockpit-ui/src/components/cockpit/EvidenceShelf/EvidenceShelf.tsx`. Renders inside Zen mode's right-edge dock (320px wide, full canvas height). Layout:
   - Header: `Evidence` in `text-h3` + `+ Add` ghost button
   - List body: vertically scrollable list of attached evidence items, newest first
   - Each item: 56px row with file-type icon · name (truncated) · `text-caption` size + relative timestamp · drag handle on the right

2. **AC2 — Three ingest paths.** Clicking `+ Add` opens an ingest popover with three tabs:
   - **Drop a file:** drag-drop zone (reuses `DocumentUploadZone` from Story 3-8) accepting PDFs, images (PNG/JPG), text (.txt, .eml)
   - **Paste from clipboard:** a button reading `Paste image / file from clipboard`. Reads `navigator.clipboard.read()`, normalizes to a Blob, uploads as `pasted-<timestamp>.<ext>`
   - **Paste email body:** a `<textarea>` + `Save as evidence`. Saves the textarea content as `email-<timestamp>.txt` with mime `text/plain`

3. **AC3 — Backend route reuse.** All three paths POST to the existing `POST /v1/cases/{case_id}/documents` endpoint from Story 3-8 with a new query param `?kind=evidence` (default still `?kind=intake`). The endpoint stores files under `${UPLOADS_ROOT}/case_<id>/evidence/` and returns the same `Document` payload used by the existing Documents panel.

4. **AC4 — Drag-into-editor inserts reference chip.** Each evidence item has a drag handle. Dragging an item over the Tiptap editor surface and releasing inserts a Tiptap inline node `evidenceRef` with attrs `{ document_id, filename }`. The chip renders inline as `[evidence: <filename>]` with a click-to-preview affordance (clicking opens the file in a new tab via the existing `/v1/cases/.../documents/.../download` route).

5. **AC5 — Empty state.** When no evidence is attached, the shelf body shows a centered empty state: small icon + caption `Drop files, paste from clipboard, or paste email body to attach evidence to this case.`

6. **AC6 — Item delete.** Each evidence item has a hover-revealed delete (×) icon. Confirms via inline `Delete?` chip → fires `DELETE /v1/cases/{case_id}/documents/{document_id}` (already exists from Story 3-8). The corresponding evidence ledger entry from Story 8-6 is **not** deleted (ledger is append-only).

7. **AC7 — Tests.**
   - `EvidenceShelf.test.tsx::renders_attached_evidence_items_newest_first`
   - `EvidenceShelf.test.tsx::drop_file_uploads_via_documents_endpoint_with_kind_evidence`
   - `EvidenceShelf.test.tsx::paste_clipboard_image_creates_evidence`
   - `EvidenceShelf.test.tsx::paste_email_body_saves_as_text_file`
   - `EvidenceShelf.test.tsx::drag_to_editor_inserts_evidence_ref_node`
   - Backend integration test in `apps/cockpit-api/tests/test_documents_router.py::test_post_document_with_kind_evidence_writes_to_evidence_subdir`

8. **AC8 — `make lint` + `make test` clean.**

## Tasks / Subtasks

- [ ] **Task 1 — Backend: `?kind=evidence` query param** (AC: #3)
  - [ ] Update `apps/cockpit-api/src/cockpit_api/routers/documents.py` to accept the param
  - [ ] Update `document_storage.py` to write to `evidence/` subdir when `kind == 'evidence'`
- [ ] **Task 2 — `EvidenceShelf` component** (AC: #1, #5, #6)
- [ ] **Task 3 — Ingest popover with three tabs** (AC: #2)
- [ ] **Task 4 — Tiptap `evidenceRef` inline node** (AC: #4)
  - [ ] Reuse Tiptap extensions from Story 7-1
- [ ] **Task 5 — Tests** (AC: #7, #8)
- [ ] **Task 6 — Update sprint-status.yaml to `review`**

## Dev Notes

- **`?kind` discriminator is intentional.** The Documents panel keeps `kind=intake` (the default); EvidenceShelf uses `kind=evidence`. This keeps the storage flat under `case_<id>/intake/` and `case_<id>/evidence/` — useful for audit later.
- **Tiptap inline node `evidenceRef`** is structured like the citation chip from Story 8-4 but references a document_id, not a ledger ULID. Two distinct chip types: `citationChip` (ledger ID) + `evidenceRef` (document ID).
- **Email-body paste** is a `text/plain` upload — not an HTML email. The bank-buyer scope hinted at structured email parsing; for the demo, plain text is sufficient.
- **Story 8-6 produces the ledger entry** for each upload here. This story's AC do not assert anything about the ledger — that's tested in 8-6's AC.
- **The 320px shelf width** matches Story 8-2's evidence dock width; keep them aligned.

### File List

**To create**
- `apps/cockpit-ui/src/components/cockpit/EvidenceShelf/EvidenceShelf.tsx`
- `apps/cockpit-ui/src/components/cockpit/EvidenceShelf/EvidenceShelf.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/EvidenceShelf/IngestPopover.tsx`
- `apps/cockpit-ui/src/components/cockpit/EvidenceShelf/EvidenceRefMark.tsx` (Tiptap inline node)

**To modify**
- `apps/cockpit-api/src/cockpit_api/routers/documents.py` (accept `?kind=evidence`)
- `apps/cockpit-api/src/cockpit_api/services/document_storage.py` (write to `evidence/` subdir)
- `apps/cockpit-api/tests/test_documents_router.py`
- `apps/cockpit-ui/src/components/cockpit/ZenMode/ZenMode.tsx` (replace 8-2's placeholder dock with `<EvidenceShelf>`)
- `apps/cockpit-ui/src/components/cockpit/DecisionZone/DecisionZone.tsx` (register `evidenceRef` Tiptap extension)
- `Documentation/implementation-artifacts/sprint-status.yaml`
