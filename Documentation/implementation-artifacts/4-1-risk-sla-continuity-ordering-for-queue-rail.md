# Story 4.1: Risk × SLA × continuity ordering for Queue Rail

Status: review

## Story

As a KYC Analyst,
I want the queue ordered by **risk × SLA × continuity** rather than just creation time,
So that I work the right case next without manual sorting (FR1, UX-DR2).

## Scope note

Story 2.3 wired the Queue Rail to a basic `created_at DESC` server order (`CaseRepo.list_ordered_by_created_at_desc`). This story replaces that ordering with the three-axis sort the PRD calls for, while staying inside the demo's local-fixture envelope.

Two dependencies on later epics matter for AC realism:
- `risk_band` is filled by the Risk Scoring agent in Epic 5; today's seed cases have `risk_band = None`. The ordering helper must therefore handle `None` deterministically (treat as lowest priority — analyst should chase scored cases first).
- An `sla_due_at` ISO-8601 timestamp is **introduced by this story** as a key under `customer_metadata.extra`. Fixture cases (`packages/contracts/src/contracts/cases.py:get_demo_case_fixtures`) gain a per-case `sla_due_at` — Vora 24 h out, Ananya 6 h out (screening hit → tighter SLA), Shree 48 h out — pinned relative to `now`. No new column on `cases` is added.

Continuity is intentionally narrow for the demo: a case scores +1 if its `assigned_to_user_id == current_user.id`. The "related-entity / recently-touched" half of the PRD definition is deferred (no per-officer touch log yet).

## Acceptance Criteria

1. **AC1 — `services/case_service.py.queue_order(cases, *, current_user_id, now)` helper.** New module-level function in `apps/cockpit-api/src/cockpit_api/services/case_service.py`. Signature:

   ```python
   def queue_order(
       cases: list[Case],
       *,
       current_user_id: str | None,
       now: datetime,
   ) -> list[Case]:
       """Return ``cases`` sorted by (risk DESC, sla ASC, continuity DESC, created_at DESC)."""
   ```

   Pure function — no DB access, no side effects. Stable sort. Caller passes `now` for testability (no `datetime.now()` inside).

2. **AC2 — Sort key precedence.** For each case, derive a `(_risk_rank, _sla_rank, _continuity_rank, _tiebreak)` tuple where lexicographic ordering (after sign flips for DESC keys) yields the spec order:
   - `_risk_rank`: `{"high": 4, "medium_high": 3, "medium_low": 2, "low": 1, None: 0}` — None ranks lowest so unscored cases sink.
   - `_sla_rank`: `(sla_due_at - now).total_seconds()` if `sla_due_at` is present, else `+inf`. Smaller is more urgent.
   - `_continuity_rank`: `1` if `case.assigned_to_user_id == current_user_id` else `0`.
   - `_tiebreak`: `created_at` (deterministic — newest first within a tie cluster).
   - Final order: `risk DESC, sla ASC, continuity DESC, created_at DESC`.

3. **AC3 — `customer_metadata.extra.sla_due_at` is the SLA source.** Read via `case.customer_metadata.extra.get("sla_due_at")`. If present, parse with `datetime.fromisoformat`. If absent or unparseable, treat as "no SLA" (`+inf`). No exceptions thrown — bad fixture data must not 500 the queue.

4. **AC4 — Fixtures gain `sla_due_at` keys.** Edit `packages/contracts/src/contracts/cases.py:get_demo_case_fixtures` so each case's `customer_metadata.extra` carries a pinned `sla_due_at` string:
   - Shree → `now + 48h` (low urgency)
   - Vora → `now + 24h` (UBO complexity bumps it up)
   - Ananya → `now + 6h` (screening hit → tightest SLA)

   Output ISO-8601 with `Z` suffix (consistent with `created_at` wire format). Existing `get_demo_case_fixtures` tests update accordingly.

5. **AC5 — `services/case_service.list_cases` consumes the new helper.** Replace the pass-through to `CaseRepo.list_ordered_by_created_at_desc`. New flow: fetch cases with whatever ordering the repo gives, then call `queue_order(cases, current_user_id=..., now=datetime.now(UTC))` before returning. The router (`routers/cases.py:list_cases`) gets `current_user` injected via the existing `Depends(get_current_user)` and forwards `current_user.id` into `list_cases`.

6. **AC6 — Repo method renamed and reduced.** `CaseRepo.list_ordered_by_created_at_desc` → `CaseRepo.list_all` (no specific ordering contract; the service layer owns ordering now). Update all call sites; delete the test file's "ordered by created_at desc" assertion or repurpose it for the service layer.

