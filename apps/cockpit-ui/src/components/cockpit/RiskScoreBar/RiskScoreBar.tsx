// RiskScoreBar — Story 5.7.
//
// Horizontal stacked bar with one segment per RiskComponent. Segment widths
// are proportional to `contribution` (which sums to `total`). Tooltips
// surface value/weight/contribution + rationale per segment. Total + band
// pill render to the right. Animations: 200ms cross-fade on segments whose
// contribution changed since the last render (suppressed under
// prefers-reduced-motion).

import { useEffect, useRef, useState, type CSSProperties, type KeyboardEvent } from 'react';
import { useReducedMotion } from 'framer-motion';
import type { components } from '@/api-types';

export type RiskScore = components['schemas']['RiskScore'];
export type RiskComponent = components['schemas']['RiskComponent'];
type RiskComponentName = RiskComponent['name'];

export interface RiskScoreBarProps {
  score: RiskScore | null | undefined;
  isPending?: boolean;
  isError?: boolean;
  /** Default true. Skipped under prefers-reduced-motion regardless. */
  animate?: boolean;
  onSegmentClick?: (componentName: RiskComponentName) => void;
  className?: string;
}

const COLOR_BY_COMPONENT: Record<RiskComponentName, string> = {
  country: 'bg-sky-500',
  entity_type: 'bg-amber-500',
  ownership_clarity: 'bg-violet-500',
  screening: 'bg-rose-500',
  adverse_media: 'bg-zinc-500',
};

const LABEL_BY_COMPONENT: Record<RiskComponentName, string> = {
  country: 'Country',
  entity_type: 'Entity Type',
  ownership_clarity: 'Ownership Clarity',
  screening: 'Screening',
  adverse_media: 'Adverse Media',
};

const BAND_PILL_CLASSES: Record<RiskScore['band'], string> = {
  low: 'bg-emerald-100 text-emerald-700',
  medium: 'bg-amber-100 text-amber-700',
  high: 'bg-rose-100 text-rose-700',
};

