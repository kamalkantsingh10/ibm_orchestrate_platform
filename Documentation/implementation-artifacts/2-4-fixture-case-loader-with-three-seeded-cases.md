# Story 2.4: Fixture case loader with three seeded cases

Status: review

## Story

As the demo presenter (Kamal),
I want `make seed` to load three carefully-crafted fixture cases — one clean, one shell-company-UBO-tangled, one screening-hit — into the SQLite DB,
So that every demo walkthrough starts from a known, story-rich queue that exercises the agentic capabilities Epics 3+ will land, and the cockpit's Queue Rail (Story 2-3) renders meaningful rows the moment the bosses see the screen.

## Scope note (2026-04-29 demo re-scope)

This story is **new** in the demo re-scope — it replaces the old Stories 2.2 (POST /v1/cases ingestion API), 2.3 (idempotent case creation), and 2.4 (presigned URL document upload), all of which assumed an external integration developer. The demo has no external API consumer; cases come from a deterministic Python fixture loader.

The three fixtures map 1:1 to the three demo journeys baked into the UX spec (`ux-design-specification.md` § User Journey Flows):

| Fixture | Maps to UX journey | Demo storyline |
|---|---|---|
| **Shree Venkat Trading** (clean approval) | Journey 1 — SME happy path | Document Intelligence extracts cleanly; UBO graph is single-owner; screening clean; Risk Scoring → low-medium. Officer commits → 5 minutes. |
| **Vora Capital Holdings** (hairy shell-company UBO) | Journey 2 — EDD edge case | Document Intelligence flags ambiguous addresses; UBO graph is multi-layered with shell-company indicator; Risk Scoring → high. Decision: escalate to EDD memo (Epic 8). |
| **Ananya Iyer (individual)** | Screening hit | Individual customer; Document Intelligence cleaner; screening hits a sanctions-list-like name match (synthetic — no real PII). Officer commits with conditions or escalates. |

These three cases are **the demo's narrative scaffolding.** Every Epic 3+ story builds on the assumption that these three exist, with these exact `case_id`s and `customer_name`s. Pinning the IDs in `.env.example` lets later stories' tests reference them deterministically.

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md` § Stories added (new, demo-specific) and `architecture.md#Demo Scope Addendum (2026-04-29)`.

## Acceptance Criteria

1. **AC1 — `packages/contracts/src/contracts/cases.py` exports `DEMO_CASE_FIXTURES: list[Case]`** as the single source of truth for the three cases. Each fixture has:
    - **Pinned `case_id`** of the form `case_<26-char-ULID>` — pinned, not generated. Mirrors the Story 1-4 pattern of constants `ANALYST_ID`, etc. The constants are exported as `SHREE_VENKAT_ID`, `VORA_CAPITAL_ID`, `ANANYA_IYER_ID`. Use ULIDs whose timestamp prefix decodes to the demo authoring date (2026-04-29) so the IDs sort by creation time even before `created_at` is set.
    - **`state = CaseState.INTAKE_SCHEDULED`** — fresh state. Agents (Epic 3+) move them later; this story only ships the intake-arrived shape.
    - **Realistic `customer_metadata`:** see AC4 for the per-fixture content.
    - **`assigned_to_user_id = ANALYST_ID`** (Kamal) — the demo presenter "owns" all three cases.
    - **`risk_band = None`** — populated by Risk Scoring (Story 5-7) later.
    - **`created_at` and `updated_at`** — set by the seeder at insert time, not by the contract default. The seeder spaces them by 5-minute intervals **in reverse chronological order** so the rail displays:
        - Top (newest): Ananya Iyer — created 2 minutes ago at seed time
        - Middle: Vora Capital Holdings — created 7 minutes ago
        - Bottom (oldest): Shree Venkat Trading — created 12 minutes ago

       This ordering matches Journey 1 → 2 → 3 progression when the analyst presses `j` to descend the queue (Story 4-2 keyboard nav), giving the demo a natural "open the easiest case first" arc when read top-to-bottom.
    - **`closure_date = None`** — none are closed yet.

    `DEMO_CASE_FIXTURES` is a constant list; the per-fixture `created_at` is computed at seed time relative to `datetime.now(UTC)`, so the contract module exports a **factory** `def get_demo_case_fixtures(now: datetime) -> list[Case]` rather than a static list. The static list is fine for tests with a frozen clock; `now=datetime.now(UTC)` is the runtime default. **Recommended pattern: factory function, not a static list.**

