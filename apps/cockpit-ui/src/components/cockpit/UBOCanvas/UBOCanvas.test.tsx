// UBOCanvas — Story 5.4 / AC #11.
//
// react-flow doesn't render edges/nodes when measured size is 0 in jsdom.
// We test the empty/loading/error states + the UBOEdgeList companion +
// the adapter outputs (covered in adapter.test.ts) rather than asserting
// on rendered edge DOM, which is unreliable in jsdom.

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import vora from './__fixtures__/vora-ubo-graph.json';
import { UBOCanvas, type UBOEdge, type UBOGraph } from './index';

const voraGraph = vora as unknown as UBOGraph;

describe('UBOCanvas', () => {
  it('renders empty state when graph is null and not pending', () => {
    render(<UBOCanvas graph={null} />);
    expect(screen.getByTestId('ubo-canvas-empty')).toBeInTheDocument();
    expect(screen.getByText(/UBO graph not built yet/i)).toBeInTheDocument();
  });

  it('renders skeleton when isPending and graph is null', () => {
    render(<UBOCanvas graph={null} isPending />);
    expect(screen.getByTestId('ubo-canvas-skeleton')).toBeInTheDocument();
    expect(screen.getByText(/Building UBO graph/i)).toBeInTheDocument();
  });

  it('renders error state with alert role', () => {
    render(<UBOCanvas graph={null} isError />);
    const alert = screen.getByRole('alert');
    expect(alert).toBeInTheDocument();
    expect(alert).toHaveTextContent(/Could not load UBO graph/i);
  });

  it('renders the UBOEdgeList companion below the canvas with 6 rows for Vora', () => {
    render(<UBOCanvas graph={voraGraph} />);
    const list = screen.getByLabelText(/UBO graph relationships/i);
    expect(list).toBeInTheDocument();
    const rows = list.querySelectorAll('li');
    expect(rows).toHaveLength(6);
  });

  it('marks the three nominee_suspected edges in the edge list', () => {
    render(<UBOCanvas graph={voraGraph} />);
    const flagged = document.querySelectorAll('[data-edge-flag="nominee_suspected"]');
    expect(flagged).toHaveLength(3);
  });

  it('shows the foreign-corporate rationale text in the edge list', () => {
    render(<UBOCanvas graph={voraGraph} />);
    expect(
      screen.getByText(/Foreign corporate holder \(SG\) with 70.0% ownership/i),
    ).toBeInTheDocument();
  });

  it('invokes onEdgeClick when an edge list row is clicked', () => {
    const onEdgeClick = vi.fn();
    render(<UBOCanvas graph={voraGraph} onEdgeClick={onEdgeClick} />);
    const flagged = document.querySelectorAll('[data-edge-flag="nominee_suspected"]');
    fireEvent.click(flagged[0]);
    expect(onEdgeClick).toHaveBeenCalledTimes(1);
    const edge = onEdgeClick.mock.calls[0][0] as UBOEdge;
    expect(edge.nominee_flag).toBe('nominee_suspected');
  });

  it('renders heading "Ownership relationships" above the edge list', () => {
    render(<UBOCanvas graph={voraGraph} />);
    expect(screen.getByText('Ownership relationships')).toBeInTheDocument();
  });

  it('does not render the empty state when a graph is provided', () => {
    render(<UBOCanvas graph={voraGraph} />);
    expect(screen.queryByTestId('ubo-canvas-empty')).not.toBeInTheDocument();
  });
});
