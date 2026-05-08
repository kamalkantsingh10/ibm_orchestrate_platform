// Pure adapter from the Pydantic UBOGraph shape to react-flow's Node/Edge shape.
// Story 5.4 / AC #4. The custom node types use the full UBO node shape via `data`.

import type { Edge, Node } from 'reactflow';
import type { components } from '@/api-types';
import { edgeLabel, edgeStyle } from './style';

export type UBOGraph = components['schemas']['UBOGraph'];
export type UBOEdge = components['schemas']['UBOEdge'];
export type UBONode =
  | components['schemas']['UBOPersonNode']
  | components['schemas']['UBOEntityNode'];
export type UBOPersonNode = components['schemas']['UBOPersonNode'];
export type UBOEntityNode = components['schemas']['UBOEntityNode'];

export function reactFlowEdgeId(edge: UBOEdge): string {
  return `${edge.kind}-${edge.from_id}-${edge.to_id}`;
}

export function toReactFlowGraph(graph: UBOGraph): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = graph.nodes.map((n) => ({
    id: n.id,
    type: n.kind,
    data: { ...n },
    position: { x: 0, y: 0 },
  }));

  const edges: Edge[] = graph.edges.map((e) => ({
    id: reactFlowEdgeId(e),
    source: e.from_id,
    target: e.to_id,
    type: 'default',
    label: edgeLabel(e),
    labelStyle: { fontSize: 10, fontFamily: 'JetBrains Mono, monospace' },
    animated: e.nominee_flag === 'nominee_suspected',
    style: edgeStyle(e),
    data: { ...e },
  }));

  return { nodes, edges };
}
