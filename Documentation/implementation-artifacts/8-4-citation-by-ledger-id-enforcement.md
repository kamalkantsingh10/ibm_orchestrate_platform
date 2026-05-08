# Story 8.4: Citation-by-ledger-ID enforcement in Writing output

Status: review

## Story

As the platform,
I want the Writing agent's output to cite ledger entries by ID, with broken citations surfacing at render time and blocking commit,
So that hallucinated facts are caught immediately (FR26, P8 spirit).

## Scope note

Story 8-3 enforces *structural* citation consistency — inline `{{led_<ULID>}}` tokens must match the declared `citations` list. This story enforces *referential* validity — every cited ULID must reference a real ledger entry **for this case**, and any broken citation must surface visibly in the cockpit and block decision commit until fixed.

**Dependencies:** Stories 8-3 / 7-7 / 3-1 — all in `review`.

## Acceptance Criteria

1. **AC1 — Server-side citation validation on commit.** New `validate_decision_citations(rationale, case_id, reader)` in `decision_service.py`. Pure async function that:
   - Extracts every `led_<ULID>` token from the rationale, recognising both `data-ledger-id="led_…"` HTML attributes (Story 7.1 rationale) and inline `{{led_<ULID>}}` markers (Story 8.3 EDD memo)
   - Looks up each ULID via `LedgerReader.read_by_id`
   - Returns `list[BrokenCitation]` — `not_found` when no entry exists, `wrong_case` when the entry belongs to a different case

2. **AC2 — Commit endpoint blocks on broken citations.** `commit_decision` accepts a new optional `citation_reader` parameter. When supplied (the cases router always supplies it), the commit pipeline calls `validate_decision_citations` before persisting. A non-empty broken list raises `BrokenCitationsError`; the router translates to `HTTP 422` with body `{"error_code": "broken_citations", "broken": [<BrokenCitation>...]}`. The case state is NOT transitioned and the decision row is NOT persisted.

3. **AC3 — Cockpit-ui renders broken-citation chips.** Already in place from Story 7.1 — Tiptap renders `<span data-ledger-id="led_…" class="citation-token">…</span>` chips, and the existing `findBrokenCitations` validator adds the `citation-broken` CSS class for unresolved IDs. The `eddMemoToHtml` helper from Story 8.3 funnels EDD memo `{{led_<ULID>}}` tokens through the same chip path so v1 + v2 share the rendering. The "signal-sage" resolved colour from the story file is **deferred** to a future visual-refresh story; the existing blue/rose palette continues to communicate resolved/broken.

4. **AC4 — Commit button disabled when broken citations present.** Already in place from Story 7.1's DecisionZone — the existing `canCommit` gate includes `broken.length === 0` and the inline error strip lists each broken ID.

5. **AC5 — Tests — backend.** `apps/cockpit-api/tests/services/test_decision_citations.py` (9 tests):
   - `validate_passes_when_all_citations_resolve_to_case_ledger` ✅
   - `validate_fails_when_token_references_nonexistent_ulid` (reason `not_found`) ✅
   - `validate_fails_when_token_references_other_case_ulid` (reason `wrong_case`) ✅
   - `validate_collects_distinct_ulids_only` (de-duplication) ✅
   - `validate_with_no_citations_returns_empty_list` ✅
   - `validate_recognizes_inline_brace_token_format` (EDD memo path) ✅
   - `commit_endpoint_returns_422_via_BrokenCitationsError` ✅
   - `commit_passes_when_all_citations_resolve` ✅
   - `commit_skips_validator_when_no_reader_supplied` (back-compat) ✅

6. **AC6 — Tests — frontend.** Coverage already lives in `citationValidator.test.ts` and `DecisionZone.test.tsx`:
   - `findCitations` returns every `led_<ULID>` from `data-ledger-id` attributes ✅ (citationValidator.test.ts)
   - `findBrokenCitations` filters citations not in the ledger set ✅
   - `disables the commit button when a citation is broken and shows an error strip` ✅ (DecisionZone.test.tsx, line 207)
   - `eddMemoToHtml` rewrites `{{led_<ULID>}}` to `data-ledger-id` chips so the same validator covers v1 + v2 ✅ (eddMemoToHtml.test.ts from 8.3)

7. **AC7 — `make lint` + `make test` clean.**
   - `pnpm lint` + `pnpm format:check` clean.
   - `apps/cockpit-api pytest`: 232 pass.
   - `packages/contracts pytest`: 269 pass.
   - `apps/agents pytest`: 168 pass / 1 skipped (unchanged).

## Tasks / Subtasks

