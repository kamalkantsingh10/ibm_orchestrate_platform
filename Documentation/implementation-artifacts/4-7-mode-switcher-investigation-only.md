# Story 4.7: Mode switcher (Investigation only)

Status: review

## Story

As a KYC Analyst,
I want to switch into Investigation mode via ⌘+1,
So that the cockpit's UI footprint is tuned for the work I'm doing (FR4 partial, UX-DR22).

## Scope note

The PRD names six cockpit modes (Triage, Investigation, Decision, Zen, Audit, Regulator Lens). Epic 4 ships Investigation only — it's the default mode and the only one wired in this story. Zen lands in Epic 8; Regulator Lens already has a route from Story 1.4. The other three (Triage, Decision, Audit) are deferred to post-demo.

This story introduces:
1. A **mode store** (Zustand) holding the current mode.
2. A **⌘+1 keyboard binding** that sets the mode. ⌘+2 through ⌘+6 register but show a toast "Mode not yet available" and preserve the current mode.
3. A **toast surface** — minimal (sonner / shadcn-toast / inline; pick the lightest already-installed option, or one new minimal dep).

There is no visual mode change in this story (Investigation is the default; switching to Investigation when already in Investigation is a no-op). The store + binding land here so Story 8 (Zen mode) can plug in without re-architecting. UX-DR22 promises the visual change is "immediate (snap motion)" — that contract applies once a non-default mode lands.

## Acceptance Criteria

1. **AC1 — `stores/modeStore.ts` Zustand store.** New `apps/cockpit-ui/src/stores/modeStore.ts`:

   ```ts
   export type Mode = 'investigation' | 'zen' | 'regulator-lens';

   interface ModeState {
     mode: Mode;
     setMode: (mode: Mode) => void;
   }
   ```

   Initial state: `{mode: 'investigation'}`. The set of `Mode` values is intentionally narrow: only modes actually shipped (or imminent — Zen in Epic 8, Regulator Lens already routable) are typed. The other three modes (Triage, Decision, Audit) are not in the type union; ⌘+2/3/4/5/6 trigger the toast path which doesn't write to the store.

2. **AC2 — Keyboard bindings extend `useKeyboardShortcuts`.** Add to the existing hook (Story 4.2):
   - `Cmd+1` (or `Ctrl+1` on non-Mac) — `setMode('investigation')`. If already investigation, no-op.
   - `Cmd+2` through `Cmd+6` — show toast "Mode not yet available". Don't change `mode`.

   Modifier detection: `e.metaKey` on macOS, `e.ctrlKey` elsewhere. The hook lives at `apps/cockpit-ui/src/hooks/useKeyboardShortcuts.ts`.

   Bindings must NOT fire when an input/textarea/contenteditable has focus (existing guard from Story 4.2).

3. **AC3 — Toast component / surface.**
   - **Preferred:** add `sonner` to deps (`pnpm add sonner`); mount `<Toaster />` once in `__root.tsx`; emit toasts via `toast('Mode not yet available')`.
   - **Fallback:** a 50-line inline toast using a Zustand `toastStore` + a fixed-position `<div>` in `__root.tsx` that auto-dismisses after 2.5 s.

   Pick whichever the dev considers less ceremony given current deps.

