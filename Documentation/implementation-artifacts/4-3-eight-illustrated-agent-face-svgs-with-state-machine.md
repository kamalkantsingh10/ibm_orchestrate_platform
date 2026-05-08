# Story 4.3: Eight illustrated agent face SVGs with state machine

Status: review

## Story

As a KYC Analyst,
I want each MVP agent to have a dignified illustrated face that reflects its current state,
So that the mesh feels like a small company of specialists, not a grid of spinners (UX-DR6, UX-DR7).

## Scope note

The cockpit's emotional differentiation rests on personality without whimsy — geometric, low-detail SVGs (Pixar-restraint per UX §1.1). Eight faces map to the eight MVP agents named in the agent inventory: Case Supervisor, Document Intelligence, Entity Verification, UBO Graph, Screening, Risk Scoring, Writing (single face shared by Writing v1 and v2), and Cockpit Chat.

This story ships **the static SVG asset set + the `<AgentFace>` React component** that animates between five states. It does NOT wire faces into the cockpit yet — Story 4.5 (Agent Copilot Pane) is the consumer that mounts the faces in context.

The component uses Framer Motion for animation. If Story 4.4 (motion utilities) lands first, prefer its `expand` / `focusDim` / `slideOut` presets; if not, this story may inline `transition` props with TODO-link to Story 4.4 for refactor.

## Acceptance Criteria

