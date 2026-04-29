# Story 1.10: Empty cockpit shell with auth-protected routes

Status: ready-for-dev

## Story

As an authenticated KYC Analyst,
I want to see a recognizable cockpit shell with the six-zone scaffold and "marble and spring flowers" visual language,
So that the foundation is visible and ready for subsequent epics to fill in.

## Acceptance Criteria

1. **AC1 — Six-zone layout renders at `/t/{tenant_id}/queue`** for an authenticated KYC Analyst:
   - **Top Bar** (full width, 48 px): displays tenant indicator, env badge ("dev" / "staging" / "prod"), placeholder ⌘K hint (not interactive yet — Story 4.9), notifications bell (silent in MVP, Story 4.10 makes it operational), user display name, sign-out button.
   - **Queue Rail** (left, 260 px fixed; collapses to 64 px mini at viewport `< 1536 px`): empty list with the empty-state copy "No cases in queue · you're caught up" centered, `ink-tertiary` color.
   - **Case Canvas** (center, `flex-1`): empty state "No case selected · pick one from the queue" with `ink-tertiary` text. Canvas does NOT scroll yet — empty.
   - **Agent Copilot Pane** (right, 320 px fixed): hidden until a case is opened (UX spec: "Hidden until case opens; never rendered empty"). For MVP shell, render as a 320 px reserved column with subtle `vein-soft` left border but no content; or hide it entirely until Epic 4. **Pick: render the column, no content** — more honest about the future layout. Document the choice.
   - **Decision Zone** (bottom of Canvas, full canvas width, 64 px collapsed): collapsed empty placeholder with "No decision pending" hint; `vein-soft` top border.
   - **Bottom Ribbon** (full width, 32 px): displays system-wide agent pulse placeholder (silent — `ink-ghost` "All systems quiet"), per-case SLA placeholder, quick actions placeholder.
2. **AC2 — Tailwind 4 `@theme` tokens are applied** (UX-DR1) — every color, spacing, radius, shadow, motion duration is sourced from the Tailwind 4 `@theme` directive in `apps/cockpit-ui/src/styles/tokens.css`. No hex literals, no `rgb(...)`, no inline-stat magic numbers in component code (eslint-rule guarded).
3. **AC3 — Typography hierarchy follows UX-DR2** — Inter (UI default 14 px), JetBrains Mono (case IDs / hashes / timestamps), Source Serif 4 (Zen-mode body — wired but not used here). All three fonts self-hosted under `apps/cockpit-ui/public/fonts/` (no Google Fonts CDN). `tabular-nums` enabled globally on monospace.
4. **AC4 — Spacing/radii/shadows follow UX-DR3, UX-DR4** — 4 px base grid; radius scale (none, sm-4, md-6, lg-8, full); shadow scale (sm/md/lg/modal). Documented in `tokens.css`.
5. **AC5 — Three motion utilities exported from `lib/motion.ts`** (UX-DR11):
   - `motion-snap` (100 ms, ease-out)
   - `motion-ease` (250 ms, `cubic-bezier(0.22, 1, 0.36, 1)`)
   - `motion-reveal` (300 ms, ease-in-out)
   - `motion-seal` (400 ms, ease-out) — author the fourth as well per UX spec; even though "three" is in the AC text, the motion vocabulary is four. Document the discrepancy via tests.
   - All Framer Motion variants use these tokens; bare ms numbers in component code are eslint-banned.
6. **AC6 — Persistent, high-contrast focus indicator on every keyboard-navigable element** (UX-DR12, NFR-AC5): `focus-ring` (2 px solid `#2563EB`, 2 px offset). Implemented via global CSS `:focus-visible` rule in `base.css`; never overridden.
7. **AC7 — Tab navigation traverses every interactive element**: from page load, repeated `Tab` presses move focus through Top Bar items (env badge → palette hint → bell → user → sign-out) → Queue Rail (empty, so skipped) → Decision Zone (collapsed, skipped if no interactive children) → Bottom Ribbon → back to top. **No element is keyboard-trapped**. Verified by Playwright keyboard test.
8. **AC8 — Role-gated routes**: cockpit-ui's `_auth.tsx` route layout enforces:
   - On render, calls `GET /t/{tenant_id}/v1/me` to load the current `Session` (this story creates a minimal `me` endpoint in cockpit-api).
   - If session role is `kyc_analyst` → show shell.
   - If session role is `team_lead` → redirect to `/t/{tenant_id}/approvals` (route exists as a stub page; full impl Story 10.1).
   - If session role is `internal_auditor` → redirect to `/t/{tenant_id}/audit` (stub page; full impl Story 9.3).
   - If session role is `cco` → redirect to `/t/{tenant_id}/portfolio` (stub page; full impl Story 10.4).
   - **Other roles or no session** → redirect to `/t/{tenant_id}/login`.
   - For MVP cockpit shell, the **Analyst** path is the only fully-rendered route; the other role-redirect targets are stub pages that show "Welcome <role> — your zone lands in Epic <N>."
