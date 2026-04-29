# Story 1.5: Postgres tenant-schema isolation primitives

Status: ready-for-dev

## Story

As the platform,
I want `tenant_id` to be a hard isolation primitive at the database layer,
So that no query can ever cross a tenant boundary by accident (FR49).

## Acceptance Criteria

1. **AC1 — `tenants` table exists in `public` schema** after the first Alembic migration runs. Columns:
   - `id UUID PRIMARY KEY` — UUID v4, externally provisioned per architecture identifier formats.
   - `name TEXT NOT NULL`
   - `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
   - `signing_public_key TEXT NOT NULL` — Ed25519 PEM-encoded public key (per-tenant signing key per S1).
   - `idp_config_json JSONB NOT NULL` — OIDC/SAML config payload consumed by Story 1.6.
   - Indexes: `ix_tenants_name` on `name` (lowercase), unique constraint on `name`.
2. **AC2 — `apps/cockpit-api/src/cockpit_api/db/tenant_schemas.py` exposes helpers** to derive a per-tenant schema name from a tenant id and to manage tenant schemas:
   - `tenant_schema_name(tenant_id: TenantId) -> str` returning `"tenant_<short>"` where `<short>` is a deterministic, DB-safe identifier (e.g., first 12 chars of the UUID hex, lowercase, prefixed). Function is pure + injection-safe (no string interpolation that allows SQL injection — emit only via SQLAlchemy `quoted_name`).
   - `create_tenant_schema(tenant_id: TenantId)` async function that creates the per-tenant schema if it doesn't exist (`CREATE SCHEMA IF NOT EXISTS`).
   - `drop_tenant_schema(tenant_id: TenantId)` async function — used in tests and in tenant-offboarding runbook (Story 10.x); guarded behind a `confirm_phrase` argument to prevent accidental drop in app code.
3. **AC3 — Custom Ruff rule `cockpit-tenant-id-required`** is implemented as a Ruff plugin (or, if Ruff plugin support is too heavy in 2026, a separate `pre-commit` hook + Python AST checker). The rule **fails the lint check** when a function in `apps/cockpit-api/src/cockpit_api/repositories/**.py` or `services/**.py` reads or writes case data without accepting `tenant_id` as a keyword-only parameter.
4. **AC4 — Runtime guardrail: `TenantScopeError`** is raised when a SQL query is built without a `tenant_id` filter on a tenant-scoped table. Implementation:
   - `apps/cockpit-api/src/cockpit_api/db/session.py` defines an async session factory that wraps SQLAlchemy 2.0 async session with a `TenantScopedSession` adapter.
   - The adapter inspects every `select`/`update`/`delete` statement for tenant-scoped tables and raises `TenantScopeError(case_id?, tenant_id?)` if `tenant_id` filter is absent.
   - "Tenant-scoped tables" are declared in `cockpit_api.db.models` via a `__tenant_scoped__ = True` class var on the SQLAlchemy ORM base.
   - The error is logged as a security event per NFR-O6 — structured log line with `event=tenant_scope_violation`, `actor`, `route`, `tenant_id`, `request_id`. **No customer PII** in the log line per I14.
5. **AC5 — Pydantic `TenantId` typed wrapper** lives in `packages/contracts/src/contracts/ids.py`:
   - `TenantId = Annotated[UUID, Field(...)]` (UUID v4 only — validate version on parse).
   - Same module also exports `CaseId`, `OfficerId`, etc., as ULID-backed wrappers (architecture identifier formats); for **this story**, only `TenantId` is mandatory; ULID wrappers can land here but are exercised by Epic 2+.
6. **AC6 — `apps/cockpit-api/src/cockpit_api/db/models.py` defines** the SQLAlchemy ORM `Tenant` model and the abstract base `TenantScopedBase` (declares `tenant_id: Mapped[UUID]`, `__tenant_scoped__ = True`). No tenant-scoped concrete tables exist in this story (cases/ledger/etc. land later); the base is provided so subsequent stories inherit from it.
7. **AC7 — Migration is reversible**: `alembic downgrade base` cleanly drops `tenants` table and reverts to the empty pre-state.
8. **AC8 — `make migrate` (from Story 1.2) actually applies this migration** when run. `make seed` (Story 1.2) now succeeds in writing the demo tenant row (Story 1.2 had it as a graceful no-op pending this schema).
9. **AC9 — Unit tests cover**:
   - `tenant_schema_name` is deterministic, returns DB-safe identifier, rejects non-UUID input.
   - `create_tenant_schema` + `drop_tenant_schema` round-trip against an ephemeral Postgres (use `pytest-postgresql` or testcontainers).
   - `TenantScopedSession` raises `TenantScopeError` when a tenant-scoped query lacks the `tenant_id` filter.
   - Custom Ruff rule fires on a fixture function lacking `tenant_id` and is silent on a function with it.

## Tasks / Subtasks

- [ ] **Task 1 — Define `TenantId` and identifier wrappers in contracts package** (AC: #5)
  - [ ] Subtask 1.1 — Create `packages/contracts/src/contracts/ids.py`:
    ```python
    from typing import Annotated
    from uuid import UUID
    from pydantic import AfterValidator

    def _ensure_uuid_v4(v: UUID) -> UUID:
        if v.version != 4:
            raise ValueError(f"TenantId must be UUID v4, got version {v.version}")
        return v

    TenantId = Annotated[UUID, AfterValidator(_ensure_uuid_v4)]
    ```
  - [ ] Subtask 1.2 — Add ULID-backed wrappers as TODO/skeleton (full Epic 2): `CaseId`, `OfficerId`, `LedgerEntryId`, `AgentActionId`, `DocumentId`, `WebhookDeliveryId`. Each is `Annotated[str, AfterValidator(_validate_ulid_with_prefix("case_"))]` style. The validator may raise `ValueError("invalid ULID format")`. **For this story**, only `TenantId` MUST be operational; the rest can be stubs that pass-through with format checks.
  - [ ] Subtask 1.3 — Re-export from `packages/contracts/src/contracts/__init__.py`: `from .ids import TenantId`. (Other ids re-exported once their stories activate.)
  - [ ] Subtask 1.4 — Add tests in `packages/contracts/tests/test_ids.py`: valid v4 UUID parses; v1/v3/v5 UUIDs raise; non-UUID strings raise.

- [ ] **Task 2 — Create the Alembic migration for `tenants` table** (AC: #1, #7, #8)
  - [ ] Subtask 2.1 — `cd apps/cockpit-api && poetry run alembic revision -m "create_tenants_table"`. Edit the generated `migrations/versions/<rev>_create_tenants_table.py`.
  - [ ] Subtask 2.2 — `upgrade()`: create `public.tenants` with the columns from AC1. Use `sa.UUID(as_uuid=True)` for `id`, `sa.JSON(astext_type=sa.Text())` (= JSONB on Postgres) for `idp_config_json`. Add `ix_tenants_name` (lowercase functional index).
  - [ ] Subtask 2.3 — `downgrade()`: drop the table + index cleanly.
  - [ ] Subtask 2.4 — Verify: `alembic upgrade head` then `alembic downgrade base` round-trips with no errors.

- [ ] **Task 3 — Implement `tenant_schemas.py` helpers** (AC: #2)
  - [ ] Subtask 3.1 — `apps/cockpit-api/src/cockpit_api/db/tenant_schemas.py`:
    ```python
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql.elements import quoted_name
    from contracts.ids import TenantId

    SAFE_SCHEMA_PREFIX = "tenant_"

    def tenant_schema_name(tenant_id: TenantId) -> str:
        # 12 hex chars from UUID4 are 48 bits of entropy — collision-resistant for our scale (NFR-SC1: 10 analysts MVP)
        short = tenant_id.hex[:12]
        return f"{SAFE_SCHEMA_PREFIX}{short}"

    async def create_tenant_schema(session: AsyncSession, *, tenant_id: TenantId) -> None:
        name = quoted_name(tenant_schema_name(tenant_id), quote=True)
        await session.execute(text(f"CREATE SCHEMA IF NOT EXISTS {name}"))

    async def drop_tenant_schema(session: AsyncSession, *, tenant_id: TenantId, confirm_phrase: str) -> None:
        if confirm_phrase != f"yes-drop-{tenant_id}":
            raise ValueError("drop_tenant_schema requires explicit confirm_phrase")
        name = quoted_name(tenant_schema_name(tenant_id), quote=True)
        await session.execute(text(f"DROP SCHEMA IF EXISTS {name} CASCADE"))
    ```
  - [ ] Subtask 3.2 — Mark `drop_tenant_schema` with a docstring: "Used in tests and tenant-offboarding only. Never call from request handlers."
  - [ ] Subtask 3.3 — Add Ruff lint rule: `drop_tenant_schema` calls outside `tests/` and `apps/cockpit-api/src/cockpit_api/services/tenant_lifecycle.py` (placeholder for offboarding, post-MVP) are forbidden.

- [ ] **Task 4 — Implement `TenantScopedBase` and `Tenant` ORM model** (AC: #6)
  - [ ] Subtask 4.1 — `apps/cockpit-api/src/cockpit_api/db/models.py`:
    ```python
    from datetime import datetime
    from uuid import UUID
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
    from sqlalchemy import UUID as SAUUID, Text, TIMESTAMP, JSON

    class Base(DeclarativeBase):
        pass

    class TenantScopedBase(Base):
        __abstract__ = True
        __tenant_scoped__ = True
        tenant_id: Mapped[UUID] = mapped_column(SAUUID(as_uuid=True), nullable=False, index=True)

    class Tenant(Base):
        __tablename__ = "tenants"
        __tenant_scoped__ = False
        id: Mapped[UUID] = mapped_column(SAUUID(as_uuid=True), primary_key=True)
        name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
        created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
        signing_public_key: Mapped[str] = mapped_column(Text, nullable=False)
        idp_config_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    ```
  - [ ] Subtask 4.2 — Confirm `Tenant.__tenant_scoped__ = False` (the tenants table itself is the registry, not tenant-scoped).

- [ ] **Task 5 — Implement `TenantScopedSession` runtime guardrail** (AC: #4)
  - [ ] Subtask 5.1 — `apps/cockpit-api/src/cockpit_api/db/session.py`:
    ```python
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
    from sqlalchemy import event
    from sqlalchemy.sql.expression import Select, Update, Delete, Insert
    from .models import TenantScopedBase

    class TenantScopeError(Exception):
        ...

    def _statement_targets_tenant_scoped(stmt) -> bool:
        # Inspect SQLAlchemy Core/ORM stmt to find tenant-scoped tables in FROM/UPDATE/DELETE
        ...

    def _statement_filters_by_tenant_id(stmt) -> bool:
        # Walk WHERE clause for an equality on tenant_id
        ...
    ```
  - [ ] Subtask 5.2 — Hook via SQLAlchemy `before_execute` event on the async engine. For every `Select`/`Update`/`Delete` that targets a tenant-scoped table, assert `tenant_id` is in the WHERE clause; otherwise raise `TenantScopeError`.
  - [ ] Subtask 5.3 — Structured log on raise per AC4. Use `cockpit_api.observability.logging` (placeholder import — full structured logger lands in observability work; for now, plain `logging.getLogger(__name__).warning(...)` with all required fields per architecture#Communication Patterns).
  - [ ] Subtask 5.4 — Provide a test-only context manager `bypass_tenant_scope()` for fixture setup that explicitly disables the guardrail with a logged warning. Required for migrations / superuser scripts.

- [ ] **Task 6 — Implement custom Ruff rule for keyword-only `tenant_id`** (AC: #3)
  - [ ] Subtask 6.1 — Investigate whether Ruff supports custom rules in the resolved 2026 version. **If not** (Ruff custom-rule plugin support has historically been limited): implement as a separate `pre-commit` hook in Python using `ast`:
    ```python
    # tools/ci/checks/check_tenant_id_kwarg.py
    # Walks AST of files in apps/cockpit-api/src/cockpit_api/{repositories,services}/**.py
    # For each FunctionDef whose name is in {"create_*","get_*","update_*","delete_*","list_*","fetch_*"}
    # OR which has a parameter typed as a tenant-scoped ORM model:
    #   require a kw-only arg named "tenant_id" with type Annotated[UUID,...] or TenantId
    ```
  - [ ] Subtask 6.2 — Wire into `.pre-commit-config.yaml` (replacing/extending Story 1.3) and into `make lint`.
  - [ ] Subtask 6.3 — Tests in `tools/ci/checks/tests/`: positive and negative fixtures.
  - [ ] Subtask 6.4 — **Document why we use a custom hook over a Ruff plugin** in the commit message (and as an inline comment).

- [ ] **Task 7 — Update `apps/cockpit-api/scripts/seed_dev.py`** (AC: #8)
  - [ ] Subtask 7.1 — Now that `tenants` exists, write the demo tenant row idempotently. The `signing_public_key` for the demo tenant is a deterministic dev keypair (generate once at seed time using `cryptography` — `Ed25519PrivateKey.generate()`; store the **private** key in Vault Transit so subsequent stories can use it; print it OR write to a dev-only file `apps/cockpit-api/.dev-secrets/demo-tenant.pem` that's in `.gitignore`).
  - [ ] Subtask 7.2 — `idp_config_json` for the demo tenant is a placeholder OIDC config pointing at a local IdP mock — actual OIDC arrives in Story 1.6, but the field must be non-null.
  - [ ] Subtask 7.3 — Print demo tenant `id` to stdout. (Officer user row insertion lands in Story 1.6 — defer.)

- [ ] **Task 8 — Tests** (AC: #9)
  - [ ] Subtask 8.1 — `apps/cockpit-api/tests/db/test_tenant_schemas.py`:
    - `tenant_schema_name(UUID4)` returns `tenant_<12-char-hex>` matching `^tenant_[a-f0-9]{12}$`.
    - `tenant_schema_name(non-UUID)` raises (Pydantic enforces).
    - Round-trip: `create_tenant_schema → SELECT FROM information_schema.schemata → drop_tenant_schema` (against pytest-postgresql or testcontainers Postgres).
  - [ ] Subtask 8.2 — `apps/cockpit-api/tests/db/test_tenant_scope_session.py`:
    - Build a `Select` against `TenantScopedBase` subclass without `WHERE tenant_id = :x` → `TenantScopeError`.
    - Build with `WHERE tenant_id = :x` → no error.
    - Bypass context manager allows the unsafe query (logged warning).
  - [ ] Subtask 8.3 — `tools/ci/checks/tests/test_tenant_id_kwarg.py`:
    - Fixture function lacking `tenant_id` kw-only param → checker reports violation.
    - Fixture function with `tenant_id: TenantId` kw-only → checker silent.
  - [ ] Subtask 8.4 — Migration round-trip test: `pytest` fixture that runs `alembic upgrade head` then `alembic downgrade base` against an ephemeral Postgres; asserts cleanly.

## Dev Notes

### Architectural context

[Source: architecture.md#D2] — Separate Postgres schema per tenant within shared cluster (MVP); separate cluster for high-touch on-prem. **Strong logical isolation with operational simplicity.** Schema name is derived deterministically from `tenant_id`.

[Source: architecture.md#Pattern P2 — Tenant Scoping Pattern]
```python
async def fetch_case(case_id: CaseId, *, tenant_id: TenantId) -> Case:
    case = await session.execute(select(Case).where(Case.id == case_id, Case.tenant_id == tenant_id))
    if case is None: raise TenantScopeError(...)
```
**Rule:** `tenant_id` is the first non-self keyword-only argument on every function that touches data. CI lint check (custom Ruff rule) flags any data-access function lacking it. `TenantScopeError` is logged as a security event (NFR-O6).

[Source: architecture.md#Identifier Formats]
- Tenant ID: UUID v4 (externally provisioned).
- Other IDs (case, agent action, ledger, etc.): ULID with type-prefix (`case_<ULID>`).

[Source: prd.md#FR49] — All tenant data is isolated; no cross-tenant reads, writes, or queries are permitted.

### Critical pitfalls to avoid

1. **DO NOT use string interpolation to build `CREATE SCHEMA tenant_xxxx`** — even with a controlled prefix, treat the schema name as user-derived input and quote via SQLAlchemy `quoted_name`. Otherwise: SQL injection via crafted UUIDs (in theory) or future tenant-name-derived schemas.
2. **Schema-name length**: Postgres identifiers max 63 chars. `tenant_` (7) + 12 hex (12) = 19 — well under. Don't extend the suffix without re-verifying.
3. **Don't enforce `tenant_id` filter via raw SQL parsing** — that's brittle. Use SQLAlchemy's `before_execute` event with statement introspection (`stmt.column_descriptions`, `stmt.whereclause`).
4. **Migration discipline**: this story creates the FIRST real migration. Every subsequent story's migration depends on its `revision` ID. Don't touch the generated revision after this story merges.
5. **`__tenant_scoped__` is a class var, NOT a column.** Don't accidentally make it a SQLAlchemy mapped column.
6. **`Tenant` table itself is `__tenant_scoped__ = False`** — it IS the tenant registry. The runtime guardrail must short-circuit on it.
7. **`TenantScopeError` must NOT include customer PII** in its log payload. Only `tenant_id`, `route`, `request_id`, `actor` per architecture#Communication Patterns + I14.
8. **Custom Ruff rule investigation**: as of late 2025 / early 2026, Ruff's custom-rule API is stable but limited (no AST-walking custom checks via plugin without forking). **Default to a `pre-commit` hook + Python AST script** for AC3; only attempt a Ruff plugin if explicit research confirms ergonomic support.
9. **Don't auto-create a tenant schema on seed** — schema creation is a tenant-onboarding ceremony, not a side-effect. Seed only the row in `public.tenants`. Subsequent stories may add a `tenant-onboarding` runbook step that creates the schema.
10. **Round-trip the migration** before pushing — many migrations look correct on `upgrade` and silently fail to revert on `downgrade`.

### Architecture patterns relevant here

[Source: architecture.md#P2 — Tenant Scoping Pattern] — this story is the **canonical implementation** of P2. Subsequent stories that touch repositories/services MUST follow the same pattern, enforced by the custom lint rule from this story.

[Source: architecture.md#Architectural Boundaries — Data boundary] — "`repositories/*` own all SQL; nothing else touches the DB session." This story doesn't yet introduce repositories (no business tables yet), but it sets up `db/session.py` as the gateway.

[Source: architecture.md#Anti-Patterns to Refuse]
- ❌ Pydantic schemas duplicated in apps (must import from `packages/contracts/`). `TenantId` lives in `contracts.ids` and is imported into `cockpit_api.db.tenant_schemas` — never re-defined.

### Project Structure Notes

Creates:
- `packages/contracts/src/contracts/ids.py`
- `packages/contracts/tests/test_ids.py`
- `apps/cockpit-api/src/cockpit_api/db/__init__.py`
- `apps/cockpit-api/src/cockpit_api/db/models.py`
- `apps/cockpit-api/src/cockpit_api/db/session.py`
- `apps/cockpit-api/src/cockpit_api/db/tenant_schemas.py`
- `apps/cockpit-api/migrations/versions/<rev>_create_tenants_table.py`
- `apps/cockpit-api/tests/db/test_tenant_schemas.py`
- `apps/cockpit-api/tests/db/test_tenant_scope_session.py`
- `tools/ci/checks/check_tenant_id_kwarg.py`
- `tools/ci/checks/tests/test_tenant_id_kwarg.py`

Modifies:
- `apps/cockpit-api/scripts/seed_dev.py` (now actually inserts the demo tenant row).
- `.pre-commit-config.yaml` (adds the AST-checker hook).

### References

- [Source: architecture.md#D1] — PostgreSQL 16+.
- [Source: architecture.md#D2] — Separate Postgres schema per tenant.
- [Source: architecture.md#D3] — asyncpg + SQLAlchemy 2.0 async.
- [Source: architecture.md#D4] — Alembic.
- [Source: architecture.md#Pattern P2 — Tenant Scoping Pattern]
- [Source: architecture.md#Identifier Formats]
- [Source: architecture.md#Architectural Boundaries — Data boundary]
- [Source: architecture.md#Communication Patterns] — structured log fields.
- [Source: prd.md#FR49] — tenant isolation.
- [Source: prd.md#NFR-O6] — alerting on integrity violations.
- [Source: epics.md#Story 1.5: Postgres tenant-schema isolation primitives]

### Previous Story Intelligence

[Source: 1-1-bootstrap-the-polyglot-monorepo-from-the-canonical-scaffold.md]
- `packages/contracts/` is the source-of-truth Pydantic package; `cockpit-api` and `agents` consume via path-dep `poetry add --editable ../../packages/contracts`. **Do not duplicate `TenantId` in cockpit-api**.
- `apps/cockpit-api/migrations/` was scaffolded by Alembic but contains no real migrations yet. This story owns the first one.

[Source: 1-2-one-command-local-development-environment.md]
- Postgres 16 runs in `docker-compose.yml`; migrations apply via `make migrate`.
- `apps/cockpit-api/scripts/seed_dev.py` was a graceful no-op when the schema didn't exist. This story makes it operational.
- Demo tenant constants used in seed: stable UUID across re-runs.

[Source: 1-3-cicd-skeleton-with-oidc-federated-cloud-creds.md]
- `.pre-commit-config.yaml` runs Ruff/mypy on staged Python; this story adds an AST-checker hook for the `tenant_id` kw-only rule.
- CI runs `pre-commit run --all-files` as a pre-flight; the new hook gets exercised on every PR.

[Source: 1-4-adr-discipline-and-architecture-documentation-skeleton.md]
- ADR 0006 (Pluggable Adapter) and the runtime guardrail decision in this story are aligned. **Consider adding ADR `0009-tenant-scoping-runtime-guardrail.md`** in this story documenting the SQLAlchemy `before_execute`-based check (custom decision, not yet ADR'd). This is the kind of "non-trivial design decision" NFR-RI2 mandates.

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