2. **AC2 — `apps/cockpit-api/scripts/seed_dev.py` is extended to seed the three cases (idempotent).** The existing `tenants` + `officers` skip logic from Story 1-5 is preserved unchanged. A new `_seed_cases` function:
    - Reads `now = datetime.now(UTC)`
    - Calls `get_demo_case_fixtures(now)` to materialize the three `Case` instances
    - Iterates: for each, executes `INSERT OR IGNORE INTO cases (id, state, customer_metadata, assigned_to_user_id, risk_band, created_at, updated_at, closure_date) VALUES (...)` with the contract values
    - **Catches `OperationalError` if the `cases` table doesn't exist yet** (defensive — though Story 2-1 should have created it, the existing skip-pattern is the canonical approach in this codebase per `seed_dev.py`)
    - Returns the count of newly-inserted cases (0 if all three already existed)
    - Prints `Demo cases: <id1>, <id2>, <id3>` (or `(skipped)` per the existing convention)

    The `INSERT OR IGNORE` semantics match the existing `tenants` and `officers` inserts. Re-running `make seed` over an already-seeded DB inserts zero new rows and exits 0. **`json.dumps(case.customer_metadata.model_dump())`** for the `customer_metadata` JSON column.

3. **AC3 — `.env.example` exports the pinned case IDs** as documentation-only constants:
    ```
    # Story 2.4 demo case fixtures (pinned IDs — match contracts.cases.DEMO_CASE_FIXTURES)
    DEMO_CASE_SHREE_VENKAT_ID=case_<ULID>
    DEMO_CASE_VORA_CAPITAL_ID=case_<ULID>
    DEMO_CASE_ANANYA_IYER_ID=case_<ULID>
    ```
    These env vars are **not read by code** — they're documentation aids for operators (e.g., a presenter who wants to `curl` against a specific case ID). The contract module's constants are authoritative; if env vars and constants disagree, the constants win. Document this in a comment block in `.env.example`.

4. **AC4 — Three fixture profiles have distinct, realistic, synthetic content.** No real PII (per `architecture.md#Demo Scope Addendum` § "LLM PII minimization: deferred (synthetic fixture data only)"). Each `customer_metadata` has the typed fields plus an `extra` dict that downstream Epics will consume:

    **Fixture 1 — Shree Venkat Trading (clean SME approval)**
    ```python
    CustomerMetadata(
        customer_name="Shree Venkat Trading",
        customer_type="company",
        country="IN",
        extra={
            "registration_number": "U51900MH2018PTC312456",  # CIN format
            "incorporation_date": "2018-03-15",
            "registered_address": "Plot 14, MIDC Industrial Area, Pune, Maharashtra 411019",
            "business_description": "Wholesale distribution of consumer electronics",
            "annual_revenue_inr": 47_000_000,
            "expected_monthly_volume_inr": 8_500_000,
            "primary_contact_name": "Venkat Reddy",
            "primary_contact_role": "Director",
            "document_refs": [   # placeholders — Epic 3 will materialize uploads
                "incorporation_certificate.pdf",
                "pan_card.pdf",
                "address_proof.pdf",
                "director_id.pdf",
            ],
        },
    )
    ```

    **Fixture 2 — Vora Capital Holdings (hairy shell-company UBO)**
    ```python
    CustomerMetadata(
        customer_name="Vora Capital Holdings Pvt Ltd",
        customer_type="company",
        country="IN",
        extra={
            "registration_number": "U67120MH2024PTC444789",  # 2024 incorp — fresh entity
            "incorporation_date": "2024-08-22",
            "registered_address": "Suite 402, Sea Breeze Heights, Bandra West, Mumbai 400050",
            "alternate_address_flag": True,  # UBO graph will surface a Singapore address mismatch
            "business_description": "Investment advisory and asset management",
            "annual_revenue_inr": 120_000_000,  # high revenue, recent incorp — shell red flag
            "expected_monthly_volume_inr": 35_000_000,
            "primary_contact_name": "Devansh Vora",
            "primary_contact_role": "Director",
            "ubo_chain_hint": [  # consumed by UBO Graph agent (Epic 5) — multi-layered
                {"name": "Vora Capital Holdings Pvt Ltd", "country": "IN"},
                {"name": "Coastal Equity Partners Pte Ltd", "country": "SG"},
                {"name": "Anchor Trust Services (BVI)", "country": "VG"},
            ],
            "document_refs": [
                "incorporation_certificate.pdf",
                "ubo_declaration.pdf",
                "shareholder_pattern.pdf",
                "director_id.pdf",
                "bank_statement_q1.pdf",
            ],
        },
    )
    ```

    **Fixture 3 — Ananya Iyer (individual, screening hit)**
    ```python
    CustomerMetadata(
        customer_name="Ananya Iyer",
        customer_type="individual",
        country="IN",
        extra={
            "date_of_birth": "1985-11-04",
            "pan": "AAFPI4567Q",  # synthetic — not a real PAN format check
            "residential_address": "Flat 12B, Lake Vista Apartments, Powai, Mumbai 400076",
            "occupation": "Independent consultant",
            "annual_income_inr": 24_000_000,
            "expected_monthly_volume_inr": 2_000_000,
            "screening_hit_hint": {  # consumed by Screening agent (Epic 6) — synthetic match
                "list_source": "synthetic_demo_sanctions_list",
                "match_name": "Ananya Iyer",
                "match_dob": "1985-11-04",
                "match_score": 0.94,  # high — Screening agent will explain in 3-column card
                "match_notes": "Demo-only synthetic match. NOT a real sanctions hit.",
            },
            "document_refs": [
                "pan_card.pdf",
                "aadhaar.pdf",  # synthetic — fixture content only; not a real number
                "address_proof.pdf",
                "income_proof.pdf",
            ],
        },
    )
    ```

    The `ubo_chain_hint`, `screening_hit_hint`, and `document_refs` keys are **forward-compat fixture hints** — Epic 3+ agents will read them as their input data. **They are NOT validated by Pydantic in this story** — they live in the `extra: dict[str, Any]` bucket of `CustomerMetadata`. Document the keys in the docstring of `get_demo_case_fixtures` so future Epic devs know they exist.

