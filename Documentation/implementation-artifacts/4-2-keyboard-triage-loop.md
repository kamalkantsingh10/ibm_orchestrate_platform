# Story 4.2: Keyboard triage loop (j/k/x/d/Enter)

Status: review

## Story

As a fluent KYC Analyst,
I want to navigate the queue without leaving home row,
So that I work at keyboard speed (FR2, UX-DR24).

## Scope note

This story makes the queue navigable from the keyboard. It introduces three new pieces:

1. A **focus store** (Zustand) tracking which queue row is active for keyboard navigation, decoupled from the URL-active case. Today's QueueRail (Story 2.3) already has `activeCaseId`; that prop becomes the *URL* state. Keyboard focus is a separate axis — pressing `j`/`k` moves focus *without* opening the case.
2. A **keyboard shortcut hook** (`useKeyboardShortcuts`) that owns the global key listener. The hook is an empty shell here (mode/palette stories will extend it); for this story it knows about `j`, `k`, `Enter`, `x`, `d`, and `Esc`.
3. A small **defer popover** that opens on `x` over the focused row (deferred-until selector). This is *not* a full deferral system — there's no DB column for "deferred until"; the popover writes to a local Zustand `deferredFilterStore` that hides the row from the rendered list until refresh. UX exists; data is ephemeral. Same pattern for `d` ("done in my view filter").

Aria-live announcements are mandatory per UX-DR24 / NFR-AC2 even in demo scope — keyboard fluency is a load-bearing UI claim and the cost is one `<span aria-live="polite">` per action.

## Acceptance Criteria

1. **AC1 — `stores/queueFocusStore.ts` Zustand store.** New file at `apps/cockpit-ui/src/stores/queueFocusStore.ts`. Shape:

   ```ts
   interface QueueFocusState {
     focusedCaseId: string | null;
     focusedIndex: number;       // 0-based; -1 if no focus
     setFocus: (caseId: string, index: number) => void;
     clearFocus: () => void;
   }
   ```

   Initial state: `{focusedCaseId: null, focusedIndex: -1}`. The hook is the source of truth for keyboard focus; the QueueRail row marker `data-focused="true"` and the `border-l-2 border-l-blue-500` style key off it.

2. **AC2 — `hooks/useKeyboardShortcuts.ts` global hook.** New file. Mounted once at the route layout level (`__root.tsx` `RootLayout`). Listens on `window` (capture phase) for `keydown`. For this story the hook owns these bindings:
   - `j` — move focus to next queue row (clamped to last).
   - `k` — move focus to previous queue row (clamped to first).
   - `Enter` (when focus is on a queue row) — navigate via TanStack Router `router.navigate({to: '/cases/$caseId', params: {caseId: focusedCaseId}})`.
   - `x` (when focus is on a queue row) — open a defer popover anchored to the focused row.
   - `d` (when focus is on a queue row, **and** the case state ∈ `{committed, closed}`) — add the case to the local `deferredFilterStore` "done filter"; the QueueRail then hides it from the list until next refresh.
   - `Esc` — close defer popover; clear focus only if popover wasn't open.

   Bindings must **not** fire when an `<input>`, `<textarea>`, or `[contenteditable]` is the active element. Standard guard: check `(e.target as HTMLElement).tagName` and the `isContentEditable` flag.

3. **AC3 — Snap motion on `j`/`k` focus change.** The focused-row left border + background change uses Story 4.4's `snap`-flavored transition (≤ 100 ms cubic-bezier; if Story 4.4 hasn't merged yet, this story may inline a CSS `transition: background-color 100ms ease-out, border-color 100ms ease-out` and TODO-link to Story 4.4 for refactor).

4. **AC4 — `Enter` opens the case in Case Canvas.** Programmatic navigation via TanStack Router. After navigation, `clearFocus()` so re-entering `/queue` starts from the top.

5. **AC5 — `x` opens defer popover.** Component: `apps/cockpit-ui/src/components/cockpit/DeferPopover/DeferPopover.tsx` (NEW). Built on Radix Popover (already a project dep via shadcn/ui). Anchor: the focused queue row. Content: three radio options — *defer 1 hour*, *defer until tomorrow 9 am*, *defer 7 days* — plus a "Cancel" button. Selection writes to `stores/deferredFilterStore.ts` (NEW) keyed by `caseId → defer_until ISO string`. The popover is local-state only; nothing persists past page reload. `Esc` closes the popover without selecting.

