// UBOPanel — Story 5.9 / AC #1.
//
// Wraps UBOCanvas with the shared CollapsiblePanel chrome and wires the
// drag-correct mutation. Auto-expands on first data arrival; user toggles
// override.

import { useEffect, useRef, useState } from 'react';
import { CollapsiblePanel } from '@/components/cockpit/CollapsiblePanel';
import { UBOCanvas } from '@/components/cockpit/UBOCanvas';
import type { UBOEdge } from '@/components/cockpit/UBOCanvas/adapter';
import type { CorrectionTag } from '@/components/cockpit/UBOCanvas/CorrectionTagModal';
import { useCase } from '@/hooks/useCase';
import { useUboCorrection } from '@/hooks/useUboCorrection';
import { useUboGraph } from '@/hooks/useUboGraph';

export interface UBOPanelProps {
  caseId: string;
}

export function UBOPanel({ caseId }: UBOPanelProps) {
  const { data: caseEnv } = useCase(caseId);
  const { data: graph, isPending, isError } = useUboGraph(caseId);
  const correction = useUboCorrection(caseId);
  const [expanded, setExpanded] = useState<boolean>(false);
  const hasAutoExpanded = useRef<boolean>(false);

  const isIndividual = caseEnv?.customer_metadata?.customer_type === 'individual';

  useEffect(() => {
    if (graph != null && graph.nodes.length > 0 && !hasAutoExpanded.current) {
      setExpanded(true);
      hasAutoExpanded.current = true;
    }
  }, [graph]);

  const summary = graph
    ? `${graph.nodes.length} nodes · ${graph.edges.filter((e) => e.nominee_flag === 'nominee_suspected').length} flagged`
    : isPending
      ? 'Building…'
      : isIndividual
        ? 'N/A — individual customer'
        : '—';

  const handleEdgeCorrect = async (
    edge: UBOEdge,
    newToId: string,
    tag: CorrectionTag,
    evidenceNote: string,
    optInForRetraining: boolean,
  ) => {
    await correction.mutateAsync({
      edge_kind: edge.kind,
      from_id: edge.from_id,
      original_to_id: edge.to_id,
      new_to_id: newToId,
      correction_tag: tag,
      evidence_note: evidenceNote,
      opt_in_for_retraining: optInForRetraining,
    });
  };

  return (
    <CollapsiblePanel
      title="UBO Ownership"
      summary={summary}
      expanded={expanded}
      onToggle={setExpanded}
    >
      {isIndividual && !graph ? (
        <div
          data-testid="ubo-panel-individual"
          className="flex min-h-[120px] flex-col items-center justify-center rounded border border-dashed border-zinc-300 bg-white px-3 py-2 text-center text-sm text-zinc-500"
        >
          <p>Not applicable for individual customers.</p>
          <p className="mt-1 text-xs text-zinc-400">
            UBO graphs only apply to corporate entities (CIN required).
          </p>
        </div>
      ) : (
        <UBOCanvas
          graph={graph}
          isPending={isPending}
          isError={isError}
          onEdgeCorrect={handleEdgeCorrect}
          isSubmitting={correction.isPending}
        />
      )}
    </CollapsiblePanel>
  );
}
