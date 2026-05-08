# Story 8.4: Citation-by-ledger-ID enforcement in Writing output

Status: backlog

## Story

As the platform,
I want the Writing agent's output to cite ledger entries by ID, with broken citations surfacing at render time and blocking commit,
So that hallucinated facts are caught immediately (FR26, P8 spirit).

## Scope note

Story 8-3 enforces *structural* citation consistency — the inline `{{led_<ULID>}}` tokens must match the declared `citations` list. This story enforces *referential* validity — every cited ULID must reference a real ledger entry **for this case**, and any broken citation must surface visibly in the cockpit and block decision commit until fixed.

This story is the runtime / UI enforcement layer that pairs with 8-3's structural validator.

**Dependencies:**
- Story 8-3 (citation tokens exist in the schema)
- Story 7-7 (POST /decision endpoint — broken citations block commit at this gate)
- Story 3-1 (JSON ledger reader — used to verify a cited ULID exists)

## Acceptance Criteria

1. **AC1 — Server-side citation validation on commit.** `apps/cockpit-api/src/cockpit_api/services/decision_service.py.validate_decision_citations(decision: Decision, case_id: str) -> list[BrokenCitation]`. Pure function that:
   - Extracts every `{{led_<ULID>}}` token from the decision's rationale text (or each section if EDD memo)
   - For each token, checks the ledger reader for an entry with that ULID `AND case_id == case_id`
   - Returns a list of `BrokenCitation(token=..., reason='not_found' | 'wrong_case')` for any failures

2. **AC2 — Commit endpoint blocks on broken citations.** `POST /v1/cases/{case_id}/decision` (Story 7-7) calls `validate_decision_citations` before persisting. If the returned list is non-empty:
   - Returns HTTP 422 with body `{ "error_code": "broken_citations", "broken": [<list of BrokenCitation>] }`
   - Does not persist the decision
   - Does not transition case state

3. **AC3 — Cockpit-ui renders broken-citation chips.** When the Tiptap editor (Story 7-1) renders text containing `{{led_<ULID>}}` tokens:
   - For each token, attempt to resolve the ULID via `GET /v1/ledger/{ledger_id}` (or whichever reader endpoint exists by Epic 9; for now, use the `useCaseLedger()` hook backed by case-detail data)
   - Resolved tokens render as a `signal-sage` ledger-chip with the entry's short label (e.g., `[doc_intelligence — extract] 11:42`)
   - Unresolved tokens render as a `signal-rose` broken-citation chip with text `Broken citation` and a tooltip showing the bad ULID
   - The broken-citation chip is keyboard-focusable; pressing `Enter` opens an inline edit field that lets the analyst delete or replace the token

4. **AC4 — Commit button disabled when broken citations present.** The decision-commit button (in the existing DecisionZone or Story 12.5's drawer) is disabled when any broken-citation chip is rendered. The button's tooltip reads `Fix N broken citation(s) before committing` where N is the count.

5. **AC5 — Tests — backend.** `apps/cockpit-api/tests/test_decision_citations.py`:
   - `validate_passes_when_all_citations_resolve_to_case_ledger`
   - `validate_fails_when_token_references_nonexistent_ulid` → reason `not_found`
   - `validate_fails_when_token_references_other_case_ulid` → reason `wrong_case`
   - `commit_endpoint_returns_422_on_broken_citations`

6. **AC6 — Tests — frontend.** `apps/cockpit-ui/src/components/cockpit/DecisionZone/CitationChip.test.tsx`:
   - `resolved_citation_renders_sage_chip_with_label`
   - `broken_citation_renders_rose_chip_with_bad_ulid_in_tooltip`
   - `commit_button_disabled_while_any_broken_chip_present`

7. **AC7 — `make lint` + `make test` clean.**

## Tasks / Subtasks

- [ ] **Task 1 — `BrokenCitation` Pydantic + `validate_decision_citations` helper** (AC: #1, #5)
- [ ] **Task 2 — Wire into POST /decision** (AC: #2, #5)
- [ ] **Task 3 — `<CitationChip>` Tiptap inline-mark component** (AC: #3, #6)
  - [ ] Resolved + broken variants
  - [ ] Inline edit affordance for broken
- [ ] **Task 4 — Disable commit button when broken citations present** (AC: #4, #6)
- [ ] **Task 5 — Tests + lint** (AC: #5, #6, #7)
- [ ] **Task 6 — Update `sprint-status.yaml` to `review`**

## Dev Notes

- **Two enforcement layers, complementary.**
  - **8-3 structural:** does the `citations` list match the inline tokens? (server-side, at agent output time)
  - **8-4 referential:** do the cited ULIDs reference real entries on this case? (server-side at commit time + client-side at render time)
  - Both must pass before a decision can be committed.
- **Why client-side rendering + server-side enforcement.** Client-side gives the analyst immediate visual feedback (broken chips appear as they type/edit). Server-side is the unbypassable gate (don't trust the client for the real check).
- **Reason codes** (`not_found`, `wrong_case`) are extensible. If Story 9-x later adds a notion of cross-case citations being intentional, we can add `cross_case_intentional` as a third state without rewriting the validator.
- **The `useCaseLedger()` hook** doesn't exist yet — for the demo, pull ledger entries from the case-detail response (which already includes them via Story 3-x). If the case-detail response doesn't expose ledger entries, add a new `GET /v1/cases/{case_id}/ledger` endpoint (small) — but Epic 9 (Audit Trail) is the cleaner home; coordinate sequencing.

### File List

**To create**
- `apps/cockpit-api/src/cockpit_api/services/decision_service.py` (`validate_decision_citations` if not already present from 7-7)
- `apps/cockpit-api/tests/test_decision_citations.py`
- `apps/cockpit-ui/src/components/cockpit/DecisionZone/CitationChip.tsx`
- `apps/cockpit-ui/src/components/cockpit/DecisionZone/CitationChip.test.tsx`
- `packages/contracts/src/contracts/decisions.py` (`BrokenCitation` if not already there)

**To modify**
- `apps/cockpit-api/src/cockpit_api/routers/decisions.py` (call validator; return 422 on failure)
- `apps/cockpit-ui/src/components/cockpit/DecisionZone/DecisionZone.tsx` (Tiptap inline-mark wiring + commit-button disabling)
- `Documentation/implementation-artifacts/sprint-status.yaml`
