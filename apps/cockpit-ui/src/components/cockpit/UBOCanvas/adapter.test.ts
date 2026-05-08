import { describe, expect, it } from 'vitest';
import vora from './__fixtures__/vora-ubo-graph.json';
import { toReactFlowGraph, type UBOGraph } from './adapter';

const voraGraph = vora as unknown as UBOGraph;

describe('toReactFlowGraph', () => {
  it('maps every UBO node to a react-flow node', () => {
    const { nodes } = toReactFlowGraph(voraGraph);
    expect(nodes).toHaveLength(6);
    const types = nodes.map((n) => n.type);
    expect(types.filter((t) => t === 'entity')).toHaveLength(3);
    expect(types.filter((t) => t === 'person')).toHaveLength(3);
  });

  it('preserves UBO node id verbatim and stashes the full shape under data', () => {
    const { nodes } = toReactFlowGraph(voraGraph);
    const root = nodes.find((n) => n.id === 'ubo_e_u67120mh2024ptc444789');
    expect(root).toBeDefined();
    expect(root?.type).toBe('entity');
    expect(root?.data.name).toBe('Vora Capital Holdings Pvt Ltd');
  });

  it('maps every UBO edge to a react-flow edge with deterministic ids', () => {
    const { edges } = toReactFlowGraph(voraGraph);
    expect(edges).toHaveLength(6);
    const ids = edges.map((e) => e.id);
    expect(ids).toContain('owns-ubo_e_coastal_equity_partners_pte_ltd-ubo_e_u67120mh2024ptc444789');
    expect(ids).toContain('director-ubo_p_09876545-ubo_e_u67120mh2024ptc444789');
  });

  it('sets `animated: true` only on nominee_suspected edges', () => {
    const { edges } = toReactFlowGraph(voraGraph);
    const animated = edges.filter((e) => e.animated);
    expect(animated).toHaveLength(3);
  });

  it('flagged edges have rose stroke + dasharray', () => {
    const { edges } = toReactFlowGraph(voraGraph);
    const coastal = edges.find(
      (e) => e.id === 'owns-ubo_e_coastal_equity_partners_pte_ltd-ubo_e_u67120mh2024ptc444789',
    );
    expect(coastal?.style).toMatchObject({
      stroke: '#dc2626',
      strokeDasharray: '6,4',
      strokeWidth: 2,
    });
  });

  it('clear high-confidence edges use emerald stroke', () => {
    const { edges } = toReactFlowGraph(voraGraph);
    const devanshDirector = edges.find(
      (e) => e.id === 'director-ubo_p_09876543-ubo_e_u67120mh2024ptc444789',
    );
    expect(devanshDirector?.style).toMatchObject({ stroke: '#059669', strokeWidth: 1.5 });
  });
});
