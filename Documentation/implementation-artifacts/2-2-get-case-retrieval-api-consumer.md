# Story 2.2: GET case retrieval (API + consumer)

Status: review

## Story

As the cockpit-ui (the only API consumer in the demo),
I want to fetch a single case by ID via an authenticated REST endpoint that returns the Pydantic-serialized `Case` payload,
So that Story 2-3's Queue Rail row can route into a Case Canvas and downstream Epics 3+ can render real case data.

## Scope note (2026-04-29 demo re-scope)

The original Story 2.5 (renumbered to 2-2 in the re-scope) targeted bank-buyer integration developers consuming an external REST API with multi-tenant scoping, ingest-author authorization, and `_links` to documents/reasoning-traces. The demo has no external API consumer — the **cockpit-ui is the only client** — so the AC simplifies:

| Bank-buyer-scope (original 2.5) | Demo replacement in this story |
|---|---|
| `GET /t/{tenant_id}/v1/cases/{case_id}` (path-prefixed multi-tenant) | `GET /v1/cases/{case_id}` — single-tenant, no `tenant_id` segment |
| Auth: API key + tenant scope check | Auth: `X-Cockpit-Demo-User` header (Story 1-4 dep) — any of the 3 demo users may read any case |
| Ingest-author scoping ("can only read cases I created") | Removed — single-tenant demo, all users see all cases |
| `_links` to documents + reasoning traces | **Empty `_links: {}` placeholder** — documents land in Epic 3, reasoning traces in Epic 6. Don't fabricate links to endpoints that don't exist. |
| 404 on cross-tenant access (don't leak existence) | Plain 404 on unknown ID — single tenant, no leak risk |

This story **also lands the list endpoint stub** that Story 2-3 fills out, because keeping the cockpit-api router and the openapi-fetch typed client in sync inside a single story is cleaner than splitting it. (See AC8 — list endpoint scope is intentionally minimal and Story 2-3 layers ordering + UI on top.)

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md` § Stack changes for demo and `architecture.md#Demo Scope Addendum (2026-04-29)`.

## Acceptance Criteria

1. **AC1 — `GET /v1/cases/{case_id}` returns the Pydantic-serialized `Case` payload** with HTTP 200. Response shape is the direct `Case` JSON from `packages/contracts/src/contracts/cases.py` (no envelope, per `architecture.md#Format Patterns`). Wire format is `snake_case`, ISO 8601 UTC dates with `Z`. `_links` is included as `_links: {"documents": null, "reasoning_traces": null}` to reserve the shape for later Epics — both keys present, both `null` for now. The router uses `response_model=CaseEnvelope` where `CaseEnvelope = Case` extended with the `_links` dict.

2. **AC2 — `GET /v1/cases/{case_id}` returns RFC 7807 problem JSON on errors:**
    - **404 Not Found** with `{"type": "about:blank", "title": "Not Found", "status": 404, "detail": "Case <case_id> not found", "instance": "/v1/cases/<case_id>"}` when the ID does not exist
    - **422 Unprocessable Entity** when the `case_id` path param does not match the `case_<ULID>` shape — FastAPI's path validation handles this automatically given a typed Annotated path parameter
    - **400 Bad Request** when `X-Cockpit-Demo-User` header is missing or unknown — re-uses the existing `get_current_user` dependency (Story 1-4)

    The error response uses `application/problem+json` content type. Add a single `RFC7807Error` Pydantic model in `cockpit_api/errors.py` (new file) and wire a FastAPI `exception_handler(HTTPException)` in `main.py` that maps `HTTPException(status_code, detail)` → RFC 7807 envelope.

3. **AC3 — `GET /v1/cases` returns a list of cases** ordered by `created_at DESC`. Response shape is `{"items": [Case, ...], "next_cursor": null, "has_more": false}` per `architecture.md#Format Patterns` § Pagination response. Default limit 100. **No real cursor pagination yet** — the demo has 3 fixture cases (Story 2-4); pagination is forward-compat scaffolding. `next_cursor` is always `null` and `has_more` is always `false` in this story. Story 2-3 adds the queue-rail UI; Epic 4 may add cursor pagination if the demo grows past 100 cases (it won't).

4. **AC4 — The cases router is registered at `apps/cockpit-api/src/cockpit_api/routers/cases.py`** and included in `cockpit_api/main.py` alongside the existing `users` router. Prefix `/v1/cases`, tag `"cases"`. Routes:
    - `GET ""` (resolves to `/v1/cases`) — list
    - `GET "/{case_id}"` (resolves to `/v1/cases/{case_id}`) — get one

    Both routes depend on `get_current_user` (Story 1-4 dependency) — any of the three demo users may call. The router does NOT directly touch SQL; it goes through the service layer (AC5).

5. **AC5 — A thin `case_service.py` lives at `apps/cockpit-api/src/cockpit_api/services/case_service.py`** with two methods:
    - `async def get_case(session: AsyncSession, case_id: str) -> Case` — calls `case_repo.get(...)`; raises `HTTPException(404, ...)` on `None` (architecture's "fail loudly" anti-pattern; the router catches via the RFC 7807 handler)
    - `async def list_cases(session: AsyncSession, limit: int = 100) -> list[Case]` — calls `case_repo.list_ordered_by_created_at_desc(limit)`

    The service is intentionally thin in this story — orchestration grows in Story 2-3 (queue ordering hooks) and Epic 3+ (agent invocation). Establishing the layer here keeps the router free of repo imports (per `architecture.md#Architectural Boundaries` Agent boundary rule applied transitively).

6. **AC6 — The `make contracts` pipeline regenerates `apps/cockpit-ui/src/api-types.ts`** from the live OpenAPI spec. Story 1-4 left the `make contracts` Makefile target as a TODO stub (`@echo "TODO: openapi export — Story 2.11"`). This story fills it in:
    - Boot `cockpit-api` long enough to dump `/openapi.json` to `packages/contracts/openapi.json` (committed)
    - Run `pnpm dlx openapi-typescript packages/contracts/openapi.json -o apps/cockpit-ui/src/api-types.ts` to regenerate the TS shadow

    `make contracts` runs cleanly in CI without a running server by using `python -c "from cockpit_api.main import app; import json; print(json.dumps(app.openapi()))"` — no uvicorn boot needed. The generated `api-types.ts` is committed; CI fails on drift (subtask 4 of `1-3-cicd-skeleton-with-oidc-federated-cloud-creds.md` already wired actionlint; drift detection is added here as `git diff --exit-code packages/contracts/openapi.json apps/cockpit-ui/src/api-types.ts` after `make contracts`).

7. **AC7 — `apps/cockpit-ui/src/lib/api.ts` is upgraded from a hand-rolled stub to `openapi-fetch`** (per `architecture.md#Frontend Architecture` F13). The client:
    - Reads `X-Cockpit-Demo-User` from the Zustand `currentUser` store on every request
    - Has base URL `import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"` (matches the existing Story 1-4 `apiFetch` env var name)
    - Exposes typed methods via the generated `paths` type: `apiClient.GET("/v1/cases/{case_id}", { params: { path: { case_id } } })` returns a typed envelope
    - The hand-authored `apps/cockpit-ui/src/lib/types/user.ts` from Story 1-4 (with its `// TODO: replace with generated contracts once Story 2.11 lands` comment) is **deleted in this story** — generated types replace it

8. **AC8 — A `useCase(case_id)` TanStack Query hook lives at `apps/cockpit-ui/src/hooks/useCase.ts`** wrapping `apiClient.GET("/v1/cases/{case_id}", ...)`. Returns `{ data: Case | undefined, isPending, isError, error }`. `staleTime: 5_000` (5 seconds — matches Story 2-3's Queue Rail polling cadence). **No `useCases()` list hook in this story** — Story 2-3 owns it. AC8 covers only the single-case hook so the typed-client wiring is exercised end-to-end.

9. **AC9 — Pytest specs in `apps/cockpit-api/tests/test_cases_router.py` cover:**
    - `GET /v1/cases/{case_id}` returns 200 + the seeded Case payload (use a per-test fixture that inserts a `Case` via `CaseRepo.insert` against an in-memory SQLite engine, with `app.dependency_overrides[get_session] = lambda: that_session`)
    - `GET /v1/cases/{case_id}` returns 404 + RFC 7807 body when the case is missing
    - `GET /v1/cases/{case_id}` returns 422 when the `case_id` is malformed (`"bogus"`)
    - `GET /v1/cases/{case_id}` returns 400 when `X-Cockpit-Demo-User` is missing
    - `GET /v1/cases/{case_id}` returns 400 when `X-Cockpit-Demo-User` is unknown
    - `GET /v1/cases/{case_id}` returns 200 for **each** of the three demo users (parametrized) — confirms no role gate at the API level
    - `GET /v1/cases` returns 200 + an empty `items` list when no cases exist
    - `GET /v1/cases` returns 200 + the list ordered `created_at DESC` when 3 cases are seeded with distinct created_at values
    - `GET /v1/cases` and `GET /v1/cases/{case_id}` both reject missing `X-Cockpit-Demo-User`

10. **AC10 — Vitest spec in `apps/cockpit-ui/src/hooks/useCase.test.tsx`** covers:
    - `useCase(case_id)` calls the typed client with `path.case_id` matching the hook arg
    - The Zustand `currentUser.id` is propagated to the request as the `X-Cockpit-Demo-User` header
    - On 404, the hook surfaces `isError: true` and `error.detail` matches the RFC 7807 detail string

    Use `msw` (Mock Service Worker) — already a Vitest convention or add it as a dev dep — to mock the API in this hook test. **Recommended: install `msw` here** since Story 2-3 and downstream Epics will all need API mocking; one install pays for all.

11. **AC11 — `make lint` + `make test` + `make contracts` all pass green.** No regression to existing tests. `packages/contracts/openapi.json` and `apps/cockpit-ui/src/api-types.ts` are committed and CI passes the drift check.

12. **AC12 — `routes/cases.$caseId.tsx` is deferred to Story 4-X (Case Canvas).** This story only proves that `useCase(case_id)` works — no route, no Case Canvas component. The dev should manually verify the hook against a real seeded fixture (after Story 2-4 lands) by attaching a temporary `<pre>{JSON.stringify(useCase(...).data)}</pre>` to `routes/queue.tsx` for a 30-second eyeball, then remove. **Do NOT commit a temporary debug render** — delete before merging.

## Tasks / Subtasks

- [x] **Task 1 — Author the cases router** (AC: #1, #2, #3, #4)
  - [x] Subtask 1.1 — Create `apps/cockpit-api/src/cockpit_api/routers/cases.py`. Define `router = APIRouter(prefix="/v1/cases", tags=["cases"])`. Add `GET ""` for list, `GET "/{case_id}"` for single.
  - [x] Subtask 1.2 — Path param: `case_id: Annotated[str, Path(pattern=r"^case_[0-9A-HJKMNP-TV-Z]{26}$")]`. FastAPI returns 422 automatically on pattern mismatch.
  - [x] Subtask 1.3 — Define `CaseEnvelope` Pydantic model in `cockpit_api/routers/cases.py` (or in `packages/contracts/src/contracts/cases.py` if the dev judges it belongs in contracts — **prefer router-local** since the envelope is API-shape, not domain-shape). `class CaseEnvelope(Case): _links: dict[str, str | None] = {"documents": None, "reasoning_traces": None}`. Use Pydantic's `Field(default_factory=lambda: {...})` to avoid the mutable-default footgun.
  - [x] Subtask 1.4 — Define `CaseListResponse(BaseModel)` with `items: list[CaseEnvelope]`, `next_cursor: str | None = None`, `has_more: bool = False`. Per architecture's pagination format.
  - [x] Subtask 1.5 — Wire `app.include_router(cases_router.router)` in `cockpit_api/main.py`.

- [x] **Task 2 — Author the case service** (AC: #5)
  - [x] Subtask 2.1 — Create `apps/cockpit-api/src/cockpit_api/services/__init__.py` and `services/case_service.py`. Two async methods, both taking `AsyncSession` as a positional arg.
  - [x] Subtask 2.2 — `get_case` raises `HTTPException(status_code=404, detail=f"Case {case_id} not found")` on `None`. The RFC 7807 handler (Task 3) translates.
  - [x] Subtask 2.3 — `list_cases` returns the list directly; the router wraps in `CaseListResponse`.

- [x] **Task 3 — Author the RFC 7807 error handler** (AC: #2)
  - [x] Subtask 3.1 — Create `apps/cockpit-api/src/cockpit_api/errors.py` with `class RFC7807Problem(BaseModel)` (fields: `type`, `title`, `status`, `detail`, `instance`). Default `type = "about:blank"` per RFC 7807.
  - [x] Subtask 3.2 — Add `app.exception_handler(HTTPException)` in `cockpit_api/main.py` returning `JSONResponse(content=problem.model_dump(), status_code=status_code, media_type="application/problem+json")`. Read `instance` from the request URL path.
  - [x] Subtask 3.3 — Add `app.exception_handler(RequestValidationError)` mapping FastAPI's 422 → RFC 7807 with `detail` listing each Pydantic error message in a single string. Keep it readable; don't over-engineer.
  - [x] Subtask 3.4 — Verify the existing `GET /v1/users/me` 400 errors (Story 1-4) now return RFC 7807 — they should automatically since they go through `HTTPException`. Story 1-4's tests assert on `detail`; verify they still pass after adding the handler.

- [x] **Task 4 — Wire `make contracts`** (AC: #6, #11)
  - [x] Subtask 4.1 — Replace the Makefile `contracts` stub with: (a) `cd apps/cockpit-api && poetry run python -c "from cockpit_api.main import app; import json; print(json.dumps(app.openapi(), indent=2))" > ../../packages/contracts/openapi.json`, (b) `cd apps/cockpit-ui && pnpm dlx openapi-typescript ../../packages/contracts/openapi.json -o src/api-types.ts`. Both steps must succeed for the target to exit 0. *(Also runs `prettier --write` on the generated TS so format-check stays clean.)*
  - [x] Subtask 4.2 — Add `apps/cockpit-ui/src/api-types.ts` and `packages/contracts/openapi.json` as committed (currently both gitignored or absent — verify with `git ls-files` and unignore). Add a header comment `// @generated by openapi-typescript — do not edit. Regenerate: make contracts` at the top of `api-types.ts` (openapi-typescript adds one automatically; verify).
  - [x] Subtask 4.3 — Add CI step in `.github/workflows/ci.yml` `lint-and-test` job: after `make contracts`, run `git diff --exit-code packages/contracts/openapi.json apps/cockpit-ui/src/api-types.ts` to fail on drift. Mirror the existing CI pattern (Story 1-3 set up `lint-and-test` and `secrets-scan`; this is a new step inside `lint-and-test`).
  - [x] Subtask 4.4 — Document in `README.md#Daily development` that `make contracts` should run after any `routers/*.py` or contract change, and that CI will fail PRs with stale generated artifacts.

- [x] **Task 5 — Upgrade `cockpit-ui` API client to openapi-fetch** (AC: #7)
  - [x] Subtask 5.1 — `pnpm add openapi-fetch` in `apps/cockpit-ui/`. Verify `openapi-typescript` is a `devDependencies` entry; add if missing.
  - [x] Subtask 5.2 — Replace `apps/cockpit-ui/src/lib/api.ts` with the canonical openapi-fetch pattern: `createClient<paths>({ baseUrl, headers })`. Headers function reads `useCurrentUser.getState().user.id` directly from the Zustand store (don't call hooks outside React — `useStore.getState()` is the correct API). *(Implemented as `apiClient.use({ onRequest })` middleware so each request reads the latest user.)*
  - [x] Subtask 5.3 — Delete `apps/cockpit-ui/src/lib/types/user.ts` (the hand-authored shadow from Story 1-4). Update any importers — the User type now comes from `import type { components } from "../api-types"` — `components["schemas"]["User"]`. Add a tiny `import type { User } from ...` re-export at the same path if the import surface is stable, OR rename consumers. *(Renamed: data-only constants moved to `lib/demoUsers.ts`; type re-exported from generated schema.)*
  - [x] Subtask 5.4 — Verify the existing Story 1-4 tests (`UserSwitcher.test.tsx`, `__root.test.tsx`, etc.) still pass — they import `User` and `Role`. If they break on the type swap, rename the import path; don't change semantics.
  - [x] Subtask 5.5 — Update `apps/cockpit-ui/src/hooks/useUsersMe.ts` (Story 1-4) to use the new `apiClient` instead of `apiFetch`. Same query key, same return type — just wired through the typed client.

- [x] **Task 6 — Author the `useCase` hook** (AC: #8, #10)
  - [x] Subtask 6.1 — Create `apps/cockpit-ui/src/hooks/useCase.ts`. Use `useQuery` from `@tanstack/react-query` (already installed per Story 1.4? — verify; install if missing). Query key: `["case", case_id]`. `staleTime: 5_000`.
  - [x] Subtask 6.2 — Wrap the openapi-fetch call: `const { data, error } = await apiClient.GET("/v1/cases/{case_id}", { params: { path: { case_id } } });` — throw if `error` so TanStack Query surfaces it; return `data`.
  - [x] Subtask 6.3 — Confirm React Query's `QueryClientProvider` wraps the app in `main.tsx` (Story 1.4 may or may not have done this). If not, add it with a default `QueryClient` (no custom retry; defaults are fine for the demo). *(Already wired in main.tsx by Story 1.4.)*
  - [x] Subtask 6.4 — Author `apps/cockpit-ui/src/hooks/useCase.test.tsx`. Set up `msw` server in `apps/cockpit-ui/src/test/setup-msw.ts` (or extend the existing `vitest.setup.ts`). Test the three scenarios from AC10. Use `renderHook` from `@testing-library/react`. *(Used `vi.stubGlobal('fetch')` instead of MSW — MSW v2 + vitest jsdom + undici has known intercept issues; same three scenarios covered. msw dep removed; can be revisited later.)*

- [x] **Task 7 — Author cockpit-api tests** (AC: #9)
  - [x] Subtask 7.1 — Create `apps/cockpit-api/tests/test_cases_router.py`. Reuse the in-memory SQLite engine fixture pattern from Story 2-1's `test_case_repo.py`. Add a session-scoped `client` fixture using `httpx.AsyncClient(transport=ASGITransport(app=app))` with `app.dependency_overrides[get_session] = lambda: test_session` to inject the test session.
  - [x] Subtask 7.2 — Helper: `_seed_case(session, **overrides)` inserts a `Case` via `CaseRepo.insert` and returns the inserted `case_id`.
  - [x] Subtask 7.3 — Write the eight test cases from AC9. Parametrize the "each demo user can read" test over `DEMO_USERS`.
  - [x] Subtask 7.4 — Confirm `make test` passes; check coverage — both router branches (200 + 404) and both list branches (empty + populated) must be hit.

- [x] **Task 8 — Run `make contracts` and commit generated artifacts** (AC: #6, #11)
  - [x] Subtask 8.1 — Run `make contracts` after all router code is in place. Inspect the diff to `packages/contracts/openapi.json` — should show new `/v1/cases` and `/v1/cases/{case_id}` paths, plus `Case`, `CaseState`, `CustomerMetadata`, `CaseEnvelope`, `CaseListResponse`, `RFC7807Problem` schemas.
  - [x] Subtask 8.2 — Inspect the diff to `apps/cockpit-ui/src/api-types.ts` — types match. If a Python `StrEnum` is rendered as a plain string TS type instead of a literal union, no fix needed (openapi-typescript handles enums correctly via `enum` in the spec — verify). *(Confirmed: both `Role` and `CaseState` rendered as TS literal unions.)*
  - [x] Subtask 8.3 — Commit both files. Run `git diff --exit-code packages/contracts/openapi.json apps/cockpit-ui/src/api-types.ts` locally to confirm clean state.

- [x] **Task 9 — Manual smoke verification** (AC: #11, #12)
  - [x] Subtask 9.1 — Run `make demo-reset` (requires Story 2-1 already merged), then `make dev`. The cases table is empty — list returns `{"items": [], "next_cursor": null, "has_more": false}`.
  - [x] Subtask 9.2 — `curl -sf -H "X-Cockpit-Demo-User: dc2aaaa3-555b-4636-89d0-6047dc205220" http://localhost:8000/v1/cases | jq` — verify shape.
  - [x] Subtask 9.3 — `curl -sf -H "X-Cockpit-Demo-User: bogus" http://localhost:8000/v1/cases | jq` — verify RFC 7807 body + 400 status.
  - [x] Subtask 9.4 — `curl -sf -H "X-Cockpit-Demo-User: dc2aaaa3-555b-4636-89d0-6047dc205220" http://localhost:8000/v1/cases/case_BOGUS | jq` — verify 422 RFC 7807.
  - [x] Subtask 9.5 — Visit `http://localhost:8000/docs` — Scalar (or Swagger UI default — Scalar is Story 2.11 in the bank-buyer scope but we don't ship that in the demo) should show the new endpoints with the `Case` and `CaseListResponse` schemas. Eyeball that `_links` appears in the `CaseEnvelope` schema. *(The Swagger UI from Story 1.2 already exposes the new endpoints with their full schemas; the openapi.json artifact also confirms `CaseEnvelope._links`.)*

## Dev Notes

### Architectural context (binding)

[Source: `architecture.md#API & Communication Patterns` A1, A4, A5, A6] — REST + JSON, OpenAPI 3.1 auto-generated by FastAPI, RFC 7807 error format, cursor-based pagination convention. The path-prefix tenant segment (`/t/{tenant_id}/v1/...`) is **dropped for the demo** per the re-scope; routes start at `/v1/...`.

[Source: `architecture.md#Frontend Architecture` F1, F13] — TanStack Query for server state, openapi-fetch for the typed client. `Case` flows from Pydantic → OpenAPI → `api-types.ts` automatically. **No hand-written DTOs**; the UI imports types from `api-types.ts`.

[Source: `architecture.md#Architectural Boundaries`] — **API boundary:** only `cockpit-api/routers/*` exposes HTTP. **Data boundary:** `repositories/*` own all SQL; ORM rows never escape. **Contract boundary:** all wire types live in `packages/contracts/`. **Cross-app types live in contracts; envelopes (with `_links`) live in the router** — envelopes are an API concern, not a domain concern.

[Source: `architecture.md#Format Patterns`] — Direct payload (no envelope), RFC 7807 errors with `application/problem+json`, ISO 8601 dates with `Z`, snake_case JSON, no booleans-as-1/0, empty list `[]`. The `_links` field uses `null` (not omitted) for missing relations to keep the shape stable across releases — this is a deliberate departure from the architecture's "omit if absent" rule because the cockpit-ui pattern-matches on the keys.

[Source: `architecture.md#Implementation Patterns & Consistency Rules` § Validation timing] — Validate at the boundary, never deeper. The router does Pydantic validation on path params (FastAPI built-in); the service trusts the router; the repo trusts the service. **Don't re-validate inside the repo** — the existing Story 2-1 pattern is correct.

[Source: `architecture.md#Anti-Patterns to Refuse`]:
- ❌ **camelCase JSON over the wire** — `_links`, `case_id`, `next_cursor`, `has_more` are all snake_case.
- ❌ **Pydantic schemas duplicated in apps** — `Case` and `CustomerMetadata` are imported from `contracts.cases`; the cockpit-api never re-defines them.
- ❌ **Silent failures** — `case_service.get_case` raises an explicit `HTTPException` on missing rows. The router never returns `null` for a missing case.
- ❌ **Loading flag in Zustand** — `useCase` uses TanStack Query's `isPending` only.

### Critical pitfalls to avoid

1. **`HTTPException` from `cockpit_api.deps.current_user` already runs through the new RFC 7807 handler.** Story 1-4's test_users.py asserts `detail` field shape. After Task 3's handler is added, the response body changes from FastAPI's default `{"detail": "..."}` to RFC 7807's `{"type": "about:blank", "title": "...", "status": 400, "detail": "...", "instance": "..."}`. **Story 1-4's tests must be updated** to assert on the RFC 7807 envelope shape — OR the dev decides to keep Story 1-4's tests asserting on `detail` only (still works since RFC 7807 has a `detail` key). Either is fine; verify the test still asserts on the right thing.

2. **Don't fabricate `_links` to endpoints that don't exist yet.** The `_links: {"documents": null, "reasoning_traces": null}` shape is intentional — both keys present, both `null` until later Epics. Don't put placeholder URLs like `/v1/cases/{id}/documents` here; that's Epic 3's responsibility to wire up real URLs that actually return data. Returning a URL that 404s is worse than `null`.

3. **`openapi-fetch` reads headers via a function, not a static object.** The Zustand `currentUser.id` changes when the user clicks the switcher. If the dev passes a static `headers: { "X-Cockpit-Demo-User": id }` object at client-creation time, switcher changes won't propagate. Use `headers: () => ({ "X-Cockpit-Demo-User": useCurrentUser.getState().user.id })` (or the equivalent middleware pattern) so each request reads the latest store value.

4. **`make contracts` requires a working FastAPI app.** If the cockpit-api fails to import (broken router, missing dep, etc.), `make contracts` fails. Run `make test` first to verify the API boots; then `make contracts`.

5. **`api-types.ts` and `openapi.json` ARE committed.** The temptation is to gitignore them as "generated artifacts." They are NOT — CI checks them for drift. If this story's dev gitignores them, the next dev's PR will silently regenerate without comparison.

6. **Don't pre-create `CaseCanvas`, `Case Canvas` route, or any UI beyond `useCase`.** Story 2-3 owns the queue rail render; Epic 4+ owns the Case Canvas. AC12 is explicit about this — the temporary debug `<pre>` for manual verification is a tool, not a deliverable. Delete before merge.

7. **422 vs 400 distinction:** 422 is FastAPI/Pydantic validation (path-param shape, body shape); 400 is application validation (unknown user, business-rule violation). The RFC 7807 handler must distinguish — different handlers for `RequestValidationError` (422) vs `HTTPException` (400, 404, 500). Don't collapse them.

8. **`AsyncClient(transport=ASGITransport(app=app))`** is the canonical 2026 httpx-FastAPI test pattern. Don't use `TestClient` (sync; doesn't exercise async paths cleanly). pytest-asyncio + httpx is the stack that matches the rest of the project.

9. **`pydantic-settings` dependency.** `fastapi[all]` historically did NOT pull `pydantic-settings`. Story 2-1 introduces `cockpit_api/config.py` which uses it. Verify with `poetry show pydantic-settings -C apps/cockpit-api`. If absent, `cd apps/cockpit-api && poetry add pydantic-settings`.

10. **`pnpm dlx openapi-typescript` runs from `apps/cockpit-ui/`.** The relative path to `packages/contracts/openapi.json` is `../../packages/contracts/openapi.json`. Verify on the dev's machine before assuming it works in CI — Make's `cd` is per-line, so `cd apps/cockpit-ui && pnpm ...` resets cwd each Make rule. Use `&&` chains, not multiple lines.

11. **Don't add tenancy back accidentally.** A reflexive senior-dev urge to "make this proper" by adding `/t/{tenant_id}/v1/cases` to match the architecture is wrong for the demo. The Demo Scope Addendum is binding — single-tenant, no path prefix. If/when the bank-buyer scope revives, all routers grow the prefix in one PR.

### Architecture patterns relevant here

[Source: `architecture.md#Project-Specific Patterns` P6 SSE Event Pattern] — N/A in this story (SSE is Epic 4). But the polling cadence chosen by Story 2-3 (5s) and the `staleTime: 5_000` in `useCase` are chosen to align — when SSE lands, both will be replaced by SSE-driven `queryClient.invalidateQueries(["case", case_id])` calls.

[Source: `architecture.md#Implementation Patterns & Consistency Rules` § Format Patterns] — RFC 7807 fields: `type`, `title`, `status`, `detail`, `instance`. Bank-buyer scope mandates additional `tenant_id` and `request_id` fields; **demo omits both** (single-tenant; no request_id middleware in scope). Document this departure in the `RFC7807Problem` model's docstring.

### Project Structure Notes

This story creates:

- `apps/cockpit-api/src/cockpit_api/routers/cases.py`
- `apps/cockpit-api/src/cockpit_api/services/__init__.py`
- `apps/cockpit-api/src/cockpit_api/services/case_service.py`
- `apps/cockpit-api/src/cockpit_api/errors.py`
- `apps/cockpit-api/tests/test_cases_router.py`
- `apps/cockpit-ui/src/hooks/useCase.ts`
- `apps/cockpit-ui/src/hooks/useCase.test.tsx`
- `apps/cockpit-ui/src/test/setup-msw.ts` (or equivalent)
- `apps/cockpit-ui/src/api-types.ts` — generated, committed (header `// @generated`)
- `packages/contracts/openapi.json` — generated, committed

This story modifies:

- `apps/cockpit-api/src/cockpit_api/main.py` — register `cases` router; add `HTTPException` + `RequestValidationError` handlers
- `apps/cockpit-api/pyproject.toml` — add `pydantic-settings` if missing (not present in Story 2-1's expected dep set)
- `apps/cockpit-ui/package.json` — add `openapi-fetch` (runtime dep), `openapi-typescript` (dev dep), `msw` (dev dep)
- `apps/cockpit-ui/src/lib/api.ts` — replace stub with openapi-fetch client
- `Makefile` — fill in `make contracts` (replaces the TODO stub)
- `.github/workflows/ci.yml` — add the `make contracts` + drift check step inside `lint-and-test`
- `.gitignore` — confirm `apps/cockpit-ui/src/api-types.ts` and `packages/contracts/openapi.json` are NOT gitignored
- `README.md#Daily development` — document `make contracts` regeneration trigger
- Story 1-4's `apps/cockpit-ui/src/lib/types/user.ts` — **deleted**; consumers updated to import from `api-types.ts`

This story DOES NOT create:

- Queue Rail UI (Story 2-3)
- Case Canvas / case detail route (Story 4-X)
- Fixture cases (Story 2-4)
- Documents, ledger, agent-action, reasoning-trace endpoints (Epic 3+)
- Webhooks, idempotency, rate limiting, OpenAPI/Scalar serving — all deferred per the demo re-scope (originally Stories 2.7–2.11)

### References

- [Source: `architecture.md#Demo Scope Addendum (2026-04-29)` § Stack changes for demo] — single-tenant, no path-prefix tenancy
- [Source: `architecture.md#API & Communication Patterns` A1, A4, A5, A6]
- [Source: `architecture.md#Frontend Architecture` F1, F13]
- [Source: `architecture.md#Architectural Boundaries`]
- [Source: `architecture.md#Format Patterns`]
- [Source: `architecture.md#Anti-Patterns to Refuse`]
- [Source: `epics.md#Epic 2 — Case Ingest & Lifecycle` § Story 2.5] — original ACs (re-scoped here as Story 2-2)
- [Source: `prd.md#FR45`] — case retrieval functional requirement (kept; demo's only consumer is cockpit-ui)
- [Source: `2-1-case-schema-and-state-machine.md`] — repo + contract this story consumes
- [Source: `1-4-cockpit-shell-with-user-switcher-three-hardcoded-roles.md` AC #11, #12] — `get_current_user` dependency + the to-be-deleted hand-authored User type

### Previous Story Intelligence

[Source: `2-1-case-schema-and-state-machine.md` — predecessor]
- `Case`, `CaseState`, `CustomerMetadata`, `CaseId`, `assert_transition`, `CaseStateTransitionError` are all importable from `contracts.cases` after Story 2-1 lands.
- `CaseRepo` exposes `get(session, case_id) -> Case | None`, `list_ordered_by_created_at_desc(session, limit) -> list[Case]`, `insert(session, case)`, and `transition(session, case_id, target)`. This story's service layer wraps `get` and `list_*` only.
- DB session plumbing (`db/session.py`, `config.py`) exists and supplies `get_session()` as a FastAPI dependency.
- Recommendation: if Story 2-1's `python-ulid` decision was "skip the dep," this story does not need ULIDs at runtime (only for path-param validation regex). If the decision was "add the dep," the regex still suffices for path-param validation — the lib is for ID *generation*, which Story 2-4 owns.

[Source: `1-4-cockpit-shell-with-user-switcher-three-hardcoded-roles.md`]
- `get_current_user` dependency reads `X-Cockpit-Demo-User` header. The router reuses it as-is — no role gate; any of the three demo users may read any case in the demo.
- `find_user_by_id(user_id) -> User | None` is the contract helper used by `get_current_user`. Don't duplicate.
- The Story 1-4 `test_users.py` asserts on the `detail` field of the 400 response. After Task 3's RFC 7807 handler, the response gains additional fields (`type`, `title`, `status`, `instance`) — `detail` is preserved, so the existing assertion still passes if it's a substring match. Verify by running the existing test suite after the handler is added.
- The hand-authored `apps/cockpit-ui/src/lib/types/user.ts` is the immediate consumer of `User` and `Role`. After Task 5.3, all consumers re-import from `api-types.ts` (`components["schemas"]["User"]`). Sweep: `grep -rn "from \"../lib/types/user\"" apps/cockpit-ui/src` to find them all.

[Source: `1-5-fresh-clone-to-running-demo-in-sixty-minutes.md`]
- `make verify` already pings `/health` and `/v1/users/me`. Consider adding a `/v1/cases` ping to `verify_demo.sh` once this story lands — but this story is NOT the right place for that update; Story 2-4's seeded fixtures make the check meaningful (otherwise list returns empty and the verify step adds no signal). Defer to Story 2-4.
- CI's `demo-verify` job runs `make verify` after the new `cases` router exists. Empty list is still a 200 — no regression expected.

### Demo verification protocol (operator hand-off)

```bash
# After implementation:

# 1. Lint + test green:
make lint
make test
# Expected: existing 55+ tests + new router tests + new UI hook test all pass.

# 2. Generated contracts up to date:
make contracts
git diff --exit-code packages/contracts/openapi.json apps/cockpit-ui/src/api-types.ts
# Expected: clean. If diff appears, commit it.

# 3. End-to-end smoke (after Story 2-4 lands; otherwise list is empty):
make demo-reset && make dev &
sleep 5
curl -sf -H "X-Cockpit-Demo-User: dc2aaaa3-555b-4636-89d0-6047dc205220" http://localhost:8000/v1/cases | jq .
# Expected: {"items": [...], "next_cursor": null, "has_more": false}

curl -sf -H "X-Cockpit-Demo-User: dc2aaaa3-555b-4636-89d0-6047dc205220" http://localhost:8000/v1/cases/case_BOGUS_ID
# Expected: 422 RFC 7807 with detail explaining the path pattern.

curl -sf -H "X-Cockpit-Demo-User: bogus" http://localhost:8000/v1/cases
# Expected: 400 RFC 7807 with detail "Unknown X-Cockpit-Demo-User: bogus".

# 4. Browser eyeball:
#    Open http://localhost:8000/docs
#    Verify the `cases` tag, two endpoints, and the schemas (Case, CaseEnvelope,
#    CustomerMetadata, CaseListResponse, RFC7807Problem) all render.

kill %1
```

If any step fails, the bug is in this story's deliverables; do not ship until green.

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (Amelia persona, bmad-dev-story workflow)

### Debug Log References

- **MSW v2 + vitest jsdom + undici don't intercept fetch reliably.** `server.listen({onUnhandledRequest: 'error'})` ran but requests still reached the real network as `TypeError: fetch failed`. Fell back to `vi.stubGlobal('fetch', vi.fn())` for `useCase.test.tsx`; covers all three AC #10 scenarios. `msw` removed from devDeps.
- **openapi-fetch captures `globalThis.fetch` at create time.** Stubbing fetch after `apiClient` was imported had no effect. Fix: pass `fetch: (...args) => globalThis.fetch(...args)` to `createClient`, indirecting through the global so test stubs win.
- **`HTTP_422_UNPROCESSABLE_ENTITY` is deprecated in starlette 1.0.** Switched to `HTTP_422_UNPROCESSABLE_CONTENT` to silence a `DeprecationWarning` that surfaced through the validation handler.
- **`make contracts` needs a Prettier pass.** `openapi-typescript` output failed `prettier --check`; piping the generated file through `prettier --write` keeps the committed artifact format-clean and the CI drift check honest.

### Completion Notes List

- AC1: `GET /v1/cases/{case_id}` returns the full `CaseEnvelope` payload — direct JSON, snake_case, `_links: {documents: null, reasoning_traces: null}` placeholder.
- AC2: RFC 7807 envelope on every error path — 404 (missing), 422 (malformed path), 400 (missing/unknown header). `application/problem+json` content type wired in `main.py`.
- AC3: `GET /v1/cases` returns `{items, next_cursor: null, has_more: false}`; default limit 100; ordered by `created_at DESC`.
- AC4: `cases` router mounted at `/v1/cases` with both routes; `Depends(get_current_user)` enforces the demo header.
- AC5: `case_service.get_case` and `case_service.list_cases` are the only call sites for `CaseRepo`; the router has zero repo imports.
- AC6: `make contracts` exports `packages/contracts/openapi.json` and regenerates `apps/cockpit-ui/src/api-types.ts` (Prettier-formatted). CI drift check added to `lint-and-test`.
- AC7: `apps/cockpit-ui/src/lib/api.ts` upgraded to `openapi-fetch` with `apiClient.use({onRequest})` middleware that reads the live Zustand `currentUser.id` per request. Hand-authored `lib/types/user.ts` deleted; runtime constants moved to `lib/demoUsers.ts`; `User` + `Role` re-exported from `@/api-types`.
- AC8: `useCase(caseId)` hook ships with `staleTime: 5_000` matching Story 2-3's queue-rail polling.
- AC9: 11 router tests in `tests/test_cases_router.py` covering all 9 listed scenarios (parametrised over the 3 demo users).
- AC10: 3 vitest specs in `useCase.test.tsx` cover URL/path-arg, header propagation from store, and 404 RFC 7807 error surface.
- AC11: `make lint` + `make test` + `make contracts` (with drift check) all clean.
- AC12: No Case Canvas route created (deferred to Story 4-X). No temporary debug render committed.

### File List

**Created**
- `apps/cockpit-api/src/cockpit_api/errors.py`
- `apps/cockpit-api/src/cockpit_api/services/__init__.py`
- `apps/cockpit-api/src/cockpit_api/services/case_service.py`
- `apps/cockpit-api/src/cockpit_api/routers/cases.py`
- `apps/cockpit-api/tests/test_cases_router.py`
- `apps/cockpit-ui/src/lib/demoUsers.ts`
- `apps/cockpit-ui/src/api-types.ts` (generated; committed)
- `apps/cockpit-ui/src/hooks/useCase.ts`
- `apps/cockpit-ui/src/hooks/useCase.test.tsx`
- `packages/contracts/openapi.json` (generated; committed)

**Modified**
- `apps/cockpit-api/src/cockpit_api/main.py` — register `cases` router + RFC 7807 handlers
- `apps/cockpit-ui/src/lib/api.ts` — replaced hand-rolled `apiFetch` with openapi-fetch typed client
- `apps/cockpit-ui/src/hooks/useUsersMe.ts` — switched to typed `apiClient`
- `apps/cockpit-ui/src/stores/currentUser.ts`, `stores/currentUser.test.ts`, `components/cockpit/UserSwitcher.tsx`, `components/cockpit/UserSwitcher.test.tsx`, `router.test.tsx` — import path swap (`@/lib/types/user` → `@/lib/demoUsers`)
- `apps/cockpit-ui/package.json` + `pnpm-lock.yaml` — added `openapi-fetch` (runtime) and `openapi-typescript` (dev)
- `Makefile` — replaced `contracts` stub with the openapi-export → openapi-typescript → prettier pipeline
- `.github/workflows/ci.yml` — added `make contracts` drift check inside `lint-and-test`
- `README.md` — documented `make contracts` regeneration trigger
- `Documentation/implementation-artifacts/sprint-status.yaml` — story 2-2 → review

**Deleted**
- `apps/cockpit-ui/src/lib/types/user.ts` (consumers migrated to `lib/demoUsers.ts` + generated types)

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-04-29 | Story 2.2 drafted in the demo re-scope. Single-tenant `GET /v1/cases/{id}` + `GET /v1/cases` list. RFC 7807 errors. `make contracts` filled in (was Story 2.11 stub). openapi-fetch typed client replaces hand-rolled stub. `useCase` TanStack Query hook ready for Story 4-X Case Canvas. |
| 2026-04-30 | Implemented all 9 tasks. 11 new router tests + 3 new useCase vitest specs; `make lint`/`make test`/`make contracts` all green; manual curl smoke confirmed all error paths. Status → review. |
