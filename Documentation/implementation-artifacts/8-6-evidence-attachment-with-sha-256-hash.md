# Story 8.6: Evidence attachment with SHA-256 hash

Status: backlog

## Story

As the platform,
I want every evidence attachment to be hash-recorded in the ledger,
So that evidence integrity is verifiable end-to-end (FR9, FR31 spirit).

## Scope note

This story is the **persistence + integrity** half that pairs with Story 8-5's UI ingest. Every file uploaded via EvidenceShelf gets:
1. A SHA-256 hash computed by the API on first read
2. The hash stored on the existing `Document` row alongside the file path
3. A new ledger entry of type `case.evidence_attached` recording who attached what when, with the hash as evidence

**Demo-scope simplifications (vs bank-buyer scope):**

- **No Ed25519 signing.** The bank-buyer story said "ledger entry signed by my key (Story 7.4)". Story 7-4 (officer Ed25519 keypair generation) is **cut** in the demo scope. The ledger entry records `user_id` only — no cryptographic signature. The audit trail is honest about being a JSON append-only log without crypto, per the architecture's Demo Scope Addendum.
- **JSON append-only ledger** (Story 3-1), not Postgres + hash chain.

**Dependencies:**
- Story 3-1 (JSON ledger writer)
- Story 3-3 (Pydantic ledger contracts)
- Story 8-5 (UI ingest fires uploads with `?kind=evidence`)

## Acceptance Criteria

1. **AC1 — SHA-256 computed on upload.** `apps/cockpit-api/src/cockpit_api/services/document_storage.py.store_document(case_id, file, kind)` is extended to compute the SHA-256 of the file contents (streaming-friendly via `hashlib.sha256().update()` chunks) before returning. The hash is stored on the `Document` model as a new field `sha256: str` (64-char hex). Migration: add the field as nullable for backward compatibility with documents uploaded before this story; null only allowed for pre-existing rows.

2. **AC2 — `case.evidence_attached` ledger entry.** When `kind == 'evidence'`, after the file is stored and hashed, a new ledger entry is appended via the Story 3-1 writer with:
   - `entry_type: "case.evidence_attached"`
   - `case_id: <case_id>`
   - `actor_type: "officer"`
   - `actor_id: <user_id from request context>`
   - `payload: { document_id, filename, sha256, kind: "evidence", ingest_method: "drop"|"clipboard"|"email_paste" }`
   - `timestamp: <UTC now>`
   - The Pydantic schema for this entry lives in `packages/contracts/src/contracts/ledger.py`

3. **AC3 — Hash returned in API response.** The `POST /v1/cases/{case_id}/documents` response now includes `sha256` in the returned `Document` payload. The cockpit-ui consumes this in EvidenceShelf for tooltip display (`Hash: a1b2c3...`).

4. **AC4 — Re-hash on download verifies integrity.** The cockpit-ui's evidence-preview affordance (click an evidence item to download) is extended:
   - Fetch the file via `GET /v1/cases/.../documents/.../download`
   - Compute SHA-256 client-side via `crypto.subtle.digest`
   - Compare to the stored `document.sha256`
   - On match: open in new tab as before
   - On mismatch: show a `signal-rose` toast `Evidence integrity check failed for <filename>` and refuse to open the file

5. **AC5 — Intake documents also get hashed.** Although the ledger entry is only emitted for `kind == 'evidence'`, the SHA-256 computation runs for **all** uploads (intake + evidence). This means existing Documents-panel uploads from Story 3-8 also get hashed going forward; the `sha256` field is present on intake documents too. (No retro-hashing of pre-existing docs — null is acceptable for those.)

6. **AC6 — Backend tests.** `apps/cockpit-api/tests/test_evidence_attachment.py`:
   - `sha256_computed_on_upload_matches_known_fixture_hash`
   - `evidence_upload_appends_case_evidence_attached_ledger_entry`
   - `intake_upload_does_not_append_evidence_ledger_entry` (ensures the entry is gated on `kind`)
   - `evidence_ledger_entry_carries_user_id_from_request_context`

7. **AC7 — Frontend test.** `EvidenceShelf.test.tsx::download_recomputes_hash_and_warns_on_mismatch` — uses a stub Web Crypto API to fake a mismatch and asserts the toast renders + the download is blocked.

8. **AC8 — `make lint` + `make test` clean.**

## Tasks / Subtasks

- [ ] **Task 1 — `sha256` field on Document model + migration** (AC: #1)
  - [ ] Add nullable `sha256: str | None` to the document schema in `packages/contracts/`
  - [ ] If using SQLite (per demo scope) — add column with default null
- [ ] **Task 2 — Compute SHA-256 in `store_document`** (AC: #1, #5)
  - [ ] Streaming hash to handle large PDFs without loading entire file in memory
- [ ] **Task 3 — Pydantic `EvidenceAttachedEntry`** (AC: #2)
  - [ ] Add to `packages/contracts/src/contracts/ledger.py`
- [ ] **Task 4 — Append entry on `kind == 'evidence'`** (AC: #2)
  - [ ] Wire the ledger writer into the documents router for the evidence path
- [ ] **Task 5 — Include `sha256` in API response** (AC: #3)
- [ ] **Task 6 — Client-side re-hash on download** (AC: #4, #7)
- [ ] **Task 7 — Backend tests** (AC: #6)
- [ ] **Task 8 — `make lint` + `make test` clean** (AC: #8)
- [ ] **Task 9 — Update sprint-status.yaml to `review`**

## Dev Notes

- **No signature on the ledger entry.** This is the explicit demo-scope simplification. The bank-buyer scope ties evidence to officer cryptographic signing for unimpeachable provenance; the demo is honest about being a JSON log without crypto. If this scope is revived for the bank-buyer scenario, Story 7-4 (officer keys) lights up first, then this story's ledger writer adds a `signature` field.
- **`ingest_method` discriminator** in the payload (AC2) is for audit forensics — knowing whether evidence came from drop, clipboard, or email-body paste informs how much trust to give it. Cheap to record, useful later.
- **Streaming hash** is non-negotiable for large PDFs. Reading entire files into memory just to hash them will OOM the demo container. `hashlib.sha256()` accepts incremental `update()` calls.
- **Why retro-hash is rejected (AC5).** Pre-existing intake docs from Story 3-8 don't have hashes; back-filling them isn't load-bearing for the demo. A note in the story file is enough; nullable is the contract.
- **Web Crypto API for client re-hash (AC4)** is supported in all modern browsers. No polyfill needed.

### File List

**To create**
- `apps/cockpit-api/tests/test_evidence_attachment.py`

**To modify**
- `packages/contracts/src/contracts/documents.py` (add `sha256: str | None`)
- `packages/contracts/src/contracts/ledger.py` (add `EvidenceAttachedEntry`)
- `packages/contracts/tests/test_ledger.py`
- `apps/cockpit-api/src/cockpit_api/services/document_storage.py` (compute hash in `store_document`)
- `apps/cockpit-api/src/cockpit_api/routers/documents.py` (append ledger entry on `kind == 'evidence'`; include sha256 in response)
- `apps/cockpit-ui/src/components/cockpit/EvidenceShelf/EvidenceShelf.tsx` (re-hash on download)
- `apps/cockpit-ui/src/api-types.ts` (re-generated from contracts)
- `Documentation/implementation-artifacts/sprint-status.yaml`
