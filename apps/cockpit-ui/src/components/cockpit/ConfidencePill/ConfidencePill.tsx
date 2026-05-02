// ConfidencePill — Story 3.7.
//
// Four-tier banded pill with shape + position + label redundancy
// (NFR-AC3 color-blind safety) in three size variants. The canonical
// confidence renderer for the entire cockpit; consumed first by Story 3.6's
// ProvenanceIndicator.
//
// Visual matrix (dev-facing reference):
//
//   | Variant         | LOW          | MEDIUM_LOW   | MEDIUM_HIGH    | HIGH         | unknown      |
//   |-----------------|--------------|--------------|----------------|--------------|--------------|
//   | inline-small    | △            | ○            | ◐              | ●            | ?            |
//   | inline-default  | △ Low        | ○ Medium     | ◐ Med-High     | ● High       | ? Unknown    |
//   | panel-header    | △ Low 18%    | ○ Medium 62% | ◐ Med-High 78% | ● High 92%   | ? Unknown    |
//
// Color choices (per Story 3.7 Pitfall #15): emerald-600, sky-600,
// amber-600, rose-600 over -50 backgrounds. Ring -600/20.

import clsx from 'clsx';
import { ConfidenceBand, toBand } from '@/lib/confidence';
import { bandLabel, type BandOrUnknown } from './bandLabel';

export interface ConfidencePillProps {
  /** Internal confidence float in [0.0, 1.0]. NaN/inf/<0/>1 → "unknown". */
  confidence: number;
  /** Optional explicit band. Mismatch with `toBand(confidence)` → "unknown". */
  band?: ConfidenceBand;
  /** Visual size variant. Defaults to "inline-default". */
  variant?: 'inline-small' | 'inline-default' | 'panel-header';
  /** Show numeric percentage. Defaults to true for panel-header, false elsewhere. */
  showNumeric?: boolean;
  /** Render as a focusable button with onClick handler. */
  interactive?: boolean;
  onClick?: () => void;
  className?: string;
}

// ───────────── shape SVGs (10×10 viewBox) ─────────────

function HighShape() {
  return (
    <svg data-band-shape="high" aria-hidden="true" viewBox="0 0 10 10" className="w-full h-full">
      <circle cx="5" cy="5" r="3.5" fill="currentColor" />
    </svg>
  );
}

function MediumHighShape() {
  return (
    <svg
      data-band-shape="medium_high"
      aria-hidden="true"
      viewBox="0 0 10 10"
      className="w-full h-full"
    >
      <circle cx="5" cy="5" r="3.5" fill="none" stroke="currentColor" strokeWidth="1.2" />
      <path d="M 5,1.5 A 3.5,3.5 0 0 0 5,8.5 Z" fill="currentColor" />
    </svg>
  );
}

function MediumLowShape() {
  return (
    <svg
      data-band-shape="medium_low"
      aria-hidden="true"
      viewBox="0 0 10 10"
      className="w-full h-full"
    >
      <circle cx="5" cy="5" r="3.2" fill="none" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  );
}

