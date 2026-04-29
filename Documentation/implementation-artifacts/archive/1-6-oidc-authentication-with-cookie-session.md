# Story 1.6: OIDC authentication with cookie session

Status: ready-for-dev

## Story

As a KYC Analyst,
I want to log in using my bank's identity provider (OIDC),
So that I authenticate with credentials I already have (FR47).

## Acceptance Criteria

1. **AC1 — `GET /t/{tenant_id}/login` redirects to the tenant's IdP authorization endpoint**. The route loads `tenants.idp_config_json` for the path-supplied tenant id, builds a standards-compliant OIDC authorization URL using `authlib`, and 302-redirects. State + nonce + PKCE code-challenge are generated and stored server-side in Redis keyed by a short-lived auth-state token; the auth-state token is **also** set as an `HttpOnly`, `Secure`, `SameSite=Strict` cookie scoped to `/t/{tenant_id}/auth/`.
2. **AC2 — `GET /t/{tenant_id}/auth/callback` handles the IdP redirect**: validates state matches the auth-state cookie, validates nonce, exchanges the authorization code via PKCE, validates the ID token signature against the IdP's JWKS, validates `iss`/`aud`/`exp`/`iat` claims, maps the IdP `sub` claim to a `users` row (creating the user on first login), and creates a server-side session in Redis. Sets the session cookie. Redirects to `/t/{tenant_id}/queue` (post-login landing — UX `routes/_auth.tsx` guard owned by Story 1.10) or to a stored `redirect_uri` if the user was deep-linked.
3. **AC3 — Server-side session is stored in Redis** keyed by an opaque session token (32 random bytes, base64url-encoded). Session payload (Pydantic-validated):
   ```python
   class Session(BaseModel):
     session_id: str           # opaque token
     tenant_id: TenantId
     user_id: OfficerId        # usr_<ULID>
     idp_sub: str              # IdP subject claim (audit linkage)
     role: Role                # enum from rbac.py — single role per session in MVP
     created_at: datetime
     last_activity: datetime
   ```
   TTL refreshed on every authenticated request (Story 1.9 owns the inactivity timer; this story sets `last_activity` correctly).
