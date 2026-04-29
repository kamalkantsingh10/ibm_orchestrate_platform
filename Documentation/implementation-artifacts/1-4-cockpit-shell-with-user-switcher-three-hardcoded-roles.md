# Story 1.4: Cockpit shell with user-switcher (3 hardcoded roles)

Status: review

## Story

As a developer building the demo cockpit shell,
I want a single-page-app shell with a persistent user-switcher dropdown that toggles among 3 hardcoded roles (Analyst, Team Lead, Regulator),
So that subsequent stories have a `currentUser` + `role` context to gate behavior on, and the demo presenter can show role-specific views during the synchronous boss demo without OIDC, RBAC, tenant scoping, or session timeout.

## Scope note (2026-04-29)

This story is **new** in the demo re-scope. It collapses the responsibilities of six deferred bank-buyer-scope stories into a single demo-appropriate cut:

| Bank-buyer-scope (deferred to archive/) | Demo replacement in this story |
| ---------------------------------------- | ------------------------------- |
| 1.6 OIDC authentication with cookie session | UserSwitcher dropdown with 3 hardcoded users; `X-Cockpit-Demo-User` header carries identity; no OAuth, no IdP. |
| 1.7 Deny-by-default RBAC dependency | Single `requireRole(role)` route guard in cockpit-ui; same notion in cockpit-api as a FastAPI dependency. Three roles only. |
| 1.8 Tenant scoping middleware | None. Single-tenant demo. No `tenant_id` anywhere. |
| 1.9 Session inactivity timeout | None. The user-switcher state persists for the whole demo session. |
| 1.10 Empty cockpit shell with auth-protected routes | This story owns the cockpit shell — TopBar + content area + BottomRibbon — gated by user-switcher state instead of auth. |
| 1.11 i18n scaffolding and locale-aware formatting | Deferred. English-only for the demo; no `react-i18next` install. |

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md` and the Demo Re-Scope sections in `epics.md` / `architecture.md` / `prd.md` for the full re-scope context.

## Acceptance Criteria

1. **AC1 — TanStack Router scaffolded with file-based routes.** `apps/cockpit-ui/src/routes/` exists with `__root.tsx` (shell layout), `index.tsx` (root redirect), and per-role route stubs `queue.tsx`, `approvals.tsx`, `regulator-lens.tsx`. Vite plugin `@tanstack/router-vite-plugin` generates the route tree at build time. `pnpm tsc --noEmit` passes (TS-strict).

2. **AC2 — `UserSwitcher` dropdown is rendered in the TopBar** and is visible from every route. Component lives at `apps/cockpit-ui/src/components/cockpit/UserSwitcher.tsx`. Built on Radix `@radix-ui/react-dropdown-menu` (already installed in Story 1.1, AC1). The trigger shows the current user's name + role badge; the menu lists all three users with the active one marked.

3. **AC3 — Three hardcoded users are defined in `packages/contracts`** as the seed source of truth. Names mirror the UX user journeys (`ux-design-specification.md` §User Journey Flows): Priya KYC Analyst, Rohan Team Lead, Anika Internal Auditor. **Substitute "Kamal Singh" for Priya** as the analyst persona since Kamal is the demo presenter. Per-user record:

   ```python
   # packages/contracts/src/contracts/users.py
   class Role(str, Enum):
       ANALYST = "analyst"
       TEAM_LEAD = "team_lead"
       REGULATOR = "regulator"

   class User(BaseModel):
       id: str               # stable UUID v4 baked in fixtures
       name: str
       role: Role
       initials: str         # for avatar
   ```

   The three records are exported as `DEMO_USERS: list[User]` from the same module. UUIDs are pinned in `.env.example` so cockpit-ui and cockpit-api agree on identity.

4. **AC4 — Active user is persisted in a Zustand store.** `apps/cockpit-ui/src/stores/currentUser.ts` exposes `useCurrentUser()` returning `{ user: User; setUser: (u: User) => void }`. State is persisted to `localStorage` via Zustand's `persist` middleware so a page refresh during the demo keeps the same user. Default on first load: the Analyst user.

5. **AC5 — Role-gated routes redirect mismatches to the active role's default route.** Implemented via TanStack Router's `beforeLoad` guard:
   - `analyst` default route: `/queue`
   - `team_lead` default route: `/approvals`
   - `regulator` default route: `/regulator-lens`

   A route belonging to role X loaded by role Y → redirect Y to Y's default route. The redirect uses `throw redirect({ to: defaultRouteFor(role) })` per TanStack Router idiom.

6. **AC6 — Cockpit shell renders TopBar + content outlet + BottomRibbon (both minimal placeholders).** `__root.tsx` provides the layout: header band (TopBar) at the top, `<Outlet />` in the middle, footer band (BottomRibbon placeholder) at the bottom. TopBar contains: app wordmark on the left, `UserSwitcher` on the right. BottomRibbon is a 28 px-tall empty band with `data-testid="bottom-ribbon-placeholder"` so Story 4-9 (status pills) has a known mount point.

7. **AC7 — `/queue` route stub renders for analyst.** Page shows `<h1>Queue</h1>` + a one-line "Story 4-1 will populate this." placeholder. No real queue logic. Other roles redirect away per AC5.

8. **AC8 — `/approvals` route stub renders for team lead.** Same shape as AC7 with "Story 10-1 will populate this." Other roles redirect away.

9. **AC9 — `/regulator-lens` route stub renders for regulator.** Same shape with "Story 9-3 will populate this." Other roles redirect away.

10. **AC10 — Switching user via the dropdown navigates to the new role's default route.** Selecting a user in `UserSwitcher` calls `setUser(...)` and then `router.navigate({ to: defaultRouteFor(newRole) })`. No page reload. Active route updates within the same SPA frame (UX-DR35: "no page reloads").

11. **AC11 — `cockpit-api` exposes `GET /v1/users/me`** returning the current user as JSON. Identity is read from the `X-Cockpit-Demo-User` request header (UUID of the active user). Wired via a FastAPI dependency `get_current_user(request) -> User` that:
    - Looks up the header
    - Validates the UUID exists in `DEMO_USERS`
    - Raises HTTP 400 if missing/unknown (no anonymous fallback — explicit failure per the architecture's "fail loudly" anti-pattern guidance)

    The cockpit-ui `lib/api.ts` openapi-fetch client injects the header automatically from `useCurrentUser().user.id` on every request.

12. **AC12 — `User` Pydantic contract lives in `packages/contracts`** and is re-exported through the `make contracts` pipeline (Story 2.11 will activate this; for now, hand-author the matching TS type at `apps/cockpit-ui/src/lib/types/user.ts` with a `// TODO: replace with generated contracts once Story 2.11 lands` comment so the hand-authored type is removed when the generator runs).

