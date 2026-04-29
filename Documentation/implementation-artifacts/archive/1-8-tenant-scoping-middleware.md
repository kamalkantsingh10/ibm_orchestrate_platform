# Story 1.8: Tenant scoping middleware

Status: ready-for-dev

## Story

As the platform,
I want every authenticated request to carry an authoritative `tenant_id` from the URL path validated against the user's session,
So that tenant scoping is enforced at the API boundary (P2).

## Acceptance Criteria

1. **AC1 — `apps/cockpit-api/src/cockpit_api/middleware/tenant_scope.py` middleware** runs after `request_id` and `error_handler` middlewares (Story 1.6) but **before** the route's `Depends(require_session)`. For every request matching `/t/{tenant_id}/...`:
   - Extracts `tenant_id` from path (regex or starlette path params).
   - Validates `tenant_id` is a valid UUID v4 (using `contracts.ids.TenantId`); if not → 404 (no body that could leak).
   - Looks up the tenant in `public.tenants`; if not found → 404.
   - If the request has a session, validates `session.tenant_id == path.tenant_id`; on mismatch → 403 RFC 7807 + structured log `event=tenant_scope_violation` per NFR-O6 (architecture#Communication Patterns).
   - On all success paths: attaches `request.state.tenant_id: TenantId` for downstream dependencies.
2. **AC2 — Routes NOT under `/t/{tenant_id}/...` skip the middleware** (e.g., `GET /health`, `GET /docs`). The middleware is a no-op pass-through for non-tenant-scoped paths.
3. **AC3 — `tenant_id` not present in path on a tenant-scoped route → 404** (`type=route_not_found`, no body details about tenant existence). This is intentionally **404**, not 400, to prevent route-existence enumeration.
4. **AC4 — Mismatched `tenant_id` between path and session → 403 RFC 7807** with `type=tenant_scope_violation`. The log payload includes `path_tenant_id`, `session_tenant_id`, `actor` (user_id), `request_id`, `route`. **NO customer PII** in the log.
5. **AC5 — `Depends(get_tenant_id)` dependency** returns `request.state.tenant_id`. Used by routers/services downstream so they don't re-extract from path. Type `TenantId`. Raises `RuntimeError` (server-side bug, not a 4xx) if called on a route the middleware didn't process — defense in depth.
6. **AC6 — Performance budget**: middleware adds ≤ 5ms p95 to request latency on a request that loads + validates tenant from cache (Redis). Tenant lookups cached in Redis with key `tenant:{id}` and TTL 60 seconds; cache invalidation is manual (admin runbook for tenant updates) — acceptable in MVP since tenants change rarely.
7. **AC7 — Tests cover**:
   - Valid tenant + valid session → 200 + `request.state.tenant_id` populated.
   - Valid tenant + session mismatch → 403 `type=tenant_scope_violation`.
   - Unknown tenant id (well-formed UUID, not in DB) → 404.
   - Malformed `tenant_id` (not a UUID) → 404.
   - Tenant-scoped route with `tenant_id` missing in URL → 404.
   - Non-tenant route (`/health`) → middleware is bypassed.
   - Cache hit path is exercised (second request inside 60s does not query DB).
8. **AC8 — Custom AST/Ruff hook `cockpit-tenant-path-required`** warns at lint time when a router file declares a route under `/t/...` that does NOT include `{tenant_id}` in its path (e.g., catches accidental `/t/cases` instead of `/t/{tenant_id}/cases`).

## Tasks / Subtasks

- [ ] **Task 1 — Implement `middleware/tenant_scope.py`** (AC: #1, #2, #3, #4, #5)
  - [ ] Subtask 1.1 — Use a Starlette `BaseHTTPMiddleware` subclass. Compile a regex `^/t/(?P<tenant_id>[^/]+)(/.*)?$` to detect tenant-scoped paths.
  - [ ] Subtask 1.2 — Order: register AFTER `RequestIdMiddleware` and the RFC 7807 `ErrorHandlerMiddleware` so logged errors carry `request_id`. Register BEFORE auth-related dependencies (FastAPI `Depends` runs at route resolution; middleware runs first).
  - [ ] Subtask 1.3 — Validate `tenant_id` via `TenantId` Pydantic type — wrap `UUID(...)` parse, catch `ValueError` → 404.
  - [ ] Subtask 1.4 — Look up tenant via repository helper `tenant_repo.get_by_id(tenant_id)`. Cache hits short-circuit the DB call.
  - [ ] Subtask 1.5 — On session mismatch: structured log with `event=tenant_scope_violation`, `level=WARN`, raise 403 RFC 7807. **Do not include the legitimate session's tenant_id in the response body** — only in logs (NFR-O3 / I14 PII discipline still allows internal IDs in logs).
  - [ ] Subtask 1.6 — Set `request.state.tenant_id = tenant_id`.

- [ ] **Task 2 — Implement `repositories/tenant_repo.py`** (AC: #1, #6)
  - [ ] Subtask 2.1 — `apps/cockpit-api/src/cockpit_api/repositories/tenant_repo.py`:
    ```python
    async def get_by_id(session: AsyncSession, *, tenant_id: TenantId) -> Tenant | None:
        # Note: tenants is __tenant_scoped__ = False (registry table)
        # — TenantScopeError guardrail must allow this query.
        ...
    ```
  - [ ] Subtask 2.2 — Use SQLAlchemy 2.0 async select against `Tenant` ORM model. Bypass the `TenantScopeError` guardrail via `bypass_tenant_scope()` context manager (Story 1.5) since `tenants` is the registry, NOT a tenant-scoped table — but the guardrail's heuristic needs help.
  - [ ] Subtask 2.3 — **Important** — `tenant_repo.get_by_id` does NOT take `tenant_id` as keyword-only-arg-on-tenant-scoped-table sense; it takes the lookup id. The custom AST checker from Story 1.5 must NOT false-positive here. Add explicit `# noqa: COCKPIT-TENANT-ID-001` or extend the hook's allow-list for `tenant_repo.py`.
  - [ ] Subtask 2.4 — Redis cache layer: `cache.get(f"tenant:{id}")` → on miss, query DB, `cache.set(f"tenant:{id}", json.dumps(tenant.model_dump()), ex=60)`.

- [ ] **Task 3 — `Depends(get_tenant_id)` dependency** (AC: #5)
  - [ ] Subtask 3.1 — `apps/cockpit-api/src/cockpit_api/deps.py` adds:
    ```python
    async def get_tenant_id(request: Request) -> TenantId:
        if not hasattr(request.state, "tenant_id"):
            raise RuntimeError("tenant_scope middleware did not run for this route")
        return request.state.tenant_id
    ```
  - [ ] Subtask 3.2 — Update existing `require_session` (Story 1.6) to read `request.state.tenant_id` and validate against `session.tenant_id` — though the middleware already enforced it; this is defense-in-depth.

- [ ] **Task 4 — Custom AST hook for `/t/...` route declaration** (AC: #8)
  - [ ] Subtask 4.1 — Extend `tools/ci/checks/check_tenant_path_required.py` (mirroring Story 1.5's hook framework):
    - Walk `apps/cockpit-api/src/cockpit_api/routers/*.py` AST.
    - For each `@router.<verb>(...)` decorator, parse the path string.
    - If path starts with `/t/` and does NOT include `{tenant_id}`, emit a violation.
  - [ ] Subtask 4.2 — Tests with positive + negative fixture routers.

- [ ] **Task 5 — Wire middleware in `main.py`** (AC: #1, #2)
  - [ ] Subtask 5.1 — Order: `RequestIdMiddleware` → `ErrorHandlerMiddleware` → `TenantScopeMiddleware`. Auth-rate-limit middleware (Story 1.6) sits BEFORE tenant scope on the auth routes only — verify the chain doesn't break tenant validation on `/t/{tenant_id}/login`.
  - [ ] Subtask 5.2 — Register the middleware globally; the regex inside the middleware decides which paths are processed.

- [ ] **Task 6 — Tests** (AC: #7)
  - [ ] Subtask 6.1 — `tests/integration/test_tenant_scope.py`:
    - Fixture: seed a tenant in DB; mint a valid session for that tenant; mint another session for a different tenant.
    - Build a simple test route `GET /t/{tenant_id}/probe` → returns `{"tenant_id": str(request.state.tenant_id)}`. Protected by `require_role(Role.KYC_ANALYST)`.
    - Test cases per AC7.
  - [ ] Subtask 6.2 — `tests/integration/test_tenant_repo_cache.py`:
    - First `get_by_id` call queries DB (use SQLAlchemy `event.listen` to count queries).
    - Second call inside 60s does NOT query DB.
  - [ ] Subtask 6.3 — `tools/ci/checks/tests/test_tenant_path_required.py`: AST hook positive/negative.

## Dev Notes

### Architectural context

[Source: architecture.md#Pattern P2 — Tenant Scoping Pattern] — `tenant_id` is the first non-self keyword-only argument on every function that touches data. **The middleware is the API-layer enforcement.** The DB-layer enforcement (Story 1.5's `TenantScopedSession`) is the second line of defense.

[Source: architecture.md#A1] — `/t/{tenant_id}/v1/...` path-prefix versioning. `tenant_id` is FIRST in the path, before the version. Routes that don't start with `/t/` (health, docs, top-level auth-utility) are exempt.

[Source: architecture.md#middleware/tenant_scope.py] — explicitly named in the architecture's project tree (`apps/cockpit-api/src/cockpit_api/middleware/tenant_scope.py`).

[Source: prd.md#FR49] — All tenant data is isolated; no cross-tenant reads, writes, or queries are permitted.

[Source: prd.md#Tenant Model] — `tenant_id` in URL path validated at API gateway and every agent/tool boundary. **API gateway in MVP = our FastAPI app middleware** (no Kong/Tyk per A8).

[Source: prd.md#NFR-O6] — Alerting on cross-tenant attempts. The structured log line `event=tenant_scope_violation` is the alert source.

### Critical pitfalls to avoid

1. **Middleware order matters.** `RequestId` first (so all log lines include it), then `ErrorHandler` (so RFC 7807 wraps everything below), then `TenantScope`. Auth-rate-limit middleware sits in front of auth routes but doesn't conflict — verify by integration test.
2. **404 vs 403 disambiguation**: 
   - Malformed path / unknown tenant → **404** (no enumeration).
   - Authenticated session, mismatched tenant → **403** (the user IS authenticated; the action is forbidden).
   - Authenticated session, but tenant_id missing in path → this should never happen (lint enforces routes have `{tenant_id}` per AC8); if it does, treat as **404** since the route shouldn't exist conceptually.
3. **Redis cache stampede**: 60s TTL + many parallel requests on a cold cache hit → DB stampede. Add a small jitter to TTL (e.g., 60-90s random) or use a per-key lock (Redis SETNX). Fine in MVP at 10 analysts; scale concern for SC2.
4. **Don't cache the SQLAlchemy ORM object** — cache a serialized Pydantic representation. ORM objects bound to a session aren't safe across requests.
5. **Tenant-scope cache invalidation** on tenant update: not in MVP scope (tenants change rarely; runbook runs `redis-cli DEL tenant:<id>` after a manual change). Document this in the tenant-onboarding runbook.
6. **`request.state.tenant_id` MUST be the path tenant**, not the session tenant — they must match (validated), but the path is the authoritative source. This is so a malicious actor that bypasses the session check (lower-priority routes) still gets path-derived tenant scoping at the data layer.
7. **The `tenants` table itself**: `Tenant.__tenant_scoped__ = False` (Story 1.5). The runtime guardrail must NOT raise on `tenant_repo.get_by_id`. Verify with a unit test.
8. **Don't forget the 404 wrapping for malformed UUID**: `UUID("not-a-uuid")` raises `ValueError` — catch and 404. **Do not propagate the actual error message** — just 404 with no body.
9. **Performance**: avoid `await session.execute(select(Tenant)...)` on every request. Cache hit must be the common case. Measure latency in tests; ensure middleware adds ≤ 5 ms p95 (AC6).

### Architecture patterns relevant here

[Source: architecture.md#P2] — middleware is the API-layer impl.
[Source: architecture.md#Architectural Boundaries — Data boundary] — `repositories/tenant_repo.py` is the only place SQL touches tenants table; middleware calls into it.
[Source: architecture.md#Anti-Patterns to Refuse] — "Stale data shown as fresh (NFR-A7)" — cached tenant data is fresh-enough for MVP scope. Document the choice; if it bites, switch to event-driven invalidation (Redis pub/sub).

### Project Structure Notes

Creates:
- `apps/cockpit-api/src/cockpit_api/middleware/tenant_scope.py`
- `apps/cockpit-api/src/cockpit_api/repositories/__init__.py`
- `apps/cockpit-api/src/cockpit_api/repositories/tenant_repo.py`
- `apps/cockpit-api/tests/integration/test_tenant_scope.py`
- `apps/cockpit-api/tests/integration/test_tenant_repo_cache.py`
- `tools/ci/checks/check_tenant_path_required.py`
- `tools/ci/checks/tests/test_tenant_path_required.py`

Modifies:
- `apps/cockpit-api/src/cockpit_api/main.py` — register middleware.
- `apps/cockpit-api/src/cockpit_api/deps.py` — add `get_tenant_id` and tighten `require_session`.
- `.pre-commit-config.yaml` — add the new AST hook.
- `tools/ci/checks/check_tenant_id_kwarg.py` — extend allow-list to whitelist `tenant_repo.get_by_id` (the registry-lookup function, not a tenant-scoped data accessor).

### References

- [Source: architecture.md#Pattern P2 — Tenant Scoping Pattern]
- [Source: architecture.md#A1] — path-prefix versioning under `/t/{tenant_id}/v1/...`.
- [Source: architecture.md#A8] — no API gateway in MVP; rate limiting + tenant scoping in middleware.
- [Source: architecture.md#middleware/tenant_scope.py] — explicit file in tree.
- [Source: architecture.md#Communication Patterns] — structured log fields for security events.
- [Source: prd.md#FR49] — tenant isolation is a hard invariant.
- [Source: prd.md#Tenant Model] — tenant_id in URL path validated at API gateway.
- [Source: prd.md#NFR-O6] — alerting on tenant-scope violations.
- [Source: epics.md#Story 1.8: Tenant scoping middleware]

### Previous Story Intelligence

[Source: 1-5-postgres-tenant-schema-isolation-primitives.md]
- `TenantId` Pydantic type lives in `contracts.ids`. Import; do not redefine.
- `TenantScopedSession` raises `TenantScopeError` on missing `tenant_id` filter. The `tenants` table is `__tenant_scoped__ = False`, so registry queries pass.
- `bypass_tenant_scope()` context manager exists for legitimate cross-tenant queries (rare). Use sparingly; document each use site.

[Source: 1-6-oidc-authentication-with-cookie-session.md]
- `Session.tenant_id: TenantId` is set at session creation. The middleware reads `request.state.session.tenant_id` for comparison.
- RFC 7807 `error_handler.py` middleware exists; reuse for 403 / 404 emissions.
- `RequestIdMiddleware` exists; this story sits below it in the middleware chain.

[Source: 1-7-deny-by-default-rbac-dependency.md]
- `require_session` returns the typed `Session`; `require_role` depends on it. The tenant-scope middleware doesn't replace either — it runs FIRST and supplies `request.state.tenant_id`.
- The custom-rule AST hook framework is reused for `cockpit-tenant-path-required`.

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
