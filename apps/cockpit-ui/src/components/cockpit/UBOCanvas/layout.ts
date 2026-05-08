// Dagre-driven deterministic layout for UBOCanvas — Story 5.4 / AC #2.
//
// react-flow doesn't ship a layout primitive; we run dagre on the
// (nodes, edges) tuple, then write the resulting positions back onto each
// react-flow node. Determinism enables Vitest snapshot-style tests.

import dagre from 'dagre';
import type { Edge, Node } from 'reactflow';

const NODE_WIDTH = 180;
const NODE_HEIGHT = 64;

export function layoutWithDagre(
  nodes: Node[],
  edges: Edge[],
  direction: 'TB' | 'LR' = 'TB',
): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: direction, ranksep: 80, nodesep: 40 });
  g.setDefaultEdgeLabel(() => ({}));

  for (const node of nodes) {
    g.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }
  for (const edge of edges) {
    g.setEdge(edge.source, edge.target);
  }

  dagre.layout(g);

  const positionedNodes: Node[] = nodes.map((node) => {
    const pos = g.node(node.id);
    return {
      ...node,
      position: {
        x: pos.x - NODE_WIDTH / 2,
        y: pos.y - NODE_HEIGHT / 2,
      },
      // dagre positions are top-left when rendered via the offset above.
      targetPosition: direction === 'LR' ? ('left' as const) : ('top' as const),
      sourcePosition: direction === 'LR' ? ('right' as const) : ('bottom' as const),
    };
  });

  return { nodes: positionedNodes, edges };
}
