# Story 1.9: Session inactivity timeout

Status: ready-for-dev

## Story

As the platform,
I want sessions to expire after a configured period of inactivity,
So that abandoned sessions cannot be hijacked (FR51, NFR-T2).

## Acceptance Criteria

1. **AC1 — Default inactivity timeout is 30 minutes**, configurable per tenant within bounds **[15 min, 60 min]** (NFR-T2). Configuration lives in `tenants.idp_config_json.inactivity_timeout_seconds` (or a separate column — pick one and document; the simpler choice is to extend the existing JSON config). Default applied if absent.
2. **AC2 — Idle session is rejected with 401 RFC 7807** (`type=session_expired`, `title="Session expired"`, `detail="Sign in again to continue."`) — same envelope shape as Story 1.6's session-required error.
3. **AC3 — Expired session is deleted from Redis** when detected. (Server-side TTL is the primary expiry mechanism; the explicit DEL is a defense-in-depth cleanup if `last_activity` math says expired but Redis hasn't TTL'd yet.)
4. **AC4 — `last_activity` is refreshed on every authenticated request**: `require_session` writes `session.last_activity = utcnow()` and `EXPIRE session:<token> <timeout>` on Redis key after successful validation. **Idempotent**: refreshing on a non-mutating request (GET) is fine — that's the sliding-window contract.
5. **AC5 — Cockpit-ui handles 401 `session_expired`**: hooks/`useSessionExpiry.ts` (or interceptor at the typed `openapi-fetch` client level) catches the 401, **stores current route + UI state**, redirects to `/t/{tenant_id}/login` with `?return_to=<route>` query, and on re-auth lands the user back at the route they were on (the bank-IdP-issuer flow round-trips through `state` parameter — the `return_to` survives via Redis-side auth-state from Story 1.6).
6. **AC6 — Tenant `inactivity_timeout_seconds` is bounds-checked at write time** (admin runbook only in MVP — no UI). A helper `cockpit_api.services.tenant_lifecycle.set_inactivity_timeout(tenant_id, seconds)` rejects values outside [900, 3600]; raises `ValueError`. Used by the tenant-onboarding runbook.
7. **AC7 — Active session refreshing pattern is documented**: cockpit-ui can OPTIONALLY ping a "keepalive" endpoint (`POST /t/{tenant_id}/auth/heartbeat`) periodically when the user has the cockpit open but is, e.g., reading a long document. **For MVP**: NO automatic heartbeat — the timeout is meaningful. Timer ticks from the last *real* user request. Document the choice; revisit post-pilot if officers complain.
8. **AC8 — Tests cover**:
   - Idle past timeout → next request 401 `type=session_expired`; Redis key deleted.
   - Active request inside timeout → success; `last_activity` is updated; Redis TTL refreshed.
   - Custom per-tenant timeout (e.g., 15 min) is honored.
   - Invalid bounds (5 min, 90 min) raise at config-write time.
   - Cockpit-ui captures 401 → redirects to login with `return_to` populated.

## Tasks / Subtasks

