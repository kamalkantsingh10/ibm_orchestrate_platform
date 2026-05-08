# Story 12.4: Agent activity strip and UBO refresh

Status: backlog

## Story

As an officer needing mesh activity legible without dominating the canvas and ownership investigations to fit the work,
I want the right rail to compress 8 agents into a horizontal status strip plus a chronological event log, and the UBO panel to support a full-width expand mode with sober monochrome nodes,
So that the cockpit signals what's happening without the noise of "No activity yet" and the UBO drag-correct interaction has the canvas it needs.

## Scope note

Depends on 12.1 (tokens, full-viewport shell, agent-rail grid column) and 12.2 (canvas section frames). Two cohesive workstreams that share the right edge of the canvas:

1. **Agent activity (`apps/cockpit-ui/src/components/cockpit/AgentCopilotPane/`).** Rebuild the right rail. Today it stacks 8 agents vertically; 5 of 8 say "No activity yet." Replace with a horizontal status strip of 8 face chips at the top + a chronological event log below + a collapse-to-56px option that frees canvas width for the UBO expand mode in this same story.

2. **UBO refresh (`apps/cockpit-ui/src/components/cockpit/UBOCanvas/`, `UBOPanel/`).** Sober node redesign — monochrome rectangles, accent only on flagged nominees, edge labels with ownership %, distinct visual styles for officer-corrected vs system-derived edges. Add an `Expand` toggle on the UBO section header that expands the canvas to full canvas-row width (collapsing the Identity stub to a one-line marker) and collapses the agent rail to 56px.

The Story 5-5 drag-correct functionality is preserved end-to-end. The 8-illustrated-agent-face SVGs from Story 4-3 are reused inside the new strip; only their container changes.

## Acceptance Criteria

### Agent activity strip

1. **AC1 — Horizontal status strip.** At the top of the agent rail (above any event log), render a single ~72px-tall row showing 8 agent face chips in a horizontal layout. Each chip:
   - 56px square containing the agent's face SVG (Story 4-3) at full size
   - A 4px ring around the chip indicating state: `idle` → `ink-200` outline / `running` → `accent-claret` pulsing ring / `complete` → `signal-sage` filled check / `error` → `signal-rose` outline
   - Agent name below the chip in `text-micro` `ink-700`, single-line truncated.
   - The 8 agents in fixed order: Case Supervisor · Document Intelligence · Entity Verification · UBO Graph · Screening · Risk Scoring · Writing · Cockpit Chat.

2. **AC2 — Chronological event log.** Beneath the strip, an event log occupying the rest of the rail height. Each event is one row in `text-caption` showing `<time> · <agent> · <event>`. Events are ordered newest-first. Each row has a 2px left rule in the agent's accent color (or `ink-300` if no per-agent accent assigned) so events thread visually by agent. Examples (rendered from existing ledger data):
   - `11:42 · Document Intelligence · extracted 6 fields (94% mean confidence)`
   - `11:43 · Risk Scoring · 35 / medium`
   - The event log subscribes to the existing SSE feed (Story 4-6) so events update live.