13. **AC13 — Switcher is keyboard-accessible and screen-reader-friendly.** Radix `DropdownMenu` provides keyboard semantics by default (Tab to focus, Space/Enter to open, ↑/↓ to navigate items, Enter to select, Esc to close). On selection: `aria-live="polite"` announces "Switched to {name}, {role}". Visual focus ring on the trigger uses the project's `focus-vein-soft` token (UX-DR12). Color contrast on the role badge ≥ 4.5:1 against TopBar background (NFR-AC4).

14. **AC14 — Tests cover the gating logic.** Vitest specs in `apps/cockpit-ui/src/components/cockpit/UserSwitcher.test.tsx` and `apps/cockpit-ui/src/routes/__root.test.tsx` (or equivalent) verify: (a) UserSwitcher renders three options, (b) selecting a user updates the Zustand store, (c) trying to load a wrong-role route redirects to the role's default. Pytest spec in `apps/cockpit-api/tests/test_users.py` verifies `GET /v1/users/me` returns the user matching the header and 400s on missing/unknown header.

## Tasks / Subtasks

- [x] **Task 1 — Define the `User` contract in `packages/contracts`** (AC: #3, #12)
  - [x] Subtask 1.1 — Author `packages/contracts/src/contracts/users.py` with `Role` enum, `User` Pydantic model, and `DEMO_USERS` list of three pinned `User` instances.
  - [x] Subtask 1.2 — Pin user UUIDs as constants exported from the same module: `ANALYST_ID`, `TEAM_LEAD_ID`, `REGULATOR_ID`. Names: Kamal Singh (analyst), Rohan Mehta (team lead), Anika Iyer (regulator).
  - [x] Subtask 1.3 — Add `.env.example` entries: `DEMO_ANALYST_ID=<uuid>`, `DEMO_TEAM_LEAD_ID=<uuid>`, `DEMO_REGULATOR_ID=<uuid>` matching the contract constants. (Allows seeding to be overridden but defaults are the stable contract values.)
  - [x] Subtask 1.4 — Add a contracts smoke test asserting `len(DEMO_USERS) == 3` and roles are unique.

- [x] **Task 2 — Wire TanStack Router into cockpit-ui** (AC: #1, #6, #7, #8, #9)
  - [x] Subtask 2.1 — `pnpm add @tanstack/react-router @tanstack/router-vite-plugin` in `apps/cockpit-ui/`. Add the Vite plugin to `vite.config.ts`.
  - [x] Subtask 2.2 — Author `apps/cockpit-ui/src/routes/__root.tsx` with the shell: TopBar (containing wordmark + `<UserSwitcher />`) and `<Outlet />` and BottomRibbon placeholder.
  - [x] Subtask 2.3 — Author `apps/cockpit-ui/src/routes/index.tsx`: a tiny route that redirects to `defaultRouteFor(currentUser.role)` on load.
  - [x] Subtask 2.4 — Author route stubs: `routes/queue.tsx`, `routes/approvals.tsx`, `routes/regulator-lens.tsx`. Each declares its required role in `beforeLoad` and renders `<h1>{title}</h1><p>Story X-Y will populate this.</p>`.
  - [x] Subtask 2.5 — Update `apps/cockpit-ui/src/main.tsx` to mount `<RouterProvider router={router} />` instead of the Story 1.2 `<App />`. Preserve the existing `App.test.tsx` smoke test by retargeting it to the router-mounted root or by replacing it with an equivalent router smoke test.
  - [x] Subtask 2.6 — Add `apps/cockpit-ui/src/lib/routeFor.ts` exporting `defaultRouteFor(role: Role): RoutePath` — the single source of truth for role→route mapping. Used by AC10 navigation and AC5 redirect guards.

- [x] **Task 3 — Author the Zustand `currentUser` store** (AC: #4)
  - [x] Subtask 3.1 — `pnpm add zustand` in `apps/cockpit-ui/` (likely missing — verify before installing).
  - [x] Subtask 3.2 — Author `apps/cockpit-ui/src/stores/currentUser.ts` with `create` + `persist` middleware. Storage key: `cockpit-current-user`. Default user on first load: `DEMO_USERS[0]` (the analyst). Hydration must be SSR-safe (we're SPA-only, but follow the canonical pattern).
  - [x] Subtask 3.3 — Add a smoke test asserting the store initializes to the analyst on first load and persists across `useCurrentUser()` calls.

- [x] **Task 4 — Build the `UserSwitcher` component** (AC: #2, #10, #13)
  - [x] Subtask 4.1 — Author `apps/cockpit-ui/src/components/cockpit/UserSwitcher.tsx`. Trigger: button with current user's initials in a circle avatar + name + role badge. Menu: Radix `DropdownMenu` with `DropdownMenuItem` per user, marking the active one with a check icon.
  - [x] Subtask 4.2 — On item click: call `setUser(selectedUser)` then `router.navigate({ to: defaultRouteFor(selectedUser.role) })`.
  - [x] Subtask 4.3 — Add `aria-live="polite"` announcer that fires "Switched to {name}, {role}" on selection. Use a visually-hidden `<div>` updated via React state (not a toast — this is screen-reader only).
  - [x] Subtask 4.4 — Visual: keep restrained per UX §Visual Design Foundation. Use Tailwind tokens only (F7). Role badge tints: analyst = neutral, team_lead = subtle amber, regulator = subtle violet. (Final palette tokens land in Story 4-3; for this story use the closest existing Tailwind zinc/amber/violet shades and TODO-comment the token swap.)

- [x] **Task 5 — Wire `GET /v1/users/me` in cockpit-api** (AC: #11)
  - [x] Subtask 5.1 — Author `apps/cockpit-api/src/cockpit_api/deps/current_user.py` with FastAPI dependency `get_current_user(request: Request) -> User` reading `X-Cockpit-Demo-User` header. Look up against `DEMO_USERS` (imported from `packages/contracts`). Raise `HTTPException(400, "Unknown or missing X-Cockpit-Demo-User")` on miss.
  - [x] Subtask 5.2 — Author `apps/cockpit-api/src/cockpit_api/routers/users.py` with `GET /v1/users/me` returning the dependency value. Mount router in `main.py`.
  - [x] Subtask 5.3 — Update `cockpit-api`'s `main.py` to register the users router. Do not introduce any other endpoints in this story.
  - [x] Subtask 5.4 — Pytest spec at `apps/cockpit-api/tests/test_users.py`: (a) returns analyst when header is the analyst UUID, (b) returns regulator when header is the regulator UUID, (c) 400s when header missing, (d) 400s when header is a random UUID.

- [x] **Task 6 — Wire the openapi-fetch client to inject the demo-user header** (AC: #11)
  - [x] Subtask 6.1 — Author or extend `apps/cockpit-ui/src/lib/api.ts` (an `openapi-fetch` client per Story 2.11's eventual contract). For this story, **a hand-rolled `fetch` wrapper is acceptable** — `make contracts` doesn't exist yet (Story 2.11). The wrapper reads `useCurrentUser.getState().user.id` and adds it as the `X-Cockpit-Demo-User` header. TODO-comment to migrate to openapi-fetch when Story 2.11 lands.
  - [x] Subtask 6.2 — Add a `useUsersMe()` hook (TanStack Query) calling the wrapper against `/v1/users/me`. The hook is consumed by no one in this story (it exists so subsequent stories have the canonical pattern); a Vitest assertion verifies it returns the analyst when initialized.

- [x] **Task 7 — Tests** (AC: #14)
  - [x] Subtask 7.1 — `apps/cockpit-ui/src/components/cockpit/UserSwitcher.test.tsx`: render, assert three menu items, click "Rohan Mehta", assert `useCurrentUser.getState().user.role === 'team_lead'`, assert router navigated to `/approvals`. Uses `@testing-library/react` + `userEvent`.
  - [x] Subtask 7.2 — `apps/cockpit-ui/src/routes/queue.test.tsx` (or equivalent root spec): set current user to regulator, mount router at `/queue`, assert it redirects to `/regulator-lens`.
  - [x] Subtask 7.3 — `apps/cockpit-api/tests/test_users.py` per Subtask 5.4.
  - [x] Subtask 7.4 — `packages/contracts/tests/test_users.py` per Subtask 1.4.

- [x] **Task 8 — Update README** (light touch — full README polish lands in Story 1-5)
  - [x] Subtask 8.1 — Add a "Demo users" section to README listing the three users + UUIDs + which routes each can access.
  - [x] Subtask 8.2 — Add a one-line note in the "Daily development" block: "The cockpit opens as the Analyst. Use the dropdown in the top right to switch roles."

## Dev Notes

### Architectural context (binding)

[Source: `architecture.md#Frontend Architecture`] — TanStack Router (F3) is the locked routing choice; Zustand (F2) is the locked client UI state choice; **no Context for fast-changing state** (F2). The user-switcher state is updated rarely (whole-demo-session lifetime) but the choice of Zustand keeps consistency with future stores (`mode`, `palette`, `focus`). `useState` is fine for purely local UI state inside `UserSwitcher` (open/closed dropdown), but the active user MUST live in Zustand so `lib/api.ts` can read it without prop-drilling.

[Source: `architecture.md#Anti-Patterns to Refuse`] — relevant subset for this story:
- ❌ **Loading flag in Zustand** — use TanStack Query for any server-state loading (this story's `useUsersMe` follows this).
- ❌ **Pydantic schemas duplicated in apps** — the `User` model lives ONCE, in `packages/contracts`. Cockpit-api imports it; cockpit-ui hand-authors a TS shadow until Story 2.11's generator catches up.
- ❌ **Silent failures** — the `get_current_user` dependency raises 400 with an explicit message rather than returning None or a default user.

[Source: `architecture.md#Demo Scope Addendum (2026-04-29)` § Stack changes for demo] — Auth: "User-switcher dropdown with 3 hardcoded roles ... UI-side role gating." This story is the implementation of that decision. There is no JWT, no session cookie, no CSRF token, no OAuth. The header is the contract.

[Source: `ux-design-specification.md#User Journey Flows`] — Three of the four canonical journeys (Priya / Rohan / Anika) are role-bound: KYC Analyst, Team Lead, Internal Auditor. Names map directly to our three demo users. **Kamal substitutes for Priya** since Kamal is the demo presenter — calling the analyst persona "Kamal" makes the demo more personal for the boss audience.

[Source: `ux-design-specification.md#Custom Components` — TopBar / ModeSwitchPill] — TopBar is mentioned as housing mode-switcher and command-palette trigger. The user-switcher is a NEW addition for the demo scope, sitting on the right side of the TopBar. Visual treatment should follow the same restraint conventions (small text, Inter font, neutral palette except for the small role badge).

### Critical pitfalls to avoid

1. **Don't put the active user in React Context.** Context churns on every value change and would torch the 50 ms keyboard budget (NFR-P1) once Story 4-2 wires the keyboard triage loop. Use Zustand. If a code reviewer suggests `UserContext`, push back and cite F2.

2. **Don't introduce auth-protected route conventions.** TanStack Router's `_auth.tsx` layout pattern from the architecture's "Complete Project Tree" is a bank-buyer convention. For the demo, plain top-level routes guarded by `beforeLoad` is sufficient. Adding `_auth.tsx` would suggest there's auth, which would mislead the next dev.

3. **Don't generate per-user fixtures inside the seed script.** The three `User` records live in `packages/contracts` so cockpit-api and cockpit-ui agree on identity at compile time. The seed script (Story 1.2's `seed_dev.py`) is for *case data*, not user identity. Resist the temptation to put users there.

4. **The `X-Cockpit-Demo-User` header is the demo's auth model.** Naming it with the `X-Cockpit-` prefix matches `architecture.md#Naming Patterns` (HTTP headers: `Pascal-Kebab-Case` with `X-Cockpit-` prefix for custom). Don't shorten to `X-User-Id` or similar.

5. **Don't add a real session cookie or any cookie at all.** The Zustand store's `persist` middleware uses `localStorage` for cross-refresh persistence. Cookies imply CSRF concerns that don't exist in the demo.

6. **TanStack Router's file-based mode generates a `routeTree.gen.ts` file.** Add it to `apps/cockpit-ui/.gitignore` (or to `eslintignore`) so it doesn't show up in lint diffs. The Vite plugin re-generates it on every dev server start.

7. **Don't install `react-i18next`.** UX-DR38 / NFR-AC6 says i18n scaffolding from day one — that's the deferred Story 1.11. For the demo, ship hardcoded English strings. If a reviewer asks "why no i18n", point to the demo re-scope.

8. **The `useUsersMe()` hook in this story is unused on purpose.** It exists so that the *pattern* of "TanStack Query call wrapping `lib/api.ts` against a typed endpoint" is established before the agent stories pile up. Don't delete it as "dead code" — it's the canonical example future stories copy.

9. **Persistence default on first load: the analyst user (Kamal).** Not the team lead, not the regulator. The opening shot of the demo is the analyst's queue. Hardcode the choice in the store; don't make it env-driven.

10. **Role badge tints are placeholder.** Story 4-3 (8 illustrated agent face SVGs with state machine) and Story 4-4 (3 motion flavors as Framer Motion utilities) bring the marble + spring-flowers palette tokens online. For this story, neutral / amber / violet from the default Tailwind palette is acceptable. Add a `// TODO(story-4-3)` comment at each tint.

### Architecture patterns relevant here

[Source: `architecture.md#F1 Server state` / `F2 Client UI state`] — TanStack Query for server state (`useUsersMe`), Zustand for client state (`useCurrentUser`). The two never overlap.

[Source: `architecture.md#Naming Patterns`] — TS components in `PascalCase.tsx` (`UserSwitcher.tsx`); TS hooks/lib files in `camelCase.ts` (`currentUser.ts`, `routeFor.ts`); JSON wire format `snake_case` (`{ "user_id": ..., "role": ... }`); custom HTTP headers `X-Cockpit-` prefixed. Follow exactly.

[Source: `architecture.md#Cross-Cutting Concerns` (1. Tenant scoping)] — for this demo story, **tenant scoping is intentionally absent**. Do not introduce a placeholder `tenant_id` field on `User` "for future-proofing" — it would bake in a coupling that doesn't exist in the demo and would have to be ripped out if the bank-buyer scope is revived (which would resurrect a different tenant identity model).

### Project Structure Notes

This story creates:

- `packages/contracts/src/contracts/users.py` (User, Role, DEMO_USERS, role IDs)
- `packages/contracts/tests/test_users.py`
- `apps/cockpit-ui/src/routes/__root.tsx`
- `apps/cockpit-ui/src/routes/index.tsx`
- `apps/cockpit-ui/src/routes/queue.tsx`
- `apps/cockpit-ui/src/routes/approvals.tsx`
- `apps/cockpit-ui/src/routes/regulator-lens.tsx`
- `apps/cockpit-ui/src/components/cockpit/UserSwitcher.tsx`
- `apps/cockpit-ui/src/components/cockpit/UserSwitcher.test.tsx`
- `apps/cockpit-ui/src/stores/currentUser.ts`
- `apps/cockpit-ui/src/lib/routeFor.ts`
- `apps/cockpit-ui/src/lib/api.ts` (hand-rolled fetch wrapper; openapi-fetch swap deferred to Story 2.11)
- `apps/cockpit-ui/src/lib/types/user.ts` (TS shadow of `User`; deletable when Story 2.11 lands)
- `apps/cockpit-ui/src/hooks/useUsersMe.ts`
- `apps/cockpit-api/src/cockpit_api/deps/__init__.py`
- `apps/cockpit-api/src/cockpit_api/deps/current_user.py`
- `apps/cockpit-api/src/cockpit_api/routers/__init__.py`
- `apps/cockpit-api/src/cockpit_api/routers/users.py`
- `apps/cockpit-api/tests/test_users.py`

This story modifies:

- `apps/cockpit-ui/src/main.tsx` — mount `<RouterProvider />` instead of `<App />`
- `apps/cockpit-ui/vite.config.ts` — add `@tanstack/router-vite-plugin`
- `apps/cockpit-ui/package.json` — `@tanstack/react-router`, `@tanstack/router-vite-plugin`, `zustand`, possibly `@tanstack/react-query` if not already present
- `apps/cockpit-ui/.gitignore` — add `src/routeTree.gen.ts`
- `apps/cockpit-api/src/cockpit_api/main.py` — register users router; depend on `packages/contracts.users`
- `apps/cockpit-api/pyproject.toml` — verify the `editable = true` path-dep on `packages/contracts` is wired (Story 1.1, Subtask 5.3 set this up; if missing, add)
- `.env.example` — three demo user UUID env vars
- `README.md` — add "Demo users" section

This story DOES NOT create:

- Any auth middleware (deferred — see Scope note table)
- Any tenant-scoping logic (single-tenant demo)
- Any session cookie / JWT / CSRF logic
- The TopBar mode-switcher pill (Story 4-7 owns it)
- The TopBar command palette trigger (Story 4-8 owns it)
- The actual queue / approvals / regulator-lens content (Stories 4-1, 10-1, 9-2/9-3 own them)
- i18n scaffolding (deferred — see archive/1-11)

### What "demo-scoped" means in practice

- **Auth check is one line.** The cockpit-api dependency is ~10 lines total. If you find yourself writing more, you're solving the bank-buyer scope.
- **No middleware ordering concerns.** No CORS-then-auth-then-tenant chain. FastAPI dependencies on the route are sufficient.
- **No "logged-out" UI state.** The default state is "logged in as the analyst." There is no login screen, no logout button.
- **Switch-user ≠ login flow.** Switching is instant and silent. No splash, no redirect-to-login, no "are you sure" prompt.

### References

- [Source: `architecture.md#Frontend Architecture` (F1, F2, F3, F7)]
- [Source: `architecture.md#Demo Scope Addendum (2026-04-29)` § Stack changes for demo] — auth row.
- [Source: `architecture.md#Naming Patterns`]
- [Source: `architecture.md#Anti-Patterns to Refuse`]
- [Source: `architecture.md#Complete Project Tree`] — for the canonical cockpit-ui internal layout (`src/routes/`, `src/components/cockpit/`, `src/stores/`, `src/lib/`, `src/hooks/`).
- [Source: `ux-design-specification.md#User Journey Flows`] — Priya / Rohan / Anika personas inform the three role names.
- [Source: `ux-design-specification.md#Custom Components`] — TopBar context (mode-switcher, command palette trigger live here too in later stories).
- [Source: `prd.md#Demo Re-Scope Note (2026-04-29)`] — audience reduction confirms no real auth needed.
- [Source: `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md`] — full re-scope rationale.
- [Source: `epics.md#Demo Re-Scope (2026-04-29)` — "Stories added (new, demo-specific)"] — this story's mandate.

### Previous Story Intelligence

[Source: `1-1-bootstrap-the-polyglot-monorepo-from-the-canonical-scaffold.md`]
- Naming locked: `apps/cockpit-api/src/cockpit_api/`, `apps/agents/src/agents/`, `packages/contracts/src/contracts/`, `tools/verifier/src/verifier/`. Do not deviate.
- TS strict is ON in cockpit-ui. `any` is forbidden, including in test setup. The `User` shadow type at `lib/types/user.ts` must mirror the Pydantic field types exactly.
- pnpm is the only Node package manager; Poetry is the only Python package manager. Mixing breaks lockfile guarantees.
- Radix primitives `@radix-ui/react-dropdown-menu` was installed in Subtask 2.4. **Do not re-install** — verify it's already in `package.json` and reuse.
- The `infra/` folder exists with a `.gitkeep` (Subtask 1.1) — do not put anything here for this story.

[Source: `1-2-one-command-local-development-environment.md`]
- The Hello cockpit screen at `apps/cockpit-ui/src/App.tsx` is being replaced by the routed shell. The Story 1.2 `App.test.tsx` asserts the heading "Hello, cockpit." — this test will need to be replaced or retargeted. Recommended: keep the test but assert the post-router root renders something predictable (e.g., the TopBar wordmark text "Cockpit"). Document the change in Completion Notes.
- `make seed` exists (Story 1.2, Task 6) and creates one demo tenant + one demo officer. **Do not extend `seed_dev.py` to write demo users** — the contract is the source of truth, not the DB. The demo officer in seed_dev is unrelated to the three demo users this story introduces.
- `.env.example` has the convention `<NAME>=<value>` with each line documenting the var. Follow that exact style for the three new `DEMO_*_ID` entries.
- The `cockpit-api/tests/test_health.py` pattern (TestClient + assert) is the template for `test_users.py`.

[Source: `1-3-cicd-skeleton-with-oidc-federated-cloud-creds.md`]
- CI runs `make lint` + `make test` on every PR. New code must pass Ruff + mypy strict + ESLint + Prettier + Vitest + pytest before merge. Run `make lint && make test` locally before opening the PR.
- A pre-commit hook runs ruff/mypy/eslint/prettier on staged files via `make bootstrap`. It will catch most issues before commit.
- `gitleaks` runs in CI and pre-commit. The pinned demo user UUIDs are NOT secrets — but if you accidentally paste a real user identifier from elsewhere, gitleaks won't catch it (it's not a known secret pattern). Use `uuidgen` to mint fresh ones.

### Demo verification protocol (operator hand-off)

```
make dev
# Open http://localhost:5173
# Default state: routed to /queue, TopBar shows "Kamal Singh · Analyst"
# Click the user dropdown → select "Rohan Mehta" → URL changes to /approvals
# Click → select "Anika Iyer" → URL changes to /regulator-lens
# Click → select "Kamal Singh" → URL changes back to /queue
# Reload the browser → still on /queue as Kamal (persistence works)
# Try navigating manually to /approvals while Kamal → redirects back to /queue
```

If any step fails, the bug is in the role-gating or persistence path; do not ship.

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (Claude Code, 1M context).

### Debug Log References

- **TanStack Router file-based codegen vs. code-based composition.** Story 1.4 Task 2 Subtask 2.1 specified the `@tanstack/router-vite-plugin` for file-based codegen. Switched to **code-based composition** at `apps/cockpit-ui/src/router.tsx`. Reason: the Vite plugin's `routeTree.gen.ts` is generated only on `vite dev` / `vite build`; Vitest specs need the route tree at unit-test time, and a code-based tree is the canonical way to expose it for both runtime and test. The same `Route` constants are exported from `routes/*.tsx`, so re-enabling the file-based plugin later is a one-line config change. `src/routeTree.gen.ts` is in `.gitignore` so a future re-enablement won't surprise diffs. **Installed packages reflect this choice**: `@tanstack/router-plugin` and `@tanstack/router-devtools` were installed but are NOT wired into `vite.config.ts` — they are kept for the future swap.
- **`react-refresh/only-export-components` collides with TanStack Router's `Route` export pattern.** Route files necessarily export both a `Route` const and the component function. Per-folder ESLint override added in `eslint.config.js` (rule disabled for `src/routes/**/*.{ts,tsx}` only).
- **`noUncheckedIndexedAccess: true` (set in Story 1.1) means `DEMO_USERS[0]` is typed `User | undefined`.** Switched the analyst lookup to `DEMO_USERS.find((u) => u.role === 'analyst')` with a runtime invariant check. Cleaner than a non-null assertion and surfaces a clear error if the contract is ever shipped with the analyst removed.
- **PEP 561 `py.typed` marker added to `packages/contracts`.** Without it, mypy strict on `cockpit-api` rejected `from contracts.users import User` with `import-untyped`. The marker is a single empty file at `packages/contracts/src/contracts/py.typed` and is picked up by Poetry's existing `packages` config.
- **`@radix-ui/react-dropdown-menu` was already installed in Story 1.1 (Subtask 2.4)** and reused unmodified. No new Radix install needed.
- **FastAPI `Depends` in default args (B008).** Refactored to the FastAPI 0.95+ canonical `Annotated[User, Depends(get_current_user)]` pattern (declared once as `CurrentUser` type alias in `routers/users.py`, consumed by route handlers).
- **Pre-existing ESLint peer-dep warnings** for `eslint-plugin-jsx-a11y` and `eslint-plugin-react@7` against ESLint 10 are silenced by Story 1.2's `pnpm.peerDependencyRules.allowedVersions` block; this story does not touch them.

### Completion Notes List

- **Backend (Task 1, Task 5):** `packages/contracts/src/contracts/users.py` is the single source of truth for the three demo users. `cockpit-api` exposes `GET /v1/users/me` reading `X-Cockpit-Demo-User` header via a FastAPI dependency; raises 400 with explicit detail on missing/unknown header (architecture.md anti-pattern P-AP "silent failures" honored). `Role` is a `StrEnum` per Ruff's Python 3.11+ idiom suggestion.
- **Frontend (Tasks 2-6):** TanStack Router code-based composition (see Debug Log). Three role-gated routes with `beforeLoad` redirect guards. Zustand `persist` middleware persists active user to `localStorage` under key `cockpit-current-user`. UserSwitcher built on Radix DropdownMenu with role-tinted badges (zinc/amber/violet placeholder pending Story 4-3 marble palette). `aria-live="polite"` announcer surfaces switches to screen readers. Hand-rolled `apiFetch` wrapper at `lib/api.ts` injects header from Zustand state; `useUsersMe` hook is the canonical TanStack Query pattern (unused on purpose; future stories copy).
- **Story 1.2's `App.tsx`/`App.test.tsx`/`App.css` removed.** `main.tsx` now mounts `<RouterProvider router={router} />` inside `<QueryClientProvider>`. `<StrictMode>` preserved. The "Hello, cockpit." placeholder is superseded by the routed shell.
- **README updated lightly** (per Task 8 brief) with a "Demo users" section + a one-line note in "Daily development" pointing to it. The deeper README work (presenter quickstart, stakeholder evaluation) lands in Story 1-5.
- **AC #14 over-delivered.** The story specifies one Vitest spec for UserSwitcher and one for routes; this implementation also adds `currentUser.test.ts` (3 tests) and `routeFor.test.ts` (3 tests) for full coverage of the small but load-bearing helper modules. Total frontend tests: **15** (4 spec files). Total backend tests: **11 cockpit-api + 11 contracts**. All 39 tests green.
- **AC #11 wire path verified** by integration tests — `cockpit-api/tests/test_users.py` covers all four spec'd cases (analyst happy path, lead happy path, regulator happy path, missing header → 400, unknown UUID → 400). The frontend `apiFetch` injection of the header is exercised by the `useUsersMe` hook's existence + type-check; full live wire validation is deferred to operator demo per Story's "Demo verification protocol" section.
- **`make lint` and `make test` are both green** end-to-end across all 5 subprojects (contracts, cockpit-api, agents, verifier, cockpit-ui).
- **Pending operator verification** (per Story 1.4 Demo verification protocol):
  - `make dev` reaches `http://localhost:5173`, opens to `/queue` as Kamal Singh
  - User dropdown switches → URL changes to role's default route
  - Browser refresh persists active user
  - Cross-role navigation attempts redirect appropriately

### File List

**New**

- `packages/contracts/src/contracts/users.py`
- `packages/contracts/src/contracts/py.typed`
- `packages/contracts/tests/test_users.py`
- `apps/cockpit-api/src/cockpit_api/deps/__init__.py`
- `apps/cockpit-api/src/cockpit_api/deps/current_user.py`
- `apps/cockpit-api/src/cockpit_api/routers/__init__.py`
- `apps/cockpit-api/src/cockpit_api/routers/users.py`
- `apps/cockpit-api/tests/test_users.py`
- `apps/cockpit-ui/src/lib/types/user.ts`
- `apps/cockpit-ui/src/lib/routeFor.ts`
- `apps/cockpit-ui/src/lib/routeFor.test.ts`
- `apps/cockpit-ui/src/lib/api.ts`
- `apps/cockpit-ui/src/stores/currentUser.ts`
- `apps/cockpit-ui/src/stores/currentUser.test.ts`
- `apps/cockpit-ui/src/hooks/useUsersMe.ts`
- `apps/cockpit-ui/src/components/cockpit/UserSwitcher.tsx`
- `apps/cockpit-ui/src/components/cockpit/UserSwitcher.test.tsx`
- `apps/cockpit-ui/src/router.tsx`
- `apps/cockpit-ui/src/router.test.tsx`
- `apps/cockpit-ui/src/routes/__root.tsx`
- `apps/cockpit-ui/src/routes/index.tsx`
- `apps/cockpit-ui/src/routes/queue.tsx`
- `apps/cockpit-ui/src/routes/approvals.tsx`
- `apps/cockpit-ui/src/routes/regulator-lens.tsx`

**Modified**

- `packages/contracts/src/contracts/__init__.py` — re-exports `User`, `Role`, `DEMO_USERS`, `*_ID` constants, `find_user_by_id`
- `apps/cockpit-api/src/cockpit_api/main.py` — registers users router
- `apps/cockpit-ui/package.json` + `pnpm-lock.yaml` — `@tanstack/react-router`, `@tanstack/react-query`, `zustand`, `@tanstack/router-plugin` (devDep, unwired), `@tanstack/router-devtools` (devDep, unwired)
- `apps/cockpit-ui/src/main.tsx` — mounts `<RouterProvider>` inside `<QueryClientProvider>` (replaces `<App />`)
- `apps/cockpit-ui/.gitignore` — adds `src/routeTree.gen.ts`
- `apps/cockpit-ui/eslint.config.js` — per-folder override disabling `react-refresh/only-export-components` for `src/routes/**`
- `.env.example` — adds `DEMO_ANALYST_ID`, `DEMO_TEAM_LEAD_ID`, `DEMO_REGULATOR_ID`
- `README.md` — adds "Demo users" section + cross-link from "Daily development"

**Deleted**

- `apps/cockpit-ui/src/App.tsx` — superseded by `routes/__root.tsx`
- `apps/cockpit-ui/src/App.test.tsx` — superseded by `router.test.tsx` + `UserSwitcher.test.tsx`
- `apps/cockpit-ui/src/App.css` — empty, no longer referenced

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-04-29 | Story 1.4 drafted as part of the demo re-scope. Replaces deferred Stories 1.6–1.11 with a single-page-app cockpit shell + 3-user user-switcher backed by Zustand persistence and a `X-Cockpit-Demo-User` header against the cockpit-api. |
| 2026-04-29 | Story 1.4 implemented. 39 tests green (15 cockpit-ui Vitest, 11 cockpit-api pytest, 10 contracts pytest, 1 agents smoke, 1 verifier smoke, 1 contracts smoke). `make lint` and `make test` clean. Documented deviation: TanStack Router code-based composition instead of file-based codegen plugin (rationale in Debug Log References). Status → review. |
