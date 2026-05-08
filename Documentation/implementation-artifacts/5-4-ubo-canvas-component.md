# Story 5.4: UBO Canvas component

Status: review

## Story

As a KYC Analyst opening a case where Story 5.3's UBO Graph agent has already run,
I want to see the ownership graph as a force-directed react-flow canvas with confidence-banded edges, dashed-red `nominee_suspected` edges, hover tooltips on edges + nodes that surface ownership %, source, confidence, and rationale, and full keyboard accessibility (Tab to navigate nodes/edges, Enter to focus a node's detail tooltip),
So that I understand the case's ownership structure at a glance — including which holders the agent flagged for further inspection — and the UI is ready for Story 5.5's drag-correct interaction (FR15, UX-DR19, NFR-AC3 color-blind safety, NFR-P3 frame-time ≤ 16ms p95).

## Scope note (2026-04-29 demo re-scope)

This story is the demo-equivalent of the bank-buyer Story 5.5. UI fidelity is a load-bearing demo constraint per `architecture.md#Demo Scope Addendum` § What stays — the canvas's signature visual moment (force-directed layout + confidence-banded edges + nominee dashing) is preserved.

| Bank-buyer scope (original 5.5) | Demo replacement in this story |
|---|---|
| ≥ 50 UBO node performance budget (frame-time ≤ 16 ms p95) | **Demo's largest graph is Vora's 6 nodes / 6 edges.** Frame-time budget is unchanged but not formally measured in CI. Manual verification suffices. |
| Tenant-scoped TanStack Query keys | Single-tenant — query key is `['cases', caseId, 'intake', 'ubo_graph']`. |
| ARIA-compliant keyboard-only edge manipulation (drag-correct via Tab + arrow keys) | **Drag-correct itself is Story 5.5.** This story ships read-only canvas with focusable nodes/edges; the drag-correct cursor change + modal land in 5.5. |
| Full-screen overlay on UBO panel click (UX-DR19's "spatial work requiring full focus") | **Inline canvas at full panel width** initially; full-screen overlay deferred to Story 5.9. The component is layout-agnostic — it fills its container. Keep the option open. |

What survives: **react-flow rendering, force-directed layout via dagre OR a small in-component force layout pass, confidence-banded edge colors, dashed-red on `nominee_suspected`, hover tooltips, focusable nodes + edges, screen-reader linearization.**

See `Documentation/planning-artifacts/sprint-change-proposal-2026-04-29.md` § Stories simplified, `architecture.md#Demo Scope Addendum (2026-04-29)`, `ux-design-specification.md` § UBOCanvas.

## Acceptance Criteria

1. **AC1 — Component lives at `apps/cockpit-ui/src/components/cockpit/UBOCanvas/UBOCanvas.tsx`.**

    Public props:
    ```typescript
    import type { components } from '@/api-types';

    type UBOGraph = components['schemas']['UBOGraph'];
    type UBOEdge = components['schemas']['UBOEdge'];
    type UBONode = components['schemas']['UBOPersonNode'] | components['schemas']['UBOEntityNode'];

    export interface UBOCanvasProps {
        graph: UBOGraph | null | undefined;
        isPending?: boolean;
        isError?: boolean;
        /** Story 5.5 — drag-correct callback. Story 5.4 wires the prop but no-ops. */
        onEdgeCorrect?: (edge: UBOEdge, newToId: string) => void;
        /** Story 5.5 — clicking a flagged edge opens a tag modal. Story 5.4 wires the prop but no-ops. */
        onEdgeClick?: (edge: UBOEdge) => void;
        /** When true, renders the canvas in read-only mode (no drag, no edit). Default: false. */
        readOnly?: boolean;
        className?: string;
    }
    ```

    The component:
    * Receives the `UBOGraph` from the calling parent (Story 5.9 passes it via `useUboGraph(caseId)`).
    * Renders nothing meaningful when `graph == null` and `!isPending` (empty state — see AC10).
    * Adapts the `UBOGraph` shape (Pydantic-typed) into react-flow's `Node[]` + `Edge[]` shape via a pure helper `toReactFlowGraph(graph) -> {nodes, edges}` (see AC4).
    * Wraps the rendering in `<ReactFlow>` from `reactflow ^11.11.4` (already in `package.json` per Story 5.3 verification).

2. **AC2 — Layout is force-directed via dagre.**

    Use `dagre` (already in `reactflow` peer deps as of 11.x) for a deterministic force-directed-ish layout. The root entity node anchors at the visual top; directors arrange in a row below; shareholders arrange in a row below directors. Layout direction `LR` (left-to-right) reads better for narrow panels — but `TB` (top-to-bottom) reads better in full-screen. **Default to `TB`**; expose `direction: 'TB' | 'LR'` as an internal helper-arg, default `'TB'`.

    ```typescript
    // apps/cockpit-ui/src/components/cockpit/UBOCanvas/layout.ts
    import dagre from 'dagre';
    import type { Node, Edge } from 'reactflow';

    export function layoutWithDagre(
        nodes: Node[],
        edges: Edge[],
        direction: 'TB' | 'LR' = 'TB',
    ): { nodes: Node[]; edges: Edge[] } { /* … */ }
    ```

    `dagre` produces deterministic positions given the same input, which makes Vitest snapshot-style tests possible. Add `dagre ^0.8.5` to `apps/cockpit-ui/package.json` (`pnpm add dagre`); add `@types/dagre ^0.7.x` as a devDependency.

    **Don't** roll your own physics-based force simulation (`d3-force`, `react-force-graph`) — overkill for the demo's 6-node max + non-deterministic for tests.

3. **AC3 — Custom node types: `UBOEntityNodeView` and `UBOPersonNodeView`.**

    Distinct visual treatment:

    * **Entity node** (corporate): rounded-square, `radius-md`, white background, `border-zinc-300`, **building icon** from `lucide-react`, name displayed in `text-xs font-medium`. CIN displayed in `text-[10px] font-mono text-zinc-500` (only for the root); foreign-corporate shareholders display country code as a small chip after the name (e.g., `[SG]`, `[VG]`).
    * **Person node**: circular, `rounded-full`, `border-zinc-400`, **user icon** from `lucide-react`, name displayed below the circle in `text-xs`. Director nodes get a `director` label chip (`text-[10px] uppercase tracking-wide bg-zinc-100`); the same node also shown as shareholder gets no special chip (the edge's `kind="owns"` is what surfaces ownership).

    Both node views are React components registered with react-flow via `nodeTypes={{ entity: UBOEntityNodeView, person: UBOPersonNodeView }}` (the adapter from AC4 sets each react-flow `node.type` to `"entity"` or `"person"`).

    Tabbable via `tabIndex={0}` on the wrapping `<div>`. Focus ring `focus-visible:ring-2 focus-visible:ring-zinc-500`.

4. **AC4 — `toReactFlowGraph` adapter.**

    ```typescript
    // apps/cockpit-ui/src/components/cockpit/UBOCanvas/adapter.ts
    import type { Node, Edge } from 'reactflow';
    import type { components } from '@/api-types';

    type UBOGraph = components['schemas']['UBOGraph'];

    export function toReactFlowGraph(graph: UBOGraph): { nodes: Node[]; edges: Edge[] } { /* … */ }
    ```

    Mapping rules:

    * **Each `UBONode`** → react-flow `Node`:
      ```typescript
      {
          id: ubo_node.id,                           // unchanged (e.g., "ubo_e_u67120mh...")
          type: ubo_node.kind,                       // "entity" or "person"
          data: { ...ubo_node },                     // pass the full Pydantic shape into the custom node view
          position: { x: 0, y: 0 },                  // dagre overrides; placeholder
      }
      ```

    * **Each `UBOEdge`** → react-flow `Edge`:
      ```typescript
      {
          id: `${ubo_edge.kind}-${ubo_edge.from_id}-${ubo_edge.to_id}`,
          source: ubo_edge.from_id,
          target: ubo_edge.to_id,
          type: 'default',                            // react-flow's smoothstep edge
          label: edgeLabel(ubo_edge),                 // see below
          labelStyle: { fontSize: 10, fontFamily: 'JetBrains Mono' },
          animated: ubo_edge.nominee_flag === 'nominee_suspected',
          style: edgeStyle(ubo_edge),                  // see AC5
          data: { ...ubo_edge },                       // pass the full edge for hover + click handlers
      }
      ```

    `edgeLabel(edge)`:
    * `kind="owns"` → `${ownership_pct}%`
    * `kind="director"` → designation initial (e.g., `MD`, `D`, `ND`, `AD`)
    * `kind="beneficial"` → `B${ownership_pct}%`

5. **AC5 — Edge styling per confidence band + nominee_flag.**

    The edge's `confidence_band` (HIGH / MEDIUM_HIGH / MEDIUM_LOW / LOW) determines stroke color. The `nominee_flag` overrides to red dashed when `"nominee_suspected"`.

    ```typescript
    function edgeStyle(edge: UBOEdge): CSSProperties {
        if (edge.nominee_flag === 'nominee_suspected') {
            return { stroke: '#dc2626', strokeWidth: 2, strokeDasharray: '6,4' };  // rose-600 dashed
        }
        if (edge.nominee_flag === 'officer_corrected') {
            return { stroke: '#059669', strokeWidth: 2 };  // emerald-600 solid (Story 5.5)
        }
        // confidence-band coloring (clear edges only)
        const band = edge.confidence.provenance.confidence_band;
        const stroke = {
            high: '#059669',         // emerald-600
            medium_high: '#0284c7',  // sky-600
            medium_low: '#d97706',   // amber-600
            low: '#dc2626',          // rose-600
        }[band];
        return { stroke, strokeWidth: 1.5 };
    }
    ```

    The Tailwind colors are listed inline (don't rely on Tailwind's tree-shaking — react-flow inline styles can't use Tailwind classes). Mirror the palette from Story 3.7's ConfidencePill.

    The dashed-red treatment satisfies UX-DR19 ("nominee-suspected edges as red dotted") and NFR-AC3 (color is a SECONDARY signal — the dashed pattern + later tooltip-rendered rationale are PRIMARY).

6. **AC6 — Hover tooltip on edges.**

    On `onEdgeMouseEnter`, render a small tooltip (Radix `Tooltip` or `Popover`-like, anchored to the edge's midpoint) showing:
    * Edge type (`Owns`, `Director`, `Beneficial`)
    * `Ownership: 70%` for owns/beneficial
    * `Designation: nominee_director` for director
    * `Source: MCA mock`
    * `Confidence: High (95%)` (from `confidence_band` + `confidence`)
    * Rationale (only when `nominee_flag != "clear"`)

    Use the existing `@/components/ui/tooltip.tsx` (shadcn copy). Wire via `onEdgeMouseEnter` / `onEdgeMouseLeave`. Don't wire react-flow's built-in tooltip — it's not customizable enough.

    **Performance:** the tooltip mounts/unmounts on hover. Keep its render shallow (no nested fetches). Story 6.7 (ReasoningTraceSlideOut) extends this to a slide-out per provenance click; this story only ships the inline tooltip.

7. **AC7 — Hover tooltip on nodes.**

    On `onNodeMouseEnter`, show a tooltip with:
    * Node name (large)
    * Kind (`Entity` / `Person`)
    * Country if non-null
    * CIN if entity + present
    * DIN if person + present
    * For shareholder nodes: total ownership % (sum of incoming `kind="owns"` edges)
    * For director nodes: list of designations across incoming `kind="director"` edges (usually one)

8. **AC8 — Empty / loading / error states.**

    * `isPending && !graph`: skeleton — a faint grey rectangle with a "Building UBO graph…" caption. Frame size ≥ 320px tall to avoid layout shift.
    * `isError`: rose-bordered alert: `"Could not load UBO graph for this case."`. Render a "Retry" button that calls `queryClient.invalidateQueries({ queryKey: ['cases', caseId, 'intake', 'ubo_graph'] })`.
    * `graph == null && !isPending`: empty state with copy: `"UBO graph not built yet. Run intake to populate."` — same visual frame as the skeleton but with an icon.

    All three states pass the 320px-tall frame so the surrounding 2-column grid (Story 5.9) doesn't reflow on data arrival.

9. **AC9 — Accessibility.**

    * `<ReactFlow>` exposes nodes via `tabIndex={0}` on the wrapper; ensure focus ring is visible on focused nodes.
    * Edges in react-flow 11.x are not focusable by default. Add `tabIndex={0}` via the custom edge component (`edgeTypes` registration) — but be aware this requires a custom edge type. **Trade-off decision:** keep edges keyboard-inaccessible in this story; expose the data via the edge **list** in a sibling `<UBOEdgeList />` companion component (a simple table-shaped accessible alternative). Document the choice in the file. The list is rendered hidden (visually) but reachable for screen readers, OR rendered visibly below the canvas as a fallback. **Pick the visible-below variant** — it's also useful for power users.
      ```typescript
      export function UBOEdgeList({ graph, onEdgeClick }: { graph: UBOGraph; onEdgeClick?: (edge: UBOEdge) => void }) { /* … */ }
      ```
      Renders below the canvas: a `<ul>` with one `<li>` per edge; each `<li>` is a `<button>` for keyboard activation; activation is a no-op in this story (Story 5.5 wires the click).
    * `prefers-reduced-motion`: react-flow's default animations should be suppressed via the `proOptions={{ hideAttribution: true }}` plus any explicit `animated: edge.nominee_flag === 'nominee_suspected'` should be conditionally `animated: false` when the user prefers reduced motion. Use a `useReducedMotion()` hook from Framer Motion.
    * Color-blind safety: edge styling uses both color AND dashing pattern (per AC5).

10. **AC10 — `apps/cockpit-ui/src/hooks/useUboGraph.ts` — already shipped by Story 5.3.**

    Story 5.3 ships the hook. **This story uses it but does not modify it.** If the hook isn't yet importable when this story is implemented (Story 5.3 hasn't merged), defer this story.

11. **AC11 — Tests in `apps/cockpit-ui/src/components/cockpit/UBOCanvas/UBOCanvas.test.tsx`.** Cover (Vitest + React Testing Library):

    * **Empty graph:** pass `graph={null}`; assert empty-state copy is visible.
    * **Pending:** pass `graph={null}, isPending={true}`; assert skeleton visible.
    * **Error:** pass `isError={true}`; assert alert + Retry button visible.
    * **Vora canonical fixture:** pass a hand-crafted `UBOGraph` matching Story 5.3's pinned Vora output (6 nodes, 6 edges, 3 nominee_suspected). Assert:
        * 6 nodes rendered (3 person, 3 entity).
        * 6 edges rendered.
        * 3 edges have `data-edge-nominee-flag="nominee_suspected"`.
        * Coastal edge stroke style is `stroke="#dc2626"` and `strokeDasharray="6,4"` (assert via `getComputedStyle` or DOM attribute).
    * **Edge tooltip:** hover over the Coastal edge; assert the tooltip shows `Ownership: 70%`, `Confidence: Medium (55%)`, rationale `"Foreign corporate holder (SG) with 70% ownership; structure suggests nominee/shell"`.
    * **Node tooltip:** hover over Vora's root entity node; assert the tooltip shows `CIN: U67120MH2024PTC444789`.
    * **Edge list:** assert `<UBOEdgeList />` renders 6 list items with the correct text.
    * **`onEdgeClick` wired but no-op (Story 5.5 enables):** assert `props.onEdgeClick` is a function in the rendered component's children.
    * **`prefers-reduced-motion=true`:** mock the hook; assert no edge has `animated: true`.
    * **A11y check:** run `axe-core` on the rendered tree; assert no violations.

12. **AC12 — Snapshot test for `toReactFlowGraph` adapter.**

    `apps/cockpit-ui/src/components/cockpit/UBOCanvas/adapter.test.ts`:
    * Hand-construct the Vora `UBOGraph` (or import a pinned JSON fixture from `apps/cockpit-ui/src/components/cockpit/UBOCanvas/__fixtures__/vora-ubo-graph.json`).
    * Call `toReactFlowGraph(graph)`.
    * Assert the resulting `nodes` array has 6 items, each with the expected `id`, `type`, `data.name`.
    * Assert the resulting `edges` array has 6 items, each with the expected `source`, `target`, `data.kind`, `style.stroke` matching AC5.

13. **AC13 — `make lint && make test` clean.** Net new test count: ≥ 9 in `UBOCanvas.test.tsx`, ≥ 5 in `adapter.test.ts`, ≥ 1 layout helper test (`layout.test.ts` — assert dagre returns finite positions).

14. **AC14 — No backend changes.** This story is pure cockpit-ui. If `make adk-spec` regenerates anything, that's coincidental — don't commit unrelated openapi.yaml changes.

## Tasks / Subtasks

- [x] **Task 1 — Add `dagre` dep** (AC: #2)
  - [x] Subtask 1.1 — `pnpm -F cockpit-ui add dagre @types/dagre` (or equivalent root command).
  - [x] Subtask 1.2 — Verify `package.json` updated; commit `pnpm-lock.yaml`.

- [x] **Task 2 — Author the adapter + layout helpers** (AC: #4, #2)
  - [x] Subtask 2.1 — `apps/cockpit-ui/src/components/cockpit/UBOCanvas/adapter.ts`.
  - [x] Subtask 2.2 — `apps/cockpit-ui/src/components/cockpit/UBOCanvas/layout.ts`.
  - [x] Subtask 2.3 — `apps/cockpit-ui/src/components/cockpit/UBOCanvas/style.ts` for `edgeStyle`/`edgeLabel` helpers (split out for testability).

- [x] **Task 3 — Author the custom node + edge views** (AC: #3, #5, #6, #7)
  - [x] Subtask 3.1 — `UBOEntityNodeView.tsx`.
  - [x] Subtask 3.2 — `UBOPersonNodeView.tsx`.
  - [x] Subtask 3.3 — Tooltip wiring via `@/components/ui/tooltip.tsx`.

- [x] **Task 4 — Author the canvas component** (AC: #1, #8, #9)
  - [x] Subtask 4.1 — `UBOCanvas.tsx` — pulls everything together; wires `<ReactFlow>` with `nodeTypes`, applied dagre layout, edge styling.
  - [x] Subtask 4.2 — Empty / pending / error states (320px-tall frame).
  - [x] Subtask 4.3 — `useReducedMotion()` integration.
  - [x] Subtask 4.4 — `index.ts` re-exports `UBOCanvas` and `UBOEdgeList`.

- [x] **Task 5 — Author UBOEdgeList accessibility companion** (AC: #9)
  - [x] Subtask 5.1 — `UBOEdgeList.tsx`: `<ul>` with `<li>` rows; each row a `<button>`.
  - [x] Subtask 5.2 — Visible by default; `aria-label` documents the list intent.

- [x] **Task 6 — Tests** (AC: #11, #12, #13)
  - [x] Subtask 6.1 — Pinned Vora fixture in `__fixtures__/vora-ubo-graph.json`.
  - [x] Subtask 6.2 — `UBOCanvas.test.tsx` covers all 9 cases from AC11.
  - [x] Subtask 6.3 — `adapter.test.ts` covers all 5 cases from AC12.
  - [x] Subtask 6.4 — `layout.test.ts` asserts dagre output is finite + deterministic.
  - [x] Subtask 6.5 — `make lint && make test` green.

## Dev Notes

### Architectural context (binding)

* [Source: `architecture.md#Frontend Architecture`] react-flow is the chosen graph library (already a dep). Tailwind 4 + shadcn/ui copies for primitives; Framer Motion for motion utilities (Story 4.4).
* [Source: `ux-design-specification.md` § UBOCanvas] target component contract — preserved.
* [Source: `architecture.md#Project-Specific Patterns` P3] every datum is a `ProvenancedField` (the edge's confidence). Tooltip surfaces source_system, source_agent, confidence_band, evidence_ids.
* [Source: `ux-design-specification.md` § Confidence bands never rely on color alone] dashed pattern + label rationale.

### Critical pitfalls

1. **react-flow 11 vs 12 API differences.** The repo pins `reactflow ^11.11.4` (per `apps/cockpit-ui/package.json`). Don't accidentally `pnpm add reactflow@latest` — 12.x is `@xyflow/react` and a breaking rename. Confirm version before writing the imports.

2. **`dagre` is not a peer dep of react-flow 11.** It must be added explicitly (Task 1). The dagre→react-flow adapter pattern is documented in react-flow's own examples; skim before authoring `layout.ts`.

3. **Inline styles on edges, NOT Tailwind classes.** react-flow's `edge.style` is a CSS `style` object, not a `className`. Tailwind colors must be expanded to hex (per AC5).

4. **Edge tooltips are NOT a react-flow built-in.** You must implement them via `onEdgeMouseEnter` / `onEdgeMouseLeave` callbacks + a custom positioned overlay. Use `<TooltipProvider>` from shadcn at the canvas root.

5. **`nominee_suspected` edges are `animated: true` by default** — react-flow renders this as a flowing dashed pattern, which combined with `strokeDasharray` produces the canonical "moving ants" effect. Test with `prefers-reduced-motion` to ensure the animation is suppressed (per AC9).

6. **`Coastal Equity Partners Pte Ltd` and `Anchor Trust Services (BVI)` are long names.** They WILL overflow a 100px-wide entity node. Truncate with CSS `text-overflow: ellipsis` + tooltip showing the full name.

7. **`useUboGraph` queries the per-agent intake row.** If Story 5.3's `GET /v1/cases/{case_id}/intake/{agent_id}` route returns the persisted JSON blob, the data may have `confidence_band` strings vs the OpenAPI-emitted enum values. Verify by inspecting the actual response shape — both should be lowercase snake_case but watch for `MEDIUM_LOW` vs `medium_low`. The Pydantic `ConfidenceBand.value` is `medium_low`; that's what lands on the wire.

8. **Don't fetch the graph inside `<UBOCanvas>`.** Story 5.9 will fetch via `useUboGraph` in the parent route component and pass it down. This component is a pure-rendering component (data in, JSX out). Tests pass `graph` directly; no MSW / network mocks needed.

9. **`tabIndex={0}` on react-flow nodes via the custom node view.** react-flow's wrapper element doesn't expose `tabIndex` on its own — you must add it on your custom node component's outermost `<div>`.

10. **`framer-motion` is already in the repo** — `useReducedMotion` hook lives there. Don't import from `framer/animation` — that's a different package.

### Story dependencies

* **Strict prereqs:** Story 5.3 (UBO Graph agent) — provides the `UBOGraph` Pydantic shape and `useUboGraph` hook.
* **Reads from:** Story 3.7 (ConfidencePill) — color palette consistency for edge colors.
* **Read by:** Story 5.5 (drag-correct) — wires `onEdgeClick` and `onEdgeCorrect`. Story 5.9 (UBO + Risk panels on Case Canvas) — places this canvas into the panel grid.

### Project Structure Notes

This story creates:
- `apps/cockpit-ui/src/components/cockpit/UBOCanvas/UBOCanvas.tsx`
- `apps/cockpit-ui/src/components/cockpit/UBOCanvas/UBOEntityNodeView.tsx`
- `apps/cockpit-ui/src/components/cockpit/UBOCanvas/UBOPersonNodeView.tsx`
- `apps/cockpit-ui/src/components/cockpit/UBOCanvas/UBOEdgeList.tsx`
- `apps/cockpit-ui/src/components/cockpit/UBOCanvas/adapter.ts`
- `apps/cockpit-ui/src/components/cockpit/UBOCanvas/layout.ts`
- `apps/cockpit-ui/src/components/cockpit/UBOCanvas/style.ts`
- `apps/cockpit-ui/src/components/cockpit/UBOCanvas/index.ts`
- `apps/cockpit-ui/src/components/cockpit/UBOCanvas/UBOCanvas.test.tsx`
- `apps/cockpit-ui/src/components/cockpit/UBOCanvas/adapter.test.ts`
- `apps/cockpit-ui/src/components/cockpit/UBOCanvas/layout.test.ts`
- `apps/cockpit-ui/src/components/cockpit/UBOCanvas/__fixtures__/vora-ubo-graph.json`

This story modifies:
- `apps/cockpit-ui/package.json` — adds `dagre`, `@types/dagre`
- `apps/cockpit-ui/pnpm-lock.yaml` — locked

This story DOES NOT create:
- The drag-correct interaction (Story 5.5)
- A learning-event ledger entry path (Story 5.5)
- The wired-into-case-canvas placement (Story 5.9)
- A backend route (no API changes)

### References

- [Source: `architecture.md#Frontend Architecture`] react-flow chosen
- [Source: `ux-design-specification.md` § UBOCanvas] target component contract
- [Source: `epics.md#Epic 5` § Story 5.5] original AC (re-scoped here)
- [Source: `prd.md#FR15, NFR-AC3, NFR-P3`] UBO graph rendering, color-blind safety, frame-time budget
- [Source: `5-3-ubo-graph-agent-basic.md`] `UBOGraph` shape; pinned Vora fixture (3 nominee edges)
- [Source: `3-7-confidence-pill-component.md`] confidence-band color palette

### Demo verification protocol

```bash
# After Story 5.3 has run intake on Vora, this story is purely UI.
# Boot the dev stack:
make dev

# Open the browser to:
# http://localhost:5173/cases/case_01KQC7GQ70GYHP15CZ8JB5ZT6A
# (Vora's pinned ID)

# Manually verify:
# 1. UBO panel area renders the canvas with 6 nodes laid out top-down (root entity at top).
# 2. Three edges are dashed-red (Coastal, Anchor, A K Filing).
# 3. Hover each edge → tooltip shows ownership %, source, rationale.
# 4. Hover root entity → tooltip shows CIN.
# 5. Tab into the canvas → focus ring appears on a node.
# 6. UBOEdgeList below the canvas lists 6 rows with correct text.
# 7. Open browser DevTools → toggle "prefers-reduced-motion: reduce" via Rendering tab → reload → confirm nominee edges are NOT animated.

# Run unit tests:
make test
# Expected: green; UBOCanvas / adapter / layout test suites visible in coverage.

# axe-core check:
poetry -C apps/cockpit-ui run vitest --grep 'a11y'
# Expected: no violations.
```

If any step fails, the bug is in this story's deliverables; do not ship until green.

## Dev Agent Record

### Agent Model Used

(claude-opus-4-7 + Amelia persona, bmad-dev-story workflow)

### Debug Log References

### Completion Notes List

### File List

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-05-08 | Story 5.4 drafted. Demo replacement for the bank-buyer Story 5.5: react-flow + dagre layout, custom entity/person node views, confidence-banded + nominee-dashed edges, hover tooltips, accessible UBOEdgeList companion, read-only canvas (drag-correct deferred to 5.5). |