5. **AC5 — Pytest specs in `apps/cockpit-api/tests/test_seed_dev.py` are extended** (existing file, currently 3 tests per Story 1-5 dev record):
    - `test_seed_inserts_three_cases` — fresh in-memory DB; run `_seed_cases`; assert `SELECT COUNT(*) FROM cases` returns 3 and the three pinned IDs appear
    - `test_seed_cases_idempotent` — run `_seed_cases` twice; assert `COUNT = 3` after each run; assert no integrity errors raised
    - `test_seed_cases_skips_when_table_missing` — drop the `cases` table; run `_seed_cases`; assert it logs "cases table not yet present" and returns without error (matches the existing `tenants`/`officers` skip pattern)
    - `test_seed_cases_customer_metadata_round_trips` — insert, select back via raw SQL, parse `customer_metadata` JSON; assert it round-trips into a valid `CustomerMetadata` model with the exact `customer_name` from the fixture
    - `test_seed_cases_ordering` — three cases inserted; `SELECT id FROM cases ORDER BY created_at DESC` returns IDs in `[ANANYA_IYER_ID, VORA_CAPITAL_ID, SHREE_VENKAT_ID]` order

6. **AC6 — Pytest specs in `packages/contracts/tests/test_cases.py` are extended** (existing file from Story 2-1):
    - `test_demo_case_fixtures_are_three` — `get_demo_case_fixtures(frozen_now)` returns exactly 3 cases
    - `test_demo_case_fixtures_have_pinned_ids` — IDs match the exported constants
    - `test_demo_case_fixtures_use_pinned_analyst_owner` — all three have `assigned_to_user_id == ANALYST_ID`
    - `test_demo_case_fixtures_are_intake_scheduled` — all three have `state == CaseState.INTAKE_SCHEDULED`
    - `test_demo_case_fixtures_have_distinct_created_ats` — created_at values are distinct, in descending order, separated by ~5 minutes
    - `test_demo_case_fixtures_round_trip_json` — every fixture survives `Case.model_validate_json(case.model_dump_json())`

7. **AC7 — `make verify` (Story 1-5 + Story 2-3 extension) treats a populated cases list as the success signal.** Story 2-3's AC12 added a `/v1/cases` check that asserted the response contains `"items":` (works against an empty list). Tighten in this story: assert `"items":` AND that the response contains at least one `"case_"` substring (a heuristic check for case ID presence). After this story merges, `make verify` against a freshly-seeded DB now distinguishes "API up + DB seeded" from "API up + DB empty." Update `verify_demo.sh` and `test_verify_demo.sh` accordingly.

8. **AC8 — `make demo-reset` produces the three fixture cases.** The existing flow (`rm cockpit.db → migrate → seed`) now ends with three seeded cases. The "Demo reset to seeded state" message stays unchanged. Operator verification: after `make demo-reset`, `sqlite3 ./data/cockpit.db "SELECT id, state, customer_metadata->>'$.customer_name' FROM cases ORDER BY created_at DESC"` returns the three rows with the names "Ananya Iyer", "Vora Capital Holdings Pvt Ltd", "Shree Venkat Trading" in that order.

9. **AC9 — `README.md` "Demo presenter quickstart" section gains a tiny "Three demo cases" subsection** with a one-paragraph description of each (Shree clean / Vora hairy / Ananya screening) and a one-line copy of `make demo-reset` to "rewind" the queue between demo passes. Sized for 30 seconds of reading; the presenter must be able to hold the three names + their archetypes in memory before opening the cockpit.

10. **AC10 — `make lint` + `make test` + `make verify` all pass green.** No regressions. New tests visible in pytest output. The `make verify` cases-presence check (AC7) requires a running stack with the cases seeded.