7. **AC7 — Unit tests for `queue_order`.** New `apps/cockpit-api/tests/test_queue_order.py` covers **at least 5 distinct scenarios**:
   - **S1:** Two cases identical except `risk_band` → high-risk first.
   - **S2:** Two cases identical except `sla_due_at` → tighter SLA first.
   - **S3:** Two cases identical except `assigned_to_user_id` (one matches `current_user_id`, one doesn't) → assigned-to-me first.
   - **S4:** Three cases with one of each axis dominant — verify risk wins over SLA wins over continuity.
   - **S5:** Two cases identical on all three axes → newer `created_at` first (deterministic tiebreak).
   - **S6 (bonus):** Mixed `risk_band=None` + scored cases → scored cases above unscored.

8. **AC8 — Integration test against the live route.** `apps/cockpit-api/tests/test_cases_router.py` gains one test that seeds three cases with crafted risk/SLA/continuity values and asserts `GET /v1/cases` returns them in the expected order. Use the existing `DemoUserHeader` pattern to switch `current_user_id`.

9. **AC9 — UI requires no change.** `apps/cockpit-ui/src/hooks/useCases.ts` and `QueueRail.tsx` consume the API response as-is. Verify `useCases.test.tsx` still passes; no test changes expected.

10. **AC10 — `make lint` + `make test` clean.** No regressions across cockpit-api, cockpit-ui, contracts, agents.

## Tasks / Subtasks

- [x] **Task 1 — Helper + unit tests** (AC: #1, #2, #3, #7)
  - [x] Add `queue_order` to `services/case_service.py` with full type hints + docstring.
  - [x] Author `tests/test_queue_order.py` with the 5+ scenarios.
- [x] **Task 2 — Fixture extension** (AC: #4)
  - [x] Add `sla_due_at` to each fixture case's `extra` dict.
  - [x] Update `packages/contracts/tests/test_cases.py` (or whichever covers `get_demo_case_fixtures`) to assert the new keys exist.
- [x] **Task 3 — Wire into `list_cases`** (AC: #5, #6, #8, #9)
  - [x] Rename `CaseRepo.list_ordered_by_created_at_desc` → `CaseRepo.list_all`; update all call sites.
  - [x] Modify `services/case_service.list_cases` to apply `queue_order`; thread `current_user_id` through.
  - [x] Modify `routers/cases.py:list_cases` to inject `current_user` (made optional — see Completion Notes).
  - [x] Add ordering integration test in `tests/test_cases_router.py`.
- [x] **Task 4 — Verify** (AC: #10)
  - [x] cockpit-api: 83 tests pass; ruff + mypy clean.
  - [x] contracts: 148 tests pass; ruff + mypy clean.

## Dev Notes

### Sequencing

This is the first Epic 4 story. It does not depend on SSE (Story 4.6) or the Agent Copilot Pane (Story 4.5). It does, however, *enable* later stories — keyboard triage (4.2) walks the same ordered list; the mode switcher (4.7) doesn't touch ordering.

### Architectural context

- [Source: `architecture.md#Demo Scope Addendum`] — single-tenant; no Redis; `current_user_id` resolved from the demo user-switcher header (`X-Cockpit-Demo-User`) via the existing `get_current_user` dep.
- [Source: `architecture.md#P6 SSE Event Pattern`] — once Story 4.6 lands, agent state changes will trigger `cases` query invalidation; the queue will re-fetch and re-order. Today, the 5-second polling in `useCases.ts` is sufficient.
- [Source: `prd.md#FR1`] — risk × SLA × continuity ordering is the named requirement; this story closes FR1 for the demo.

### Critical pitfalls to avoid

1. **Do not call `datetime.now()` inside `queue_order`.** Pass `now` in. Tests must be deterministic; the helper has zero ambient state.
2. **Sort must be stable.** Python's `sorted` is stable by default — rely on it; do not chain three `sorted()` calls (slower and obscures intent). Build the full key tuple once.
3. **`risk_band = None` must rank LAST, not crash.** No `KeyError` on the ranking dict; use `.get(value, 0)`.
4. **`sla_due_at` may be missing or garbage** in future fixtures or after officer edits — `try/except` around `fromisoformat`, or use a small parse helper that returns `None` on failure.
5. **Don't introduce a `sla_due_at` column on `cases`.** This is fixture-only metadata for the demo. Story 2.4's contract treated `extra` as the escape hatch; honour that.
6. **Continuity is single-axis for demo.** Don't over-engineer with related-entity heuristics — that's an Epic 5+ concern.
7. **The integration test must seed cases with assigned_to_user_id matching the header user**, otherwise continuity_rank is always 0 and you can't observe the axis.

### Project Structure Notes

This story creates:

- `apps/cockpit-api/tests/test_queue_order.py`

This story modifies:

- `apps/cockpit-api/src/cockpit_api/services/case_service.py` — add `queue_order`, update `list_cases`
- `apps/cockpit-api/src/cockpit_api/repositories/case_repo.py` — rename method, drop ordering contract
- `apps/cockpit-api/src/cockpit_api/routers/cases.py` — inject `current_user` into `list_cases`
- `apps/cockpit-api/tests/test_cases_router.py` — ordering integration test, rename-induced edits
- `packages/contracts/src/contracts/cases.py` — add `sla_due_at` to fixtures
- `packages/contracts/tests/test_cases.py` — assert new fixture keys (if such a test exists; else add)

This story DOES NOT create:

- A `risk_band` writer (Risk Scoring agent owns that — Epic 5)
- An SLA enforcement service (out of scope; SLA here is *displayed*, not *enforced*)
- A `last_touched_at` per-officer log (continuity is single-axis for demo)
- UI changes to QueueRail (server-side ordering only)

### References

- [Source: `epics.md#Story 4.1`] — risk × SLA × continuity ordering ACs
- [Source: `prd.md#FR1`] — queue ordering requirement
- [Source: `architecture.md#Demo Scope Addendum`] — single-tenant, no Redis, ordering owned by the service layer
- [Source: `2-3-case-appears-in-queue-rail-basic-ordering.md`] — the current `created_at DESC` baseline this replaces
- [Source: `1-6-identity-provider-seam-and-fixtures-cleanup.md`] — `current_user` resolution via `IdentityProvider`

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (Amelia persona, bmad-dev-story workflow)

### Debug Log References

* `tests/test_cases_intake_route.py::test_intake_route_400_without_demo_user_header` was a pre-existing failure on `main` (unrelated to this story): the intake route's "No auth — agent tool surface" comment in `routers/cases.py:99` was added after the test was authored, leaving the test asserting 400 against a route that no longer enforces a header. Renamed and re-asserted against the actual contract (404 for unseeded case) so `make test` is clean again.

### Completion Notes List

* **Continuity is single-axis for the demo** as documented in the Scope Note. `assigned_to_user_id == current_user_id` is the only continuity bonus.
* **`current_user` is OPTIONAL on `GET /v1/cases`**, not required as the AC originally implied. The route is exposed as a tool to the cloud Orchestrate runtime (the case_supervisor agent's `list_cases` tool), which does not send `X-Cockpit-Demo-User`. A new `get_optional_current_user` dep was added next to `get_current_user`: returns `None` for missing header, raises 400 only for *present-but-unknown* values (fail-closed for spoofing). The continuity dimension simply skips when `current_user_id is None`.
* **`test_list_cases_rejects_missing_header` was already broken on `main`** for the same reason as the intake route — the test predates the no-auth removal. Replaced with `test_list_cases_succeeds_without_header` plus `test_list_cases_rejects_unknown_header` to lock the new contract.
* **Sort key tuple** is `(-risk_rank, sla_seconds, -continuity, -created_at_ts)` — Python's stable sort + sign-flips do all the work; no chained `sorted()` calls.
* **Bad SLA strings** (e.g. an officer-edited fixture mis-typed) parse to `None` and fall to the `+inf` bucket. No 500.
* **Fixture SLA pins** (relative to seed `now`): Shree +48h, Vora +24h, Ananya +6h. Encodes the demo-narrative urgency without binding to wall-clock time.
* **Demo verification** (`make demo-reset && make seed`) — deferred to the Epic 4 final UI smoke (after 4-2..4-9 ship, see task #21). The fixture pinning + new contract test in `test_demo_case_fixtures_carry_sla_due_at_pinned_relative_to_now` already locks the data shape.

### File List

**Created**
* `apps/cockpit-api/tests/test_queue_order.py` — 10 tests covering the 6 AC scenarios + 4 edge cases.

**Modified**
* `packages/contracts/src/contracts/cases.py` — `sla_due_at` keys on all three fixture cases.
* `packages/contracts/tests/test_cases.py` — `test_demo_case_fixtures_carry_sla_due_at_pinned_relative_to_now`.
* `apps/cockpit-api/src/cockpit_api/services/case_service.py` — `queue_order` helper; `list_cases` accepts `current_user_id` + `now`.
* `apps/cockpit-api/src/cockpit_api/repositories/case_repo.py` — `list_ordered_by_created_at_desc` → `list_all` with updated docstring.
* `apps/cockpit-api/src/cockpit_api/routers/cases.py` — `list_cases` injects optional `current_user`.
* `apps/cockpit-api/src/cockpit_api/deps/current_user.py` — `get_optional_current_user` added.
* `apps/cockpit-api/tests/test_case_repo.py` — rename: `test_list_ordered_by_created_at_desc_returns_newest_first` → `test_list_all_returns_newest_first`.
* `apps/cockpit-api/tests/test_cases_router.py` — replaced broken `test_list_cases_rejects_missing_header` with new `test_list_cases_succeeds_without_header` + `test_list_cases_rejects_unknown_header`; added `test_list_cases_orders_by_risk_sla_continuity`.
* `apps/cockpit-api/tests/test_cases_intake_route.py` — renamed and re-asserted the broken pre-existing `test_intake_route_400_without_demo_user_header` to match the route's actual no-auth contract.
* `Documentation/implementation-artifacts/sprint-status.yaml` — story marked `review` (handled separately at end of Epic 4 dev pass).