- [ ] **Task 1 — Schema change for per-tenant timeout** (AC: #1, #6)
  - [ ] Subtask 1.1 — Decide: extend `tenants.idp_config_json` (no migration) OR add `tenants.inactivity_timeout_seconds INTEGER NOT NULL DEFAULT 1800` column (migration). **Recommendation:** add a column — it's a first-class operational setting, keeps `idp_config_json` purely for IdP config, and migration cost is low.
  - [ ] Subtask 1.2 — `alembic revision -m "add_tenants_inactivity_timeout"`. Add column with DEFAULT 1800 (30 min) NOT NULL. Round-trip `upgrade`/`downgrade` test.
  - [ ] Subtask 1.3 — Update `Tenant` ORM model + `OidcConfig` Pydantic contract — separate `inactivity_timeout_seconds: int = 1800` field on `Tenant` (not on OidcConfig, which is IdP-specific).

- [ ] **Task 2 — `services/tenant_lifecycle.py` helper** (AC: #6)
  - [ ] Subtask 2.1 — Create `apps/cockpit-api/src/cockpit_api/services/tenant_lifecycle.py`:
    ```python
    INACTIVITY_BOUNDS = (900, 3600)  # NFR-T2

    async def set_inactivity_timeout(session: AsyncSession, *, tenant_id: TenantId, seconds: int) -> None:
        lo, hi = INACTIVITY_BOUNDS
        if not (lo <= seconds <= hi):
            raise ValueError(f"inactivity_timeout must be in [{lo}, {hi}]; got {seconds}")
        await tenant_repo.update_inactivity_timeout(session, tenant_id=tenant_id, seconds=seconds)
        # Invalidate cache (Story 1.8)
        await redis.delete(f"tenant:{tenant_id}")
    ```
  - [ ] Subtask 2.2 — `repositories/tenant_repo.py` adds `update_inactivity_timeout`.
  - [ ] Subtask 2.3 — Document: this helper is invoked **only** from the tenant-onboarding runbook (Story 10.7) — there is no API route exposing it in MVP.

- [ ] **Task 3 — `require_session` refresh logic** (AC: #2, #3, #4)
  - [ ] Subtask 3.1 — Update `apps/cockpit-api/src/cockpit_api/deps.py` `require_session`:
    ```python
    async def require_session(request: Request) -> Session:
        token = request.cookies.get("cockpit_session")
        if not token: raise HTTPException(401, type="session_required", ...)
        raw = await redis.get(f"session:{token}")
        if not raw: raise HTTPException(401, type="session_expired", ...)
        session = Session.model_validate_json(raw)
        tenant = await tenant_repo.get_by_id(..., tenant_id=session.tenant_id)
        timeout = tenant.inactivity_timeout_seconds
        if (utcnow() - session.last_activity).total_seconds() > timeout:
            await redis.delete(f"session:{token}")
            raise HTTPException(401, type="session_expired", ...)
        # Refresh
        session.last_activity = utcnow()
        await redis.set(f"session:{token}", session.model_dump_json(), ex=timeout)
        request.state.session = session
        return session
    ```
  - [ ] Subtask 3.2 — Ensure RFC 7807 envelope is correctly emitted via `error_handler.py` from Story 1.6. The `type` and `detail` distinguish `session_required` (no cookie) vs `session_expired` (cookie present, server-side state gone or stale).
  - [ ] Subtask 3.3 — Atomic semantics: the read + check + write isn't atomic (no Redis transaction). Acceptable for this story; risk is a tiny race where two concurrent requests both refresh — both succeed, last write wins. **Document; revisit only if NFR-O6 alerts surface false-positives.**

- [ ] **Task 4 — Cockpit-ui 401 interceptor** (AC: #5)
  - [ ] Subtask 4.1 — `apps/cockpit-ui/src/lib/api.ts` (the typed `openapi-fetch` client wrapper from Story 2.11 — for THIS story, scaffold the wrapper if not yet present and place the 401 interceptor in it):
    ```ts
    import createClient from 'openapi-fetch';
    import type { paths } from '../api-types';

    const baseClient = createClient<paths>({ baseUrl: '/' });

    export const apiClient = {
      ...baseClient,
      // Wrap each verb to intercept 401 → session_expired
    };
    ```
    Implementation hint: wrap each method to check `response.status === 401` and `response.body.type === 'https://docs.cockpit.example/errors/session_expired'` → trigger a redirect with `return_to`.
  - [ ] Subtask 4.2 — `apps/cockpit-ui/src/hooks/useSessionExpiry.ts` is a global app-level hook that listens for 401 events and:
    1. Stores `window.location.pathname + window.location.search` to localStorage (key `cockpit:returnTo`).
    2. Navigates to `/t/${tenantId}/login?return_to=<encoded>`.
  - [ ] Subtask 4.3 — On post-login redirect (in Story 1.10's `_auth.tsx`), read `cockpit:returnTo` from localStorage and `nav(returnTo)` if present.
  - [ ] Subtask 4.4 — A toast announces "Your session expired — please sign in again" via the toast pattern from UX (UX-spec Notifications). Toast persists 4s.

- [ ] **Task 5 — `seed_dev.py` and runbook stub** (AC: #1)
  - [ ] Subtask 5.1 — `seed_dev.py` writes the demo tenant with `inactivity_timeout_seconds=1800` (default). No change to the seed flow beyond the new column.
  - [ ] Subtask 5.2 — `docs/runbooks/tenant-onboarding.md` placeholder (Story 1.4) — append a short note showing how to call `set_inactivity_timeout` (CLI invocation pattern lands properly in Story 10.7).

- [ ] **Task 6 — Tests** (AC: #8)
  - [ ] Subtask 6.1 — `tests/integration/test_session_timeout.py`:
    - Fixture: create a session with `last_activity = utcnow() - 31min`. Make a request → 401 RFC 7807 `type=session_expired`. Verify Redis key gone.
    - Fixture: create a session with `last_activity = utcnow() - 5min`. Make a request → 200. Verify Redis TTL refreshed (`TTL session:<token>` ≥ 1700).
    - Fixture: tenant with `inactivity_timeout_seconds=900`. Session at `utcnow() - 16min` → 401.
  - [ ] Subtask 6.2 — `tests/services/test_tenant_lifecycle.py`:
    - `set_inactivity_timeout(tenant_id, 600)` → `ValueError`.
    - `set_inactivity_timeout(tenant_id, 4000)` → `ValueError`.
    - `set_inactivity_timeout(tenant_id, 1800)` → success; cache invalidated.
  - [ ] Subtask 6.3 — `apps/cockpit-ui/src/lib/api.test.ts`:
    - Mock fetch to return 401 + RFC 7807 `type=session_expired`. Assert `useSessionExpiry` triggers redirect with `return_to`.

## Dev Notes

### Architectural context

[Source: prd.md#NFR-T2] — 30-minute default inactivity timeout; configurable per tenant within bounds [15 min, 60 min].

[Source: prd.md#FR51] — Platform automatically signs users out after a configurable period of inactivity.

[Source: architecture.md#S4] — HttpOnly secure cookie session, server-side state in Redis. The TTL on the Redis key is the primary timeout enforcement; the application-side `last_activity` check is defense in depth (handles cases where Redis TTL hasn't fired yet but our calculation says expired).

[Source: architecture.md#Process Patterns — Authentication failure] — "OIDC re-auth flow always returns user to the exact route they were on." This story implements the `return_to` plumbing.

### Critical pitfalls to avoid

1. **Don't mix `last_activity` math with `EXPIRE` semantics.** The Redis TTL is the *bound*; the calculated "if (now - last_activity) > timeout" is the *check*. If you only rely on TTL, fast clocks can let an expired session through; if you only rely on math, slow Redis can spam stale data. **Use both.**
2. **Heartbeat URL is intentionally NOT implemented** in MVP per AC7. If officers need to read documents for > 30 minutes, they'll re-authenticate. This is a security tradeoff explicitly accepted; add a comment and revisit after the pilot. Avoid the temptation to add a `/heartbeat` endpoint just because it's easy.
3. **`return_to` must be sanitized**: never trust the cookie or query param. Validate that `return_to` matches an allow-list of internal paths under `/t/{tenant_id}/...`. Otherwise: open redirect vulnerability.
4. **OIDC `state` round-trip vs. localStorage `return_to`**: pick ONE. The simpler approach is localStorage on the client (UI-side); the OIDC `state` parameter is already used for CSRF binding (Story 1.6). Don't overload `state` with return_to data.
5. **Race during timeout calculation**: clock skew between server, Redis, and client is small but real. Round to seconds; never use sub-second granularity for timeout decisions.
6. **Per-tenant config caching**: the tenant-scope middleware (Story 1.8) caches `Tenant` for 60s. A change to `inactivity_timeout_seconds` via runbook MUST invalidate the cache (`redis-cli DEL tenant:<id>`) — Subtask 2.1 already does this; document in runbook.
7. **Cookie `Max-Age` vs. server-side TTL**: cookie should outlive the server-side TTL so the cookie itself doesn't expire mid-flow. Set cookie `Max-Age` to `max(timeout, 3600 + buffer)` or simply make it a session cookie (no `Max-Age`/`Expires` → expires when browser closes). **Recommendation: session cookie**, leaving server-side state as the single source of truth.

### Architecture patterns relevant here

[Source: architecture.md#Process Patterns] — Authentication failure → OIDC re-auth flow always returns user to the exact route. **This story enforces that contract on the cockpit-ui side.**

[Source: architecture.md#Coherence Validation — C3] — "120-second undo timer with fail-closed Redis policy." DIFFERENT mechanism from session timeout but related: same fail-closed posture. If Redis is unreachable, treat as failure (close session) rather than allowing a permissive default.

### Project Structure Notes

Creates:
- `apps/cockpit-api/migrations/versions/<rev>_add_tenants_inactivity_timeout.py`
- `apps/cockpit-api/src/cockpit_api/services/tenant_lifecycle.py`
- `apps/cockpit-api/tests/integration/test_session_timeout.py`
- `apps/cockpit-api/tests/services/test_tenant_lifecycle.py`
- `apps/cockpit-ui/src/lib/api.ts` (interceptor wrapper — first instance; full openapi-fetch client lands fully in Story 2.11)
- `apps/cockpit-ui/src/hooks/useSessionExpiry.ts`
- `apps/cockpit-ui/src/lib/api.test.ts`

Modifies:
- `apps/cockpit-api/src/cockpit_api/db/models.py` (add `inactivity_timeout_seconds` to `Tenant`).
- `apps/cockpit-api/src/cockpit_api/deps.py` (`require_session` refresh + expired check).
- `apps/cockpit-api/src/cockpit_api/repositories/tenant_repo.py` (add `update_inactivity_timeout`).
- `apps/cockpit-api/scripts/seed_dev.py` (default value).
- `docs/runbooks/tenant-onboarding.md` (note about the helper).

### References

- [Source: prd.md#FR51]
- [Source: prd.md#NFR-T2]
- [Source: architecture.md#S4]
- [Source: architecture.md#Process Patterns — Authentication failure]
- [Source: architecture.md#Coherence Validation — C3]
- [Source: epics.md#Story 1.9: Session inactivity timeout]

### Previous Story Intelligence

[Source: 1-5-postgres-tenant-schema-isolation-primitives.md]
- Migration discipline: don't touch prior revision IDs. This story's revision depends on Story 1.6's `users` migration AND Story 1.5's `tenants` migration.

[Source: 1-6-oidc-authentication-with-cookie-session.md]
- `Session` Pydantic model has `last_activity: datetime`. This story makes that field load-bearing.
- Cookie name `cockpit_session`, opaque token, `HttpOnly`, `Secure` (env-gated), `SameSite=Strict`.
- RFC 7807 envelope shape established. Reuse, don't redefine.
- `require_session` already returns the typed `Session`; this story adds expiry math + refresh.

[Source: 1-7-deny-by-default-rbac-dependency.md]
- `require_role` depends on `require_session`. The expiry check happens BEFORE role check by chain order.

[Source: 1-8-tenant-scoping-middleware.md]
- Tenant cache invalidation pattern (`redis-cli DEL tenant:<id>`) is reused for inactivity-timeout config changes.
- Tenant-scope middleware sets `request.state.tenant_id` BEFORE `require_session` runs; `require_session` can read tenant config without a second DB lookup if needed (use the cached tenant from the middleware's lookup).

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
