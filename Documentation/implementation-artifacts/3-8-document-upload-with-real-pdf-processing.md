# Story 3.8: Document upload with real PDF processing

Status: review

## Story

As a KYC Analyst opening a case,
I want to upload supporting PDF documents directly to the case from the cockpit UI, then trigger Document Intelligence extraction so the watsonx LLM reads the actual PDF text and produces typed extracted fields,
So that the demo can show the **end-to-end ADK loop** — *upload → real LLM extraction → typed fields with provenance + confidence in the cockpit* — rather than pre-baked fixture data, satisfying NFR-RI1 (ADK pattern showcase) at the most visible layer of the demo (FR3, FR14, FR16).

## Scope note (added 2026-05-01 post Story 3.7)

This story closes the "fake documents" loop. Stories 3.4 / 3.5 / 3.6 / 3.7 ship a fully working chat-driven experience using **fixture mode** (synthetic extractions keyed by filename, no actual PDFs read). That works for offline CI and for a rehearsable demo, but it stops short of the moment that sells the platform: *"watch the LLM read this real PDF and extract the fields I care about."*

This story adds the upload boundary and flips the demo to watsonx mode by default when the user uploads. **Both modes coexist**: fixture mode remains the offline / CI default; uploads use watsonx.

| Bank-buyer scope | Demo replacement in this story |
|---|---|
| Presigned-PUT upload to IBM COS / S3 / MinIO via `DocStore` adapter | **Local filesystem** at `./fixtures/uploads/<case_id>/<filename>` (no object store; matches the demo's local-first stance) |
| Multi-tenant scoped storage with KMS encryption | Single-tenant; no encryption beyond filesystem perms |
| Anti-virus + MIME validation pipeline | **Basic checks only**: PDF magic bytes, file size cap (10 MB), filename sanitization. No AV scan. |
| Resumable / chunked uploads | Single-shot multipart/form-data |

What survives: **the upload boundary, the real watsonx LLM extraction path, the case-metadata sync, and the `Process this case` chat-driven flow now reading PDFs the user just uploaded.**

## Acceptance Criteria

1. **AC1 — `POST /v1/cases/{case_id}/documents` multipart upload endpoint.** New router method on `apps/cockpit-api/src/cockpit_api/routers/cases.py` (or a dedicated `documents.py` if the dev prefers). Accepts `multipart/form-data` with one or more `UploadFile` parts under field name `files`. For each file:
    - Validate the case exists; 404 if not.
    - Validate the filename: max 100 chars, no path separators (`/` or `\`), only `[a-zA-Z0-9._-]+\.pdf$`. Reject with 400 otherwise.
    - Read up to 10 MB; reject with 413 if larger (use `file.size` if available; else stream-read with a counter).
    - Verify magic bytes (`%PDF-`); reject with 415 otherwise.
    - Persist to `./fixtures/uploads/<case_id>/<sanitized_filename>` (overwrite if exists).
    - Update the case's `customer_metadata.extra.document_refs` to include the new filename (deduplicated, preserves order). Use `CaseRepo.add_document_ref` (new helper, see AC2).
    Returns 200 with body:
    ```json
    {"case_id": "...", "uploaded": ["incorporation_certificate.pdf", ...], "document_refs": ["..."]}
    ```

2. **AC2 — `CaseRepo.add_document_ref(session, case_id, filename) -> Case`** helper. Mirrors the `add_block_marker` pattern from Story 3.5. Reads the case row, merges the filename into `customer_metadata.extra.document_refs` (creating the list if missing), commits, returns the updated case.

3. **AC3 — `GET /v1/cases/{case_id}/documents` list endpoint.** Returns the case's current `document_refs` plus per-file metadata (size, mtime). Used by the upload UI to render existing files.

4. **AC4 — `DELETE /v1/cases/{case_id}/documents/{filename}` endpoint.** Removes the file from disk AND from `customer_metadata.extra.document_refs`. Returns 204 on success, 404 if file or case missing.

5. **AC5 — Upload UI component.** `apps/cockpit-ui/src/components/cockpit/DocumentUploadZone/DocumentUploadZone.tsx`:
    - Drag-and-drop zone (HTML5 native — no `react-dropzone` dep) + a file-picker fallback button.
    - Accepts only `.pdf` files (client-side filter via `accept="application/pdf"`).
    - Shows progress per file during upload (use `XMLHttpRequest.upload.onprogress` since `fetch` doesn't support upload progress without streams API).
    - On success, invalidates the case's TanStack Query cache (`['cases', caseId]`) so the documents list refreshes.
    - On error, shows an inline alert with the API's RFC 7807 `detail`.
    - Empty state: "Drag a PDF here or click to browse"; populated state: filename list + delete buttons.

6. **AC6 — "Process this case" chat command works against uploaded docs.** End-to-end:
    - User uploads `incorporation_certificate.pdf` to case X.
    - Sets `DOC_AI_PROVIDER=watsonx` in `.env` and re-runs `make adk-up`.
    - In ADK chat: "Process case X."
    - The supervisor agent invokes `extract_document_fields` (Story 3.4's tool).
    - The Document Intelligence agent reads the PDF via `pypdf.PdfReader`, renders the Jinja prompt with the extracted text, calls watsonx LLM, parses the JSON response, returns typed `ExtractedField` records.
    - Each field's `Provenance.source_system == "watsonx_<model_id>"` (vs `"fixture_doc_ai"`).
    - cockpit UI Documents panel renders the fields with the same `ProvenanceIndicator` + `ConfidencePill` (Stories 3.6 / 3.7).

7. **AC7 — Fixture mode still works for unknown uploaded filenames.** If `DOC_AI_PROVIDER=fixture` AND the user uploads a filename not in `_FIXTURE_EXTRACTIONS` (e.g., `my_company_pan.pdf`), the agent's existing "unknown filename" fallback returns one `raw_text` field with low confidence. **No regression** to the offline demo path.

8. **AC8 — Sample PDFs.** Ship 3-5 short, plausible sample PDFs at `./fixtures/sample_pdfs/` (gitignored or LFS-tracked — dev's call). A `make seed-uploads` target copies them into `./fixtures/uploads/<case_id>/` to bootstrap the watsonx-mode demo without manual upload. Decision point: generate via `reportlab` from a Python script (preferred — no binary commits) OR commit small PDFs (~50 KB each).

9. **AC9 — Case canvas integration.** Story 3.6's `cases.$caseId.tsx` route gains an "Upload documents" zone (renders `<DocumentUploadZone />` above the Documents panel). After successful upload, a "Process now" button appears that POSTs to `/v1/cases/{id}/intake` (Story 3.5's endpoint). On success, the Documents panel re-renders.

10. **AC10 — Tests.**
    - Backend: `test_documents_upload_route.py` — 6+ tests covering happy path, oversized file, non-PDF, path-traversal filename, multi-file upload, list+delete round-trip.
    - UI: `DocumentUploadZone.test.tsx` — 5+ tests covering drag-enter focus, file-picker click, progress events, error rendering, delete confirmation.
    - End-to-end: a manual demo verification (no automated browser test) that uploads a PDF, runs intake in watsonx mode, observes the field appear in the Documents panel.

11. **AC11 — Storage hygiene.**
    - `make demo-reset` wipes `./fixtures/uploads/` (already does — AC verified).
    - `.gitignore` already excludes `fixtures/uploads/` (verify; add line if missing).
    - Files older than 24 hours could be auto-pruned by a future cron — out of scope here; document as future work.

12. **AC12 — `make lint` + `make test` clean.** New test count: ≥6 backend, ≥5 UI. No regressions.

## Tasks / Subtasks

- [x] **Task 1 — Backend upload endpoint** (AC: #1, #2, #10)
  - [x] Create `apps/cockpit-api/src/cockpit_api/services/document_storage.py` — pure helper for filename sanitization, magic-byte validation, file write. Keeps `routers/` thin.
  - [x] Add `CaseRepo.add_document_ref` (mirrors `add_block_marker`).
  - [x] Add the POST endpoint to `routers/cases.py` (or new `routers/documents.py`).
  - [x] Author `test_documents_upload_route.py`.

- [x] **Task 2 — Backend list + delete** (AC: #3, #4, #10)
  - [x] GET `/v1/cases/{id}/documents` returns `[{filename, size_bytes, uploaded_at}]`.
  - [x] DELETE `/v1/cases/{id}/documents/{filename}` removes file + metadata entry.
  - [x] Tests for both paths.

- [x] **Task 3 — Sample PDFs + `make seed-uploads`** (AC: #8)
  - [x] Create `tools/scripts/generate_sample_pdfs.py` using `reportlab` (add as dev dep on cockpit-api). Generates 5 plausible KYC-shaped PDFs to `./fixtures/sample_pdfs/`.
  - [x] Add `make seed-uploads` target that runs the generator, then copies into `./fixtures/uploads/<case_id>/` for each demo case.

- [x] **Task 4 — Upload UI component** (AC: #5, #10)
  - [x] Create `DocumentUploadZone.tsx` + `index.ts` + `DocumentUploadZone.test.tsx`.
  - [x] Use `XMLHttpRequest` for progress; fall back to `fetch` if not needed.
  - [x] Empty / progress / populated / error states.

- [x] **Task 5 — Integrate into case canvas** (AC: #9)
  - [x] Edit `apps/cockpit-ui/src/routes/cases.$caseId.tsx` (Story 3.6's route).
  - [x] Place upload zone above the Documents panel.
  - [x] Wire "Process now" button to `POST /v1/cases/{id}/intake` (Story 3.5's endpoint).
  - [x] After intake succeeds, invalidate the `useDocumentIntelligence` query.

- [x] **Task 6 — End-to-end demo verification** (AC: #6, #7, #11, #12)
  - [x] `make demo-reset && make seed && make adk-up && make adk-register && make dev`.
  - [x] Set `DOC_AI_PROVIDER=watsonx` + `WATSONX_APIKEY=...` in `.env`.
  - [x] Open chat UI, upload a PDF via the cockpit UI, run "Process case X" in chat.
  - [x] Verify field extraction works against the actual PDF text.
  - [x] Switch back to `DOC_AI_PROVIDER=fixture`; verify the offline demo path still works (uploaded files hit the unknown-filename fallback).
  - [x] `make lint` + `make test` clean.

## Dev Notes

### Sequencing

This story comes AFTER Stories 3.5 (case supervisor backend), 3.6 (case canvas + Documents panel), and 3.7 (ConfidencePill). The case canvas is where the upload zone lives; the Documents panel is what re-renders after upload+process; the supervisor's `POST /v1/cases/{id}/intake` is what the "Process now" button calls.

### Architectural context

[Source: `architecture.md#Demo Scope Addendum (2026-04-29)` § Stack changes for demo, row "Document storage"] — Local filesystem at `./fixtures/uploads/` is the demo's choice; bank-buyer scope's IBM COS / S3 / MinIO adapter is deferred.

[Source: `3-4-document-intelligence-agent-llm-extract.md`] — `WatsonxDocAILLM` already reads from `./fixtures/uploads/<filename>.pdf`. This story changes the path to `./fixtures/uploads/<case_id>/<filename>.pdf` (case-scoped subdir) — a small refactor to the agent's `_read_pdf_text` helper.

### Critical pitfalls to avoid

1. **Never trust user-supplied filenames as paths.** `os.path.join(upload_dir, user_filename)` is exploitable via `../../../etc/passwd`. Sanitize via regex; reject anything that doesn't match the safe-name pattern.

2. **Don't store uploaded PDFs in the cockpit-api Docker image.** They're per-case mutable state; persist to a host-mounted volume (`./fixtures/uploads/`).

3. **Multipart `UploadFile.size` is None until the body is read.** FastAPI streams the upload; you have to count bytes as you write. Cap at 10 MB.

4. **`pypdf.PdfReader` keeps the file handle open.** Use `with` context manager; don't `pdf = PdfReader(open(path))` without close.

5. **Re-uploading the same filename overwrites.** Document this in the API description so users aren't surprised.

6. **The case-detail route isn't analyst-only after this story** — Team Lead might also upload? Check Story 3.6's role gating; default to "Analyst only" for the upload zone (UX call).

### Project Structure Notes

This story creates:

- `apps/cockpit-api/src/cockpit_api/services/document_storage.py`
- `apps/cockpit-api/src/cockpit_api/routers/documents.py` (or extends `cases.py`)
- `apps/cockpit-api/tests/test_documents_upload_route.py`
- `tools/scripts/generate_sample_pdfs.py`
- `apps/cockpit-ui/src/components/cockpit/DocumentUploadZone/DocumentUploadZone.tsx`
- `apps/cockpit-ui/src/components/cockpit/DocumentUploadZone/DocumentUploadZone.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/DocumentUploadZone/index.ts`

This story modifies:

- `apps/cockpit-api/src/cockpit_api/repositories/case_repo.py` — `add_document_ref`
- `apps/cockpit-api/src/cockpit_api/main.py` — wire new router (if separate file)
- `apps/cockpit-api/pyproject.toml` — add `reportlab` (dev dep) for sample-PDF generator
- `apps/agents/src/agents/intake/document_intelligence.py` — adjust `_read_pdf_text` to use case-scoped subdir
- `apps/cockpit-ui/src/routes/cases.$caseId.tsx` — add upload zone + Process Now button
- `apps/cockpit-ui/src/api-types.ts` — regenerated
- `Makefile` — `seed-uploads` target

This story DOES NOT create:

- A presigned-PUT endpoint (cut from demo; local FS instead)
- Multi-tenant storage scoping (single-tenant)
- AV scanning (out of scope)
- Resumable / chunked uploads (single-shot)
- A document-preview pane in the UI (future)

### References

- [Source: `architecture.md#Demo Scope Addendum (2026-04-29)`] — local-FS for document storage
- [Source: `3-4-document-intelligence-agent-llm-extract.md`] — `WatsonxDocAILLM`, fixture mode
- [Source: `3-5-case-supervisor-intake-fan-out.md`] — `POST /v1/cases/{id}/intake`
- [Source: `3-6-documents-panel-on-case-canvas-with-provenance-pills.md`] — case canvas route
- [Source: `prd.md#FR3, FR14, FR16, NFR-RI1`] — instant canvas, intake automation, doc storage, ADK showcase

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (Amelia persona, bmad-dev-story workflow)

### Debug Log References

* Live upload smoke against the demo's `case_01KQC7GQ70GYHP15CZ8JB5ZT6A`:
    ```
    $ curl -F files=@incorporation_certificate.pdf .../documents
    {
      "case_id": "case_01KQC7GQ70GYHP15CZ8JB5ZT6A",
      "uploaded": [{"filename": "incorporation_certificate.pdf", "size_bytes": 2155, "uploaded_at": "..."}],
      "document_refs": ["incorporation_certificate.pdf", "ubo_declaration.pdf", "shareholder_pattern.pdf", "director_id.pdf", "bank_statement_q1.pdf"]
    }
    ```
* `make seed-uploads` copies 13 PDFs into per-case subdirs (5 for Vora, 4 each for Shree + Ananya). Sample PDFs generated via `reportlab` in 9 known filenames matching the demo's pinned fixture refs.
* JSDOM's `fireEvent.drop` doesn't auto-flush React state; switched the upload-error test from `await Promise.resolve()` to `screen.findByRole('alert')` which polls.

### Completion Notes List

* **Storage layout**: `./fixtures/uploads/<case_id>/<filename>.pdf` (case-scoped subdirs). Story 3.4's agent `_read_pdf_text` was refactored to honor this path AND fall back to the legacy flat path so pre-3.8 setups don't break.
* **Filename safety**: regex `^[A-Za-z0-9._-]+\.pdf$`, max 100 chars, explicit reject on `..`/`/`/`\`. Path-traversal rejection tested (returns 400).
* **Magic-byte check**: first 5 bytes must be `%PDF-`. Rejects PNG-as-PDF etc. with 415.
* **Size cap**: 10 MiB. Rejected with 413 (FastAPI's deprecated `HTTP_413_REQUEST_ENTITY_TOO_LARGE` constant — switching to `HTTP_413_CONTENT_TOO_LARGE` is a low-priority follow-up, surfaces a single warning during tests).
* **`add_document_ref` is idempotent**: re-adding the same filename is a no-op (preserves order). `remove_document_ref` filters by exact match.
* **`DocumentUploadZone` uses `XMLHttpRequest`** for upload progress (fetch's streams API doesn't support upload progress reliably across browsers). Calls `onUploadComplete` on each successful 2xx so the parent can invalidate query caches.
* **"Process now" button** in the case-canvas calls `POST /v1/cases/{id}/intake` (Story 3.5), invalidates the document-intelligence query, and the DocumentsPanel re-renders with fresh extractions. On a case in `decision_ready`, the supervisor returns 409; the UI surfaces this inline.
* **Sample PDFs are gitignored** at `fixtures/sample_pdfs/` and `fixtures/uploads/`. Generate via `make sample-pdfs` (one-shot) or bootstrap per-case via `make seed-uploads` (which is what the demo presenter runs).
* **Watsonx-mode demo path**: `make seed-uploads` + set `DOC_AI_PROVIDER=watsonx` + `WATSONX_APIKEY` in `.env` → re-run `make seed` → cases get watsonx-extracted fields (instead of fixture's pre-baked values). Fixture mode remains the offline default for CI.

### File List

**Created (backend)**
* `apps/cockpit-api/src/cockpit_api/services/document_storage.py` — pure helpers (sanitize, magic check, write, list, delete)
* `apps/cockpit-api/src/cockpit_api/routers/documents.py` — POST/GET/DELETE
* `apps/cockpit-api/tests/test_documents_router.py` — 8 tests

**Created (UI)**
* `apps/cockpit-ui/src/components/cockpit/DocumentUploadZone/DocumentUploadZone.tsx`
* `apps/cockpit-ui/src/components/cockpit/DocumentUploadZone/DocumentUploadZone.test.tsx` — 6 tests
* `apps/cockpit-ui/src/components/cockpit/DocumentUploadZone/index.ts`

**Created (tooling)**
* `tools/scripts/generate_sample_pdfs.py` — `reportlab`-based 9-PDF generator

**Modified**
* `apps/cockpit-api/src/cockpit_api/repositories/case_repo.py` — `add_document_ref` + `remove_document_ref` helpers
* `apps/cockpit-api/src/cockpit_api/main.py` — wire documents router
* `apps/cockpit-api/pyproject.toml` — add `reportlab` dev dep
* `apps/cockpit-api/poetry.lock` — locked
* `apps/agents/src/agents/intake/document_intelligence.py` — `_read_pdf_text` honors per-case subdir + legacy fallback
* `apps/cockpit-ui/src/routes/cases.$caseId.tsx` — DocumentUploadZone above panel grid + "Process now" button
* `apps/cockpit-ui/src/api-types.ts` — regenerated
* `Makefile` — `sample-pdfs` and `seed-uploads` targets
* `.gitignore` — `fixtures/uploads/` and `fixtures/sample_pdfs/`
* `Documentation/implementation-artifacts/sprint-status.yaml` — story marked `review`

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-05-01 | Story 3.8 drafted post-Story-3.7. Closes the "fake documents" loop with a real upload boundary + watsonx-mode end-to-end demo. Sequenced AFTER 3.5/3.6/3.7. Fixture mode preserved for offline CI. |
