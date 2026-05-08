# Story 1.6: Identity provider seam and fixtures cleanup

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an evaluator (or future implementer) sizing this POC for a real bank deployment,
I want demo user identity to live in a clearly-named **fixture file** behind a clearly-named **`IdentityProvider` seam** — not scattered as constants across contracts code, env vars, and a hand-mirrored TS module,
So that (a) the dummy-data nature of the three users is visible at a glance, (b) there is a single, named integration point where a real IdP (Azure AD / Okta / IBM Verify / OIDC) will plug in for production, and (c) replacing the dummy users with the evaluator's own names during a POC walkthrough is a JSON edit, not a code change.

## Scope note

This story is a **structural cleanup** preparing the POC for evaluator scrutiny. It introduces no new user-facing capability — every existing endpoint, route, switcher dropdown, and test must continue to work end-to-end after the refactor.

The need surfaced during a 2026-05-06 working session that re-framed the project from "demo" to "POC". A POC evaluator will ask "where does my IdP plug in?" and today there's no defensible answer — the three users are hardcoded as constants in `packages/contracts/src/contracts/users.py:16-18` AND as TypeScript constants in `apps/cockpit-ui/src/lib/demoUsers.ts:15-23` AND as env-var mirrors in `.env`/`.env.example` lines 22-24. This story collapses those three copies into one fixture file and names the seam where production IdP code will swap in.

The OIDC implementation itself is **not** in this story (deferred to v2, see "Out of scope" below). What this story delivers is the *architectural seam* — a Protocol with one concrete impl — so a future story can land `OIDCIdentityProvider` without touching any consumer code.

## Acceptance Criteria

1. **AC1 — `fixtures/users.json` exists as the single source of demo user data.** File at `fixtures/users.json` contains a JSON array of three objects, each shaped exactly like a `User` record (`{id, name, role, initials}`). The three users preserve the Story 1.4 identities byte-for-byte:
   - `dc2aaaa3-555b-4636-89d0-6047dc205220` — Kamal Singh / analyst / KS
   - `a725a9bb-5b8e-4984-8d23-19c682225002` — Rohan Mehta / team_lead / RM
   - `a1582a20-62e1-497b-910c-45c0b0ee7030` — Anika Iyer / regulator / AI

   The file lives next to the existing `fixtures/sample_pdfs/` and `fixtures/uploads/` content, anchoring "users are demo data, just like sample PDFs are demo data."

2. **AC2 — `packages/contracts/src/contracts/users.py` exports only the schema.** The module contains exactly: `Role` (StrEnum) and `User` (BaseModel). The following symbols are **removed**: `ANALYST_ID`, `TEAM_LEAD_ID`, `REGULATOR_ID`, `DEMO_USERS`, `find_user_by_id`. The module docstring is updated to say "User schema. Demo data lives in `fixtures/users.json`; identity logic lives in `apps/cockpit-api/.../auth/identity.py` behind the `IdentityProvider` seam."

3. **AC3 — `packages/contracts/src/contracts/__init__.py` is updated to drop the deleted re-exports.** The package's public surface no longer advertises `ANALYST_ID`, `TEAM_LEAD_ID`, `REGULATOR_ID`, `DEMO_USERS`, `find_user_by_id`. The `__all__` list is updated accordingly. `User` and `Role` remain re-exported.

4. **AC4 — `apps/cockpit-api/src/cockpit_api/auth/identity.py` defines the `IdentityProvider` Protocol and `FixtureIdentityProvider` impl.** New module containing:
   - `IdentityProvider(Protocol)` with at minimum:
     - `current_user(x_cockpit_demo_user: str | None) -> User` (the existing get-by-header behavior, raising `HTTPException(400, ...)` on miss — preserves Story 1.4 AC11 wire contract verbatim).
     - `list_users() -> list[User]` (returns all three users in a stable order — analyst, team_lead, regulator).
   - `FixtureIdentityProvider(IdentityProvider)` — a concrete implementation that loads `fixtures/users.json` at init and answers both methods from in-memory copies. Path resolution: anchor to the repo root via `pathlib.Path(__file__).resolve().parents[N] / "fixtures" / "users.json"` (compute `N` from the actual depth — confirm during impl).
   - Module docstring naming the seam: `"""Identity provider seam — POC swaps in FixtureIdentityProvider; production swaps in OIDCIdentityProvider (see TBD story for v2)."""`
   - A FastAPI dependency factory `get_identity_provider() -> IdentityProvider` returning a process-singleton `FixtureIdentityProvider`. Existing `get_current_user` dependency is rewritten as a thin shim that resolves the provider via `Depends(get_identity_provider)` and calls `provider.current_user(...)`.

5. **AC5 — `apps/cockpit-api/src/cockpit_api/routers/users.py` adds `GET /v1/users` (list) and preserves `GET /v1/users/me` byte-for-byte.** The list endpoint resolves the provider via DI and returns `provider.list_users()`. Response model: `list[User]`. The `/me` endpoint's wire format does not change — same response shape, same status codes, same header contract — but its implementation now goes through the provider. This is explicit so AC #1 of Story 1.4 (Demo verification protocol) still holds.

