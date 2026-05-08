// CollapsiblePanel — Story 5.9 / AC #3.
//
// Shared panel chrome used by UBOPanel and RiskPanel. DocumentsPanel keeps
// its own header convention; this primitive is for the new panels only.
//
// Header is a button with aria-expanded for keyboard + screen-reader support.
// Body uses Framer Motion's AnimatePresence for the expand/collapse motion;
// reduced-motion suppresses the animation duration.

import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { type KeyboardEvent, type ReactNode, useId } from 'react';

export interface CollapsiblePanelProps {
  title: string;
  summary: string;
  tag?: ReactNode;
  expanded: boolean;
  onToggle: (next: boolean) => void;
  children: ReactNode;
  className?: string;
  /** Story 6.3 / AC #9 — `attention` adds a soft hero-tint for officer-attention panels. */
  tone?: 'default' | 'attention';
}

export function CollapsiblePanel({
  title,
  summary,
  tag,
  expanded,
  onToggle,
  children,
  className,
  tone = 'default',
}: CollapsiblePanelProps) {
  const reducedMotion = useReducedMotion();
  const bodyId = useId();
  const duration = reducedMotion ? 0 : 0.18;

  const handleKeyDown = (e: KeyboardEvent<HTMLButtonElement>) => {
    if (e.key === ' ' || e.key === 'Enter') {
      e.preventDefault();
      onToggle(!expanded);
    }
  };

  return (
    <section
      data-tone={tone}
      className={`rounded-md border px-4 py-3.5 ${
        tone === 'attention' ? 'border-amber-200 bg-amber-50/40' : 'border-zinc-200 bg-white'
      } ${className ?? ''}`}
    >
      <button
        type="button"
        aria-expanded={expanded}
        aria-controls={bodyId}
        onClick={() => onToggle(!expanded)}
        onKeyDown={handleKeyDown}
        className="flex w-full items-center justify-between gap-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-500 rounded"
        data-testid={`collapsible-panel-header-${title.toLowerCase().replace(/\s+/g, '-')}`}
      >
        <div className="flex items-center gap-2">
          <span aria-hidden="true" className="text-zinc-400 text-xs">
            {expanded ? '▼' : '▶'}
          </span>
          <span className="text-sm font-semibold text-zinc-900">{title}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-zinc-500">{summary}</span>
          {tag}
        </div>
      </button>

      <AnimatePresence initial={false}>
        {expanded ? (
          <motion.div
            id={bodyId}
            data-testid="collapsible-panel-body"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration }}
            className="overflow-hidden"
          >
            <hr className="my-3 border-zinc-100" />
            {children}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </section>
  );
}
