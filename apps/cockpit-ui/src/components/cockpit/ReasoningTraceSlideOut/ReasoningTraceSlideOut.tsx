// ReasoningTraceSlideOut — Story 6.6 (refactored from Story 3.6 placeholder).
//
// Right-edge 480 px Radix Dialog drawer. Two modes:
//   * action mode (Story 6.6) — fetches the typed ReasoningTrace via Story
//     6.5's endpoint and renders the 4 fixed sections; embeds Story 6.3's
//     ScreeningExplainer cards when the action is the screening agent's.
//   * legacy mode (Story 3.6) — renders a 4-section placeholder body for
//     ProvenancePill clicks on Document Intelligence extracted fields.
//
// Mode resolution priority: actionId > extractedField > empty state.
//
// Demo simplifications (per Story 6.6):
//   * Use Radix Dialog's default `role="dialog"` + an `aria-label`. UX spec
//     says role="complementary" but Radix's dialog role gives focus-trap
//     ARIA semantics screen readers expect.
//   * Use only Radix's overlay for canvas dim — pairing it with a separate
//     `focusDim` motion would produce a stacked dim too dark for the
//     marble aesthetic.
//   * Skip the sticky-on-scroll header state — visual polish without
//     behavioural change.

import * as Dialog from '@radix-ui/react-dialog';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { X } from 'lucide-react';
import type { ReactNode } from 'react';
import type { components } from '@/api-types';
import { ConfidencePill } from '@/components/cockpit/ConfidencePill';
import { ScreeningExplainer } from '@/components/cockpit/ScreeningExplainer';
import { useReasoningTrace, type ReasoningTraceState } from '@/hooks/useReasoningTrace';
import { slideOut } from '@/lib/motion';

type AgentSlug = components['schemas']['AgentSlug'];
type ExtractedField = components['schemas']['ExtractedField'];
type ScreeningHit = components['schemas']['ScreeningHit'];

export interface ReasoningTraceSlideOutProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  // Action-driven path (Story 6.6).
  caseId?: string | null;
  actionId?: string | null;
  agentSlug?: AgentSlug | null;
  screeningHits?: ScreeningHit[] | null;
  // Legacy (Story 3.6) — preserved for backwards compatibility.
  extractedField?: ExtractedField | null;
}

const _AGENT_LABEL: Record<AgentSlug, string> = {
  'case-supervisor': 'Case Supervisor',
  'document-intelligence': 'Document Intelligence',
  'entity-verification': 'Entity Verification',
  'ubo-graph': 'UBO Graph',
  screening: 'Screening',
  'risk-scoring': 'Risk Scoring',
  writing: 'Writing',
  'cockpit-chat': 'Cockpit Chat',
};

export function ReasoningTraceSlideOut({
  open,
  onOpenChange,
  caseId,
  actionId,
  agentSlug,
  screeningHits,
  extractedField,
}: ReasoningTraceSlideOutProps) {
  const reducedMotion = useReducedMotion();
  const traceState = useReasoningTrace(caseId ?? null, actionId ?? null);
  const mode: 'action' | 'legacy' | 'empty' = actionId
    ? 'action'
    : extractedField
      ? 'legacy'
      : 'empty';

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <AnimatePresence>
        {open ? (
          <Dialog.Portal forceMount>
            <Dialog.Overlay asChild>
              <motion.div
                className="fixed inset-0 bg-black/20 motion-reduce:transition-none"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={reducedMotion ? { duration: 0 } : slideOut}
              />
            </Dialog.Overlay>
            <Dialog.Content asChild aria-label="Reasoning trace" aria-describedby={undefined}>
              <motion.div
                className="fixed right-0 top-0 bottom-0 w-[480px] bg-white shadow-2xl border-l border-zinc-200 flex flex-col"
                initial={{ x: 480, opacity: 0 }}
                animate={{ x: 0, opacity: 1 }}
                exit={{ x: 480, opacity: 0 }}
                transition={reducedMotion ? { duration: 0 } : slideOut}
              >
                <Header agentSlug={mode === 'action' ? (agentSlug ?? null) : null} />
                <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5" aria-live="polite">
                  {mode === 'action' ? (
                    <ActionBody
                      state={traceState}
                      agentSlug={agentSlug ?? null}
                      screeningHits={screeningHits ?? null}
                    />
                  ) : mode === 'legacy' && extractedField ? (
                    <LegacyBody field={extractedField} />
                  ) : (
                    <p className="text-sm text-zinc-500">Click a provenance pill to inspect.</p>
                  )}
                </div>
              </motion.div>
            </Dialog.Content>
          </Dialog.Portal>
        ) : null}
      </AnimatePresence>
    </Dialog.Root>
  );
}