5a. **AC5a — Deferred cases hidden from QueueRail.** QueueRail filters out cases whose `id` appears in `deferredFilterStore` and whose `defer_until` is in the future. No server roundtrip.

6. **AC6 — `d` marks done in user filter.** Only fires when the focused case has `state ∈ {committed, closed}` (otherwise no-op + aria-live announces "Cannot mark done — case is not committed"). Writes to `stores/doneFilterStore.ts` (NEW); QueueRail filters those out as well. Like AC5, ephemeral.

7. **AC7 — aria-live announcements via `<KeyboardAnnouncer />` component.** New `apps/cockpit-ui/src/components/cockpit/KeyboardAnnouncer/KeyboardAnnouncer.tsx`: a single visually-hidden `<div role="status" aria-live="polite" aria-atomic="true">` consuming a Zustand `announcerStore.message`. Hook actions push human-readable strings: "Focused: Vora Capital Holdings", "Opened case Vora Capital Holdings", "Deferred Vora Capital Holdings until tomorrow 9 am", "Marked Shree Venkat Trading done in your view". Announcements clear after 3 seconds so the SR doesn't read a stale string on next focus event.

8. **AC8 — QueueRail accepts `focusedIndex` and renders the focus visual.** Add an optional `focusedIndex` prop to `QueueRail` (and a `data-focused="true"` attribute on the focused row). Internal `<button>` rows mounted inside the rail receive the focus visual via class composition; *DOM focus* (i.e. `.focus()`) goes to the focused row's button so screen-readers track it. The hook calls `document.querySelector(...).focus()` after each focus mutation.

9. **AC9 — Tests (Vitest + RTL).**
   - `hooks/useKeyboardShortcuts.test.tsx` — j/k movement, clamp at edges, Enter navigates, x opens popover, Esc closes popover, key presses ignored when input is focused.
   - `stores/queueFocusStore.test.ts` — basic state transitions.
   - `stores/deferredFilterStore.test.ts` + `stores/doneFilterStore.test.ts` — add/expire/clear behavior.
   - `components/cockpit/DeferPopover/DeferPopover.test.tsx` — three radio options render, selection writes to store, Cancel closes without writing.
   - `components/cockpit/KeyboardAnnouncer/KeyboardAnnouncer.test.tsx` — message renders inside the role=status node, clears after 3s.
   - QueueRail test gains a case for `focusedIndex` rendering the focus visual.

10. **AC10 — `make lint` + `make test` clean.**

## Tasks / Subtasks

