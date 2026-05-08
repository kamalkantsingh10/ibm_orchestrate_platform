// StatusPill — Story 4.9.
//
// Four-state agent status pill consumed by the Agent Copilot Pane (Story
// 4.5). Mirrors the ConfidencePill convention: shape + color + label, never
// color alone (NFR-AC4 floor 4.5:1 contrast on -100/-800 token pairs).
//
// State matrix:
//
//   | state        | shape    | palette  | label        | icon            |
//   |--------------|----------|----------|--------------|-----------------|
//   | done         | disc     | emerald  | Done         | Check           |
//   | in-progress  | half     | amber    | In progress  | Loader2 (static)|
//   | blocked      | square   | rose     | Blocked      | AlertOctagon    |
//   | needs-input  | triangle | violet   | Needs input  | MessageSquareWarning

import clsx from 'clsx';
import { AlertOctagon, Check, Loader2, MessageSquareWarning } from 'lucide-react';

export type StatusPillState = 'done' | 'in-progress' | 'blocked' | 'needs-input';

export interface StatusPillProps {
  state: StatusPillState;
  /** Override the default human label. */
  label?: string;
  /** Override the auto-generated aria-label. */
  'aria-label'?: string;
  /** Default 'sm'; 'md' enlarges padding/text. */
  size?: 'sm' | 'md';
  className?: string;
}

const _LABELS: Record<StatusPillState, string> = {
  done: 'Done',
  'in-progress': 'In progress',
  blocked: 'Blocked',
  'needs-input': 'Needs input',
};

const _PALETTES: Record<StatusPillState, string> = {
  done: 'bg-emerald-100 text-emerald-800 border-emerald-300',
  'in-progress': 'bg-amber-100 text-amber-800 border-amber-300',
  blocked: 'bg-rose-100 text-rose-800 border-rose-300',
  'needs-input': 'bg-violet-100 text-violet-800 border-violet-300',
};

const _ICONS: Record<StatusPillState, React.ComponentType<{ className?: string }>> = {
  done: Check,
  'in-progress': Loader2,
  blocked: AlertOctagon,
  'needs-input': MessageSquareWarning,
};

export function StatusPill({
  state,
  label,
  'aria-label': ariaLabel,
  size = 'sm',
  className,
}: StatusPillProps): JSX.Element {
  const text = label ?? _LABELS[state];
  const aria = ariaLabel ?? `${_LABELS[state]} — agent status`;
  const Icon = _ICONS[state];

  const sizingClasses =
    size === 'md' ? 'px-2 py-1 text-xs gap-1.5' : 'px-1.5 py-0.5 text-[11px] gap-1';

  const iconSize = size === 'md' ? 'h-3.5 w-3.5' : 'h-3 w-3';

  return (
    <span
      role="status"
      aria-label={aria}
      data-status-state={state}
      className={clsx(
        'inline-flex items-center rounded-full border font-medium',
        sizingClasses,
        _PALETTES[state],
        className,
      )}
    >
      <Icon className={clsx(iconSize, 'flex-shrink-0')} aria-hidden="true" />
      {text}
    </span>
  );
}
