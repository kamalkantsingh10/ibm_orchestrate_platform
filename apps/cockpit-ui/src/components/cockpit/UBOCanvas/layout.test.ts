import { describe, expect, it } from 'vitest';
import vora from './__fixtures__/vora-ubo-graph.json';
import { toReactFlowGraph, type UBOGraph } from './adapter';
import { layoutWithDagre } from './layout';

const voraGraph = vora as unknown as UBOGraph;

describe('layoutWithDagre', () => {
  it('returns finite positions for every node', () => {
    const adapted = toReactFlowGraph(voraGraph);
    const laidOut = layoutWithDagre(adapted.nodes, adapted.edges);
    for (const node of laidOut.nodes) {
      expect(Number.isFinite(node.position.x)).toBe(true);
      expect(Number.isFinite(node.position.y)).toBe(true);
    }
  });

  it('is deterministic across runs with the same input', () => {
    const adapted = toReactFlowGraph(voraGraph);
    const a = layoutWithDagre(adapted.nodes, adapted.edges);
    const b = layoutWithDagre(adapted.nodes, adapted.edges);
    for (let i = 0; i < a.nodes.length; i++) {
      expect(a.nodes[i].position).toEqual(b.nodes[i].position);
    }
  });

  it('places the root entity at lower y than its children in TB direction', () => {
    const adapted = toReactFlowGraph(voraGraph);
    const { nodes } = layoutWithDagre(adapted.nodes, adapted.edges, 'TB');
    const root = nodes.find((n) => n.id === 'ubo_e_u67120mh2024ptc444789');
    const directors = nodes.filter((n) => n.id.startsWith('ubo_p_'));
    expect(root).toBeDefined();
    // In TB layout, the root (target of every edge) sits at the bottom rank.
    for (const dir of directors) {
      expect(dir.position.y).toBeLessThan(root!.position.y);
    }
  });
});
