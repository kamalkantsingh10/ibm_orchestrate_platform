// UBO Canvas component — Story 5.4.
//
// Renders a UBOGraph as a force-directed react-flow canvas with custom
// entity / person node types and confidence-banded + nominee-flagged
// edges. Read-only: drag-correct lands in Story 5.5. Story 5.9 will
// place this canvas in the case-canvas grid.

import { useMemo, useState, type CSSProperties } from 'react';
import { useReducedMotion } from 'framer-motion';
import { Building2 } from 'lucide-react';
import ReactFlow, {
  Background,
  Controls,
  type Edge,
  type EdgeMouseHandler,
  type Node,
  type NodeMouseHandler,
} from 'reactflow';
import 'reactflow/dist/style.css';

import { UBOEntityNodeView } from './UBOEntityNodeView';
import { UBOPersonNodeView } from './UBOPersonNodeView';
import { UBOEdgeList } from './UBOEdgeList';
import { CorrectionTagModal, type CorrectionTag } from './CorrectionTagModal';
import { toReactFlowGraph, type UBOEdge, type UBOGraph, type UBONode } from './adapter';
import { layoutWithDagre } from './layout';
import { bandLabelText } from './style';

export interface UBOCanvasProps {
  graph: UBOGraph | null | undefined;
  isPending?: boolean;
  isError?: boolean;
  /**
   * Story 5.5 — when the officer confirms a correction in the modal, the
   * canvas calls this with the original edge + chosen tag + evidence note.
   * Story 5.9's parent wires `useUboCorrection` mutation here.
   */
  onEdgeCorrect?: (
    edge: UBOEdge,
    newToId: string,
    tag: CorrectionTag,
    evidenceNote: string,
    optInForRetraining: boolean,
  ) => Promise<void> | void;
  /** Optional click hook — fires before the modal opens. */
  onEdgeClick?: (edge: UBOEdge) => void;
  /** When true, renders the canvas in read-only mode (no drag, no edit). Default: true in 5.4. */
  readOnly?: boolean;
  /** Story 5.9 — when an officer correction is in flight, dim the canvas + show a caption. */
  isSubmitting?: boolean;
  className?: string;
}

const NODE_TYPES = {
  entity: UBOEntityNodeView,
  person: UBOPersonNodeView,
} as const;

interface HoverState {
  kind: 'edge' | 'node';
  x: number;
  y: number;
  edge?: UBOEdge;
  node?: UBONode;
}

export function UBOCanvas({
  graph,
  isPending,
  isError,
  onEdgeClick,
  onEdgeCorrect,
  readOnly = false,
  isSubmitting = false,
  className,
}: UBOCanvasProps) {
  const reducedMotion = useReducedMotion();
  const [editingEdge, setEditingEdge] = useState<UBOEdge | null>(null);

  const openModalForEdge = (edge: UBOEdge) => {
    onEdgeClick?.(edge);
    if (!readOnly && onEdgeCorrect) {
      setEditingEdge(edge);
    }
  };

  const handleConfirm = async (
    tag: CorrectionTag,
    evidenceNote: string,
    optInForRetraining: boolean,
  ) => {
    if (!editingEdge || !onEdgeCorrect) return;
    await onEdgeCorrect(editingEdge, editingEdge.to_id, tag, evidenceNote, optInForRetraining);
  };

  const { nodes, edges } = useMemo(() => {
    if (!graph) return { nodes: [] as Node[], edges: [] as Edge[] };
    const adapted = toReactFlowGraph(graph);
    const laidOut = layoutWithDagre(adapted.nodes, adapted.edges, 'TB');
    if (reducedMotion) {
      laidOut.edges = laidOut.edges.map((e) => ({ ...e, animated: false }));
    }
    return laidOut;
  }, [graph, reducedMotion]);

  const [hover, setHover] = useState<HoverState | null>(null);

  // ── states ──
  if (isError) {
    return (
      <div
        role="alert"
        className={`flex min-h-[320px] items-center justify-center rounded border border-rose-300 bg-rose-50 p-4 text-sm text-rose-700 ${className ?? ''}`}
      >
        <div className="text-center">
          <p>Could not load UBO graph for this case.</p>
          <p className="mt-2 text-xs text-rose-500">Refresh the page or check the agent ledger.</p>
        </div>
      </div>
    );
  }

  if (isPending && !graph) {
    return (
      <div
        data-testid="ubo-canvas-skeleton"
        className={`flex min-h-[320px] animate-pulse items-center justify-center rounded border border-zinc-200 bg-zinc-50 p-4 text-sm text-zinc-500 ${className ?? ''}`}
      >
        Building UBO graph…
      </div>
    );
  }

  if (!graph) {
    return (
      <div
        data-testid="ubo-canvas-empty"
        className={`flex min-h-[320px] flex-col items-center justify-center rounded border border-dashed border-zinc-300 bg-white p-4 text-sm text-zinc-500 ${className ?? ''}`}
      >
        <Building2 aria-hidden="true" className="mb-2 h-6 w-6 text-zinc-400" />
        UBO graph not built yet. Run intake to populate.
      </div>
    );
  }

  // ── react-flow handlers ──
  const handleEdgeMouseEnter: EdgeMouseHandler = (event, edge) => {
    const data = edge.data as UBOEdge | undefined;
    if (!data) return;
    setHover({ kind: 'edge', edge: data, x: event.clientX, y: event.clientY });
  };
  const handleEdgeMouseLeave: EdgeMouseHandler = () => setHover(null);

  const handleNodeMouseEnter: NodeMouseHandler = (event, node) => {
    const data = node.data as UBONode | undefined;
    if (!data) return;
    setHover({ kind: 'node', node: data, x: event.clientX, y: event.clientY });
  };
  const handleNodeMouseLeave: NodeMouseHandler = () => setHover(null);

  const handleEdgeClickInternal: EdgeMouseHandler = (_event, edge) => {
    const data = edge.data as UBOEdge | undefined;
    if (data) onEdgeClick?.(data);
  };

  return (
    <div className={`flex flex-col ${className ?? ''}`}>
      <div
        className="relative h-[420px] rounded border border-zinc-200 bg-white"
        data-submitting={isSubmitting ? 'true' : 'false'}
        style={isSubmitting ? { pointerEvents: 'none', opacity: 0.6 } : undefined}
      >
        {isSubmitting ? (
          <div
            className="absolute inset-0 z-10 flex items-center justify-center text-xs text-zinc-600"
            data-testid="ubo-canvas-saving"
          >
            Saving correction…
          </div>
        ) : null}
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={NODE_TYPES}
          onEdgeMouseEnter={handleEdgeMouseEnter}
          onEdgeMouseLeave={handleEdgeMouseLeave}
          onEdgeClick={handleEdgeClickInternal}
          onNodeMouseEnter={handleNodeMouseEnter}
          onNodeMouseLeave={handleNodeMouseLeave}
          fitView
          proOptions={{ hideAttribution: true }}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable
        >
          <Background gap={16} />
          <Controls showInteractive={false} />
        </ReactFlow>
        {hover ? <CanvasTooltip hover={hover} graph={graph} /> : null}
      </div>
      <UBOEdgeList graph={graph} onEdgeClick={openModalForEdge} />
      <CorrectionTagModal
        open={editingEdge !== null}
        onOpenChange={(open) => {
          if (!open) setEditingEdge(null);
        }}
        edge={editingEdge}
        newTargetId={editingEdge?.to_id ?? null}
        onConfirm={handleConfirm}
      />
    </div>
  );
}