6. **AC6 — All existing cockpit-api code that imported the deleted contract symbols is rewritten** to either:
   - (a) Consume the `IdentityProvider` via FastAPI `Depends` (preferred for production code paths), OR
   - (b) Read fixed UUIDs from a small test-helper module (preferred for test files — see AC #11 for the test-helper pattern).

   Concrete: `apps/cockpit-api/src/cockpit_api/deps/current_user.py:11` import line is replaced; the `find_user_by_id` call at line 25 goes away.

7. **AC7 — `packages/contracts/src/contracts/cases.py` no longer imports `ANALYST_ID` from the contracts package.** The fixture cases (lines 185, 223, 259) need an analyst UUID to assign as `assigned_to_user_id`. Implementation: load the analyst UUID at module import time from `fixtures/users.json` via a small helper (e.g., `_load_analyst_id_from_fixtures() -> str` that reads, parses, and finds the role-analyst record). Path resolution: same anchor pattern as AC #4. **Rationale for this approach:** keeps case fixtures inside `contracts/` (matches existing project shape — out-of-scope to relocate them) but eliminates the contracts → contracts.users coupling that this story is removing.

8. **AC8 — `apps/cockpit-ui/src/lib/demoUsers.ts` is rewritten to consume `fixtures/users.json` at build time, not as inline TS constants.** Implementation options (dev's call):
   - **Preferred: Vite static JSON import** via a path alias `@fixtures` (configured in `vite.config.ts` and `tsconfig.json` `paths`) pointing at the repo's `fixtures/` directory. Then `import demoUsers from '@fixtures/users.json'` at the top of `demoUsers.ts` and re-export with type assertions. Type-safe via TS's built-in JSON import.
   - **Acceptable fallback: pre-build codegen step** — a small Node/TS script (`apps/cockpit-ui/scripts/gen_demo_users.ts`) that reads the JSON at build/dev time and emits `demoUsers.generated.ts`, gitignored. Wire into `pnpm dev` and `pnpm build` via `predev` / `prebuild` package.json scripts.

   The exported symbols (`DEMO_USERS`, `ANALYST_ID`, `TEAM_LEAD_ID`, `REGULATOR_ID`, `User`, `Role`) keep their names and runtime values — consumer files (`UserSwitcher.tsx`, `currentUser.ts`, `router.test.tsx`, `useCase.test.tsx`, `currentUser.test.ts`) need NO changes. Type imports for `User` and `Role` continue to come from the generated `@/api-types` shadow.

9. **AC9 — `.env` and `.env.example` no longer contain `DEMO_ANALYST_ID` / `DEMO_TEAM_LEAD_ID` / `DEMO_REGULATOR_ID`.** Lines 19–24 of `.env.example` (the "Story 1.4 — three demo users for the user-switcher dropdown" block) are deleted. Lines 22–24 of `.env` are deleted. The `DEMO_TENANT_ID` and `DEMO_OFFICER_ID` entries remain — those are seed-time pins for `seed_dev.py`, legitimately env-driven.

10. **AC10 — `tools/scripts/verify_demo.sh` reads the analyst UUID from `fixtures/users.json` instead of env vars.** Line 18 currently is `ANALYST_ID="${DEMO_ANALYST_ID:-dc2aaaa3-555b-4636-89d0-6047dc205220}"`. Replace with a `jq` lookup against `fixtures/users.json` (`jq -r '.[] | select(.role == "analyst") | .id' fixtures/users.json`). Add `jq` to the prerequisites mention in the script header comment if not already there. The script's existing tests (`tools/scripts/test_verify_demo.sh`) continue to pass.

11. **AC11 — A small test-helper exposes the three UUIDs to backend tests without re-introducing the deleted contract symbols.** Add `apps/cockpit-api/tests/_demo_user_ids.py` (or equivalent — module-level constants, NOT a test fixture). It loads `fixtures/users.json` once and exposes `ANALYST_ID`, `TEAM_LEAD_ID`, `REGULATOR_ID` for tests to import. The five existing test files (`test_users.py`, `test_cases_router.py`, `test_cases_intake_route.py`, `test_cases_intake_get_route.py`, `test_documents_router.py`) update their `from contracts.users import ...` line to `from tests._demo_user_ids import ...`. **No production code may import this helper** — it's tests-only by convention, enforced by location under `tests/`.

12. **AC12 — `GET /v1/users/me` returns the same payload as before** (verified by existing `test_users.py` cases passing unchanged after the import-line swap — analyst happy path, team-lead happy path, regulator happy path, missing-header 400, unknown-UUID 400). **`GET /v1/users` is exercised by a new test** asserting it returns exactly three users in the order analyst, team_lead, regulator with the canonical names and roles.

13. **AC13 — Cockpit-ui user-switcher dropdown still works end-to-end** (manual operator verification via `make dev` — the existing Story 1.4 demo verification protocol passes verbatim). No FE behavioral change is acceptable; this is a structural-only refactor.

14. **AC14 — Tests cover the new identity surface.**
    - `apps/cockpit-api/tests/test_identity_provider.py` (NEW) — at minimum: (a) `FixtureIdentityProvider.list_users()` returns three users in canonical order; (b) `current_user()` returns the user matching a known header value; (c) `current_user()` raises `HTTPException(400)` when header is `None`; (d) `current_user()` raises `HTTPException(400)` when header is an unknown UUID.
    - `packages/contracts/tests/test_users.py` — pre-existing tests are updated: drop assertions about `DEMO_USERS` / `ANALYST_ID` (those symbols no longer exist in contracts). Keep schema-shape tests for `User` and `Role`.
    - The new `GET /v1/users` endpoint has at least one test in `test_users.py` per AC #12.
    - All existing tests across `packages/contracts`, `apps/cockpit-api`, `apps/cockpit-ui`, `apps/agents`, `tools/verifier` pass after the refactor. Total test count is preserved or grows (no test deletions except for tests that were asserting on the removed contract symbols — those are converted, not deleted).

15. **AC15 — `make lint` passes** across all five subprojects (Ruff + mypy strict + ESLint + Prettier). New files conform to the project's existing conventions: Python files use `from __future__ import annotations`, mypy strict, Ruff. TS files are TS-strict, no `any`. Path-resolution patterns in Python use `pathlib` not `os.path`.

16. **AC16 — README "Demo users" section is updated** to reference `fixtures/users.json` as the source of truth ("Edit `fixtures/users.json` and restart the cockpit-api process to swap in different evaluator names during a POC walkthrough"). The link to Story 1.4's UUID table can stay; the sentence about "UUIDs are mirrored in `.env.example`" is removed.

## Tasks / Subtasks

- [ ] **Task 1 — Create `fixtures/users.json` and slim `packages/contracts/src/contracts/users.py`** (AC: #1, #2, #3)
  - [ ] Subtask 1.1 — Author `fixtures/users.json` with the three records per AC #1. Validate the JSON parses cleanly and round-trips through `User.model_validate(...)` for all three records.
  - [ ] Subtask 1.2 — Edit `packages/contracts/src/contracts/users.py`: remove `ANALYST_ID`, `TEAM_LEAD_ID`, `REGULATOR_ID` constants (lines 16–18), remove `DEMO_USERS` list (lines 42–46), remove `find_user_by_id` function (lines 49–51). Update the module docstring per AC #2. Confirm the file is exactly: `Role`, `User`, and supporting imports.
  - [ ] Subtask 1.3 — Edit `packages/contracts/src/contracts/__init__.py`: drop `ANALYST_ID`, `DEMO_USERS`, `REGULATOR_ID`, `TEAM_LEAD_ID`, `find_user_by_id` from both the `from contracts.users import (...)` block AND the `__all__` list. Keep `Role` and `User`.
  - [ ] Subtask 1.4 — Update `packages/contracts/tests/test_users.py`: remove any tests asserting on `DEMO_USERS` / `ANALYST_ID` / `find_user_by_id`. Keep tests asserting `Role` enum membership and `User` schema validation.

- [ ] **Task 2 — Author `IdentityProvider` Protocol and `FixtureIdentityProvider` impl** (AC: #4)
  - [ ] Subtask 2.1 — Create `apps/cockpit-api/src/cockpit_api/auth/__init__.py` (empty package init).
  - [ ] Subtask 2.2 — Author `apps/cockpit-api/src/cockpit_api/auth/identity.py` with: (a) module docstring naming the seam, (b) `IdentityProvider` Protocol (`@runtime_checkable`), (c) `FixtureIdentityProvider` class loading `fixtures/users.json` at init and exposing `current_user(...)` + `list_users()`, (d) `get_identity_provider()` FastAPI dependency factory returning a process-singleton instance (use `functools.lru_cache(maxsize=1)` on a private factory function for the singleton pattern — common FastAPI idiom).
  - [ ] Subtask 2.3 — Path-resolution: anchor the fixtures path to repo root via `Path(__file__).resolve().parents[N] / "fixtures" / "users.json"`. Run `python -c "from pathlib import Path; print(Path(__file__).resolve().parents[N])"` from inside the new module to confirm `N` (likely 4 or 5 depending on the chain `apps/cockpit-api/src/cockpit_api/auth/identity.py` → repo root).
  - [ ] Subtask 2.4 — Add type stubs / `from __future__ import annotations` so mypy strict accepts the Protocol-with-runtime-check pattern.

- [ ] **Task 3 — Rewrite `deps/current_user.py` as a thin provider shim** (AC: #6)
  - [ ] Subtask 3.1 — Edit `apps/cockpit-api/src/cockpit_api/deps/current_user.py`: replace the `from contracts.users import User, find_user_by_id` line with `from contracts.users import User` and `from cockpit_api.auth.identity import IdentityProvider, get_identity_provider`. Replace the body to resolve the provider via `Depends(get_identity_provider)` and delegate. Preserve the `_HEADER_NAME = "X-Cockpit-Demo-User"` constant and the exact 400 error messages — Story 1.4 tests assert on the substring `"X-Cockpit-Demo-User"` in `detail`.
  - [ ] Subtask 3.2 — The signature of `get_current_user` should remain `(x_cockpit_demo_user: str | None = Header(...)) -> User` so existing route handlers (`apps/cockpit-api/src/cockpit_api/routers/users.py:CurrentUser` alias and any other consumer) require zero changes. Internally, it now calls into the provider.

- [ ] **Task 4 — Add `GET /v1/users` endpoint** (AC: #5, #12)
  - [ ] Subtask 4.1 — Edit `apps/cockpit-api/src/cockpit_api/routers/users.py`: add a new route handler `@router.get("", response_model=list[User])` that takes `provider: Annotated[IdentityProvider, Depends(get_identity_provider)]` and returns `provider.list_users()`.
  - [ ] Subtask 4.2 — Verify the existing `/me` endpoint's wire contract is unchanged (response model `User`, header behavior identical). Story 1.4 AC11 is non-negotiable here.
  - [ ] Subtask 4.3 — Update the `_demo_user_ids.py` test-helper (Task 6) and add a test for the new list endpoint.

- [ ] **Task 5 — Decouple `cases.py` fixtures from `contracts.users`** (AC: #7)
  - [ ] Subtask 5.1 — Edit `packages/contracts/src/contracts/cases.py`: remove the `from contracts.users import ANALYST_ID` import (line 28). Add a small helper `_load_analyst_id_from_fixtures() -> str` that resolves `fixtures/users.json` (anchor pattern: `Path(__file__).resolve().parents[N] / "fixtures" / "users.json"` — compute `N` for `packages/contracts/src/contracts/cases.py` → repo root, likely 4), parses, finds the role-analyst record, returns the id string. Cache via `functools.lru_cache(maxsize=1)`.
  - [ ] Subtask 5.2 — Replace the three `assigned_to_user_id=ANALYST_ID` references (lines 185, 223, 259) with `assigned_to_user_id=_load_analyst_id_from_fixtures()`. Run the existing contracts test suite to confirm fixture cases still validate.
  - [ ] Subtask 5.3 — If `__init__.py` re-exports any of the case-fixture builders by name (e.g., `get_demo_case_fixtures`), confirm they continue to work post-refactor. Add a smoke test if needed: `assert get_demo_case_fixtures()[0].assigned_to_user_id == "dc2aaaa3-..."`.

- [ ] **Task 6 — Add tests-only `_demo_user_ids.py` helper and migrate test imports** (AC: #11)
  - [ ] Subtask 6.1 — Create `apps/cockpit-api/tests/_demo_user_ids.py`. Single module reading `fixtures/users.json` once at import (top-level code is fine for tests-only modules) and exposing `ANALYST_ID`, `TEAM_LEAD_ID`, `REGULATOR_ID` as string constants. Add a module-level docstring noting it is tests-only.
  - [ ] Subtask 6.2 — In each of the five test files (`test_users.py`, `test_cases_router.py`, `test_cases_intake_route.py`, `test_cases_intake_get_route.py`, `test_documents_router.py`), change `from contracts.users import ANALYST_ID, ...` to `from tests._demo_user_ids import ANALYST_ID, ...`. (Adjust import path to whatever pytest's rootdir resolution requires — likely the import works as-is if `apps/cockpit-api/` is in `sys.path` per Story 1.1's pyproject config; if not, use a relative import from within the `tests/` package.)
  - [ ] Subtask 6.3 — Run `make test` for cockpit-api alone (`cd apps/cockpit-api && poetry run pytest`) to confirm all five files import the helper successfully and tests pass.

- [ ] **Task 7 — Frontend: rewire `lib/demoUsers.ts` to consume `fixtures/users.json`** (AC: #8)
  - [ ] Subtask 7.1 — Choose the integration approach (Vite alias preferred, codegen acceptable per AC #8). If Vite alias: edit `apps/cockpit-ui/vite.config.ts` to add `resolve.alias['@fixtures'] = path.resolve(__dirname, '../../fixtures')` and `apps/cockpit-ui/tsconfig.app.json` (or whichever holds `compilerOptions.paths`) to add `"@fixtures/*": ["../../fixtures/*"]`.
  - [ ] Subtask 7.2 — Rewrite `apps/cockpit-ui/src/lib/demoUsers.ts`: replace the inline `DEMO_USERS` array with `import users from '@fixtures/users.json'` and `export const DEMO_USERS: readonly User[] = users as readonly User[];`. Derive the three `*_ID` constants from the array (e.g., `export const ANALYST_ID = users.find(u => u.role === 'analyst')!.id;` — TS-strict-friendly with a runtime invariant check or non-null assertion guarded by a unit test).
  - [ ] Subtask 7.3 — Verify `pnpm tsc --noEmit` passes (TS strict). Verify `pnpm vite build` produces a working bundle. Verify `pnpm vitest run` is green.
  - [ ] Subtask 7.4 — If the Vite JSON import surfaces a typing concern (TS by default types JSON as `any` unless `resolveJsonModule: true` is set, which it should already be from earlier stories — verify), add a one-time `// eslint-disable-next-line` only as a last resort. Cleaner: derive a typed local copy via `User`-typed cast at the import site.

- [ ] **Task 8 — Trim `.env` and `.env.example`** (AC: #9)
  - [ ] Subtask 8.1 — Edit `.env.example`: delete lines 19–24 (the "Story 1.4 — three demo users for the user-switcher dropdown" comment block + the three `DEMO_*_ID=` lines). Confirm `DEMO_TENANT_ID` and `DEMO_OFFICER_ID` (lines 16–17) remain untouched.
  - [ ] Subtask 8.2 — Edit `.env`: delete the corresponding three lines (currently 22–24). The user's local `.env` may have these or may not — preserve any other content.

- [ ] **Task 9 — Update `verify_demo.sh` to read from `fixtures/users.json`** (AC: #10)
  - [ ] Subtask 9.1 — Edit `tools/scripts/verify_demo.sh:18`: replace the env-var-with-fallback line with `ANALYST_ID="$(jq -r '.[] | select(.role == "analyst") | .id' fixtures/users.json)"`. Quote properly to handle paths with spaces. Add a `set -u`-safe fallback if the file is somehow missing (e.g., `[ -f fixtures/users.json ] || { echo "fixtures/users.json missing"; exit 1; }` before the jq call).
  - [ ] Subtask 9.2 — Add a one-line note at the top of the script (in the existing comment header) listing `jq` as a prerequisite alongside `curl`.
  - [ ] Subtask 9.3 — Run `bash tools/scripts/test_verify_demo.sh` to confirm the harness still passes. The harness's "API down" assertion does not depend on the analyst UUID source, so it should be unaffected.

- [ ] **Task 10 — Tests for the new identity surface** (AC: #14)
  - [ ] Subtask 10.1 — Author `apps/cockpit-api/tests/test_identity_provider.py` with the four cases per AC #14 first bullet.
  - [ ] Subtask 10.2 — Add a test in `apps/cockpit-api/tests/test_users.py` for `GET /v1/users` per AC #12 (returns three users in canonical order; correct names and roles). Use the `_demo_user_ids.py` helper for assertion values.
  - [ ] Subtask 10.3 — Verify `apps/cockpit-ui/src/components/cockpit/UserSwitcher.test.tsx`, `currentUser.test.ts`, `router.test.tsx`, `useCase.test.tsx` all pass with the rewired `demoUsers.ts`. No changes expected to the test files themselves.

- [ ] **Task 11 — README update** (AC: #16)
  - [ ] Subtask 11.1 — Locate the "Demo users" section in `README.md` (added by Story 1.4 / 1.5). Update the prose to reference `fixtures/users.json` as the source of truth. Add the line: "To swap in evaluator names during a POC walkthrough, edit `fixtures/users.json` and restart the cockpit-api process — the `IdentityProvider` reloads on next request." (Note: with `lru_cache(maxsize=1)`, a process restart IS required — alternative is to clear the cache on a SIGHUP, but that's out of scope.)
  - [ ] Subtask 11.2 — Remove or update the sentence about "UUIDs are mirrored in `.env.example`" since they no longer are.

- [ ] **Task 12 — Lint and full-suite verification** (AC: #15)
  - [ ] Subtask 12.1 — Run `make lint`. Fix any Ruff / mypy strict / ESLint / Prettier issues.
  - [ ] Subtask 12.2 — Run `make test`. All subprojects must be green. Document the final test count (matching the Story 1.4/1.5 pattern in Completion Notes).
  - [ ] Subtask 12.3 — Run `make verify` (with `make dev` running) to confirm the demo path is intact end-to-end. The verify script should now derive the analyst UUID from the JSON fixture, hit `/v1/users/me` with that UUID, and pass.

## Dev Notes

### Architectural context (binding)

[Source: `architecture.md#Demo Scope Addendum (2026-04-29)` § Stack changes for demo] — Auth row reads "User-switcher dropdown with 3 hardcoded roles ... UI-side role gating." This story does NOT change that demo behavior — it preserves the user-switcher exactly as Story 1.4 shipped. What it changes is *where the data lives* (fixture file, not constants) and *how identity is resolved* (provider seam, not contracts re-exports).

[Source: `architecture.md#Anti-Patterns to Refuse`] — "Pydantic schemas duplicated in apps" — this story REINFORCES that anti-pattern's intent. The duplicated DUMMY DATA across three places (Python constants, TS constants, env vars) is the spirit of the same anti-pattern — schema is one thing, data is another, both should live in one place. The fix here is the same shape: one source, multiple typed consumers.

[Source: `architecture.md#Anti-Patterns to Refuse`] — "Silent failures" — the `current_user` 400 behavior is preserved verbatim. The provider seam adds a layer but does not soften the error semantics. Missing/unknown header still 400s loudly.

[Source: `architecture.md#Naming Patterns`] — Python modules are `snake_case.py`; the new file is `apps/cockpit-api/src/cockpit_api/auth/identity.py` (singular `identity`, not `identities`). Headers stay `X-Cockpit-Demo-User`. JSON wire format `snake_case`. The fixture file is `fixtures/users.json` (kebab-free; matches `fixtures/sample_pdfs/`).

[Source: `architecture.md#Cross-Cutting Concerns` (1. Tenant scoping)] — single-tenant demo; `IdentityProvider` does not return a `tenant_id`. If the bank-buyer scope is ever revived, a future `OIDCIdentityProvider` would extend the Protocol — that's a separate problem.

[Source: `architecture.md#Frontend Architecture` F2] — Zustand for client UI state. `currentUser.ts` store stays on Zustand; this story does not move identity into TanStack Query (which would imply server state, which we are not introducing). The fact that the FE now CAN call `GET /v1/users` is incidental — the existing pattern of "switcher pre-renders from a static list" is preserved by reading from the JSON at build time.

[Source: `architecture.md#Build & Deployment`] — local dev runs cockpit-api as a uvicorn process. `lru_cache(maxsize=1)` on the provider factory means the cached provider lives for the process lifetime — a `make dev` restart picks up `fixtures/users.json` edits. Document this in README per AC #16.

### Critical pitfalls to avoid

1. **Do NOT change the wire contract of `GET /v1/users/me`.** Same response shape, same 400 messages including the `X-Cockpit-Demo-User` substring. Story 1.4 tests assert on the substring; the FE's `apiFetch` and `useUsersMe` hook are downstream consumers. Any wire-format drift breaks Story 1.4 silently.

2. **Do NOT introduce `OIDCIdentityProvider` in this story.** The Protocol is the seam; only `FixtureIdentityProvider` is implemented. A code-resident OIDC stub will look half-finished and invite a reviewer to ask "why isn't this wired up?". Name the seam in the docstring; defer the impl to v2.

3. **Do NOT delete `apps/cockpit-ui/src/lib/demoUsers.ts`.** The file is imported by 5+ FE files. Rewrite its contents (consume the JSON fixture); keep the exports' shapes identical so downstream files are zero-touch. If the file is deleted, every consumer breaks and the diff balloons.

4. **Path resolution from inside Python modules to repo root must use `pathlib`, not `os.path`.** The project uses `pathlib` per Ruff convention — see `apps/cockpit-api/src/cockpit_api/services/document_storage.py` for the canonical pattern. Use `Path(__file__).resolve().parents[N]` and explicitly count the levels from the new file. Test with a `print()` during dev to confirm `N` is correct before relying on it.

5. **The fixture file's path differs between cockpit-api and contracts.** From `apps/cockpit-api/src/cockpit_api/auth/identity.py` → `parents[4]` reaches `apps/cockpit-api/`, `parents[5]` reaches `apps/`, `parents[6]` reaches the repo root. From `packages/contracts/src/contracts/cases.py` → `parents[3]` reaches `packages/contracts/src/`, `parents[4]` reaches `packages/contracts/`, `parents[5]` reaches `packages/`, `parents[6]` reaches the repo root. **Confirm via `print` during impl** rather than assuming.

6. **`functools.lru_cache(maxsize=1)` on the provider factory is the singleton pattern.** Do NOT introduce a global module-level instance — that wires badly with FastAPI's dependency override system used in tests (Story 1.4 tests use `app.dependency_overrides` for some scenarios; the lru_cache pattern composes correctly with that, a global doesn't).

7. **Vite JSON imports are typed as `any` unless `resolveJsonModule` + `esModuleInterop` are set in `tsconfig`.** Verify both are already true in `tsconfig.app.json` (likely from Story 1.4's TS-strict baseline). If a typing issue surfaces, the cleaner fix is a typed re-cast at the import site, not a global TS config change.

8. **The `_demo_user_ids.py` test-helper module is tests-only.** Do not let production code import it. The naming (leading underscore) signals private; the location (under `tests/`) prevents accidental imports from cockpit-api source. If someone wants the IDs in production code, they should resolve them via the `IdentityProvider` like every other consumer.

9. **Story 1.4's TopBar dropdown pre-renders three options on first paint.** Do NOT introduce a "loading" state where the switcher is empty for a few hundred ms while waiting for `GET /v1/users`. The Vite static JSON import path keeps the FE behavior identical to today (synchronous render of the three options).

10. **`fixtures/users.json` is checked into the repo.** It is NOT gitignored (unlike `data/cockpit.db` or `fixtures/uploads/`). The dummy users are deliberate, fixed test data — they're the same UUIDs every developer uses.

11. **The user's `.env` file may contain other values not in this story's scope.** When deleting lines 22–24, do not touch other lines. Use `Edit` with a unique-enough `old_string` to be surgical.

12. **The fixture path inside `cases.py` creates a contracts → fixtures coupling.** This is intentional (it removes a worse contracts → contracts.users coupling). If a reviewer pushes back, point to AC #7 rationale: it's the minimum-scope path to keep case fixtures inside `contracts/` while breaking the constants dependency. Option B (move case fixtures to `fixtures/cases/*.json`) is a separate cleanup and explicitly out of scope.

### Architecture patterns relevant here

[Source: `architecture.md#Frontend Architecture` F1, F2] — TanStack Query for server state, Zustand for client state. This story preserves the boundary: `useCurrentUser` (Zustand) for the active user, the new `GET /v1/users` is callable but NOT consumed by the switcher (which uses the build-time JSON) — it's there for future code that wants the list at runtime, and so the API is symmetric.

[Source: `architecture.md#Naming Patterns`] — Python: `snake_case.py`, `PascalCase` for classes, `lower_case` for functions. TS: `camelCase.ts` for hooks/lib, `PascalCase.tsx` for components. JSON wire `snake_case`. `fixtures/users.json` content uses `snake_case` field names (`id`, `name`, `role`, `initials` — already lowercase).

[Source: `architecture.md#Build & Deployment`] — uvicorn for cockpit-api, Vite for cockpit-ui. The Vite static JSON import is a build-time read; the Python `lru_cache` is a process-lifetime read. Both invalidate on restart, which matches the documented operator workflow.

### Project Structure Notes

This story creates:

- `fixtures/users.json` — the demo user fixture (3 records)
- `apps/cockpit-api/src/cockpit_api/auth/__init__.py` — empty package init
- `apps/cockpit-api/src/cockpit_api/auth/identity.py` — `IdentityProvider` Protocol + `FixtureIdentityProvider` impl + `get_identity_provider` DI factory
- `apps/cockpit-api/tests/_demo_user_ids.py` — tests-only helper exposing the three UUIDs
- `apps/cockpit-api/tests/test_identity_provider.py` — unit tests for the provider

This story modifies:

- `packages/contracts/src/contracts/users.py` — slim to schema only (delete constants + DEMO_USERS + find_user_by_id)
- `packages/contracts/src/contracts/__init__.py` — drop deleted re-exports
- `packages/contracts/src/contracts/cases.py` — replace `ANALYST_ID` import with fixture-driven helper
- `packages/contracts/tests/test_users.py` — drop tests for removed symbols, keep schema tests
- `apps/cockpit-api/src/cockpit_api/deps/current_user.py` — rewrite as provider shim
- `apps/cockpit-api/src/cockpit_api/routers/users.py` — add `GET /v1/users` (list) endpoint
- `apps/cockpit-api/tests/test_users.py` — add list-endpoint test; switch import to `_demo_user_ids`
- `apps/cockpit-api/tests/test_cases_router.py` — switch import to `_demo_user_ids`
- `apps/cockpit-api/tests/test_cases_intake_route.py` — switch import to `_demo_user_ids`
- `apps/cockpit-api/tests/test_cases_intake_get_route.py` — switch import to `_demo_user_ids`
- `apps/cockpit-api/tests/test_documents_router.py` — switch import to `_demo_user_ids`
- `apps/cockpit-ui/src/lib/demoUsers.ts` — rewrite to consume `fixtures/users.json` (Vite alias or codegen)
- `apps/cockpit-ui/vite.config.ts` — add `@fixtures` path alias (if Vite alias approach chosen)
- `apps/cockpit-ui/tsconfig.app.json` (or equivalent) — add matching `paths` entry
- `tools/scripts/verify_demo.sh` — read analyst UUID from JSON via `jq`
- `.env.example` — delete the three `DEMO_*_ID` user lines + their comment block
- `.env` — delete the three `DEMO_*_ID` user lines (preserve other content)
- `README.md` — update "Demo users" section to reference `fixtures/users.json`

This story DOES NOT create:

- `OIDCIdentityProvider` impl (deferred to v2)
- A `Documentation/POC-bridge.md` doc enumerating mocked vs production seams (separate concern)
- A SIGHUP/file-watch-driven cache invalidation for `fixtures/users.json` edits (process restart is fine)
- A separate `fixtures/cases/*.json` for case-fixture data (option (b) of AC #7's rationale — out of scope)
- Any change to the `X-Cockpit-Demo-User` header name or the wire format of `/v1/users/me`

### Operator verification protocol

```bash
# Refactor verification — must pass before this story is marked done.

# 1. Lint + tests across the suite.
make lint
make test
# Expect: green across packages/contracts, apps/cockpit-api, apps/cockpit-ui,
# apps/agents, tools/verifier. Total test count ≥ pre-refactor count.

# 2. Demo path end-to-end.
make dev &
sleep 30
make verify
# Expect: 5 green checks (or 4 + skipped ADK if not running locally).

# 3. User-switcher manual verification.
# Open http://localhost:5173
# Default state: routed to /queue, TopBar shows "Kamal Singh · Analyst".
# Click dropdown → select "Rohan Mehta" → URL changes to /approvals.
# Click → select "Anika Iyer" → URL changes to /regulator-lens.
# Reload → still on the last selected user's default route.

# 4. POC editor swap simulation.
# Edit fixtures/users.json: change "Kamal Singh" to "Test Evaluator".
# Stop and restart `make dev` (Ctrl-C, then `make dev`).
# Reload http://localhost:5173.
# Expect: TopBar shows "Test Evaluator · Analyst".
# Revert fixtures/users.json before committing.

# 5. .env hygiene.
grep -E 'DEMO_(ANALYST|TEAM_LEAD|REGULATOR)_ID' .env .env.example
# Expect: zero matches.

# 6. New endpoint smoke.
curl -sf -H "X-Cockpit-Demo-User: dc2aaaa3-555b-4636-89d0-6047dc205220" \
  http://localhost:8000/v1/users | jq .
# Expect: JSON array of three users in order analyst, team_lead, regulator.

# Tear down.
kill %1
```

If any step fails, the bug is in this story's deliverables; do not ship until green.

### References

- [Source: `architecture.md#Demo Scope Addendum (2026-04-29)` § Stack changes for demo]
- [Source: `architecture.md#Anti-Patterns to Refuse`] — "Pydantic schemas duplicated in apps", "Silent failures"
- [Source: `architecture.md#Frontend Architecture`] — F2 Zustand for client UI state
- [Source: `architecture.md#Naming Patterns`]
- [Source: `architecture.md#Build & Deployment`]
- [Source: `architecture.md#Cross-Cutting Concerns`] — single-tenant demo
- [Source: `1-4-cockpit-shell-with-user-switcher-three-hardcoded-roles.md`] — predecessor; this story preserves its wire contracts (AC #11 `GET /v1/users/me`, header name, 400 semantics)
- [Source: `1-5-fresh-clone-to-running-demo-in-sixty-minutes.md`] — predecessor; this story preserves its `make verify` flow, just changes the analyst UUID source

### Previous Story Intelligence

[Source: `1-4-cockpit-shell-with-user-switcher-three-hardcoded-roles.md` (Dev Notes)]
- TS strict is ON in cockpit-ui. `any` is forbidden. The Vite JSON import must produce a typed `User[]`, not `any[]`. Verify `resolveJsonModule: true` is already set; if not, this story does NOT add it (would be scope creep — escalate).
- pnpm + Poetry are the only package managers. No `npm install` or `pip install`.
- The `User` Pydantic contract lives ONCE in `packages/contracts`; cockpit-ui hand-authors a TS shadow — that shadow is now in `apps/cockpit-ui/src/api-types.ts` (generated) per `apps/cockpit-ui/src/lib/demoUsers.ts:8`. Story 2.11 owns the contracts generator; this story does NOT touch it.
- The `X-Cockpit-Demo-User` header is the demo's auth model. Naming is binding (architecture.md#Naming Patterns).
- `noUncheckedIndexedAccess: true` (Story 1.1) means `users.find(u => u.role === 'analyst')!` in `currentUser.ts` already uses non-null assertion guarded by an invariant check. The new `demoUsers.ts` should follow the same pattern.

[Source: `1-5-fresh-clone-to-running-demo-in-sixty-minutes.md` (Dev Notes + Completion Notes)]
- `tools/scripts/verify_demo.sh` exists and uses `set -uo pipefail`. New jq-based UUID lookup must be `set -u`-safe (no unbound variable expansions).
- `make verify` is part of the CI `demo-verify` job (`.github/workflows/ci.yml`). The job runs `CI=1 make verify`. The CI runner has `jq` available (Ubuntu default). If not, surface the dependency in the workflow's setup step.
- `apps/cockpit-api/tests/test_seed_dev.py` was rewritten on SQLAlchemy async. New tests should follow the same async pattern if they need DB access (`test_identity_provider.py` does NOT need DB access — it only needs the JSON fixture).
- Test count was 44 + 2 bash assertions. Post-refactor: at least preserved (likely +2 or +3 from `test_identity_provider.py` and the `GET /v1/users` test).

[Source: `1-1-bootstrap-the-polyglot-monorepo-from-the-canonical-scaffold.md`]
- Naming locked: `apps/cockpit-api/src/cockpit_api/`, `packages/contracts/src/contracts/`. The new `auth/` subpackage under `cockpit_api/` is consistent.
- `from __future__ import annotations` at the top of every Python file. mypy strict.
- `py.typed` marker exists at `packages/contracts/src/contracts/py.typed` (Story 1.4 added it). Type imports across the package boundary work.

[Source: `1-3-cicd-skeleton-with-oidc-federated-cloud-creds.md`]
- CI runs `make lint` + `make test` on every PR. Pre-commit hooks run subset locally.
- `actionlint` is wired — if `ci.yml` needs touching for a `jq` setup step, format accordingly.

### Sales-narrative context (why this matters for the POC)

A POC evaluator at a bank will ask "where does my IdP plug in?" — they will not accept "we hardcoded users." Today's code gives no good answer. Post-this-story:

1. Point at `apps/cockpit-api/src/cockpit_api/auth/identity.py` — "this is the seam."
2. Point at `FixtureIdentityProvider` — "this is the POC stub; production swaps in `OIDCIdentityProvider` here."
3. Point at `fixtures/users.json` — "and during the POC walkthrough, edit this file to put your evaluators' names in the cockpit, restart, done."

That story is what reframes "hardcoded users" from "this is unfinished" to "this is a deliberate stub at a clearly-named integration point" — and unblocks claim #6 ("Keep humans firmly in control") in the IBM sales-pitch readout. Bookmark this rationale for when a future story implements `OIDCIdentityProvider`.

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-05-06 | Story 1.6 drafted in response to a 2026-05-06 working-session re-frame from "demo" to "POC". Introduces the `IdentityProvider` seam (Protocol + `FixtureIdentityProvider` impl) and consolidates demo user data into a single `fixtures/users.json` source-of-truth. Removes the duplicated UUID constants from `packages/contracts/src/contracts/users.py`, `apps/cockpit-ui/src/lib/demoUsers.ts`, and `.env`/`.env.example`. Adds `GET /v1/users` (list) endpoint. Defers `OIDCIdentityProvider` impl to v2. |
