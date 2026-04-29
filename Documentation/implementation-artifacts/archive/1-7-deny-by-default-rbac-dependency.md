# Story 1.7: Deny-by-default RBAC dependency

Status: ready-for-dev

## Story

As the platform,
I want every API route to require an explicit role declaration,
So that protected resources fail closed by default (FR48).

## Acceptance Criteria

1. **AC1 — `Depends(require_role(...))` is the canonical role-check dependency**, callable as either `require_role("kyc_analyst")` or `require_role("kyc_analyst", resource="case", action="read")`. It runs after `require_session` (Story 1.6) and:
   - 401 + RFC 7807 if no session.
   - 403 + RFC 7807 if session role does not match.
   - Attaches a typed `Permission` object to `request.state.permission` for downstream use.
2. **AC2 — Routes lacking `Depends(require_role(...))` deny by default**: a global FastAPI dependency (registered on the application) inspects every route at startup. If a route under `/t/{tenant_id}/...` does not declare `require_role`, requests to it return **401** (NOT 403 — to be consistent with "no auth context could be established") with `type=route_role_undeclared`. Health-check routes (`GET /health`) and auth routes (`/t/{tenant_id}/login`, `/t/{tenant_id}/auth/callback`, `/t/{tenant_id}/auth/logout`) are explicit allow-list exceptions.
3. **AC3 — A typed `RoleMatrix` lives in `apps/cockpit-api/src/cockpit_api/services/rbac.py`** mirroring the PRD's six-role × ~14-resource permission matrix exactly. Roles: `kyc_analyst`, `team_lead`, `cco`, `internal_auditor`, `tenant_admin`, `api_consumer`. Resources match the PRD permission matrix verbatim (see Dev Notes for the table).
4. **AC4 — Custom Ruff (or AST hook) lint rule `cockpit-route-role-required`** warns at lint time when a `@router.get/post/put/patch/delete(...)` decorator's function does NOT declare `Depends(require_role(...))`. Allow-list path patterns: `^GET /health$`, `^GET /t/.+/login$`, `^GET /t/.+/auth/callback$`, `^POST /t/.+/auth/logout$`.
5. **AC5 — Positive + negative role tests**: `tests/services/test_rbac.py` covers at least one positive + one negative case per `(role, resource)` pair in the matrix. **This is binding** — coverage is verified by the test parametrization fixture iterating over `RoleMatrix.entries()`.
6. **AC6 — RFC 7807 403 includes `type=role_forbidden`**, `title="Insufficient role"`, `detail` listing the **role required** + the **role observed** (the latter ONLY when the user has a session — never disclosed when unauthenticated). Examples:
   ```json
   {
     "type": "https://docs.cockpit.example/errors/role_forbidden",
     "title": "Insufficient role",
     "status": 403,
     "detail": "Role 'team_lead' required; you are authenticated as 'kyc_analyst'.",
     "instance": "/t/{tenant_id}/v1/approvals",
     "tenant_id": "...",
     "request_id": "..."
   }
   ```
7. **AC7 — Attribute-based overlays are scaffolded but not yet wired** (per PRD: "Team Lead can approve only within their team's risk-threshold band"; "Analyst can write only on own assigned case"). For Epic 1, only the simple `role-only` check is enforced. The `Permission` Pydantic object exposes `attributes: dict` so future attribute checks slot in without API changes. Document this in `services/rbac.py` with a `# TODO Epic-7+: attribute-based overlays` comment.
8. **AC8 — Tenant Admin (role 5) is enforced via runbook in MVP** per PRD; the role IS in the `RoleMatrix` so API routes that gate on it (none in MVP, all hidden behind runbook scripts) work. The runbook scripts authenticate via short-lived service tokens — out of scope for THIS story; documented as Story 10.7 dependency.
9. **AC9 — Multi-role users are NOT supported in MVP** (PRD: "Single role per session"). `Session.role` is a single-value enum. If the IdP returns multiple group claims, the auth-service maps to a single canonical role — mapping config lives in `tenants.idp_config_json.role_mapping`.

## Tasks / Subtasks

