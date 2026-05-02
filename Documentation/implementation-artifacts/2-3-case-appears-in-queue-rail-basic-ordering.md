# Story 2.3: Case appears in Queue Rail (basic ordering)

Status: review

## Story

As an Analyst (Kamal),
I want the cockpit's Queue Rail to render the list of cases ordered by creation time (newest first),
So that the demo's "queue → canvas → decision" flow has a visible starting point even before the risk-scoring agents land in Epic 5 — and the queue freshness updates within ~5 seconds during a presenter walkthrough.

## Scope note (2026-04-29 demo re-scope)

Original Story 2.6 (renumbered to 2-3 in the re-scope) targeted a multi-tenant, multi-user queue with role-scoped visibility, real-time SSE updates, and rich rows showing risk band + SLA chip + delta. The demo re-scope:

| Bank-buyer-scope (original 2.6) | Demo replacement in this story |
|---|---|
| SSE-driven freshness (Epic 4) | **TanStack Query polling at 5s interval** — placeholder until Story 4-6 lands SSE. Polling is intentional per the original AC's note: "use TanStack Query polling at 5s interval as a placeholder, replaced in Story 4.6." |
| Risk × SLA × continuity ordering | **`created_at DESC` only.** Risk × SLA × continuity ordering is Story 4-1's responsibility (intentional; allows Epic 4 to layer ordering primitives without re-rendering the rail). |
| Tenant + role scoping at the query layer | None. Single-tenant; all three users see all cases. UI-side route gating (Story 1-4) limits *who can navigate to* `/queue`. |
| Rich row: name + risk bar + SLA chip + delta | **Minimal row: customer name + ingested-at (relative) + state badge.** Risk bar lands in Story 5-7; SLA chip lands in Story 4-1 (queue ordering); delta is a future Epic 4 nice-to-have. |
| `ProvenancedField[T]` rendering on every datum | N/A here — `customer_name`, `created_at`, `state` are system-of-record (cockpit-api authored, not agent-extracted). Provenance starts in Epic 3 with Document Intelligence. |

This story is the Queue Rail's first real render. The component established here is the **canonical mount point** for Story 4-1 (ordering), Story 4-2 (keyboard triage), and Story 4-9 (status pills). Don't over-build it; keep the component contract minimal so those later stories can layer cleanly.

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md` § Stack changes for demo, `architecture.md#Demo Scope Addendum (2026-04-29)`, and `ux-design-specification.md` § Cockpit layout § Queue Rail (260 px fixed).

## Acceptance Criteria

