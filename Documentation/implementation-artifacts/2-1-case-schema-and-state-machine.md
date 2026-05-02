# Story 2.1: Case schema and state machine

Status: review

## Story

As the platform,
I want a typed `Case` aggregate with a persisted state machine and a first real Alembic migration,
So that ingest, retrieval, queue-rail rendering, and decision flows in this Epic and downstream Epics have a canonical lifecycle to write against.

## Scope note (2026-04-29 demo re-scope)

This story is the **first real schema work** in the project — Stories 1-1 through 1-5 set up the SQLite + Alembic plumbing but committed no application tables. Original Story 2.1 (bank-buyer scope) specified a `tenant_id`-scoped Postgres schema with JSONB columns. The demo re-scope removes tenancy entirely and uses SQLite-portable types:

| Bank-buyer-scope (original 2.1) | Demo replacement in this story |
|---|---|
| Postgres + per-tenant schema isolation | **Single-tenant SQLite** — no `tenant_id` column anywhere |
| `customer_metadata JSONB` | `customer_metadata JSON` (SQLAlchemy `JSON` type — works against both dialects) |
| Postgres `ENUM` type for state | **`String` column with Pydantic-enforced enum values** (SQLite has no native ENUM; portable to Postgres if the bank-buyer scope revives) |
| Per-tenant migration runbook | **Single migration tree** under `apps/cockpit-api/migrations/versions/` (no per-tenant fan-out) |

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md` § Stack changes for demo and `architecture.md#Demo Scope Addendum (2026-04-29)`.

## Acceptance Criteria

1. **AC1 — `Case` Pydantic contract lives in `packages/contracts/src/contracts/cases.py`** and is the single source of truth for the case shape. Fields:
    - `id: CaseId` — string of form `case_<ULID>` (26-char Crockford-Base32 ULID), validated by a typed `CaseId = Annotated[str, ...]` alias
    - `state: CaseState` — `StrEnum` with values `intake_scheduled`, `decision_ready`, `committed`, `escalated`, `closed`
    - `customer_metadata: CustomerMetadata` — typed sub-model with required `customer_name: str` (min 1 char), optional `customer_type: Literal["individual", "company"] | None`, optional `country: str | None`, and an extensibility `extra: dict[str, Any]` (default `{}`) for fixture-driven demo fields without schema churn
    - `assigned_to_user_id: str | None` — references a `User.id` from `contracts.users.DEMO_USERS`; nullable
    - `risk_band: Literal["low", "medium_low", "medium_high", "high"] | None` — banded risk; nullable until Risk Scoring agent (Epic 5) populates it
    - `created_at: datetime` — UTC, ISO 8601 wire format
    - `updated_at: datetime` — UTC, ISO 8601 wire format
    - `closure_date: datetime | None` — populated when state becomes `closed`

    The model is `frozen=True` (immutable), and its `model_config` uses `use_enum_values = False` so `Role`-style enums survive round-trips. Re-export from `packages/contracts/src/contracts/__init__.py`.

2. **AC2 — `CaseState` state machine is encoded in `packages/contracts/src/contracts/cases.py`** as a module-level constant `ALLOWED_TRANSITIONS: dict[CaseState, set[CaseState]]` with these edges (and only these edges):

    ```
    intake_scheduled → decision_ready, escalated, closed
    decision_ready   → committed, escalated, closed
    committed        → closed
    escalated        → committed, closed
    closed           → (terminal)
    ```

    A pure function `assert_transition(current: CaseState, target: CaseState) -> None` raises `CaseStateTransitionError` (a custom subclass of `ValueError` defined in the same module) when the transition is not in `ALLOWED_TRANSITIONS`. The error's message includes both the source and target state names.

3. **AC3 — SQLAlchemy ORM model `Case` lives in `apps/cockpit-api/src/cockpit_api/db/models.py`** mirroring the contract column-for-column, using **dialect-portable column types**:
    - `id: Mapped[str]` — `String(32)` primary key
    - `state: Mapped[str]` — `String(32)` not-null, application-level CHECK against the `CaseState` enum (no native ENUM type)
    - `customer_metadata: Mapped[dict[str, Any]]` — `JSON` (not `JSONB`), not-null, defaults to `{}`
    - `assigned_to_user_id: Mapped[str | None]` — `String(36)`, nullable (no FK — `users` table is contract-only in the demo, no DB row)
    - `risk_band: Mapped[str | None]` — `String(16)`, nullable
    - `created_at: Mapped[datetime]` — `DateTime(timezone=True)`, not-null, default `func.now()`
    - `updated_at: Mapped[datetime]` — `DateTime(timezone=True)`, not-null, default + onupdate `func.now()`
    - `closure_date: Mapped[datetime | None]` — `DateTime(timezone=True)`, nullable

    SQLAlchemy `DeclarativeBase` is defined here as `class Base(DeclarativeBase): pass` — the project's first ORM base. Indexes: a single `ix_cases_created_at` on `created_at DESC` (used by the queue-rail ordering in Story 2-3 and the cursor-pagination convention in `architecture.md#Format Patterns`). No `tenant_id` column, no `ix_cases_tenant_id_state` (single-tenant demo).