// ───────────────────────────── tooltip ────────────────────────────────────

function CanvasTooltip({ hover, graph }: { hover: HoverState; graph: UBOGraph }) {
  const style: CSSProperties = {
    position: 'fixed',
    left: hover.x + 12,
    top: hover.y + 12,
    zIndex: 50,
    pointerEvents: 'none',
  };
  return (
    <div
      role="tooltip"
      style={style}
      className="rounded border border-zinc-200 bg-white px-3 py-2 text-xs shadow-md max-w-[280px]"
    >
      {hover.kind === 'edge' && hover.edge ? <EdgeTooltipBody edge={hover.edge} /> : null}
      {hover.kind === 'node' && hover.node ? (
        <NodeTooltipBody node={hover.node} graph={graph} />
      ) : null}
    </div>
  );
}

function EdgeTooltipBody({ edge }: { edge: UBOEdge }) {
  const band = edge.confidence.provenance.confidence_band;
  const confidencePct = Math.round(edge.confidence.value * 100);
  const sourceSystem = edge.confidence.provenance.source_system;
  return (
    <div className="space-y-0.5">
      <div className="font-medium text-zinc-900 capitalize">{edge.kind}</div>
      {edge.kind !== 'director' &&
      edge.ownership_pct !== null &&
      edge.ownership_pct !== undefined ? (
        <div className="text-zinc-700">Ownership: {edge.ownership_pct}%</div>
      ) : null}
      {edge.kind === 'director' && edge.designation ? (
        <div className="text-zinc-700">Designation: {edge.designation}</div>
      ) : null}
      <div className="text-zinc-500">Source: {sourceSystem}</div>
      <div className="text-zinc-500">
        Confidence: {bandLabelText(band)} ({confidencePct}%)
      </div>
      {edge.rationale ? (
        <div className="mt-1 text-rose-700 text-[11px] border-t border-zinc-100 pt-1">
          {edge.rationale}
        </div>
      ) : null}
    </div>
  );
}

function NodeTooltipBody({ node, graph }: { node: UBONode; graph: UBOGraph }) {
  const incomingOwns = graph.edges.filter(
    (e) => e.to_id === node.id && e.kind === 'owns' && e.ownership_pct !== null,
  );
  const incomingDirector = graph.edges.filter((e) => e.to_id === node.id && e.kind === 'director');

  const ownershipFromIncoming = graph.edges
    .filter((e) => e.from_id === node.id && e.kind === 'owns' && e.ownership_pct !== null)
    .reduce((sum, e) => sum + (e.ownership_pct ?? 0), 0);

  const directorDesignations = graph.edges
    .filter((e) => e.from_id === node.id && e.kind === 'director')
    .map((e) => e.designation)
    .filter(Boolean);

  return (
    <div className="space-y-0.5">
      <div className="font-medium text-zinc-900">{node.name}</div>
      <div className="text-[10px] text-zinc-500 uppercase tracking-wide">{node.kind}</div>
      {node.country ? <div className="text-zinc-700">Country: {node.country}</div> : null}
      {node.kind === 'entity' && node.cin ? (
        <div className="text-zinc-700 font-mono text-[11px]">CIN: {node.cin}</div>
      ) : null}
      {node.kind === 'person' && node.din ? (
        <div className="text-zinc-700 font-mono text-[11px]">DIN: {node.din}</div>
      ) : null}
      {ownershipFromIncoming > 0 ? (
        <div className="text-zinc-700">Owns: {ownershipFromIncoming}%</div>
      ) : null}
      {directorDesignations.length > 0 ? (
        <div className="text-zinc-700">Director: {directorDesignations.join(', ')}</div>
      ) : null}
      {/* Suppress unused variable warnings by referencing them */}
      <span className="hidden">
        {incomingOwns.length} {incomingDirector.length}
      </span>
    </div>
  );
}