function Header({ agentSlug }: { agentSlug: AgentSlug | null }) {
  return (
    <header className="flex items-center justify-between px-5 py-4 border-b border-zinc-200">
      <div className="flex items-center gap-3 min-w-0">
        <Dialog.Title className="text-sm font-semibold text-zinc-900">Reasoning trace</Dialog.Title>
        {agentSlug ? (
          <span
            data-testid="reasoning-trace-agent-tag"
            className="inline-flex items-center gap-1 rounded-full bg-zinc-100 px-2 py-0.5 text-xs font-medium text-zinc-700"
          >
            {_AGENT_LABEL[agentSlug]}
          </span>
        ) : null}
      </div>
      <div className="flex items-center gap-3">
        <span className="text-xs text-zinc-500">Esc to close</span>
        <Dialog.Close asChild>
          <button
            type="button"
            className="p-1 rounded hover:bg-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-400"
            aria-label="Close reasoning trace"
          >
            <X className="w-4 h-4 text-zinc-600" />
          </button>
        </Dialog.Close>
      </div>
    </header>
  );
}

function ActionBody({
  state,
  agentSlug,
  screeningHits,
}: {
  state: ReasoningTraceState;
  agentSlug: AgentSlug | null;
  screeningHits: ScreeningHit[] | null;
}) {
  if (state.status === 'pending') {
    return <PendingSkeleton />;
  }
  if (state.status === 'no-trace') {
    return (
      <EmptyState role="status">
        No trace produced — this action was deterministic and didn&rsquo;t emit a reasoning trace.
      </EmptyState>
    );
  }
  if (state.status === 'not-found') {
    return <EmptyState role="status">Action not found.</EmptyState>;
  }
  if (state.status === 'error') {
    return (
      <EmptyState role="alert">
        Failed to load trace. Try closing and reopening.
        <details className="mt-2 text-xs text-zinc-500">
          <summary>Details</summary>
          <pre className="whitespace-pre-wrap">{state.error.message}</pre>
        </details>
      </EmptyState>
    );
  }
  const { trace } = state;
  return (
    <>
      <Section title="What searched">
        <p className="text-sm text-zinc-700">{trace.what_searched}</p>
      </Section>
      <Section title="What hit">
        <p className="text-sm text-zinc-700 whitespace-pre-line">{trace.what_hit}</p>
        {agentSlug === 'screening' && screeningHits && screeningHits.length > 0 ? (
          <div className="mt-3 space-y-2">
            {screeningHits.map((hit) => (
              <ScreeningExplainer
                key={hit.hit_id}
                hit={hit}
                subjectName={hit.matched_name}
                onOpenSlideOut={() => {}}
              />
            ))}
          </div>
        ) : null}
      </Section>
      <Section title="Confidence">
        <ConfidencePill confidence={trace.confidence_self_rating.value} variant="panel-header" />
        <p className="mt-2 text-xs text-zinc-600">{trace.confidence_self_rating.rationale}</p>
      </Section>
      <Section title="What would change it" ariaLabel="What would change this conclusion">
        <p className="text-sm text-zinc-700">{trace.counterfactual}</p>
      </Section>
    </>
  );
}

function LegacyBody({ field }: { field: ExtractedField }) {
  return (
    <>
      <Section title="What was searched">
        <p className="text-sm text-zinc-700">
          Document: <code className="font-mono">{field.document_ref}</code>; field:{' '}
          <code className="font-mono">{field.field_name}</code>
        </p>
      </Section>
      <Section title="What returned">
        <p className="text-sm text-zinc-900 break-words">
          {field.value.value === null ? (
            <span className="text-zinc-400">—</span>
          ) : (
            String(field.value.value)
          )}
        </p>
      </Section>
      <Section title="Confidence">
        <ConfidencePill confidence={field.value.provenance.confidence} variant="panel-header" />
      </Section>
    </>
  );
}

function PendingSkeleton() {
  return (
    <div className="space-y-5" data-testid="reasoning-trace-skeleton">
      {['What searched', 'What hit', 'Confidence', 'What would change it'].map((title) => (
        <Section key={title} title={title}>
          <div className="space-y-1.5">
            <div className="h-3 w-full rounded bg-zinc-200 motion-safe:animate-pulse" />
            <div className="h-3 w-4/5 rounded bg-zinc-200 motion-safe:animate-pulse" />
            <div className="h-3 w-2/3 rounded bg-zinc-200 motion-safe:animate-pulse" />
          </div>
        </Section>
      ))}
    </div>
  );
}

function EmptyState({ children, role }: { children: ReactNode; role?: 'status' | 'alert' }) {
  return (
    <div
      role={role}
      className="rounded-md border border-zinc-200 bg-zinc-50 px-4 py-6 text-center text-sm text-zinc-600"
    >
      {children}
    </div>
  );
}

function Section({
  title,
  ariaLabel,
  children,
}: {
  title: string;
  ariaLabel?: string;
  children: ReactNode;
}) {
  return (
    <section aria-label={ariaLabel}>
      <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 mb-1.5">
        {title}
      </h3>
      {children}
    </section>
  );
}
