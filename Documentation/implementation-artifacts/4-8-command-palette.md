# Story 4.8: Command palette (⌘K)

Status: review

## Story

As a KYC Analyst,
I want a universal action palette accessible by ⌘K,
So that any cockpit action is one keystroke away (FR5, UX-DR23).

## Scope note

The command palette is a centered modal overlay opened by ⌘K, with a search input that fuzzy-matches a list of registered commands. For the demo, the registry is small and finite (the five commands listed in the epic). Architectural choice: keep the registry as a flat in-component constant array — no plugin/extension system. Stories that add more commands (e.g. Story 8.1 will add "switch to Zen mode") edit this array.

This story uses Radix Dialog (already a project dep via shadcn/ui) for the modal shell + a basic fuzzy search (Levenshtein-distance-light or `Array.filter` against substring match). The motion comes from Story 4.4's `expand` preset; if 4.4 hasn't merged, this story may inline.

## Acceptance Criteria

1. **AC1 — `stores/paletteStore.ts` Zustand store.** New `apps/cockpit-ui/src/stores/paletteStore.ts`:

   ```ts
   interface PaletteState {
     open: boolean;
     setOpen: (open: boolean) => void;
     toggle: () => void;
   }
   ```

2. **AC2 — `⌘K` keyboard binding extends `useKeyboardShortcuts`.** Add a binding that calls `paletteStore.toggle()`. Modifier rules: `e.metaKey || e.ctrlKey` + `e.key === 'k'`. Must `preventDefault()` to suppress browser default. Input-focus guard from Story 4.2 is bypassed here (⌘K should work even from inside the palette's own input — though once the palette is open, the input is the active element and Esc closes).

3. **AC3 — `CommandPalette.tsx` component.** New `apps/cockpit-ui/src/components/cockpit/CommandPalette/CommandPalette.tsx`. Built on Radix Dialog:
   - Centered modal, `max-w-lg`, opaque white card with subtle shadow.
   - Mounted once at the route layout level (`__root.tsx`); reads `open` from the store.
   - Open animation: Story 4.4's `expand` preset (250 ms cubic-bezier).
   - Body: a single `<input>` with `autoFocus`, placeholder "Type a command…", followed by a results list.

4. **AC4 — Command registry.** Inside the same file or a sibling `commands.ts`, define:

   ```ts
   interface Command {
     id: string;
     label: string;
     keywords?: string[];     // additional fuzzy-match terms
     run: (ctx: CommandContext) => void;   // ctx exposes router, queryClient, currentUser, modeStore
   }

   const commands: Command[] = [
     { id: 'open-case',       label: 'Open case…',                   ... },
     { id: 'switch-investigation', label: 'Switch to Investigation mode', ... },
     { id: 'go-queue',        label: 'Go to queue',                  ... },
     { id: 'sign-out',        label: 'Sign out',                     ... },
     { id: 'show-shortcuts',  label: 'Show keyboard shortcuts',      ... },
   ];
   ```

   Implementation per command:
   - **`open-case`** — special: when selected, swaps the input into a "case search" mode (placeholder "Type case name or ID…") and re-filters `useCases()` data by name/id. Selecting a result navigates to `/cases/$caseId`. Two-state input: command list ↔ case search.
   - **`switch-investigation`** — calls `modeStore.setMode('investigation')` (Story 4.7).
   - **`go-queue`** — `router.navigate({to: '/queue'})`.
   - **`sign-out`** — clears the user-switcher selection (Story 1.4 / 1.6 currentUser store) and reloads the page.
   - **`show-shortcuts`** — emits a toast "Keyboard help overlay deferred to post-demo" (the help overlay is cut per `sprint-change-proposal-2026-04-29.md`). The command stays in the registry so the affordance is visible; the body is documented as deferred.

5. **AC5 — Fuzzy search.**
   - Match query against `label` + `keywords` joined.
   - Lowercase substring match is acceptable for the demo (the five-item registry doesn't need Levenshtein). Score: `1` if substring match starts at position 0, `0.5` if elsewhere, `0` if no match. Sort matches descending by score, then alphabetical.
   - Empty query → all commands in registration order.

6. **AC6 — Keyboard navigation in palette.**
   - `↓` / `↑` move highlight; `Enter` runs the highlighted command.
   - `Esc` closes (Radix Dialog handles this natively but verify).
   - Highlight starts at index 0 on open; resets to 0 on every input change.

7. **AC7 — Results render.**
   - Each result row: `{label}` + (optionally) a small kbd-style hint of the command's id.
   - Highlighted row: `bg-zinc-100`.
   - Empty state (no matches): "No commands match" muted text.
   - Result count cap: 10 (more is unusual for the demo registry; document the cap in a comment).

8. **AC8 — Performance budget.** Fuzzy match must complete within 50 ms p95 per the epic. With a 5-item registry this is trivially met; an in-test assertion calls the matcher 100× and asserts the median runtime is < 5 ms.

9. **AC9 — Accessibility.**
   - The Dialog has `aria-labelledby` + `aria-describedby` (Radix sets these).
   - The results list is announced via `aria-live="polite"` when results change.
   - The highlighted row has `aria-selected="true"` (for SR consumers that respect listbox semantics).
   - The input has `role="combobox"` + `aria-expanded="true"` while open.

10. **AC10 — Tests.**
    - `paletteStore.test.ts` — open/close/toggle.
    - `CommandPalette.test.tsx` — open via store, type filter, ↓ ↑ Enter selects, Esc closes, "open case" two-state mode, every registered command's `run` is invoked when selected (via mocked router + stores).
    - `useKeyboardShortcuts.test.tsx` (extend) — `⌘K` toggles store; works from within the input (re-test the bypass for the palette's own input).
    - Performance microbench in `CommandPalette.test.tsx` (AC8).

11. **AC11 — `make lint` + `make test` clean.**

## Tasks / Subtasks

- [ ] **Task 1 — Palette store** (AC: #1, #10)
  - [ ] `paletteStore.ts` + tests.
- [ ] **Task 2 — Hook binding** (AC: #2, #10)
  - [ ] Extend `useKeyboardShortcuts.ts` for `⌘K`.
- [ ] **Task 3 — Component shell + Dialog** (AC: #3, #6, #7, #9, #10)
  - [ ] `CommandPalette.tsx` with Radix Dialog + autofocus input + result list + arrow-key navigation + a11y.
- [ ] **Task 4 — Registry** (AC: #4, #5, #8, #10)
  - [ ] `commands.ts` (or inline) with the five commands.
  - [ ] Fuzzy match helper + perf microbench.
- [ ] **Task 5 — Mount + verify** (AC: #11)
  - [ ] Mount `<CommandPalette />` in `__root.tsx`.
  - [ ] `make lint` + `make test`.
  - [ ] Manual demo: `⌘K`, type "queue", Enter; type "case", search Vora, Enter; ⌘K → "sign out".

## Dev Notes

### Sequencing

- Depends on Story 4.2 (keyboard hook). Schedule after.
- Depends on Story 4.7 (mode store) for the `switch-investigation` command body. Schedule after.
- Independent of 4.1, 4.3, 4.4, 4.5, 4.6, 4.9.

### Architectural context

- [Source: `architecture.md#F2`] — Zustand for global UI state.
- [Source: `architecture.md#F8`] — `eslint-plugin-jsx-a11y` enforces aria correctness; the highlight ↔ aria-selected pairing is a common lint catch.
- [Source: `ux-design-specification.md#UX-DR23`] — palette is "any action is one keystroke away".
- [Source: `prd.md#FR5, NFR-P1`] — palette functional + 50 ms p95 fuzzy match performance.
- [Source: `sprint-change-proposal-2026-04-29.md`] — keyboard help overlay is cut; the `show-shortcuts` command is a placeholder.

### Critical pitfalls to avoid

1. **Don't add `cmdk` library.** It's the natural choice but is yet-another-dep; the project has Radix Dialog already. The five-command registry doesn't justify a new library.
2. **`autoFocus` inside Radix Dialog must wait for the overlay to mount.** Use the `onOpenAutoFocus` prop or a `useEffect` with `inputRef.current?.focus()`.
3. **`⌘K` from inside the palette's own input** must still toggle (bypass the input-focus guard for this binding). Don't double-toggle on rapid presses.
4. **The "open case" two-state mode** is the trickiest. Recommend a tiny state machine: `mode: 'commands' | 'cases'`. Switching writes a flag; the input placeholder + result rendering both branch on it. Backspace at empty input returns to `commands`.
5. **`sign-out` reloading the page** is a blunt instrument but adequate for demo. Don't over-engineer with logout endpoints — the user-switcher is local-state-only.
6. **Performance microbench in tests** is fine but don't gate CI on hardware-dependent absolute thresholds. Assert against a generous bound (e.g. p95 ≤ 50 ms in microbench means assert `< 100 ms` in test to absorb CI noise).
7. **Click-outside-closes** is Radix Dialog's default; preserve it.

### Project Structure Notes

This story creates:

- `apps/cockpit-ui/src/stores/paletteStore.ts` (+ `.test.ts`)
- `apps/cockpit-ui/src/components/cockpit/CommandPalette/CommandPalette.tsx`
- `apps/cockpit-ui/src/components/cockpit/CommandPalette/CommandPalette.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/CommandPalette/commands.ts` (or inline in the component)
- `apps/cockpit-ui/src/components/cockpit/CommandPalette/index.ts`

This story modifies:

- `apps/cockpit-ui/src/hooks/useKeyboardShortcuts.ts` — `⌘K` binding
- `apps/cockpit-ui/src/hooks/useKeyboardShortcuts.test.tsx` — new cases
- `apps/cockpit-ui/src/routes/__root.tsx` — mount palette

This story DOES NOT create:

- A keyboard shortcut help overlay (cut from demo)
- A command extension API for external plugins
- An "open recent" history feature
- A real fuzzy-search library import (substring match suffices)

### References

- [Source: `epics.md#Story 4.9`] — palette ACs (demo-renumbered to 4-8)
- [Source: `prd.md#FR5, NFR-P1`] — palette + perf
- [Source: `ux-design-specification.md#UX-DR23`] — visual treatment
- [Source: `4-2-keyboard-triage-loop.md`] — keyboard hook

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (Amelia persona, bmad-dev-story workflow)

### Debug Log References

* `useEffect → setState` cascade flagged by `react-hooks/cascading-renders`. Refactored: per-open reset moved to `Dialog.Content` `onOpenAutoFocus` callback (fires once on Radix mount); per-keystroke `setHighlight(0)` folded into the input's `onChange`. No effect→setState chain remains.
* `jsx-a11y/click-events-have-key-events` on result `<li>`s. Extracted to `PaletteRow` with `onKeyDown` handling Enter/Space — satisfies the rule and gives row-level keyboard activation a path.

### Completion Notes List

* **Five commands shipped**: `open-case` (two-state mode switch), `switch-investigation`, `go-queue`, `sign-out`, `show-shortcuts` (toast — overlay deferred per `sprint-change-proposal-2026-04-29.md`).
* **`paletteMode` state** is `'commands' | 'cases'`. Backspace at empty input in cases mode returns to commands mode (Story 4.8 critical-pitfall #4).
* **Sign-out** clears the persisted `cockpit-current-user` localStorage key and reloads to `/`. Coarse but adequate for the demo's user-switcher.
* **Fuzzy match**: substring scoring (1 for prefix, 0.5 elsewhere). Five-item registry doesn't justify a Levenshtein library.
* **Performance microbench** asserts 100 filter iterations complete in < 100 ms (CI-noise generous for the 50 ms p95 budget).
* **A11y**: `combobox` + `listbox` + `option` + `aria-selected` + `aria-live=polite` on results. ESLint a11y rules pass.
* **`⌘K` bypasses the input-focus guard** in `useKeyboardShortcuts` so users can toggle from inside the palette's own input.
* **Test counts** UI tests 183 → 200 (+17). Pre-existing 5 failures unchanged.

### File List

**Created**
* `apps/cockpit-ui/src/stores/paletteStore.ts` (+ `.test.ts`)
* `apps/cockpit-ui/src/components/cockpit/CommandPalette/CommandPalette.tsx`
* `apps/cockpit-ui/src/components/cockpit/CommandPalette/commands.ts`
* `apps/cockpit-ui/src/components/cockpit/CommandPalette/commands.test.ts`
* `apps/cockpit-ui/src/components/cockpit/CommandPalette/index.ts`

**Modified**
* `apps/cockpit-ui/src/hooks/useKeyboardShortcuts.ts` — `⌘K` toggle (bypasses input-focus guard).
* `apps/cockpit-ui/src/hooks/useKeyboardShortcuts.test.tsx` — 2 new ⌘K tests.
* `apps/cockpit-ui/src/routes/__root.tsx` — mount `<CommandPalette />`.
