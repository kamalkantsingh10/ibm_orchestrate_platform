// ScreeningPanel — Story 6.3 / AC #4.
//
// Wraps the 3-column ScreeningExplainer cards with the shared
// CollapsiblePanel chrome. Auto-expands on first data arrival when there's
// at least one hit. Hero-tints amber when ≥ 1 open hit exists.
//
// Auto-dismissed hits live under a <details> disclosure so the audit trail
// stays legible without crowding the canvas.

import { useEffect, useRef, useState } from 'react';
import type { components } from '@/api-types';
import { CollapsiblePanel } from '@/components/cockpit/CollapsiblePanel';
import { ScreeningExplainer } from '@/components/cockpit/ScreeningExplainer';
import { useScreeningHits } from '@/hooks/useScreeningHits';
import { useScreeningSubjectResolver } from '@/hooks/useScreeningSubjectResolver';

type ScreeningHit = components['schemas']['ScreeningHit'];

export interface ScreeningPanelProps {
  caseId: string;
  onOpenReasoningTrace: (agentActionId: string | null, hitId: string) => void;
}

function _agentActionId(hit: ScreeningHit): string | null {
  return hit.name_match_score.provenance.evidence_ids[0] ?? null;
}

export function ScreeningPanel({ caseId, onOpenReasoningTrace }: ScreeningPanelProps) {
  const { data, isPending, isError } = useScreeningHits(caseId);
  const resolveSubject = useScreeningSubjectResolver(caseId);
  const [expanded, setExpanded] = useState<boolean>(false);
  const hasAutoExpanded = useRef<boolean>(false);

  const hits = data?.hits ?? [];
  const openHits = hits.filter((h) => h.disposition === 'open');
  const dismissedHits = hits.filter((h) => h.disposition === 'dismissed_by_agent');

  useEffect(() => {
    if (data && hits.length > 0 && !hasAutoExpanded.current) {
      setExpanded(true);
      hasAutoExpanded.current = true;
    }
  }, [data, hits.length]);

  let summary: string;
  if (isPending && data == null) {
    summary = 'Screening…';
  } else if (data == null && !isError) {
    summary = '—';
  } else if (hits.length === 0) {
    summary = 'No matches';
  } else {
    summary = `${openHits.length} open · ${dismissedHits.length} auto-dismissed`;
  }

  const tone: 'default' | 'attention' = openHits.length >= 1 ? 'attention' : 'default';

  const handleClick = (hit: ScreeningHit) => {
    onOpenReasoningTrace(_agentActionId(hit), hit.hit_id);
  };

  return (
    <CollapsiblePanel
      title="Screening"
      summary={summary}
      expanded={expanded}
      onToggle={setExpanded}
      tone={tone}
    >
      {isError ? (
        <div className="text-sm text-rose-700">Could not load screening results.</div>
      ) : isPending && data == null ? (
        <div className="text-sm text-zinc-500">Loading screening hits…</div>
      ) : openHits.length === 0 && dismissedHits.length === 0 ? (
        <div className="text-sm text-zinc-500">No matches surfaced.</div>
      ) : (
        <div className="flex flex-col gap-2">
          {openHits.map((hit) => {
            const resolved = resolveSubject({
              subjectId: hit.subject_id,
              fallbackName: hit.matched_name,
            });
            return (
              <ScreeningExplainer
                key={hit.hit_id}
                hit={hit}
                subjectName={resolved.name}
                subjectDob={resolved.dob}
                onOpenSlideOut={() => handleClick(hit)}
              />
            );
          })}
          {dismissedHits.length > 0 ? (
            <details className="mt-1 rounded-md border border-zinc-200 bg-white px-3 py-2">
              <summary className="cursor-pointer text-xs text-zinc-600">
                {dismissedHits.length} auto-dismissed (review)
              </summary>
              <div className="mt-2 flex flex-col gap-2">
                {dismissedHits.map((hit) => {
                  const resolved = resolveSubject({
                    subjectId: hit.subject_id,
                    fallbackName: hit.matched_name,
                  });
                  return (
                    <ScreeningExplainer
                      key={hit.hit_id}
                      hit={hit}
                      subjectName={resolved.name}
                      subjectDob={resolved.dob}
                      dimmed
                      onOpenSlideOut={() => handleClick(hit)}
                    />
                  );
                })}
              </div>
            </details>
          ) : null}
        </div>
      )}
    </CollapsiblePanel>
  );
}