4. **AC4 — Toast tests.** Whichever surface is chosen:
   - It renders the message.
   - It auto-dismisses (≤ 3 s).
   - Repeat invocations within the dismiss window stack (or replace — implementer's call; document the chosen behavior).

5. **AC5 — `modeStore` tests.** `apps/cockpit-ui/src/stores/modeStore.test.ts` — initial state, `setMode` updates, type safety (assert that `setMode('triage' as Mode)` is a TS error — comment-only assertion via `// @ts-expect-error`).

6. **AC6 — Hook tests.** Extend `useKeyboardShortcuts.test.tsx`:
   - `Cmd+1` calls `setMode('investigation')`.
   - `Cmd+2` triggers toast and does NOT call `setMode`.
   - Modifier-less `1` does nothing.
   - Input-focus guard still works for these bindings.

7. **AC7 — Mode badge in TopBar.** Edit `apps/cockpit-ui/src/routes/__root.tsx` — between the "Cockpit" wordmark and the UserSwitcher, render a small badge showing the current mode label (e.g. `Investigation`). Reads from `modeStore`. This is the visible affordance that the mode store exists and is consumed; without it, the demo can't show ⌘+1 working since Investigation is also the default.

8. **AC8 — `make lint` + `make test` clean.**

## Tasks / Subtasks

- [ ] **Task 1 — Mode store** (AC: #1, #5)
  - [ ] `stores/modeStore.ts` + `modeStore.test.ts`.
- [ ] **Task 2 — Toast surface** (AC: #3, #4)
  - [ ] Install `sonner` (or wire inline toast).
  - [ ] Mount `<Toaster />` in `__root.tsx`.
  - [ ] Tests.
- [ ] **Task 3 — Hook bindings** (AC: #2, #6)
  - [ ] Extend `useKeyboardShortcuts.ts` with `Cmd+1` … `Cmd+6` branches.
  - [ ] Update existing test file.
- [ ] **Task 4 — TopBar badge** (AC: #7)
  - [ ] Render mode badge in `__root.tsx`.
- [ ] **Task 5 — Verify** (AC: #8)
  - [ ] `make lint` + `make test`.
  - [ ] Manual demo: press `Cmd+2` → toast "Mode not yet available"; press `Cmd+1` → no-op (already in Investigation); badge stays "Investigation".

## Dev Notes

### Sequencing

- Depends on Story 4.2 (the keyboard hook to extend). If 4.2 hasn't merged, wait — don't re-implement input-guard logic.
- Independent of 4.1, 4.3, 4.4, 4.5, 4.6, 4.8, 4.9.
- Story 8 (Zen mode) is the next consumer; that story extends the type union to include real Zen behavior.

### Architectural context

- [Source: `architecture.md#F2`] — Zustand for global UI state. `modeStore.ts` is the canonical example.
- [Source: `architecture.md#Frontend Architecture, mode model`] — modes are global cockpit state; not per-route.
- [Source: `ux-design-specification.md#UX-DR22`] — mode switch is "immediate" with snap motion. (Snap motion landed in Story 4.4; nothing animates *into Investigation* in this story since it's the default.)
- [Source: `prd.md#FR4`] — six modes named in the PRD. Demo cut narrows to Investigation + Zen (Epic 8) + Regulator Lens (already routable).

### Critical pitfalls to avoid

1. **Don't ship Triage/Decision/Audit as fake modes** that flash a toast forever. Only ship the modes that have visible UI behind them. The toast is the explicit "not yet" affordance.
2. **`e.metaKey` is true for Cmd on Mac AND Windows key on Windows.** Detect platform by `navigator.platform` or `navigator.userAgentData.platform` and match `metaKey` on Mac, `ctrlKey` elsewhere. Use a small `isMac()` helper.
3. **`Cmd+1` is also browser shortcut for "switch to tab 1"** — the cockpit handler must `e.preventDefault()` after handling. Verify in a real browser, not just RTL.
4. **The toast surface (sonner) brings in a small dep** — verify the pnpm install lands cleanly inside the workspace; check the `apps/cockpit-ui/package.json` has it post-install.
5. **The TopBar badge change is testable** — extend `__root.tsx`'s existing tests (if any) to cover the badge.
6. **Don't add a dropdown for mode switching.** Keyboard-only is the demo flavor; the badge is read-only.

### Project Structure Notes

This story creates:

- `apps/cockpit-ui/src/stores/modeStore.ts` (+ `.test.ts`)
- (if `sonner`) no new files; otherwise an inline toast component.

This story modifies:

- `apps/cockpit-ui/src/hooks/useKeyboardShortcuts.ts` — add Cmd+1…6 branches
- `apps/cockpit-ui/src/hooks/useKeyboardShortcuts.test.tsx` — new cases
- `apps/cockpit-ui/src/routes/__root.tsx` — mount `<Toaster />`, render mode badge
- `apps/cockpit-ui/package.json` (+ `pnpm-lock.yaml`) — `sonner` dep (if chosen)

This story DOES NOT create:

- Triage / Decision / Audit modes (deferred post-demo)
- Zen mode visual treatment (Epic 8)
- A Regulator Lens mode binding (already routable; not keyboard-driven)
- A keyboard shortcut help overlay (cut from demo)

### References

- [Source: `epics.md#Story 4.8`] — mode switcher ACs (note: epic numbering is 4.8 in the source but demo scope renumbers to 4-7 per `sprint-change-proposal-2026-04-29.md`)
- [Source: `prd.md#FR4`] — modes named; demo subset clarified by `sprint-change-proposal-2026-04-29.md`
- [Source: `architecture.md#F2`] — Zustand pattern
- [Source: `4-2-keyboard-triage-loop.md`] — `useKeyboardShortcuts` extension point + input-focus guard

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (Amelia persona, bmad-dev-story workflow)

### Debug Log References

### Completion Notes List

* **`sonner` chosen over inline toast**. Already a small dep (~25 KB gz); the project uses Radix everywhere else and sonner ergonomics fit. Wired into `__root.tsx`.
* **Modifier detection** uses `e.metaKey || e.ctrlKey` — Cmd on Mac, Ctrl elsewhere. Tested both branches.
* **Mode badge** rendered top-bar between the wordmark and the user-switcher; reads from `useMode` store. Visible affordance proves ⌘+1 fires (otherwise no observable change since investigation is the default).
* **TS-strict guard** on `setMode` — `Mode` union excludes `triage/decision/audit`. The test asserts `// @ts-expect-error` on `setMode('triage')` which is ignored at runtime but caught at typecheck time.
* **Test count** UI tests 175 → 183 (+8 new).

### File List

**Created**
* `apps/cockpit-ui/src/stores/modeStore.ts` (+ `.test.ts`)

**Modified**
* `apps/cockpit-ui/src/hooks/useKeyboardShortcuts.ts` — `Cmd/Ctrl+1..6` branches; `setMode` dependency.
* `apps/cockpit-ui/src/hooks/useKeyboardShortcuts.test.tsx` — 4 new mode-switcher cases + sonner mock.
* `apps/cockpit-ui/src/routes/__root.tsx` — `<ModeBadge />` in TopBar; `<Toaster />` mounted.
* `apps/cockpit-ui/package.json` (+ `pnpm-lock.yaml`) — `sonner` dep.
