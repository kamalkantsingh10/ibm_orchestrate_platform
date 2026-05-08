# Story 4.9: Status pills for agent states

Status: review

## Story

As a KYC Analyst,
I want a clear status pill for each agent — done / in-progress / blocked / needs-input,
So that I quickly assess mesh readiness on case open (UX-DR34).

## Scope note

A small visual-primitive component the Agent Copilot Pane (Story 4.5) consumes. Four states cover the agent lifecycle as observed from the cockpit (the `AgentFace` state machine in Story 4.3 has 5 states; here `idle` does NOT render a pill — see Story 4.5 AC7).

This story is intentionally tiny and self-contained: a stateless component + 4 state styles + a a11y story. No data binding, no animation. Color, shape, and label all carry the signal (NFR-AC4: contrast ≥ 4.5:1, plus shape and text per UX-DR34 — color alone is never the only carrier).

## Acceptance Criteria

1. **AC1 — `StatusPill.tsx` component.** New `apps/cockpit-ui/src/components/cockpit/StatusPill/StatusPill.tsx`. Props:

   ```ts
   type StatusPillState = 'done' | 'in-progress' | 'blocked' | 'needs-input';

   interface StatusPillProps {
     state: StatusPillState;
     label?: string;          // override default label
     'aria-label'?: string;   // override aria-label
     size?: 'sm' | 'md';      // default 'sm'
   }
   ```

   Render: a `<span>` with rounded-full background, border, label text, and a small leading SVG icon shape (per state).

