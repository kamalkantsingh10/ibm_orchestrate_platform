// Queue Rail — Story 2.3 + Story 4.2 (keyboard focus visual).
// Presentational vertical list of cases. The /queue route owns data fetching
// and passes pending/error props down. Story 4.1 reorders before passing
// (server-side); Story 4.2 adds focusedIndex for keyboard nav; Story 4.9
// will overlay status pills.

import { useEffect, useRef } from 'react';
import type { Case, CaseState } from '@/lib/types/case';
import { badgeFor } from '@/lib/caseState';
import { formatRelative } from '@/lib/formatRelative';

export interface QueueRailProps {
  cases: Case[];
  activeCaseId?: string;
  onSelect?: (caseId: string) => void;
  isPending?: boolean;
  isError?: boolean;
  onRetry?: () => void;
  /** Story 4.2 — keyboard-focused row index; -1 = no focus. */
  focusedIndex?: number;
}

const RAIL_CLASSES =
  // TODO(epic-4): extract surface-warm to a Tailwind @theme token.
  'flex h-full w-[260px] flex-col border-r border-zinc-200 bg-[#FAFAF9]';

export function QueueRail({
  cases,
  activeCaseId,
  onSelect,
  isPending,
  isError,
  onRetry,
  focusedIndex = -1,
}: QueueRailProps) {
  if (isError) {
    return (
      <div className={RAIL_CLASSES}>
        <div role="alert" className="p-3 text-sm text-red-700">
          Could not load cases.{' '}
          {onRetry ? (
            <button type="button" onClick={onRetry} className="ml-1 underline hover:text-red-900">
              Retry
            </button>
          ) : null}
        </div>
      </div>
    );
  }

  if (isPending && cases.length === 0) {
    return (
      <div className={RAIL_CLASSES}>
        <ul className="flex flex-col" data-testid="queue-rail-skeleton">
          {Array.from({ length: 4 }).map((_, idx) => (
            <li key={idx} className="h-16 animate-pulse border-b border-zinc-100 bg-zinc-100" />
          ))}
        </ul>
      </div>
    );
  }

  if (cases.length === 0) {
    return (
      <div className={RAIL_CLASSES}>
        <div className="p-4 text-sm text-zinc-600">
          <p className="font-medium">No cases yet.</p>
          <p className="mt-1 text-xs text-zinc-500">
            Run <code className="rounded bg-zinc-100 px-1">make seed</code> to load fixture cases.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={RAIL_CLASSES}>
      <ul className="flex flex-col">
        {cases.map((c, i) => (
          <QueueRow
            key={c.id}
            caseItem={c}
            isActive={c.id === activeCaseId}
            isFocused={i === focusedIndex}
            onSelect={onSelect}
          />
        ))}
      </ul>
    </div>
  );
}

interface QueueRowProps {
  caseItem: Case;
  isActive: boolean;
  isFocused: boolean;
  onSelect?: (caseId: string) => void;
}

function QueueRow({ caseItem, isActive, isFocused, onSelect }: QueueRowProps) {
  const badge = badgeFor(caseItem.state as CaseState);
  const name = truncate(caseItem.customer_metadata.customer_name, 28);
  const relative = formatRelative(caseItem.created_at);
  const buttonRef = useRef<HTMLButtonElement | null>(null);

  // Move DOM focus when the keyboard hook flags this row. SR announces the
  // row's content; users without SR see the visual focus ring.
  useEffect(() => {
    if (isFocused && document.activeElement !== buttonRef.current) {
      buttonRef.current?.focus({ preventScroll: false });
    }
  }, [isFocused]);

  // hover:bg-zinc-100 is intentional — the rail bg is #FAFAF9 (≈zinc-50),
  // so zinc-100 (#f4f4f5) is the first shade that visibly contrasts. The
  // duration-100 ease-out matches Story 4.4's `snap` motion preset (CSS
  // mirror of `lib/motion.ts` `snap`); kept as Tailwind utilities here
  // because the row state isn't a Framer Motion variant.
  const baseClasses =
    'flex h-16 w-full items-center justify-between gap-3 border-b border-zinc-100 px-3 py-2 text-left transition-[background-color,border-color] duration-100 ease-out hover:bg-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500';
  const activeClasses = isActive ? 'border-l-2 border-l-blue-500 bg-zinc-100' : '';
  const focusedClasses = isFocused && !isActive ? 'border-l-2 border-l-zinc-400 bg-zinc-50' : '';

  return (
    <li>
      <button
        ref={buttonRef}
        type="button"
        data-focused={isFocused ? 'true' : undefined}
        onClick={() => onSelect?.(caseItem.id)}
        className={`${baseClasses} ${activeClasses} ${focusedClasses}`}
      >
        <span className="flex min-w-0 flex-col">
          <span className="truncate text-sm font-medium text-zinc-900">{name}</span>
          <span className="truncate text-xs text-zinc-500">{relative}</span>
        </span>
        <span
          className={`shrink-0 rounded-sm px-1.5 py-0.5 text-[11px] font-medium ${badge.classes}`}
        >
          {badge.label}
        </span>
      </button>
    </li>
  );
}

function truncate(value: string, max: number): string {
  return value.length > max ? `${value.slice(0, max - 1)}…` : value;
}