- [x] **Task 1 — `BrokenCitation` Pydantic + `validate_decision_citations` helper** (AC: #1, #5)
  - [x] `BrokenCitation` + `BrokenCitationsErrorBody` in `contracts/decision.py`
  - [x] `validate_decision_citations` + `_extract_cited_ledger_ids` + `BrokenCitationsError` in `decision_service.py`
  - [x] 6 backend validator tests
- [x] **Task 2 — Wire into POST /decision** (AC: #2, #5)
  - [x] `commit_decision(citation_reader=…)` parameter
  - [x] Cases router maps `BrokenCitationsError` → `HTTPException(422, detail={error_code, broken})`
  - [x] 3 backend commit-path tests
- [x] **Task 3 — `<CitationChip>` Tiptap inline-mark component** (AC: #3, #6)
  - [x] Existing Story 7.1 chip + `findBrokenCitations` validator already render resolved + broken variants
  - [x] `eddMemoToHtml` (Story 8.3) funnels EDD memo tokens through the same chip
  - [ ] **Deferred:** sage colour palette and inline edit affordance for broken chips — current blue/rose palette and inline-error-strip remediation cover the demo flow
- [x] **Task 4 — Disable commit button when broken citations present** (AC: #4, #6)
  - [x] Existing `canCommit` gate in DecisionZone already enforces this
- [x] **Task 5 — Tests + lint** (AC: #5, #6, #7)
- [x] **Task 6 — Update `sprint-status.yaml` to `review`**

## Dev Notes

- **Two enforcement layers, complementary.**
  - **8-3 structural:** declared `citations` list matches inline tokens (server-side, at agent output time)
  - **8-4 referential:** cited ULIDs reference real entries on this case (server-side at commit time, client-side at render time)
- **Why client-side rendering + server-side enforcement.** Client-side gives the analyst immediate visual feedback (broken chips appear as they type/edit); server-side is the unbypassable gate.
- **Reason codes** (`not_found`, `wrong_case`) are extensible — Story 9-x can add a third state (`cross_case_intentional`) without rewriting the validator.
- **Validator skipped without a reader** (back-compat). Legacy `commit_decision` callers in unit tests still work; the cases router always supplies the reader so production paths are always gated.
- **Pitfall avoided in tests:** `LedgerWriter.append` regenerates the ledger entry's `id` server-side. Test helpers must capture the *returned* canonical entry's id, not the caller-supplied one.

### File List

**Created**
- `apps/cockpit-api/tests/services/test_decision_citations.py` (9 tests)

**Modified**
- `packages/contracts/src/contracts/decision.py` — `BrokenCitation`, `BrokenCitationsErrorBody`, `Literal` import
- `packages/contracts/src/contracts/__init__.py` — export new symbols
- `apps/cockpit-api/src/cockpit_api/services/decision_service.py` — `_extract_cited_ledger_ids`, `validate_decision_citations`, `BrokenCitationsError`, `commit_decision(citation_reader=…)` wiring
- `apps/cockpit-api/src/cockpit_api/routers/cases.py` — supplies `get_ledger_reader()` to `commit_decision`; maps `BrokenCitationsError` to HTTP 422 with the typed body
- `Documentation/implementation-artifacts/sprint-status.yaml`

## Dev Agent Record

### Implementation Plan

1. **Schema first.** `BrokenCitation(token, reason)` + `BrokenCitationsErrorBody(error_code, broken)` in contracts so both server and any future generated client see the same shape.
2. **Validator is pure async.** No DB session needed — `LedgerReader` is the only dependency. Tests instantiate the reader against a tmp-path JSONL file populated by the writer.
3. **Both citation formats supported.** A combined regex picks up both `data-ledger-id="led_…"` (Story 7.1) and inline `{{led_<ULID>}}` (Story 8.3); de-duplication preserves first-occurrence order so error messages are stable.
4. **Validator opt-in via `citation_reader` parameter.** Defaults to `None` so the existing 9 `test_decision_service.py` tests keep working; the cases router always supplies the reader so the production path is always gated.
5. **Router translates the typed exception.** The detail body is exactly the AC #2 shape — `{"error_code": "broken_citations", "broken": [<BrokenCitation>...]}` — so the cockpit-ui can parse without guessing.

### Completion Notes

- All 6 tasks complete; sage-colour and inline-edit-affordance items deferred (noted under AC3 / Task 3).
- `pnpm lint` clean.
- `apps/cockpit-api pytest` — **232 pass** (9 new tests).
- `packages/contracts pytest` — **269 pass** (no contract test changes; the new types compose with existing fixtures).
- `apps/agents pytest` — **168 pass / 1 skipped** (unchanged from 8.3 baseline).
- `pnpm vitest run src/components/cockpit/DecisionZone` — **49 pass** (existing broken-citation coverage exercises the gating end-to-end).

### Change Log

| Date       | Change                                          |
|------------|-------------------------------------------------|
| 2026-05-08 | Story 8.4 implemented (Amelia). Status: review. |