4. **AC4 — Session cookie is `HttpOnly`, `Secure`, `SameSite=Strict`** with a name like `cockpit_session`. **Cookie value contains ONLY the session token** — no payload, no JWT, no encrypted blob. Attribute `Path=/t/{tenant_id}/`. `Domain` is left unset (host-only cookie). Cookie is `Secure` even in dev (Vite serves over HTTP — document the workaround: dev uses `http://localhost` with a relaxed `Secure` flag in dev mode ONLY, gated by `Settings.environment == "dev"`).
5. **AC5 — `Depends(require_session)` dependency** loads the session from Redis on each protected request and attaches `request.state.session` (Pydantic `Session`). On missing/invalid/expired token: respond with **RFC 7807 401** (`type=session_required` or `type=session_expired`), clear the cookie, do NOT redirect server-side (cockpit-ui handles redirect on 401 — coordinated with Story 1.9).
6. **AC6 — `POST /t/{tenant_id}/auth/logout` clears the session**: deletes the Redis entry, clears the cookie, returns 204. Cockpit-ui then navigates to a public sign-out page (Story 1.10 owns the page).
7. **AC7 — `users` table exists** (created by an Alembic migration in this story), columns:
   - `id UUID PRIMARY KEY` (or `TEXT` for ULID — choose ULID per architecture identifier formats: `usr_<ULID>`, store as `TEXT` to preserve prefix).
   - `tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT`
   - `idp_sub TEXT NOT NULL` — IdP `sub` claim.
   - `email TEXT NOT NULL`
   - `display_name TEXT NOT NULL`
   - `role TEXT NOT NULL` — single MVP role (one of: `kyc_analyst`, `team_lead`, `cco`, `internal_auditor`, `tenant_admin`, `api_consumer`); Story 1.7's RBAC matrix enforces.
   - `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
   - `last_login_at TIMESTAMPTZ`
   - Unique constraint `(tenant_id, idp_sub)`.
8. **AC8 — Tenant `idp_config_json` schema is defined as Pydantic** in `packages/contracts/src/contracts/tenant.py`:
   ```python
   class OidcConfig(BaseModel):
     issuer: HttpUrl
     client_id: str
     client_secret_ref: str       # secrets-client key, NOT the secret itself
     redirect_uri: HttpUrl
     scopes: list[str] = ["openid", "email", "profile"]
   ```
   Loading the secret resolves the `client_secret_ref` against the `SecretsClient` adapter (Vault dev, Secrets Manager prod) — **for THIS story**, a minimal `VaultKvSecretsClient` ships in `apps/cockpit-api/src/cockpit_api/adapters/secrets/vault_kv.py` (the broader `SecretsClient` adapter family lands in Epic 3 or wherever S2 is fully realized; this story creates the contract + dev impl).
9. **AC9 — Auth attempts are rate-limited per IP and per tenant**: 10 login attempts per IP per minute, 5 failed-callback validations per `(tenant_id, idp_sub)` per 10 minutes (NFR-S2 — account lockout). Implementation uses Redis as the counter store. **Note:** the broader API rate limit middleware is Epic 2 (Story 2.10); this story implements localized auth-only rate limiting.
10. **AC10 — Tests cover the OIDC happy path + key failure modes**:
    - Happy: redirect → callback → session created.
    - Bad state (CSRF) → 400 + RFC 7807.
    - Expired/invalid ID token → 401 + RFC 7807; no session created.
    - Missing/unknown `tenant_id` → 404 (do NOT leak tenant existence per architecture#middleware/tenant_scope.py rationale).
    - 5 failed callbacks within 10 min → subsequent callback returns 429 with `Retry-After` (NFR-S2).
    - Logout clears Redis entry and cookie.

## Tasks / Subtasks

- [ ] **Task 1 — Add Pydantic contracts** (AC: #3, #8)
  - [ ] Subtask 1.1 — `packages/contracts/src/contracts/tenant.py`: `OidcConfig`, `IdpConfig` (union for OIDC vs SAML — SAML branch is a stub; SAML lands per FR47 alternate path post-MVP if a tenant requires it per S3).
  - [ ] Subtask 1.2 — `packages/contracts/src/contracts/session.py`: `Session`, `Role` enum (six values per PRD permission matrix).
  - [ ] Subtask 1.3 — `packages/contracts/src/contracts/__init__.py` re-exports.
  - [ ] Subtask 1.4 — Tests for the contracts.

- [ ] **Task 2 — Migration: `users` table** (AC: #7)
  - [ ] Subtask 2.1 — `alembic revision -m "create_users_table"`.
  - [ ] Subtask 2.2 — `upgrade()`/`downgrade()` per AC7 schema. Add `ix_users_tenant_id_idp_sub` (unique).
  - [ ] Subtask 2.3 — Round-trip test.

- [ ] **Task 3 — `SecretsClient` minimal adapter** (AC: #8)
  - [ ] Subtask 3.1 — `packages/contracts/src/contracts/secrets.py`: `class SecretsClient(Protocol)` with `async def get_secret(self, key: str, *, tenant_id: TenantId) -> str` and `async def set_secret(self, key: str, value: str, *, tenant_id: TenantId) -> None`. Per P1, a typed Protocol.
  - [ ] Subtask 3.2 — `apps/cockpit-api/src/cockpit_api/adapters/secrets/vault_kv.py` — dev impl using HashiCorp Vault KV v2 against `localhost:8200` (the dev container from Story 1.2). Per-tenant scoping = `secret/data/tenants/{tenant_id}/{key}`.
  - [ ] Subtask 3.3 — `apps/cockpit-api/src/cockpit_api/adapters/secrets/base.py` — re-exports the Protocol from contracts.
  - [ ] Subtask 3.4 — Conformance pair: stub `mock.py` for tests (NFR-RI6 — every adapter ships with a second impl).
  - [ ] Subtask 3.5 — Conformance test in `apps/cockpit-api/tests/contract/test_secrets_contract.py` — runs the same suite against `vault_kv` and `mock`. Pre-figures the full-bore conformance pattern that lands in Epic 3.

- [ ] **Task 4 — OIDC routes + service** (AC: #1, #2, #6)
  - [ ] Subtask 4.1 — `apps/cockpit-api/src/cockpit_api/routers/auth.py`:
    - `GET /t/{tenant_id}/login` → `auth_service.start_oidc_flow(tenant_id, return_to)`.
    - `GET /t/{tenant_id}/auth/callback` → `auth_service.complete_oidc_flow(tenant_id, code, state)`.
    - `POST /t/{tenant_id}/auth/logout` → `auth_service.logout(session)`.
  - [ ] Subtask 4.2 — `apps/cockpit-api/src/cockpit_api/services/auth_service.py`:
    - Loads `OidcConfig` for tenant.
    - Resolves `client_secret_ref` via `SecretsClient`.
    - Uses `authlib.integrations.starlette_client.OAuth` (or equivalent) for OIDC flow with PKCE.
    - Stores auth-state in Redis (key `oidc:state:<token>`, TTL 10 min).
    - Maps IdP `sub` → `users` row (find or create); enforces `(tenant_id, idp_sub)` uniqueness.
    - Generates session token (32 random bytes, b64url) and stores `Session` Pydantic model in Redis (key `session:<token>`, TTL = tenant `inactivity_timeout` from Story 1.9 default 30 min).
  - [ ] Subtask 4.3 — `apps/cockpit-api/src/cockpit_api/deps.py`:
    - `async def require_session(request: Request, ...) -> Session` — raises 401 on missing/invalid/expired token.
    - `async def get_current_user(session: Session = Depends(require_session)) -> User`.

- [ ] **Task 5 — Cookie + RFC 7807 wiring** (AC: #4, #5)
  - [ ] Subtask 5.1 — Cookie helpers in `cockpit_api/services/auth_service.py`. Cookie name `cockpit_session`. Attributes per AC4. Dev `Secure` flag handled via `Settings.environment`.
  - [ ] Subtask 5.2 — Error handler middleware emits RFC 7807 (`application/problem+json`) for all 4xx/5xx — even before Epic 2 middleware is full. `apps/cockpit-api/src/cockpit_api/middleware/error_handler.py`:
    ```python
    {
      "type": "https://docs.cockpit.example/errors/session_expired",
      "title": "Session expired",
      "status": 401,
      "detail": "Your session has expired. Please sign in again.",
      "instance": "/t/{tenant}/v1/cases/{case_id}",
      "tenant_id": "...",
      "request_id": "..."
    }
    ```
  - [ ] Subtask 5.3 — `request_id` middleware (`apps/cockpit-api/src/cockpit_api/middleware/request_id.py`) — generates ULID per request, attaches to `request.state.request_id`, includes as `X-Cockpit-Request-Id` header in response.

- [ ] **Task 6 — Auth rate limiting** (AC: #9)
  - [ ] Subtask 6.1 — `apps/cockpit-api/src/cockpit_api/middleware/auth_rate_limit.py` — Redis-backed sliding-window counters scoped to login + callback endpoints only.
  - [ ] Subtask 6.2 — On exceed: 429 + RFC 7807 `Retry-After` header.
  - [ ] Subtask 6.3 — Document this is local; cross-route rate limiting is Epic 2 Story 2.10.

- [ ] **Task 7 — Update `seed_dev.py`** (AC: #7)
  - [ ] Subtask 7.1 — Insert one demo officer user `(tenant_id=demo_tenant, idp_sub="demo-officer", email="priya@demo", display_name="Priya K.", role="kyc_analyst")`. Idempotent on `(tenant_id, idp_sub)`.
  - [ ] Subtask 7.2 — Print demo user id to stdout.

- [ ] **Task 8 — Tests** (AC: #10)
  - [ ] Subtask 8.1 — `apps/cockpit-api/tests/integration/test_auth_oidc.py`:
    - Mock IdP using `respx` or a small test FastAPI app that emits OIDC discovery + JWKS + token endpoints.
    - Happy path: `GET /t/{tenant}/login` 302 to mock IdP authorize URL with state+nonce+PKCE; mock IdP redirects back to `/auth/callback`; callback exchanges code for tokens; user row created on first login; session in Redis; session cookie set.
    - Bad state → 400.
    - Expired ID token → 401 RFC 7807.
    - Unknown `tenant_id` → 404 (no body leak).
    - Logout deletes Redis + cookie.
  - [ ] Subtask 8.2 — `tests/integration/test_auth_rate_limit.py`: 5 failed callbacks → 6th returns 429.
  - [ ] Subtask 8.3 — `tests/unit/test_session_pydantic.py`: validation, serialization round-trip.

## Dev Notes

### Architectural context

[Source: architecture.md#S3] — Direct OIDC via `authlib` in FastAPI; SAML via `python3-saml` if a tenant requires it. **No Keycloak/Authentik proxy** — banks bring their own IdP; we are a relying party.

[Source: architecture.md#S4] — HttpOnly secure cookie session, server-side state in Redis. **No JWTs.** Cookies are simpler, revocable; no microservice fan-out that needs JWT statelessness.

[Source: architecture.md#S10] — `SameSite=Strict` cookies + per-mutation CSRF token. **CSRF tokens for state-changing endpoints land in a later story** (CSRF middleware in Epic 2 / Story 2.x); SameSite=Strict is sufficient for THIS story's auth flow.

[Source: architecture.md#A5] — RFC 7807 Problem Details (`application/problem+json`). Standard error format across the API.

[Source: architecture.md#API & Communication Patterns A1] — REST with `/t/{tenant_id}/v1/...` path-prefix versioning. **Auth routes are exempt from `/v1/`** by convention (login is a meta-route, not a versioned API endpoint) — verify this with the route mounting strategy.

[Source: prd.md#FR47] — OIDC / SAML SSO. SAML deferred to per-tenant requirement.

[Source: prd.md#NFR-S2] — Failed authentication attempts lock the account after 5 failures within 10 minutes. **AC9 implements this**.

[Source: prd.md#FR51 + NFR-T2] — 30-minute default inactivity timeout; configurable per tenant within [15, 60]. **Owned by Story 1.9; this story sets `last_activity` correctly so 1.9's timer works.**

### Critical pitfalls to avoid

1. **JWTs are explicitly forbidden** by S4. Cookie value carries only an opaque session token. The `Session` Pydantic model lives in **Redis**, not in the cookie.
2. **PKCE is mandatory** even though the IdP-side may not enforce it — defense in depth against code interception.
3. **Validate ID token signature against IdP JWKS** — never accept the ID token's claims without signature verification. `authlib.jose` does this; do not write your own JWT parser.
4. **State + nonce binding** — without both, you're vulnerable to CSRF (state) and replay (nonce). authlib generates these by default; verify they ARE actually bound to the auth-state cookie.
5. **`Domain=` should be unset** — host-only cookie. Setting `Domain` widens scope and risks token leakage to subdomains.
6. **`Path=/t/{tenant_id}/`** — this constrains the cookie to one tenant's path, defense-in-depth against multi-tenant collision (though host-only cookie + same hostname per tenant typically guarantees this).
7. **`Secure` in dev**: Vite serves over HTTP. Either (a) run behind a TLS-terminating reverse proxy in dev (overkill), or (b) gate `Secure` cookie attribute on `Settings.environment`. Choose (b); document why; ensure prod environments NEVER hit the dev branch.
8. **404 for unknown tenant_id** — never 401/403 — that would confirm tenant existence. (Also consistent with Story 1.8's tenant-scope middleware behavior.)
9. **Don't store the secret_ref `client_secret`** in `tenants.idp_config_json` — store a *reference* (e.g., the Vault KV path) that the SecretsClient resolves. The actual secret lives in Vault.
10. **Redis TTL semantics**: setting TTL on session create AND refreshing on every authenticated request is the correct pattern. Sliding window. Story 1.9 owns the refresh.
11. **First-login user creation race**: two concurrent first-login requests for the same `(tenant_id, idp_sub)` could both INSERT. Use `INSERT ... ON CONFLICT DO NOTHING` + then `SELECT`. Test this case explicitly.
12. **IdP discovery caching**: don't re-fetch `.well-known/openid-configuration` on every request. authlib caches by default — verify cache TTL is sane (24h is typical).
13. **Don't log the auth code or tokens** — even in DEBUG. Logs must scrub these per I14.
14. **The session payload MUST be Pydantic** — not a dict, not pickle. Forward-compat with the Session contract for SSE / RBAC.

### Architecture patterns relevant here

[Source: architecture.md#P1 — Pluggable Adapter Pattern] — `SecretsClient` is the **second adapter** (after KeyVault, which lands Epic 3). This story introduces the contract + Vault dev impl + mock conformance pair. Adheres to the architecture's "every adapter ships with a second reference implementation" rule.

[Source: architecture.md#P2 — Tenant Scoping Pattern] — every auth-route function takes `tenant_id` as a path parameter that's validated against the tenant registry. The Story 1.5 `TenantScopeError` runtime guardrail applies — every read/write against `users`, `oidc:state:*`, `session:*` is scoped to a tenant.

[Source: architecture.md#Communication Patterns] — log every auth event as structured JSON with required fields: `tenant_id`, `actor` (user_id when known, `anonymous` when not), `action` (`auth.login_started`, `auth.callback_succeeded`, `auth.callback_failed`), `level`, `request_id`, `trace_id`. **Customer PII (email) does NOT go to logs** per I14.

### Project Structure Notes

Creates:
- `packages/contracts/src/contracts/tenant.py` (`OidcConfig`, `IdpConfig`)
- `packages/contracts/src/contracts/session.py` (`Session`, `Role`)
- `packages/contracts/src/contracts/secrets.py` (`SecretsClient` Protocol)
- `apps/cockpit-api/migrations/versions/<rev>_create_users_table.py`
- `apps/cockpit-api/src/cockpit_api/routers/auth.py`
- `apps/cockpit-api/src/cockpit_api/services/auth_service.py`
- `apps/cockpit-api/src/cockpit_api/deps.py` (`require_session`, `get_current_user`)
- `apps/cockpit-api/src/cockpit_api/middleware/error_handler.py` (RFC 7807)
- `apps/cockpit-api/src/cockpit_api/middleware/request_id.py`
- `apps/cockpit-api/src/cockpit_api/middleware/auth_rate_limit.py`
- `apps/cockpit-api/src/cockpit_api/adapters/secrets/__init__.py`, `base.py`, `vault_kv.py`, `mock.py`
- `apps/cockpit-api/src/cockpit_api/db/models.py` (extends with `User` ORM model)
- `apps/cockpit-api/tests/integration/test_auth_oidc.py`
- `apps/cockpit-api/tests/integration/test_auth_rate_limit.py`
- `apps/cockpit-api/tests/contract/test_secrets_contract.py`

Modifies:
- `apps/cockpit-api/src/cockpit_api/main.py` (mount `auth` router, register middleware).
- `apps/cockpit-api/scripts/seed_dev.py` (insert demo officer user).
- `apps/cockpit-api/pyproject.toml` (add `authlib`, `httpx`, `python-multipart`).

This story does NOT yet:
- Add the `Depends(require_role(...))` dependency — that's Story 1.7's RBAC story.
- Add CSRF token middleware — deferred to Epic 2 / Story 2.x.
- Wire the cockpit-ui sign-in flow — that's Story 1.10.
- Implement session inactivity timeout logic — Story 1.9 owns the timer + auto-expiry.

### References

- [Source: architecture.md#S3] — direct OIDC via authlib.
- [Source: architecture.md#S4] — cookie session over JWT.
- [Source: architecture.md#S10] — SameSite=Strict + CSRF.
- [Source: architecture.md#A5] — RFC 7807.
- [Source: architecture.md#A1] — `/t/{tenant_id}/v1/...` path versioning.
- [Source: architecture.md#P1] — Pluggable Adapter (SecretsClient).
- [Source: architecture.md#Communication Patterns]
- [Source: prd.md#FR47] — OIDC SSO.
- [Source: prd.md#NFR-S2] — account lockout on failed auth attempts.
- [Source: prd.md#NFR-T2] — 30-min default inactivity (Story 1.9 owns).
- [Source: epics.md#Story 1.6: OIDC authentication with cookie session]

### Previous Story Intelligence

[Source: 1-1-bootstrap-the-polyglot-monorepo-from-the-canonical-scaffold.md]
- `apps/cockpit-api/src/cockpit_api/routers/`, `services/`, `middleware/`, `adapters/` directories don't exist yet — this story creates them.
- `pyproject.toml` may need `authlib`, `httpx`, etc. — add via `poetry add`.

[Source: 1-2-one-command-local-development-environment.md]
- Vault Transit runs in Docker Compose; root token `dev-root-token`. SecretsClient dev impl reads from this.
- Redis runs at `redis:6379` in compose. Session + auth-state storage uses it.

[Source: 1-3-cicd-skeleton-with-oidc-federated-cloud-creds.md]
- Gitleaks scans diffs; the OIDC client secret MUST come from Vault, not from a committed file.
- pre-commit checks Ruff/mypy strict — `auth_service.py` must pass.

[Source: 1-4-adr-discipline-and-architecture-documentation-skeleton.md]
- Consider adding ADR `0010-oidc-via-authlib-cookie-session.md` to capture the S3+S4 decisions formally as a single ADR. **The architecture covers the why; the ADR can be brief — one paragraph each on context, decision, consequences, with cross-link.**

[Source: 1-5-postgres-tenant-schema-isolation-primitives.md]
- `TenantId` lives in `contracts.ids`. Import; do not redefine.
- `tenants` table exists with `idp_config_json` column — this story populates it via `seed_dev.py`.
- `TenantScopeError` runtime guardrail applies to `users` queries — every `users` SELECT/UPDATE/DELETE MUST include `tenant_id` filter or it'll raise.
- Custom Ruff rule (or AST hook) enforces kw-only `tenant_id` on data-access functions — `auth_service.py` functions that touch `users` must comply.

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