9. **AC9 — Sign-out works**: Top Bar sign-out button calls `POST /t/{tenant_id}/auth/logout` (Story 1.6 endpoint), then clears any client-side state (Zustand stores) and navigates to `/t/{tenant_id}/login`.
10. **AC10 — Direct unauthenticated access to `/t/{tenant_id}/queue` redirects to `/t/{tenant_id}/login`** with `?return_to=/t/{tenant_id}/queue`. Re-auth lands the user back on `/queue` (Story 1.9 plumbing).
11. **AC11 — Hostile role test**: a session with role `team_lead` requesting `/t/{tenant_id}/queue` is **redirected client-side to `/approvals`**, AND the cockpit-api endpoint backing the queue fetch (when it lands in Epic 2) returns 403 — defense in depth. For THIS story (no queue endpoint exists yet), only the client-side redirect is verifiable; document the API-side gate as a Story 2.x dependency.
12. **AC12 — Crumb trail above the Case Canvas** (UX-DR navigation pattern) shows context — for empty queue route, render "Queue · 0 cases" in `text-xs ink-tertiary`.

## Tasks / Subtasks

- [ ] **Task 1 — Tailwind 4 + tokens.css** (AC: #2, #3, #4)
  - [ ] Subtask 1.1 — `apps/cockpit-ui/src/styles/tokens.css` declares the marble-and-spring-flowers palette via Tailwind 4 `@theme`:
    ```css
    @theme {
      --color-surface-pure: #FFFFFF;
      --color-surface-warm: #FAFAF9;
      --color-surface-sunken: #F4F4F5;
      --color-vein-soft: #E4E4E7;
      --color-vein-strong: #D4D4D8;
      --color-ink-primary: #0A0A0A;
      --color-ink-secondary: #52525B;
      --color-ink-tertiary: #71717A;
      --color-ink-ghost: #A1A1AA;
      --color-conf-high: #059669;
      --color-conf-med-high: #65A30D;
      --color-conf-medium: #D97706;
      --color-conf-low: #DC2626;
      --color-focus-ring: #2563EB;
      /* spring-flower agent hues (used per-agent in later epics) */
      --color-agent-supervisor: #C7D2FE;
      --color-agent-document-intelligence: #D9F99D;
      --color-agent-entity-verification: #FECDD3;
      --color-agent-ubo-graph: #BAE6FD;
      --color-agent-screening: #FDE68A;
      --color-agent-risk-scoring: #99F6E4;
      --color-agent-writing: #DDD6FE;
      --color-agent-cockpit-chat: #FED7AA;

      /* spacing 4 px base */
      --spacing-0: 0;
      --spacing-1: 0.25rem;
      --spacing-2: 0.5rem;
      --spacing-3: 0.75rem;
      --spacing-4: 1rem;
      --spacing-5: 1.25rem;
      --spacing-6: 1.5rem;
      --spacing-8: 2rem;
      --spacing-10: 2.5rem;
      --spacing-12: 3rem;
      --spacing-16: 4rem;
      --spacing-20: 5rem;

      /* radius */
      --radius-none: 0;
      --radius-sm: 4px;
      --radius-md: 6px;
      --radius-lg: 8px;
      --radius-full: 9999px;

      /* shadows */
      --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.04);
      --shadow-md: 0 2px 4px 0 rgb(0 0 0 / 0.06);
      --shadow-lg: 0 4px 10px 0 rgb(0 0 0 / 0.08);
      --shadow-modal: 0 12px 24px 0 rgb(0 0 0 / 0.12);

      /* fonts */
      --font-sans: 'Inter', system-ui, sans-serif;
      --font-mono: 'JetBrains Mono', 'Courier New', monospace;
      --font-serif: 'Source Serif 4', Georgia, serif;
    }
    ```
  - [ ] Subtask 1.2 — Self-host fonts: download Inter Variable, JetBrains Mono Variable, Source Serif 4 Variable WOFF2; place in `apps/cockpit-ui/public/fonts/`. Add `@font-face` declarations in `tokens.css` referencing them with `font-display: swap`.
  - [ ] Subtask 1.3 — Configure Tailwind breakpoints in `tailwind.config.ts` per UX spec:
    ```ts
    screens: { md: '1366px', lg: '1536px', xl: '1920px', '2xl': '2560px' }
    ```
  - [ ] Subtask 1.4 — `apps/cockpit-ui/src/styles/base.css` global CSS: `:focus-visible { outline: 2px solid var(--color-focus-ring); outline-offset: 2px; }`. Disable default browser `outline: none` overrides. Body uses `font-sans` + `tabular-nums` on monospace via `code, pre, .mono { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }`.

- [ ] **Task 2 — Motion utilities** (AC: #5)
  - [ ] Subtask 2.1 — `apps/cockpit-ui/src/lib/motion.ts`:
    ```ts
    export const motion = {
      snap:    { duration: 0.1, ease: 'easeOut' },
      ease:    { duration: 0.25, ease: [0.22, 1, 0.36, 1] },
      reveal:  { duration: 0.3, ease: 'easeInOut' },
      seal:    { duration: 0.4, ease: 'easeOut' },
    } as const;

    // Honor prefers-reduced-motion
    export const reducedMotion = (m: typeof motion[keyof typeof motion]) =>
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
        ? { ...m, duration: 0 }
        : m;
    ```
  - [ ] Subtask 2.2 — ESLint custom rule (or simple regex check via `pnpm lint`) bans literal `ms` durations in component CSS / Framer Motion props. Document in code review checklist (Story 1.3 PR template — extend if needed).

- [ ] **Task 3 — Six-zone layout component** (AC: #1, #12)
  - [ ] Subtask 3.1 — `apps/cockpit-ui/src/components/cockpit/CockpitShell/index.tsx` is the layout shell. Uses CSS Grid:
    ```tsx
    <div className="grid h-screen grid-rows-[48px_1fr_32px]">
      <TopBar />
      <div className="grid grid-cols-[260px_1fr_320px] lg:grid-cols-[260px_1fr_320px] md:grid-cols-[64px_1fr_320px]">
        <QueueRail />
        <CaseCanvas>
          <Crumbtrail label="Queue · 0 cases" />
          <CaseCanvasEmpty />
          <DecisionZoneCollapsed />
        </CaseCanvas>
        <AgentCopilotPane />
      </div>
      <BottomRibbon />
    </div>
    ```
  - [ ] Subtask 3.2 — Each sub-component is a stub that owns its empty state per UX spec. Files:
    - `components/cockpit/TopBar/index.tsx`
    - `components/cockpit/QueueRail/index.tsx`
    - `components/cockpit/CaseCanvas/index.tsx`
    - `components/cockpit/AgentCopilotPane/index.tsx`
    - `components/cockpit/DecisionZone/index.tsx` (collapsed shell only)
    - `components/cockpit/BottomRibbon/index.tsx`
  - [ ] Subtask 3.3 — Each component file colocates `index.tsx` + `index.test.tsx` + (if needed) sub-files; per architecture#Structural Patterns "Bespoke cockpit: `apps/cockpit-ui/src/components/cockpit/<Component>/`".

- [ ] **Task 4 — TanStack Router routes** (AC: #8, #10)
  - [ ] Subtask 4.1 — Install: `pnpm add @tanstack/react-router @tanstack/react-query @tanstack/router-devtools`. Set up file-based routing per architecture#F3.
  - [ ] Subtask 4.2 — Routes:
    - `apps/cockpit-ui/src/routes/__root.tsx` — root layout (just an outlet + dev tools).
    - `apps/cockpit-ui/src/routes/login.tsx` — placeholder login page that just shows "Sign in via your bank IdP" + button → `window.location.assign(\`/t/${tenantId}/login\`)` (the cockpit-api OIDC route from Story 1.6). The browser then completes OIDC and lands at `/t/{tenant_id}/queue`.
    - `apps/cockpit-ui/src/routes/_auth.tsx` — auth-protected layout: on render, fetch `GET /t/{tenant_id}/v1/me` via TanStack Query. On 401 → redirect (via Story 1.9's interceptor). On role mismatch → role-based redirect (AC8). On match → render `<Outlet />`.
    - `apps/cockpit-ui/src/routes/_auth/queue.tsx` — Analyst-only page; renders `<CockpitShell />`.
    - `apps/cockpit-ui/src/routes/_auth/approvals.tsx` — Team Lead stub.
    - `apps/cockpit-ui/src/routes/_auth/audit.tsx` — Auditor stub.
    - `apps/cockpit-ui/src/routes/_auth/portfolio.tsx` — CCO stub.
  - [ ] Subtask 4.3 — Tenant id is sourced from path. Use TanStack Router's path-param API; do NOT hardcode.

- [ ] **Task 5 — Cockpit-api `GET /t/{tenant_id}/v1/me`** (AC: #8)
  - [ ] Subtask 5.1 — `apps/cockpit-api/src/cockpit_api/routers/users.py` (NEW):
    ```python
    @router.get("/me", response_model=MePayload)
    async def me(
      session: Session = Depends(require_session),
      _ = Depends(require_role(Role.KYC_ANALYST, Role.TEAM_LEAD, Role.CCO, Role.INTERNAL_AUDITOR, Role.TENANT_ADMIN, Role.API_CONSUMER)),
    ):
        return MePayload(user_id=session.user_id, role=session.role, display_name=...)
    ```
  - [ ] Subtask 5.2 — Mount at `/t/{tenant_id}/v1/me`. Add `MePayload` Pydantic to `contracts.session` (or new `contracts.me`).

- [ ] **Task 6 — Sign-out flow** (AC: #9)
  - [ ] Subtask 6.1 — `TopBar` sign-out button → calls `POST /t/{tenant_id}/auth/logout` via `apiClient.POST`. On success → navigate to `/t/{tenant_id}/login`.

- [ ] **Task 7 — i18n integration point** (AC: prerequisite for Story 1.11)
  - [ ] Subtask 7.1 — Wrap visible strings in placeholder `t('...')` calls — even though `react-i18next` itself is wired in Story 1.11. **Document in this story**: every `t('...')` key used here must be present in Story 1.11's `en/common.json`. Suggested keys: `cockpit.queue.empty`, `cockpit.canvas.empty`, `cockpit.decision.placeholder`, `cockpit.signout`, `cockpit.crumbtrail.queue_count`.
  - [ ] Subtask 7.2 — Until Story 1.11, `t()` is a passthrough function that returns the default text — define as `const t = (_key: string, fallback: string) => fallback;` in a module that Story 1.11 will replace.

- [ ] **Task 8 — Tests** (AC: #6, #7, #11)
  - [ ] Subtask 8.1 — `apps/cockpit-ui/src/components/cockpit/CockpitShell/index.test.tsx`:
    - Render `<CockpitShell />`. Assert each zone is present with the empty-state copy.
    - Assert focus ring renders on `Tab` press (use `userEvent.tab()`).
    - Snapshot test of the layout.
  - [ ] Subtask 8.2 — Playwright e2e (`apps/cockpit-ui/tests/e2e/auth-routing.spec.ts`):
    - Unauthenticated → `/t/{tenant_id}/queue` redirects to login.
    - Auth as analyst → land on `/queue` shell.
    - Auth as team_lead → redirect to `/approvals` stub.
    - `Tab` traversal hits every Top Bar button and Bottom Ribbon item.
    - Sign-out → land on `/login`.
  - [ ] Subtask 8.3 — `apps/cockpit-ui/tests/e2e/a11y.spec.ts` (axe-core integrated; UX#Testing Strategy):
    - Run axe against the empty `<CockpitShell />` — expect 0 violations.
    - Verify focus indicator visible at 4.5:1 contrast against the surface.
  - [ ] Subtask 8.4 — `apps/cockpit-api/tests/integration/test_me_endpoint.py`:
    - 200 with valid session, returns `MePayload`.
    - 401 without session.
    - 401 with expired session (cross-validates Story 1.9).

## Dev Notes

### UX context (binding)

[Source: ux-design-specification.md#Spacing & Layout Foundation — Cockpit layout — fixed-dimension zones]
- Top Bar: 48 px tall.
- Queue Rail: 260 px (collapses to 64 px mini at < 1536 px viewport).
- Case Canvas: `flex-1`.
- Agent Copilot Pane: 320 px (always reserved).
- Decision Zone: 280 px expanded / 64 px collapsed.
- Bottom Ribbon: 32 px.

[Source: ux-design-specification.md#Color System]
- "Marble and spring flowers" palette codified above.
- Confidence bands: emerald / lime / amber / red — never used in this story (no agent data) but tokens MUST be present for later epics.

[Source: ux-design-specification.md#Typography System] — Inter (UI), JetBrains Mono (data density), Source Serif 4 (Zen-mode body — UX-DR locked here, used in Epic 8). All self-hosted.

[Source: ux-design-specification.md#Motion tokens] — four tokens; this story exports them. AC text says "three motion utilities" (per epic story); code provides four (per UX spec). The fourth (`motion-seal`) is locked here even though it's used only on commit (Epic 7).

[Source: ux-design-specification.md#Accessibility Considerations] — focus ring `#2563EB`, 2 px solid, 2 px offset. Persistent on every keyboard-navigable element.

[Source: ux-design-specification.md#Empty States]
- Queue Rail empty: "No cases in queue · you're caught up" + small icon, centered, `ink-tertiary`.
- Agent Copilot empty: "Open a case to see the mesh at work" — but UX rule says hide when empty; for THIS story, render the column with no content so the layout is visible to evaluators.

[Source: ux-design-specification.md#Navigation Patterns — Role-based auto-route on login] — Analyst → Queue Rail; Team Lead → Approval Queue; Auditor → Regulator Lens; CCO → Portfolio Dashboard. AC8 implements this client-side.

[Source: ux-design-specification.md#Copy & Voice Patterns] — Direct, no greetings ("Queue · 0 cases", not "Hi Priya!"), no emoji, professional register, sentence case.

### Architectural context

[Source: architecture.md#F2] — Zustand for client UI state (mode, palette, focus stores). For THIS story, only stub stores are created (e.g., `modeStore` with default mode "investigation"); they're populated in Epic 4.

[Source: architecture.md#F3] — TanStack Router file-based, type-safe.

[Source: architecture.md#F1] — TanStack Query for server state. The `me` fetch is a TanStack Query.

[Source: architecture.md#F7] — Tailwind 4 `@theme` is single source of truth for design tokens.

[Source: architecture.md#F8] — `eslint-plugin-jsx-a11y` (Story 1.2 wired), `axe-core` in Playwright (this story exercises).

[Source: architecture.md#F9] — `react-i18next` scaffolding lands in Story 1.11; this story uses placeholder `t()` so the migration is painless.

[Source: architecture.md#NFR-CP3 — minimum viewport] — 1366 × 768. Below that, banner: "This cockpit is optimized for 1366 × 768 or larger." Implement the banner in this story OR defer to a polish task — recommendation: implement here so the shell ships with viewport discipline.

### Critical pitfalls to avoid

1. **No emoji in any visible string** (UX#Copy & Voice). Even in placeholders. Lint check via custom regex `/[\u{1F000}-\u{1FFFF}]/u` against `apps/cockpit-ui/src/**/*.{ts,tsx}`.
2. **Fonts MUST be self-hosted** (UX#Typography System privacy + reliability). No Google Fonts CDN. WOFF2 in `public/fonts/`.
3. **Tokens-only**: NO hex literals or rgb() in component code. ESLint rule `no-restricted-syntax` against `Literal[value=/^#[0-9a-f]{3,8}$/i]` in component files (allowed in `tokens.css` only).
4. **`outline: none` is BANNED** without a custom focus indicator that meets NFR-AC5. ESLint rule.
5. **Don't render an empty Agent Copilot Pane with copy** — UX explicitly says "Hidden until case opens; never rendered empty." We render the *column* (for layout), but the inner content is empty. NOT "Open a case…" placeholder text — that's misleading.
6. **No icon-only buttons** without `aria-label` and tooltip (UX#Button Hierarchy). The Top Bar bell is icon-only — give it `aria-label="Notifications"` and a Radix Tooltip.
7. **Role-based redirect**: must NOT happen on the server (cockpit-api). It happens client-side after `/me` returns the role. This decouples the API surface from UI routing decisions. (Server-side, the cockpit-api just enforces RBAC per route.)
8. **Don't pre-render the cockpit shell for non-Analyst roles**. Stub pages for `team_lead`, `internal_auditor`, `cco` are placeholder content only.
9. **Tab order MUST be logical** (top-down, left-to-right). Verify with `userEvent.tab()` in tests; don't rely on tabindex=0 default ordering being correct without checking.
10. **Don't use stale fonts**: if a developer's machine has older Inter cached, the CSS must `@font-face` *load* the variable WOFF2 with `font-display: swap` and trust the browser to fall back to system-ui until loaded. Verify Lighthouse "no FOIT" at first paint.
11. **Soft-dim convention** (UX#Soft-dim) — when overlays open elsewhere in the app, the canvas dims to 70%. Establish the CSS pattern (`opacity-70` on `<main>` when `data-overlay-open="true"`) here so Epic 4+ overlays slot in without rewiring.
12. **`prefers-reduced-motion` is ALWAYS honored**: motion utilities collapse to 0 ms. Test with `media={prefers-reduced-motion: reduce}` query in jsdom (or skip motion in tests entirely).

### Architecture patterns relevant here

[Source: architecture.md#Anti-Patterns to Refuse] — most don't apply yet, but:
- ❌ `camelCase` JSON over the wire — `MePayload` Pydantic uses `snake_case`; cockpit-ui consumes via `openapi-typescript` types (Story 2.11). Until 2.11 lands, the `me` endpoint is the FIRST API call from cockpit-ui to cockpit-api — write the fetch by hand (not via openapi-fetch yet) but use `snake_case` field names.
- ❌ Loading flag in Zustand — use TanStack Query's `isPending`/`isFetching`. The `me` fetch must NOT introduce a `loading: boolean` Zustand store.

[Source: architecture.md#Process Patterns — Loading state] — TanStack Query state only.

[Source: architecture.md#Process Patterns — Error surfacing] — Three channels: inline (most), toast (cross-cutting), full-page error boundary (catastrophic). For `me` 401, the interceptor (Story 1.9) handles redirect. Other errors: inline if possible; full-page boundary only for catastrophic.

### Project Structure Notes

Creates (frontend):
- `apps/cockpit-ui/src/styles/tokens.css`
- `apps/cockpit-ui/src/styles/base.css`
- `apps/cockpit-ui/public/fonts/{Inter-Variable.woff2, JetBrainsMono-Variable.woff2, SourceSerif4-Variable.woff2}`
- `apps/cockpit-ui/src/lib/motion.ts`
- `apps/cockpit-ui/src/lib/i18n.ts` (placeholder passthrough — replaced in Story 1.11)
- `apps/cockpit-ui/src/routes/__root.tsx`
- `apps/cockpit-ui/src/routes/login.tsx`
- `apps/cockpit-ui/src/routes/_auth.tsx`
- `apps/cockpit-ui/src/routes/_auth/queue.tsx`
- `apps/cockpit-ui/src/routes/_auth/approvals.tsx`
- `apps/cockpit-ui/src/routes/_auth/audit.tsx`
- `apps/cockpit-ui/src/routes/_auth/portfolio.tsx`
- `apps/cockpit-ui/src/components/cockpit/CockpitShell/{index.tsx, index.test.tsx}`
- `apps/cockpit-ui/src/components/cockpit/TopBar/{index.tsx, index.test.tsx}`
- `apps/cockpit-ui/src/components/cockpit/QueueRail/{index.tsx, index.test.tsx}`
- `apps/cockpit-ui/src/components/cockpit/CaseCanvas/{index.tsx, index.test.tsx}`
- `apps/cockpit-ui/src/components/cockpit/AgentCopilotPane/{index.tsx, index.test.tsx}`
- `apps/cockpit-ui/src/components/cockpit/DecisionZone/{index.tsx, index.test.tsx}`
- `apps/cockpit-ui/src/components/cockpit/BottomRibbon/{index.tsx, index.test.tsx}`
- `apps/cockpit-ui/src/stores/modeStore.ts` (Zustand stub, default mode = `investigation`)
- `apps/cockpit-ui/src/hooks/useMe.ts` (TanStack Query hook)
- `apps/cockpit-ui/tests/e2e/auth-routing.spec.ts`
- `apps/cockpit-ui/tests/e2e/a11y.spec.ts`

Creates (backend):
- `apps/cockpit-api/src/cockpit_api/routers/users.py` (`GET /me`)
- `apps/cockpit-api/tests/integration/test_me_endpoint.py`
- `packages/contracts/src/contracts/me.py` (`MePayload`)

Modifies:
- `apps/cockpit-ui/tailwind.config.ts` — `screens` breakpoints + content paths.
- `apps/cockpit-ui/src/main.tsx` — wrap in TanStack Router + TanStack QueryClientProvider; install i18n.ts placeholder; load tokens.css + base.css.
- `apps/cockpit-api/src/cockpit_api/main.py` — mount `users` router under `/t/{tenant_id}/v1`.

This story does NOT yet:
- Wire `react-i18next` (Story 1.11).
- Implement keyboard shortcuts (Story 4.2 / 4.9).
- Implement the command palette (Story 4.9).
- Implement notifications (Story 4.10).
- Render any case data (Epic 2+).
- Render any agent data (Epic 3+).

### References

- [Source: architecture.md#F1, F2, F3, F7, F8, F9]
- [Source: architecture.md#Structural Patterns] — `components/cockpit/<Component>/{index.tsx, *.test.tsx}` layout.
- [Source: architecture.md#Frontend Architecture — Cockpit-ui internal layout]
- [Source: architecture.md#Anti-Patterns to Refuse]
- [Source: ux-design-specification.md#Color System]
- [Source: ux-design-specification.md#Typography System]
- [Source: ux-design-specification.md#Spacing & Layout Foundation]
- [Source: ux-design-specification.md#Motion tokens]
- [Source: ux-design-specification.md#Accessibility Considerations]
- [Source: ux-design-specification.md#Navigation Patterns — Role-based auto-route]
- [Source: ux-design-specification.md#Copy & Voice Patterns]
- [Source: ux-design-specification.md#Empty States]
- [Source: prd.md#NFR-CP3] — minimum viewport 1366 × 768.
- [Source: prd.md#NFR-AC1, AC4, AC5] — WCAG 2.2 AA, focus indicators.
- [Source: epics.md#Story 1.10: Empty cockpit shell with auth-protected routes]

### Previous Story Intelligence

[Source: 1-1-bootstrap-the-polyglot-monorepo-from-the-canonical-scaffold.md]
- Vite + React 19 + TS strict + Tailwind 4 + shadcn/ui + Radix + Framer + Lucide installed.
- TS strict enforced: any/implicit/etc. blocks merge.

[Source: 1-2-one-command-local-development-environment.md]
- Vitest is wired; tests run via `pnpm test`.
- ESLint + Prettier are wired; `--max-warnings=0` is the gate.
- "Hello cockpit" placeholder in `App.tsx` from Story 1.2 — REPLACED by `<CockpitShell />` in this story.

[Source: 1-6-oidc-authentication-with-cookie-session.md]
- OIDC login flow at `/t/{tenant_id}/login` (cockpit-api). Cockpit-ui's `/login` route navigates the browser there.
- Sign-out endpoint `POST /t/{tenant_id}/auth/logout` exists.

[Source: 1-7-deny-by-default-rbac-dependency.md]
- `Depends(require_role(...))` is the canonical role-check on cockpit-api routes. The `me` endpoint accepts ANY of the six roles (it's the role-discovery endpoint).

[Source: 1-8-tenant-scoping-middleware.md]
- All `/t/{tenant_id}/...` routes require valid path tenant. The `_auth.tsx` layout reads tenant_id from path params.

[Source: 1-9-session-inactivity-timeout.md]
- 401 `type=session_expired` interceptor in `lib/api.ts` redirects to login with `return_to`.
- After re-auth, cockpit-ui consumes `localStorage.getItem('cockpit:returnTo')` to navigate back. **Implement that read in `_auth.tsx` mount-effect**.

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