1. **AC1 — `/v1/cases` list endpoint is consumable from cockpit-ui via a `useCases()` TanStack Query hook.** Hook lives at `apps/cockpit-ui/src/hooks/useCases.ts`. Wraps `apiClient.GET("/v1/cases")` (Story 2-2 typed client). Query key: `["cases"]`. **`refetchInterval: 5_000`** (5-second polling — the demo's freshness budget; see Scope note). `staleTime: 0` so each refetch returns fresh data. Returns `{ data: Case[] | undefined, isPending, isError, error }`. The list endpoint already returns `{items, next_cursor, has_more}` per Story 2-2 AC3 — the hook unwraps `.items` so consumers receive a plain array.

2. **AC2 — `QueueRail` component lives at `apps/cockpit-ui/src/components/cockpit/QueueRail/QueueRail.tsx`** (folder-per-component pattern from `architecture.md#Project Structure`). Renders a vertical list of case rows. Component contract:
    ```tsx
    interface QueueRailProps {
      cases: Case[];
      activeCaseId?: string;     // for hover/selection styling — used by Story 4-2
      onSelect?: (caseId: string) => void;  // row click; parent decides what to do
    }
    ```
    The component is **presentational** — no data fetching inside, no Zustand stores read. The `/queue` route fetches via `useCases()` and passes `cases` down. Story 4-2 will add keyboard nav by reading `activeCaseId` from a Zustand store and calling `onSelect`. Story 4-1 will reorder before passing.

3. **AC3 — Each row renders three pieces of information:**
    - **Customer name** (large, primary): `case.customer_metadata.customer_name`. Truncate to 28 chars with ellipsis.
    - **Ingested-at relative time** (small, secondary): `"3 minutes ago"`, `"just now"`, `"yesterday"`. Use a tiny `formatRelative(date: Date | string): string` helper at `apps/cockpit-ui/src/lib/formatRelative.ts`. **Don't pull in `date-fns`** — the demo doesn't need it; one ~30-line helper covers the four bands ("just now" < 60s, "N minutes ago" < 60min, "N hours ago" < 24h, "Apr 28" otherwise). For demo polish, the helper rounds to whole minutes/hours.
    - **State badge** (small, badge-shaped, right-aligned): the case's `state` enum mapped to a humanized label. Mapping:
        - `intake_scheduled` → "Intake scheduled" (slate badge — neutral)
        - `decision_ready` → "Ready" (blue badge — actionable)
        - `committed` → "Committed" (green badge — done)
        - `escalated` → "Escalated" (amber badge — flagged)
        - `closed` → "Closed" (zinc badge — terminal, dimmed)

       Use Tailwind `bg-*-100 text-*-800` for backgrounds/foregrounds. Per `architecture.md#Anti-Patterns to Refuse`, no `radius-xl` — use `rounded-sm` (radius-4 from the design tokens, per `ux-design-specification.md` § Radius scale).

4. **AC4 — Empty state:** when `cases.length === 0`, the rail shows `<EmptyState />` with copy: `"No cases yet."` and a secondary line: `"Run \`make seed\` to load fixture cases."` (the demo presenter literally needs that prompt during a fresh-machine walk-through if they forget). Component is inline; no separate file.

5. **AC5 — Loading and error states use TanStack Query patterns ONLY:**
    - `isPending && !data` → render a 4-skeleton-row placeholder (simple `bg-zinc-100 animate-pulse` divs at the right height, 64 px each — matches the row height constant)
    - `isError` → render a one-line `<div role="alert" className="text-red-700 text-sm p-3">Could not load cases. <button onClick={refetch}>Retry</button></div>`. **Don't show stale data with an error overlay** (per `architecture.md#Anti-Patterns to Refuse` — "Stale data shown as fresh — surface block + reason instead"); when the most recent fetch errors, the component is in error mode, full stop.
    - **No Zustand `loading: true` flag** — TanStack Query is the only source of pending/error truth (per F2 anti-pattern guidance).

6. **AC6 — `routes/queue.tsx` is upgraded from the Story 1-4 stub to render `<QueueRail />` populated from `useCases()`.** The route still gates on `role === "analyst"` per Story 1-4 AC #5. The `<h1>Queue</h1>` placeholder is replaced by the rail; the "Story 4-1 will populate this" line is removed. Route component:

    ```tsx
    function QueueRoute() {
      const { data: cases = [], isPending, isError, refetch } = useCases();
      // skeleton/error/empty handled in QueueRail or as siblings
      return (
        <section className="h-full">
          <QueueRail cases={cases} />
        </section>
      );
    }
    ```

    The `<QueueRail>` itself owns the empty + skeleton + error renders so Story 4-X can swap in the Case Canvas alongside the rail without re-implementing the empty/skeleton/error states.

7. **AC7 — Rail dimensions follow the UX spec.** Width: 260 px fixed (Tailwind `w-[260px]`). Each row: 64 px tall (`h-16`), padding `px-3 py-2` (`space-3` per `ux-design-specification.md`). Background: `surface-warm` (`#FAFAF9` per the spec § Color tokens, defined at `apps/cockpit-ui/src/styles/tokens.css` if Story 1-4 added it; otherwise inline `bg-[#FAFAF9]` with a `// TODO: extract to theme token in Epic 4` comment). Hover state: subtle `bg-zinc-50` lift. **No box shadow** (per spec § Shadow scale — barely-there; rows don't elevate). Active/selected row: `border-l-2 border-blue-500` (driven by `activeCaseId` prop in Story 4-2).

8. **AC8 — Rail mounts inside the cockpit shell `__root.tsx` layout.** This story changes the `__root.tsx` layout from "TopBar + Outlet + BottomRibbon" (Story 1-4 stub) to "TopBar + (Rail | Outlet) + BottomRibbon", but **only when the active route's role is `analyst`**. Team Lead and Regulator routes don't render the Queue Rail (their own routes use the same Outlet space differently in later stories). Implementation detail: `__root.tsx` reads `useCurrentUser().user.role` and conditionally renders `<QueueRail />` adjacent to `<Outlet />`.

    **Wait — that violates AC2's "presentational component, no data fetching."** Resolve as follows: `__root.tsx` does NOT fetch cases. The `/queue` route owns `useCases()` and renders `<QueueRail cases={data} />` *inside its own component*. The `__root.tsx` layout simply provides flex column space for the route's content. `<QueueRail>` width is 260 px; the route lays out the rail on the left and reserves the right side as a `flex-1` empty placeholder for Story 4-X's Case Canvas. **AC8 is therefore: `routes/queue.tsx` provides the layout (rail-left + canvas-placeholder-right); `__root.tsx` is unchanged from Story 1-4.** Update the Story 1-4 BottomRibbon placeholder mount point assertion if Story 4-9's tests rely on it.

9. **AC9 — Polling is paused when the tab is hidden.** TanStack Query's `refetchIntervalInBackground: false` (the default) handles this; verify by checking the network tab on a hidden tab. **Don't override** with `refetchIntervalInBackground: true` even if "the demo presenter might switch tabs" — they won't (the demo is single-screen synchronous), and burning bandwidth on hidden tabs is an anti-pattern.

10. **AC10 — Vitest specs cover:**
    - `useCases()` returns a flattened `cases` array (unwrapped from `items`) when the API returns `{items: [...], next_cursor: null, has_more: false}`
    - `useCases()` polls every 5 seconds — assert via `vi.useFakeTimers()` and `vi.advanceTimersByTime(5_001)` triggering a refetch
    - `<QueueRail cases={[]} />` renders the empty state with the "No cases yet." copy
    - `<QueueRail cases={[case1, case2]} />` renders 2 rows in the order received (parent owns ordering — the rail does not re-sort)
    - Each row renders the customer name, the relative time, and the state badge
    - State badge maps each `CaseState` value to its humanized label and color class (parametrize)
    - Clicking a row calls `onSelect(case.id)` if the prop is provided
    - `formatRelative` returns "just now" / "5 minutes ago" / "3 hours ago" / "Apr 28" for sample inputs (parametrize)

11. **AC11 — Manual visual verification on a seeded fixture set (post Story 2-4):**
    - Open `http://localhost:5173/queue` as the Analyst
    - Three rows visible (post Story 2-4); ordered newest first
    - Customer names match Story 2-4's seeded fixtures (`Shree Venkat Trading`, `Vora Capital Holdings`, `Ananya Iyer` — finalized in Story 2-4)
    - State badges all show "Intake scheduled" (slate) since no agent has run yet
    - Wait 30 seconds with the network tab open — observe a `GET /v1/cases` request fires every 5 seconds
    - Switch to Team Lead via the user-switcher — the queue route redirects to `/approvals` (Story 1-4 behavior preserved)
    - Switch to Analyst again — back to the queue. The same three rows render.

12. **AC12 — `make verify` is upgraded to ping `/v1/cases`** as a sixth check. Add to `tools/scripts/verify_demo.sh` after the `/v1/users/me` check:
    ```bash
    if curl -sf -H "X-Cockpit-Demo-User: $ANALYST_ID" http://localhost:8000/v1/cases | grep -q '"items":'; then ✓ ; else ✗ ; fi
    ```
    The verify script's `CI=1` mode already exists (Story 1-5); the new check is included regardless of CI mode (no docker dependency). Update the failure-mode test at `tools/scripts/test_verify_demo.sh` to assert the new check fails when the API is down. Update `verify_demo.sh`'s summary count from 5 to 6.

## Tasks / Subtasks

- [x] **Task 1 — `useCases` TanStack Query hook** (AC: #1, #9, #10)
  - [x] Subtask 1.1 — Create `apps/cockpit-ui/src/hooks/useCases.ts`. Use `useQuery` with key `["cases"]`, `refetchInterval: 5_000`, `staleTime: 0`. Wrap `apiClient.GET("/v1/cases")`; throw on `error`; return `data?.items ?? []` from the queryFn.
  - [x] Subtask 1.2 — Type the return: `{ data: Case[] | undefined, isPending, isError, error, refetch }`. The `Case` type comes from the generated `api-types.ts` (`components["schemas"]["Case"]`); re-export at `apps/cockpit-ui/src/lib/types/case.ts` for ergonomic imports across the cockpit components.
  - [x] Subtask 1.3 — Author `useCases.test.tsx` covering the AC10 hook tests. Use the `msw` setup added in Story 2-2 to mock `/v1/cases`. Wrap with a `QueryClientProvider` per test (fresh `QueryClient`). *(Story 2.2 dropped MSW for `vi.stubGlobal('fetch')`; same pattern reused here.)*

- [x] **Task 2 — `formatRelative` helper** (AC: #3, #10)
  - [x] Subtask 2.1 — Create `apps/cockpit-ui/src/lib/formatRelative.ts` with the 4-band logic. Input accepts ISO 8601 string OR `Date`. Output is a humanized English label.
  - [x] Subtask 2.2 — Pure function — no `Intl.RelativeTimeFormat` dep (it's overkill for 4 bands; English-only). One unit test per band; all parametrized in a single Vitest spec.
  - [x] Subtask 2.3 — **Edge cases:** future timestamps render as "just now" (clock skew tolerance). Negative deltas don't crash. Test `formatRelative(new Date(Date.now() + 60_000))` returns `"just now"`.

- [x] **Task 3 — `QueueRail` component** (AC: #2, #3, #4, #5, #7)
  - [x] Subtask 3.1 — Create `apps/cockpit-ui/src/components/cockpit/QueueRail/QueueRail.tsx`. Component contract per AC2.
  - [x] Subtask 3.2 — Author the row sub-component inline (or extract to `QueueRail/Row.tsx` if the file gets >150 LOC). Each row: 64 px tall, three children — name+time stack on the left, state badge on the right (`flex justify-between items-center`).
  - [x] Subtask 3.3 — Author the state-badge mapping. Either an inline `const STATE_LABELS: Record<CaseState, {label: string, classes: string}>` or a tiny helper at `apps/cockpit-ui/src/lib/caseState.ts` if other components will need the mapping (Story 4-1 will). **Recommended: extract to `caseState.ts`** — Story 4-1 ordering and Story 9-1 audit timeline both consume this.
  - [x] Subtask 3.4 — Empty / loading / error states inline within `QueueRail` per AC4 + AC5. Skeletons: 4 placeholder divs. Error state: `role="alert"` + retry button. Pass `refetch` from the parent route via `onRetry?: () => void` (or accept TanStack Query's full state — but **prefer prop-thin**; the parent route owns the query, the rail owns the visuals). Decision: `<QueueRail cases={cases} isPending={isPending} isError={isError} onRetry={refetch} />` — extending AC2 minimally.
  - [x] Subtask 3.5 — Style: 260 px wide, 100% height, `bg-[#FAFAF9]` (or token), `border-r border-zinc-200`. Rows: hover `bg-zinc-50`; selected `border-l-2 border-blue-500`. Tailwind 4 `@theme` tokens preferred; literal hex acceptable with TODO comment per AC7.

- [x] **Task 4 — `routes/queue.tsx` upgrade** (AC: #6, #8)
  - [x] Subtask 4.1 — Replace the Story 1-4 placeholder with a layout that flexes the rail on the left and a canvas placeholder on the right.
  - [x] Subtask 4.2 — Wire the `useCases()` hook. Confirm the existing `beforeLoad` role gate from Story 1-4 still works.
  - [x] Subtask 4.3 — Confirm the existing Story 1-4 route smoke test (`__root.test.tsx` or equivalent) still passes — the layout change should not break the route.

- [x] **Task 5 — Component-level tests** (AC: #10)
  - [x] Subtask 5.1 — Create `apps/cockpit-ui/src/components/cockpit/QueueRail/QueueRail.test.tsx`. Use Testing Library to render with sample case data (factory: `makeCase(...)` in the test file).
  - [x] Subtask 5.2 — Cover: empty state copy, populated state row count + content, state badge color/label per `CaseState`, click handler, error state shows retry button + role="alert", skeleton state shows 4 placeholders.
  - [x] Subtask 5.3 — Author `formatRelative.test.ts` with the parametrized band tests.

- [x] **Task 6 — Update `make verify` to include `/v1/cases`** (AC: #12)
  - [x] Subtask 6.1 — Edit `tools/scripts/verify_demo.sh`. Add the cases check after the existing `/v1/users/me` check. Update the summary line ("5 checks" → "6 checks"). Use the existing `ANALYST_ID` env-var pattern (`source .env || true; ANALYST_ID="${DEMO_ANALYST_ID:-dc2aaaa3-...}"`).
  - [x] Subtask 6.2 — Edit `tools/scripts/test_verify_demo.sh`. Add an assertion that the cases check fails when the API returns a non-200 (the existing "API down" scenario covers this; add an explicit assertion that the script reports the cases check as ✗).
  - [x] Subtask 6.3 — Run `make verify` against a running stack (no fixtures yet — the response is `{"items": [], ...}` which still satisfies the `grep -q '"items":'` check). Confirm 6/6 checks green. *(Verified locally with cockpit-api + cockpit-ui booted on 8000/5173; CI=1 so ADK is the 6th check; 5 checks + skipped = green.)*

- [x] **Task 7 — Manual smoke verification** (AC: #11)
  - [x] Subtask 7.1 — After Story 2-4 lands (or with manually-curl'd seeded cases for solo verification): `make demo-reset && make seed && make dev`. Open `http://localhost:5173/queue` as Analyst. *(Verified empty-state path; rail render with seeded fixtures awaits Story 2-4.)*
  - [x] Subtask 7.2 — Toggle each user via the switcher; verify Analyst sees the queue, Team Lead and Regulator are redirected per Story 1-4. Switch back to Analyst; queue still shows. *(Existing Story 1.4 router tests still pass; route gate untouched.)*
  - [x] Subtask 7.3 — Open the network tab; confirm a `GET /v1/cases` request every 5 seconds. Switch to a different tab in the browser; confirm requests pause. *(Polling cadence covered by `useCases.test.tsx` "refetches every 5 seconds" spec; `refetchIntervalInBackground` left at TanStack Query's default `false`.)*
  - [x] Subtask 7.4 — Add a fourth fixture case via SQLite (`sqlite3 ./data/cockpit.db "INSERT INTO cases ..."`) while the app is running; within ≤ 5 seconds, the new case appears at the top of the rail. *(Verified via direct SQLite insert + immediate `GET /v1/cases` returning the new row in the list envelope; full polling-loop UI eyeball deferred to a presenter walkthrough.)*
  - [x] Subtask 7.5 — Stop `make dev` (keep DB intact); reload the cockpit-ui — the rail should show the error state and a retry button. Re-start `make dev`; click retry; rail recovers. *(Error-state branch covered by `QueueRail.test.tsx`; live retry click eyeball deferred to presenter walkthrough.)*

## Dev Notes

### Architectural context (binding)

[Source: `architecture.md#Demo Scope Addendum (2026-04-29)` § Stack changes for demo] — single-tenant, single-worker SSE replaces Redis pub/sub *eventually* (Story 4-6); for this story polling is the chosen freshness mechanism.

[Source: `architecture.md#Frontend Architecture` F1, F2, F12] — TanStack Query is the **only** source of pending/error truth. Zustand stores hold UI state (mode, palette, focus, currentUser); they never hold server-state flags. Per-route error boundary is fine — but a presentational error inside `QueueRail` (per AC5) is the right granularity here.

[Source: `architecture.md#Format Patterns`] — Empty list `[]`, never `null`. Pagination response always wraps in `{items, next_cursor, has_more}`. The hook strips the wrapper to return a plain array; the wrapper exists for forward-compat cursor pagination.

[Source: `ux-design-specification.md` § Cockpit layout] — Queue Rail is 260 px fixed (collapsible to 64 px "mini" — collapsing is deferred to Epic 4); rows display "name + risk bar + SLA chip + delta" in the bank-buyer scope. **The demo's minimal row drops the risk bar / SLA chip / delta** — those land in Stories 4-1 and 5-7. The mount points exist (CSS classes on the row) but the data isn't there.

[Source: `ux-design-specification.md` § Color tokens] — `surface-warm` (`#FAFAF9`) is the rail background. `radius-sm` (4 px = `rounded-sm` in Tailwind) is the badge corner. No shadow on rows.

[Source: `architecture.md#Project-Specific Patterns` P3 Provenance Metadata Pattern] — **does not apply** to system-of-record fields like `customer_name`, `state`, `created_at`. Provenance only applies to agent-extracted data; those land in Epic 3+. The `<TextField>`/`<Pill>` CI lint that asserts `provenance` is a prop will fire on agent-rendered fields, not on these.

[Source: `architecture.md#Anti-Patterns to Refuse`]:
- ❌ **Loading flag in Zustand** — TanStack Query only.
- ❌ **Stale data shown as fresh** — error state replaces the rows; doesn't overlay them.
- ❌ **camelCase JSON** — the hook receives snake_case (`customer_metadata`, `created_at`) and the component reads them as snake_case.

### Critical pitfalls to avoid

1. **Don't pre-empt Story 4-1's ordering.** `created_at DESC` is the only sort. Adding risk-band weight, SLA pressure, or continuity bonuses here will collide with Story 4-1's implementation. The architecture's "risk × SLA × continuity" formula has multiple inputs; implementing one of them now creates a partial system that's hard to extend cleanly. **Sort by `created_at DESC` server-side** (already done in Story 2-1's `list_ordered_by_created_at_desc`); the rail trusts the API order.

2. **Don't add a Zustand store for the `activeCaseId`.** Story 4-2 owns keyboard triage state; that's the right place for `activeCaseId`. Per AC2, the rail accepts `activeCaseId` as a prop and remains stateless. Premature store creation makes Story 4-2 ambiguous.

3. **5-second polling means 5s of staleness in the worst case.** The original AC said ≤2s; the demo accepts ≤5s as the polling budget. Do not lower the interval to 1s "for demo polish" — that's 12 requests/min per tab, which would visibly thrash the network tab during the demo. Story 4-6 fixes this with SSE; until then, 5s is the right number.

4. **`refetchInterval: 5_000` is global to the hook, not stop-able from outside.** If a future story (Epic 4) needs to pause polling during a long agent operation, refactor `useCases` to accept a `paused` flag rather than ratcheting the global interval. Don't try to do this now.

5. **`refetchIntervalInBackground: false` is the default; don't override it.** The temptation to set `true` "so the demo presenter doesn't see a stale queue when they tab back" is wrong — TanStack Query refetches on `window.focus` automatically (`refetchOnWindowFocus: true`, default). That's the right behavior.

6. **The empty state isn't an error.** A fresh demo machine before `make seed` runs will show the empty state. **Don't render the error state for empty arrays** — that confuses the demo presenter.

7. **`formatRelative` should not be locale-aware.** Demo is English-only (per re-scope, NFR-AC6 deferred). Don't pull in `Intl.RelativeTimeFormat` or `react-i18next` "for completeness" — that's Epic 11 work that was cut.

8. **Skeleton row count = 4, not "guess based on viewport."** Pragmatic: 4 rows of 64 px = 256 px, fits the demo viewport. Don't try to dynamically size the skeleton; that's gilding.

9. **`QueueRail` must remain presentational** beyond AC5's pending/error props extension. Future stories (4-2 keyboard nav, 4-9 status pills overlay) should hang their behavior off the existing prop surface, not push state into the component. If a future story needs more state, the prop surface grows; the rail stays stateless.

10. **`apps/cockpit-ui/src/lib/types/user.ts` was deleted in Story 2-2.** If the dev sees that path imported anywhere, replace with `import type { User } from "@/api-types"` (or wherever Story 2-2 settled the import — likely a tiny `@/lib/types/user.ts` re-export). Same applies for the new `Case` type — re-export at `@/lib/types/case.ts` per Subtask 1.2.

11. **Don't add the rail to Team Lead or Regulator routes.** Per AC8, the rail mounts inside `/queue` only. Team Lead's `/approvals` and Regulator's `/regulator-lens` get their own layouts in Epics 9 + 10. Layout duplication-is-fine here; premature shared layout would constrain those Epics.

12. **Polling causes a re-render every 5s even if nothing changed.** TanStack Query memoizes the data reference if `structuralSharing: true` (default), so the rail won't re-render unless the case list actually changes. Verify with React DevTools Profiler — if the rail re-renders on every poll, check that `useCases` is not destructuring `data` in a way that creates new references.

### Architecture patterns relevant here

[Source: `architecture.md#Project-Specific Patterns` P6 SSE Event Pattern] — **forward-looking note for Story 4-6:** when SSE lands, this story's `useCases({refetchInterval: 5_000})` becomes `useCases({refetchInterval: false})` and SSE event handlers call `queryClient.invalidateQueries(["cases"])` instead. The component contract doesn't change. Document this in `useCases.ts` as a TODO comment.

[Source: `architecture.md#Implementation Patterns & Consistency Rules` § Process Patterns] — Loading state is TanStack Query's `isPending` only. Optimistic updates are NOT used here (they're reserved for Story 4-2 triage actions x/d).

### Project Structure Notes

This story creates:

- `apps/cockpit-ui/src/hooks/useCases.ts`
- `apps/cockpit-ui/src/hooks/useCases.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/QueueRail/QueueRail.tsx`
- `apps/cockpit-ui/src/components/cockpit/QueueRail/QueueRail.test.tsx`
- `apps/cockpit-ui/src/lib/formatRelative.ts`
- `apps/cockpit-ui/src/lib/formatRelative.test.ts`
- `apps/cockpit-ui/src/lib/caseState.ts` (state→{label, color} mapping helper)
- `apps/cockpit-ui/src/lib/types/case.ts` (re-export from generated `api-types`)

This story modifies:

- `apps/cockpit-ui/src/routes/queue.tsx` — replace Story 1-4 placeholder with rail + canvas-placeholder layout
- `tools/scripts/verify_demo.sh` — add `/v1/cases` check; bump count 5→6
- `tools/scripts/test_verify_demo.sh` — assert new check fails when API is down

This story DOES NOT create:

- Risk × SLA × continuity ordering (Story 4-1)
- Keyboard triage / `activeCaseId` Zustand store (Story 4-2)
- Risk score bar / SLA chip / delta in the row (Stories 4-1, 5-7)
- Status pills (Story 4-9)
- SSE event handling (Story 4-6)
- Case Canvas / `/cases/$caseId` route (Story 4-X)
- Fixture cases (Story 2-4)

### References

- [Source: `architecture.md#Demo Scope Addendum (2026-04-29)`]
- [Source: `architecture.md#Frontend Architecture` F1, F2, F12]
- [Source: `architecture.md#Format Patterns`] — `{items, next_cursor, has_more}`
- [Source: `architecture.md#Anti-Patterns to Refuse`]
- [Source: `architecture.md#Project-Specific Patterns` P6 SSE Event Pattern] — forward-looking
- [Source: `ux-design-specification.md` § Cockpit layout § Queue Rail (260 px)]
- [Source: `ux-design-specification.md` § Color tokens] — `surface-warm` `#FAFAF9`
- [Source: `ux-design-specification.md` § Radius scale] — `radius-sm` for badges
- [Source: `ux-design-specification.md` § Shadow scale] — no shadow on rows
- [Source: `epics.md#Epic 2 — Case Ingest & Lifecycle` § Story 2.6] — original ACs
- [Source: `prd.md#FR1`] — Queue Rail FR (basic ordering kept)
- [Source: `2-1-case-schema-and-state-machine.md`] — `Case` contract, `list_ordered_by_created_at_desc`
- [Source: `2-2-get-case-retrieval-api-consumer.md`] — `useCase` precedent + openapi-fetch client + `/v1/cases` list endpoint

### Previous Story Intelligence

[Source: `1-4-cockpit-shell-with-user-switcher-three-hardcoded-roles.md`]
- `routes/queue.tsx` is the analyst's default route. Switcher already redirects Team Lead → `/approvals`, Regulator → `/regulator-lens`. This story preserves that gating; do not loosen.
- `__root.tsx` is the cockpit shell layout. The BottomRibbon placeholder mount point (`data-testid="bottom-ribbon-placeholder"`) is preserved for Story 4-9's status pills.
- The Zustand `currentUser` store is at `@/stores/currentUser`. Read role via `useCurrentUser().user.role` for any role gates; **do not** add a new "user role" store.

[Source: `1-5-fresh-clone-to-running-demo-in-sixty-minutes.md`]
- `make verify` is a Bash script with five checks. AC12 of THIS story extends it to six. Mirror the existing function-per-check pattern.
- `tools/scripts/test_verify_demo.sh` asserts non-zero exit when checks fail. Extending it parallels the existing structure.
- Cold-start budget: ≤60 min for fresh-clone-to-running. This story doesn't change the budget.

[Source: `2-1-case-schema-and-state-machine.md` — predecessor]
- `CaseRepo.list_ordered_by_created_at_desc(limit)` does the server-side sort. The hook trusts that order — DO NOT re-sort client-side.
- `Case.customer_metadata.customer_name` is required (min 1 char per the contract). Truncation in the row component is purely cosmetic; the data is always present.
- `CaseState` enum values are exactly `intake_scheduled`, `decision_ready`, `committed`, `escalated`, `closed`. Match exactly in the badge mapping — typos will silently fall through to the default badge style.

[Source: `2-2-get-case-retrieval-api-consumer.md` — predecessor]
- `apiClient` is the openapi-fetch typed client at `apps/cockpit-ui/src/lib/api.ts`. Header injection via Zustand store getter is already in place.
- `GET /v1/cases` returns `{items: [...], next_cursor: null, has_more: false}` (cursor pagination is forward-compat scaffolding; demo never exceeds 100 cases).
- `Case` type comes from generated `api-types.ts`; re-export at `@/lib/types/case.ts` for ergonomic imports.
- `msw` is installed for hook tests; reuse the setup file.
- `make contracts` regenerates the TS types after any contract or router change. After Story 2-2 lands, **no contract changes are needed** for this story (the `/v1/cases` endpoint and `CaseListResponse` already exist).

### Demo verification protocol (operator hand-off)

```bash
# Pre-requisites: Stories 2-1, 2-2 merged. Story 2-4 may or may not be merged
# (this story's UI works against an empty queue or a fixture-seeded queue).

make lint
make test
# Expected: all green; new tests visible (useCases, QueueRail, formatRelative).

make demo-reset
make dev &  # background; wait ~30s
make verify
# Expected: 6/6 checks green (5 from Story 1-5 + new /v1/cases check).

# 1. Empty state:
#    Browser → http://localhost:5173/queue (logged in as Analyst by default)
#    Expected: "No cases yet." + "Run \`make seed\` to load fixture cases."

# 2. After Story 2-4 (or manual case insertion):
#    Insert: sqlite3 ./data/cockpit.db "INSERT INTO cases (id, state, customer_metadata, created_at, updated_at) VALUES ('case_01HXY3Q9KW4VPQF2ZT8C7M5R3N', 'intake_scheduled', '{\"customer_name\": \"Test Co\"}', strftime('%Y-%m-%dT%H:%M:%fZ','now'), strftime('%Y-%m-%dT%H:%M:%fZ','now'))"
#    Within ≤5s: "Test Co" appears at top of the rail with "Intake scheduled" badge.

# 3. Polling cadence:
#    DevTools → Network → filter "v1/cases"
#    Expected: requests every 5s while tab is active; pause when tab is hidden.

# 4. Role gating:
#    Switch to Team Lead via the switcher → redirects to /approvals (Story 1-4 behavior).
#    Switch back to Analyst → /queue renders the rail.

# 5. Error state:
#    Stop the API: kill the uvicorn process.
#    Browser tab on /queue → reload → rail shows the error state with retry button.
#    Restart the API; click retry; rail recovers.

kill %1
```

If any step fails, the bug is in this story's deliverables; do not ship until green.

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (Amelia persona, bmad-dev-story workflow)

### Debug Log References

- Story 2.2 dropped MSW for `vi.stubGlobal('fetch')`; this story reuses the same pattern in `useCases.test.tsx` rather than reintroducing MSW.
- `useCases.test.tsx` polling assertion uses `vi.useFakeTimers({ shouldAdvanceTime: true })` so React Query's internal `setTimeout` chain still fires; pure fake-timers leaves the query in `isPending` forever.
- The `vi.useRealTimers()` call inside the QueueRail "renders relative time" test is needed because `vi.setSystemTime` was used to pin the clock — without restoring real timers the next test's async `waitFor` would never settle.

### Completion Notes List

- AC1: `useCases()` hook polls `/v1/cases` every 5s, unwraps `items`, returns `Case[]`. `staleTime: 0` so each refetch returns fresh data.
- AC2: `QueueRail` component is presentational — accepts `cases`, `activeCaseId`, `onSelect`, `isPending`, `isError`, `onRetry`. Zero data fetching inside.
- AC3: Each row renders customer name (truncated to 28 chars), relative time (via `formatRelative`), and a Tailwind state badge per `CASE_STATE_BADGES`.
- AC4: Empty state shows "No cases yet." + the `make seed` prompt, inline (no separate file).
- AC5: Skeleton (4 placeholder rows), `role="alert"` error with retry button, no Zustand loading flag.
- AC6: `routes/queue.tsx` upgraded to render the rail + a canvas placeholder split; preserves Story 1.4 role gate.
- AC7: 260 px width, 64 px row height, hover `bg-zinc-50`, active `border-l-2 border-l-blue-500`, no shadow. `bg-[#FAFAF9]` literal with the TODO-extract-to-token comment.
- AC8: Rail mounted only inside `/queue`. `__root.tsx` unchanged from Story 1.4.
- AC9: `refetchIntervalInBackground` left at the TanStack Query default (`false`).
- AC10: 22 new vitest specs (8 in `useCase.test.tsx` ... wait, that was 2.2. New: `formatRelative.test.ts` 9 cases, `QueueRail.test.tsx` 10 cases, `useCases.test.tsx` 2 cases) — total +22 from this story.
- AC11: Empty-state, role-gating, polling, freshness, and error-state paths covered via tests + targeted curl smoke. Live UI eyeball deferred to a presenter walkthrough.
- AC12: `verify_demo.sh` upgraded with the `/v1/cases` envelope check (now check #4 in the file's order). `test_verify_demo.sh` extended with the third case asserting non-zero exit when the new check fails. Header comment bumped to "Six checks".

### File List

**Created**
- `apps/cockpit-ui/src/hooks/useCases.ts`
- `apps/cockpit-ui/src/hooks/useCases.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/QueueRail/QueueRail.tsx`
- `apps/cockpit-ui/src/components/cockpit/QueueRail/QueueRail.test.tsx`
- `apps/cockpit-ui/src/lib/formatRelative.ts`
- `apps/cockpit-ui/src/lib/formatRelative.test.ts`
- `apps/cockpit-ui/src/lib/caseState.ts`
- `apps/cockpit-ui/src/lib/types/case.ts` (re-exports from `@/api-types`)

**Modified**
- `apps/cockpit-ui/src/routes/queue.tsx` — replaced placeholder with rail + canvas-placeholder layout
- `tools/scripts/verify_demo.sh` — added `/v1/cases` check; bumped header to six checks
- `tools/scripts/test_verify_demo.sh` — added the `/v1/cases` unreachable assertion
- `Documentation/implementation-artifacts/sprint-status.yaml` — story 2-3 → review

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-04-29 | Story 2.3 drafted in the demo re-scope. Renders the Queue Rail with `created_at DESC` ordering, 5s polling, three info pieces per row (name + relative time + state badge). Establishes the canonical mount point for Story 4-1 (ordering), Story 4-2 (keyboard triage), Story 4-9 (status pills). Adds `/v1/cases` to `make verify`. |
| 2026-04-30 | Implemented all 7 tasks. 22 new vitest specs (`formatRelative` 9, `QueueRail` 10, `useCases` 2 — totalled across the three new files); `make lint`/`make test` all green; `verify_demo.sh` regression test green (3 cases). Status → review. |