function LowShape() {
  return (
    <svg data-band-shape="low" aria-hidden="true" viewBox="0 0 10 10" className="w-full h-full">
      <path
        d="M 5,1.2 L 9,8.5 L 1,8.5 Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function UnknownShape() {
  return (
    <svg data-band-shape="unknown" aria-hidden="true" viewBox="0 0 10 10" className="w-full h-full">
      <circle
        cx="5"
        cy="5"
        r="3.4"
        fill="none"
        stroke="currentColor"
        strokeWidth="1"
        strokeDasharray="1.5 1"
      />
      <text x="5" y="6.6" textAnchor="middle" fontSize="5" fontWeight="700" fill="currentColor">
        ?
      </text>
    </svg>
  );
}

const SHAPES: Record<BandOrUnknown, () => JSX.Element> = {
  [ConfidenceBand.HIGH]: HighShape,
  [ConfidenceBand.MEDIUM_HIGH]: MediumHighShape,
  [ConfidenceBand.MEDIUM_LOW]: MediumLowShape,
  [ConfidenceBand.LOW]: LowShape,
  unknown: UnknownShape,
};

// ───────────── colors per band (AC3) ─────────────

const COLORS: Record<BandOrUnknown, string> = {
  [ConfidenceBand.HIGH]: 'text-emerald-600 bg-emerald-50 ring-emerald-600/20',
  [ConfidenceBand.MEDIUM_HIGH]: 'text-sky-600 bg-sky-50 ring-sky-600/20',
  [ConfidenceBand.MEDIUM_LOW]: 'text-amber-600 bg-amber-50 ring-amber-600/20',
  [ConfidenceBand.LOW]: 'text-rose-600 bg-rose-50 ring-rose-600/20',
  unknown: 'text-zinc-500 bg-zinc-50 ring-zinc-300',
};

// ───────────── unknown-state warn-once ─────────────

const _warned = new Set<string>();

function warnOnce(key: string, message: string): void {
  if (_warned.has(key)) return;
  _warned.add(key);
  console.warn(message);
}

// ───────────── main component ─────────────

export function ConfidencePill({
  confidence,
  band: explicitBand,
  variant = 'inline-default',
  showNumeric,
  interactive,
  onClick,
  className,
}: ConfidencePillProps): JSX.Element {
  const resolvedShowNumeric = showNumeric ?? variant === 'panel-header';

  // Resolve the band — handle invalid input + mismatched explicit band.
  let band: BandOrUnknown;
  let percentText = '';
  try {
    const derived = toBand(confidence);
    if (explicitBand !== undefined && explicitBand !== derived) {
      warnOnce(
        `${confidence}_${explicitBand}`,
        `ConfidencePill: band ${explicitBand} mismatch with confidence ${confidence} (expected ${derived}); rendering unknown band`,
      );
      band = 'unknown';
    } else {
      band = derived;
      const pct = Math.round(confidence * 100);
      percentText = `${pct}%`;
    }
  } catch {
    warnOnce(
      `invalid_${confidence}`,
      `ConfidencePill: invalid confidence ${confidence}, rendering unknown band`,
    );
    band = 'unknown';
  }

  const Shape = SHAPES[band];
  const label = bandLabel(band);
  const showLabel = variant !== 'inline-small';
  const showPercent = resolvedShowNumeric && band !== 'unknown';

  // Build aria-label — single composite read by screen readers.
  let ariaLabel: string;
  if (band === 'unknown') {
    ariaLabel = 'Confidence: unknown — invalid value';
  } else if (showPercent) {
    ariaLabel = `Confidence: ${label}, ${percentText}`;
  } else if (showLabel) {
    ariaLabel = `Confidence: ${label}`;
  } else {
    // inline-small without numeric — still convey full info to AT
    const pct = band === 'unknown' ? '' : `, ${Math.round(confidence * 100)}%`;
    ariaLabel = `Confidence: ${label}${pct}`;
  }
  if (interactive) {
    ariaLabel = `${ariaLabel} — click to inspect`;
  }

  const sizingClasses =
    variant === 'panel-header' ? 'px-2 py-1 text-sm gap-1.5' : 'px-1.5 py-0.5 text-xs gap-1';

  const shapeSize = variant === 'panel-header' ? 'w-3.5 h-3.5' : 'w-2.5 h-2.5';

  const composedClasses = clsx(
    'inline-flex items-center rounded-full ring-1 transition-colors duration-150 motion-reduce:transition-none',
    sizingClasses,
    COLORS[band],
    interactive &&
      'cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-400',
    className,
  );

  const content = (
    <>
      <span className={clsx('inline-block flex-shrink-0', shapeSize)}>
        <Shape />
      </span>
      {showLabel ? <span className="font-medium">{label}</span> : null}
      {showPercent ? <span className="tabular-nums">{percentText}</span> : null}
    </>
  );

  if (interactive) {
    return (
      <button type="button" className={composedClasses} aria-label={ariaLabel} onClick={onClick}>
        {content}
      </button>
    );
  }

  return (
    <span role="img" aria-label={ariaLabel} className={composedClasses}>
      {content}
    </span>
  );
}