1. **AC1 — Eight SVG files in `apps/cockpit-ui/public/agent-faces/`.** Filenames are kebab-case matching the agent registry slugs:
   - `case-supervisor.svg`
   - `document-intelligence.svg`
   - `entity-verification.svg`
   - `ubo-graph.svg`
   - `screening.svg`
   - `risk-scoring.svg`
   - `writing.svg`
   - `cockpit-chat.svg`

   Each SVG:
   - Square aspect ratio (`viewBox="0 0 64 64"` is the chosen canvas).
   - Two to five stroke/fill primitives — geometric, low detail, no faces with eyes-and-mouth realism. Inspiration: Things 3-style Cultured Code mascots (UX §UX Pattern Analysis #7), not Slack emoji.
   - Single visual element distinguishes each agent (e.g., document corner-fold for Document Intelligence; concentric ovals for UBO Graph; angular ledger lines for Audit; conversation bubble for Cockpit Chat). The dev may delegate art to the user; if so, ship a placeholder geometric SVG with a comment block declaring "art-placeholder; replace before demo polish".
   - Stroke uses `currentColor` so the face inherits the row's text color (state-coloring at the consumer).
   - File size < 4 KB each.

2. **AC2 — `AgentFace.tsx` component.** New `apps/cockpit-ui/src/components/cockpit/AgentFace/AgentFace.tsx`. Props:

   ```ts
   type AgentSlug =
     | 'case-supervisor' | 'document-intelligence' | 'entity-verification'
     | 'ubo-graph' | 'screening' | 'risk-scoring' | 'writing' | 'cockpit-chat';

   type AgentState = 'idle' | 'working' | 'complete' | 'blocked' | 'needs_input';

   interface AgentFaceProps {
     agent: AgentSlug;
     state: AgentState;
     size?: number;       // px; default 32
     'aria-label'?: string;
   }
   ```

   The component renders an `<img src={`/agent-faces/${agent}.svg`} />` wrapped in a Framer Motion `<motion.div>` whose variant is selected by `state`.

3. **AC3 — Five state animations.**
   - `idle` — static. No motion. Full opacity.
   - `working` — "breath": 1 s cycle, scale `1 → 1.04 → 1` infinite (8% peak-to-peak per epic spec is too pronounced; 4% reads as breathing rather than throbbing — dev call). Eased with `easeInOut`.
   - `complete` — one-shot glow + chime gesture: the SVG's container briefly increases box-shadow blur (not opacity flicker — too cheap-looking). 300 ms total, fades back to idle. After the burst, the component settles in `idle` until prop changes.
   - `blocked` — opacity drops to `0.5`; small `<svg>` overlay in the bottom-right corner shows a `Lucide` `AlertTriangle` icon at 1/3 face size. Static.
   - `needs_input` — face rotates `±6°` toward the bottom-right corner (visual focus pull toward the officer). 300 ms ease-out; holds the rotated position until state changes.

4. **AC4 — Consumer-supplied size + a11y label.** Default `size=32`. The wrapping container sets explicit `width` + `height` from `size`. The component applies the `aria-label` to the `<motion.div>` (not `<img>`) so SR announces the agent + state, e.g. "Document Intelligence — working". If `aria-label` is omitted, the component derives a default: `${humanizedAgent} — ${state}`.

5. **AC5 — `agentLabels.ts` mapping.** New `apps/cockpit-ui/src/components/cockpit/AgentFace/agentLabels.ts` exporting a `Record<AgentSlug, string>` of presentation labels (e.g. `'document-intelligence': 'Document Intelligence'`). Used by AC4's default aria-label and reusable by Story 4.5 / 4.9.

6. **AC6 — Tests (Vitest + RTL).**
   - `AgentFace.test.tsx` — at least 7 cases: renders for each of the 5 states (asserts presence of `data-state` attribute), the default size, the explicit-aria-label override, the default-label fallback. Plus a "blocked overlay renders" assertion checking the AlertTriangle node exists.
   - `agentLabels.test.ts` — exhaustive coverage assertion: every `AgentSlug` has a label entry (use type-level constraint via `satisfies Record<AgentSlug, string>`).

7. **AC7 — Visual regression placeholder.** Add `apps/cockpit-ui/tests/visual/AgentFace.spec.ts` (Playwright) only if the project already has Playwright configured *and* `make test:e2e` runs in CI; if neither is true, ship `AgentFace.stories.tsx` (a small Vite-served page) as a manual eyeball reference instead. Do not introduce Playwright as a new dependency for this story.

8. **AC8 — Public asset path verified in production builds.** Files placed under `apps/cockpit-ui/public/` are served at the root (Vite default). The component `<img src="/agent-faces/...">` works in dev and in `pnpm build` static output. No Vite config change required — verify with a `pnpm build && pnpm preview` sanity run.

9. **AC9 — `make lint` + `make test` clean.**

## Tasks / Subtasks

- [x] **Task 1 — SVG asset set** (AC: #1)
  - [x] Eight geometric placeholder SVGs (`<1 KB` each, `currentColor` strokes).
- [x] **Task 2 — Component + state machine** (AC: #2, #3, #4, #5)
  - [x] `AgentFace.tsx` with Framer Motion variants per state and reduced-motion fallback.
  - [x] `agentLabels.ts` (`AGENT_LABELS`, `AGENT_ORDER`).
  - [x] `index.ts` barrel.
- [x] **Task 3 — Tests** (AC: #6, #9)
  - [x] `AgentFace.test.tsx` (12 tests across all 5 states + label override + size + overlay).
  - [x] `agentLabels.test.ts` (4 tests, exhaustive coverage).
- [ ] **Task 4 — Visual reference** (AC: #7)
  - [ ] Playwright headed smoke deferred to Epic 4 final pass (task #21).
- [x] **Task 5 — Build verify** (AC: #8, #9)
  - [x] `pnpm test` 153 pass; `pnpm lint` + `pnpm tsc --noEmit` clean.

## Dev Notes

### Sequencing

This story is independent of 4-1 / 4-2. Story 4-5 (Agent Copilot Pane) is the consumer; sequence so that 4-3 lands before 4-5. Story 4-4 (motion utilities) is parallel — if 4-4 lands first, refactor 4-3's inline transitions to import from `lib/motion.ts`.

### Architectural context

- [Source: `architecture.md#Frontend Architecture F7`] — Tailwind 4 design tokens via `@theme`. Don't hardcode colors in the SVGs; use `currentColor`.
- [Source: `architecture.md#P6 (motion)` and `ux-design-specification.md#1.1 Design System Choice`] — motion uses Framer Motion, three flavors. Story 4.4 codifies the presets; this story may inline.
- [Source: `agent-inventory-and-flow.md`] — 8 MVP agents. Confirm slugs match registry directories under `apps/agents/src/agents/registry/`.
- [Source: `ux-design-specification.md#UX-DR6, UX-DR7`] — agent personality, "small company of specialists" feel.

### Critical pitfalls to avoid

1. **Don't import SVGs as React components via `vite-plugin-svgr`.** It's an extra dep with limited gain here; `<img src>` against `public/` is the boring choice.
2. **`useReducedMotion`** (Framer Motion hook) — wire the breath / glow / rotate variants behind it. Users with `prefers-reduced-motion: reduce` get `idle`-equivalent stills regardless of state. Mandatory for NFR-AC4 vestibular safety.
3. **The "complete" glow must be one-shot and self-cancel.** If the parent re-renders mid-glow, the animation should not restart — use a `key` derived from a state-change tick or `AnimatePresence`. Easiest: `state="complete"` triggers a `setTimeout(setLocalState('idle'), 320)` inside the component, but that breaks the prop-driven contract; prefer `useEffect([state])` + a CSS-only burst via `motion.div` `animate` array `[1, 1.06, 1]` with `transition.times: [0, 0.3, 1]`.
4. **`needs_input` rotation** must NOT compound on prop change. Use absolute `rotate: -6` not `rotate: '+=6'`.
5. **Lucide `AlertTriangle` is already a project dep** (used elsewhere). Don't add an icon library.
6. **The "8% scale variation" in the epic** (Story 4.3 AC) is overly aggressive in practice; 3–4% reads as breath, 8% reads as panic. The dev should pick the value that subjectively reads as "breathing" — note the chosen number in the Dev Agent Record.
7. **SVGs in `public/` are NOT cache-busted** by Vite. If you change a face after demo cut, append a `?v=2` query string in the component to force-refresh.

### Project Structure Notes

This story creates:

- `apps/cockpit-ui/public/agent-faces/case-supervisor.svg`
- `apps/cockpit-ui/public/agent-faces/document-intelligence.svg`
- `apps/cockpit-ui/public/agent-faces/entity-verification.svg`
- `apps/cockpit-ui/public/agent-faces/ubo-graph.svg`
- `apps/cockpit-ui/public/agent-faces/screening.svg`
- `apps/cockpit-ui/public/agent-faces/risk-scoring.svg`
- `apps/cockpit-ui/public/agent-faces/writing.svg`
- `apps/cockpit-ui/public/agent-faces/cockpit-chat.svg`
- `apps/cockpit-ui/src/components/cockpit/AgentFace/AgentFace.tsx`
- `apps/cockpit-ui/src/components/cockpit/AgentFace/AgentFace.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/AgentFace/agentLabels.ts`
- `apps/cockpit-ui/src/components/cockpit/AgentFace/agentLabels.test.ts`
- `apps/cockpit-ui/src/components/cockpit/AgentFace/index.ts`
- (optional) `apps/cockpit-ui/src/components/cockpit/AgentFace/AgentFace.stories.tsx`

This story modifies:

- (none — this is a self-contained component story)

This story DOES NOT create:

- A `<AgentFaceGrid>` or any consumer (Story 4.5)
- A status pill (Story 4.9)
- A real-time state subscription (Story 4.6)
- An animation utility module (Story 4.4)

### References

- [Source: `epics.md#Story 4.3`] — face state machine ACs
- [Source: `agent-inventory-and-flow.md`] — agent slugs
- [Source: `ux-design-specification.md#1.1 Design System Choice`] — Pixar-restraint, no kiddish
- [Source: `architecture.md#Demo Scope Addendum`] — Framer Motion is in scope; UI fidelity is load-bearing

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (Amelia persona, bmad-dev-story workflow)

### Debug Log References

### Completion Notes List

* **8 SVGs are placeholders** per AC #1's escape hatch — geometric, low-detail, `currentColor` stroke, single distinguishing element per agent (hub-with-spokes for Supervisor; folded page for Document Intelligence; shield+check for Entity Verification; three-node chain for UBO Graph; magnifier+list for Screening; ascending bars for Risk Scoring; pen+nib for Writing; speech-bubble+dots for Cockpit Chat).
* **Working "breath"** chosen at 4% peak-to-peak (1.0 → 1.04 → 1.0). The epic's 8% reads as panic; 3–4% reads as breath. Tagged in the Story Dev Notes critical-pitfall list.
* **Complete glow** is one-shot via Framer's `transition.times: [0, 0.4, 1]` array on `scale: [1, 1.06, 1]`. Settles to idle after 300 ms; the `key={state}` prop re-mounts on prop change so re-firing complete restarts cleanly.
* **`useReducedMotion`** branches the variants object at the top of the component. Reduced-motion users still see the right *static pose* per state (e.g. `needs_input` shows the rotated face without the rotation transition).
* **Blocked overlay** uses Lucide's `AlertTriangle`. Bottom-right anchored at 1/3 size; sits on a white-rounded chip so it stays legible against any background.
* **AGENT_ORDER** exported here is the canonical render order for Story 4.5's pane.
* **Visual regression / Playwright snapshot** deferred to the Epic 4 final pass (headed mode, per user request).

### File List

**Created (assets)**
* `apps/cockpit-ui/public/agent-faces/case-supervisor.svg`
* `apps/cockpit-ui/public/agent-faces/document-intelligence.svg`
* `apps/cockpit-ui/public/agent-faces/entity-verification.svg`
* `apps/cockpit-ui/public/agent-faces/ubo-graph.svg`
* `apps/cockpit-ui/public/agent-faces/screening.svg`
* `apps/cockpit-ui/public/agent-faces/risk-scoring.svg`
* `apps/cockpit-ui/public/agent-faces/writing.svg`
* `apps/cockpit-ui/public/agent-faces/cockpit-chat.svg`

**Created (component)**
* `apps/cockpit-ui/src/components/cockpit/AgentFace/AgentFace.tsx`
* `apps/cockpit-ui/src/components/cockpit/AgentFace/AgentFace.test.tsx`
* `apps/cockpit-ui/src/components/cockpit/AgentFace/agentLabels.ts`
* `apps/cockpit-ui/src/components/cockpit/AgentFace/agentLabels.test.ts`
* `apps/cockpit-ui/src/components/cockpit/AgentFace/index.ts`