4. **AC4 — First Alembic migration is generated and applies cleanly to fresh SQLite.** `apps/cockpit-api/migrations/env.py` is updated to point `target_metadata` at `Base.metadata` (currently `None` per the Story 1.5 scaffold). A new revision file `apps/cockpit-api/migrations/versions/<rev>_create_cases.py` is generated via `alembic revision --autogenerate -m "create cases"` and contains the `cases` table + the `ix_cases_created_at` index.

    `make migrate` against a fresh `./data/cockpit.db` produces the table; `sqlite3 ./data/cockpit.db ".schema cases"` confirms the columns. The migration is **dialect-portable** — it uses `sa.JSON()` not `postgresql.JSONB()`, `sa.String(32)` not `postgresql.UUID`, and no `gen_random_uuid()` server defaults (per `apps/cockpit-api/migrations/README` guidance from Story 1.5 pitfall #5).

5. **AC5 — `CaseRepo` is the only path that touches the `cases` table.** `apps/cockpit-api/src/cockpit_api/repositories/case_repo.py` exposes async methods:
    - `async def get(case_id: str) -> Case | None` — returns the Pydantic contract or `None`; never the ORM row
    - `async def list_ordered_by_created_at_desc(limit: int = 100) -> list[Case]` — for Story 2-3's queue rail; pure SQL `ORDER BY created_at DESC` against the index; default limit 100 keeps demo behavior bounded
    - `async def insert(case: Case) -> None` — inserts a contract-validated row; no UPSERT (idempotency was deferred per re-scope); `Case.created_at` is server-generated by the column default if the contract value is the zero datetime — but for fixture seeds (Story 2-4) the seed passes explicit timestamps to control demo ordering
    - `async def transition(case_id: str, target: CaseState) -> Case` — loads the row, calls `assert_transition(current, target)`, updates `state`, sets `closure_date = now()` if `target == CLOSED`, persists, returns the updated `Case`

    All methods take an `AsyncSession` argument (no global session). The repo translates ORM ↔ contract via a private `_to_contract(row: CaseRow) -> Case` helper. **Wire types are `Case` from `packages/contracts`; ORM rows never escape the repo** (per `architecture.md#Architectural Boundaries` Data boundary rule).

6. **AC6 — DB session plumbing lives at `apps/cockpit-api/src/cockpit_api/db/session.py`.** Exposes a FastAPI dependency `async def get_session() -> AsyncIterator[AsyncSession]` backed by a module-level `create_async_engine(settings.database_url)` and `async_sessionmaker`. Engine is created once at import (lazy on first use is fine); reads `DATABASE_URL` via a Pydantic `Settings` at `cockpit_api/config.py` (new file — `pydantic-settings` already in the FastAPI extras dep tree). Session is committed on dependency exit; rolled back on exception. Every test that touches the DB uses an in-memory SQLite engine via fixture override (see AC10).

7. **AC7 — `assert_transition` is documented in `apps/cockpit-api/migrations/README` (or a new `docs/architecture/data-flow.md` snippet)** with a state diagram. Mermaid is fine; ASCII is fine. The diagram lists every allowed edge from AC2 and is the canonical reference cited by Story 7-9 (decision outcomes) and Story 10-2 (approve-with-conditions). **Skip a separate `docs/` file** if the dev judges the README addendum sufficient — the demo prizes light docs.

8. **AC8 — Contract round-trip and migration rollback are smoke-tested.** Pytest specs in `packages/contracts/tests/test_cases.py` cover:
    - `Case` round-trips through JSON (`Case(...).model_dump_json()` → `Case.model_validate_json(...)`) preserving every field
    - `CaseId` rejects non-`case_*` prefixes and non-26-char-ULID bodies
    - `CustomerMetadata` rejects empty `customer_name`
    - `assert_transition` accepts every edge in `ALLOWED_TRANSITIONS` and raises `CaseStateTransitionError` on every disallowed pair (parametrized — at least one rejection case per source state, including the canonical `closed → intake_scheduled`)
    - Each `CaseState` value is a member of at least one allowed transition (sanity check: no orphaned states)

9. **AC9 — Repo is integration-tested against an in-memory SQLite engine.** Pytest specs in `apps/cockpit-api/tests/test_case_repo.py` cover, against a fixture that builds a fresh in-memory engine and runs `Base.metadata.create_all`:
    - `insert` then `get` round-trips a `Case` and the returned object is equal to what was inserted (modulo timestamp truncation if any)
    - `list_ordered_by_created_at_desc` returns rows in descending creation order
    - `transition(case_id, CaseState.DECISION_READY)` from `intake_scheduled` succeeds and returns the updated `Case`
    - `transition(case_id, CaseState.INTAKE_SCHEDULED)` from `closed` raises `CaseStateTransitionError`
    - `transition` to `CLOSED` populates `closure_date`
    - `get(unknown_id)` returns `None`

10. **AC10 — `make migrate` + `make test` + `make lint` all pass green.** No regression to the 44 tests + 2 bash assertions inherited from Story 1.5. The new test count adds at least: 5+ in `packages/contracts/tests/test_cases.py`, 6+ in `apps/cockpit-api/tests/test_case_repo.py`. `make lint` (Ruff + mypy strict + ESLint + Prettier) clean.

11. **AC11 — `make demo-reset` continues to work end-to-end.** The reset wipes `./data/cockpit.db`, re-runs `make migrate` (which now creates the `cases` table), re-runs `make seed` (still operates only on `tenants` + `officers` per Story 1.5 — those tables still don't exist, so the existing graceful "table not yet present" log lines remain unchanged in this story). **Story 2-4 will extend `make seed` to also seed cases — do not pre-empt that work here.**

## Tasks / Subtasks

- [x] **Task 1 — Author the `Case` contract in `packages/contracts`** (AC: #1, #2, #8)
  - [x] Subtask 1.1 — Create `packages/contracts/src/contracts/cases.py` with `CaseId` (Annotated string, ULID-shaped — accept `case_` prefix + 26 Crockford-Base32 chars; use `python-ulid` or a regex `^case_[0-9A-HJKMNP-TV-Z]{26}$`). The project doesn't currently depend on `python-ulid`; either add it (Poetry add in `packages/contracts` and `apps/cockpit-api`) OR use a regex Annotated validator and generate ULIDs with a small inline implementation. **Recommended: add `python-ulid` as a contracts dep** — it's tiny (~50 LOC), well-maintained, and Story 2-4 will need ULID generation for fixtures.
  - [x] Subtask 1.2 — Author `CaseState` as a `StrEnum` with the five values from AC2.
  - [x] Subtask 1.3 — Author `CustomerMetadata` Pydantic model with required `customer_name`, optional `customer_type` and `country`, and `extra: dict[str, Any] = {}`.
  - [x] Subtask 1.4 — Author `Case` Pydantic model with the fields from AC1; `model_config = {"frozen": True}`.
  - [x] Subtask 1.5 — Author `ALLOWED_TRANSITIONS: dict[CaseState, set[CaseState]]` and `assert_transition(current, target) -> None`. Define `class CaseStateTransitionError(ValueError)`.
  - [x] Subtask 1.6 — Re-export `Case`, `CaseState`, `CaseId`, `CustomerMetadata`, `CaseStateTransitionError`, `ALLOWED_TRANSITIONS`, `assert_transition` from `packages/contracts/src/contracts/__init__.py`.
  - [x] Subtask 1.7 — Author `packages/contracts/tests/test_cases.py` with the round-trip + transition tests from AC8. Parametrize the negative transitions exhaustively.

- [x] **Task 2 — Author the SQLAlchemy ORM + DB session** (AC: #3, #6)
  - [x] Subtask 2.1 — Create `apps/cockpit-api/src/cockpit_api/db/__init__.py`, `db/models.py`, `db/session.py`. In `models.py`, define `class Base(DeclarativeBase): pass` and `class CaseRow(Base):` with the columns from AC3 (use the `Mapped[...]` 2.0 style, not the legacy `Column(...)`).
  - [x] Subtask 2.2 — Author `cockpit_api/config.py` with a Pydantic `Settings(BaseSettings)` (from `pydantic-settings`, already a transitive dep via `fastapi[all]` — verify; add explicit dep if missing). Reads `DATABASE_URL` from env. Cache via `@lru_cache` getter `get_settings()`.
  - [x] Subtask 2.3 — Author `db/session.py` with the lazy `_engine` / `_sessionmaker` and the `get_session()` FastAPI dependency. Commit on success, rollback on exception, always close.
  - [x] Subtask 2.4 — Wire `get_session()` into `cockpit_api/main.py` only as part of router setup — **don't add a router yet for cases**; that's Story 2-2's responsibility. This story only proves the session plumbing works through the repo tests.

- [x] **Task 3 — Generate the first Alembic migration** (AC: #4, #11)
  - [x] Subtask 3.1 — Update `apps/cockpit-api/migrations/env.py`: import `from cockpit_api.db.models import Base` and set `target_metadata = Base.metadata`. Verify the import path works (the migrations dir is at `apps/cockpit-api/migrations/`, the package is at `apps/cockpit-api/src/cockpit_api/` — Alembic invocation cwd is `apps/cockpit-api/`, so `cockpit_api.db.models` resolves through the `src` layout's editable install). If the import fails, add `sys.path.insert(0, str(Path(__file__).parent.parent / "src"))` at the top of `env.py` as the canonical Alembic-with-src-layout fix.
  - [x] Subtask 3.2 — Run `cd apps/cockpit-api && DATABASE_URL='sqlite+aiosqlite:////$(pwd)/../../data/cockpit.db' poetry run alembic revision --autogenerate -m "create cases"`. **Inspect the generated revision file** before committing — autogenerate sometimes infers the wrong column types or orders. Hand-fix any `JSONB` → `JSON`, `UUID` → `String(36)`, missing index, etc.
  - [x] Subtask 3.3 — Run `make migrate` and confirm the table is created. `sqlite3 ./data/cockpit.db ".schema cases"` to eyeball the resulting DDL.
  - [x] Subtask 3.4 — Run `cd apps/cockpit-api && DATABASE_URL='...' poetry run alembic downgrade -1` to confirm the migration is reversible. Re-upgrade to head before moving on.
  - [x] Subtask 3.5 — **Add a SQLite-Postgres portability note** at the top of `apps/cockpit-api/migrations/README` (currently a one-line "Generic single-database configuration" stub). Include the rules from Story 1.5 pitfall #5: prefer `sa.JSON()` over `postgresql.JSONB()`, `sa.String(N)` over native UUID, no `gen_random_uuid()` server defaults. Future agents reading this will understand why.

- [x] **Task 4 — Author the `CaseRepo`** (AC: #5, #9)
  - [x] Subtask 4.1 — Create `apps/cockpit-api/src/cockpit_api/repositories/__init__.py` and `case_repo.py`. Methods per AC5; each takes an explicit `session: AsyncSession` argument.
  - [x] Subtask 4.2 — `_to_contract(row: CaseRow) -> Case` helper translates the ORM row to the Pydantic `Case`, parsing `customer_metadata` into a `CustomerMetadata` instance. `_to_row(case: Case) -> CaseRow` does the reverse for inserts.
  - [x] Subtask 4.3 — `transition(case_id, target)` loads the row, reads `CaseState(row.state)` (catches `ValueError` if the DB has a corrupted state value — defensive but not expected in practice), calls `assert_transition`, mutates, commits, returns the updated `Case`. Sets `closure_date = datetime.now(UTC)` only when `target == CaseState.CLOSED` and `closure_date IS NULL`.
  - [x] Subtask 4.4 — Add type hints throughout; mypy strict must pass.

- [x] **Task 5 — Repo integration tests** (AC: #9)
  - [x] Subtask 5.1 — Create `apps/cockpit-api/tests/test_case_repo.py`. Use a session-scoped pytest fixture that returns a fresh `AsyncEngine` against `sqlite+aiosqlite:///:memory:` and runs `await conn.run_sync(Base.metadata.create_all)`. Use a function-scoped session fixture to keep tests isolated.
  - [x] Subtask 5.2 — Write the six test cases from AC9. Use `pytest.mark.asyncio` (already configured via `asyncio_mode = "auto"` in `pyproject.toml`).
  - [x] Subtask 5.3 — Helper: `make_case(state=CaseState.INTAKE_SCHEDULED, **overrides) -> Case` for terse test setup. Generate distinct `case_<ULID>` ids per call.

- [x] **Task 6 — State diagram doc note** (AC: #7)
  - [x] Subtask 6.1 — Append a "Case state machine" section to `apps/cockpit-api/migrations/README` with the Mermaid diagram of allowed transitions. Cross-reference `packages/contracts/src/contracts/cases.py` as the authoritative encoding. Keep it terse — half a page max.

- [x] **Task 7 — End-to-end smoke + lint pass** (AC: #10, #11)
  - [x] Subtask 7.1 — Run `make demo-reset` end-to-end. Verify `cases` table exists post-reset; verify `make seed` still no-ops on `tenants`/`officers` with the same skip log lines.
  - [x] Subtask 7.2 — Run `make test` — all subprojects green. Run `make lint` — clean across all five subprojects.
  - [x] Subtask 7.3 — Update the `packages/contracts/tests/test_users.py`-adjacent smoke test count expectations if any test count assertions exist (none currently — verify).

## Dev Notes

### Architectural context (binding)

[Source: `architecture.md#Demo Scope Addendum (2026-04-29)` § Stack changes for demo] — SQLite is the canonical demo DB; SQLAlchemy 2.0 + Alembic stay. No `tenant_id`, no schema isolation, no asyncpg.

[Source: `architecture.md#Data Architecture` D3] — async SQLAlchemy 2.0 is the project standard. Use `Mapped[...]` 2.0 idioms, not the legacy `Column` declarative.

[Source: `architecture.md#Architectural Boundaries`] — **the data boundary is non-negotiable**: `repositories/*` own all SQL; ORM models never leave the repo; wire types are always `packages/contracts` Pydantic. This story establishes the precedent for every subsequent table.

[Source: `architecture.md#Naming Patterns`] — Postgres tables = `snake_case` plural (`cases`); column FKs = `<referenced_singular>_id` (none here — no FKs); indexes = `ix_<table>_<columns>` (`ix_cases_created_at`); JSON over the wire = `snake_case` (Pydantic models match — no humps translation).

[Source: `architecture.md#Identifier Formats`] — Case IDs are `case_<ULID>`. ULIDs are sortable (created-time-first 48 bits + 80-bit randomness in Crockford-Base32), so an `ORDER BY id` index could substitute for `ORDER BY created_at` in principle — but **the architecture mandates `ORDER BY created_at` for queue-rail rendering** to keep the cursor-pagination convention dialect-portable. Use the `created_at` index.

[Source: `architecture.md#Format Patterns`] — wire format is direct payload (no `{data: ...}` envelope); ISO 8601 dates with explicit `Z`; pagination response (later stories) is `{"items": [...], "next_cursor": "...", "has_more": bool}`.

[Source: `architecture.md#Anti-Patterns to Refuse`] — relevant subset:
- ❌ **Pydantic schemas duplicated in apps** — `Case` lives ONLY in `packages/contracts`. The cockpit-api ORM mirror is a SQL-shape, not a duplicate of the contract.
- ❌ **Silent failures** — `transition` raises explicit `CaseStateTransitionError`. Repo `get` returns `None`, not a fabricated empty case.
- ❌ **Stale data shown as fresh** — N/A here, but worth noting that Story 2-3's queue-rail polling (5s interval) is the chosen freshness budget.

### Critical pitfalls to avoid

1. **`UUID` and `JSONB` are Postgres-native — not SQLite-portable.** The Story 1.5 README addendum already flags this; this story is the first to actually generate a migration, so the rule binds here. Use `sa.String(N)` for IDs, `sa.JSON()` for JSON. The migration must apply to SQLite cleanly, AND remain re-applicable to Postgres if the bank-buyer scope is ever revived (the `sa.JSON()` type renders as `JSONB` on Postgres dialects — so portability cuts both ways for free).

2. **Don't use a native `ENUM` column type for `state`.** SQLite ignores it; Postgres creates a real type that's hell to migrate later. Use `String(32)` + Pydantic enum + `assert_transition`. The state machine lives in **Python**, not the DB.

3. **`alembic --autogenerate` is not perfect.** Always inspect the generated migration before running it. Common autogen mistakes against the demo SQLite stack: emitting `JSONB` (we want `JSON`), missing `index_property=True` on Mapped column declarations, double-creating tables when `target_metadata` references duplicated bases. Hand-edit if needed.

4. **`target_metadata = None` is the Story 1.5 placeholder.** Story 1.5 explicitly punted setting `target_metadata` to this story (per its Subtask 1.7). Without flipping it to `Base.metadata`, autogenerate produces an empty migration. Verify by running `alembic revision --autogenerate` BEFORE adding the model and confirming the generated file's `upgrade()` is empty; THEN add the model and re-run to confirm it picks up the table.

5. **`UUID` import temptation.** Resist `from sqlalchemy.dialects.postgresql import UUID` even though it might appear in autogenerate output. Replace with `sa.String(36)` or `sa.String(32)`. Document in `apps/cockpit-api/migrations/README`.

6. **`asyncio_mode = "auto"` is set in `pyproject.toml`.** Don't add `@pytest.mark.asyncio` decorators redundantly — they're inferred. Just write `async def test_...`.

7. **Don't pre-create routers/services for cases.** Story 2-2 owns `routers/cases.py` and the case service layer. This story stops at the repo. Pre-creating them now creates merge conflicts and makes Story 2-2 ambiguous.

8. **`python-ulid` vs hand-rolled ULID.** If the dev opts to skip the dep, the regex for ULID validation is `^case_[0-9A-HJKMNP-TV-Z]{26}$` (Crockford excludes I, L, O, U). Generation: `secrets.token_bytes(10).hex()` is NOT a ULID — it lacks the timestamp prefix. **Recommended: add `python-ulid` (~50 LOC, MIT-licensed)**; it's the canonical 2026 choice and Story 2-4 needs it for fixture seed IDs.

9. **`closure_date` is set ONLY on transition into `CLOSED`.** Not on `committed` (a case can be committed-but-still-open during the 120s undo window of Story 7-4) and not on `escalated` (escalation can resolve back to committed). The semantics: closure_date = "moment the case left the live workflow." If the dev disagrees, push back in the story file before implementing — but the architecture's audit-trail story (Epic 9) depends on this distinction.

10. **The `assigned_to_user_id` column has no FK.** `users` is contract-only in the demo (per Story 1.4) — there's no `users` table in SQLite. Treating this as a string FK without a real referenced row is intentional; CI lint won't flag it because there's no FK constraint to lint. Comment in the ORM model explaining this.

11. **`updated_at` `onupdate=func.now()` only fires on SQLAlchemy-ORM-mediated updates** — raw SQL `UPDATE` won't trigger it. The repo's `transition` method uses ORM, so it's fine for this story. If a future story needs to bulk-update via `Update(...)`, the dev must explicitly set `updated_at` in the `.values(...)`.

12. **In-memory SQLite engines don't share state across connections.** For repo tests, use `connect_args={"check_same_thread": False}` and a `StaticPool` if test isolation issues appear. Per pytest-asyncio defaults, function-scoped engine fixtures are safest.

### Architecture patterns relevant here

[Source: `architecture.md#Project-Specific Patterns` P2 Tenant Scoping] — **deliberately violated** in the demo. The bank-buyer rule "`tenant_id` is the first non-self keyword-only argument on every data-access function" does NOT apply here. If/when the bank-buyer scope revives, every `repositories/*` method gets a `tenant_id` parameter retrofitted; the demo just doesn't ship it.

[Source: `architecture.md#Project-Specific Patterns` P3 Provenance Metadata Pattern] — the `Case` aggregate itself does NOT carry provenance (it's a system-of-record entity, not an agent-extracted datum). Provenance attaches to fields that agents populate — `risk_band` will get a `ProvenancedField[Literal["low",...]]` wrapper later (Epic 5). For now, `risk_band` is a plain nullable string; document this distinction in the contract's docstring.

[Source: `architecture.md#Implementation Patterns & Consistency Rules` § Validation timing] — validation at the boundary, never deeper. The repo trusts that callers pass valid `Case` instances. The router (Story 2-2) is where `model_validate_json` happens. The repo's `_to_contract` builds a contract from a known-shape DB row and trusts the DB column constraints.

### Project Structure Notes

This story creates:

- `packages/contracts/src/contracts/cases.py`
- `packages/contracts/tests/test_cases.py`
- `apps/cockpit-api/src/cockpit_api/db/__init__.py`
- `apps/cockpit-api/src/cockpit_api/db/models.py`
- `apps/cockpit-api/src/cockpit_api/db/session.py`
- `apps/cockpit-api/src/cockpit_api/config.py`
- `apps/cockpit-api/src/cockpit_api/repositories/__init__.py`
- `apps/cockpit-api/src/cockpit_api/repositories/case_repo.py`
- `apps/cockpit-api/migrations/versions/<rev>_create_cases.py` (Alembic-generated, hand-corrected)
- `apps/cockpit-api/tests/test_case_repo.py`

This story modifies:

- `packages/contracts/src/contracts/__init__.py` — re-export the new symbols
- `packages/contracts/pyproject.toml` — add `python-ulid` dep (recommended) or skip (regex-only)
- `apps/cockpit-api/pyproject.toml` — add `python-ulid` if used in `case_repo.py` for default ID generation; otherwise no change
- `apps/cockpit-api/migrations/env.py` — `target_metadata = Base.metadata`; add `sys.path` shim if needed
- `apps/cockpit-api/migrations/README` — add SQLite-Postgres portability rules + state machine diagram

This story DOES NOT create:

- `apps/cockpit-api/src/cockpit_api/routers/cases.py` (Story 2-2 owns this)
- `apps/cockpit-api/src/cockpit_api/services/case_service.py` (Story 2-2 owns)
- Any frontend code (Story 2-3 owns the queue-rail render)
- Fixture cases (Story 2-4 owns the seed)
- Document, ledger, or agent-action tables (Epic 3+ own those)

### References

- [Source: `architecture.md#Demo Scope Addendum (2026-04-29)` § Stack changes for demo]
- [Source: `architecture.md#Data Architecture` D1, D3, D4]
- [Source: `architecture.md#Architectural Boundaries`] — Data boundary
- [Source: `architecture.md#Naming Patterns`] — table/column/index naming
- [Source: `architecture.md#Identifier Formats`] — ULID + `case_*` prefix
- [Source: `architecture.md#Format Patterns`] — JSON wire format, ISO 8601 dates
- [Source: `architecture.md#Anti-Patterns to Refuse`]
- [Source: `architecture.md#Project Structure & Boundaries` § Complete Project Tree] — repo + ORM + DB session locations
- [Source: `epics.md#Epic 2 — Case Ingest & Lifecycle` § Story 2.1] — original AC (re-scoped here)
- [Source: `prd.md#FR42, FR45`] — case schema and lifecycle FRs (FR42 ingest deferred per re-scope; FR45 retrieval kept and lands in Story 2-2)
- [Source: `1-5-fresh-clone-to-running-demo-in-sixty-minutes.md` Pitfall #5] — dialect-portable migration types

### Previous Story Intelligence

[Source: `1-1-bootstrap-the-polyglot-monorepo-from-the-canonical-scaffold.md`]
- Naming locked: `apps/cockpit-api/src/cockpit_api/`. New subpackages (`db/`, `repositories/`) live under `cockpit_api/`.
- pnpm and Poetry only. New deps (`python-ulid`) go through `poetry add` in the right subproject's directory.
- `packages/contracts` is consumed by `apps/cockpit-api` and `apps/agents` via path-dep editable install. New contract symbols are immediately importable from cockpit-api as `from contracts.cases import ...` after a contracts edit (no re-install needed for editable installs, but if mypy resists, run `cd apps/cockpit-api && poetry install --no-root` to refresh).

[Source: `1-2-one-command-local-development-environment.md`]
- `make migrate` and `make seed` exist; this story's migration plugs into the existing `make migrate` flow without changes to the Makefile.
- `pre-commit` runs Ruff + mypy + ESLint on staged files. Run hooks locally before pushing to avoid CI churn.

[Source: `1-3-cicd-skeleton-with-oidc-federated-cloud-creds.md`]
- CI's `lint-and-test` job runs `make lint` and `make test` against every PR. Missing migrations or schema/contract drift will be caught.
- `actionlint` lints workflow YAML; this story does not touch CI workflows.

[Source: `1-4-cockpit-shell-with-user-switcher-three-hardcoded-roles.md`]
- `User.id` is a UUID v4 string in the contract (`packages/contracts/src/contracts/users.py`). The `assigned_to_user_id` column on `cases` references this string format (`String(36)`) but has no DB FK because there's no `users` table in the demo (users are contract-only). Document the convention in the column's ORM-model comment.

[Source: `1-5-fresh-clone-to-running-demo-in-sixty-minutes.md`]
- **Critical handoff:** Story 1.5 set `target_metadata = None` in `migrations/env.py` and explicitly noted that Story 2-1 owns the first real migration (Subtask 1.7). This story flips that switch.
- `apps/cockpit-api/migrations/README` was hand-edited to a one-line stub by Alembic init. This story extends it with portability rules (per Pitfall #5) and the state diagram (AC7).
- `seed_dev.py`'s graceful "table not present" log lines for `tenants` and `officers` remain intact — those tables are still not part of this story. **Don't accidentally remove the skip handling**; Story 2-4 will tackle the seed for cases separately.
- `make demo-reset` runs `migrate` then `seed`. After this story lands, `migrate` creates the `cases` table; `seed` continues to skip `tenants`/`officers` (still missing) and does not yet seed cases.
- Test count expectation: 44 tests + 2 bash assertions before this story. After: at minimum 44 + 5 (new contract tests) + 6 (new repo tests) = 55 + 2 bash assertions. Update story 1-5's count in any forward-looking ledger if it gets cited downstream.

### Demo verification protocol (operator hand-off)

```bash
# After implementing, the dev must verify:

# 1. Fresh DB has the cases table:
make demo-reset
sqlite3 ./data/cockpit.db ".schema cases"
# Expected: CREATE TABLE cases (...) with columns from AC3 + ix_cases_created_at index.

# 2. Migration is reversible:
cd apps/cockpit-api
DATABASE_URL='sqlite+aiosqlite:////$(pwd)/../../data/cockpit.db' poetry run alembic downgrade -1
sqlite3 ../../data/cockpit.db ".schema cases"
# Expected: empty (table dropped).
DATABASE_URL='sqlite+aiosqlite:////$(pwd)/../../data/cockpit.db' poetry run alembic upgrade head
# Expected: cases table back.

# 3. Lint + test green from repo root:
cd ../..
make lint
make test
# Expected: all subprojects pass; new contract + repo tests visible in pytest output.

# 4. State machine quick eyeball:
poetry run python -c "
from contracts.cases import CaseState, assert_transition, CaseStateTransitionError
assert_transition(CaseState.INTAKE_SCHEDULED, CaseState.DECISION_READY)  # ok
try:
    assert_transition(CaseState.CLOSED, CaseState.INTAKE_SCHEDULED)
except CaseStateTransitionError as e:
    print('Rejected closed→intake_scheduled:', e)
"
# Expected: 'Rejected closed→intake_scheduled: ...'.
```

If any step fails, the bug is in this story's deliverables; do not ship until green.

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (Amelia persona, bmad-dev-story workflow)

### Debug Log References

- SQLite drops `tzinfo` on `DATETIME` round-trip; `CaseRepo._ensure_utc` re-attaches UTC so the wire format stays compliant with AC1 ("UTC, ISO 8601"). Postgres `timestamptz` round-trips natively, so the helper is a no-op there.
- Alembic autogenerate behaved correctly against the SQLite stack — emitted `sa.JSON()` and `sa.String(N)` rather than the Postgres natives we were watching for.
- `target_metadata = None` in `migrations/env.py` is now `Base.metadata`; added a `sys.path` shim so the import works from the Alembic invocation cwd regardless of editable-install state.

### Completion Notes List

- AC1: `Case` Pydantic contract authored at `packages/contracts/src/contracts/cases.py`; frozen, `use_enum_values=False`, all 8 fields per spec.
- AC2: `ALLOWED_TRANSITIONS` encodes the exact 8 allowed edges; `assert_transition` raises `CaseStateTransitionError` with both state names in the message.
- AC3: `CaseRow` ORM model uses dialect-portable types (`String(N)`, `JSON`, `DateTime(timezone=True)`); single `ix_cases_created_at` index.
- AC4: First Alembic revision `639bd74d07e4_create_cases.py` autogenerated, hand-polished for ruff. Reversible via `alembic downgrade -1` then re-`upgrade head`. `target_metadata` flipped from `None` to `Base.metadata`.
- AC5: `CaseRepo` exposes `get` / `list_ordered_by_created_at_desc` / `insert` / `transition` — each takes an explicit `AsyncSession`. `_to_contract` / `_to_row` helpers keep the ORM out of the wire.
- AC6: `db/session.py` exposes `get_session` FastAPI dependency with commit-on-success / rollback-on-exception lifecycle, lazy engine. `config.py` loads `DATABASE_URL` via `pydantic-settings`.
- AC7: Mermaid + ASCII state diagrams added to `apps/cockpit-api/migrations/README` alongside the SQLite-Postgres portability rules.
- AC8: 41 contract tests (round-trip, ID validation, state machine, terminal-state sanity).
- AC9: 6 repo integration tests against in-memory SQLite — all green.
- AC10: `make test` 74 Python tests + 15 vitest tests, all green; `make lint` clean across all five subprojects.
- AC11: `make demo-reset` end-to-end verified — creates the `cases` table, then re-runs `make seed` which gracefully skips the still-missing `tenants` / `officers` tables with the same log lines.

### File List

**Created**
- `packages/contracts/src/contracts/cases.py`
- `packages/contracts/tests/test_cases.py`
- `apps/cockpit-api/src/cockpit_api/db/__init__.py`
- `apps/cockpit-api/src/cockpit_api/db/models.py`
- `apps/cockpit-api/src/cockpit_api/db/session.py`
- `apps/cockpit-api/src/cockpit_api/config.py`
- `apps/cockpit-api/src/cockpit_api/repositories/__init__.py`
- `apps/cockpit-api/src/cockpit_api/repositories/case_repo.py`
- `apps/cockpit-api/migrations/versions/639bd74d07e4_create_cases.py`
- `apps/cockpit-api/tests/test_case_repo.py`

**Modified**
- `packages/contracts/src/contracts/__init__.py` — re-export new symbols
- `packages/contracts/pyproject.toml` + `poetry.lock` — added `python-ulid ^3.0.0`
- `apps/cockpit-api/pyproject.toml` + `poetry.lock` — added `python-ulid ^3.0.0`
- `apps/cockpit-api/migrations/env.py` — `target_metadata = Base.metadata` + `sys.path` shim
- `apps/cockpit-api/migrations/README` — portability rules + state diagrams
- `Documentation/implementation-artifacts/sprint-status.yaml` — story 2-1 → review

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-04-29 | Story 2.1 drafted in the demo re-scope. Removes tenancy + JSONB + native ENUM in favor of single-tenant SQLite + `JSON` + Python-side state machine. First real Alembic migration. Establishes the contract-mirrors-ORM-via-repo precedent for subsequent tables. |
| 2026-04-30 | Implemented all 7 tasks. 41 new contract tests + 6 new repo tests; `make lint`/`make test`/`make demo-reset` all green. Status → review. |
