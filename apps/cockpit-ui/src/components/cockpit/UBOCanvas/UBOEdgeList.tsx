// Accessibility companion for UBOCanvas — Story 5.4 / AC #9.
//
// react-flow 11 edges are not natively keyboard-focusable. We render this
// list below the canvas so screen readers + keyboard users can reach every
// edge. Story 5.5 wires the row click; in 5.4 it's a no-op.

import type { UBOEdge, UBOGraph } from './adapter';
import { bandLabelText, edgeLabel } from './style';

interface UBOEdgeListProps {
  graph: UBOGraph;
  onEdgeClick?: (edge: UBOEdge) => void;
}

function describeEdge(edge: UBOEdge): string {
  const label = edgeLabel(edge);
  const band = edge.confidence.provenance.confidence_band;
  const confLabel = bandLabelText(band);
  const flag = edge.nominee_flag === 'nominee_suspected' ? ' (nominee suspected)' : '';
  return `${edge.kind} ${label} from ${edge.from_id} to ${edge.to_id} — ${confLabel} confidence${flag}`;
}

export function UBOEdgeList({ graph, onEdgeClick }: UBOEdgeListProps) {
  return (
    <div className="mt-3 border-t border-zinc-200 pt-3">
      <h3 className="text-xs font-medium text-zinc-700 mb-2">Ownership relationships</h3>
      <ul aria-label="UBO graph relationships" className="space-y-1">
        {graph.edges.map((edge) => {
          const isFlagged = edge.nominee_flag === 'nominee_suspected';
          return (
            <li key={`${edge.kind}-${edge.from_id}-${edge.to_id}`}>
              <button
                type="button"
                onClick={() => onEdgeClick?.(edge)}
                className={`w-full text-left text-xs rounded px-2 py-1 hover:bg-zinc-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-500 ${
                  isFlagged ? 'text-rose-700' : 'text-zinc-700'
                }`}
                data-edge-flag={edge.nominee_flag}
                data-edge-id={`${edge.kind}-${edge.from_id}-${edge.to_id}`}
              >
                {describeEdge(edge)}
                {edge.rationale ? (
                  <span className="block text-[11px] text-zinc-500 mt-0.5">{edge.rationale}</span>
                ) : null}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
