# Story 8.1: ⌘+4 mode switch to Zen

Status: backlog

## Story

As a KYC Analyst,
I want to switch into SAR/EDD Writing Zen mode via ⌘+4,
So that my environment changes when I shift to narrative work (FR4 full, FR25, UX-DR22).

## Scope note

This story wires the `zen` mode as a real, transitionable mode. The keystroke handler, the mode store update, and the entry/exit transition motion are the deliverables. **The visual treatment of Zen mode itself is Story 8.2** — this story only ensures the switch fires.

**Dependency on Story 4-7 (mode switcher):** the mode store and the existing keyboard bindings (⌘1 Investigation, etc.) are the surface this story extends.

**Coordination with Epic 12 (if in flight):** Story 12.1 builds a 6-mode segmented control with `Zen` listed under the `Memo` segment label — if 12.1 has landed, this story flips the `Memo` segment from `disabled` to `active` and points its `⌘4` shortcut at the zen mode store. If 12.1 has not landed, this story uses the existing Story 4-7 mode switcher and adds zen as a fourth active mode. Either way, the mode store state value `zen` is the single source of truth.

## Acceptance Criteria

1. **AC1 — `⌘+4` keystroke switches to Zen.** A new keyboard handler in `apps/cockpit-ui/src/components/cockpit/CommandPalette/keyboard.ts` (or wherever Story 4-7's mode shortcuts live) maps `⌘+4` (and `Ctrl+4` on non-Mac) to `setMode('zen')`. The handler is registered on case routes only (`/cases/:caseId`), not on `/queue` or `/approvals`.

2. **AC2 — Mode store update.** `apps/cockpit-ui/src/stores/modeStore.ts` (the existing mode store from Story 4-7) accepts `'zen'` as a valid mode value. Switching to `zen` from any other mode persists the mode in URL state (`?mode=zen`) so deep-linking and reload preserve the user's mode.

3. **AC3 — Transition uses `expand` preset.** The transition into Zen mode runs the `expand` Framer Motion preset (from Story 4-4) at 250ms duration. The transition out of Zen back to Investigation uses the inverse preset at the same duration. No transition uses default browser easing.

4. **AC4 — Mode is route-gated.** Pressing `⌘+4` on `/queue`, `/approvals`, or `/regulator-lens` is a no-op (or shows the existing toast pattern from Story 12.1's mode switcher saying "Zen mode is only available inside a case"). The mode store does not switch.

5. **AC5 — Tests.** New tests in `modeStore.test.ts`:
   - `accepts_zen_as_a_valid_mode_value`
   - `cmd_4_switches_to_zen_only_on_case_routes`
   - `transition_uses_expand_preset_at_250ms`

6. **AC6 — `make lint` + `make test` clean.**

## Tasks / Subtasks

- [ ] **Task 1 — Mode store** (AC: #2)
  - [ ] Add `'zen'` to the mode union type in `modeStore.ts`
  - [ ] Wire URL state persistence
- [ ] **Task 2 — Keystroke binding** (AC: #1, #4)
  - [ ] Register `⌘+4` / `Ctrl+4` on case routes
  - [ ] No-op on non-case routes
- [ ] **Task 3 — Transition motion** (AC: #3)
  - [ ] Wrap the case canvas in a Framer Motion `<AnimatePresence>` or equivalent that uses the `expand` preset on `mode` change
- [ ] **Task 4 — Tests** (AC: #5, #6)
  - [ ] Update `modeStore.test.ts`
  - [ ] `make lint` + `make test` clean
  - [ ] Update `Documentation/implementation-artifacts/sprint-status.yaml` to `review`

## Dev Notes

- **Zen mode visual treatment lands in 8.2.** This story produces a working ⌘+4 switch that toggles the mode store value but visually only triggers the transition motion — the dark canvas, large type, evidence dock, etc. all come in 8.2. After 8.1 alone, pressing ⌘+4 will run the `expand` motion on the existing Investigation layout.
- **The `expand` preset** is documented in `apps/cockpit-ui/src/lib/motion/presets.ts` from Story 4-4. Reuse, don't redefine.
- **Route-gating** is intentional: zen is a writing mode that only makes sense inside a case context.

### File List

**To modify**
- `apps/cockpit-ui/src/stores/modeStore.ts`
- `apps/cockpit-ui/src/stores/modeStore.test.ts`
- `apps/cockpit-ui/src/components/cockpit/CommandPalette/keyboard.ts` (or whichever module owns Story 4-7's mode shortcuts)
- `apps/cockpit-ui/src/routes/cases.$caseId.tsx` (wrap canvas in motion preset)
- `Documentation/implementation-artifacts/sprint-status.yaml`
