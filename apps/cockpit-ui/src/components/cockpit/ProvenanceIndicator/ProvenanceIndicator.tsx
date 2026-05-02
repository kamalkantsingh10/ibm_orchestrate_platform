// ProvenanceIndicator — Story 3.6 AC #4.
//
// Inline composite of source-icon + ConfidencePill (Story 3.7). Click is
// the only interaction (hover-popover deferred to Story 6-7). Used by the
// DocumentsPanel on every extracted field row.

import { FileText } from 'lucide-react';
import clsx from 'clsx';
import type { components } from '@/api-types';
import { ConfidenceBand, toBand } from '@/lib/confidence';
import { ConfidencePill, bandLabel } from '@/components/cockpit/ConfidencePill';

type Provenance = components['schemas']['Provenance'];

export interface ProvenanceIndicatorProps {
  provenance: Provenance;
  onClick?: () => void;
  size?: 'sm' | 'md';
}

export function ProvenanceIndicator({
  provenance,
  onClick,
  size = 'md',
}: ProvenanceIndicatorProps): JSX.Element {
  const interactive = typeof onClick === 'function';

  // The contract guarantees confidence_band consistency; trust it.
  const band = (provenance.confidence_band as ConfidenceBand) ?? toBand(provenance.confidence);
  const pct = Math.round(provenance.confidence * 100);
  const label = bandLabel(band);

  const ariaLabel =
    `Field provenance: source ${provenance.source_agent} · ${provenance.source_system}, ` +
    `confidence ${label} (${pct}%)` +
    (interactive ? ' — click to inspect' : '');

  const composedClasses = clsx(
    'inline-flex items-center gap-1.5',
    interactive
      ? 'cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-400 rounded-full'
      : '',
  );

  const inner = (
    <>
      <FileText
        aria-hidden="true"
        className={size === 'sm' ? 'w-2.5 h-2.5' : 'w-3 h-3 text-zinc-500'}
      />
      <ConfidencePill
        confidence={provenance.confidence}
        band={band}
        variant={size === 'sm' ? 'inline-small' : 'inline-default'}
      />
    </>
  );

  if (interactive) {
    return (
      <button type="button" className={composedClasses} aria-label={ariaLabel} onClick={onClick}>
        {inner}
      </button>
    );
  }
  return (
    <span className={composedClasses} aria-label={ariaLabel} role="group">
      {inner}
    </span>
  );
}