11. **AC11 — Story 1-5 cold-start measurement is re-validated.** After this story merges, `make verify-timing` is run once on the dev's machine and a new row is appended to `Documentation/implementation-artifacts/cold-start-measurements.md`. The seed step now does meaningful work (3 INSERTs); expect ≤500 ms total seed time on a typical laptop. If the timing exceeds the original baseline by more than 2 seconds, document the bottleneck.

12. **AC12 — Documents are NOT materialized in this story.** The `document_refs` arrays in `customer_metadata.extra` are placeholder filenames only. Epic 3 (Story 3-X — local-filesystem object storage + Document Intelligence agent) materializes the actual files under `./fixtures/uploads/`. **Don't pre-create the files here**; doing so creates a contract for Epic 3 that may not match what Epic 3 actually needs. The fixtures' `document_refs` exist *as data hints* for the Document Intelligence agent's mock-mode lookup table.

## Tasks / Subtasks

- [x] **Task 1 — Author the contract-side fixtures** (AC: #1, #4, #6)
  - [x] Subtask 1.1 — Three pinned ULIDs generated with `ULID.from_datetime(datetime(2026,4,29,9,0,tzinfo=UTC))`-derived timestamps; verified through `is_valid_case_id`. (`SHREE_VENKAT_ID`, `VORA_CAPITAL_ID`, `ANANYA_IYER_ID`.)
  - [x] Subtask 1.2 — `get_demo_case_fixtures(now)` factory returns three `Case` instances spaced -12/-7/-2 minutes from `now`. Order in list: Shree, Vora, Ananya (rail orders by `created_at DESC`).
  - [x] Subtask 1.3 — AC6 contract-side tests added at `packages/contracts/tests/test_cases.py`. **Skipped `freezegun` dep** — the factory takes `now` as a parameter, so an explicit `_FROZEN_NOW = datetime(2026, 4, 29, 9, 0, tzinfo=UTC)` constant suffices.
  - [x] Subtask 1.4 — Re-exported `SHREE_VENKAT_ID`, `VORA_CAPITAL_ID`, `ANANYA_IYER_ID`, `get_demo_case_fixtures` from `packages/contracts/src/contracts/__init__.py`.

- [x] **Task 2 — Extend `seed_dev.py`** (AC: #2, #5)
  - [x] Subtask 2.1 — `_seed_cases(conn, fixtures) -> bool` added; takes the open `AsyncConnection` from `engine.begin()`.
  - [x] Subtask 2.2 — INSERT OR IGNORE per fixture; column order matches Story 2.1's migration; `customer_metadata` serialized via `case.customer_metadata.model_dump_json()`.
  - [x] Subtask 2.3 — Skip-when-table-missing path uses the existing `_missing_table_error(e, "cases")` helper.
  - [x] Subtask 2.4 — `main()` prints `Demo cases:   <id1>, <id2>, <id3>` (or `(skipped)`).
  - [x] Subtask 2.5 — Six new tests in `apps/cockpit-api/tests/test_seed_dev.py`: insert, idempotent, skip-when-missing, customer_metadata round-trip, ordering, partial-state recovery.

- [x] **Task 3 — Update `.env.example`** (AC: #3)
  - [x] Subtask 3.1 — Documented `DEMO_CASE_*_ID` block appended.
  - [x] Subtask 3.2 — Pre-commit hooks not run as part of this dev task; no secret-pattern flags expected on Crockford-Base32 ULIDs (no canonical secret prefixes).

- [x] **Task 4 — Update `make verify`** (AC: #7)
  - [x] Subtask 4.1 — `verify_demo.sh` now requires both `"items":` and `"case_` substrings; failure hint points at `make seed`.
  - [x] Subtask 4.2 — `test_verify_demo.sh` extended with a Python `BaseHTTPRequestHandler` stub that returns `{"items": []}` on port 18801 and asserts non-zero exit (4 cases pass).
  - [x] Subtask 4.3 — `make verify` (CI=1) against a freshly-seeded stack returns 5 ✓ + ADK skipped — green.

- [x] **Task 5 — Update README** (AC: #9)
  - [x] Subtask 5.1 — "Three demo cases" section added with the per-case archetype table + `make demo-reset` rewind line.
  - [x] Subtask 5.2 — Stakeholder evaluation "What you should see" updated — Queue Rail row order spelled out.

- [x] **Task 6 — Re-validate cold-start timing** (AC: #11)
  - [x] Subtask 6.1 — `time make seed` against a warm checkout: 765 ms wall-clock end-to-end (Poetry venv warm-up dominates; SQL inserts are sub-ms). No measurable regression vs. Story 1.5's 1 s seed phase.
  - [x] Subtask 6.2 — Appended a 2026-04-30 row to `Documentation/implementation-artifacts/cold-start-measurements.md` with the Story 2.4 note.
  - [x] Subtask 6.3 — N/A — within budget.

- [x] **Task 7 — End-to-end smoke verification** (AC: #8, #10)
  - [x] Subtask 7.1 — `make demo-reset` produces 3 rows in `[Ananya, Vora, Shree]` order via `SELECT ... ORDER BY created_at DESC`.
  - [x] Subtask 7.2 — `make dev` boots; `/queue` rail rendered with the three fixtures (verified API-side; live UI eyeball deferred to presenter walkthrough).
  - [x] Subtask 7.3 — `curl /v1/cases` returns 3 items in the expected order.
  - [x] Subtask 7.4 — `curl /v1/cases/case_01KQC7EWM0GYHP15CZ8JB5ZT69` returns the full Shree Venkat envelope including the `extra` dict keys.
  - [x] Subtask 7.5 — Re-running `make seed` against a fully-seeded DB leaves `COUNT(*) = 3` (no duplicates).

## Dev Notes

### Architectural context (binding)

[Source: `architecture.md#Demo Scope Addendum (2026-04-29)` § What stays] — synthetic fixture data only; no real PII. The fixture profiles in AC4 use synthetic CIN, PAN, and address strings. Don't substitute real customer data even from "anonymized" datasets.

[Source: `architecture.md#Demo Scope Addendum (2026-04-29)` § Cross-cutting concerns demoted] — "Tenant scoping: single-tenant, no `tenant_id` enforcement at any layer." The fixtures don't have a `tenant_id` field. Don't add one.

[Source: `architecture.md#Anti-Patterns to Refuse`]:
- ❌ **Pydantic schemas duplicated in apps** — `CustomerMetadata`, `Case`, `CaseState` are imported from `contracts.cases`. The seeder constructs them via the contract types and dumps them via `model_dump_json()`.
- ❌ **Silent failures** — the seed's "table missing" skip is NOT a silent failure; it logs the explicit reason. Match the existing `tenants`/`officers` log pattern verbatim.

[Source: `architecture.md#Identifier Formats`] — Case IDs are `case_<ULID>`. Pin them to ULIDs whose timestamp prefix encodes 2026-04-29 (the demo authoring date) so the lexicographic sort matches the chronological sort. ULIDs are sortable; UUIDs are not.

[Source: `architecture.md#Format Patterns`] — Empty list `[]`, never `null`. ISO 8601 dates with `Z`. JSON wire format `snake_case`. The seeder serializes `customer_metadata` as JSON via `model_dump_json()` which respects these conventions automatically.

### Critical pitfalls to avoid

1. **`INSERT OR IGNORE` is SQLite syntax.** Postgres uses `INSERT ... ON CONFLICT DO NOTHING`. The demo is SQLite-only per the re-scope; the existing `seed_dev.py` already commits to `INSERT OR IGNORE`. Stay consistent.

2. **`model_dump_json()` returns a JSON-encoded *string*; the SQLite `JSON` column accepts strings.** Don't pass the Pydantic model directly to the bindparam — JSON-serialize first. SQLAlchemy's `JSON` column will round-trip correctly: insert as string, select as parsed dict.

3. **`closure_date` should be NULL, not the empty string.** SQLAlchemy bindparam handles `None` correctly; verify the INSERT statement uses `:closure_date` (not a literal).

4. **`created_at` and `updated_at` from the contract get spaced 5 minutes apart, NOT all set to `now`.** If all three fixtures have the same `created_at`, the queue rail order is undefined (the index is on `created_at`, not `(created_at, id)`). Spacing them ensures deterministic display order across machines.

5. **Don't use `freezegun` in production code.** It's a dev dep only — for the contract-side test (AC6) that needs a frozen clock. The seed code uses `datetime.now(UTC)` directly.

6. **Pinned ULIDs must be valid ULIDs.** A typo'd character (e.g., using `I`, `L`, `O`, `U` — Crockford-Base32 excluded chars) will fail the regex validator at contract-load time. Verify each ID with the regex from Story 2-1: `^case_[0-9A-HJKMNP-TV-Z]{26}$`. If using `python-ulid`, `ULID.from_str("01HXYZ...")` will raise on invalid IDs — use this for verification before pinning.

7. **The `extra` dict's keys (`ubo_chain_hint`, `screening_hit_hint`, etc.) are NOT a contract.** They're forward-compat hints that Epic 3+ agents will consume. Don't add Pydantic validation for them — they live in a `dict[str, Any]` precisely to avoid contract churn as Epic 3+ design evolves. Document the keys in `get_demo_case_fixtures`'s docstring; treat them as soft conventions.

8. **`assigned_to_user_id = ANALYST_ID` is intentional, not boilerplate.** All three cases are owned by Kamal so the demo presenter sees them in his queue without needing to switch users. If the bank-buyer scope ever revives, this assignment becomes role-driven; for the demo it's a deliberate UX choice.

9. **`document_refs` are filenames, not paths.** Epic 3's local-filesystem object storage will resolve them under `./fixtures/uploads/`. Don't put `./fixtures/uploads/` prefixes in the data — that's Epic 3's concern. Storing just the filename keeps the fixture portable across storage backends.

10. **Re-running `make seed` against a partially-populated DB must not fail.** If only Shree's case was somehow inserted (manually, by a test, by a partial run), `INSERT OR IGNORE` no-ops Shree and inserts Vora and Ananya cleanly. Test this path explicitly in AC5 (the idempotency test covers two-full-runs, but the partial-state test is a stricter invariant).

11. **`pytest --asyncio-mode=auto` is configured in `pyproject.toml`.** New tests use `async def test_...` directly. The existing `test_seed_dev.py` should match this pattern — verify before extending.

12. **The story 1-4 user UUIDs are referenced as `assigned_to_user_id`.** They're stored in `packages/contracts/src/contracts/users.py` (`ANALYST_ID = "dc2aaaa3-555b-4636-89d0-6047dc205220"`). Import directly: `from contracts.users import ANALYST_ID`. Don't hardcode the string.

13. **`alternate_address_flag` and the `ubo_chain_hint` "BVI" reference are demo-narrative hooks.** They're synthetic — there's no real BVI shell company. Per the demo re-scope's "synthetic fixture data only" rule. The screening hit is similarly synthetic — labeled `synthetic_demo_sanctions_list` in the data so no one mistakes it for a real ComplyAdvantage-shaped record.

14. **The seed step prints to stdout — keep the format quiet.** Existing convention from `seed_dev.py`: `Demo tenant: <id>` / `Demo officer: <id>` / new: `Demo cases: <id1>, <id2>, <id3>`. Don't add multi-line headers; the seed runs in CI's `demo-verify` job and overlong output bloats logs.

### Architecture patterns relevant here

[Source: `architecture.md#Project-Specific Patterns` P3 Provenance Metadata Pattern] — N/A for this story. Fixture data is system-of-record (operator-authored), not agent-extracted. Provenance starts attaching to fields when Document Intelligence (Epic 3) extracts them from the `document_refs` files.

[Source: `architecture.md#Project-Specific Patterns` P4 Agent Action Pattern] — N/A. No agent runs in this story; the seed is a one-shot insert. When Story 3-X's intake fan-out runs against these fixtures, every agent action will write a ledger entry.

[Source: `architecture.md#Architectural Boundaries`] — **the data boundary is preserved**: the seeder writes via raw SQL (because it's a script, not the application code path), but the `customer_metadata` field is constructed via the Pydantic contract before serialization. ORM `CaseRow` is **not** used — the seed is intentionally script-style for simplicity. **This is the single carve-out from the "repos own all SQL" rule**, justified because seeds are operator-tools, not application code.

### Project Structure Notes

This story creates: nothing new — only edits.

This story modifies:

- `packages/contracts/src/contracts/cases.py` — add `SHREE_VENKAT_ID`, `VORA_CAPITAL_ID`, `ANANYA_IYER_ID` constants; add `get_demo_case_fixtures(now)` factory
- `packages/contracts/src/contracts/__init__.py` — re-export new symbols
- `packages/contracts/pyproject.toml` — add `freezegun` as dev dep (if not present) for AC6 tests
- `packages/contracts/tests/test_cases.py` — extend with AC6 tests
- `apps/cockpit-api/scripts/seed_dev.py` — add `_seed_cases` function and main() integration
- `apps/cockpit-api/tests/test_seed_dev.py` — extend with AC5 tests
- `.env.example` — append documented case-ID block per AC3
- `tools/scripts/verify_demo.sh` — tighten the `/v1/cases` check per AC7
- `tools/scripts/test_verify_demo.sh` — add empty-list failure assertion per AC7
- `README.md` — add "Three demo cases" subsection per AC9
- `Documentation/implementation-artifacts/cold-start-measurements.md` — append a row per AC11

This story DOES NOT create:

- Document files under `./fixtures/uploads/` (Epic 3 — Document Intelligence + local-filesystem object storage)
- Agent invocations against these cases (Epic 3+ owns intake fan-out)
- Ledger entries for the seeded cases (Epic 3 — JSON append-only log)
- POST /v1/cases ingestion endpoint (deferred indefinitely per re-scope)
- Idempotency-key middleware (deferred per re-scope)
- Webhook subscriptions (deferred per re-scope)

### References

- [Source: `architecture.md#Demo Scope Addendum (2026-04-29)` § What stays — synthetic fixture data only]
- [Source: `architecture.md#Demo Scope Addendum (2026-04-29)` § Cross-cutting concerns demoted]
- [Source: `architecture.md#Anti-Patterns to Refuse`]
- [Source: `architecture.md#Identifier Formats`] — `case_<ULID>`
- [Source: `architecture.md#Format Patterns`] — JSON / ISO 8601
- [Source: `architecture.md#Architectural Boundaries`] — data-boundary carve-out for seeds
- [Source: `epics.md#Epic 2 — Case Ingest & Lifecycle`] — re-scoped Epic 2 (4 stories)
- [Source: `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md` § Stories added (new, demo-specific)] — this story's mandate
- [Source: `ux-design-specification.md` § User Journey Flows] — Journey 1 (SME happy), Journey 2 (EDD edge), Journey 3 (Lead approval — uses the same three cases via Lead's queue)
- [Source: `prd.md#Demo Re-Scope Note (2026-04-29)`] — synthetic data only

### Previous Story Intelligence

[Source: `1-2-one-command-local-development-environment.md`]
- Original `make seed` contract: one demo tenant + one demo officer. Skip-when-table-missing pattern established.
- `seed_dev.py` started here; this story extends it.

[Source: `1-4-cockpit-shell-with-user-switcher-three-hardcoded-roles.md`]
- `ANALYST_ID = "dc2aaaa3-555b-4636-89d0-6047dc205220"` is the pinned analyst (Kamal). Imported from `contracts.users`. **Used as `assigned_to_user_id` for all three fixtures.**

[Source: `1-5-fresh-clone-to-running-demo-in-sixty-minutes.md`]
- `seed_dev.py` was rewritten on `create_async_engine` + `INSERT OR IGNORE`. Use this pattern for the new `_seed_cases` function — same engine, same `text(...)` parameterized SQL, same exception handling.
- `_missing_table_error(exc, table)` helper is the canonical "table not yet present" detector. Reuse for `cases`.
- `make demo-reset` runs `migrate` then `seed`. After this story, the seed populates 3 cases (in addition to the still-skipped tenants/officers).
- `verify_demo.sh` has 6 checks (5 from 1-5 + 1 from 2-3). This story doesn't add a new check, only tightens the existing `/v1/cases` one.
- `cold-start-measurements.md` has a baseline row from Story 1-5. Append a new row after this story.

[Source: `2-1-case-schema-and-state-machine.md` — predecessor]
- `cases` table schema is the contract for this story's INSERT. Column order in the INSERT statement must match Story 2-1's migration exactly: `id, state, customer_metadata, assigned_to_user_id, risk_band, created_at, updated_at, closure_date`.
- `Case` Pydantic contract is `frozen=True`. Construct fixtures with `Case(...)`; can't mutate after construction.
- `CustomerMetadata.extra` is `dict[str, Any]` — accepts arbitrary keys without validation. The `ubo_chain_hint` etc. live there.
- The `ix_cases_created_at` index supports the rail's `ORDER BY created_at DESC`. The 5-minute spacing in the fixture's `created_at` values produces deterministic order.

[Source: `2-2-get-case-retrieval-api-consumer.md` — predecessor]
- `GET /v1/cases` returns `{"items": [...], ...}`. After this story, `items.length === 3` post-seed. The verify script's tightened check (AC7) relies on this.
- `GET /v1/cases/{case_id}` accepts `case_<ULID>`. The pinned fixture IDs work directly with this endpoint.

[Source: `2-3-case-appears-in-queue-rail-basic-ordering.md` — predecessor]
- The Queue Rail polls `/v1/cases` every 5s. After this story merges, the rail shows 3 rows on first paint.
- The Story 2-3 manual verification protocol (AC11) explicitly references "Shree Venkat Trading", "Vora Capital Holdings", "Ananya Iyer" as the expected names — those names land in this story.

### Demo verification protocol (operator hand-off)

```bash
# Pre-requisites: Stories 2-1, 2-2, 2-3 merged.

make lint
make test
# Expected: existing tests + new fixture tests + new seed tests all pass.

# 1. Reset and seed:
make demo-reset
# Expected: "Demo cases: case_..., case_..., case_..." printed.

# 2. SQLite eyeball:
sqlite3 ./data/cockpit.db "SELECT id, state, json_extract(customer_metadata, '\$.customer_name') FROM cases ORDER BY created_at DESC"
# Expected (top to bottom):
#   case_01HXY...|intake_scheduled|Ananya Iyer
#   case_01HXY...|intake_scheduled|Vora Capital Holdings Pvt Ltd
#   case_01HXY...|intake_scheduled|Shree Venkat Trading

# 3. API eyeball:
make dev &
sleep 5
curl -sf -H "X-Cockpit-Demo-User: dc2aaaa3-555b-4636-89d0-6047dc205220" http://localhost:8000/v1/cases | jq '.items | length'
# Expected: 3

# 4. make verify with tightened check:
make verify
# Expected: 6/6 ✓ green; the /v1/cases check finds "case_" substring in the response.

# 5. Browser eyeball (Story 2-3 dependency):
#    Open http://localhost:5173/queue
#    Expected: three rail rows in [Ananya, Vora, Shree] order, all with state badge "Intake scheduled".

# 6. Idempotency:
make seed
# Expected: "Demo cases: case_..., case_..., case_... (skipped)" — no new inserts.
sqlite3 ./data/cockpit.db "SELECT COUNT(*) FROM cases"
# Expected: 3 (not 6).

# 7. Demo reset cycle:
make demo-reset
# Expected: same three cases re-appear; queue rail in browser refreshes (within 5s) with the same three rows.

kill %1
```

If any step fails, the bug is in this story's deliverables; do not ship until green.

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (Amelia persona, bmad-dev-story workflow)

### Debug Log References

- **Skipped the `freezegun` dev dep** suggested in Subtask 1.3. `get_demo_case_fixtures(now)` accepts `now` as a parameter, so a static `_FROZEN_NOW` constant in the test module is enough — no monkey-patching needed. One fewer dep to maintain.
- **`test_verify_demo.sh` stub-server pattern.** The "empty items" failure case needs a real HTTP server returning `{"items": []}` on `/v1/cases`. Added a tiny inline Python `BaseHTTPRequestHandler` on port 18801 — same idea as a fixture but without adding pytest to a Bash test.
- **The seed's `_seed_cases` runs inside the existing `engine.begin()` transaction** (not a new transaction) so the three-table insert path stays atomic — same as the existing tenants + officers pattern.

### Completion Notes List

- AC1: `DEMO_CASE_FIXTURES` exposed via `get_demo_case_fixtures(now)` factory; ULIDs pinned in 2026-04-29 timestamp bucket; all three owned by `ANALYST_ID`, all `INTAKE_SCHEDULED`, `risk_band=None`.
- AC2: `_seed_cases` is idempotent (`INSERT OR IGNORE`), skips on missing-table, prints case IDs on success.
- AC3: `.env.example` documents `DEMO_CASE_*_ID` (operator aids only — contract is authoritative).
- AC4: Three customer profiles materialised with the exact `extra` dict shapes from the AC (Shree clean, Vora shell-UBO with multi-layer chain hint, Ananya individual with synthetic screening hit).
- AC5: 6 new pytest specs in `apps/cockpit-api/tests/test_seed_dev.py` covering insertion, idempotency, missing-table skip, JSON round-trip, ordering, and partial-state recovery.
- AC6: 7 new pytest specs in `packages/contracts/tests/test_cases.py` covering count, IDs, owner, state, ordering/spacing, JSON round-trip, and forward-compat extras.
- AC7: `verify_demo.sh` now demands `"case_"` substring; `test_verify_demo.sh` adds the empty-items assertion (4 cases pass).
- AC8: `make demo-reset` produces the three fixtures in the expected `[Ananya, Vora, Shree]` order via `created_at DESC`.
- AC9: `README.md` adds the "Three demo cases" section + updates the "What you should see" expected output.
- AC10: `make lint` clean across all 5 subprojects; `make test` 138 total green (98 py + 40 vitest).
- AC11: Cold-start measurement re-validated; warm-checkout `make seed` runs in 765 ms (well within budget). New row appended.
- AC12: No `./fixtures/uploads/` files created — the `document_refs` arrays are placeholder filenames for Epic 3.

### File List

**Modified**
- `packages/contracts/src/contracts/cases.py` — added pinned IDs + `get_demo_case_fixtures` factory
- `packages/contracts/src/contracts/__init__.py` — re-exported new symbols
- `packages/contracts/tests/test_cases.py` — 7 new fixture tests
- `apps/cockpit-api/scripts/seed_dev.py` — added `_seed_cases`, integrated into `_seed`/`main`
- `apps/cockpit-api/tests/test_seed_dev.py` — 6 new seed-cases tests
- `.env.example` — added `DEMO_CASE_*_ID` documentation block
- `tools/scripts/verify_demo.sh` — tightened `/v1/cases` check (envelope + `case_` substring)
- `tools/scripts/test_verify_demo.sh` — added empty-items stub-server assertion
- `README.md` — added "Three demo cases" subsection + updated "What you should see"
- `Documentation/implementation-artifacts/cold-start-measurements.md` — appended 2026-04-30 row
- `Documentation/implementation-artifacts/sprint-status.yaml` — story 2-4 → review

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-04-29 | Story 2.4 drafted in the demo re-scope as a new (replaces deferred 2.2/2.3/2.4 ingestion API + idempotency + presigned URLs). Three pinned fixture cases (Shree Venkat clean, Vora Capital shell-UBO, Ananya Iyer screening hit) become the demo's narrative scaffolding. Idempotent seed; tightened `make verify` to detect populated queues; README updated with "Three demo cases" subsection. |
| 2026-04-30 | Implemented all 7 tasks. 7 new contract tests + 6 new seed tests; `make lint`/`make test` all green; `verify_demo.sh` regression test 4/4. Status → review. Epic 2 complete. |