3. **AC3 — Collapsible to 56px.** A chevron at the agent rail's top-left edge toggles a collapsed state. Collapsed:
   - Rail width shrinks from 360px (default in 12.1's grid) to 56px, freeing canvas width
   - The horizontal strip becomes a 8-tall vertical stack of just the face chips (no name labels, no event log)
   - Same chip ring states preserved
   - Click a collapsed chip → expand the rail back to 360px and scroll the event log to that agent's most recent event.

4. **AC4 — "Active now" emphasis.** When any agent is in `running` state, its chip in the strip pulses subtly (use the existing `motion` utility from Story 4-4). All idle chips dim to 70% opacity to deemphasize them. When no agents are running, all chips are at 100% opacity.

5. **AC5 — Replaces the existing vertical 8-row pane.** The current `AgentCopilotPane.tsx` flat-list layout is fully replaced. The 8-row pane is deleted; tests are updated.

### UBO refresh

6. **AC6 — Expand toggle on the UBO section header.** New `Expand` button (right-aligned in the section header, like the Documents `+ Add documents` button in 12.2). Toggling expands the UBO canvas to 100% of the canvas-row width. When expanded:
   - Identity section above collapses to a single-line marker (already a stub from 12.2)
   - Agent rail collapses to 56px (fires the same collapse as AC3)
   - The expanded UBO canvas is at least 800px tall to give react-flow room to lay out nodes without overlap
   - `Collapse` toggle returns to the original layout.

7. **AC7 — Sober node design.** Each node is a rounded rectangle, 120 × 44 px, `paper` background, 1px `ink-200` border. Inside:
   - Left: 16px monogram or icon (Person → user glyph; Entity → building glyph)
   - Center: name in `text-body` 500, single-line truncated
   - Below: identifier (CIN / DIN / passport last 4) in `text-micro` `ink-500`
   - Existing per-node `ProvenanceIndicator` is preserved but rendered at 12px in a corner.

8. **AC8 — Flagged nominee styling.** Nodes flagged as nominee or shell get an additional 2px left border in `accent-amber` (no fill change, preserving monochrome). The "MD/D/ND/5%/70%/25%" rendering currently shown next to nodes is removed — those were edge labels that bled into node space.

9. **AC9 — Edge labels with ownership %.** Each edge shows an inline label rendered as a 16px-tall pill: percentage in `text-caption` tabular figures (e.g. `70%`) on a `paper` background with hairline `ink-200` border, positioned at the edge midpoint. Edge labels do not overlap nodes (use react-flow's `EdgeLabelRenderer` API).

10. **AC10 — Officer-corrected vs system-derived edges.** Officer-corrected edges (those with `correction_tag` in the existing UBO data) render as solid `ink-700` 1.5px lines. System-derived edges render as `ink-400` 1px lines. Nominee-suspected edges add a small amber dot at the source endpoint.

11. **AC11 — Skeleton on data load.** While react-flow lays out, render a skeleton (3 rounded rectangles in `ink-100` with hairline borders) instead of the current pre-layout flicker where labels float without edges. Once layout completes, fade in the rendered graph.

12. **AC12 — Drag-correct preserved.** The existing Story 5-5 drag-correct interaction works end-to-end after this rebuild — dragging an edge endpoint to a different node fires the existing learning-event ledger entry. Add one regression test in `UBOCanvas.test.tsx` asserting the drag handler still fires after the refactor.

### General

13. **AC13 — `make lint` + `make test` clean.** Existing tests for `AgentCopilotPane.test.tsx`, `UBOCanvas.test.tsx`, `UBOPanel.test.tsx` are updated. New tests:
    - `AgentActivityStrip.test.tsx::renders_8_chips_in_fixed_order`
    - `AgentActivityStrip.test.tsx::collapse_toggle_changes_rail_width_to_56px`
    - `EventLog.test.tsx::events_render_newest_first`
    - `UBOPanel.test.tsx::expand_toggle_collapses_identity_and_agent_rail`
    - `UBOCanvas.test.tsx::edge_styling_distinguishes_officer_corrected_from_system_derived`
    - `UBOCanvas.test.tsx::drag_correct_handler_still_fires_after_refactor` (regression for Story 5-5)

14. **AC14 — Visual QA at 1440×900.** Manual screenshots: `__visual__/12-4-agent-strip.png`, `12-4-agent-collapsed.png`, `12-4-ubo-default.png`, `12-4-ubo-expanded.png`.

## Tasks / Subtasks

- [ ] **Task 1 — `AgentActivityStrip` component** (AC: #1, #4)
  - [ ] New `apps/cockpit-ui/src/components/cockpit/AgentCopilotPane/AgentActivityStrip.tsx`
  - [ ] Reuse face SVGs from Story 4-3 (`apps/cockpit-ui/src/components/cockpit/AgentFace/`)
- [ ] **Task 2 — `EventLog` component subscribed to SSE** (AC: #2)
- [ ] **Task 3 — Collapse toggle + 56px rail width** (AC: #3)
  - [ ] Wire the rail-width state into the shell grid from Story 12.1 (the `agentrail` column flexes from 360px → 56px)
- [ ] **Task 4 — Replace `AgentCopilotPane` flat list** (AC: #5)
- [ ] **Task 5 — UBO Expand toggle + section integration** (AC: #6)
- [ ] **Task 6 — Sober node design** (AC: #7, #8)
- [ ] **Task 7 — Edge labels via `EdgeLabelRenderer`** (AC: #9)
- [ ] **Task 8 — Edge styling: officer-corrected vs system-derived** (AC: #10)
- [ ] **Task 9 — Skeleton + lazy layout** (AC: #11)
- [ ] **Task 10 — Drag-correct regression test** (AC: #12)
- [ ] **Task 11 — Tests + lint + visual QA** (AC: #13, #14)
  - [ ] Update existing tests
  - [ ] Add new tests
  - [ ] Commit visual screenshots
  - [ ] Update `sprint-status.yaml` to `review`

## Dev Notes

- **The 8 agent face SVGs from Story 4-3** are the demo's signature visual primitive. Reuse them directly; do not redraw or replace.
- **SSE feed (Story 4-6)** already streams agent events. The event log subscribes to the same channel; no new transport.
- **Rail collapse state** lives in TanStack Router URL state (`?rail=collapsed`) so deep-linking works and the state survives navigation.
- **UBO Expand toggle** also lives in URL state (`?ubo=expanded`).
- **`accent-amber` for flagged nominees** is intentional: the spec calls flagged nodes a signal moment. Color usage is restrained elsewhere in the panel so the amber border reads as an actionable flag.
- **Skeleton layout (AC11)** matters for the demo — the current pre-layout flicker (labels visible without edges) is the most jarring moment in the cockpit.
- **Story 5-5 regression test** is non-negotiable. The drag-correct interaction is a load-bearing demo moment; any refactor that breaks it without test failure is a real risk.

### File List

**To create**
- `apps/cockpit-ui/src/components/cockpit/AgentCopilotPane/AgentActivityStrip.tsx`
- `apps/cockpit-ui/src/components/cockpit/AgentCopilotPane/AgentActivityStrip.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/AgentCopilotPane/EventLog.tsx`
- `apps/cockpit-ui/src/components/cockpit/AgentCopilotPane/EventLog.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/UBOPanel/ExpandToggle.tsx`
- `apps/cockpit-ui/src/__tests__/__visual__/12-4-*.png`

**To modify**
- `apps/cockpit-ui/src/components/cockpit/AgentCopilotPane/AgentCopilotPane.tsx`
- `apps/cockpit-ui/src/components/cockpit/AgentCopilotPane/AgentCopilotPane.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/UBOCanvas/UBOCanvas.tsx` (node + edge styling)
- `apps/cockpit-ui/src/components/cockpit/UBOCanvas/UBOCanvas.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/UBOPanel/UBOPanel.tsx`
- `apps/cockpit-ui/src/components/cockpit/UBOPanel/UBOPanel.test.tsx`
- `apps/cockpit-ui/src/routes/__root.tsx` (rail-width state plumbing)
- `Documentation/implementation-artifacts/sprint-status.yaml`