export function RiskScoreBar({
  score,
  isPending,
  isError,
  animate = true,
  onSegmentClick,
  className,
}: RiskScoreBarProps) {
  const reducedMotion = useReducedMotion();
  const previousContributionsRef = useRef<Record<string, number>>({});
  const [pulsing, setPulsing] = useState<Set<string>>(new Set());
  const [hovered, setHovered] = useState<RiskComponent | null>(null);
  const animationsEnabled = animate && !reducedMotion;

  useEffect(() => {
    if (!score) return;
    const prev = previousContributionsRef.current;
    const next = Object.fromEntries(score.components.map((c) => [c.name, c.contribution]));
    const changed = new Set<string>();
    if (Object.keys(prev).length > 0 && animationsEnabled) {
      for (const c of score.components) {
        if (prev[c.name] !== undefined && !Object.is(prev[c.name], c.contribution)) {
          changed.add(c.name);
        }
      }
    }
    previousContributionsRef.current = next;
    if (changed.size === 0) return undefined;
    // Defer state update one tick so React 19's eslint rule (no setState
    // synchronously in an effect) is satisfied; the visual delay is invisible.
    const startTimer = setTimeout(() => setPulsing(changed), 0);
    const endTimer = setTimeout(() => setPulsing(new Set()), 200);
    return () => {
      clearTimeout(startTimer);
      clearTimeout(endTimer);
    };
  }, [score, animationsEnabled]);

  // ── states ──
  if (isError) {
    return (
      <div
        role="alert"
        className={`flex min-h-[64px] items-center justify-between rounded border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-700 ${className ?? ''}`}
      >
        <span>Could not compute risk score.</span>
      </div>
    );
  }
  if (isPending && !score) {
    return (
      <div
        data-testid="risk-bar-skeleton"
        className={`flex min-h-[64px] animate-pulse items-center gap-3 rounded border border-zinc-200 bg-zinc-50 p-2 text-sm text-zinc-500 ${className ?? ''}`}
      >
        <div className="h-8 flex-1 rounded-md bg-zinc-200" />
        <div className="h-8 w-12 rounded bg-zinc-200" />
      </div>
    );
  }
  if (!score) {
    return (
      <div
        data-testid="risk-bar-empty"
        className={`flex min-h-[64px] items-center justify-center rounded border border-dashed border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-500 ${className ?? ''}`}
      >
        Risk score not computed. Run intake to populate.
      </div>
    );
  }

  // ── rendered bar ──
  const totalContribution = score.components.reduce((sum, c) => sum + c.contribution, 0);
  const safeTotal = totalContribution > 0 ? totalContribution : 1;

  return (
    <div className={className}>
      <div className="grid grid-cols-[1fr_auto] items-center gap-3">
        <div
          role="img"
          aria-label={`Risk score: ${score.total}, band ${score.band}`}
          className="flex h-8 w-full overflow-hidden rounded-md border border-zinc-200 bg-white"
          data-testid="risk-bar"
        >
          {score.components.map((c) => {
            const widthPct = (c.contribution / safeTotal) * 100;
            const isPulsing = pulsing.has(c.name);
            const segStyle: CSSProperties = {
              width: `${widthPct}%`,
              opacity: isPulsing ? 0.6 : 1,
              transition: animationsEnabled
                ? 'width 200ms ease-out, opacity 200ms ease-out'
                : 'none',
            };
            return (
              <button
                type="button"
                key={c.name}
                style={segStyle}
                aria-label={`${LABEL_BY_COMPONENT[c.name]}, value ${c.value}, weight ${c.weight}, contributes ${c.contribution} of ${score.total}`}
                onMouseEnter={() => setHovered(c)}
                onMouseLeave={() => setHovered(null)}
                onFocus={() => setHovered(c)}
                onBlur={() => setHovered(null)}
                onClick={() => onSegmentClick?.(c.name)}
                onKeyDown={(e: KeyboardEvent<HTMLButtonElement>) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onSegmentClick?.(c.name);
                  }
                }}
                data-testid={`risk-segment-${c.name}`}
                data-component-name={c.name}
                data-contribution={c.contribution}
                className={`${COLOR_BY_COMPONENT[c.name]} h-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-700`}
              />
            );
          })}
        </div>
        <div className="flex flex-col items-end">
          <div className="text-2xl font-semibold tabular-nums text-zinc-900">{score.total}</div>
          <div
            className={`mt-0.5 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${BAND_PILL_CLASSES[score.band]}`}
            data-testid="risk-band-pill"
          >
            {score.band}
          </div>
        </div>
      </div>

      {hovered ? <SegmentTooltip component={hovered} /> : null}

      <ul aria-label="Risk components" className="mt-3 grid grid-cols-1 gap-1 sm:grid-cols-2">
        {score.components.map((c) => (
          <li
            key={c.name}
            className="flex items-center gap-2 text-xs text-zinc-700"
            data-testid={`risk-legend-${c.name}`}
          >
            <span className={`inline-block h-2.5 w-2.5 rounded-sm ${COLOR_BY_COMPONENT[c.name]}`} />
            <span className="font-medium">{LABEL_BY_COMPONENT[c.name]}</span>
            <span className="text-zinc-500 tabular-nums">{c.contribution.toFixed(1)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function SegmentTooltip({ component }: { component: RiskComponent }) {
  return (
    <div
      role="tooltip"
      data-testid="risk-segment-tooltip"
      className="mt-2 w-60 rounded border border-zinc-200 bg-white px-3 py-2 text-xs shadow-md"
    >
      <div className="font-semibold text-zinc-900">{LABEL_BY_COMPONENT[component.name]}</div>
      <div className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-zinc-700">
        <span>Value:</span>
        <span className="tabular-nums">{component.value}</span>
        <span>Weight:</span>
        <span className="tabular-nums">{component.weight}</span>
        <span>Contribution:</span>
        <span className="tabular-nums">{component.contribution}</span>
      </div>
      <div className="mt-1 border-t border-zinc-100 pt-1 text-zinc-600">{component.rationale}</div>
    </div>
  );
}
