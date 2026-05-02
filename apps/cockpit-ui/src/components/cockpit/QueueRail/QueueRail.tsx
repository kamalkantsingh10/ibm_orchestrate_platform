// Queue Rail — Story 2.3.
// Presentational vertical list of cases. The /queue route owns data fetching
// and passes pending/error props down. Story 4-1 will reorder before passing;
// Story 4-2 will drive activeCaseId from a Zustand store; Story 4-9 will
// overlay status pills.

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
        {cases.map((c) => (
          <QueueRow key={c.id} caseItem={c} isActive={c.id === activeCaseId} onSelect={onSelect} />
        ))}
      </ul>
    </div>
  );
}

interface QueueRowProps {
  caseItem: Case;
  isActive: boolean;
  onSelect?: (caseId: string) => void;
}

function QueueRow({ caseItem, isActive, onSelect }: QueueRowProps) {
  const badge = badgeFor(caseItem.state as CaseState);
  const name = truncate(caseItem.customer_metadata.customer_name, 28);
  const relative = formatRelative(caseItem.created_at);

  // hover:bg-zinc-100 is intentional — the rail bg is #FAFAF9 (≈zinc-50),
  // so zinc-100 (#f4f4f5) is the first shade that visibly contrasts.
  const baseClasses =
    'flex h-16 w-full items-center justify-between gap-3 border-b border-zinc-100 px-3 py-2 text-left transition-colors hover:bg-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500';
  const activeClasses = isActive ? 'border-l-2 border-l-blue-500 bg-zinc-100' : '';

  return (
    <li>
      <button
        type="button"
        onClick={() => onSelect?.(caseItem.id)}
        className={`${baseClasses} ${activeClasses}`}
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