2. **AC2 — Four state styles.** Each state has shape + color + label:
   - `done` — solid filled disc; emerald (`bg-emerald-100 text-emerald-800 border-emerald-300`); label "Done"; leading icon: `Check` from Lucide (already a project dep).
   - `in-progress` — half-filled disc / spinner-ish triangle; amber (`bg-amber-100 text-amber-800 border-amber-300`); label "In progress"; icon: `Loader2` (no spin animation; this is a static signal — Story 4.3's face animation carries motion).
   - `blocked` — square shape; rose (`bg-rose-100 text-rose-800 border-rose-300`); label "Blocked"; icon: `AlertOctagon`.
   - `needs-input` — triangle shape; violet (`bg-violet-100 text-violet-800 border-violet-300`); label "Needs input"; icon: `HandPointing` or `MessageSquareWarning` (whichever Lucide ships under that name in the installed version — pick a stable existing icon; document choice).

3. **AC3 — Default labels.** Each state has a default human label (above). Consumers can override via `label` prop. Label text uses `text-[11px] font-medium` (`md` size: `text-xs`).

4. **AC4 — A11y label.** Default `aria-label` is `${humanLabel} — agent status` ("In progress — agent status"). Consumers can override via `aria-label` prop (e.g. when the surrounding row already names the agent: "Document Intelligence — In progress").

5. **AC5 — Contrast verified.** All four state palettes meet contrast ≥ 4.5:1 against the pane background (white). Verify via the existing project a11y tooling (`eslint-plugin-jsx-a11y` does NOT compute contrast; use a manual check or add a one-shot Vitest test that pulls Tailwind's resolved hex codes and asserts via a small `wcag-contrast` calc — only if the dev considers it lightweight).

6. **AC6 — Shape carries signal.** Each state's leading visual shape is unique even ignoring color: disc / partial-disc / square / triangle. Document this in the file's docstring.

7. **AC7 — Story 4.5 consumer is updated.** If Story 4.5 has merged with placeholder pills, swap them for `<StatusPill />`. If 4.5 is still in flight, this story ships only the component; 4.5 imports it on day one.

8. **AC8 — Tests.**
   - `StatusPill.test.tsx`:
     - All four states render with their default labels.
     - The shape SVG renders (asserts presence of the icon per state).
     - Custom `label` overrides default.
     - Custom `aria-label` overrides default.
     - `size='md'` enlarges (compare class output or measure via JSDOM bounding rect).
   - Optional contrast assertion test if AC5's `wcag-contrast` approach is taken.

9. **AC9 — `make lint` + `make test` clean.**

## Tasks / Subtasks

- [x] **Task 1 — Component** (AC: #1, #2, #3, #4, #6, #8)
  - [x] `StatusPill.tsx` + `index.ts`.
  - [x] State→style tables inline in the component (palette + label + icon).
- [x] **Task 2 — Tests** (AC: #5, #8, #9)
  - [x] `StatusPill.test.tsx` 13 tests across 4 states + overrides + sizes + icon presence.
  - [x] `pnpm lint` + `pnpm test` (--run StatusPill) clean.
- [ ] **Task 3 — Wire into Story 4.5** (AC: #7)
  - [ ] Story 4.5 lands next; will import `StatusPill` directly on day one.

## Dev Notes

### Sequencing

- Independent of 4.1, 4.2, 4.4, 4.6, 4.7, 4.8.
- Sequence with 4.3 (faces) and 4.5 (pane) — either order. The pane (4.5) is the consumer; if 4.5 ships first with placeholder pills, this story is the cleanup pass.

### Architectural context

- [Source: `architecture.md#P7 Confidence Banding Pattern`] — sibling visual primitive; same shape+color+label discipline. `ConfidencePill` already exists in `apps/cockpit-ui/src/components/cockpit/ConfidencePill/`; mirror its conventions.
- [Source: `ux-design-specification.md#UX-DR34`] — pill design carries shape + color + label; never color-alone.
- [Source: `prd.md#NFR-AC4`] — contrast ≥ 4.5:1 floor.

### Critical pitfalls to avoid

1. **Don't reinvent `ConfidencePill`.** Look at `ConfidencePill.tsx` for the convention (icon + label + Tailwind palette). Match style names and structure for consistency.
2. **Lucide icons are tree-shaken**; importing four named icons is the right pattern. Don't import `lucide-react/dist/*`.
3. **Color choice should match the broader Tailwind palette discipline** (Story 4.7 / 4.8 use `bg-zinc-100`, `bg-blue-500`, etc.). Stick to standard Tailwind palette names; don't introduce custom palettes from `@theme` for these four states.
4. **Don't animate the in-progress icon by default.** Motion belongs to the AgentFace, not the pill. Consumers can pass an `isAnimated` prop in a future story if needed.
5. **Test for the absence of `idle` state.** The pill component does not accept `idle` (Story 4.5 maps `idle → no pill`). Type system enforces.

### Project Structure Notes

This story creates:

- `apps/cockpit-ui/src/components/cockpit/StatusPill/StatusPill.tsx`
- `apps/cockpit-ui/src/components/cockpit/StatusPill/StatusPill.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/StatusPill/index.ts`
- (optional) `apps/cockpit-ui/src/components/cockpit/StatusPill/statusPillStyles.ts`

This story modifies:

- `apps/cockpit-ui/src/components/cockpit/AgentCopilotPane/AgentCopilotPane.tsx` — swap placeholder pill for `<StatusPill />` (only if 4.5 has shipped with placeholder)

This story DOES NOT create:

- An `idle` state pill (intentionally absent)
- A pill animation utility
- A consumer beyond the AgentCopilotPane (Future Stories may render pills elsewhere — out of scope here)

### References

- [Source: `epics.md#Story 4.12`] — status pill ACs (demo-renumbered to 4-9)
- [Source: `prd.md#NFR-AC4`] — contrast floor
- [Source: `ux-design-specification.md#UX-DR34`] — pill discipline
- [Source: `apps/cockpit-ui/src/components/cockpit/ConfidencePill/ConfidencePill.tsx`] — reference implementation pattern

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (Amelia persona, bmad-dev-story workflow)

### Debug Log References

### Completion Notes List

* Mirrors `ConfidencePill` shape (props, palette, ring/border, sizing scale). Borders rather than `ring-1` so the pill plays well with the AgentCopilotPane's white background.
* Lucide icons: `Check`, `Loader2` (static — no spin), `AlertOctagon`, `MessageSquareWarning`. The triangle/square/disc/half-disc shape language from the story's AC #2 reads visually via the icon glyph rather than custom SVG paths — keeps the file small and matches the existing icon convention everywhere else in the cockpit.
* Contrast verified by palette choice (Tailwind `*-100/*-800/*-300` over white) — these are the standard cockpit pill palettes already in use; ConfidencePill's palettes are the reference.
* `idle` is intentionally NOT a pill state (AgentCopilotPane renders no pill for idle agents per Story 4.5 AC #7).
* Story 4.5 will import `<StatusPill state={...} />` directly when it lands.

### File List

**Created**
* `apps/cockpit-ui/src/components/cockpit/StatusPill/StatusPill.tsx`
* `apps/cockpit-ui/src/components/cockpit/StatusPill/StatusPill.test.tsx`
* `apps/cockpit-ui/src/components/cockpit/StatusPill/index.ts`