- [ ] **Task 1 — Define `Role`, `Resource`, `Action`, `RoleMatrix`** (AC: #3, #9)
  - [ ] Subtask 1.1 — `packages/contracts/src/contracts/rbac.py`:
    ```python
    from enum import Enum
    from pydantic import BaseModel

    class Role(str, Enum):
        KYC_ANALYST = "kyc_analyst"
        TEAM_LEAD = "team_lead"
        CCO = "cco"
        INTERNAL_AUDITOR = "internal_auditor"
        TENANT_ADMIN = "tenant_admin"
        API_CONSUMER = "api_consumer"

    class Resource(str, Enum):
        OWN_CASE = "own_case"
        TEAM_CASE = "team_case"
        OTHER_TEAM_CASE = "other_team_case"
        CASE_DECISION_COMMIT = "case_decision_commit"
        CASE_APPROVAL_EDD = "case_approval_edd"
        AGENT_CONFIG = "agent_config"
        REASONING_TRACE = "reasoning_trace"
        AUDIT_LEDGER = "audit_ledger"
        AUDIT_LEDGER_EXPORT = "audit_ledger_export"
        PORTFOLIO_DASHBOARD = "portfolio_dashboard"
        USER_MANAGEMENT = "user_management"
        TENANT_CONFIG = "tenant_config"
        API_CASES_POST = "api_cases_post"
        API_CASES_GET = "api_cases_get"

    class Action(str, Enum):
        READ = "R"
        WRITE = "W"
        EXECUTE = "X"

    class Permission(BaseModel):
        role: Role
        resource: Resource
        action: Action
        attributes: dict = {}
    ```
  - [ ] Subtask 1.2 — Re-export from `contracts/__init__.py`.
  - [ ] Subtask 1.3 — Tests for enum membership (catch typo regressions).

- [ ] **Task 2 — Implement `services/rbac.py`** (AC: #1, #3)
  - [ ] Subtask 2.1 — `RoleMatrix` is a frozen mapping of `(Role, Resource) → set[Action]` reflecting the PRD permission table (see Dev Notes for verbatim).
  - [ ] Subtask 2.2 — `def has_permission(role: Role, resource: Resource, action: Action) -> bool` — pure function; lookup in matrix.
  - [ ] Subtask 2.3 — `def require_role(*roles: Role | str, resource: Resource | None = None, action: Action | None = None)` — returns a FastAPI dependency callable. Implementation:
    ```python
    def require_role(*allowed_roles, resource=None, action=None):
        async def _dep(session: Session = Depends(require_session)) -> Permission:
            allowed = {Role(r) if isinstance(r, str) else r for r in allowed_roles}
            if session.role not in allowed:
                raise HTTPException(403, ...) # RFC 7807
            if resource and action and not has_permission(session.role, resource, action):
                raise HTTPException(403, ...)
            return Permission(role=session.role, resource=resource, action=action)
        return _dep
    ```
  - [ ] Subtask 2.4 — Inline comments tying the matrix rows to the PRD permission-matrix table headers.

- [ ] **Task 3 — Global "deny-by-default if no role declared" guard** (AC: #2, #4)
  - [ ] Subtask 3.1 — At app startup, walk `app.routes`. For each route under `/t/{tenant_id}/...` not in the allow-list, inspect dependencies for `require_role`. If absent, register a wrapper that returns 401 + RFC 7807 `type=route_role_undeclared`.
  - [ ] Subtask 3.2 — Allow-list:
    ```python
    ROLE_DECLARATION_EXEMPT = {
        ("GET", "/health"),
        ("GET", "/t/{tenant_id}/login"),
        ("GET", "/t/{tenant_id}/auth/callback"),
        ("POST", "/t/{tenant_id}/auth/logout"),
    }
    ```
  - [ ] Subtask 3.3 — Custom AST checker (or Ruff plugin) at lint-time that scans `apps/cockpit-api/src/cockpit_api/routers/*.py` and warns on any route function whose dependency list doesn't include `require_role`.

- [ ] **Task 4 — RFC 7807 error envelopes** (AC: #6)
  - [ ] Subtask 4.1 — Extend `cockpit_api/middleware/error_handler.py` (Story 1.6) to handle the 403 case:
    - `type=role_forbidden`
    - `detail` includes role required + role observed.
    - **Do NOT include role observed when no session** — falls back to 401 path.
  - [ ] Subtask 4.2 — `type=route_role_undeclared` 401 — only emitted if the global guard is hit (which means the developer forgot a `require_role`; lint should have caught this in dev).

- [ ] **Task 5 — Tests** (AC: #5)
  - [ ] Subtask 5.1 — `tests/services/test_rbac.py`:
    - For every `(role, resource)` pair in the matrix, parametrize a positive test (action allowed → `True`) AND a negative test (action NOT allowed → `False`). The matrix is read from `RoleMatrix`; the tests are auto-generated.
    - Use `pytest.mark.parametrize` with `RoleMatrix.iter_pairs()` returning `(role, resource, allowed_actions, denied_actions)`.
  - [ ] Subtask 5.2 — `tests/integration/test_require_role.py`:
    - Build a test FastAPI app with a route protected by `Depends(require_role(Role.KYC_ANALYST))`. Send a request with a session of role `kyc_analyst` → 200. Send with `team_lead` → 403 RFC 7807. Send with no session → 401.
    - Build a test FastAPI app with a route NOT protected by `require_role`. Verify: at startup, the global guard intercepts; request returns 401 `type=route_role_undeclared`.
  - [ ] Subtask 5.3 — `tests/lint/test_route_role_required.py`: AST checker fires on a fixture router lacking `require_role`; silent on a fixture with it.

## Dev Notes

### PRD Permission Matrix (verbatim — source of truth)

[Source: prd.md#Permission Model (RBAC Matrix)]

| Resource | Analyst | Team Lead | CCO | Auditor | Admin | API Consumer |
|----------|:-------:|:---------:|:---:|:-------:|:-----:|:------------:|
| **Own case (assigned)** | R/W | R | R | R | — | — |
| **Other analysts' cases (same team)** | R | R | R | R | — | — |
| **Other teams' cases** | — | R (if lead) | R | R | — | — |
| **Case decision commit** | X | X (conditional) | — | — | — | — |
| **Case approval (EDD)** | — | X | — | — | — | — |
| **Agent configuration** | — | — | — | — | X | — |
| **Agent reasoning trace (own case)** | R | R | R | R | — | — |
| **Audit ledger (own tenant)** | R (own case) | R (team) | R (tenant) | R (tenant) | R | — |
| **Audit ledger export** | — | — | X (portfolio) | X (individual cases) | — | — |
| **Portfolio dashboard** | — | — | R | — | — | — |
| **User management** | — | — | — | — | X | — |
| **Tenant config (jurisdiction, vendor, SAR)** | — | — | — | — | X | — |
| **API: POST /v1/cases** | — | — | — | — | — | X |
| **API: GET /v1/cases/{id}** | — | — | — | — | — | X (own ingests) |

**Encode the simple cells in `RoleMatrix` for THIS story.** Conditional cells (R "if lead", X "conditional", X "portfolio", X "individual cases", X "own ingests") become attribute-based overlays in later stories — for THIS story, encode the **base** allow set and document the conditional in a code comment with `# TODO Epic-X: attribute overlay`.

### Architectural context

[Source: architecture.md#S5] — RBAC policy engine: hand-rolled FastAPI dependency over typed permission matrix in code. **No OPA/Casbin.** Matrix is small (6 roles × ~15 resources); auditable, unit-testable, no policy server.

[Source: architecture.md#A5] — RFC 7807 Problem Details for all errors.

[Source: prd.md#FR48] — RBAC enforced at both API and UI layers with deny-by-default.

[Source: prd.md#RBAC enforcement principles]:
- Deny-by-default at every layer (API, service, datastore).
- Role assertions in agent contracts (Epic 3+).
- Attribute-based overlays (Epic 5/7+).
- Segregation of duties (analyst cannot self-approve EDD).
- Break-glass (Story 10.6).
- Impersonation forbidden (single-tenant model).

### Critical pitfalls to avoid

1. **Global "deny if no role" guard MUST run AT ROUTE-RESOLUTION TIME**, not as a middleware that introspects every request. Otherwise a missed `require_role` declaration ships to prod and is only caught by audit. **Fail fast at app startup**: if any non-allowlisted route lacks `require_role`, log a critical error AND register a 401-returning wrapper.
2. **NEVER include role observed in the 401 case** (no session) — only in the 403 case (authenticated but wrong role). Otherwise auth presence leaks.
3. **DO NOT short-circuit `require_session` first**: the dependency chain matters. `require_role` depends on `require_session`. A non-authenticated request hits 401 before role evaluation.
4. **Single role per session** in MVP (PRD-locked). If the IdP returns multiple groups, **map to a single canonical role at session creation** (Story 1.6 owns the IdP-claim → role mapping). `Session.role` is `Role`, not `set[Role]`.
5. **Don't add OPA / Casbin / Cerbos** — explicitly rejected in S5. Hand-rolled is the architecture decision.
6. **`Permission.attributes`** is forward-compat only in this story. Don't write checks against attributes yet — they're future-state. But add the field so we don't churn the contract later.
7. **AST/Ruff lint rule for `require_role`**: same caveat as Story 1.5's `tenant_id` rule — Ruff custom-rule plugin support may be limited. Use a `pre-commit` Python AST hook if needed.
8. **CCO permission "Audit ledger export X (portfolio)" vs Auditor "X (individual cases)"** — these are two different attribute-conditioned versions of the same resource. Encode both as base `EXECUTE` allowed; the attribute overlay distinguishes per-case vs per-cohort. Test cases lock the contract.
9. **Tenant Admin in MVP**: API routes that would gate on Admin (`AGENT_CONFIG`, `USER_MANAGEMENT`, `TENANT_CONFIG`) DO NOT EXIST in MVP. The `RoleMatrix` includes them so when runbooks call internal services, they don't bypass authorization. Don't accidentally remove these rows because "no UI uses them yet."

### Architecture patterns relevant here

[Source: architecture.md#Architectural Boundaries — API boundary] — only `cockpit-api/routers/*` exposes HTTP. The `require_role` dependency is mounted on routers; services don't enforce role independently (they receive a typed `Permission` from the router and trust it — service-internal trust boundary).

[Source: architecture.md#Anti-Patterns to Refuse] — N/A directly to this story, but enforcement of "no untyped permissions" is the spirit.

### Project Structure Notes

Creates:
- `packages/contracts/src/contracts/rbac.py` (`Role`, `Resource`, `Action`, `Permission`)
- `apps/cockpit-api/src/cockpit_api/services/rbac.py` (`RoleMatrix`, `has_permission`, `require_role`)
- `apps/cockpit-api/tests/services/test_rbac.py`
- `apps/cockpit-api/tests/integration/test_require_role.py`
- `tools/ci/checks/check_route_role_required.py` (AST hook)
- `tools/ci/checks/tests/test_route_role_required.py`

Modifies:
- `apps/cockpit-api/src/cockpit_api/main.py` (registers global "deny-if-undeclared" startup guard).
- `apps/cockpit-api/src/cockpit_api/middleware/error_handler.py` (extend with 403 case).
- `.pre-commit-config.yaml` (add the new AST hook).

This story does NOT yet:
- Add attribute-based overlays (own-case write, conditional approval) — those come in Epic 5/7 with the relevant routes.
- Wire the cockpit-ui's role-based UI guard — that's Story 1.10.

### References

- [Source: architecture.md#S5] — hand-rolled RBAC dependency.
- [Source: architecture.md#A5] — RFC 7807.
- [Source: architecture.md#Architectural Boundaries — API boundary]
- [Source: prd.md#FR48] — deny-by-default RBAC at API + UI.
- [Source: prd.md#Permission Model (RBAC Matrix)]
- [Source: prd.md#RBAC enforcement principles]
- [Source: epics.md#Story 1.7: Deny-by-default RBAC dependency]

### Previous Story Intelligence

[Source: 1-1-bootstrap-the-polyglot-monorepo-from-the-canonical-scaffold.md]
- `packages/contracts/` is the source-of-truth for shared types. `Role`, `Resource`, `Action`, `Permission` live there — NEVER duplicated in cockpit-api.

[Source: 1-3-cicd-skeleton-with-oidc-federated-cloud-creds.md]
- Pre-commit hooks run AST checkers; the new `check_route_role_required.py` joins the chain.

[Source: 1-5-postgres-tenant-schema-isolation-primitives.md]
- The custom AST hook pattern was first introduced for `tenant_id` keyword-only enforcement. **Reuse the same hook framework** rather than authoring a separate one.

[Source: 1-6-oidc-authentication-with-cookie-session.md]
- `Session` model has `role: Role` (single value). `require_session` returns a typed `Session`. `require_role` depends on it.
- `users.role` column is a `TEXT` enum. Store as `Role.value` (string).
- Auth routes are explicit allow-list exceptions to the global "deny if no role" guard.
- RFC 7807 envelope shape is established in Story 1.6 — extend, don't redefine.
- The `Permission` and `Session` types should land in `packages/contracts/` so cockpit-ui can also enforce role-based UI guards (Story 1.10) using the SAME `Role` enum (after `make contracts` regenerates TS types).

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
