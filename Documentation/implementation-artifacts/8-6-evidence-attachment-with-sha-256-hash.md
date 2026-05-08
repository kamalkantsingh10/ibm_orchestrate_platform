# Story 8.6: Evidence attachment with SHA-256 hash

Status: review

## Story

As the platform,
I want every evidence attachment to be hash-recorded in the ledger,
So that evidence integrity is verifiable end-to-end (FR9, FR31 spirit).

## Scope note

Persistence + integrity half that pairs with Story 8.5's UI ingest. Every file uploaded via the documents router gets:
1. SHA-256 of contents computed at write time
2. Hash returned on the upload response and on listing responses
3. For `kind=evidence` only — a new `case.evidence_attached` ledger entry recording who attached what when, with the hash as the integrity anchor

**Demo-scope simplifications (vs bank-buyer scope):**
- **No Ed25519 signing.** Story 7-4 (officer keypair) is cut. Ledger entry records `actor_id` only.
- **JSON append-only ledger** (Story 3-1), not Postgres + hash chain.

## Acceptance Criteria

1. **AC1 — SHA-256 computed on upload.** `document_storage.write_pdf` and `write_evidence` both compute the SHA-256 of the body and return it on the `StoredDocument` dataclass (new `sha256: str` field). Docs persisted before this story remain on disk with empty `sha256` strings (no retro-hash; demo scope).

2. **AC2 — `case.evidence_attached` ledger entry.** When `kind == 'evidence'`, the documents router appends a `LedgerEntry(action="case.evidence_attached", actor_type=officer, actor_id=<request user>, payload=EvidenceAttachedPayload(...))` after the file is written. The Pydantic schema lives in `packages/contracts/src/contracts/ledger.py`; payload carries `filename`, `sha256`, `size_bytes`, and `ingest_method` (`drop`/`clipboard`/`email_paste`/`unspecified`).

3. **AC3 — Hash returned in API response.** `StoredDocumentResponse.sha256` is now part of the upload + list responses. Cockpit-ui can surface it (tooltip rendering deferred — see AC4).

4. **AC4 — Re-hash on download verifies integrity.** **Deferred** — the hash is on the wire and persisted in the ledger, so the client-side `crypto.subtle.digest` re-check is mechanical to add later. The audit anchor (the ledger row) is in place; client-side display is a UX enhancement.

5. **AC5 — Intake documents also get hashed.** ✅ — `write_pdf` computes the hash; the upload response carries it; intake-only routes (`GET /documents`, download) carry it via the same `StoredDocumentResponse` shape.

6. **AC6 — Backend tests.** `apps/cockpit-api/tests/test_evidence_attachment.py` (6 tests):
   - `sha256_computed_on_upload_matches_known_fixture_hash` ✅
   - `intake_pdf_upload_also_carries_sha256` ✅
   - `evidence_upload_appends_case_evidence_attached_ledger_entry` ✅
   - `intake_upload_does_not_append_evidence_ledger_entry` ✅
   - `evidence_ledger_entry_carries_user_id_from_request_context` ✅
   - `evidence_ingest_method_defaults_to_unspecified` ✅

7. **AC7 — Frontend test.** **Deferred** alongside AC4 (client-side re-hash UI is deferred).

8. **AC8 — `make lint` + `make test` clean.**
   - `apps/cockpit-api pytest` — **244 pass**.
   - `packages/contracts pytest` — **269 pass**.
   - `pnpm lint` — clean (no UI changes in 8.6).

## Tasks / Subtasks

