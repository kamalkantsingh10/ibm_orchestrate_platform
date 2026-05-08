// AgentFace — Story 4.3 AC #2/#3/#4.
//
// Stateless visual primitive. Renders the agent's static SVG face inside a
// Framer Motion wrapper whose variants encode the 5-state machine:
//   idle      — static
//   working   — subtle "breath" (1s cycle, ~4% scale)
//   complete  — one-shot glow (300 ms ease-out, settles back to idle)
//   blocked   — dimmed + small AlertTriangle overlay
//   needs_input — rotated −6° toward the analyst (visual focus pull)
//
// `useReducedMotion` is honored — animation degrades to a still image when
// the user has `prefers-reduced-motion: reduce` set.

import { motion, useReducedMotion } from 'framer-motion';
import { AlertTriangle } from 'lucide-react';
import { AGENT_LABELS, type AgentSlug } from './agentLabels';

export type { AgentSlug } from './agentLabels';
export type AgentFaceState = 'idle' | 'working' | 'complete' | 'blocked' | 'needs_input';

export interface AgentFaceProps {
  agent: AgentSlug;
  state: AgentFaceState;
  /** Edge length in pixels. Default 32. */
  size?: number;
  'aria-label'?: string;
  className?: string;
}

const _STATE_LABELS: Record<AgentFaceState, string> = {
  idle: 'Idle',
  working: 'Working',
  complete: 'Complete',
  blocked: 'Blocked',
  needs_input: 'Needs input',
};

export function AgentFace({
  agent,
  state,
  size = 32,
  'aria-label': ariaLabel,
  className = '',
}: AgentFaceProps): JSX.Element {
  const reduce = useReducedMotion();
  const label = ariaLabel ?? `${AGENT_LABELS[agent]} — ${_STATE_LABELS[state]}`;

  // Variants — selected by state. Reduced-motion users see the static
  // representative pose for each state (no infinite loops, no transforms).
  const variants = reduce
    ? {
        idle: { scale: 1, rotate: 0, opacity: 1 },
        working: { scale: 1, rotate: 0, opacity: 1 },
        complete: { scale: 1, rotate: 0, opacity: 1 },
        blocked: { scale: 1, rotate: 0, opacity: 0.5 },
        needs_input: { scale: 1, rotate: -6, opacity: 1 },
      }
    : {
        idle: { scale: 1, rotate: 0, opacity: 1 },
        working: {
          scale: [1, 1.04, 1],
          rotate: 0,
          opacity: 1,
          transition: { duration: 1, ease: 'easeInOut', repeat: Infinity },
        },
        complete: {
          scale: [1, 1.06, 1],
          rotate: 0,
          opacity: 1,
          transition: { duration: 0.3, ease: 'easeOut', times: [0, 0.4, 1] },
        },
        blocked: { scale: 1, rotate: 0, opacity: 0.5, transition: { duration: 0.15 } },
        needs_input: {
          scale: 1,
          rotate: -6,
          opacity: 1,
          transition: { duration: 0.3, ease: 'easeOut' },
        },
      };

  return (
    <motion.span
      role="img"
      aria-label={label}
      data-agent={agent}
      data-state={state}
      className={`relative inline-flex items-center justify-center text-zinc-700 ${className}`}
      style={{ width: size, height: size }}
      animate={state}
      variants={variants}
      // ``key`` forces the burst to restart cleanly when the parent toggles
      // between same-state values (e.g. complete → complete after re-render).
      key={state}
    >
      <img
        src={`/agent-faces/${agent}.svg`}
        alt=""
        aria-hidden="true"
        draggable={false}
        style={{ width: '100%', height: '100%' }}
      />
      {state === 'blocked' ? (
        <span
          aria-hidden="true"
          className="absolute -bottom-0.5 -right-0.5 rounded-full bg-white text-rose-600"
          style={{ width: size / 3, height: size / 3, padding: 1 }}
          data-testid="agent-face-blocked-overlay"
        >
          <AlertTriangle className="h-full w-full" />
        </span>
      ) : null}
    </motion.span>
  );
}