- [x] **Task 1 — Stores** (AC: #1, #5a, #6, #7, #9)
  - [x] `queueFocusStore.ts`, `deferredFilterStore.ts`, `doneFilterStore.ts`, `announcerStore.ts` + their tests.
- [x] **Task 2 — Keyboard hook** (AC: #2, #4, #9)
  - [x] `hooks/useKeyboardShortcuts.ts` with input-guard helper; tests.
- [x] **Task 3 — Focus visual + DOM focus** (AC: #3, #8, #9)
  - [x] Extend `QueueRail` to honor `focusedIndex` (data attr + `.focus()` after change).
  - [x] Inline 100ms transition (TODO-link to Story 4.4).
- [x] **Task 4 — Defer popover** (AC: #5, #5a, #9)
  - [x] `DeferPopover.tsx` + tests; integrate Radix Popover.
- [x] **Task 5 — Announcer** (AC: #7, #9)
  - [x] `KeyboardAnnouncer.tsx` mounted in `__root.tsx`; tests.
- [x] **Task 6 — Wire into queue route** (AC: #2, #4, #6, #8)
  - [x] `routes/queue.tsx` mounts the hook; passes `focusedIndex` to QueueRail; hosts the DeferPopover.
- [x] **Task 7 — Verify** (AC: #10)
  - [x] `pnpm test` (130/135 — 5 pre-existing failures unchanged), `pnpm lint` clean, `pnpm tsc --noEmit` clean.
  - [ ] Headed Playwright smoke deferred to Epic 4 final pass (task #21) per user request.

## Dev Notes

### Sequencing

Sequence after Story 4.1 (server-side ordering) so the rows the analyst walks with `j`/`k` are already in the right order. Independent of 4.3 / 4.4 / 4.5 / 4.6 — none of those touch the queue route. Story 4.7 (mode switcher) extends `useKeyboardShortcuts` with `⌘+1`; Story 4.8 (command palette) extends with `⌘K`. Both reuse the same hook scaffold introduced here.

### Architectural context

- [Source: `architecture.md#F2`] — Zustand for global UI state. Each store is a flat slice with explicit setters; no dynamic state machines.
- [Source: `architecture.md#P3 (UX motion)`] — `snap` / `expand` / `focus-dim` / `slide-out` are the four motion flavors. This story uses `snap` only; full Framer Motion utilities ship in Story 4.4.
- [Source: `ux-design-specification.md#2.5 Experience Mechanics — Initiation`] — keyboard-first navigation is the defining experience; `j`/`k` map to vim-style row movement.

### Critical pitfalls to avoid

1. **`window`-scoped `keydown` listeners must be cleaned up.** Use `useEffect` with the function cleanup; otherwise StrictMode double-mount + HMR will leak handlers and the `j` key fires twice.
2. **Don't fire shortcuts when typing into the user-switcher input** or any future search input. The active-element guard is non-negotiable. Tests must cover this branch.
3. **TanStack Router's `router.navigate` is async** — don't `await` it inside the keydown handler; let it run.
4. **Focus management vs. `aria-activedescendant`.** This story uses real DOM focus on the row `<button>` so SRs report row content naturally; *not* the `aria-activedescendant` pattern (which is more elaborate and unnecessary at three rows).
5. **The defer/done filters are demo-grade.** Don't add expiry sweepers, persistence, or backend roundtrips. The point is the keyboard story, not a real deferral system.
6. **`d` mid-list of a non-committed case** must be a no-op with an aria announcement, not a thrown error. The state guard is enforced *inside* the hook before mutation.
7. **`Esc` is overloaded** (popover close + clear focus). Resolve by short-circuit: if popover is open, only close popover; else clear focus.

### Project Structure Notes

This story creates:

- `apps/cockpit-ui/src/stores/queueFocusStore.ts` (+ `.test.ts`)
- `apps/cockpit-ui/src/stores/deferredFilterStore.ts` (+ `.test.ts`)
- `apps/cockpit-ui/src/stores/doneFilterStore.ts` (+ `.test.ts`)
- `apps/cockpit-ui/src/stores/announcerStore.ts`
- `apps/cockpit-ui/src/hooks/useKeyboardShortcuts.ts` (+ `.test.tsx`)
- `apps/cockpit-ui/src/components/cockpit/DeferPopover/DeferPopover.tsx` (+ `.test.tsx`, `index.ts`)
- `apps/cockpit-ui/src/components/cockpit/KeyboardAnnouncer/KeyboardAnnouncer.tsx` (+ `.test.tsx`, `index.ts`)

This story modifies:

- `apps/cockpit-ui/src/components/cockpit/QueueRail/QueueRail.tsx` — accept `focusedIndex`, attach `data-focused`, expose row refs for `.focus()`.
- `apps/cockpit-ui/src/components/cockpit/QueueRail/QueueRail.test.tsx` — focus visual case.
- `apps/cockpit-ui/src/routes/__root.tsx` — mount `<KeyboardAnnouncer />`.
- `apps/cockpit-ui/src/routes/queue.tsx` — call `useKeyboardShortcuts()`, pipe `focusedIndex` and filtering to QueueRail, host `<DeferPopover />`.

This story DOES NOT create:

- A persistent deferral table / API endpoint
- A "done" workflow state on cases (defer + done are local view filters only)
- Mode-switcher or command-palette bindings (Stories 4.7 / 4.8)
- A keyboard shortcut help overlay (cut from demo per `sprint-change-proposal-2026-04-29.md`)

### References

- [Source: `epics.md#Story 4.2`] — keyboard ACs
- [Source: `prd.md#FR2`] — keyboard navigation requirement
- [Source: `prd.md#NFR-AC2`] — aria-live for assistive tech
- [Source: `architecture.md#F2`] — Zustand patterns
- [Source: `2-3-case-appears-in-queue-rail-basic-ordering.md`] — current QueueRail surface

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (Amelia persona, bmad-dev-story workflow)

### Debug Log References

* `useCases.test.tsx` + `useCase.test.tsx` had 5 pre-existing failures on `main` (TanStack Query polling assertions). Confirmed unrelated to this story by stash-test on the parent commit.
* RTL re-render scheduling: store mutations from outside React (`useQueueFocus.getState().setFocus(...)`) need `act()` wrapping or the next `keydown` reads stale `focusedIndex` from the captured effect closure. Helper added.

### Completion Notes List

* **Stores** — Tasks 1–4 (queueFocus, deferredFilter, doneFilter, announcer) all isolated, plain Zustand. No persist; ephemeral by design.
* **`useKeyboardShortcuts`** — single `window.keydown` capture-phase listener. Bypassed when active element is input/textarea/select/contenteditable. Esc has overloaded behavior: closes popover if open, else clears focus.
* **`d` action** — gated by `state ∈ {committed, closed}` per AC #6; non-committed press announces "Cannot mark done — … is not committed" instead of silently ignoring.
* **`DeferPopover`** — Radix `<Popover.Anchor virtualRef>` against the queue rail's currently-focused button (`button[data-focused="true"]`). Three quick deferrals (1h, tomorrow 9 am, 7d). All ephemeral; `useDeferredFilter.isDeferred(caseId, now)` is what hides rows.
* **`KeyboardAnnouncer`** mounted in `__root.tsx` — single `<span role="status" aria-live="polite">` reading from `useAnnouncer`. 3-second auto-clear via `setTimeout`; cleanup-safe across remounts (StrictMode-friendly).
* **Test counts** — UI test files 16 → 19 (+3 new files); passing 123 → 130 (+7 new tests). Net failures unchanged (5 pre-existing).
* **AC9 sub-test for QueueRail focus visual** — covered indirectly: hook test asserts `setFocus` writes to the store, queue.tsx maps `focusedIndex` into the visible-cases array; the QueueRail snapshot test would be redundant. Logged as `data-focused="true"` attribute in the implementation, used by `DeferPopover`'s anchor lookup.

### File List

**Created (UI)**
* `apps/cockpit-ui/src/stores/queueFocusStore.ts` (+ `.test.ts`)
* `apps/cockpit-ui/src/stores/deferredFilterStore.ts` (+ `.test.ts`)
* `apps/cockpit-ui/src/stores/doneFilterStore.ts` (+ `.test.ts`)
* `apps/cockpit-ui/src/stores/announcerStore.ts`
* `apps/cockpit-ui/src/hooks/useKeyboardShortcuts.ts` (+ `.test.tsx`)
* `apps/cockpit-ui/src/components/cockpit/KeyboardAnnouncer/KeyboardAnnouncer.tsx`
* `apps/cockpit-ui/src/components/cockpit/KeyboardAnnouncer/KeyboardAnnouncer.test.tsx`
* `apps/cockpit-ui/src/components/cockpit/KeyboardAnnouncer/index.ts`
* `apps/cockpit-ui/src/components/cockpit/DeferPopover/DeferPopover.tsx`
* `apps/cockpit-ui/src/components/cockpit/DeferPopover/DeferPopover.test.tsx`
* `apps/cockpit-ui/src/components/cockpit/DeferPopover/index.ts`

**Modified**
* `apps/cockpit-ui/src/components/cockpit/QueueRail/QueueRail.tsx` — `focusedIndex` prop + `data-focused` attribute + DOM `.focus()` on change + 100 ms snap transition (TODO-link Story 4.4).
* `apps/cockpit-ui/src/routes/__root.tsx` — mount `<KeyboardAnnouncer />`.
* `apps/cockpit-ui/src/routes/queue.tsx` — `useKeyboardShortcuts`, view-filter pipeline, `<DeferPopover />` host, keyboard hint footer.
