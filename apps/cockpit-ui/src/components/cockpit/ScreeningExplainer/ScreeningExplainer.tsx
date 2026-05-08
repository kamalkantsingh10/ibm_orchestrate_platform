// ScreeningExplainer — Story 6.3 / AC #2.
//
// 3-column card: "Matched" / "Didn't match" / "What would change it" — one
// per ScreeningHit. Renders inside a <button> so the whole card is keyboard-
// activatable; click → onOpenSlideOut(hit_id).
//
// Counterfactual sentence is preferred from a server-side reasoning_trace
// (added by Story 6.4); falls back to client-side deriveCounterfactual.

import clsx from 'clsx';
import type { components } from '@/api-types';
import { ConfidencePill } from '@/components/cockpit/ConfidencePill';
import { deriveCounterfactual } from './counterfactual';

type ScreeningHit = components['schemas']['ScreeningHit'];

export interface ScreeningExplainerProps {
  hit: ScreeningHit;
  subjectName: string;
  subjectDob?: string | null;
  dimmed?: boolean;
  onOpenSlideOut: (hitId: string) => void;
}

function _yearOnly(iso: string | null | undefined): string | null {
  if (!iso) return null;
  return iso.slice(0, 4);
}

function _matchedColumn(hit: ScreeningHit): string {
  const pct = Math.round(hit.name_match_score.value * 100);
  return `Name ${pct}% similar`;
}

function _didNotMatchColumn(hit: ScreeningHit, subjectDob: string | null | undefined): string {
  const a = _yearOnly(subjectDob);
  const b = _yearOnly(hit.date_of_birth);
  if (a && b && a !== b) return `DOB ${a} vs ${b}`;
  return '—';
}

function _counterfactual(hit: ScreeningHit, subjectDob: string | null | undefined): string {
  const trace = (hit as { reasoning_trace?: { counterfactual?: string } }).reasoning_trace;
  if (trace?.counterfactual) return trace.counterfactual;
  return deriveCounterfactual(hit, subjectDob ?? null);
}

const _CATEGORY_LABEL: Record<ScreeningHit['categories'][number], string> = {
  sanctions: 'Sanctions',
  pep: 'PEP',
  adverse_media: 'Adverse media',
  law_enforcement: 'Law enforcement',
  watchlist: 'Watchlist',
};

export function ScreeningExplainer({
  hit,
  subjectName,
  subjectDob,
  dimmed,
  onOpenSlideOut,
}: ScreeningExplainerProps) {
  const sourceList = hit.source_lists?.length ? hit.source_lists.join(' · ') : null;
  const ringClass = dimmed
    ? 'opacity-60 hover:ring-2 hover:ring-zinc-300/50'
    : 'hover:ring-2 hover:ring-amber-300/50';

  return (
    <button
      type="button"
      data-testid={`screening-explainer-${hit.hit_id}`}
      data-dismissed={dimmed ? 'true' : undefined}
      onClick={() => onOpenSlideOut(hit.hit_id)}
      className={clsx(
        'w-full rounded-md border border-zinc-200 bg-white px-4 py-3 text-left transition-shadow',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400',
        ringClass,
      )}
    >
      <header className="flex items-start justify-between gap-3 mb-2">
        <div className="min-w-0">
          <div className="text-sm font-semibold text-zinc-900 truncate">{subjectName}</div>
          <div className="mt-0.5 flex flex-wrap gap-1">
            {hit.categories.map((c) => (
              <span
                key={c}
                className="rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-zinc-700"
              >
                {_CATEGORY_LABEL[c]}
              </span>
            ))}
          </div>
        </div>
        <ConfidencePill confidence={hit.name_match_score.value} variant="inline-default" />
      </header>

      <div className="grid grid-cols-3 gap-3 text-sm">
        <div>
          <div className="text-[10px] uppercase tracking-wide text-zinc-500">Matched</div>
          <div className="mt-0.5 text-zinc-700">{_matchedColumn(hit)}</div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-wide text-zinc-500">
            Didn&rsquo;t match
          </div>
          <div className="mt-0.5 text-zinc-700">{_didNotMatchColumn(hit, subjectDob)}</div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-wide text-zinc-500">
            What would change it
          </div>
          <div className="mt-0.5 text-zinc-700">{_counterfactual(hit, subjectDob)}</div>
        </div>
      </div>

      {sourceList ? (
        <footer className="mt-2 text-[11px] text-zinc-500">Source: {sourceList}</footer>
      ) : null}
    </button>
  );
}
