// RiskPanel — Story 5.9 / AC #2.
//
// Wraps RiskScoreBar with CollapsiblePanel chrome + appends decomposition
// rows below the bar when expanded. Auto-expands on first data arrival.

import { useEffect, useRef, useState } from 'react';
import { CollapsiblePanel } from '@/components/cockpit/CollapsiblePanel';
import { RiskScoreBar } from '@/components/cockpit/RiskScoreBar';
import { useRiskScore } from '@/hooks/useRiskScore';
import { RiskDecompositionList } from './RiskDecompositionList';

export interface RiskPanelProps {
  caseId: string;
}

export function RiskPanel({ caseId }: RiskPanelProps) {
  const { data: score, isPending, isError } = useRiskScore(caseId);
  const [expanded, setExpanded] = useState<boolean>(false);
  const hasAutoExpanded = useRef<boolean>(false);

  useEffect(() => {
    if (score != null && !hasAutoExpanded.current) {
      setExpanded(true);
      hasAutoExpanded.current = true;
    }
  }, [score]);

  const summary = score
    ? `${score.total} / 100 · ${score.band.toUpperCase()}`
    : isPending
      ? 'Computing…'
      : '—';

  return (
    <CollapsiblePanel
      title="Risk Score"
      summary={summary}
      expanded={expanded}
      onToggle={setExpanded}
    >
      <RiskScoreBar score={score} isPending={isPending} isError={isError} />
      {score ? <RiskDecompositionList components={score.components} /> : null}
    </CollapsiblePanel>
  );
}