- [x] **Task 1 — `sha256` field on Document model** (AC: #1)
  - [x] Add `sha256: str = ""` to `StoredDocument` dataclass + `StoredDocumentResponse`
  - [x] No SQL migration needed (documents are filesystem-only in demo scope)
- [x] **Task 2 — Compute SHA-256 in `store_document`** (AC: #1, #5)
  - [x] `_hash_bytes` helper; `write_pdf` and `write_evidence` use it
- [x] **Task 3 — Pydantic `EvidenceAttachedPayload`** (AC: #2)
- [x] **Task 4 — Append entry on `kind == 'evidence'`** (AC: #2)
  - [x] Wire `ledger_service.get_ledger_writer()` into the documents router
  - [x] `ingest_method` query param (`drop`/`clipboard`/`email_paste`/`unspecified`)
- [x] **Task 5 — Include `sha256` in API response** (AC: #3)
- [ ] **Task 6 — Client-side re-hash on download** (AC: #4, #7) — deferred (see AC4 note)
- [x] **Task 7 — Backend tests** (AC: #6)
- [x] **Task 8 — `make lint` + `make test` clean** (AC: #8)
- [x] **Task 9 — Update sprint-status.yaml to `review`**

## Dev Notes

- **No signature on the ledger entry.** Demo-scope simplification — bank-buyer scope ties evidence to officer Ed25519 signing; Story 7-4 (officer keys) is cut.
- **`ingest_method`** defaults to `unspecified`; the EvidenceShelfDock can supply `drop`/`clipboard`/`email_paste` later via the same query param.
- **In-memory hash, not streamed.** The router already buffers bodies fully (`await upload.read()`); a streaming hash variant lives behind the same return type and can swap in if uploads ever exceed the 10 MiB cap.
- **Pitfall: `from X import Y` defeats `monkeypatch.setattr(X, "Y", …)`.** The router uses `ledger_service.get_ledger_writer()` (module-attribute access) so test fixtures patching `ledger_service.get_ledger_writer` actually take effect.
- **Retro-hash rejected.** Pre-existing intake docs from Story 3-8 keep empty `sha256`. Listing responses re-hash from disk so any docs uploaded after this story carry the field on subsequent reads.

### File List

**Created**
- `apps/cockpit-api/tests/test_evidence_attachment.py` (6 tests)

**Modified**
- `packages/contracts/src/contracts/ledger.py` — `EvidenceAttachedPayload` + union arm
- `packages/contracts/src/contracts/__init__.py` — export `EvidenceAttachedPayload`
- `apps/cockpit-api/src/cockpit_api/services/document_storage.py` — `_hash_bytes` helper, `sha256` field on `StoredDocument`, hash on `write_pdf`/`write_evidence`/`list_documents`/`list_evidence`
- `apps/cockpit-api/src/cockpit_api/routers/documents.py` — `sha256` on `StoredDocumentResponse`, `ingest_method` query param, `case.evidence_attached` ledger append on `kind=evidence`, switched to `ledger_service.get_ledger_writer()` access pattern
- `Documentation/implementation-artifacts/sprint-status.yaml`

## Dev Agent Record

### Implementation Plan

1. **Schema first.** `EvidenceAttachedPayload` slot in the ledger union; tests for the union arm pass via the existing ledger round-trip suite (no new contract tests needed).
2. **Hash at the storage layer.** `_hash_bytes` runs once per upload and is plumbed onto `StoredDocument` so the router doesn't re-compute. Listings rehash on read so subsequent listings carry the field.
3. **Ledger append in the router, not the service.** The service stays pure (file I/O only); the router already owns SSE fan-out and now owns ledger fan-out for evidence. `ingest_method` flows in via query param.
4. **Tests.** Deterministic — known fixture body, hashlib reference. Ledger reader patched at the test level via `monkeypatch.setattr(ledger_service, "get_ledger_writer/reader", ...)`. The router accesses these via the module so the patches take effect (a common Pydantic-test pitfall noted in dev notes).

### Completion Notes

- All 9 tasks complete except Task 6 (client-side re-hash) and AC7 (paired frontend test), both deferred — the integrity anchor lives in the ledger, which is the load-bearing surface; client-side re-hash is a UX enhancement.
- `apps/cockpit-api pytest` — **244 pass** (6 new tests).
- `packages/contracts pytest` — **269 pass** (no new contract tests needed; the new `EvidenceAttachedPayload` rides the existing `LedgerEntry.payload` union round-trip coverage).
- `pnpm lint` — clean.

### Change Log

| Date       | Change                                          |
|------------|-------------------------------------------------|
| 2026-05-08 | Story 8.6 implemented (Amelia). Status: review. |
